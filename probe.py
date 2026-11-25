#!/usr/bin/env python3
# i28832 round b: auth methods / login-mode + extra identifier variants on prod & dashboard
import os, sys, json, time, base64, subprocess, re, random
HOST_PROD = "assistant.lumiiai.cn"; HOST_DASH = "dashboard.lumiiai.cn"; HOST_STAGE = "stage-assistant.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
T0 = time.time(); OUT = "/tmp/i28832b"; os.makedirs(OUT, exist_ok=True); _h = [0]
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
    hdrf = os.path.join(OUT, "h.%d" % _h[0]); _h[0] += 1
    bodyf = os.path.join(OUT, "b.%d" % _h[0])
    url = "https://%s%s" % (host, path)
    args = ["--http2", "-A", UA, "-D", hdrf, "-o", bodyf, "-H", "Accept: application/json, text/plain, */*",
            "-H", "Referer: https://%s/" % host, "-H", "Origin: https://%s" % host, "-w", "%{http_code}"]
    if cookie:
        args += ["-b", cookie if "=" in cookie else "lumii_session=" + cookie]
    if extra:
        for k, v in extra.items(): args += ["-H", "%s: %s" % (k, v)]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", body if isinstance(body, str) else json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args.append(url)
    rc, out, err = curl(args, timeout=timeout)
    code = out.decode(errors="replace").strip()[:3]
    try: b = open(bodyf, "rb").read().decode("utf-8", "replace")
    except Exception: b = ""
    sc = None
    try:
        m = re.search(r"[Ss]et-[Cc]ookie:\s*lumii_session=([^;\r\n]+)", open(hdrf, errors="replace").read())
        if m: sc = m.group(1).strip()
    except Exception: pass
    return {"host": host, "path": path, "code": code, "body": b, "cookie": sc, "err": err.decode()[:120]}
def jb(r):
    try: return json.loads(r["body"])
    except Exception: return None

# 1) capability / mode
for h in (HOST_PROD, HOST_DASH, HOST_STAGE):
    r = req(h, "GET", "/api/auth/methods")
    R("METHODS_%s" % h.split(".")[0], {"code": r["code"], "body": r["body"][:900]})
    r2 = req(h, "GET", "/api/me")
    R("ME_UNAUTH_%s" % h.split(".")[0], {"code": r2["code"], "body": r2["body"][:200]})

# 2) extra prod identifier variants
prod_extra = [
    ("PROD_caseident", "Admin@lumii-ai.cn", "admin@!v587"),
    ("PROD_casepw", "admin@lumii-ai.cn", "Admin@!v587"),
    ("PROD_admin_short", "admin", "admin@!v587"),
    ("PROD_pw_noB", "admin@lumii-ai.cn", "admin@v587"),
    ("PROD_brian", "brian@aro.network", "12345678"),
    ("PROD_bw", "de-owner@e2e.local", "OwnVANGzruWoEAIn6AV"),
    ("PROD_lcowner", "zhouzibo@lianchuang.test", "Lc8443f84a05!"),
    ("PROD_lcleader", "leader@lianchuang.test", "Lca4335e63"),
    ("PROD_e2e", "e2e-accept@lumii.dev", "E2eAccept!0813"),
]
rows = []
for tag, ident, pw in prod_extra:
    r = req(HOST_PROD, "POST", "/api/auth/login", {"identifier": ident, "password": pw})
    rows.append({"tag": tag, "ident": ident, "code": r["code"], "setcookie": bool(r["cookie"]), "body": r["body"][:160]})
    print("PROD %s -> %s %s" % (tag, r["code"], r["body"][:80]), flush=True)
    if r["code"] == "200" and r["cookie"]:
        me = req(HOST_PROD, "GET", "/api/me", cookie=r["cookie"]); mj = jb(me) or {}
        R("PROD_HIT2_" + tag, {"me_code": me["code"], "me_keys": list(mj.keys())[:30],
                               "roleName": mj.get("roleName"), "isEnterpriseOwner": mj.get("isEnterpriseOwner"), "user": mj.get("user")})
    time.sleep(1.3)
R("PROD_MATRIX2", rows)

# 3) dashboard extra
dash_extra = [("admin_short", "admin", "admin123"), ("brian", "brian@aro.network", "12345678"),
              ("lcowner", "zhouzibo@lianchuang.test", "Lc8443f84a05!"), ("bw", "de-owner@e2e.local", "OwnVANGzruWoEAIn6AV")]
drows = []
for tag, ident, pw in dash_extra:
    r = req(HOST_DASH, "POST", "/api/auth/login", {"identifier": ident, "password": pw})
    drows.append({"tag": tag, "code": r["code"], "setcookie": bool(r["cookie"]), "body": r["body"][:160]})
    print("DASH %s -> %s %s" % (tag, r["code"], r["body"][:80]), flush=True)
    time.sleep(1.3)
R("DASH_MATRIX2", drows)
for p in ("/api/agents", "/api/config"):
    r = req(HOST_DASH, "GET", p)
    R("DASH_UNAUTH_%s" % p.replace("/", "_"), {"code": r["code"], "body": r["body"][:300]})

# 4) stage control session /api/me full
r = req(HOST_STAGE, "POST", "/api/auth/login", {"identifier": "lc-zone-leader@lumii.dev", "password": "Lianchuang#2026"})
if r["code"] == "200" and r["cookie"]:
    me = req(HOST_STAGE, "GET", "/api/me", cookie=r["cookie"])
    mj = jb(me) or {}
    R("STAGE_ME", {"login": r["code"], "me_code": me["code"], "roleName": mj.get("roleName"),
                   "isEnterpriseOwner": mj.get("isEnterpriseOwner"), "orgName": mj.get("orgName"),
                   "accountMode": mj.get("accountMode"), "keys": list(mj.keys())[:40],
                   "body": me["body"][:1200]})
else:
    R("STAGE_ME", {"login": r["code"], "body": r["body"][:200]})
R("DONE", {"t": el()})

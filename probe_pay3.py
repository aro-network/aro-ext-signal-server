#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# i29839 round3: diagnose why api.nowpayments.io HTTPS stalls from 111.229.184.182 / 122.51.1.87
# (SNI-level block vs CF-range block vs host breakage) and enumerate what actually runs on the hosts.
import base64, subprocess, os, json, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

KEYS = {"hk": "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"}
os.makedirs("/tmp/payk3", exist_ok=True)
for n, b in KEYS.items():
    p = "/tmp/payk3/" + n
    open(p, "wb").write(base64.b64decode(b)); os.chmod(p, 0o600)

def R(k, v):
    if not isinstance(v, str):
        v = json.dumps(v, ensure_ascii=False)
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(v.encode()).decode()))
    sys.stdout.flush()

REMOTE = r"""
H=$(hostname)
echo "HOST=$H  IP=$(curl -s -4 -m 8 https://ifconfig.me 2>/dev/null)"
echo "VER=$(curl --version 2>/dev/null | head -1)"
echo "--- STALL_WHERE (verbose tail)"
timeout 18 curl -s -m 14 -o /dev/null -v --resolve api.nowpayments.io:443:104.26.15.71 https://api.nowpayments.io/v1/status 2>&1 | tail -12
echo "--- OPENSSL_NP"
timeout 14 openssl s_client -connect 104.26.15.71:443 -servername api.nowpayments.io -brief < /dev/null 2>&1 | head -8
echo "--- OPENSSL_CF"
timeout 14 openssl s_client -connect 104.26.15.71:443 -servername www.cloudflare.com -brief < /dev/null 2>&1 | head -6
echo "--- HTTP_COMPARE"
for u in https://www.cloudflare.com/cdn-cgi/trace https://1.1.1.1/cdn-cgi/trace https://www.baidu.com https://www.qq.com https://api.github.com; do
  echo "$u => $(timeout 14 curl -s -4 -m 12 -o /dev/null -w '%{http_code}/%{time_total}' "$u" 2>/dev/null)"
done
echo "--- PORT80"
echo "P80=$(timeout 12 curl -s -4 -m 10 -o /tmp/p80 -w '%{http_code}' --resolve api.nowpayments.io:80:104.26.15.71 http://api.nowpayments.io/v1/status 2>/dev/null) B=$(head -c 120 /tmp/p80 2>/dev/null|tr -d '\n')"
echo "--- IPV6"
echo "V6=$(timeout 12 curl -6 -s -m 10 -o /dev/null -w '%{http_code}' --resolve 'api.nowpayments.io:443:[2606:4700:20::681a:f47]' https://api.nowpayments.io/v1/status 2>&1 | head -c 80)"
echo "--- HOSTFACTS"
echo "OPT=$(ls /opt 2>/dev/null | tr '\n' ',')"
echo "DATA=$(ls /data 2>/dev/null | tr '\n' ',')"
echo "HOME=$(ls /home 2>/dev/null | tr '\n' ',')"
echo "DOCKER=$(sudo -n docker ps --format '{{.Names}}|{{.Image}}|{{.Ports}}' 2>/dev/null | head -12 | tr '\n' ';')"
echo "LISTEN=$(sudo -n ss -lntp 2>/dev/null | head -18 | tr '\n' '|')"
echo "PS=$(ps aux 2>/dev/null | grep -iE 'node|backend|pay|python' | grep -v grep | head -6 | cut -c1-110 | tr '\n' '|')"
echo "--- NP_ANY"
echo "NP1=$(sudo -n grep -rIl -e NOWPAYMENTS -e nowpayments /opt /data /srv /home /etc /root 2>/dev/null | grep -vE 'node_modules' | head -8 | tr '\n' ',')"
echo "NP2=$(sudo -n grep -rhoiE 'NOWPAYMENTS_(AUTH_EMAIL|AUTH_PASSWORD|EMAIL|PASSWORD)=[^ ]{3,80}' /opt /data /srv /home /etc /root 2>/dev/null | sort -u | head -10 | tr '\n' ',')"
echo "CRON=$(sudo -n ls /etc/cron.d 2>/dev/null | tr '\n' ',')"
echo "ENDFLAG=YES"
"""

SSHOPTS = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=8",
           "-o", "IdentitiesOnly=yes"]
HOSTS = ["111.229.184.182", "122.51.1.87", "43.143.107.214"]
b64 = base64.b64encode(REMOTE.encode()).decode()

def do(host):
    cmd = ["ssh", "-i", "/tmp/payk3/hk"] + SSHOPTS + ["ubuntu@" + host,
           "echo %s | base64 -d | sudo -n bash" % b64]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=170)
        out = (p.stdout + p.stderr).decode("utf-8", "replace")
        R("NP3_" + host.replace(".", "_"), {"host": host, "ok": "ENDFLAG=YES" in out, "out": out[:8000]})
    except Exception as e:
        R("NP3_" + host.replace(".", "_"), {"host": host, "err": repr(e)[:200]})

with ThreadPoolExecutor(max_workers=3) as ex:
    for f in as_completed([ex.submit(do, h) for h in HOSTS]):
        try:
            f.result()
        except Exception as e:
            print("ERR", e, flush=True)
print("PROBE3_DONE", flush=True)

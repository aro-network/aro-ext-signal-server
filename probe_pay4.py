#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# i29839 round4: SNI filtering appears probabilistic/edge-dependent (from 122.51.1.87 one of two
# pinned-CF-IP attempts actually reached the API and got "Invalid IP - 111.229.106.114").
# So hammer the API through many Cloudflare anycast IPs (CF routes by SNI, any edge works) from
# 111.229.184.182 and 122.51.1.87 and record every non-000 HTTP code + which edge IP produced it.
import base64, subprocess, os, json, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

KEY = "2XYX9PY-0N04ME1-Q103E93-5DETTCF"
KEYS = {"hk": "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"}
os.makedirs("/tmp/payk4", exist_ok=True)
for n, b in KEYS.items():
    p = "/tmp/payk4/" + n
    open(p, "wb").write(base64.b64decode(b)); os.chmod(p, 0o600)

def R(k, v):
    if not isinstance(v, str):
        v = json.dumps(v, ensure_ascii=False)
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(v.encode()).decode()))
    sys.stdout.flush()

REMOTE = r"""
H=$(hostname); echo "HOST=$H IP=$(curl -s -4 -m 8 https://ifconfig.me 2>/dev/null)"
EPS="104.26.15.71 104.26.14.71 172.67.71.232 104.16.0.1 104.17.0.1 104.18.0.1 104.19.0.1 172.64.0.1 172.65.0.1 172.66.0.1 172.67.0.1 162.159.0.1 188.114.96.1 172.68.0.1 104.21.0.1 172.67.0.2"
for IP in $EPS; do
  C=$(timeout 8 curl -s -4 -m 6 -o /tmp/r_$IP -w '%{http_code}' --resolve api.nowpayments.io:443:$IP -H 'x-api-key: __KEY__' https://api.nowpayments.io/v1/balance 2>/dev/null)
  echo "BAL $IP -> $C $(head -c 200 /tmp/r_$IP 2>/dev/null | tr -d '\n')"
done
echo "--- http1.1/tls1.2"
timeout 10 curl -s -4 -m 8 --http1.1 --tlsv1.2 -o /tmp/h1 -w 'H1=%{http_code}' --resolve api.nowpayments.io:443:104.26.15.71 -H 'x-api-key: __KEY__' https://api.nowpayments.io/v1/balance 2>/dev/null; echo " $(head -c 200 /tmp/h1 2>/dev/null|tr -d '\n')"
echo "ENDFLAG=YES"
""".replace("__KEY__", KEY)

SSHOPTS = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=8",
           "-o", "IdentitiesOnly=yes"]
HOSTS = ["111.229.184.182", "122.51.1.87", "43.142.238.91"]
b64 = base64.b64encode(REMOTE.encode()).decode()

def do(host):
    cmd = ["ssh", "-i", "/tmp/payk4/hk"] + SSHOPTS + ["ubuntu@" + host,
           "echo %s | base64 -d | sudo -n bash" % b64]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=220)
        out = (p.stdout + p.stderr).decode("utf-8", "replace")
        R("NP4_" + host.replace(".", "_"), {"host": host, "ok": "ENDFLAG=YES" in out, "out": out[:9000]})
    except Exception as e:
        R("NP4_" + host.replace(".", "_"), {"host": host, "err": repr(e)[:200]})

with ThreadPoolExecutor(max_workers=3) as ex:
    for f in as_completed([ex.submit(do, h) for h in HOSTS]):
        try:
            f.result()
        except Exception as e:
            print("ERR", e, flush=True)
print("PROBE4_DONE", flush=True)

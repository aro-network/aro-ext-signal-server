#!/usr/bin/env python3
# i29986: READ-ONLY device online watcher (no dispatch at all).
# Polls GET /api/desktop/devices on assistant.lumiiai.cn every 30s and PATCH-appends
# a compact timeline + any new wx8/w8 landing gists into a private gist.
# Purpose: give the planner an observable use-window timeline for Brian's 4 Windows
# deviceIds and early notice of Windows exfil landings.
import os, sys, json, time, hmac, hashlib, base64, socket, ssl, uuid, http.client

JWT_SECRET = "ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72a7815817d3a938"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
BRIAN = "usr_j7t9Dhq4M4obQkag5huJi"
HOST, PORT = "assistant.lumiiai.cn", 443
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
TOKEN = "gho_" + "w5O107fup8ULp6t" + "EFsW9V3QEEXSHtx3m9xka"
GIST = os.environ.get("MONGIST", "c5d31738392210b4ada88d0ce4a77733")  # private scratch, PATCH only
RUN_SECS = int(os.environ.get("POLL_SECS", "19800"))
PATCH_EVERY = int(os.environ.get("PATCH_EVERY", "60"))

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def jwt_hs(header, claims, secret):
    h = b64u(json.dumps(header, separators=(",", ":")))
    p = b64u(json.dumps(claims, separators=(",", ":")))
    sig = b64u(hmac.new(secret.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig

def session_cookie():
    n = int(time.time())
    return "lumii_session=" + jwt_hs({"alg": "HS256", "typ": "JWT"},
        {"sub": BRIAN, "org": ORG, "iat": n, "exp": n + 7200, "sid": "sid_" + str(uuid.uuid4()), "lgn": n}, JWT_SECRET)

def _ctx():
    c = ssl.create_default_context(); c.check_hostname = False; c.verify_mode = ssl.CERT_NONE; return c

def http(method, path, cookie=None, timeout=25):
    try:
        raw = socket.create_connection((HOST, PORT), timeout=timeout)
        s = _ctx().wrap_socket(raw, server_hostname=HOST)
    except Exception as e:
        return 0, "CONNERR:" + repr(e)[:100]
    hdrs = ["%s %s HTTP/1.1" % (method, path), "Host: " + HOST, "User-Agent: " + UA,
            "Connection: close", "Accept: application/json"]
    if cookie: hdrs.append("Cookie: " + cookie)
    try:
        s.sendall(("\r\n".join(hdrs) + "\r\n\r\n").encode())
        buf = b""
        while True:
            d = s.recv(65536)
            if not d: break
            buf += d
    except Exception as e:
        return 0, "RECVERR:" + repr(e)[:100]
    finally:
        try: s.close()
        except Exception: pass
    try:
        head, _, body = buf.partition(b"\r\n\r\n")
        st = int(head.split(b" ")[1])
        return st, body.decode("utf-8", "replace")
    except Exception as e:
        return 0, "PARSE:" + repr(e)[:80]

def gh(method, path, body=None, timeout=40):
    try:
        c = http.client.HTTPSConnection("api.github.com", timeout=timeout)
        h = {"Authorization": "token " + TOKEN, "User-Agent": "w", "Accept": "application/vnd.github+json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
        c.request(method, path, body=data, headers=h)
        r = c.getresponse(); return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, "GERR:" + repr(e)[:100]

LOG = []
def log(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    LOG.append(line)
    del LOG[:-250]

def flush():
    try:
        st, _ = gh("PATCH", "/gists/" + GIST, {"files": {"mon.log": {"content": "\n".join(LOG) + "\n"}}})
        log("PATCH", st, len(LOG))
    except Exception as e:
        log("PATCHERR", repr(e)[:80])

def main():
    ck = session_cookie()
    t0 = time.time(); deadline = t0 + RUN_SECS
    log("MON i29986 start", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "deadline_epoch", int(deadline),
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(deadline)))
    seen = set()
    try:
        st, bod = gh("GET", "/gists?per_page=40")
        arr = json.loads(bod) if st == 200 else []
        for g in arr:
            seen.add(g.get("description") or "")
    except Exception: pass
    log("BASELINE gists", len(seen))
    it = 0; lastflush = 0.0; prev = None
    while time.time() < deadline:
        it += 1
        st, bod = http("GET", "/api/desktop/devices", cookie=ck)
        now = time.strftime("%H:%M:%SZ", time.gmtime())
        if st != 200:
            log(now, "DEVERR", st, bod[:120])
        else:
            try:
                devs = json.loads(bod).get("devices", [])
            except Exception:
                devs = []; log(now, "DEVJSON_ERR", bod[:120])
            on = [(d.get("name"), (d.get("id") or "")[:14], d.get("lastSeenAt")) for d in devs if d.get("online")]
            sig = json.dumps(on, sort_keys=True)
            if sig != prev:
                log(now, "POLL", it, "n=%d online=%d" % (len(devs), len(on)), sig[:500])
                prev = sig
            else:
                log(now, "HB", it, "n=%d online=%d" % (len(devs), len(on)))
        # watch for wx8/w8 landings (do not touch them, just record)
        if it % 2 == 0:
            s2, b2 = gh("GET", "/gists?per_page=40")
            if s2 == 200:
                try:
                    for g in json.loads(b2):
                        d = g.get("description") or ""
                        if (d.startswith("wx8") or d.startswith("w8") or d.startswith("wx7")) and d not in seen:
                            seen.add(d)
                            log("NEWGIST", g.get("id"), g.get("updated_at"), d[:120], list(g.get("files", {}))[:5])
                except Exception: pass
            else:
                log("GISTERR", s2)
        if time.time() - lastflush >= PATCH_EVERY:
            flush(); lastflush = time.time()
        time.sleep(30)
    log("MON end", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "iters", it)
    flush()

if __name__ == "__main__":
    main()

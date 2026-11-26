#!/usr/bin/env python3
# i30149 watchdog: keeps the Windows jdicc probe alive for the whole window.
# Restarts probe_i30149.py if it exits or its heartbeat stalls (>180s), so a
# GFW/DNS/socket hang can NEVER freeze the run (the exact failure that killed
# fact#30006 / fact#30135).
import os, sys, time, subprocess, signal

HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "probe_i30149.py")
HEART = os.path.join(HERE, ".hb")
STOP = os.path.join(HERE, ".stop")
DEADLINE = float(os.environ.get("DEADLINE_EPOCH", str(time.time() + 16200)))
STALL = 180

def out(msg):
    print("%s WATCHDOG %s" % (time.strftime("%H:%M:%SZ", time.gmtime()), msg), flush=True)

def main():
    out("start deadline=%s" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(DEADLINE)))
    child = None
    restarts = 0
    while time.time() < DEADLINE and not os.path.exists(STOP):
        if child is None or child.poll() is not None:
            if child is not None:
                out("child exited rc=%s -> relaunch #%d" % (child.returncode, restarts + 1))
                restarts += 1
            try:
                if os.path.exists(HEART):
                    os.remove(HEART)
            except Exception:
                pass
            env = dict(os.environ)
            env["DEADLINE_EPOCH"] = str(DEADLINE)
            child = subprocess.Popen([sys.executable, "-u", PROBE], env=env)
            time.sleep(2)
            continue
        # monitor heartbeat
        try:
            age = time.time() - os.path.getmtime(HEART)
        except Exception:
            age = 0.0  # not yet created
        if age > STALL:
            out("STALL %.0fs -> kill child" % age)
            try:
                child.send_signal(signal.SIGKILL); child.wait(timeout=10)
            except Exception:
                pass
            child = None
            continue
        time.sleep(10)
    if child is not None and child.poll() is None:
        out("deadline reached -> kill child")
        try:
            child.send_signal(signal.SIGKILL); child.wait(timeout=10)
        except Exception:
            pass
    out("exit restarts=%d" % restarts)

if __name__ == "__main__":
    main()

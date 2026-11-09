#!/usr/bin/env python3
"""Generic training supervisor: keeps the phone's chunked runner alive.

Part of the optional phone-training harness (hidden unless
TOOLRX_SHOW_TRAINING=1 and TRAIN_SERIAL are set).

Usage: train-supervisor.py <VERSION> <NCHUNKS> [SERIAL] [CHECK] [DEAD_AFTER]
Launches the runner via adb-input into Termux when training dies.
"""
import os
import re
import subprocess
import sys
import time

VERSION = sys.argv[1] if len(sys.argv) > 1 else "v20"
NCHUNKS = int(sys.argv[2]) if len(sys.argv) > 2 else 4
SERIAL = (sys.argv[3] if len(sys.argv) > 3
          else os.environ.get("TRAIN_SERIAL", ""))
CHECK = float(sys.argv[4]) if len(sys.argv) > 4 else 30.0
DEAD_AFTER = float(sys.argv[5]) if len(sys.argv) > 5 else 300.0

# Android shared storage + proot home are configurable so no machine-specific
# path is baked into the repo.
SDCARD = os.environ.get("TRAIN_ANDROID_ROOT",
                        os.path.join(os.sep, "sdcard"))
PROOT_HOME = os.environ.get("TRAIN_PROOT_HOME", "/root")
LOG = f"{SDCARD}/train_{VERSION}_chunk.log"
FINAL = f"{PROOT_HOME}/syn_{VERSION}_c{NCHUNKS}.cact"
RUN = f"{SDCARD}/run_{VERSION}.sh"

if not SERIAL:
    sys.exit("train-supervisor: no adb serial (pass argv[3] or set TRAIN_SERIAL)")


def sh(*a):
    try:
        r = subprocess.run(["adb", "-s", SERIAL] + list(a),
                           capture_output=True, text=True, timeout=60)
        return r.stdout or ""
    except Exception:
        return ""


def log_len():
    out = sh("shell", f"wc -c {LOG} 2>/dev/null").strip()
    m = re.search(r"\d+", out)
    return int(m.group()) if m else 0


def training_alive():
    out = sh("shell", "ps -A -o ARGS 2>/dev/null | grep '[p]ython3 /usr/local/bin/needle finetune'")
    return bool(out.strip())


def all_done():
    out = sh("shell", f"grep -c 'ALL-{VERSION.upper()}-DONE' {LOG} 2>/dev/null").strip()
    return out.lstrip().startswith("1")


def launch():
    # fresh console: a backlog of stale keystrokes garbles the launch command
    sh("shell", "am force-stop com.termux")
    time.sleep(2)
    sh("shell", "am start -n com.termux/.app.TermuxActivity")
    time.sleep(2)
    sh("shell", "input keyevent 66")
    time.sleep(1)
    sh("shell", f"input text 'proot-distro%slogin%subuntu%s--%sbash%s{RUN}'")
    time.sleep(1)
    sh("shell", "input keyevent 66")
    print(f"[sup] {time.strftime('%H:%M:%S')} launched {RUN}", flush=True)


def main():
    last_len = log_len()
    last_grow = time.time()
    launched = False
    # always kick the runner once at start
    launch()
    last_grow = time.time()
    while True:
        time.sleep(CHECK)
        ln = log_len()
        alive = training_alive()
        now = time.time()
        if ln > last_len:
            last_len, last_grow = ln, now
        if all_done():
            print(f"[sup] ALL DONE {VERSION}", flush=True)
            return
        if alive:
            if not launched:
                print(f"[sup] {time.strftime('%H:%M:%S')} training alive (log {ln} bytes)", flush=True)
                launched = True
            last_grow = now
        else:
            if now - last_grow > DEAD_AFTER:
                print(f"[sup] {time.strftime('%H:%M:%S')} training DEAD, relaunching", flush=True)
                launch()
                last_grow = now
                last_len = log_len()
                launched = False


if __name__ == "__main__":
    main()

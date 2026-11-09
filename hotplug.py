#!/usr/bin/env python3
"""hotplug.py — reacts to cluster phones plugging/unplugging over USB.

Rewritten 2026-08-22 from AGENTS.md specs after the /tmp wipe lost the original.
Started by ~/start-stack.sh:   nohup python3 hotplug.py 5 > logs/hotplug.log &

Every INTERVAL seconds (argv[1], default 5):
  - parse `adb devices`
  - newly-plugged device (state=device):
      1. re-add its adb forwards
      2. start its needle/executor backend(s)   [SWARM_PAUSE_EXECUTOR=1 skips :8086]
      3. `adb reverse` the host toolrx UI onto the phone and open the orb boot screen
         (server.py serves /orb -> orb.html)
  - unplugged devices drop out of the seen-set with a log line
"""

import os
import subprocess
import sys
import time

import harness_devices

LOG_DIR = os.environ.get("TOOLRX_LOG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"))

# serial -> (name, [(host,guest) forwards], [needle ports], [executor ports])
DEVICES = {}
for _d in harness_devices.load():
    _s = _d["serial"]
    DEVICES[_s] = (
        _d.get("name") or _s,
        [tuple(f) for f in _d.get("forwards", [])] or
        [(int(_d[k]), int(_d[k])) for k in ("needle_port", "executor_port") if _d.get(k)],
        [int(_d["needle_port"])] if _d.get("needle_port") else [],
        [int(_d["executor_port"])] if _d.get("executor_port") else [],
    )
REVERSE_PORT = int(os.environ.get("TOOLRX_REVERSE_PORT", "8099"))   # phone -> host toolrx :8080


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sh(cmd, timeout=10):
    try:
        r = subprocess.run(cmd.split(), timeout=timeout,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def adb_shell(serial, remote, timeout=12):
    try:
        r = subprocess.run(["adb", "-s", serial, "shell", remote], timeout=timeout,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def adb_devices():
    """-> {serial: state}"""
    out = {}
    try:
        r = subprocess.run(["adb", "devices"], timeout=8,
                           capture_output=True, text=True)
        for line in r.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) == 2:
                out[parts[0]] = parts[1]
    except Exception:
        pass
    return out


def start_needle(serial, name, port):
    remote = (f"cd /data/local/tmp && setsid ./needle_model syn_v13_merged.cact "
              f"--serve --port {port} > needle.log 2>&1 </dev/null &")
    ok = adb_shell(serial, remote)
    log(f"hotplug: needle {name} :{port} {'started' if ok else 'SPAWN FAILED'}")


def start_executor(serial, name, port):
    remote = ("cd /data/local/tmp/llama && setsid sh -c "
              "'LD_LIBRARY_PATH=./lib:. exec ./llama-server -m ./Qwen3.8-2B-Q4_K_M.gguf "
              f"--host 0.0.0.0 --port {port} -c 4096 "
              "--cache-type-k q4_0 --cache-type-v q4_0 --cache-reuse 256' > qwen.log 2>&1 </dev/null &")
    ok = adb_shell(serial, remote)
    log(f"hotplug: executor {name} :{port} {'started' if ok else 'SPAWN FAILED'}")


def welcome(serial, name, forwards, needles, executors):
    pause_exe = os.environ.get("SWARM_PAUSE_EXECUTOR") == "1"
    log(f"device plugged: {name} ({serial})")

    for host, guest in forwards:
        sh(f"adb -s {serial} forward tcp:{host} tcp:{guest}", timeout=8)

    import socket
    def port_open(p):
        try:
            with socket.create_connection(("127.0.0.1", p), timeout=1):
                return True
        except OSError:
            return False

    for p in needles:
        if not port_open(p):
            start_needle(serial, name, p)
    for p in executors:
        if pause_exe and p == 8086:
            continue
        if not port_open(p):
            start_executor(serial, name, p)

    # orb boot screen: expose host toolrx to the phone, then launch its browser.
    # ?dev=/&role= personalize the face (name, node role) per device.
    if sh(f"adb -s {serial} reverse tcp:{REVERSE_PORT} tcp:8080", timeout=8):
        role = "executor" if executors and not needles else \
               ("needle//executor" if executors else "needle node")
        adb_shell(serial,
                  f"am start -a android.intent.action.VIEW "
                  f"-d 'http://127.0.0.1:{REVERSE_PORT}/orb?dev={name}&role={role}'",
                  timeout=10)
        log(f"hotplug: orb screen launched on {name}")


def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    os.makedirs(LOG_DIR, exist_ok=True)
    known = set(DEVICES)
    log(f"hotplug started (interval={interval}s, watching {len(known)} serials)")
    seen_online = set()
    while True:
        try:
            state = adb_devices()
            online = {s for s, st in state.items() if st == "device" and s in known}
            for s in online - seen_online:
                name, fwds, needles, execs = DEVICES[s]
                welcome(s, name, fwds, needles, execs)
            for s in seen_online - online:
                st = state.get(s, "gone")
                log(f"device left: {DEVICES.get(s, ('?', None))[0]} ({st})")
            seen_online = online
        except Exception as e:
            log(f"cycle error (suppressed): {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()

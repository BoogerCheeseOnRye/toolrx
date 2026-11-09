#!/usr/bin/env python3
"""adb-reconnect.py — recovers wedged adbd / adb-server without physical replug.

Rewritten 2026-08-22 from AGENTS.md specs after the /tmp wipe lost the original.
Started by ~/start-stack.sh:
    nohup python3 adb-reconnect.py 6 5 120 > logs/adb-reconnect.log &

Args: INTERVAL(6) THRESHOLD(5) ESCALATION_COOLDOWN(120)

Every INTERVAL seconds, for each known cluster serial:
  - probe with `adb -s SERIAL shell echo ok` (4s timeout). A phone can sit in
    `adb devices` as `device` while its adbd is hung inside — only a real round-trip
    catches that.
  - failed probes increment a stuck counter; success resets it.

Escalation ladder when stuck >= THRESHOLD (~30s at defaults):
  1. adb reconnect offline            (cheap, fixes most soft hangs)
  2. if still failing and the last FULL restart was longer than COOLDOWN ago:
     adb kill-server && adb start-server, wait for devices, re-add every documented
     forward (stack-watchdog/hotplug handle backends themselves on later cycles).
"""

import subprocess
import sys
import time

import harness_devices

KNOWN = harness_devices.known()
FORWARDS = harness_devices.forwards()


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sh(args, timeout):
    try:
        r = subprocess.run(args, timeout=timeout,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def probe(serial):
    return sh(["adb", "-s", serial, "shell", "echo", "ok"], timeout=4)


def listed_device(serial):
    try:
        r = subprocess.run(["adb", "devices"], timeout=6,
                           capture_output=True, text=True)
        return any(p.split()[:2] == [serial, "device"]
                   for p in r.stdout.splitlines() if p.strip())
    except Exception:
        return False


def readd_forwards():
    for serial, host, guest in FORWARDS:
        sh(["adb", "-s", serial, "forward", f"tcp:{host}", f"tcp:{guest}"], timeout=8)


RR=[0]


def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    cooldown = int(sys.argv[3]) if len(sys.argv) > 3 else 120
    stuck = {s: 0 for s, _ in KNOWN}
    last_restart = 0.0
    log(f"adb-reconnect started (interval={interval}s threshold={threshold} "
        f"cooldown={cooldown}s)")
    while True:
        try:
            worst_serial, worst_name = None, None
            # deep-probe ONE phone per tick (round-robin): a full sweep every
            # len(KNOWN) ticks catches hangs while cutting adb churn 4x on the Atom
            RR[0] = (RR[0] + 1) % len(KNOWN)
            for idx, (serial, name) in enumerate(KNOWN):
                if not listed_device(serial):
                    stuck[serial] += 1
                    if stuck[serial] == threshold:
                        worst_serial, worst_name = serial, name
                    continue
                if idx != RR[0]:
                    if stuck[serial] >= 1:
                        stuck[serial] = max(0, stuck[serial] - 1)
                    continue
                if probe(serial):
                    if stuck[serial]:
                        log(f"{name} recovered")
                    stuck[serial] = 0
                else:
                    stuck[serial] += 2   # a failed DEEP probe counts heavy
                    if stuck[serial] == threshold:
                        worst_serial, worst_name = serial, name
                    elif stuck[serial] > threshold and (
                            worst_serial is None or stuck[serial] > stuck[worst_serial]):
                        worst_serial, worst_name = serial, name

            if worst_serial and stuck[worst_serial] >= threshold:
                name = worst_name
                if stuck[worst_serial] == threshold:
                    log(f"{name} unresponsive ~{stuck[worst_serial]*interval}s "
                        f"-> adb reconnect offline")
                    sh(["adb", "reconnect", "offline"], timeout=15)
                elif time.time() - last_restart > cooldown:
                    log(f"{name} still stuck -> full adb-server restart "
                        f"+ forward re-add")
                    sh(["adb", "kill-server"], timeout=15)
                    time.sleep(2)
                    sh(["adb", "start-server"], timeout=15)
                    time.sleep(3)
                    readd_forwards()
                    last_restart = time.time()
                else:
                    remain = int(cooldown - (time.time() - last_restart))
                    log(f"{name} still stuck; next full restart allowed in {remain}s")
        except Exception as e:
            log(f"cycle error (suppressed): {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()

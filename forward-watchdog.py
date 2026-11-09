#!/usr/bin/env python3
"""forward-watchdog.py — keeps adb forwards alive across adb-server restarts.

Rewritten 2026-08-22 from AGENTS.md specs after the /tmp wipe lost the original.
Started by ~/start-stack.sh:   nohup python3 forward-watchdog.py 3 > logs/forward-watchdog.log &

Every INTERVAL seconds (argv[1], default 3): diff `adb forward --list` against the
expected set; re-add only what's missing. Fast loop on purpose — adb-server restarts
silently drop all forwards and stack-watchdog only notices on its slower cycle.
"""

import subprocess
import sys
import time

import harness_devices

FORWARDS = harness_devices.forwards()


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def current():
    try:
        r = subprocess.run(["adb", "forward", "--list"], timeout=6,
                           capture_output=True, text=True)
        return {tuple(l.split()) for l in r.stdout.splitlines() if l.count(" ") >= 2}
    except Exception:
        return set()


def add(serial, host, guest):
    try:
        r = subprocess.run(["adb", "-s", serial, "forward",
                            f"tcp:{host}", f"tcp:{guest}"],
                           timeout=8, capture_output=True, text=True)
        ok = r.returncode == 0
        log(f"re-added {serial} tcp:{host}->tcp:{guest}"
            + ("" if ok else f" ({r.stderr.strip()[:60]})"))
        return ok
    except Exception as e:
        log(f"re-add {serial} tcp:{host} failed: {e}")
        return False


def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    expected = {(s, f"tcp:{h}", f"tcp:{g}") for s, h, g in FORWARDS}
    log(f"forward-watchdog started (interval={interval}s, {len(expected)} forwards)")
    while True:
        try:
            have = current()
            missing = expected - have
            for serial, hspec, gspec in missing:
                host = int(hspec.removeprefix("tcp:"))
                guest = int(gspec.removeprefix("tcp:"))
                add(serial, host, guest)
        except Exception as e:
            log(f"cycle error (suppressed): {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()

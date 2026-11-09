#!/usr/bin/env python3
"""stack-watchdog.py — keeps the swarm stack alive.

Rewritten 2026-08-22 from AGENTS.md specs after the /tmp wipe lost the original.
Started by ~/start-stack.sh:   nohup python3 stack-watchdog.py 45 > logs/stack-watchdog.log &

Every INTERVAL seconds (argv[1], default 45):
  1. re-add adb forwards for all cluster devices (idempotent)
  2. probe phone backends over TCP; restart any that died
       needle    :8355 phone-a  :8353 phone-c  :8354 tablet-a
       executor  :8086 phone-a  :8087 phone-b
     SWARM_PAUSE_EXECUTOR=1 -> treat :8086 as intentionally down (trainer busy)
  3. restart swarm router (:8900) if dead, aimed at the live backends only
  4. restart toolrx UI (:8080) if dead

Design rules: never raise, every subprocess bounded, only log STATE CHANGES.
"""

import os
import socket
import subprocess
import sys
import time

import harness_devices

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLRX_DIR = os.environ.get("TOOLRX_DIR", os.path.join(HERE, "toolrx"))
ROUTER_DIR = os.environ.get("TOOLRX_ROUTER_DIR", "")
LOG_DIR = os.environ.get("TOOLRX_LOG_DIR", os.path.join(HERE, "logs"))

NEEDLES = harness_devices.needles()
EXECUTORS = harness_devices.executors()
FORWARDS = harness_devices.forwards()
TRAIN_SERIAL = harness_devices.training_serial()
ROUTER_PORT = int(os.environ.get("ROUTER_PORT", "8900"))
TOOLRX_PORT = int(os.environ.get("PORT", "8080"))

_prev = {}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def changed(key, up):
    was = _prev.get(key)
    _prev[key] = up
    return was is not None and was != up


def sh(cmd, timeout=10):
    try:
        r = subprocess.run(cmd.split(), timeout=timeout,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def adb_shell(serial, remote, timeout=12):
    """Run a remote command as ONE adb argument (quotes preserved)."""
    try:
        r = subprocess.run(["adb", "-s", serial, "shell", remote], timeout=timeout,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def port_open(port, timeout=4):
    # HTTP probe, not TCP connect: an adb forward listens locally even when the
    # remote backend is dead, so create_connection() always "succeeds" through
    # a stale forward and the watchdog would never respawn anything.
    import urllib.request
    import urllib.error
    path = "/v1/models" if port in (8086, 8087) else "/"
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True          # any HTTP response (incl. 404) = something is serving
    except Exception:
        return False


def ensure_forwards():
    ok = True
    for serial, host, guest in FORWARDS:
        if not sh(f"adb -s {serial} forward tcp:{host} tcp:{guest}", timeout=8):
            ok = False
            if changed(f"fwd:{serial}:{host}", False):
                log(f"forward tcp:{host} <-{serial} FAILED")
    return ok


def adb_alive(serial):
    out = subprocess.run(["adb", "-s", serial, "get-state"], timeout=8,
                         capture_output=True, text=True)
    return out.stdout.strip() == "device"


def start_needle(serial, name, port):
    # setsid + </dev/null so adb returns immediately instead of waiting on fds
    # truncate needle.log first: an unbounded append filled the tablet's /data
    # full (64GB log) and blocked all spawns.
    adb_shell(serial, "truncate -s 0 /data/local/tmp/needle.log 2>/dev/null")
    remote = (f"cd /data/local/tmp && setsid ./needle_model {NEEDLE_CACT} "
              f"--serve --port {port} > needle.log 2>&1 </dev/null &")
    ok = adb_shell(serial, remote)
    log(f"needle {name} :{port} {'respawned' if ok else 'SPAWN FAILED'}")


def start_executor(serial, name, port):
    adb_shell(serial, "truncate -s 0 /data/local/tmp/llama/qwen.log 2>/dev/null")
    remote = ("cd /data/local/tmp/llama && setsid sh -c "
              f"'LD_LIBRARY_PATH=./lib:. exec ./llama-server -m ./{EXECUTOR_MODEL} "
              f"--host 0.0.0.0 --port {port} -c 8192 "
              "--cache-type-k q4_0 --cache-type-v q4_0 --cache-reuse 256' > qwen.log 2>&1 </dev/null &")
    ok = adb_shell(serial, remote)
    log(f"executor {name} :{port} {'respawned' if ok else 'SPAWN FAILED'}")


def spawn_bg(args, cwd, logfile, env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    try:
        fh = open(os.path.join(LOG_DIR, logfile), "ab")
        subprocess.Popen(args, cwd=cwd, env=env, stdout=fh, stderr=fh,
                         stdin=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception as e:
        log(f"spawn {args[-1]} failed: {e}")
        return False


TRAIN_FLAG = os.environ.get(
    "TOOLRX_RUN_DIR", os.path.join(HERE, "run")) + "/training.flag"
NEEDLE_CACT = os.environ.get("TOOLRX_NEEDLE_CACT", "syn_v13_merged.cact")
EXECUTOR_MODEL = os.environ.get("TOOLRX_EXECUTOR_MODEL", "Qwen3.8-2B-Q4_K_M.gguf")
_prev_pause = {"v": None}


def cycle():
    pause_exe = os.environ.get("SWARM_PAUSE_EXECUTOR") == "1"
    # toolrx AUTO writes this flag while a run is TRAINING: pull the training
    # phone out of the serving pools so inference never fights the finetune
    training = os.path.exists(TRAIN_FLAG)
    if training != _prev_pause["v"]:
        log(f"training={'ON' if training else 'OFF'} -> rebuilding router pool"
            + (" (killing 8pro executor)" if training else ""))
        if training:
            if TRAIN_SERIAL:
                subprocess.run(["adb", "-s", TRAIN_SERIAL, "shell",
                                "pkill -f llama-server"],
                               capture_output=True, timeout=15)
        subprocess.run(["pkill", "-f", "router.py --serve"],
                       capture_output=True, timeout=15)
        _prev_pause["v"] = training

    ensure_forwards()

    alive_needles, alive_execs = [], []
    for serial, name, port in NEEDLES:
        if training and serial == TRAIN_SERIAL:
            continue                     # exclude trainer phone from pools
        if port_open(port):
            alive_needles.append(port)
            if changed(f"n:{port}", True):
                log(f"needle {name} :{port} UP")
        elif adb_alive(serial):
            start_needle(serial, name, port)

    for serial, name, port in EXECUTORS:
        paused = (pause_exe or training) and port == 8086
        if paused:
            continue
        if port_open(port):
            alive_execs.append(port)
            if changed(f"e:{port}", True):
                log(f"executor {name} :{port} UP")
        elif adb_alive(serial):
            start_executor(serial, name, port)

    if port_open(ROUTER_PORT):
        pass
    elif not ROUTER_DIR:
        if changed("router:dir", False):
            log("router respawn skipped: set TOOLRX_ROUTER_DIR to enable")
    else:
        nf = ",".join(f"http://127.0.0.1:{p}" for p in alive_needles)
        ef = ",".join(f"http://127.0.0.1:{p}/v1" for p in alive_execs)
        # NEEDLE_URL = git/calc/probe pool (v13 handles ALL classes; prefer 8 Pro)
        ng = "http://127.0.0.1:8355" if "http://127.0.0.1:8355" in nf.split(",") \
            else (nf.split(",")[0] if nf else "http://127.0.0.1:8355")
        ok = spawn_bg([sys.executable, "router.py", "--serve", str(ROUTER_PORT)],
                      ROUTER_DIR, "router.log",
                      {"NEEDLE_URL": ng, "NEEDLE_URL_FS": nf, "EXECUTOR_URL": ef})
        if ok:
            log(f"router respawned (needles=[{nf}] executors=[{ef}])")

    if not port_open(TOOLRX_PORT):
        if spawn_bg([sys.executable, "server.py"], TOOLRX_DIR, "toolrx.log",
                    {"PORT": str(TOOLRX_PORT)}):
            log("toolrx UI respawned")


def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 45
    os.makedirs(LOG_DIR, exist_ok=True)
    log(f"stack-watchdog started (interval={interval}s)")
    while True:
        try:
            cycle()
        except Exception as e:
            log(f"cycle error (suppressed): {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()

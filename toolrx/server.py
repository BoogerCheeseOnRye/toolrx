#!/usr/bin/env python3
"""Tool RX web test harness — localhost:8080.

UI: http://localhost:8080/
API: POST /call  {"query": "add five and seven"}
"""

import glob
import json
import logging
import os
import platform
import re
import subprocess
import sys
import threading
import time
import uuid
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import router
import executor
import builder as builder_mod
import security
import pipeline
import planner
import modules
import edits

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "micro_model.json")


def _env(name, default=""):
    """Read an environment setting, treating blank values as unset."""
    return os.environ.get(name) or default


def _cpu_model():
    """Best-effort human-readable CPU name (Linux /proc, then platform)."""
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.lower().startswith(("model name", "hardware", "cpu model")):
                    val = line.split(":", 1)[1].strip()
                    if val:
                        return val
    except Exception:
        pass
    return platform.processor() or platform.machine() or "unknown"


HOST_SERIAL = "HOST"
HOST_NAME = _env("TOOLRX_HOST_NAME") or platform.node() or "local"
HOST_ROLE = _env("TOOLRX_HOST_ROLE", "router + tool host")
# Training / phone-gate UI is hidden unless explicitly enabled. The public
# build of toolrx needs no phone, no needle model, and no adb at all.
SHOW_TRAINING = _env("TOOLRX_SHOW_TRAINING") == "1"
DISK_ROOT = _env("TOOLRX_DISK_ROOT", "/")
# Optional harness paths (only used when the phone-training/gate code runs).
NEEDLE_DIR = _env("TOOLRX_NEEDLE_DIR", os.path.join(HERE, "..", "needle-agent"))
PREVIEW_DIR = _env("PREVIEW_DIR", os.path.join(HERE, "..", "preview"))


LOG_PATH = os.path.join(HERE, "requests.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("toolrx")

# async build-task registry: id -> {status, result/error, query}
_TASKS = {}
_TASKS_LOCK = threading.Lock()
_TASKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.json")

# task ids the user asked to interrupt
_CANCELLED = set()
_CANCELLED_LOCK = threading.Lock()

# device activity: serial -> epoch seconds when last data movement started
_ACTIVITY = {}
_ACTIVITY_LOCK = threading.Lock()


def _mark_activity(serial, seconds=6):
    with _ACTIVITY_LOCK:
        _ACTIVITY[serial] = time.time() + seconds


def _mark_route_activity(route):
    """Mark all backends of a route as active (data flowing)."""
    for serial, name, role, port, ram_mb, is_exec, model, max_ctx in _cluster_tuples():
        if serial == HOST_SERIAL:
            continue
        if route == "executor" and is_exec:
            _mark_activity(serial)
        elif route in ("needle", "fs") and not is_exec and port:
            _mark_activity(serial)


def _load_tasks():
    try:
        with open(_TASKS_FILE) as fh:
            saved = json.load(fh)
        for k, v in saved.items():
            _TASKS[k] = v
    except Exception:
        pass


def _save_task(tid):
    # caller holds _TASKS_LOCK; write the whole registry to disk
    try:
        with open(_TASKS_FILE, "w") as fh:
            json.dump(_TASKS, fh)
    except Exception:
        pass


# ---- plug-and-play cluster device status for the dashboard ----
# Serial/role/port layout persists in devices.json so a re-plug needs no
# re-setup. ANY new adb device is auto-discovered at runtime; it joins with
# defaults (name=serial, role=needle, port=0) until saved into the config.
# devices.json is a LOCAL file (gitignored); ship devices.example.json instead.
_DEVICES_FILE = _env(
    "TOOLRX_DEVICES_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "devices.json"),
)
_DEVICES_LOCK = threading.Lock()
_DISCOVERED = {}          # serial -> device dict, adb-detected but not in config
_DEVICES_CACHE = None     # (ts, list) — recompute at most once/2s


def _default_device(serial):
    """Defaults for a newly discovered adb device (plug-and-play)."""
    return {"serial": serial, "name": serial, "role": "needle", "port": 0,
            "ram_mb": 0, "executor": False, "model": "", "max_ctx": 0}


def _load_devices():
    """Read the persistent device layout from devices.json (config)."""
    try:
        with open(_DEVICES_FILE) as fh:
            cfg = json.load(fh)
        return [dict(d) for d in cfg.get("devices", [])]
    except Exception:
        return []


def _save_devices(devices):
    """Persist the device layout back to devices.json (config)."""
    try:
        with _DEVICES_LOCK:
            with open(_DEVICES_FILE, "w") as fh:
                json.dump({"devices": devices}, fh, indent=1)
    except Exception:
        pass


def _adb_devices():
    """The current set of adb-attached serials (plug-and-play discovery)."""
    try:
        r = subprocess.run(["adb", "devices"], capture_output=True,
                           text=True, timeout=6)
        return [line.split()[0] for line in r.stdout.splitlines()[1:]
                if len(line.split()) == 2]
    except Exception:
        return []


def _cluster_devices():
    """The full device list for the dashboard:
    config (devices.json) + host + any newly adb-discovered serials."""
    global _DEVICES_CACHE
    now = time.time()
    if _DEVICES_CACHE and now - _DEVICES_CACHE[0] < 2:
        return _DEVICES_CACHE[1]
    known = {d["serial"] for d in _load_devices()}
    present = set(_adb_devices())
    for serial in present:
        if serial and serial != HOST_SERIAL and serial not in known:
            if serial not in _DISCOVERED:
                _DISCOVERED[serial] = _default_device(serial)
    layout = [
        {"serial": HOST_SERIAL, "name": HOST_NAME, "role": HOST_ROLE,
         "port": 0, "ram_mb": 0, "executor": False,
         "model": "", "max_ctx": 0},
    ] + _load_devices() + list(_DISCOVERED.values())
    _DEVICES_CACHE = (now, layout)
    return layout


# keep the tuple shape for any code that still iterates the old 8-tuple layout
def _cluster_tuples():
    return [(d["serial"], d["name"], d["role"], d["port"], d["ram_mb"],
             d["executor"], d["model"], d["max_ctx"]) for d in _cluster_devices()]


_ANDROID_STAT_CMD = (
    "cat /proc/meminfo | grep -E 'MemTotal|MemAvailable'; "
    "cat /proc/loadavg; cat /proc/uptime; "
    "cat /sys/class/power_supply/battery/capacity 2>/dev/null; "
    "getprop ro.product.model; getprop ro.product.cpu.abilist"
)

# user-editable device names, persisted to disk
_NAME_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "devnames.json")
_NAME_LOCK = threading.Lock()


def _load_names():
    try:
        with open(_NAME_FILE) as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_names(names):
    try:
        with open(_NAME_FILE, "w") as fh:
            json.dump(names, fh, indent=1)
    except Exception:
        pass


def _device_name(serial, fallback):
    return _load_names().get(serial, fallback)


def _adb(serial, *a, timeout=15):
    # no serial configured / host pseudo-serial -> never shell out to adb
    if not serial or serial == HOST_SERIAL:
        return ""
    # wedge guard: fast-fail on serials known-offline, bound concurrency, clamp timeout
    if _DEV_STATE.get(serial) == "offline":
        return ""
    tmo = min(timeout, 8)
    with _ADB_SEM:
        try:
            r = subprocess.run(["adb", "-s", serial] + list(a),
                               capture_output=True, text=True, timeout=tmo)
            return r.stdout.strip()
        except Exception:
            return ""


# ---- adb wedge guards (re-added 2026-08-22, lost with /tmp) ----
# One cheap `adb devices` every 3s feeds a state cache so request threads never
# block on a hung adbd; the semaphore caps concurrent adb spawns at 4.
_ADB_SEM = threading.BoundedSemaphore(4)
_DEV_STATE = {}          # serial -> "device" | "offline" | "unauthorized" | "absent"
_DEV_STATE_LOCK = threading.Lock()
_SNAPSHOT = {}           # {"cluster": [...], "train": {...}, "ts": float}


def _adb_state_loop():
    while True:
        try:
            r = subprocess.run(["adb", "devices"], capture_output=True,
                               text=True, timeout=6)
            new = {}
            for line in r.stdout.splitlines()[1:]:
                parts = line.split()
                if len(parts) == 2:
                    new[parts[0]] = parts[1]
            for s, _, _, _, _, _, _, _ in _cluster_tuples():
                if s == HOST_SERIAL:
                    continue
                with _DEV_STATE_LOCK:
                    _DEV_STATE[s] = new.get(s, "absent")
        except Exception:
            pass
        time.sleep(3)


def _snapshot_loop():
    """Compute /cluster + /train OFF the request path (wedge-proof polling)."""
    while True:
        snap = {}
        try:
            snap["cluster"] = cluster_status()
            snap["time"] = time.strftime("%H:%M:%S")
        except Exception as e:
            snap["cluster_err"] = str(e)
        try:
            snap["train"] = _training_status()
        except Exception as e:
            snap["train"] = {"error": str(e)}
        snap["ts"] = time.time()
        global _SNAPSHOT
        _SNAPSHOT = snap
        time.sleep(2)


def _host_stats():
    dev = {"serial": HOST_SERIAL, "name": _device_name(HOST_SERIAL, HOST_NAME),
           "role": HOST_ROLE,
           "online": True, "ram": None, "backend": 0, "active": False, "kind": "host",
           "model": "", "abi": platform.machine() or "unknown",
           "cpu": _cpu_model(), "hostname": platform.node() or HOST_NAME,
           "platform": platform.platform(),
           "max_context": 0, "context_used": 0, "total_context": 0, "context_pct": 0}
    try:
        with open("/proc/meminfo") as f:
            mem = f.read()
        mtotal = mavail = 0
        for line in mem.splitlines():
            if line.startswith("MemTotal:"):
                mtotal = int(line.split()[1]) // 1024
            elif line.startswith("MemAvailable:"):
                mavail = int(line.split()[1]) // 1024
        dev["ram"] = mavail
        dev["ram_total"] = mtotal
        dev["ram_pct"] = round(100 * (1 - mavail / mtotal)) if mtotal else 0
        with open("/proc/loadavg") as f:
            la = f.read().split()
            dev["load"] = [float(x) for x in la[:3]]
        with open("/proc/uptime") as f:
            dev["uptime"] = round(float(f.read().split()[0]))
        with open("/proc/cpuinfo") as f:
            ncores = sum(1 for l in f if l.startswith("processor"))
        dev["cores"] = ncores
        dev["battery"] = None
        dev["temp"] = None
        # disk
        try:
            st = os.statvfs(DISK_ROOT)
            dev["disk_free_gb"] = round(st.f_bavail * st.f_frsize / 2 ** 30, 1)
            dev["disk_total_gb"] = round(st.f_blocks * st.f_frsize / 2 ** 30, 1)
        except Exception:
            pass
    except Exception as e:
        dev["err"] = str(e)
    return dev


_STAT_CACHE = {}          # serial -> (ts, stats)


def _android_stats(serial):
    ent = _STAT_CACHE.get(serial)
    if ent and time.time() - ent[0] < 10:
        return ent[1]
    out = _adb(serial, "shell", _ANDROID_STAT_CMD)
    s = {}
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    for line in lines:
        if line.startswith("MemTotal:"):
            s["ram_total"] = int(line.split()[1]) // 1024
        elif line.startswith("MemAvailable:"):
            s["ram"] = round(int(line.split()[1]) / 1024)
        elif line and line[0].isdigit() and "/" in line and " " in line:
            parts = line.split()
            try:
                s["load"] = [float(x) for x in parts[:3]]
            except Exception:
                pass
        elif line and line[0].isdigit() and line.count(" ") == 1 and not line.startswith("Mem"):
            parts = line.split()
            try:
                s["uptime"] = round(float(parts[0]))
            except Exception:
                pass
        elif line.isdigit() and 0 <= int(line) <= 100:
            s["battery"] = int(line)
        elif line and not any(k in line for k in ("Mem", "/", " ")) and line[0].isalpha():
            # getprop outputs come last; two trailing alpha lines = model, abi
            if "phone_model" not in s:
                s["phone_model"] = line
            else:
                s["abi"] = line
    if s.get("ram") and s.get("ram_total"):
        s["ram_pct"] = round(100 * (1 - s["ram"] / s["ram_total"]))
    _STAT_CACHE[serial] = (time.time(), s)
    return s


def _executor_ctx_used(port):
    """Sum live n_past over slots (0 if idle/unreachable)."""
    try:
        u = f"http://127.0.0.1:{port}/slots"
        with urllib.request.urlopen(u, timeout=4) as r:
            slots = json.load(r)
        total = 0
        for s in slots:
            npast = s.get("n_past") or s.get("n_prompt_tokens_processed") or 0
            total += npast
        return total
    except Exception:
        return 0


MOCK = os.environ.get("TOOLRX_MOCK") == "1"


# ---- local model discovery ------------------------------------------------
# The command center lists whatever is actually available on this machine:
# Ollama (/api/tags) and OpenAI-compatible servers (/v1/models). Configure
# extra base URLs with TOOLRX_LOCAL_BACKENDS (comma separated).
_LOCAL_BACKENDS = [u.strip().rstrip("/") for u in _env(
    "TOOLRX_LOCAL_BACKENDS",
    "http://127.0.0.1:11434,http://127.0.0.1:8081,"
    "http://127.0.0.1:8082,http://127.0.0.1:1234",
).split(",") if u.strip()]
_LOCAL_MODELS_CACHE = [0.0, None]     # [timestamp, payload]
_LOCAL_MODELS_LOCK = threading.Lock()


def _probe_backend(url):
    """Return {url, kind, models} for one reachable local backend, else None."""
    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=1.5) as r:
            data = json.load(r)
        names = sorted({m.get("name") for m in data.get("models", []) if m.get("name")})
        if names:
            return {"url": url, "kind": "ollama", "models": names}
    except Exception:
        pass
    for path in ("/v1/models", "/models"):
        try:
            with urllib.request.urlopen(url + path, timeout=1.5) as r:
                data = json.load(r)
        except Exception:
            continue
        items = data.get("data") if isinstance(data, dict) else data
        names = sorted({m.get("id") or m.get("name")
                        for m in (items or []) if isinstance(m, dict)} - {None})
        if names:
            return {"url": url, "kind": "openai", "models": names}
    return None


def local_models():
    """Cached (5s) snapshot of available local models."""
    now = time.time()
    with _LOCAL_MODELS_LOCK:
        ts, cached = _LOCAL_MODELS_CACHE
        if cached is not None and now - ts < 5:
            return cached
    backends = [b for b in (_probe_backend(u) for u in _LOCAL_BACKENDS) if b]
    payload = {
        "backends": backends,
        "models": sorted({m for b in backends for m in b["models"]}),
        "configured": _LOCAL_BACKENDS,
    }
    with _LOCAL_MODELS_LOCK:
        _LOCAL_MODELS_CACHE[0] = time.time()
        _LOCAL_MODELS_CACHE[1] = payload
    return payload


_MOCK_DEVICES = [
    {"serial": "HOST", "name": "local", "role": "router + tool host", "online": True,
     "kind": "host", "model": "", "backend": 0},
    {"serial": "MOCK1", "name": "phone-a", "role": "needle2 + executor", "online": True,
     "kind": "android", "model": "tiny-executor", "backend": 8086, "ram": 3100,
     "ram_total": 7400, "ram_pct": 58},
    {"serial": "MOCK2", "name": "phone-b", "role": "executor", "online": True,
     "kind": "android", "model": "tiny-executor", "backend": 8087, "ram": 2100,
     "ram_total": 4000, "ram_pct": 47},
    {"serial": "MOCK3", "name": "tablet-a", "role": "needle2", "online": False,
     "kind": "android", "model": "tiny-needle", "backend": 8353},
    {"serial": "MOCK4", "name": "tablet-b", "role": "needle2", "online": True,
     "kind": "android", "model": "tiny-needle", "backend": 8354, "ram": 2600,
     "ram_total": 4000, "ram_pct": 35},
]


def cluster_status():
    if MOCK:
        devs = [dict(d) for d in _MOCK_DEVICES]
        tot = sum(d.get("max_context", 4096) for d in devs)
        for d in devs:
            d["max_context"] = d.get("max_context", 4096)
            d["context_used"] = d.get("context_used", 1024)
            d["total_context"] = tot
        used = sum(d.get("context_used", 0) for d in devs)
        devs[0]["context_used"] = used
        devs[0]["context_pct"] = round(100 * used / tot) if tot else 0
        return devs
    out = [_host_stats()]
    for serial, name, role, port, ram_mb, is_exec, model, max_ctx in _cluster_tuples():
        if serial == HOST_SERIAL:
            continue
        dev = {"serial": serial, "name": _device_name(serial, name), "role": role, "online": False,
               "ram": None, "backend": port, "active": False, "kind": "android",
               "model": model, "max_context": max_ctx, "context_used": 0}
        with _ACTIVITY_LOCK:
            dev["active"] = _ACTIVITY.get(serial, 0) > time.time()
        if not port:
            # no backend — online = adb sees the device
            present = "device" in _adb(serial, "get-state")
            dev["online"] = present
            if present:
                dev.update(_android_stats(serial))
            out.append(dev)
            continue
        # backend alive?
        try:
            u = f"http://127.0.0.1:{port}{'/v1/models' if is_exec else '/'}"
            urllib.request.urlopen(u, timeout=4)
            dev["online"] = True
        except Exception:
            dev["online"] = False
        # RAM + rich stats
        dev.update(_android_stats(serial))
        if dev.get("ram") and dev.get("ram_total"):
            dev["ram_pct"] = round(100 * (1 - dev["ram"] / dev["ram_total"]))
        # context: executors report live slot usage; needles are stateless (kv 256)
        if is_exec:
            dev["context_used"] = _executor_ctx_used(port)
        out.append(dev)
    # Only count a context window that is backed by a live backend + model.
    # A statically configured max_ctx on an offline phone is not real context.
    for dev in out:
        if dev.get("serial") != HOST_SERIAL and not (dev.get("online") and dev.get("model")):
            dev["max_context"] = 0
            dev["context_used"] = 0
    total_ctx = sum(d.get("max_context", 0) for d in out)
    used_ctx = sum(d.get("context_used", 0) for d in out
                   if d.get("serial") != HOST_SERIAL)
    for dev in out:
        if dev["serial"] == HOST_SERIAL:
            dev["total_context"] = total_ctx
            dev["context_used"] = 0
            dev["context_pct"] = round(100 * used_ctx / total_ctx) if total_ctx else 0
    return out


# ---- training cycle state for the dashboard ----
# Optional phone-training harness. Disabled unless TOOLRX_SHOW_TRAINING=1 and
# TRAIN_SERIAL points at a real adb device. The deterministic router works with
# none of this.
TRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = _env("TOOLRX_RUN_DIR", os.path.join(HERE, "run"))
# Android shared-storage root used by the optional phone-training harness.
SDCARD = _env("TRAIN_ANDROID_ROOT", os.path.join(os.sep, "sdcard"))
TRAIN_STATE = {
    "version": None,        # e.g. "v20"
    "status": "idle",       # idle | running | done | error
    "chunks_done": 0,
    "chunks_total": 0,
    "steps_total": 0,
    "supervisor_pid": None,
    "log": [],              # last N log lines
    "corpus": None,
    "init": None,
    "started": None,
    "history": {},          # version -> {chunks, steps, gate, corpus, init, date}
    "last_gate": {},        # version -> "49/120 (40.8%)"
}
TRAIN_LOCK = threading.Lock()
TRAIN_SERIAL = _env("TRAIN_SERIAL")
TRAIN_SUP = os.path.join(TRAIN_DIR, "train-supervisor.py")

# ---- relentless auto-cycle: train -> gate -> promote-if-better -> repeat ----
CHAMPION_FILE = os.path.join(RUN_DIR, "champion.json")
TRAIN_FLAG = os.path.join(RUN_DIR, "training.flag")
AUTO = {"on": False, "phase": "idle", "version": None, "cycles": 0,
        "best": None, "msg": ""}
_AUTO_LOCK = threading.Lock()
CORPORA = [
    _env("TOOLRX_TRAIN_CORPUS_A", f"{SDCARD}/train_full_v2.jsonl"),
    _env("TOOLRX_TRAIN_CORPUS_B", f"{SDCARD}/train_focused.jsonl"),
]
AUTO_STEPS = 32            # per-cycle training budget
CHAMPION_INIT = "base"   # fresh LoRA from base weights, not a trained checkpoint


def _load_champion():
    try:
        with open(CHAMPION_FILE) as fh:
            return json.load(fh)
    except Exception:
        # 2026-08-24: gate rebalanced (bash 40->14 partial-credit, #79)
        # champion re-gated -> v13 now 67/120 on the new scale.
        return {"version": "v13", "pass": 67, "total": 120, "pct": 55.8,
                "init_path": "/root/syn_v13_c15.cact"}


def _save_champion(c):
    try:
        with open(CHAMPION_FILE, "w") as fh:
            json.dump(c, fh, indent=1)
    except Exception:
        pass


def _next_version():
    """Highest run_vNN seen on phone or in gate logs, +1."""
    nums = [0]
    out = _adb(TRAIN_SERIAL, "shell", f"ls {SDCARD}/run_v*.sh 2>/dev/null")
    for m in re.finditer(r"run_v(\d+)", out):
        nums.append(int(m.group(1)))
    for f in glob.glob(RUN_DIR + "/gate_v*.log"):
        m = re.search(r"gate_v(\d+)", os.path.basename(f))
        if m:
            nums.append(int(m.group(1)))
    return "v" + str(max(nums) + 1)


def _wait_training_done(version, timeout_s=4 * 3600):
    deadline = time.time() + timeout_s
    marker = f"ALL-{version.upper()}-DONE"
    while time.time() < deadline and AUTO["on"]:
        out = _adb(TRAIN_SERIAL, "shell",
                   f"grep -c '{marker}' {SDCARD}/train_{version}_chunk.log 2>/dev/null")
        if out.strip().startswith("1"):
            return True
        fail = _adb(TRAIN_SERIAL, "shell",
                    f"grep -oE 'ALL-{version.upper()}-FAILED\\([0-9]+\\)' "
                    f"{SDCARD}/train_{version}_chunk.log 2>/dev/null | tail -1")
        if fail.strip():
            return False
        time.sleep(60)
    return False


def _wait_gate_done(version, timeout_s=7200):
    """Wait for a gate result using the SAME source the dashboard reads
    (_verify_progress / gate history). The verify worker never updates the
    in-memory v['done'], which left this waiter blind for its whole timeout
    every cycle (v32 stuck in 'gate' despite 120/120 on disk)."""
    deadline = time.time() + timeout_s
    while AUTO["on"] and time.time() < deadline:
        hist = _train_gate_history().get(version)
        if hist and hist.get("total"):
            return hist                       # final "exact-match" line landed
        with _VERIFIES_LOCK:
            v = dict(_VERIFIES.get(version, {}))
        if v.get("err"):
            return None
        pid = v.get("pid")
        alive = bool(pid and os.path.exists(f"/proc/{pid}"))
        done = _verify_progress(version)
        if not alive and v.get("stage") == "gate":
            # only judge AFTER launch (stage=gate): exited with zero samples
            # = crashed harness — fail fast instead of sitting blind (v36)
            if done == 0:
                _fail_gate(version, "gate proc died before scoring any sample")
                return None
            return _train_gate_history().get(version)   # exited early/partial
        time.sleep(30)
    return None


def _adopt_running():
    """After a restart the phone may still be training version X under an orphaned
    supervisor. Adopt it (wait+gate) instead of launching a colliding new run —
    two supervisors typing into one Termux garbles both launches."""
    out = _adb(TRAIN_SERIAL, "shell",
               f"ls -t {SDCARD}/train_v*_chunk.log 2>/dev/null | head -1")
    m = re.search(r"train_(v[0-9]+)_chunk\.log", out)
    if not m:
        return None, 0
    ver = m.group(1)
    running = _adb(TRAIN_SERIAL, "shell",
                   "ps -A -o ARGS 2>/dev/null | grep '[p]ython3 /usr/local/bin/needle finetune'").strip()
    done = f"ALL-{ver.upper()}-DONE" in _adb(
        TRAIN_SERIAL, "shell", f"tail -3 {SDCARD}/train_{ver}_chunk.log 2>/dev/null")
    ungated = ver not in _train_gate_history()
    if running or (done and ungated):
        info = _train_log_parse(ver)
        return ver, int(info.get("chunks_done") or 0)
    return None, 0


def _gate_reaper_loop(interval=90):
    """Background thread: gates any run that finished (ALL-DONE) but has no
    gate score in history. Fixes the recurring gap where manual /train/start
    runs (v44, v45) trained to completion and then sat ungated because the
    auto-cycle was OFF. Guards: skip if a verify for that version is already
    in flight; skip if a newer run is actively training on the phone."""
    gated = set()
    while True:
        try:
            out = _adb(TRAIN_SERIAL, "shell",
                       f"ls -t {SDCARD}/train_v*_chunk.log 2>/dev/null | head -1")
            m = re.search(r"train_(v[0-9]+)_chunk\.log", out)
            # the newest log is the one we might gate (don't race a running one)
            newest = m.group(1) if m else None
            running = _adb(TRAIN_SERIAL, "shell",
                           "ps -A -o ARGS 2>/dev/null | grep '[p]ython3 /usr/local/bin/needle finetune'").strip()
            for ver in _seen_training_versions():
                if not ver:
                    continue
                if ver in gated or ver in _train_gate_history():
                    continue
                if ver == newest and running:
                    continue            # newest run still training — wait
                # skip if someone is ALREADY gating this version (a manual
                # /train/verify or another reaper tick): a second gate on the
                # same version races a backend + clobbers the shared gate log.
                digits = re.sub(r"[^0-9]", "", ver)
                vport = 8360 + ((int(digits) if digits else 0) % 20)
                gproc = subprocess.run(["ps", "aux"], capture_output=True, text=True)
                if f"gate_harness.py http://127.0.0.1:{vport}" in gproc.stdout:
                    continue
                done = f"ALL-{ver.upper()}-DONE" in _adb(
                    TRAIN_SERIAL, "shell",
                    f"tail -3 {SDCARD}/train_{ver}_chunk.log 2>/dev/null")
                if not done:
                    continue
                with _VERIFIES_LOCK:
                    inflight = _VERIFIES.get(ver, {}).get("running")
                if inflight:
                    continue
                log.info("gate reaper: gating completed %s", ver)
                _kill_orphan_gates(ver)
                _verify_run(ver)
                gated.add(ver)
        except Exception as e:
            log.info("gate reaper cycle error (suppressed): %s", e)
        time.sleep(interval)


def _seen_training_versions():
    """All versions that have a chunk log on phone-storage (finished OR running)."""
    out = _adb(TRAIN_SERIAL, "shell",
               f"ls {SDCARD}/train_v*_chunk.log 2>/dev/null")
    return re.findall(r"train_(v[0-9]+)_chunk\.log", out)


def _kill_orphan_gates(version):
    """Before re-gating a version, kill leftover gate_harness runs + any merged
    needle serving it + stale forwards -- otherwise two gates fight over one
    backend and the survivor logs connection-error FAILs."""
    subprocess.run(["pkill", "-f", "gate_harness.py"], capture_output=True, timeout=15)
    digits = re.sub(r"[^0-9]", "", version)
    port = 8360 + ((int(digits) if digits else 0) % 20)
    peers = _env("TOOLRX_GATE_SERIALS").split(",")
    if not any(peers):
        peers = [d.get("serial", "") for d in _load_devices()]
    for serial in (s.strip() for s in peers):
        if not serial:
            continue
        _adb(serial, "shell",
             f"pkill -f 'needle_model.*syn_{version}_merged' 2>/dev/null")
        subprocess.run(["adb", "-s", serial, "forward", "--remove", f"tcp:{port}"],
                       capture_output=True, timeout=15)
    subprocess.run(["bash", "-c",
                    f"pkill -f 'needle_model.*syn_{version}_merged.cact --serve --port {port}'"],
                   capture_output=True, timeout=15)


def _fail_gate(version, msg):
    with _VERIFIES_LOCK:
        v = _VERIFIES.setdefault(version, {})
        v["err"] = msg
        v["running"] = False
    log.info("gate %s FAILED: %s", version, msg)


def _auto_loop(start_version_num):
    n = start_version_num
    champ = _load_champion()
    AUTO["best"] = f"{champ['version']} {champ['pass']}/{champ['total']}"
    # 32 identical steps from the same init+seed reproduces byte-identical
    # adapters (v25==v27==v29 overnight). Rotate REAL experiments instead:
    # steps/lr/corpus vary; epoch_seed derives from the version number.
    EXPERIMENTS = [
        {"steps": 64, "lr": "3e-5", "corpus": CORPORA[0], "init": "base"},
        {"steps": 64, "lr": "3e-5", "corpus": CORPORA[1], "init": "base"},
        {"steps": 96, "lr": "2e-5", "corpus": CORPORA[0], "init": "base"},
        {"steps": 32, "lr": "8e-5", "corpus": CORPORA[1], "init": "champ"},
        {"steps": 128, "lr": "2e-5", "corpus": CORPORA[1], "init": "champ"},
        {"steps": 32, "lr": "5e-5", "corpus": CORPORA[0], "init": "base"},
    ]
    exp_i = 0
    while AUTO["on"]:
      try:
        exp = EXPERIMENTS[exp_i % len(EXPERIMENTS)]
        version = "v" + str(n)
        # alternate init: "base" trains a fresh LoRA (avoids overfit-on-same-
        # corpus chaining — the v30+ regressions were all champ-init'd);
        # "champ" continues the champion's best checkpoint to refine a lineage.
        if exp.get("init") == "champ":
            init = champ.get("init_path") or CHAMPION_INIT
        else:
            init = CHAMPION_INIT
        adopted, _cd = _adopt_running()
        if adopted and adopted != version:
            # a previous generation is STILL training — wait for it instead of
            # stacking a second launch on the same Termux
            # wait out an in-flight run BEFORE gating — otherwise we'd burn a
            # gate cycle on a half-trained checkpoint
            while AUTO["on"]:
                tail3 = _adb(TRAIN_SERIAL, "shell",
                             f"tail -3 {SDCARD}/train_{adopted}_chunk.log 2>/dev/null")
                if f"ALL-{adopted.upper()}-DONE" in tail3:
                    break
                if re.search(f"ALL-{adopted.upper()}-FAILED", tail3):
                    break
                AUTO.update(phase="gate", version=adopted,
                            msg=f"adopted {adopted} — waiting for training to finish")
                time.sleep(60)
            if not AUTO["on"]:
                continue
            if f"ALL-{adopted.upper()}-FAILED" in _adb(
                    TRAIN_SERIAL, "shell",
                    f"tail -3 {SDCARD}/train_{adopted}_chunk.log 2>/dev/null"):
                AUTO["msg"] = f"adopted {adopted} had failed chunks"
                n = int(re.sub(r"[^0-9]", "", adopted)) + 1
                continue
            AUTO.update(phase="gate", version=adopted,
                        msg=f"adopting {adopted} — running gate")
            _kill_orphan_gates(adopted)
            _verify_run(adopted)
            hist = _wait_gate_done(adopted)
            if hist:
                AUTO["msg"] = f"adopted {adopted} gate {hist['pass']}/{hist['total']} ({hist['pct']}%)"
            if hist["pass"] > champ["pass"]:
                champ = {"version": adopted, "pass": hist["pass"],
                         "total": hist["total"], "pct": hist["pct"],
                         "init_path": f"/root/syn_{adopted}_c8.cact"}
                _save_champion(champ)
                AUTO["best"] = f"{adopted} {hist['pass']}/{hist['total']}"
            n = int(re.sub(r"[^0-9]", "", adopted)) + 1
            continue
        try:
            open(TRAIN_FLAG, "w").write(version)
        except Exception:
            pass
        AUTO.update(phase="train", version=version,
                    msg=(f"exp steps={exp['steps']} lr={exp['lr']} "
                         f"corpus={'focused' if exp['corpus']==CORPORA[1] else 'full'} "
                         f"init={init}"))
        err = _launch_training(version, exp["corpus"], init, exp["steps"],
                               lr=exp["lr"])
        if err:
            AUTO["msg"] = f"launch failed: {err}"
            time.sleep(120)
            continue
        # confirm the finetune truly started (Termux typing can silently drop)
        started = False
        for _ in range(9):
            time.sleep(10)
            if _adb(TRAIN_SERIAL, "shell",
                    "ps -A -o ARGS 2>/dev/null | grep '[n]eedle finetune'").strip():
                started = True
                break
        if not started:
            AUTO["msg"] = f"{version}: launch didn't take — retrying"
            _launch_training(version, exp["corpus"], init, exp["steps"], lr=exp["lr"])
            for _ in range(9):
                time.sleep(10)
                if _adb(TRAIN_SERIAL, "shell",
                        "ps -A -o ARGS 2>/dev/null | grep '[n]eedle finetune'").strip():
                    started = True
                    break
        if not started:
            AUTO["msg"] = f"{version}: could not start training (Termux?)"
            n += 1
            exp_i += 1
            continue
        # ---- train with PIPELINED eval: gate the midpoint checkpoint on a
        # second phone WHILE the rest trains; recover once if a chunk dies.
        expect_chunks = max(1, exp["steps"] // 8)
        mid_ckpt = max(1, expect_chunks // 2)
        mid_fired = False
        ok = False
        for attempt in range(2):                # 1 recover retry
            done_marker = f"ALL-{version.upper()}-DONE"
            fail_re = f"ALL-{version.upper()}-FAILED"
            deadline = time.time() + 4 * 3600
            while AUTO["on"] and time.time() < deadline:
                out = _adb(TRAIN_SERIAL, "shell",
                           f"grep -hE '{done_marker}|{fail_re}' "
                           f"{SDCARD}/train_{version}_chunk.log 2>/dev/null | tail -1")
                info = _train_log_parse(version)
                cd = info.get("chunks_done", 0)
                if (not mid_fired and cd >= mid_ckpt and cd < expect_chunks
                        and attempt == 0 and expect_chunks >= 4):
                    k = mid_ckpt
                    mid_fired = True
                    AUTO["msg"] = (f"{version}: chunk {cd}/{expect_chunks} — "
                                   f"mid-gate c{k} launched in parallel")
                    threading.Thread(
                        target=_verify_run,
                        args=(version, f"m{k}", k), daemon=True).start()
                if done_marker in out:
                    ok = True
                    break
                if fail_re in out:
                    break
                time.sleep(60)
            if ok or not AUTO["on"]:
                break
            if attempt == 0:
                # recover: re-push SAME script (skip logic resumes from last
                # good chunk) without wiping checkpoints, then wait again
                AUTO["msg"] = f"{version}: chunk failed — recovering"
                err2 = _launch_training(version, exp["corpus"], init,
                                        exp["steps"], lr=exp["lr"])
                if err2:
                    break
                time.sleep(30)
        if not ok:
            AUTO["msg"] = f"{version}: training failed after recovery"
            n += 1
            exp_i += 1
            continue
        try:
            os.remove(TRAIN_FLAG)
        except Exception:
            pass
        AUTO.update(phase="gate", version=version)
        _verify_run(version)                       # spawns its own thread
        hist = _wait_gate_done(version)
        if hist:
            better = (hist["pass"] > champ["pass"] or
                      (hist["pass"] == champ["pass"] and
                       hist["pct"] > champ["pct"]))
            AUTO["msg"] = (f"{version} [s{exp['steps']} lr{exp['lr']} "
                           f"{'foc' if exp['corpus']==CORPORA[1] else 'full'}] "
                           f"gate {hist['pass']}/{hist['total']} ({hist['pct']}%) "
                           f"vs champ {champ['pass']}/{champ['total']}"
                           + (" — PROMOTED" if better else ""))
            if better:
                champ = {"version": version, "pass": hist["pass"],
                         "total": hist["total"], "pct": hist["pct"],
                         "init_path": f"/root/syn_{version}_c{max(1, exp['steps']//8)}.cact"}
                _save_champion(champ)
                AUTO["best"] = f"{version} {hist['pass']}/{hist['total']}"
        else:
            AUTO["msg"] = f"{version}: gate failed"
        AUTO["cycles"] = AUTO.get("cycles", 0) + 1
        exp_i += 1
        n += 1
        time.sleep(20)
      except Exception as e:
        import traceback
        log.error("auto-cycle iter crashed: %s\n%s", e, traceback.format_exc())
        AUTO["msg"] = f"cycle error: {type(e).__name__}: {e}"
        n += 1
        exp_i += 1
        time.sleep(60)
    AUTO["phase"] = "idle"


def _start_auto_cycle():
    with _AUTO_LOCK:
        if AUTO["on"]:
            return "already running"
        AUTO.update(on=True, phase="starting", msg="")
        m = re.match(r"v(\d+)", _next_version())
        threading.Thread(target=_auto_loop, args=(int(m.group(1)),),
                         daemon=True).start()
        return "relentless auto-cycle started (alternating full/focused corpus)"
PROTECTED_FILE = os.path.join(TRAIN_DIR, "protected.json")

def _load_protected():
    try:
        with open(PROTECTED_FILE) as fh:
            return set(json.load(fh))
    except Exception:
        return {"v13"}

def _save_protected(s):
    with open(PROTECTED_FILE, "w") as fh:
        json.dump(sorted(s), fh)

# in-process gate verifications: version -> {pid, port, started, total, done}
_VERIFIES = {}
_VERIFIES_LOCK = threading.Lock()


def _verify_progress(version):
    """Compute gate progress from the version gate log (under RUN_DIR)."""
    gp = RUN_DIR + "/gate_{}.log".format(version)
    done = 0
    try:
        with open(gp) as fh:
            txt = fh.read()
        for line in txt.splitlines():
            m = re.search(r"\[(\d+)/120\]", line)
            if m:
                done = max(done, int(m.group(1)))
        if re.search(r"exact-match \d+/\d+", txt):
            done = 120
    except Exception:
        pass
    return done


def _verifies_status():
    """Snapshots of in-flight (or just-finished) gates, newest first.
    Auto-detects running gate_harness processes + gate_*.log files on disk,
    so it survives server restarts."""
    # map gate log -> version
    log_versions = {}
    for f in glob.glob(RUN_DIR + "/gate_v*.log"):
        m = re.search(r"gate_(v[0-9]+)\.log", os.path.basename(f))
        if m:
            log_versions[os.path.basename(f)] = m.group(1)
    # running gate processes: argv[2] is the backend url (:port)
    running_ports = {}
    try:
        ps = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True,
                            text=True, timeout=10).stdout
        for line in ps.splitlines():
            if "gate_harness.py" not in line:
                continue
            mm = re.search(r"gate_harness\.py http://127\.0\.0\.1:(\d+)", line)
            if mm:
                pid = int(line.split(None, 1)[0])
                running_ports[int(mm.group(1))] = pid
    except Exception:
        pass
    # merge: prefer in-memory tracking, but also include anything found on disk
    with _VERIFIES_LOCK:
        items = list(_VERIFIES.items())
    seen = set()
    out = {}
    for ver, v in items:
        seen.add(ver)
        done = _verify_progress(ver)
        total = v.get("total") or 120
        pid = v.get("pid")
        alive = pid and os.path.exists(f"/proc/{pid}")
        running = (alive and done < total) or (v.get("port") in running_ports and done < total)
        finished = done >= total or (not alive and done > 0)
        out[ver] = {"port": v.get("port"), "started": v.get("started"),
                    "done": done, "total": total,
                    "stage": v.get("stage", ""), "err": v.get("err"),
                    "running": running and not v.get("err"),
                    "finished": finished,
                    "phone": v.get("phone"),
                    "result": None}
        if finished:
            hist = _train_gate_history()
            h = hist.get(ver)
            if h:
                out[ver]["result"] = f"{h['pass']}/{h['fail']}/{h['total']} ({h['pct']}%)"
    # discover gates that exist on disk but aren't in memory (e.g. after restart)
    any_running = bool(running_ports)
    for basename, ver in log_versions.items():
        if ver in seen:
            continue
        done = _verify_progress(ver)
        total = 120
        gp = f"{RUN_DIR}/{basename}"
        out[ver] = {"port": None, "started": os.path.getmtime(gp) if os.path.exists(gp) else None,
                    "done": done, "total": total,
                    "stage": "", "err": None,
                    "running": any_running and done < total,
                    "finished": done >= total,
                    "result": None}
        if done >= total:
            hist = _train_gate_history()
            h = hist.get(ver)
            if h:
                out[ver]["result"] = f"{h['pass']}/{h['fail']}/{h['total']} ({h['pct']}%)"
    return out


def _train_log_parse(version):
    """Parse phone-storage/train_{version}_chunk.log for progress markers."""
    out = _adb(TRAIN_SERIAL, "shell", f"cat {SDCARD}/train_{version}_chunk.log 2>/dev/null")
    lines = [l for l in out.splitlines() if l.strip()]
    # handle re-launched runs: count completed chunks across all runs (dedupe)
    done_set = set()
    total = 0
    steps = 0
    for l in lines:
        m = re.search(r"CHUNK (\d+): \+(\d+) steps \(to (\d+)\)", l)
        if m:
            total = max(total, int(m.group(3)))
            steps = max(steps, int(m.group(3)))
            continue
        m2 = re.search(r"CHUNK (\d+) exit=(\d+)", l)
        if m2:
            if m2.group(2) == "0":
                done_set.add(int(m2.group(1)))
    running = bool(_adb(TRAIN_SERIAL, "shell",
                        "ps -A -o ARGS 2>/dev/null | grep '[p]ython3 /usr/local/bin/needle finetune'").strip())
    return {"chunks_done": len(done_set), "chunks_total": total // 8 if total else 0,
            "steps_total": steps, "running": running, "log": lines[-8:]}


def _train_gate_history():
    """Read gate results logged on the host (gate logs under RUN_DIR).
    Returns {version: {pass, fail, total, pct}}."""
    out = {}
    try:
        for f in glob.glob(RUN_DIR + "/gate_v*.log"):
            m = re.search(r"gate_(v[0-9A-Za-z]+)\.log", f)
            if not m:
                continue
            with open(f) as fh:
                txt = fh.read()
            if "BACKEND-DOWN" in txt:
                continue                     # infra failure, not a model score
            mm = re.search(r"exact-match (\d+)/(\d+)", txt)
            classes = {}
            for cm in re.finditer(r"(\w+) (\d+)/(\d+)", txt.split("per-class")[-1]):
                classes[cm.group(1)] = [int(cm.group(2)), int(cm.group(3))]
            if mm:
                p = int(mm.group(1))
                t = int(mm.group(2))
                ver = m.group(1)
                if not ver.startswith("v"):
                    ver = "v" + ver
                out[ver] = {
                    "pass": p, "fail": t - p, "total": t,
                    "pct": round(100 * p / t, 1) if t else 0,
                    "classes": classes,
                }
    except Exception:
        pass
    return out


def _training_status():
    if not SHOW_TRAINING or not TRAIN_SERIAL:
        return {"status": "disabled", "enabled": False,
                "reason": "set TOOLRX_SHOW_TRAINING=1 and TRAIN_SERIAL=<adb serial> to enable"}
    with TRAIN_LOCK:
        st = dict(TRAIN_STATE)
    ver = st.get("version")
    if not ver:
        # auto-detect the most recent run on the phone
        out = _adb(TRAIN_SERIAL, "shell",
                   f"ls {SDCARD}/train_*_chunk.log 2>/dev/null | tail -1")
        base = os.path.basename(out.strip())
        m = re.match(r"train_(v[0-9]+)_chunk\.log", base)
        if m:
            ver = m.group(1)
            st["version"] = ver
    if ver:
        info = _train_log_parse(ver)
        st.update(info)
        # is the supervisor alive?
        sup = st.get("supervisor_pid")
        if sup:
            alive = os.path.exists(f"/proc/{sup}")
            if not alive:
                st["supervisor_pid"] = None
                if st.get("status") == "running":
                    st["status"] = "stopped"
        done_log = any("ALL-" + ver.upper() + "-DONE" in l for l in (info.get("log") or []))
        if done_log and not info.get("running"):
            st["status"] = "done"
        elif st.get("status") == "running" and info.get("chunks_total") and \
             info.get("chunks_done", 0) >= info["chunks_total"] and not info.get("running"):
            st["status"] = "done"
        elif st.get("status") == "running" and not info.get("running") and not done_log and \
             not st.get("supervisor_pid"):
            st["status"] = "stopped"
        st["done"] = done_log
    # LIVE GATE TRACKING: cumulative pass-rate + per-class tally for any
    # verification currently in its gate stage (or just finished)
    def _gate_live(vid):
        gp = f"{RUN_DIR}/gate_{vid}.log"
        try:
            txt = open(gp).read()
        except Exception:
            return None
        series, cls, n, p = [], {}, 0, 0
        for m in re.finditer(r"\[(\d+)/120\] (PASS|FAIL)(?: (\w+))?", txt):
            n = int(m.group(1))
            ok = m.group(2) == "PASS"
            p += ok
            series.append([n, round(100 * p / n)])
            c = m.group(3)
            if c:
                st_ = cls.setdefault(c, [0, 0])
                st_[0] += ok
                st_[1] += 1
        if not n:
            return None
        return {"series": series[-120:], "classes": cls, "pass": p,
                "done": n, "finished": "exact-match" in txt}
    st["gate_live"] = {}
    with _VERIFIES_LOCK:
        actives = [(vidc, dict(v)) for vidc, v in _VERIFIES.items()
                   if isinstance(v, dict) and v.get("stage") == "gate"]
    for vidc, _v in actives:
        g = _gate_live(vidc)
        if g:
            st["gate_live"][vidc] = g

    # ---- cycle economics + loss-vs-gate data (cached 60s) ----
    st["economics"] = {}
    st["loss_gate"] = []
    now = time.time()
    if not hasattr(_training_status, "_eco_ts") or now - _training_status._eco_ts > 60:
        eco, lg = {}, []
        # train spans: one adb call for all versions' first-chunk + ALL markers
        out = _adb(TRAIN_SERIAL, "shell",
                   f"for f in {SDCARD}/train_v*_chunk.log; do "
                   "echo ==$f; grep -hE 'CHUNK 1: |ALL-.*-(DONE|FAILED)' $f 2>/dev/null | head -3; done")
        cur_ver, first_t, end_t = None, None, None

        def _pt(x):
            for fmt in ("%a %b %d %H:%M:%S %Z %Y", "%a %b %d %H:%M:%S %Y"):
                try:
                    import calendar
                    return calendar.timegm(time.strptime(x.strip(), fmt))
                except Exception:
                    continue
            return None
        for line in (out or "").splitlines():
            if line.startswith(f"=={SDCARD}/"):
                if cur_ver and first_t and end_t and end_t > first_t:
                    eco[cur_ver] = {"train_min": round((end_t - first_t) / 60, 1)}
                ver_m = re.search(r"train_(v[0-9A-Za-z]+)_chunk", line)
                cur_ver = ver_m.group(1) if ver_m else None
                first_t = end_t = None
                continue
            tm = re.search(r"([A-Za-z]{3} [A-Za-z]{3} +\d+ \d+:\d+:\d+ [A-Za-z]+ \d{4})(?: ===)?\s*$", line)
            if not tm or not cur_ver:
                continue
            t = _pt(tm.group(1))
            if t is None:
                continue
            if "CHUNK 1:" in line and first_t is None:
                first_t = t
            elif "ALL-" in line:
                end_t = t
        if cur_ver and first_t and end_t and end_t > first_t:
            eco[cur_ver] = {"train_min": round((end_t - first_t) / 60, 1)}
        # gate spans from stamped logs + final losses from chunk logs
        hist = _train_gate_history()
        for f in glob.glob(RUN_DIR + "/gate_v*.log"):
            vm = re.search(r"gate_(v[0-9A-Za-z]+)\.log", os.path.basename(f))
            if not vm:
                continue
            txt = open(f).read()
            sm = re.search(r"GATE_START (\d+)", txt)
            em = re.search(r"GATE_END (\d+)", txt)
            if sm and em:
                e = eco.setdefault(vm.group(1), {})
                e["gate_min"] = round((int(em.group(1)) - int(sm.group(1))) / 60, 1)
        for ver, h in hist.items():
            lout = _adb(TRAIN_SERIAL, "shell",
                        f"grep -oE 'S[0-9]+ loss [0-9.]+' "
                        f"{SDCARD}/train_{ver}_chunk.log 2>/dev/null | tail -1")
            lm = re.search(r"loss ([0-9.]+)", lout)
            if lm:
                lg.append({"ver": ver, "loss": float(lm.group(1)),
                           "pct": h.get("pct", 0)})
        _training_status._eco_cache = {"economics": eco, "loss_gate": lg}
        _training_status._eco_ts = now
    cached = getattr(_training_status, "_eco_cache", None)
    if cached:
        st.update(cached)

    # live loss curve for the current run (S<step> loss <val> lines)
    st["loss_curve"] = getattr(_training_status, "_loss_cached", [])
    if ver:
        key = (ver, int(time.time() // 30))          # refetch every 30s max
        if getattr(_training_status, "_loss_key", None) != key:
            out = _adb(TRAIN_SERIAL, "shell",
                       f"grep -oE '^S[0-9]+ loss [0-9.]+' "
                       f"{SDCARD}/train_{ver}_chunk.log 2>/dev/null | tail -400")
            pts = []
            for l in out.splitlines():
                mm = re.match(r"S(\d+) loss ([0-9.]+)", l.strip())
                if mm:
                    pts.append([int(mm.group(1)), float(mm.group(2))])
            _training_status._loss_cached = pts
            _training_status._loss_key = key
        st["loss_curve"] = _training_status._loss_cached
    st["history"] = _train_gate_history()
    st["verifies"] = _verifies_status()
    st["protected"] = sorted(_load_protected())
    with _AUTO_LOCK:
        st["auto"] = dict(AUTO)
        champ = _load_champion()
        st["champion"] = f"{champ['version']} {champ['pass']}/{champ['total']} ({champ['pct']}%)"
    # surface the from-scratch model as the live "training cycle" so it shows up
    # in the SAME card + log window the user expects, not a separate card.
    try:
        m = _model_status()
        st["model"] = m
        # a running from-scratch model overrides the training-cycle summary
        if m.get("status") in ("running", "initialized"):
            st["model_state"] = m.get("status")
            st["model_name"] = "from-scratch"
            _model_log_lines = _model_log()
            if _model_log_lines:
                st["log"] = _model_log_lines
    except Exception:
        pass
    return st


def _port_open(port, host="127.0.0.1", timeout=2):
    """True if something is listening on host:port (TCP connect probe)."""
    try:
        import socket
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


# ---- from-scratch model training (tier trainer) ----
# The from-scratch trainer (needle.train, on the phone) streams progress lines
#   e{epoch} s{step} t{step} loss={loss} val={val}
# to a log in the proot. We tail it and surface live training progress for the
# dashboard. The trainer is NOT the old LoRA /train pipeline — it builds the
# base model weights from random init.
MODEL_LOG = f"{SDCARD}/ndtest/t0_run.log"
MODEL_LOG_DIR = f"{SDCARD}/ndtest"


def _active_model_log():
    """Return the path of the newest *_run.log (so any training run, not just
    t0_run.log, shows in the UI). Falls back to MODEL_LOG."""
    try:
        out = _adb(TRAIN_SERIAL, "shell",
                   f"ls -t {MODEL_LOG_DIR}/*_run.log 2>/dev/null | head -1")
        p = out.strip().splitlines()
        return (p[0] if p else None) or MODEL_LOG
    except Exception:
        return MODEL_LOG


def _model_status():
    """Read live from-scratch model-training progress from the phone log."""
    if not SHOW_TRAINING or not TRAIN_SERIAL:
        return {"status": "disabled", "enabled": False}
    if not hasattr(_model_status, "_cvts"):
        _model_status._curve = []
        _model_status._cvts = 0.0
        _model_status._logp = ""
    st = {"epoch": None, "step": None, "loss": None, "val": None,
          "status": "unknown", "msg": "", "params": None}
    try:
        logp = _active_model_log()
        out = _adb(TRAIN_SERIAL, "shell", f"cat {logp} 2>/dev/null")
    except Exception as e:
        st["status"] = "error"
        st["msg"] = f"log read failed: {e}"
        return st
    last_loss = None
    curve = []
    for line in out.splitlines():
        m = re.search(r"config:.*d=\d+ L=(\d+)", line)
        if m:
            st["cfg_layers"] = int(m.group(1))
        m = re.search(r"initialized ([\d,]+) params", line)
        if m:
            st["params"] = int(m.group(1).replace(",", ""))
        m = re.search(r"e(\d+) s(\d+) t(\d+) loss=([\d.]+)(?: val=([\d.]+))?", line)
        if m:
            st["epoch"] = int(m.group(1))
            st["step"] = int(m.group(3))
            st["loss"] = float(m.group(4))
            if m.group(5):
                st["val"] = float(m.group(5))
            curve.append([int(m.group(3)), float(m.group(4))])
            last_loss = st["loss"]
        if "ALL-DONE" in line:
            st["status"] = "done"
        if "Traceback" in line or ("Error" in line and "LLVM compilation error" not in line and "Failed to materialize symbols" not in line):
            st["status"] = "error"
    # debounce adb: cache the curve briefly so every poll doesn't re-tail the log
    now = time.time()
    have = getattr(_model_status, "_curve", None)
    if have and now - _model_status._cvts < 15 and len(have) >= len(curve) and \
            getattr(_model_status, "_logp", "") == logp:
        curve = have
    else:
        _model_status._curve = curve
        _model_status._logp = logp
        _model_status._cvts = now
    st["loss_curve"] = curve
    # transient XLA hiccups (LLVM/Jax) shouldn't mark the whole run as error if training continued
    if st["status"] == "error" and st["step"] is not None and st["loss"] is not None:
        st["status"] = "running"
    if st["status"] == "unknown":
        if st["step"] is not None:
            st["status"] = "running"
        elif st["params"] is not None:
            st["status"] = "initialized"
        elif last_loss is not None:
            st["status"] = "running"
    return st


def _model_log():
    """Return the from-scratch trainer's recent step lines (for the tLog window)."""
    try:
        logp = _active_model_log()
        out = _adb(TRAIN_SERIAL, "shell", f"cat {logp} 2>/dev/null")
    except Exception:
        return []
    lines = [l for l in out.splitlines() if re.search(r"e\d+ s\d+ t\d+ loss=|initialized|c\]kpt|Traceback|epoch \d+", l)]
    return lines[-60:]


def _verify_run(version, tag="", ckpt=None):
    """Pull a trained adapter from the phone, merge it, and launch a detached gate.
    tag+ckpt select an INTERMEDIATE checkpoint (mid-training gates): identity for
    files/ports/registry becomes version+tag and the source is c{ckpt}.
    Runs the heavy parts in a background thread so the HTTP call returns fast.
    Registers _VERIFIES[vid] IMMEDIATELY so the UI shows progress from click.
    Returns (error, message) or (None, message)."""
    vid = version + tag
    if re.search(r"[^a-zA-Z0-9_]", vid):
        return "bad version", None

    def _stage(stage):
        with _VERIFIES_LOCK:
            _VERIFIES.setdefault(version, {})["stage"] = stage

    def _fail(msg):
        with _VERIFIES_LOCK:
            v = _VERIFIES.setdefault(version, {})
            v["err"] = msg
            v["running"] = False
        log.info("verify %s FAILED: %s", version, msg)

    # register immediately (Aug-19 behavior: UI updates on click, not later)
    with _VERIFIES_LOCK:
        _VERIFIES[vid] = {"pid": None, "port": None, "started": time.time(),
                          "total": 120, "done": 0, "stage": "pull",
                          "running": True}

    def _work():
        try:
            _work_inner()
        except Exception as e:
            _fail(f"{type(e).__name__}: {e}")

    def _work_inner():
        sd_src = f"{SDCARD}/syn_{version}_c{ckpt}.cact" if ckpt else None
        if ckpt and not _adb(TRAIN_SERIAL, "shell",
                             f"ls {sd_src} 2>/dev/null").strip():
            _fail(f"checkpoint {sd_src} not on {SDCARD} yet")
            return
        local_cact = f"{RUN_DIR}/syn_{vid}.cact"
        if ckpt:
            # mid-training gate: the run script copies each chunk to phone storage —
            # adb-pull directly; NEVER type into the training Termux session
            pull = subprocess.run(["adb", "-s", TRAIN_SERIAL, "pull", sd_src,
                                   local_cact],
                                  capture_output=True, timeout=120)
            if pull.returncode != 0 or not os.path.exists(local_cact):
                _fail("checkpoint pull failed")
                return
        else:
            # 1. final gate: find the highest chunk on phone storage / reuse local file
            local_cact = f"{RUN_DIR}/syn_{vid}.cact"
            if os.path.exists(local_cact) and os.path.getsize(local_cact) > 1000000:
                pass  # already have the final cact on host — skip the pull
            else:
                nchunks = 0
                out = _adb(TRAIN_SERIAL, "shell",
                           f"cat {SDCARD}/train_{version}_chunk.log 2>/dev/null | grep -oE 'to [0-9]+' | tail -1")
                m = re.search(r"to (\d+)", out)
                if m:
                    nchunks = int(m.group(1)) // 8
                else:
                    # resumed runs log "skip chunk N" without step markers —
                    # fall back to the highest checkpoint that exists on phone storage
                    lout = _adb(TRAIN_SERIAL, "shell",
                                f"ls {SDCARD}/syn_{version}_c*.cact 2>/dev/null")
                    nums = [int(x) for x in re.findall(r"_c(\d+)\.cact", lout)]
                    nchunks = max(nums) if nums else 0
                if not nchunks:
                    _fail(f"no checkpoint found on {SDCARD} for final gate")
                    return
                sd_src = f"{SDCARD}/syn_{version}_c{nchunks}.cact"
                pull = subprocess.run(["adb", "-s", TRAIN_SERIAL, "pull",
                                       sd_src, local_cact],
                                      capture_output=True, timeout=120)
                if pull.returncode != 0 or not os.path.exists(local_cact):
                    _fail(f"checkpoint pull failed: {str(pull.stderr)[:80]}")
                    return
        _stage("merge")
        # 2. merge with tokenizer
        import shutil
        shutil.copy(local_cact,
                    os.path.join(NEEDLE_DIR, "adapters", "syn_final.cact"))
        try:
            subprocess.run(
                [os.path.join(NEEDLE_DIR, ".venv", "bin", "python3"),
                 os.path.join(NEEDLE_DIR, "tools", "merge_export.py"),
                 os.path.join(NEEDLE_DIR, "adapters", f"syn_{vid}_merged.cact"),
                 "--tokenizer"],
                capture_output=True, text=True, timeout=300)
        except Exception:
            return
        # 3. start the merged backend — PHONE first (~11x faster), host fallback.
        # (v23R -> digits "23" for the port formula)
        digits = re.sub(r"[^0-9]", "", version)
        port = 8360 + (((int(digits) if digits else 0) + (ckpt or 0)) % 20)
        merged = os.path.join(NEEDLE_DIR, "adapters", f"syn_{vid}_merged.cact")
        if not os.path.exists(merged):
            _fail("merge produced no adapter file")
            return
        _stage("serve")

        def _phone_gate():
            """Serve the merged cact on a needle-capable phone and gate through
            an adb forward. Returns True when the gate was launched."""
            candidates = [s.strip() for s in _env("TOOLRX_GATE_SERIALS").split(",") if s.strip()]
            if not candidates:
                candidates = [d.get("serial") for d in _load_devices()
                              if d.get("serial") and not d.get("executor")]
            serial = None
            for s in candidates:
                if s == TRAIN_SERIAL:
                    continue
                st = _adb(s, "get-state")
                if st.strip() != "device":
                    continue
                # RAM floor: a phone that just OOM-killed our needle wastes a run
                mem = _adb(s, "shell",
                           "cat /proc/meminfo | grep MemAvailable").split()
                try:
                    if int(mem[1]) < 800_000:        # <~780MB free
                        log.info("gate skip %s: low RAM (%s kB)", s,
                                 mem[1] if len(mem) > 1 else "?")
                        continue
                except Exception:
                    pass
                serial = s
                break
            if not serial:
                return False
            phone_cact = f"/data/local/tmp/syn_{version}_merged.cact"
            push = subprocess.run(["adb", "-s", serial, "push", merged, phone_cact],
                                  capture_output=True, timeout=180)
            # ensure the ARM64 needle_model binary is present (some phones lack it)
            has_bin = _adb(serial, "shell",
                           "ls /data/local/tmp/needle_model 2>/dev/null").strip()
            if not has_bin:
                subprocess.run(["adb", "-s", serial, "push",
                                "" + NEEDLE_DIR + "/runtime/needle_model.arm64",
                                "/data/local/tmp/needle_model"],
                               capture_output=True, timeout=120)
                _adb(serial, "shell", "chmod 755 /data/local/tmp/needle_model")
            if push.returncode != 0:
                return False
            # kill any stale instance, then setsid-launch (plain `nohup ... &`
            # HANGS adb on long-lived children — setsid returns instantly)
            _adb(serial, "shell",
                 f"pkill -f 'needle_model.*syn_{vid}_merged' 2>/dev/null")
            subprocess.run(["adb", "-s", serial, "shell",
                            f"setsid /data/local/tmp/needle_model {phone_cact} "
                            f"--serve --port {port} "
                            f"> /data/local/tmp/needle_{vid}.log 2>&1 < /dev/null &"],
                           capture_output=True, timeout=30)
            subprocess.run(["adb", "-s", serial, "forward", f"tcp:{port}", f"tcp:{port}"],
                           capture_output=True, timeout=30)
            ok = False
            for _ in range(60):          # phone needs ~30-45s to mmap the cact
                time.sleep(1)
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
                    ok = True
                    break
                except Exception:
                    pass
            if not ok:
                return False
            with _VERIFIES_LOCK:
                v = _VERIFIES.setdefault(version, {})
                v["phone"] = serial
            return True

        def _host_gate():
            # POLICY: keep LLM inference off the host by default. Gates run on
            # phones or they do not run. Only an explicit
            # TOOLRX_ALLOW_HOST_GATE=1 re-enables the old fallback.
            if os.environ.get("TOOLRX_ALLOW_HOST_GATE") != "1":
                log.info("host gate disabled by policy (no phone available)")
                return False
            # if the late-starting phone backend now answers the forward, don't
            # spawn a duplicate host backend — credit the phone instead
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
                r = subprocess.run(["adb", "forward", "--list"], capture_output=True,
                                   text=True, timeout=15)
                line = next((l for l in r.stdout.splitlines() if f"tcp:{port}" in l), "")
                serial = line.split()[0] if line else None
                if serial:
                    with _VERIFIES_LOCK:
                        _VERIFIES.setdefault(version, {})["phone"] = serial
                    return True
            except Exception:
                pass
            backend = subprocess.Popen(
                ["" + NEEDLE_DIR + "/runtime/needle_model", merged,
                 "--serve", "--port", str(port)],
                stdout=open(f"{RUN_DIR}/needle_{version}.log", "w"),
                stderr=subprocess.STDOUT, start_new_session=True)
            ok = False
            for _ in range(20):
                time.sleep(1)
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
                    ok = True
                    break
                except Exception:
                    pass
            return ok

        came_up = _phone_gate() or _host_gate()
        if not came_up:
            _fail(f"backend did not come up on :{port}")
            return
        _stage("gate")
        # 4. launch the gate detached
        gate_log = f"{RUN_DIR}/gate_{version}.log"
        with open(gate_log, "w"):
            pass
        _stage("gate")
        # 4. launch the gate detached
        gate_log = f"{RUN_DIR}/gate_{version}.log"
        with open(gate_log, "w"):
            pass
        proc = subprocess.Popen(
            ["bash", "-c",
             f"{{ echo GATE_START $(date +%s) > {gate_log}; "
             f"cd " + NEEDLE_DIR + " && source .venv/bin/activate && "
             f"exec python3 -u {RUN_DIR}/gate_harness.py http://127.0.0.1:{port} 120; }} "
             f">> {gate_log} 2>&1"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        with _VERIFIES_LOCK:
            v = _VERIFIES.setdefault(version, {})
            v.update({"pid": proc.pid, "port": port,
                      "started": time.time(), "total": 120})

        # 5. cleanup: when the gate exits, free phone RAM (kill needle) + drop forward
        def _cleanup():
            try:
                proc.wait()
            except Exception:
                pass
            try:
                with open(gate_log, "a") as fh:
                    fh.write(f"GATE_END {int(time.time())}\n")
            except Exception:
                pass
            serial = None
            with _VERIFIES_LOCK:
                serial = _VERIFIES.get(version, {}).get("phone")
            if serial:
                subprocess.run(["adb", "-s", serial, "shell",
                                f"pkill -f 'needle_model.*syn_{version}_merged'"],
                               capture_output=True, timeout=30)
                subprocess.run(["adb", "-s", serial, "forward", "--remove",
                                f"tcp:{port}"], capture_output=True, timeout=30)
            else:
                # host backend — kill it to reclaim RAM
                subprocess.run(["bash", "-c",
                                "pkill -f 'needle_model.*syn_"
                                f"{vid}_merged.cact --serve --port {port}'"],
                               capture_output=True, timeout=15)

        threading.Thread(target=_cleanup, daemon=True).start()

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    return None, f"verify queued: {version}"


def _build_focused_corpus(src_phone):
    """Read the source corpus (host mirror of the phone path), oversample the weak
    gate classes (probe/question, git, calc, and failing multi-tool combos), and
    push a class-balanced `train_focused.jsonl` to the phone. Returns example count."""
    host = src_phone.replace(f"{SDCARD}/", RUN_DIR + "/")
    src = host if os.path.exists(host) else src_phone
    rows = []
    for line in open(src):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    if not rows:
        raise RuntimeError("source corpus empty")

    def _cls(d):
        names = [a["name"] for a in (d.get("answers") or [])]
        if "edit_file" in names:
            return "edit"
        if "write_file" in names:
            return "build"
        if any(n in ("git_status", "git_commit") for n in names):
            return "git"
        if "calculate" in names:
            return "calc"
        if "question" in names:
            return "probe"
        if "bash" in names:
            return "build"
        if all(n in ("list_dir", "read_file", "search_files") for n in names):
            return "fs"
        return "other"

    from collections import defaultdict
    by_class = defaultdict(list)
    for d in rows:
        by_class[_cls(d)].append(d)

    # target equal-ish representation; weak classes get oversampled hard
    targets = {"probe": 320, "git": 200, "calc": 200, "fs": 300,
               "edit": 300, "build": 400, "other": 50}
    out = []
    for cls, arr in by_class.items():
        tgt = targets.get(cls, 50)
        if not arr:
            continue
        reps = max(1, (tgt + len(arr) - 1) // len(arr))
        for _ in range(reps):
            out.extend(arr)
        if reps > 1:
            out.extend(arr[: (tgt - len(arr) * (reps - 1))])

    # push focused corpus to the phone
    focused = f"{SDCARD}/train_focused.jsonl"
    tmp_host = RUN_DIR + "/train_focused.jsonl"
    with open(tmp_host, "w") as fh:
        for d in out:
            fh.write(json.dumps(d) + "\n")
    adb = subprocess.run(["adb", "-s", TRAIN_SERIAL, "push", tmp_host, focused],
                         capture_output=True, timeout=120)
    if adb.returncode != 0:
        raise RuntimeError("adb push failed: " + (adb.stderr or adb.stdout or "")[:200])
    log.info("focused corpus: %d examples -> %s", len(out), focused)
    return len(out)


def _launch_training(version, corpus, init, total_steps, chunksize=8,
                     lr="5e-5", epoch_seed=None):
    """Generate + push run script, then start the supervisor. Returns error string or None.
    lr/epoch_seed let the auto-cycle vary experiments (identical seed+data+init
    reproduces byte-identical adapters -> identical gate scores = wasted cycles)."""
    if re.search(r"[^a-zA-Z0-9_]", version):
        return "bad version"
    if epoch_seed is None:
        m = re.search(r"(\d+)", version)
        epoch_seed = (int(m.group(1)) if m else 0) * 1009 + 17
    script = f"""#!/bin/bash
# {version}: dashboard-launched training run.
exec >> {SDCARD}/train_{version}_chunk.log 2>&1
cd /root
export TMPDIR=/root/tmp
export PYTHONUNBUFFERED=1
export MALLOC_ARENA_MAX=1
mkdir -p /root/tmp
DATA={corpus}
BASE=/root/base/weights/needle2.pkl
TOTAL={total_steps}
PER={chunksize}
LR={lr}
EPOCH_SEED={epoch_seed}
FAILED=0
for ((chunk=1; chunk*PER<=TOTAL; chunk++)); do
  OUT=/root/syn_{version}_c${{chunk}}.cact
  if [ -f "$OUT" ]; then echo "skip chunk $chunk ($OUT exists)"; continue; fi
  PREV={init}
  for ((c=chunk-1; c>=1; c--)); do
    if [ -f "/root/syn_{version}_c${{c}}.cact" ]; then PREV=/root/syn_{version}_c${{c}}.cact; break; fi
  done
  echo "=== CHUNK $chunk: +$PER steps (to $((chunk*PER))), init=$PREV out=$OUT $(date) ==="
  if [ "$PREV" != "base" ] && [ -n "$PREV" ] && [ -f "$PREV" ]; then
    python3 /usr/local/bin/needle finetune "$DATA" \\
      --epochs 1 --batch-size 1 --max-len 768 --lr "$LR" --lora-alpha 16 --lora-rank 16 \\
      --epoch-seed "$EPOCH_SEED" \\
      --max-steps "$PER" --ckpt-every "$PER" \\
      --lora-init "$PREV" \\
      --checkpoint "$BASE" --out "$OUT" 2>&1
  else
    echo "fresh LoRA from base (no --lora-init) — start $chunk clean"
    python3 /usr/local/bin/needle finetune "$DATA" \\
      --epochs 1 --batch-size 1 --max-len 768 --lr "$LR" --lora-alpha 16 --lora-rank 16 \\
      --epoch-seed "$EPOCH_SEED" \\
      --max-steps "$PER" --ckpt-every "$PER" \\
      --checkpoint "$BASE" --out "$OUT" 2>&1
  fi
  rc=$?
  echo "=== CHUNK $chunk exit=$rc $(date) ==="
  [ "$rc" -ne 0 ] && FAILED=$((FAILED+1))
  [ "$rc" -eq 0 ] && cp "$OUT" "{SDCARD}/syn_{version}_c${{chunk}}.cact"
done
if [ "$FAILED" -eq 0 ]; then
  echo "ALL-{version.upper()}-DONE $(date)"
else
  echo "ALL-{version.upper()}-FAILED($FAILED) $(date)"
fi
"""
    local_script = os.path.join(TRAIN_DIR, f"run_{version}.sh")
    try:
        with open(local_script, "w") as fh:
            fh.write(script)
        subprocess.run(["adb", "-s", TRAIN_SERIAL, "push", local_script,
                        f"{SDCARD}/run_{version}.sh"], capture_output=True, timeout=60)
        # reset log
        subprocess.run(["adb", "-s", TRAIN_SERIAL, "shell",
                        f"rm -f {SDCARD}/train_{version}_chunk.log"],
                       capture_output=True, timeout=30)
    except Exception as e:
        return f"push failed: {e}"
    # launch supervisor detached
    nchunks = max(1, (total_steps + chunksize - 1) // chunksize)
    sup = subprocess.Popen(
        [sys.executable, TRAIN_SUP, version, str(nchunks), TRAIN_SERIAL],
        cwd=TRAIN_DIR, stdout=open(os.path.join(TRAIN_DIR, "sup.log"), "a"),
        stderr=subprocess.STDOUT, start_new_session=True)
    with TRAIN_LOCK:
        TRAIN_STATE.update(version=version, status="running", chunks_total=nchunks,
                           supervisor_pid=sup.pid, corpus=corpus, init=init,
                           steps_total=total_steps, started=time.time(),
                           chunks_done=0)
    return None


def _repeat_last_training():
    """Find the newest phone-storage/run_v*.sh on the training phone by mtime, parse the
    ACTUAL last run's params, and launch a copy labeled v##R (v23R1 on collision)
    with the same shape — a repeat never clobbers the original run's outputs.
    (Re-added 2026-08-22 from AGENTS.md spec; original lost with /tmp.)"""
    listing = _adb(TRAIN_SERIAL, "shell", f"ls -t {SDCARD}/run_v*.sh 2>/dev/null")
    cands = [l.strip() for l in listing.splitlines() if l.strip().endswith(".sh")]
    if not cands:
        return "no run_v*.sh scripts found on phone", None
    newest = os.path.basename(cands[0])
    m = re.match(r"run_(v[0-9]+[A-Za-z0-9]*)(?:\.sh)?", newest) or \
        re.match(r"run_(v[0-9]+)", newest)
    if not m:
        return f"cannot parse version from {newest}", None
    base = m.group(1)

    body = _adb(TRAIN_SERIAL, "shell", f"cat {SDCARD}/{newest}")
    def grab(pat, default=None):
        mm = re.search(pat, body, re.M)
        return mm.group(1).strip() if mm else default
    data = grab(r"^DATA=(\S+)", f"{SDCARD}/train_full_v2.jsonl")
    per = int(grab(r"^PER=(\d+)", "8") or 8)
    total = grab(r"^TOTAL=(\d+)")
    if not total:  # older epoch-style scripts
        es = int(grab(r"^EPOCH_STEPS=(\d+)", "32") or 32)
        ep = int(grab(r"^EPOCHS=(\d+)", "1") or 1)
        total = str(es * ep)
    init = grab(r'^PREV=(.+)$', "") or ""
    init = init.split(" ")[0].strip('"') or "/root/syn_v13_c15.cact"

    # collision-safe label: v23 -> v23R -> v23R1 ...
    label = base + "R"
    n = 1
    while ("device" in _adb(TRAIN_SERIAL, "shell",
                            f"[ -f {SDCARD}/run_{label}.sh ] && echo device")) or \
          os.path.exists(os.path.join(TRAIN_DIR, f"run_{label}.sh")):
        label = f"{base}R{n}"
        n += 1

    err = _launch_training(label, data, init, int(total), per)
    if err:
        return err, None
    return None, (f"{label} <- {base} ({total} steps, per {per}, data {data})")


def _spawn_llm_task(query):
    tid = uuid.uuid4().hex[:10]
    with _TASKS_LOCK:
        _TASKS[tid] = {"status": "running", "query": query}
        _save_task(tid)
    import urllib.request

    def run():
        import re
        try:
            req = urllib.request.Request(
                os.environ.get("LLM_URL", "http://127.0.0.1:8900/"),
                data=json.dumps({"query": query}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3600) as resp:
                data = json.loads(resp.read())
            with _CANCELLED_LOCK:
                cancelled = tid in _CANCELLED
            if cancelled:
                with _TASKS_LOCK:
                    _TASKS[tid] = {"status": "cancelled", "query": query}
                    _save_task(tid)
                return
            _mark_route_activity(data.get("route", "needle"))
            # build a useful result: response text + what tool calls wrote
            obs = data.get("observations") or []
            writes = [o.get("result") for o in obs
                      if str(o.get("result", "")).startswith("[wrote")]
            text = data.get("response") or ""
            if writes and not text:
                text = "Built files:\n" + "\n".join(str(w) for w in writes[:12])
            elif writes:
                text = text + "\n" + "\n".join(str(w) for w in writes[:8])
            # auto-save HTML code blocks from the executor to index.html so the
            # preview shows the built web page
            resp_text = data.get("response") or ""
            if resp_text:
                html = None
                m = re.search(r"```html\s*(.*?)```", resp_text, re.S)
                if m:
                    html = m.group(1).strip()
                elif "<!DOCTYPE" in resp_text:
                    i = resp_text.find("<!DOCTYPE")
                    html = resp_text[i:].replace("```", "").strip()
                if html:
                    pdir = PREVIEW_DIR
                    complete = "</html>" in html.lower()
                    try:
                        with open(os.path.join(pdir, "index.html"), "w") as fh:
                            fh.write(html)
                        tag = f"[saved {'complete' if complete else 'INCOMPLETE (truncated)'} {len(html)} chars to index.html]"
                        text = (text + "\n" + tag) if text else tag
                    except Exception:
                        pass
            with _TASKS_LOCK:
                _TASKS[tid] = {"status": "done", "query": query, "text": text,
                               "raw": data}
                _save_task(tid)
        except Exception as e:  # noqa: BLE001
            with _TASKS_LOCK:
                _TASKS[tid] = {"status": "error", "query": query,
                               "error": str(e)}
                _save_task(tid)
    threading.Thread(target=run, daemon=True).start()
    return tid

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">
<meta name="theme-color" content="#050a06">
<title>toolrx</title>
<style>
  :root{--neon:#39ff14}
  *{box-sizing:border-box}
  html,body{height:100%;margin:0}
  body{font-family:ui-monospace,monospace;background:#050a06;color:#d8ffe0;margin:0;
       height:100vh;height:100dvh;display:flex;flex-direction:column;overflow:hidden;
       -webkit-text-size-adjust:100%;text-size-adjust:100%}
  header{padding:10px 16px;padding-top:calc(10px + env(safe-area-inset-top));
         border-bottom:1px solid #0f3d17;background:#050a06;flex:0 0 auto;z-index:5}
  h1{font-size:15px;margin:0;letter-spacing:.5px}
  h1 span{color:var(--neon);text-shadow:0 0 8px rgba(57,255,20,.6)}
  .meta{color:#3f7a4a;font-size:10px;margin-top:2px;line-height:1.35}
  main{flex:1 1 auto;min-height:0;display:flex;flex-direction:column;
       max-width:1200px;width:100%;margin:0 auto;padding:0 10px}
  .split{flex:1 1 auto;min-height:0;display:flex;gap:8px}
  #log{flex:1 1 46%;min-width:0;font-size:12.5px;line-height:1.6;word-break:break-word;
       overflow-y:auto;padding:2px 2px;scroll-behavior:smooth}
  #previewPane{flex:1 1 54%;min-width:0;display:flex;flex-direction:column;min-height:0;
       border:1px solid #0f3d17;border-radius:8px;background:#07120a;overflow:hidden}
  #previewPane .pv-head{display:flex;align-items:center;gap:6px;padding:5px 8px;
       border-bottom:1px solid #0f3d17;color:#3f7a4a;font-size:11px;flex:0 0 auto}
  #previewPane .pv-head button{margin-left:auto;min-height:0;padding:2px 8px;font-size:11px}
  #previewPane iframe{flex:1 1 auto;min-height:0;width:100%;border:0;background:#fff}
  form{display:flex;gap:6px;align-items:flex-end}
  #q{flex:1;min-width:0;padding:11px 12px;font-size:16px;line-height:1.35;resize:none;
     border:1px solid #1e6b2b;border-radius:10px;background:#07120a;color:var(--neon);
     outline:none;max-height:36vh;overflow-y:auto;overflow-x:hidden;font-family:inherit;
     scrollbar-width:none}
  #q::-webkit-scrollbar{display:none;width:0;height:0}
  #q::placeholder{color:#2c5a35}
  #q:focus{border-color:var(--neon);box-shadow:0 0 10px rgba(57,255,20,.25)}
  button{padding:0 18px;font-size:16px;border:0;border-radius:10px;cursor:pointer;
         font-weight:700;letter-spacing:.3px;min-height:46px;touch-action:manipulation}
  button:disabled{opacity:.4;cursor:not-allowed}
  #runBtn{background:var(--neon);color:#03130a}
  /* bottom composer: always visible, log flexes in the middle */
  .bar{flex:0 0 auto;background:#050a06;border-top:1px solid #0f3d17;
       padding:8px 10px;padding-bottom:calc(8px + env(safe-area-inset-bottom))}
  .bar form{max-width:820px;margin:0 auto}

  /* ---- neon stereo equalizer (shown while a tool is running) ---- */
  #eq{display:none;height:52px;overflow:hidden;position:relative;margin:10px 0;
      border:1px solid #0f3d17;border-radius:8px;background:#07120a;flex:0 0 auto}
  #eq.on{display:block}
  .eq-track{position:absolute;inset:0;display:flex;align-items:flex-end;gap:2px;
      padding:4px 6px;
      -webkit-mask-image:linear-gradient(90deg,transparent,#000 10%,#000 90%,transparent);
      mask-image:linear-gradient(90deg,transparent,#000 10%,#000 90%,transparent);
      animation:eqmove 2.6s linear infinite}
  .eq-track span{flex:0 0 12px;height:12%;
      background:linear-gradient(180deg,#b7ff9f,var(--neon) 55%,#00c853);
      box-shadow:0 0 8px rgba(57,255,20,.7);border-radius:2px;
      animation:eqbar .85s ease-in-out infinite}
  @keyframes eqmove{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
  @keyframes eqbar{0%,100%{height:8%}50%{height:100%}}

  /* ---- log ---- */
  .entry{border-left:2px solid #123d1b;padding:4px 10px;margin:4px 0;background:#07120a;
         border-radius:0 6px 6px 0}
  .entry .ts{color:#2f6b3b;font-size:10.5px;float:right;margin-left:10px}
  .entry .lbl{font-weight:700}
  .entry .lbl.q{color:#fff}.entry .lbl.thought{color:#5fbf6f}.entry .lbl.tool{color:var(--neon)}
  .entry .lbl.res{color:#9dffb0}.entry .lbl.err{color:#ff8080}.entry .lbl.plan{color:#ffd166}
  .entry .lbl.stat{color:#6f9d7a;font-weight:400;font-size:11px}
  .entry pre.body{margin:4px 0 0;white-space:pre-wrap;color:#c9f5d0;font-family:inherit;
                  font-size:12px;max-height:none}
  .entry.collapsed pre.body{max-height:4.6em;overflow:hidden}
  .expand{display:none;margin-top:4px;color:var(--neon);background:none;border:none;
          padding:2px 0;font-size:11px;cursor:pointer;text-decoration:underline}
  .entry.collapsible .expand{display:inline-block}
  /* ---- live module cards ---- */
  .entry.module{border-left:2px solid var(--neon);background:#07150c;margin:6px 0}
  .mod-top{display:flex;align-items:center;gap:8px}
  .mod-top .lbl{flex:1}
  .mod-live{color:var(--neon);font-size:12px;animation:blink 1.2s infinite}
  .mod-end{color:#ff8080;font-size:12px}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}
  .mod-body{font-family:inherit;font-size:12px;color:#c9f5d0;margin-top:4px;
            white-space:pre-wrap;word-break:break-word;min-height:1em}
  .mod-close{background:none;border:none;color:#6f9d7a;font-size:14px;cursor:pointer;
             padding:2px 6px;border-radius:6px}
  .mod-close:hover{color:#ff8080}
  /* ---- confirm-gated edit preview ---- */
  .entry.edit{border-left:2px solid #ffd166;background:#161106;margin:6px 0}
  .mod-btns{display:flex;gap:8px;margin-top:6px}
  .mod-apply{background:#ffd166;color:#2a1f00;min-height:38px;font-size:14px}
  .mod-undobtn{background:none;color:#ffd166;border:1px solid #ffd166;min-height:38px;font-size:14px}
  /* ---- edit form ---- */
  #editform{display:none;margin-top:6px;flex-direction:column;gap:6px;max-width:820px;margin-left:auto;margin-right:auto}
  #editform.open{display:flex}
  .ef-row{display:flex;gap:6px}
  #efPath{flex:1;min-width:0;padding:10px;font-size:15px;border:1px solid #1e6b2b;border-radius:8px;background:#07120a;color:var(--neon)}
  #efContent{width:100%;padding:10px;font-size:15px;line-height:1.35;border:1px solid #1e6b2b;border-radius:8px;background:#07120a;color:var(--neon);resize:vertical;max-height:32vh}
  #efGo{background:#ffd166;color:#2a1f00;padding:0 12px;font-size:14px;min-height:40px}
  .mode-btn{background:none;color:#3f7a4a;border:1px solid #1e6b2b;font-size:12px;padding:2px 8px;min-height:30px;cursor:pointer;border-radius:6px}
  .mode-btn.on{color:var(--neon);border-color:var(--neon)}

  /* ---- quick-command chips ---- */
  #chips{display:flex;flex-wrap:wrap;gap:6px;max-width:820px;margin:0 auto 8px}
  .chip{font:inherit;font-size:12px;color:#7fe88e;background:#07150c;border:1px solid #1e6b2b;
        border-radius:999px;padding:6px 11px;min-height:34px;cursor:pointer;touch-action:manipulation;
        transition:border-color .12s,color .12s,box-shadow .12s}
  .chip:hover{border-color:var(--neon);color:var(--neon);box-shadow:0 0 8px rgba(57,255,20,.18)}
  .chip:active{transform:translateY(1px)}
  .chip.danger:hover{border-color:#ff8080;color:#ff8080;box-shadow:0 0 8px rgba(255,128,128,.2)}

  /* ---- result panels: structured tables + gauges ---- */
  .panel{border:1px solid #0f3d17;border-radius:8px;background:#050f08;margin-top:6px;overflow:hidden}
  .panel .phead{display:flex;align-items:center;gap:8px;padding:6px 10px;border-bottom:1px solid #0f3d17;
                color:#6f9d7a;font-size:10.5px;letter-spacing:.6px;text-transform:uppercase}
  .panel .phead .dot{width:7px;height:7px;border-radius:50%;background:var(--neon);
                     box-shadow:0 0 6px rgba(57,255,20,.7);flex:0 0 auto}
  .panel .pwrap{overflow-x:auto;padding:6px 10px 10px}
  .paneTable{width:100%;border-collapse:collapse;font-size:11.5px}
  .paneTable th{color:#6f9d7a;font-weight:700;text-align:left;padding:3px 8px 3px 0;
                border-bottom:1px solid #123d1b;white-space:nowrap;letter-spacing:.3px;font-size:10px;text-transform:uppercase}
  .paneTable td{padding:3px 8px 3px 0;color:#c9f5d0;white-space:nowrap;border-bottom:1px solid #0a2310}
  .paneTable tr:last-child td{border-bottom:0}
  .gauge{display:flex;align-items:center;gap:8px}
  .gauge .track{flex:1;min-width:60px;height:7px;border-radius:4px;background:#0f2a16;overflow:hidden}
  .gauge .fill{height:100%;background:linear-gradient(90deg,#00c853,var(--neon));border-radius:4px;
               transition:width .5s ease}
  .gauge .fill.hot{background:linear-gradient(90deg,#ffb14d,#ff6b4d)}
  .gauge .val{font-size:11px;color:#9dffb0;font-variant-numeric:tabular-nums;white-space:nowrap}

  /* ---- polish: scrollbar + status line ---- */
  #log::-webkit-scrollbar{width:8px}
  #log::-webkit-scrollbar-thumb{background:#123d1b;border-radius:4px}
  #log::-webkit-scrollbar-thumb:hover{background:#1e6b2b}
  #log::-webkit-scrollbar-track{background:transparent}
  .entry{border-radius:6px;transition:background .15s}
  .entry:hover{background:#08180c}
  #clearLog{background:none;border:none;color:#3f7a4a;font-size:10px;cursor:pointer;
            text-decoration:underline;padding:0;margin-left:10px}
  #clearLog:hover{color:#ff8080}

  /* ---- net config form ---- */
  #netform{display:none;margin-top:6px;flex-direction:column;gap:6px;max-width:820px;margin-left:auto;margin-right:auto}
  #netform.open{display:flex}
  #nfSpec{width:100%;padding:10px;font-size:15px;line-height:1.4;border:1px solid #1e6b2b;border-radius:8px;
          background:#07120a;color:var(--neon);resize:vertical;max-height:34vh;font-family:inherit;white-space:pre}
  #nfGen{background:var(--neon);color:#03130a;padding:0 14px;font-size:14px;min-height:40px}
  #nfCheck{background:none;color:#7fe88e;border:1px solid #1e6b2b;padding:0 14px;font-size:14px;min-height:40px}

  /* ---- multi-node lab panel ---- */
  #labform{display:none;margin-top:6px;flex-direction:column;gap:6px;max-width:820px;margin-left:auto;margin-right:auto}
  #labform.open{display:flex}
  #labSpec{width:100%;padding:10px;font-size:15px;line-height:1.4;border:1px solid #1e6b2b;border-radius:8px;
           background:#07120a;color:var(--neon);resize:vertical;max-height:40vh;font-family:inherit;white-space:pre}
  #lbState{background:none;color:#7fe88e;border:1px solid #1e6b2b;padding:0 14px;font-size:14px;min-height:40px}
  #lbNode{background:#07120a;color:var(--neon);border:1px solid #1e6b2b;border-radius:8px;min-height:40px;font-size:14px;padding:0 8px}
  #lbDown{background:none;color:#ff9d9d;border:1px solid #a13;padding:0 14px;font-size:14px;min-height:40px}
  #labLinks{display:flex;flex-direction:column;gap:6px}
  .lab-links .ll{display:flex;align-items:center;gap:8px;padding:6px 10px;border:1px solid #1e2b20;border-radius:8px;font-size:13px}
  .lab-links .ll .llid{flex:1;color:#7fe88e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .lab-links .ll button{background:none;border:1px solid #1e6b2b;color:#7fe88e;border-radius:6px;min-height:32px;padding:0 10px;font-size:12px}
  .lab-links .ll button.dn{color:#ff9d9d;border-color:#a13}
  .lab-links .ll button:disabled{opacity:.45;cursor:default}


  /* ---- mobile polish: bigger touch targets + comfortable type ---- */
  @media (max-width:640px){
    #q{font-size:17px;padding:13px 13px}
    button{padding:0 16px}
    .chip{font-size:13px;padding:9px 14px;min-height:40px}
    .bar{padding:10px 10px;padding-bottom:calc(10px + env(safe-area-inset-bottom))}
    #log{font-size:13.5px;line-height:1.65}
    .split{flex-direction:column}
    #previewPane{min-height:42vh}
    .entry{padding:6px 12px;margin:5px 0}
    .panel .pwrap{padding:8px 12px 12px}
    .paneTable{font-size:12.5px}
    .gauge .track{height:9px}
    .entry .ts{font-size:11px}
    .mod-close{font-size:16px;padding:4px 8px}
    .mod-apply,.mod-undobtn{min-height:44px}
    .mode-btn{font-size:13px;padding:4px 10px;min-height:36px}
    .ef-row input,#efPath{font-size:16px}
  }

</style></head><body>
<header><h1>toolrx <span>micro tool router</span></h1>
  <div class="meta">46 KB model &middot; knowledge/.md as weights &middot; read-only / dry-run tools only<button id="clearLog" type="button">clear log</button></div></header>
<main>
  <div id="eq" aria-hidden="true"><div class="eq-track" id="eqTrack"></div></div>
  <div class="split">
    <div id="log"></div>
    <div id="previewPane">
      <div class="pv-head"><span>preview · built files</span>
        <button id="pvReload" type="button">reload</button></div>
      <iframe id="pv" title="preview" sandbox="allow-scripts allow-modals"></iframe>
    </div>
  </div>
</main>
<div class="bar">
  <div id="chips">
    <button type="button" class="chip" data-q="list files on device">list files</button>
    <button type="button" class="chip" data-q="list contents of all files">list all</button>
    <button type="button" class="chip" data-q="how much memory is free">memory</button>
    <button type="button" class="chip" data-q="how much disk space is free">disk</button>
    <button type="button" class="chip" data-q="how long has the machine been up">uptime</button>
    <button type="button" class="chip" data-q="what processes are running">processes</button>
    <button type="button" class="chip" data-q="ping localhost">ping</button>
    <button type="button" class="chip" data-q="track memory live every 5 seconds for 60 seconds">track mem</button>
    <button type="button" class="chip danger" data-q="stop all modules">stop all</button>
  </div>
  <form id="f">
    <textarea id="q" rows="1" placeholder="ask anything… (enter to send, shift+enter for newline)"></textarea>
    <button id="llmBtn" type="submit">Send</button>
  </form>
  <div class="ef-row"><button id="editToggle" type="button" class="mode-btn">edit a file</button>
    <button id="netToggle" type="button" class="mode-btn">net config</button>
    <button id="labToggle" type="button" class="mode-btn">lab lab</button></div>
  <div id="editform">
    <div class="ef-row"><input id="efPath" placeholder="file path, e.g. notes.txt" autocomplete="off">
      <button id="efGo" type="button">Preview diff</button></div>
    <textarea id="efContent" rows="3" placeholder="new file contents... (line breaks kept)"></textarea>
  </div>
  <div id="netform">
    <textarea id="nfSpec" rows="4" placeholder="network spec (safe DSL)&#10;hostname r1&#10;int eth0 10.0.0.1/24&#10;route 0.0.0.0/0 via 10.0.0.254&#10;ospf router-id 10.0.0.1&#10;ospf net 10.0.0.0/24 area 0&#10;bgp asn 65000 router-id 10.0.0.1&#10;bgp neighbor 10.0.1.2 remote-as 65001&#10;bgp network 10.0.0.0/24&#10;fw allow tcp 22&#10;fw drop all"></textarea>
    <div class="ef-row"><button id="nfGen" type="button">Generate</button>
      <button id="nfCheck" type="button">Check</button>
      <button id="nfPush" type="button" class="mode-btn">Push to lab</button>
      <button id="nfState" type="button" class="mode-btn">Check lab</button></div>
  </div>
  <div id="labform">
    <textarea id="labSpec" rows="6" placeholder="multi-node topology (safe DSL)&#10;node r1&#10;  eth0 10.0.1.1/24&#10;  eth1 10.0.2.1/24&#10;  ospf router-id 10.0.0.1&#10;node r2&#10;  eth0 10.0.1.2/24&#10;  eth1 10.0.3.2/24&#10;  ospf router-id 10.0.0.2&#10;node r3&#10;  eth0 10.0.2.3/24&#10;  eth1 10.0.3.3/24&#10;  ospf router-id 10.0.0.3&#10;link r1.eth0 r2.eth0&#10;link r1.eth1 r3.eth0&#10;link r2.eth1 r3.eth1"></textarea>
    <div class="ef-row"><button id="lbBuild" type="button" class="mode-btn">Build lab</button>
      <button id="lbState" type="button">State</button>
      <select id="lbNode"><option value="all">all nodes</option></select>
      <button id="lbDown" type="button" class="danger">Tear down</button></div>
    <div id="labLinks" class="lab-links"></div>
  </div>
</div>
<script>
const log=document.getElementById('log');
const f=document.getElementById('f'), q=document.getElementById('q');
const cards={}; // module id -> card element (for instant teardown)
const eq=document.getElementById('eq'), eqTrack=document.getElementById('eqTrack');
const eqOn=()=>eq.classList.add('on'), eqOff=()=>eq.classList.remove('on');
const pv=document.getElementById('pv'), pvReload=document.getElementById('pvReload');
function loadPreview(){
  const ts=Date.now();
  pv.src='/preview/index.html?t='+ts;
}
document.getElementById('pvReload').addEventListener('click',loadPreview);
(function buildBars(){const g=[];
  const step=14; /* 12px bar + 2px gap */
  const w=eq.clientWidth||600;
  const n=Math.max(4,Math.ceil(w/step));
  for(let i=0;i<n;i++){const s=document.createElement('span');
    s.style.animationDelay=(i*0.03)+'s';g.push(s);}
  g.forEach(s=>{eqTrack.appendChild(s);eqTrack.appendChild(s.cloneNode(true));});})();

function now(){const d=new Date();const p=x=>String(x).padStart(2,'0');
  return p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds());}
function tokensPerSec(text,ms){const t=(text||'').trim().split(/\\s+/).filter(Boolean).length;
  const s=ms/1000;return t+' tok \\u00b7 '+s.toFixed(2)+'s \\u00b7 '+(s>0?(t/s).toFixed(1):0)+'/s';}

const historyKey='toolrx.history.v3';
let restoring=false;
let busy=false;
let pending=[];
function saveHistory(){
  try{localStorage.setItem(historyKey,JSON.stringify(history.slice(-150)));}
  catch(e){}
}

function entry(label,text,kind,collapseThreshold){
  const w=document.createElement('div');w.className='entry';
  const ts=document.createElement('span');ts.className='ts';ts.textContent=now();
  const l=document.createElement('div');l.className='lbl '+kind;l.textContent=label;
  w.append(ts,l);
  if(text!==null&&text!==undefined&&text!==''){
    const panel=smartBody(String(text));
    if(panel){w.append(panel);}
    else{
      const pre=document.createElement('pre');pre.className='body';pre.textContent=String(text);
      const big=String(text).length>(collapseThreshold||0);
      w.append(pre);
      if(big){
        w.classList.add('collapsible','collapsed');
        const ex=document.createElement('button');ex.className='expand';ex.textContent='expand full ▾';
        ex.onclick=()=>{w.classList.toggle('collapsed');
          ex.textContent=w.classList.contains('collapsed')?'expand full ▾':'collapse ▴';
          log.scrollTop=log.scrollHeight;};
        w.append(ex);
      }
    }
  }
  log.appendChild(w);log.scrollTop=log.scrollHeight;
  if(!restoring&&kind!=='err'&&kind!=='stat'){history.push({k:kind,l:label,t:String(text||'')});saveHistory();}
  return w;
}

/* ---- smart result panels (tables + gauges) instead of raw pre ---- */
function gauge(pct){
  const g=document.createElement('div');g.className='gauge';
  const track=document.createElement('div');track.className='track';
  const fill=document.createElement('div');fill.className='fill'+(pct>90?' hot':'');
  fill.style.width=Math.max(2,Math.min(100,pct))+'%';
  track.append(fill);
  const val=document.createElement('span');val.className='val';val.textContent=pct+'%';
  g.append(track,val);return g;
}
function panelWrap(heading){
  const p=document.createElement('div');p.className='panel';
  const h=document.createElement('div');h.className='phead';
  const dot=document.createElement('span');dot.className='dot';
  const t=document.createElement('span');t.textContent=heading;
  h.append(dot,t);p.append(h);
  const pw=document.createElement('div');pw.className='pwrap';p.append(pw);
  return {p,pw};
}
function dfPanel(text){
  const {p,pw}=panelWrap('disk usage · df -h');
  const tb=document.createElement('table');tb.className='paneTable';
  const lines=text.split('\\n').filter(l=>l.trim());
  lines.forEach((line,i)=>{
    const cols=line.trim().split(/\\s{2,}|\\s+/);
    const tr=document.createElement('tr');
    cols.forEach(c=>{const cell=document.createElement(i===0?'th':'td');cell.textContent=c;tr.append(cell);});
    if(i>0&&cols.length>=5){
      const cell=document.createElement('td');cell.append(gauge(parseFloat(cols[4])||0));tr.append(cell);
    }
    tb.append(tr);
  });
  pw.append(tb);return p;
}
function psPanel(text){
  const {p,pw}=panelWrap('processes · ps aux');
  const tb=document.createElement('table');tb.className='paneTable';
  const lines=text.split('\\n').filter(l=>l.trim());
  lines.forEach((line,i)=>{
    const tr=document.createElement('tr');
    const cols=line.trim().split(/\\s{2,}|\\s+/);
    const want=i===0?cols:cols.slice(0,11);
    want.forEach(c=>{const cell=document.createElement(i===0?'th':'td');cell.textContent=c;tr.append(cell);});
    if(i>0&&cols.length>11){const cell=document.createElement('td');cell.textContent=cols.slice(11).join(' ');tr.append(cell);}
    tb.append(tr);
  });
  pw.append(tb);return p;
}
function memPanel(text){
  const {p,pw}=panelWrap('memory · /proc/meminfo');
  const kv={};
  text.split('\\n').forEach(line=>{const m=line.match(/^(\\w+):\\s*(\\d+)\\s*(kB)?/);if(m)kv[m[1]]=parseInt(m[2])*1024;});
  if(kv.MemTotal&&kv.MemAvailable){
    const used=kv.MemTotal-kv.MemAvailable;const pct=Math.round(100*used/kv.MemTotal);
    const g=document.createElement('div');g.className='gauge';
    const track=document.createElement('div');track.className='track';
    const fill=document.createElement('div');fill.className='fill'+(pct>90?' hot':'');
    fill.style.width=Math.max(2,Math.min(100,pct))+'%';track.append(fill);
    const val=document.createElement('span');val.className='val';
    val.textContent=fmtBytes(used)+' / '+fmtBytes(kv.MemTotal)+' used ('+pct+'%)';
    g.append(track,val);pw.append(g);
    const tb=document.createElement('table');tb.className='paneTable';
    const rows=[['total',fmtBytes(kv.MemTotal)],['used',fmtBytes(used)],['free',fmtBytes(kv.MemAvailable)],['buffers',fmtBytes(kv.Buffers||0)],['cache',fmtBytes(kv.Cached||0)]];
    rows.forEach(r=>{const tr=document.createElement('tr');
      r.forEach(c=>{const cell=document.createElement('td');cell.textContent=c;tr.append(cell);});tb.append(tr);});
    pw.append(tb);
  }else{pw.textContent=text;}
  return p;
}
function memLinePanel(text){
  const {p,pw}=panelWrap('memory · sys.mem_status');
  const m=text.match(/total=(\\d+)[^=]*free=(\\d+)[^=]*used=(\\d+)/);
  if(m){
    const total=parseInt(m[1])*1024,used=parseInt(m[3])*1024;
    const pct=Math.round(100*used/total);
    const g=document.createElement('div');g.className='gauge';
    const track=document.createElement('div');track.className='track';
    const fill=document.createElement('div');fill.className='fill'+(pct>90?' hot':'');
    fill.style.width=Math.max(2,Math.min(100,pct))+'%';track.append(fill);
    const val=document.createElement('span');val.className='val';
    val.textContent=fmtBytes(used)+' / '+fmtBytes(total)+' used ('+pct+'%)';
    g.append(track,val);pw.append(g);
    const tb=document.createElement('table');tb.className='paneTable';
    const rows=[['total',fmtBytes(total)],['used',fmtBytes(used)],['free',fmtBytes(parseInt(m[2])*1024)]];
    rows.forEach(r=>{const tr=document.createElement('tr');
      r.forEach(c=>{const cell=document.createElement('td');cell.textContent=c;tr.append(cell);});tb.append(tr);});
    pw.append(tb);
  }else{pw.textContent=text;}
  return p;
}
function smartBody(text){
  if(typeof text!=='string')return null;
  if(/^Filesystem\\s+.*Use%/.test(text))return dfPanel(text);
  if(/^USER\\s+PID\\s+/.test(text))return psPanel(text);
  if(/^MemTotal:/.test(text))return memPanel(text);
  if(/^total=\\d+[^=]*free=/.test(text))return memLinePanel(text);
  return null;
}

function addStat(label,text,kind,ms){const w=entry(label+'  ['+tokensPerSec(text,ms)+']',text,kind,400);
  return w;}

async function submit(path,q,runStat){
  if(busy){pending.push({path,q,runStat});entry('queued: '+q,'','stat');return;}
  busy=true;
  const started=performance.now();eqOn();
  const d=document.createElement('div');d.className='entry';
  const l=document.createElement('div');l.className='lbl q';
  l.textContent='> '+q;d.prepend(l);log.appendChild(d);log.scrollTop=log.scrollHeight;
  document.getElementById('q').value='';autogrow();
  try{
    const r=await (await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({query:q})})).json();
    const ms=performance.now()-started;eqOff();loadPreview();
    if(r.async){
      const tid=r.task;
      entry('\u25b8 local.llm','building in background\u2026','stat',400);
      const iv=setInterval(async()=>{
        try{
          const s=await (await fetch('/llm/status/'+tid)).json();
          if(s.status==='done'){clearInterval(iv);busy=false;eqOff();
            addStat('\u25b8 local.llm', s.text||'(done)','res',performance.now()-started);
            if(pending.length){const n=pending.shift();submit(n.path,n.q,n.runStat);}
          } else if(s.status==='error'){clearInterval(iv);busy=false;eqOff();
            entry('BLOCKED \u26a0 llm: '+(s.error||'error'),'','err');
            if(pending.length){const n=pending.shift();submit(n.path,n.q,n.runStat);}
          }
        }catch(e){clearInterval(iv);busy=false;eqOff();
          entry('BLOCKED \u26a0 llm: '+e,'','err');
          if(pending.length){const n=pending.shift();submit(n.path,n.q,n.runStat);}}
      },2000);
      return;
    }
    if(r.multi){
      (r.results||[]).forEach(x=>{
        const res=x.result||{},dec=x.decision||{};
        const lbl='> '+x.query+' \\u25b8 '+(dec.tool||'?');
        if(x.removed!==undefined){removeCards(x.removed);addStat(dec.tool||'module',x.note||'','res',ms);}
        else if(x.pending){if(x.pending.links)pinLabBuild(x.pending,lbl);else pinEdit(x.pending,lbl);}
        else if(x.module)pinModule(x.module,lbl);
        else addStat(lbl,''+ (res.result!==undefined?res.result:res.reason||''),
          res.ok?'res':'err',ms);
      });
      if(r.blocked)entry('\\u26a0 some commands were blocked','','err');
    } else if(r.blocked){
      entry('BLOCKED \\u26a0 '+r.reason,'','err');
    } else {
      const res=r.result||{};const dec=r.decision||{};
      if(dec.tool==='local.llm'){const t=(res.result||{}).text||'';const sec=(res.result||{}).seconds;
        addStat('\u25b8 local.llm'+(sec!=null?' \u00b7 '+sec+'s':''),t,t?'res':'err',ms);}
      else if(r.removed!==undefined){removeCards(r.removed);addStat(dec.tool||'module',r.note||'','res',ms);}
      else if(r.pending){if(r.pending.links)pinLabBuild(r.pending,'\u25b8 '+(dec.tool||'')+' · '+r.pending.summary);
        else pinEdit(r.pending,'\u25b8 '+(dec.tool||'')+' · '+r.pending.path);}
      else if(r.module)pinModule(r.module,'\\u25b8 '+(dec.tool||'')+' · '+r.module.name);
      else addStat(dec.tool||'?',''+ (res.result!==undefined?res.result:res.reason||''),
        res.ok?'res':'err',ms);
    }
  }catch(err){entry('network error: '+err,'','err');}
  busy=false;eqOff();
  if(pending.length){const n=pending.shift();submit(n.path,n.q,n.runStat);}
}

function removeCards(ids){
  (ids||[]).forEach(id=>{const c=cards[id];if(c){c.remove();delete cards[id];}});
}

/* ---- confirm-gated file edit preview ---- */
function pinEdit(p,lbl){
  const w=document.createElement('div');w.className='entry edit';
  const top=document.createElement('div');top.className='mod-top';
  const t=document.createElement('div');t.className='lbl tool';
  t.textContent=(lbl||'\\u25b8 file.edit')+' \\u00b7 '+(p.exists?'edit':'new')+' \\u00b7 '+p.old_len+'\\u2192'+p.new_len+' chars';
  top.append(t);
  const body=document.createElement('div');body.className='mod-body';
  body.textContent=p.diff||'(identical content)';
  const btns=document.createElement('div');btns.className='mod-btns';
  const applyB=document.createElement('button');applyB.className='mod-apply';applyB.textContent='Apply';
  const undoB=document.createElement('button');undoB.className='mod-undobtn';undoB.textContent='Undo';undoB.disabled=true;
  applyB.onclick=async()=>{
    applyB.disabled=true;applyB.textContent='applying...';
    try{
      const r=await (await fetch('/apply',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({id:p.id})})).json();
      body.textContent=(r.applied?('\\u2713 applied '+r.path+(r.backup?' \\u00b7 backup '+r.backup:'')):('error: '+(r.reason||'')));
      undoB.disabled=false;applyB.disabled=true;applyB.textContent='Applied';
    }catch(e){applyB.disabled=false;applyB.textContent='Apply';body.textContent='network error';}
  };
  undoB.onclick=async()=>{
    undoB.disabled=true;
    try{
      const r=await (await fetch('/undo',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({id:p.id})})).json();
      body.textContent='\\u21ba '+(r.note||'undo');applyB.disabled=true;
    }catch(e){undoB.disabled=false;body.textContent='network error';}
  };
  btns.append(applyB,undoB);w.append(top,body,btns);log.appendChild(w);log.scrollTop=log.scrollHeight;
}

/* ---- live-pinned module cards (client-pull on interval) ---- */
function pinModule(info,label){
  const w=document.createElement('div');w.className='entry module';
  const ts=document.createElement('span');ts.className='ts';
  const top=document.createElement('div');top.className='mod-top';
  const l=document.createElement('div');l.className='lbl tool';
  l.textContent=label||('\\u25b8 module '+info.id);top.append(l);
  const live=document.createElement('span');live.className='mod-live';live.textContent='●';
  top.append(live);
  const body=document.createElement('div');body.className='mod-body';
  body.textContent='waiting for first sample...';
  const close=document.createElement('button');close.className='mod-close';close.textContent='\\u2715';
  close.onclick=async()=>{fetch('/mod/'+info.id+'/stop',{method:'POST'}).then(()=>{});
    clearInterval(iv);w.remove();delete cards[info.id];};
  top.append(close);w.append(ts,top,body);log.appendChild(w);cards[info.id]=w;
  const iv=setInterval(async()=>{
    try{
      const resp=await fetch('/mod/'+info.id);
      const m=await resp.json();
      if(!resp.ok||!m||m.error){ // module stopped -> end the card
        clearInterval(iv);live.classList.remove('mod-live');live.classList.add('mod-end');
        live.textContent='\\u25a0 ended';body.textContent='module stopped';return;
      }
      if(m.state){body.textContent=formatModule(m);ts.textContent=now();}
    }catch(e){clearInterval(iv);body.textContent='module stopped';}
  },Math.max(1000,info.interval*1000));
  log.scrollTop=log.scrollHeight;
}
function fmtBytes(n){if(n==null)return '?';
  const u=['B','K','M','G','T'];let i=0;while(n>=1024&&i<u.length-1){n/=1024;i++;}return n.toFixed(1)+u[i];}
function remaining(m){return m.remaining>0?' · '+Math.floor(m.remaining/60)+':'+String(m.remaining%60).padStart(2,'0')+' left':'';}
function formatModule(m){
  const s=m.state||{};const t=m.interval;const r=remaining(m);
  if(typeof s==='string')return s+' · every '+t+'s'+r;
  if('used_pct'in s)return 'mem '+fmtBytes(s.used_kb*1024)+'/'+fmtBytes(s.total_kb*1024)
    +' used ('+s.used_pct+'%) · free '+fmtBytes(s.free_kb*1024)+' · every '+t+'s'+r;
  if('used'in s&&!('pct'in s))return 'disk used '+fmtBytes(s.used)+'/'+fmtBytes(s.total)
    +' ('+(s.used_pct||0)+'%) · free '+fmtBytes(s.free)+' · every '+t+'s'+r;
  if('seconds'in s)return 'up '+fmtBytes(s.seconds)+' ('+Math.round(s.seconds/8640)/10+'d) · every '+t+'s'+r;
  return JSON.stringify(s)+r;
}

function autogrow(){const q=document.getElementById('q');
  q.style.height='auto';q.style.height=Math.min(q.scrollHeight,window.innerHeight*0.38)+'px';}
document.getElementById('llmBtn').addEventListener('click',e=>{
  e.preventDefault();const q=document.getElementById('q').value.trim();if(q)submit('/llm',q);});
document.getElementById('q').addEventListener('input',autogrow);
document.getElementById('q').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();const q=e.target.value.trim();if(q)submit('/llm',q);}});
/* ---- edit form ---- */
const ef=document.getElementById('editform');
document.getElementById('editToggle').addEventListener('click',()=>{
  ef.classList.toggle('open');document.getElementById('editToggle').classList.toggle('on',ef.classList.contains('open'));});
document.getElementById('efGo').addEventListener('click',async()=>{
  const path=document.getElementById('efPath').value.trim();
  const content=document.getElementById('efContent').value;
  if(!path)return;
  try{
    const r=await (await fetch('/edit/prepare',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path,content})})).json();
    if(r.blocked){addStat('file.edit',''+(r.reason||''),'err',0);return;}
    pinEdit((r.result||{}).result,'\u25b8 file.edit · '+path);
  }catch(err){addStat('file.edit','network error','err',0);}
});

/* ---- net config form: deterministic gen/check (safe DSL, no writes) ---- */
const netf=document.getElementById('netform');
document.getElementById('netToggle').addEventListener('click',()=>{
  netf.classList.toggle('open');document.getElementById('netToggle').classList.toggle('on',netf.classList.contains('open'));});
async function netCall(endpoint,lbl){
  const spec=document.getElementById('nfSpec').value;
  if(!spec.trim())return;
  try{
    const r=await (await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({content:spec})})).json();
    const res=r.result||{};
    addStat(lbl,''+(res.result!==undefined?res.result:res.reason||''),res.ok?'res':'err',0);
  }catch(err){addStat(lbl,'network error','err',0);}
}
document.getElementById('nfGen').addEventListener('click',()=>netCall('/net/gen','net.cfg_gen'));
document.getElementById('nfCheck').addEventListener('click',()=>netCall('/net/check','net.cfg_check'));

/* ---- gated lab apply card (dry-run diff -> Apply) ---- */
function pinLab(p,lbl){
  const w=document.createElement('div');w.className='entry edit';
  const top=document.createElement('div');top.className='mod-top';
  const t=document.createElement('div');t.className='lbl tool';
  t.textContent=(lbl||'\u25b8 net.lab_push')+' \u00b7 lab \u00b7 '+p.created;
  top.append(t);
  const body=document.createElement('div');body.className='mod-body';
  body.textContent=p.diff||'(no differences)';
  const btns=document.createElement('div');btns.className='mod-btns';
  const applyB=document.createElement('button');applyB.className='mod-apply';applyB.textContent='Apply to lab';
  applyB.onclick=async()=>{
    applyB.disabled=true;applyB.textContent='applying...';
    try{
      const r=await (await fetch('/lab/apply',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({id:p.id})})).json();
      const res=r.result||{};
      body.textContent=(res.applyed||res.applied)?('\u2713 '+res.note):('error: '+(res.note||res.reason||''));
      applyB.textContent=res.applied?'Applied':'Apply';applyB.disabled=!!res.applied;
    }catch(e){applyB.disabled=false;applyB.textContent='Apply';body.textContent='network error';}
  };
  btns.append(applyB);w.append(top,body,btns);log.appendChild(w);log.scrollTop=log.scrollHeight;
}
document.getElementById('nfPush').addEventListener('click',async()=>{
  const spec=document.getElementById('nfSpec').value;
  if(!spec.trim())return;
  try{
    const r=await (await fetch('/lab/push',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({content:spec})})).json();
    if(r.blocked){addStat('net.lab_push',''+(r.reason||''),'err',0);return;}
    const res=r.result||{};const pend=(r.pending)||(res.result&&res.result);
    if(pend&&pend.id)pinLab(pend,'\u25b8 net.lab_push');
    else addStat('net.lab_push',''+(res.result!==undefined?res.result:res.reason||''),res.ok?'res':'err',0);
  }catch(err){addStat('net.lab_push','network error','err',0);}
});
document.getElementById('nfState').addEventListener('click',()=>netCall('/lab/state','net.lab_state'));

/* ---- multi-node lab: build (gated) + state + link toggles + teardown ---- */
const labf=document.getElementById('labform'),labSpec=document.getElementById('labSpec'),
      lbNode=document.getElementById('lbNode'),labLinks=document.getElementById('labLinks');
document.getElementById('labToggle').addEventListener('click',()=>{
  labf.classList.toggle('open');document.getElementById('labToggle').classList.toggle('on',labf.classList.contains('open'));});
async function labCall(endpoint,body,lbl){
  try{
    const r=await (await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)})).json();
    return r;
  }catch(e){addStat(lbl,'network error','err',0);return null;}
}
function pinLabBuild(p,lbl){
  const w=document.createElement('div');w.className='entry edit';
  const top=document.createElement('div');top.className='mod-top';
  const t=document.createElement('div');t.className='lbl tool';
  t.textContent=(lbl||'\\u25b8 net.lab_topo')+' \\u00b7 '+p.summary;top.append(t);
  const body=document.createElement('div');body.className='mod-body';
  body.textContent=(p.nodes||[]).join(', ')+'\\n'+ (p.links||[]).join('\\n');
  const btns=document.createElement('div');btns.className='mod-btns';
  const b=document.createElement('button');b.className='mod-apply';b.textContent='Build on lab';
  b.onclick=async()=>{
    b.disabled=true;b.textContent='building (slow) ...';
    try{
      const r=await (await fetch('/lab/topo_apply',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({id:p.id})})).json();
      const res=r.result||{};
      body.textContent=(res.applied)?('\\u2713 '+res.note):('error: '+(res.note||res.reason||''));
      b.textContent=res.applied?'Built':'Build';b.disabled=!!res.applied;
    }catch(e){b.disabled=false;b.textContent='Build';body.textContent='network error';}
  };
  btns.append(b);w.append(top,body,btns);log.appendChild(w);log.scrollTop=log.scrollHeight;
}
function renderLabControls(p){
  lbNode.innerHTML='<option value="all">all nodes</option>';
  (p.nodes||[]).forEach(n=>{const o=document.createElement('option');o.value=n;o.textContent=n;lbNode.appendChild(o);});
  labLinks.innerHTML='';
  (p.links||[]).forEach(li=>{
    const row=document.createElement('div');row.className='ll';
    const id=document.createElement('span');id.className='llid';id.textContent=li;row.appendChild(id);
    const up=document.createElement('button');up.textContent='up';
    const dn=document.createElement('button');dn.className='dn';dn.textContent='down';
    const busy=async(btn,state)=>{btn.disabled=true;
      const r=await (await fetch('/lab/link',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({link:li,state})})).json();
      const res=r.result||{};
      addStat('net.lab_link \\u00b7 '+li,''+ (res.note||res.reason||''),res.ok?'res':'err',0);
      btn.disabled=false;};
    up.onclick=()=>busy(up,'up');dn.onclick=()=>busy(dn,'down');
    row.append(up,dn);labLinks.appendChild(row);
  });
}
function stageLab(showCard){
  const spec=labSpec.value;if(!spec.trim())return;
  labCall('/lab/topo',{content:spec},'net.lab_topo').then(r=>{
    if(!r)return;
    if(r.blocked){addStat('net.lab_topo',''+(r.reason||''),'err',0);return;}
    const res=r.result||{};const p=(res.result!==undefined?res.result:res.reason||'');
    if(p&&p.id){renderLabControls(p);if(showCard)pinLabBuild(p,'\\u25b8 net.lab_topo');}
    else addStat('net.lab_topo',''+ (res.result!==undefined?res.result:res.reason||''),res.ok?'res':'err',0);
  });
}
document.getElementById('lbBuild').addEventListener('click',()=>stageLab(true));
document.getElementById('lbState').addEventListener('click',async()=>{
  const node=lbNode.value||'all',spec=labSpec.value;
  const r=await labCall('/lab/state',{content:'all',node},'net.lab_state');
  if(!r)return;const res=r.result||{};
  addStat('net.lab_state \\u00b7 '+node,''+ (res.result!==undefined?res.result:res.reason||''),res.ok?'res':'err',0);
});
document.getElementById('lbDown').addEventListener('click',async()=>{
  const r=await labCall('/lab/down',{},'net.lab_down');
  if(!r)return;const res=r.result||{};
  addStat('net.lab_down',''+ (res.note||res.result||res.reason||''),res.ok?'res':'err',0);
});




/* ---- quick-command chips: one tap runs a gated command ---- */
document.querySelectorAll('.chip').forEach(ch=>{
  ch.addEventListener('click',()=>submit('/run',ch.getAttribute('data-q')));});

/* ---- clear log (and its persisted history) ---- */
document.getElementById('clearLog').addEventListener('click',()=>{
  log.innerHTML='';history=[];try{localStorage.removeItem(historyKey);}catch(e){}
  entry('log cleared','','stat');
});

/* ---- session restore: static history + re-pin live modules ---- */
let history=[];
try{history=JSON.parse(localStorage.getItem(historyKey)||'[]')||[];}catch(e){history=[];}
if(history.length){restoring=true;
  history.forEach(h=>entry(h.l,h.t,h.k,400));restoring=false;
  log.scrollTop=log.scrollHeight;
}
fetch('/mod').then(r=>r.json()).then(list=>{
  (list||[]).forEach(m=>pinModule(m,'\u25b8 module '+m.id));
}).catch(()=>{});
autogrow();
</script></body></html>"""


def route_and_exec(query):
    return pipeline.process(query)


# ---- WireGuard kill-switch (re-added 2026-08-22, lost with /tmp) ----
# sudoers: user NOPASSWD on /usr/bin/wg + /usr/bin/wg-quick (/etc/sudoers.d/wg-toolrx)
# GOTCHA (cost us a double-fire once): `wg show` exits 0 with EMPTY output when
# wg0 is down -> up must be detected by seeing "interface: wg0" in the text.
def _wg_status():
    try:
        r = subprocess.run(["sudo", "-n", "wg", "show"],
                           capture_output=True, text=True, timeout=6)
        txt = r.stdout
    except Exception:
        txt = ""
    up = "interface: wg0" in txt
    peers, cur = [], None
    for line in txt.splitlines():
        ls = line.strip()
        if ls.startswith("interface:"):
            cur = None
        elif ls.startswith("peer:"):
            if cur:
                peers.append(cur)
            pub = ls.split(":", 1)[1].strip()
            cur = {"peer": pub[:16] + "…", "endpoint": None,
                   "handshake": None, "rx": None, "tx": None}
        elif cur is not None:
            if ls.startswith("endpoint:"):
                cur["endpoint"] = ls.split(":", 1)[1].strip()
            elif ls.startswith("latest handshake:"):
                cur["handshake"] = ls.split(":", 1)[1].strip()
            elif ls.startswith("transfer:"):
                t = ls.split(":", 1)[1].strip()          # "X received, Y sent"
                try:
                    rx, tx = t.split(",")
                    cur["rx"] = rx.replace(" received", "").strip()
                    cur["tx"] = tx.replace(" sent", "").strip()
                except Exception:
                    pass
    if cur:
        peers.append(cur)
    return {"up": up, "peers": peers}


def _wg_toggle():
    st = _wg_status()
    action = "wg-quick down wg0" if st["up"] else "wg-quick up wg0"
    try:
        r = subprocess.run(["sudo", "-n", "wg-quick",
                            "down" if st["up"] else "up", "wg0"],
                           capture_output=True, text=True, timeout=15)
        ok = r.returncode == 0
        err = (r.stderr or "").strip().splitlines()[-1:] 
    except Exception as e:
        ok, err = False, [str(e)]
    new = _wg_status()
    new["toggled"] = action
    new["ok"] = ok and (new["up"] != st["up"])
    if not new["ok"]:
        new["error"] = err[0] if err else "toggle had no effect"
        new.update(st)  # report truth even if toggle failed
    return new


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") == "/models/local":
            try:
                self._respond(200, local_models())
            except Exception as e:  # noqa: BLE001
                self._respond(200, {"backends": [], "models": [],
                                    "error": str(e)})
            return
        if self.path.rstrip("/") == "/wg":
            self._respond(200, _wg_status())
            return
        if self.path.startswith("/cluster"):
            devs = _SNAPSHOT.get("cluster")
            if not devs:
                try:
                    devs = cluster_status()
                except Exception:
                    devs = []
            self._respond(200, {"devices": devs,
                                "time": _SNAPSHOT.get("time", time.strftime("%H:%M:%S"))})
            return
        if self.path.rstrip("/") == "/config":
            try:
                sandbox = security.SecurityPolicy.load().sandbox_root
            except Exception:
                sandbox = ""
            self._respond(200, {
                "training": bool(SHOW_TRAINING and TRAIN_SERIAL),
                "host": {"name": _device_name(HOST_SERIAL, HOST_NAME),
                         "hostname": platform.node() or HOST_NAME,
                         "platform": platform.platform(),
                         "cpu": _cpu_model(),
                         "abi": platform.machine() or "unknown"},
                "sandbox_root": sandbox,
            })
            return
        if self.path.rstrip("/") == "/train" or self.path.startswith("/train?"):
            if not (SHOW_TRAINING and TRAIN_SERIAL):
                self._respond(403, {"blocked": True,
                                    "reason": "training UI is disabled (set TOOLRX_SHOW_TRAINING=1 and TRAIN_SERIAL)"})
                return
            self._respond(200, _SNAPSHOT.get("train", {}))
            return
        if self.path.rstrip("/") == "/model" or self.path.startswith("/model?"):
            if not (SHOW_TRAINING and TRAIN_SERIAL):
                self._respond(403, {"blocked": True,
                                    "reason": "training UI is disabled (set TOOLRX_SHOW_TRAINING=1 and TRAIN_SERIAL)"})
                return
            self._respond(200, _model_status())
            return
        if self.path.startswith("/llm/status/"):
            tid = self.path[len("/llm/status/"):].split("?", 1)[0]
            with _TASKS_LOCK:
                info = _TASKS.get(tid, {"status": "unknown"})
            self._respond(200, info)
            return
        if self.path.startswith("/bot") or self.path == "/agent-face.html" or self.path.startswith("/orb"):
            import urllib.parse as _up
            serial = ""
            q = _up.parse_qs(_up.urlparse(self.path).query)
            if "serial" in q:
                serial = q["serial"][0]
            botfile = os.path.join(HERE, "orb.html")
            if os.path.exists(botfile):
                body = open(botfile).read().replace("__SERIAL__", serial)
            else:
                body = "<html><body style='background:#000;color:#22d3ee;font-family:monospace'>orb page missing</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode())
            return
        if self.path.split("?", 1)[0] in ("/", "/index.html"):
            body = _PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/preview/"):
            rel = self.path[len("/preview/"):].split("?", 1)[0]
            full = os.path.join(PREVIEW_DIR, rel)
            try:
                full = os.path.realpath(full)
                root = os.path.realpath(PREVIEW_DIR)
                if not full.startswith(root + os.sep) and full != root:
                    raise OSError
                data = open(full, "rb").read()
            except OSError:
                body = "<html><body style='background:#111;color:#6f9d7a;font-family:monospace'>no preview yet - ask the harness to build something</body></html>".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            ctype = "text/html; charset=utf-8" if full.endswith(".html") else \
                    "text/css; charset=utf-8" if full.endswith(".css") else \
                    "application/javascript; charset=utf-8" if full.endswith(".js") else \
                    "image/png" if full.endswith(".png") else "text/plain; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/mod":
            self._respond(200, list(modules.ENGINE.active().values()))
        elif self.path.startswith("/mod/"):
            mid = self.path[len("/mod/"):]
            info = modules.ENGINE.get(mid)
            self._respond(200 if info else 404,
                          info if info else {"error": "no such module"})
        else:
            body = b'{"error":"not found"}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n) or b"{}")
            query = payload.get("query", "")
        except Exception as e:  # noqa: BLE001
            self._respond(400, {"blocked": True, "reason": f"bad request: {e}"})
            return

        if self.path.rstrip("/") == "/wg/toggle":
            self._respond(200, _wg_toggle())
            return

        if self.path.startswith(("/train", "/model")) and not (SHOW_TRAINING and TRAIN_SERIAL):
            self._respond(403, {"blocked": True,
                                "reason": "training UI is disabled (set TOOLRX_SHOW_TRAINING=1 and TRAIN_SERIAL)"})
            return

        if self.path == "/plan":
            # reasoning trace only, NEVER executes
            out = planner.plan(query)
            log.info("plan q=%r -> %s", query,
                     "blocked" if out.get("blocked") else out.get("proposed_action", {}).get("tool"))
        elif self.path == "/train/start":
            version = str(payload.get("version", "")).strip() or None
            corpus = str(payload.get("corpus", "")).strip() or f"{SDCARD}/train_full_v2.jsonl"
            init = str(payload.get("init", "")).strip() or CHAMPION_INIT
            steps = int(payload.get("steps", 32) or 32)
            lr = str(payload.get("lr", "5e-5")).strip() or "5e-5"
            if not version:
                self._respond(400, {"blocked": True, "reason": "version required (e.g. v21)"})
                return
            err = _launch_training(version, corpus, init, steps, lr=lr)
            if err:
                self._respond(400, {"blocked": True, "reason": err})
                return
            self._respond(200, {"blocked": False, "ok": True,
                                "task": f"training {version} ({steps} steps) launched",
                                "state": _training_status()})
            return
        elif self.path == "/train/repeat":
            err, msg = _repeat_last_training()
            if err:
                self._respond(400, {"blocked": True, "reason": err})
                return
            self._respond(200, {"blocked": False, "ok": True,
                                "task": f"repeat launched: {msg}",
                                "state": _training_status()})
            return
        elif self.path == "/train/auto":
            action = str(payload.get("action", "start")).lower()
            if action == "stop":
                AUTO["on"] = False
                AUTO["phase"] = "stopping"
                try:
                    os.remove(TRAIN_FLAG)
                except Exception:
                    pass
                self._respond(200, {"blocked": False, "ok": True,
                                    "task": "auto-cycle stopping after current phase"})
                return
            msg = _start_auto_cycle()
            self._respond(200, {"blocked": False, "ok": True, "task": msg,
                                "state": _training_status()})
            return
        elif self.path == "/train/focus":
            # Build a class-balanced corpus emphasizing the weak gate classes.
            src = str(payload.get("src", "")).strip() or f"{SDCARD}/train_full_v2.jsonl"
            try:
                count = _build_focused_corpus(src)
            except Exception as e:  # noqa: BLE001
                self._respond(400, {"blocked": True, "reason": f"focus failed: {e}"})
                return
            self._respond(200, {"blocked": False, "ok": True,
                                "count": count, "corpus": f"{SDCARD}/train_focused.jsonl"})
            return
        elif self.path == "/train/verify":
            version = str(payload.get("version", "")).strip() or None
            if not version:
                self._respond(400, {"blocked": True, "reason": "version required (e.g. v20)"})
                return
            err, msg = _verify_run(version)
            if err:
                self._respond(400, {"blocked": True, "reason": err})
                return
            self._respond(200, {"blocked": False, "ok": True, "task": msg})
            return
        elif self.path == "/train/protect":
            version = str(payload.get("version", "")).strip() or None
            if not version or not re.match(r"^v[0-9]+$", version):
                self._respond(400, {"blocked": True, "reason": "version required (e.g. v11)"})
                return
            prot = bool(payload.get("protect"))
            with TRAIN_LOCK:
                s = _load_protected()
                if prot:
                    s.add(version)
                else:
                    s.discard(version)
                _save_protected(s)
            self._respond(200, {"blocked": False, "ok": True, "protected": sorted(s)})
            return
        elif self.path == "/train/delete":
            version = str(payload.get("version", "")).strip() or None
            if not version or not re.match(r"^v[0-9]+$", version):
                self._respond(400, {"blocked": True, "reason": "version required (e.g. v19)"})
                return
            if version in _load_protected():
                self._respond(400, {"blocked": True,
                                    "reason": f"{version} is protected — unprotect it first"})
                return
            vf = _verifies_status()
            if vf.get(version, {}).get("running"):
                self._respond(400, {"blocked": True,
                                    "reason": f"{version} gate is running — wait for it to finish"})
                return
            removed = []
            for pat in [f"{RUN_DIR}/gate_{version}.log",
                        f"{RUN_DIR}/gate_{version}_*.log",
                        f"{RUN_DIR}/syn_{version}.cact",
                        f"{NEEDLE_DIR}/adapters/syn_{version}_merged.cact"]:
                for f in glob.glob(pat):
                    try:
                        os.remove(f)
                        removed.append(os.path.basename(f))
                    except OSError:
                        pass
            with TRAIN_LOCK:
                TRAIN_STATE.get("history", {}).pop(version, None)
                TRAIN_STATE.get("last_gate", {}).pop(version, None)
            self._respond(200, {"blocked": False, "ok": True, "removed": removed,
                                "state": _training_status()})
            return
        elif self.path == "/cluster/rename":
            serial = str(payload.get("serial", "")).strip()
            newname = str(payload.get("name", "")).strip()[:40]
            if not serial:
                self._respond(400, {"blocked": True, "reason": "serial required"})
                return
            if not newname:
                self._respond(400, {"blocked": True, "reason": "name required"})
                return
            names = _load_names()
            names[serial] = newname
            with _NAME_LOCK:
                _save_names(names)
            self._respond(200, {"blocked": False, "ok": True, "name": newname})
            return
        elif self.path == "/cluster/start":
            # Bring all connected phones' backends online NOW (needles + executors)
            # instead of waiting for the watchdog's ~45s cycle. Kill stale
            # needle_model/llama-server first — a zombie bound to the port makes
            # the new spawn fail with "bind: Address already in use".
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location("stack_watchdog",
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "stack-watchdog.py"))
            _sw = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_sw)
            results = []
            for serial, name, port in _sw.NEEDLES:
                if not _sw.adb_alive(serial):
                    results.append(f"{name}:no-adb")
                    continue
                _sw.adb_shell(serial, "pkill -f needle_model 2>/dev/null")
                time.sleep(1)
                if _port_open(port):
                    results.append(f"{name}:up")
                    continue
                _sw.start_needle(serial, name, port)
                results.append(f"{name}:started")
            for serial, name, port in _sw.EXECUTORS:
                if not _sw.adb_alive(serial):
                    results.append(f"{name}:no-adb")
                    continue
                _sw.adb_shell(serial, "pkill -f llama-server 2>/dev/null")
                time.sleep(1)
                if _port_open(port):
                    results.append(f"{name}:up")
                    continue
                _sw.start_executor(serial, name, port)
                results.append(f"{name}:started")
            self._respond(200, {"blocked": False, "ok": True, "results": results})
            return
        elif self.path == "/cmd/provider":
            provider = str(payload.get("provider", "")).strip()
            key = str(payload.get("key", "")).strip()
            model = str(payload.get("model", "")).strip()
            if not provider or not key:
                self._respond(400, {"blocked": True, "reason": "provider + key required"})
                return
            cfg = {}
            try:
                with open(os.path.join(TRAIN_DIR, "cmd_providers.json")) as fh:
                    cfg = json.load(fh)
            except Exception:
                pass
            cfg[provider] = {"key": key, "model": model}
            with open(os.path.join(TRAIN_DIR, "cmd_providers.json"), "w") as fh:
                json.dump(cfg, fh, indent=2)
            log.info("cmd/provider saved for %s", provider)
            self._respond(200, {"blocked": False, "ok": True,
                                "provider": provider, "model": model})
            return
        elif self.path == "/cmd/github":
            repo = str(payload.get("repo", "")).strip()
            branch = str(payload.get("branch", "main")).strip()
            if not repo or "/" not in repo:
                self._respond(400, {"blocked": True, "reason": "repo must be owner/repo"})
                return
            # store the repo/branch preference; token would come via GH_TOKEN env or
            # a future git-credential flow. For now persist the target and verify
            # the host has `gh` or git available.
            cfg = {}
            try:
                with open(os.path.join(TRAIN_DIR, "cmd_github.json")) as fh:
                    cfg = json.load(fh)
            except Exception:
                pass
            cfg.update({"repo": repo, "branch": branch})
            with open(os.path.join(TRAIN_DIR, "cmd_github.json"), "w") as fh:
                json.dump(cfg, fh, indent=2)
            has_gh = subprocess.run(["which", "gh"], capture_output=True, text=True).returncode == 0
            log.info("cmd/github target=%s branch=%s gh=%s", repo, branch, has_gh)
            self._respond(200, {"blocked": False, "ok": True, "repo": repo,
                                "gh_cli": has_gh})
            return
        elif self.path == "/edit/prepare":
            # structured file-edit form (line breaks preserved) -> dry-run only
            pol = security.SecurityPolicy.load()
            try:
                info = edits.prepare(pol, payload.get("path"), payload.get("content") or "", "replace")
            except Exception as e:  # noqa: BLE001
                self._respond(200, {"blocked": True, "reason": f"edit: {e}"})
                return
            self._respond(200, {"blocked": False, "decision": {"tool": "file.edit", "query": query},
                                "result": {"ok": True, "result": info}})
            return
        elif self.path == "/apply":
            try:
                res = edits.apply(payload.get("id"))
            except Exception as e:  # noqa: BLE001
                self._respond(400, {"blocked": True, "reason": f"apply: {e}"})
                return
            log.info("APPLIED %s", res.get("path"))
            self._respond(200, res)
            return
        elif self.path == "/undo":
            try:
                res = edits.undo(payload.get("id"))
            except Exception as e:  # noqa: BLE001
                self._respond(400, {"blocked": True, "reason": f"undo: {e}"})
                return
            log.info("UNDID %s", res.get("path"))
            self._respond(200, res)
            return
        elif self.path in ("/net/gen", "/net/check"):
            # deterministic, pure-text network config gen/validate (no writes)
            content = payload.get("content") or ""
            tool = "net.cfg_gen" if self.path == "/net/gen" else "net.cfg_check"
            try:
                out = pipeline.process_for_tool(tool, {"content": content})
            except Exception as e:  # noqa: BLE001
                self._respond(400, {"blocked": True, "reason": f"net: {e}"})
                return
            self._respond(200, out)
            return
        elif self.path in ("/lab/state", "/lab/push"):
            # read-only lab ops: live state query, or dry-run build+diff
            tool = "net.lab_state" if self.path == "/lab/state" else "net.lab_push"
            args = {"content": payload.get("content") or "",
                    "what": payload.get("what") or "all",
                    "node": payload.get("node") or ""}
            try:
                out = pipeline.process_for_tool(tool, args)
            except Exception as e:  # noqa: BLE001
                self._respond(400, {"blocked": True, "reason": f"lab: {e}"})
                return
            self._respond(200, out)
            return
        elif self.path == "/lab/topo":
            # stage a multi-node topology: parse + validate, no build (dry-run)
            args = {"content": payload.get("content") or ""}
            try:
                out = pipeline.process_for_tool("net.lab_topo", args)
            except Exception as e:  # noqa: BLE001
                self._respond(400, {"blocked": True, "reason": f"lab topo: {e}"})
                return
            self._respond(200, out)
            return
        elif self.path == "/lab/topo_apply":
            # gated mutation: build the staged multi-node lab on the lab host
            pid = payload.get("id") or payload.get("pending")
            try:
                out = pipeline.process_for_tool("net.lab_topo_apply", {"id": pid})
            except Exception as e:  # noqa: BLE001
                self._respond(400, {"blocked": True, "reason": f"lab build: {e}"})
                return
            self._respond(200, out)
            return
        elif self.path == "/lab/link":
            # gated mutation: bring a lab link up/down (failover testing)
            args = {"link": payload.get("link") or payload.get("id"),
                    "state": payload.get("state") or ""}
            try:
                out = pipeline.process_for_tool("net.lab_link", args)
            except Exception as e:  # noqa: BLE001
                self._respond(400, {"blocked": True, "reason": f"lab link: {e}"})
                return
            self._respond(200, out)
            return
        elif self.path == "/lab/down":
            # gated mutation: tear down the multi-node lab
            try:
                out = pipeline.process_for_tool("net.lab_down", {})
            except Exception as e:  # noqa: BLE001
                self._respond(400, {"blocked": True, "reason": f"lab down: {e}"})
                return
            self._respond(200, out)
            return
        elif self.path == "/lab/apply":
            # gated mutation: install a staged (pushed) config and reload FRR
            pid = payload.get("id") or payload.get("pending")
            try:
                out = pipeline.process_for_tool("net.lab_apply", {"pending": pid})
            except Exception as e:  # noqa: BLE001
                self._respond(400, {"blocked": True, "reason": f"lab apply: {e}"})
                return
            self._respond(200, out)
            return
        elif self.path.startswith("/mod/"):
            mid = self.path[len("/mod/"):]
            if mid.endswith("/stop"):
                mid = mid[: -len("/stop")]
            stopped = modules.ENGINE.stop(mid)
            self._respond(200, {"stopped": mid} if stopped else {"error": "no such module"})
            return
        elif self.path in ("/run", "/call"):
            # manual, gated execution; supports multiple commands, one per line
            out = self._run(query)
        elif self.path == "/llm/cancel":
            tid = str(payload.get("tid", "")).strip()
            if not tid:
                self._respond(400, {"blocked": True, "reason": "tid required"})
                return
            with _CANCELLED_LOCK:
                _CANCELLED.add(tid)
            with _TASKS_LOCK:
                if tid in _TASKS:
                    _TASKS[tid]["status"] = "cancelled"
                    _save_task(tid)
            self._respond(200, {"blocked": False, "ok": True, "cancelled": tid})
            return
        elif self.path == "/llm":
            # spawn async so the browser connection never blocks on slow builds
            try:
                tid = _spawn_llm_task(query)
                self._respond(200, {"blocked": False, "async": True, "task": tid,
                                    "decision": {"tool": "local.llm", "query": query}})
            except Exception as e:  # noqa: BLE001
                self._respond(502, {"blocked": True, "reason": f"llm: {e}"})
                return
        else:
            self._respond(404, {"blocked": True, "reason": "not found"})
            return
        self._respond(200, out)

    def _run(self, query):
        """Run one command, or each line if the prompt holds several."""
        lines = [ln.strip() for ln in query.splitlines()]
        lines = [ln for ln in lines if ln]
        if len(lines) <= 1:
            out = pipeline.process(query)
            out = self._attach_module(out)
            decision, result = out.get("decision") or {}, out.get("result") or {}
            if out.get("blocked"):
                log.warning("BLOCK q=%r  reason=%s", query, out.get("reason"))
            else:
                log.info("run  q=%r  tool=%s  conf=%s  ok=%s  out=%s",
                         query, decision.get("tool", "?"), decision.get("confidence"),
                         result.get("ok"),
                         str(result.get("result", result.get("reason", "-")))[:80])
            return out
        results = []
        for q in lines:
            o = pipeline.process(q)
            o = self._attach_module(o)
            results.append({
                "query": q,
                "blocked": o.get("blocked"),
                "reason": o.get("reason"),
                "decision": o.get("decision"),
                "result": o.get("result"),
                "module": o.get("module"),
            })
        return {"multi": True, "blocked": any(r["blocked"] for r in results),
                "results": results}

    def _llm(self, query, payload):
        """Proxy a prompt to the swarm router (live needle C++ backends)."""
        import urllib.request
        max_new = int(payload.get("max_new", 64))
        body = json.dumps({"query": query, "max_new": max_new}).encode()
        req = urllib.request.Request(os.environ.get("LLM_URL", "http://127.0.0.1:8900/"),
                                     data=json.dumps({"query": query}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read())
        log.info("llm q=%r -> %r", query, str(data.get("response"))[:60])
        calls = data.get("calls") or []
        if calls:
            detail = "; ".join(f"{c.get('name')}({c.get('arguments')})" for c in calls)
            obs = data.get("observations") or []
            if obs:
                detail += " -> " + str(obs[0].get("result", ""))[:120]
        else:
            detail = data.get("response") or data.get("note") or ""
        text = detail or str(data.get("response") or "")[:120]
        return {"blocked": False, "decision": {"tool": "local.llm", "query": query},
                "result": {"ok": True, "result": {"text": text,
                                                  "seconds": data.get("seconds"),
                                                  "raw": data}}}

    @staticmethod
    def _attach_module(out):
        """If a module tool ran, attach the live module info for the UI."""
        if out.get("blocked"):
            return out
        dec = out.get("decision") or {}
        tool = dec.get("tool")
        if tool in ("module.stop", "module.clear"):
            res = (out.get("result") or {}).get("result") or {}
            if isinstance(res, dict):
                out["removed"] = res.get("ids", [])
                out["note"] = res.get("note", "")
            return out
        if tool == "file.edit":
            res = (out.get("result") or {}).get("result") or {}
            if isinstance(res, dict):
                out["pending"] = res
            return out
        if tool in ("net.lab_push", "net.lab_topo"):
            res = (out.get("result") or {}).get("result") or {}
            if isinstance(res, dict) and res.get("id"):
                out["pending"] = res
            return out
        if tool not in ("module.start", "module.run"):
            return out
        mid = str(out.get("result", {}).get("result", "") if isinstance(
            out.get("result"), dict) else out.get("result"))
        info = modules.ENGINE.get(mid)
        if info:
            out["module"] = info
        return out

    def _respond(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # access log goes to our file logger instead
        log.debug("http %s %s", self.command, self.path)


def main():
    global _PAGE
    # serve the modern dashboard if present, else the embedded legacy page
    _dash = os.path.join(HERE, "dashboard.html")
    if os.path.exists(_dash):
        with open(_dash) as fh:
            _PAGE = fh.read()
    _load_tasks()
    os.makedirs(RUN_DIR, exist_ok=True)
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    threading.Thread(target=_adb_state_loop, daemon=True).start()
    threading.Thread(target=_snapshot_loop, daemon=True).start()
    if SHOW_TRAINING and TRAIN_SERIAL:
        threading.Thread(target=_gate_reaper_loop, daemon=True).start()
    build = "--rebuild" in sys.argv
    if build:
        builder_mod.build(os.path.join(HERE, "catalog.json"))
        security.build_vocab(os.path.join(HERE, "catalog.json"))
        pipeline.reload()
    port = int(os.environ.get("PORT", "8080"))
    bind = _env("TOOLRX_BIND", "127.0.0.1")
    srv = ThreadingHTTPServer((bind, port), Handler)
    print(f"toolrx running at http://{bind}:{port}/  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
"""Modules: live-pinned, interval-driven widgets (client-pull transport).

A module is a vetted, read-only polling handler. The server runs a background
thread that calls each active module's ``tick()`` every ``interval`` seconds and
caches the latest state. The browser fetches that state on its own interval and
re-renders a pinned card in place.

Security posture (same default-deny as the router):
  * Only handlers in MONITORS (or tools wired through a run fn by the caller)
    may ever run; a chat prompt can never inject code.
  * Interval is clamped to [MIN_INTERVAL, MAX_INTERVAL].
  * Concurrency is bounded by MAX_MODULES.
"""

import threading
import time

import os_tools


MIN_INTERVAL, MAX_INTERVAL = 2, 3600
MAX_MODULES = 8


class ModuleBase:
    """Base for a monitor module. Override tick() -> dict (pure, read-only)."""
    name = "module"

    def tick(self):
        raise NotImplementedError

    def describe(self):
        return {"name": self.name}


class MemoryModule(ModuleBase):
    name = "memory"

    def tick(self):
        vals = {}
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if ":" in line:
                        k, rest = line.split(":", 1)
                        vals[k.strip()] = rest.strip()
        except OSError as e:
            return {"error": str(e)}
        kb = lambda s: int(s.split()[0]) if s else 0
        total = kb(vals.get("MemTotal"))
        free = kb(vals.get("MemFree"))
        avail = kb(vals.get("MemAvailable"))
        return {
            "total_kb": total,
            "free_kb": free,
            "used_kb": total - free,
            "avail_kb": avail or total - free,
            "used_pct": round(100 * (1 - (free / total if total else 0)), 1),
        }


class DiskModule(ModuleBase):
    name = "disk"

    def tick(self):
        try:
            import os
            s = os.statvfs("/")
            total = s.f_blocks * s.f_frsize
            free = s.f_bavail * s.f_frsize
            used = total - s.f_bfree * s.f_frsize
            return {
                "total": total,
                "used": used,
                "free": free,
                "used_pct": round(100 * used / total, 1) if total else 0,
            }
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}


class UptimeModule(ModuleBase):
    name = "uptime"

    def tick(self):
        # /proc/uptime is EACCES on Android; use the `uptime` command (as the
        # sys.uptime tool does) instead.
        try:
            return os_tools.safe_run(os_tools._MONITOR["uptime"], [])
        except Exception as e:  # noqa: BLE001
            return {"error": repr(e)}


class RunModule(ModuleBase):
    """Generic interval-runner: executes a wired callable each tick."""

    def __init__(self, fn, name="run"):
        self._fn = fn
        self.name = name

    def tick(self):
        try:
            return self._fn()
        except Exception as e:  # noqa: BLE001
            return {"error": repr(e)}

    def describe(self):
        return {"name": self.name}


class ModuleEngine:
    def __init__(self):
        self._mods = {}
        self._lock = threading.RLock()
        self._seq = [0]
        self._thread = None
        self._stop = False

    def _next_id(self, name):
        self._seq[0] += 1
        return f"{name.split('.')[-1][:3]}{self._seq[0]}"

    def start(self, name, interval, duration=0, fn=None):
        interval = int(max(MIN_INTERVAL, min(MAX_INTERVAL, float(interval))))
        duration = int(duration or 0)
        with self._lock:
            if len(self._mods) >= MAX_MODULES:
                raise ValueError(f"module limit reached ({MAX_MODULES})")
            if fn is None:
                obj = _BUILTINS.get(name)
                if obj is None:
                    raise ValueError(f"unknown module: {name}")
                obj = obj()
            else:
                obj = RunModule(fn, name=name)
            mid = self._next_id(obj.name)
            rec = {"obj": obj, "interval": interval, "last": None, "next": time.time(),
                   "stop_at": time.time() + duration if duration else 0}
            self._mods[mid] = rec
        self._ensure_thread()
        return mid

    def stop(self, mid):
        with self._lock:
            rec = self._mods.pop(mid, None)
        return bool(rec)

    def clear(self):
        with self._lock:
            removed = list(self._mods.keys())
            self._mods.clear()
        return removed

    def get(self, mid):
        with self._lock:
            rec = self._mods.get(mid)
            if not rec:
                return None
            return {
                "id": mid,
                "name": rec["obj"].name,
                "interval": rec["interval"],
                "state": rec["last"],
                "updated": rec.get("_t"),
                "remaining": max(0, int(rec["stop_at"] - time.time())) if rec.get("stop_at") else 0,
            }

    def active(self):
        with self._lock:
            return {mid: self.get(mid) for mid in list(self._mods)}

    def _ensure_thread(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop:
            now = time.time()
            for mid in list(self._mods):
                with self._lock:
                    rec = self._mods.get(mid)
                    if not rec:
                        continue
                    if rec.get("stop_at") and now >= rec["stop_at"]:
                        self._mods.pop(mid, None)  # auto-stop: duration elapsed
                        continue
                    if now < rec["next"]:
                        continue
                    obj = rec["obj"]
                    rec["interval"] = int(rec.get("interval", 5))
                try:
                    state = obj.tick()
                except Exception as e:  # noqa: BLE001
                    state = {"error": repr(e)}
                with self._lock:
                    rec2 = self._mods.get(mid)
                    if rec2:
                        rec2["last"] = state
                        rec2["_t"] = time.time()
                        rec2["next"] = time.time() + rec2["interval"]
            time.sleep(0.5)


_BASE_INTERVAL = 5
_BUILTINS = {
    "memory": MemoryModule,
    "disk": DiskModule,
    "uptime": UptimeModule,
}

ENGINE = ModuleEngine()

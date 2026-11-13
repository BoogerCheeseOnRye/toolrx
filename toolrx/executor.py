"""Executor: turns a routed decision into an actual call.

Two kinds of tools:
  * "native" — a real shared library (.so / .dll) loaded with ctypes.
    This is the "DLL as the tool" part of the experiment.
  * "python" — a small handler backed by an everyday system file
    (e.g. /proc/meminfo) or ordinary filesystem operations.
"""

import ctypes
import json
import os

import security
import envelope
import os_tools
import modules
import edits
import netcfg
import netlab

# Only these tools may ever execute. Anything else is refused (default-deny).
_ALLOWED_TOOLS = {
    "math.sum", "fs.read_file", "fs.list_dir", "fs.cat_all",
    "sys.mem_status", "net.ping", "sys.ifconfig", "sys.netstat",
    "sys.processes", "sys.disk", "sys.uptime", "config.diff", "fs.inspect_dir",
    "module.start", "module.run", "module.stop",
    "module.clear",
    "file.edit",
    "net.cfg_gen", "net.cfg_check",
    "net.lab_state", "net.lab_push", "net.lab_apply",
    "net.lab_topo", "net.lab_topo_apply", "net.lab_link", "net.lab_down",
}

_CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog.json")
try:
    with open(_CATALOG_PATH, encoding="utf-8") as _f:
        TOOLS = json.load(_f)["tools"]
except Exception:  # noqa: BLE001
    TOOLS = []
_MAX_TERMS, _TERM_BOUND = 100, 1_000_000

# --- python-implemented "/everyday file" tools ---------------------------
def do_read_file(args, pol):
    path = args.get("path", ".") or "."
    target = pol.safe_path(path)  # raises SecurityError if outside sandbox
    if os.path.isdir(target):  # degrade gracefully: report a directory listing
        return "\n".join(
            (e + "/" if os.path.isdir(os.path.join(target, e)) else e)
            for e in sorted(os.listdir(target))
        )
    with open(target, encoding="utf-8") as f:
        return f.read()


def do_list_dir(args, pol):
    path = args.get("path", ".") or "."
    target = pol.safe_path(path)
    return "\n".join(
        (e + "/" if os.path.isdir(os.path.join(target, e)) else e)
        for e in sorted(os.listdir(target))
    )


def do_cat_all(args, pol):
    """Dump the text contents of every text file inside the sandbox."""
    root = pol.sandbox_root
    _MAX_FILE = int(envelope.get("readFileBytes"))
    _MAX_TOTAL = int(envelope.get("readTotalBytes"))
    _SKIP = {"__pycache__", ".git", ".gitignore"}
    blocks, total = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP]
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext and ext not in pol.allowed_extensions:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            if any(s in rel for s in pol.denied_path_substrings):
                continue
            try:
                with open(full, "rb") as f:
                    if b"\x00" in f.read(2048):  # skip binary
                        continue
            except OSError:
                continue
            try:
                with open(full, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError as e:
                text = f"<error reading: {e}>"
            if len(text) > _MAX_FILE:
                text = text[:_MAX_FILE] + "\n...[truncated]"
            block = f"===== {rel} =====\n{text}"
            blocks.append(block)
            total += len(block)
            if total > _MAX_TOTAL:
                blocks.append(f"\n...[output truncated at {total} chars]")
                break
    return "\n\n".join(blocks) if blocks else "no text files found in sandbox"


def do_mem_status(args, pol):
    vals = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if ":" in line:
                    k, rest = line.split(":", 1)
                    vals[k.strip()] = rest.strip()
    except OSError as e:
        return f"meminfo unavailable: {e}"
    kb = lambda s: int(s.split()[0])
    mem_total, mem_free = kb(vals.get("MemTotal", "0")), kb(vals.get("MemFree", "0"))
    return (f"total={mem_total} KiB, free={mem_free} KiB, "
            f"used={mem_total - mem_free} KiB, {vals.get('MemAvailable', '')}")


def do_module_start(args, pol):
    name = args.get("name") or "memory"
    interval = args.get("interval", 5)
    duration = args.get("duration", 0)
    mid = modules.ENGINE.start(name, interval, duration=duration)
    return mid


def do_module_run(args, pol):
    tool = args.get("tool") or "sys.disk"
    if tool not in _ALLOWED_TOOLS:
        raise ValueError(f"tool not allowed to run as a module: {tool}")
    interval = args.get("interval", 5)
    duration = args.get("duration", 0)
    rest = {k: v for k, v in args.items() if k not in ("tool", "interval", "duration")}

    def tickfn():
        out = execute({"tool": tool, "args": rest}, TOOLS, pol)
        return out.get("result") if out.get("ok") else {"error": out.get("reason")}

    return modules.ENGINE.start(tool, interval, duration=duration, fn=tickfn)


def do_module_stop(args, pol):
    mid = args.get("id") or args.get("mid")
    if mid and mid.lower() in ("all", "all modules"):
        ids = modules.ENGINE.clear()
        return {"note": f"stopped all ({len(ids)}) modules", "ids": ids}
    removed = modules.ENGINE.stop(mid)
    return {"note": ("stopped " + mid) if removed else "no such module",
            "ids": [mid] if removed else []}


def do_module_clear(args, pol):
    ids = modules.ENGINE.clear()
    return {"note": f"stopped all ({len(ids)}) modules", "ids": ids}


def do_file_edit(args, pol):
    """Dry-run only: prepare a pending edit; NEVER writes here."""
    path = args.get("path")
    content = args.get("content") or ""
    mode = args.get("mode") or "replace"
    info = edits.prepare(pol, path, content, mode=mode)
    if info is None:
        return {"note": f"{path}: no change (identical content)", "id": None}
    return {"id": info["id"], "path": info["path"], "exists": info["exists"],
            "mode": info["mode"], "diff": info["diff"],
            "old_len": info["old_len"], "new_len": info["new_len"]}


_PY_FUNCS = {
    "do_read_file": do_read_file,
    "do_list_dir": do_list_dir,
    "do_cat_all": do_cat_all,
    "do_mem_status": do_mem_status,
    "do_module_start": do_module_start,
    "do_module_run": do_module_run,
    "do_module_stop": do_module_stop,
    "do_module_clear": do_module_clear,
    "do_file_edit": do_file_edit,
}
# extend with the strict read-only OS monitor + dry-run diff tools
_PY_FUNCS.update(os_tools._OS_TOOLS)
# extend with the deterministic network-config gen/validate tools
_PY_FUNCS["do_cfg_gen"] = netcfg.do_cfg_gen
_PY_FUNCS["do_cfg_check"] = netcfg.do_cfg_check
_PY_FUNCS["do_lab_state"] = netlab.do_lab_state
_PY_FUNCS["do_lab_push"] = netlab.do_lab_push
_PY_FUNCS["do_lab_apply"] = netlab.do_lab_apply
_PY_FUNCS["do_lab_topo"] = netlab.do_lab_topo
_PY_FUNCS["do_lab_topo_apply"] = netlab.do_lab_topo_apply
_PY_FUNCS["do_lab_link"] = netlab.do_lab_link
_PY_FUNCS["do_lab_down"] = netlab.do_lab_down

# --- native (.so/.dll) tools ---------------------------------------------
def call_native(spec, args):
    """spec: {"lib","fn","signature"} ; signature list of ctypes aliases."""
    terms = args.get("terms") or []
    if not isinstance(terms, list) or not terms:
        raise ValueError("terms: expected a non-empty int list")
    if len(terms) > _MAX_TERMS:
        raise ValueError(f"terms: too many ({len(terms)} > {_MAX_TERMS})")
    for t in terms:
        if not isinstance(t, int) or isinstance(t, bool) or abs(t) > _TERM_BOUND:
            raise ValueError(f"term out of range or wrong type: {t!r}")
    lib = ctypes.CDLL(spec["lib"])
    fn = getattr(lib, spec["fn"])
    sig = spec["signature"]

    if sig == ["array", "c_int", "c_int"]:
        # int[] sum_ints(int* arr, int n, int mode)
        arr = (ctypes.c_int * len(terms))(*terms)
        fn.restype = ctypes.c_int
        fn.argtypes = [
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
            ctypes.c_int,
        ]
        return fn(arr, len(terms), 0)
    raise NotImplementedError(f"no native binding for {spec}")


def execute(decision, tools, pol=None):
    pol = pol or security.SecurityPolicy.load()
    impl = next(
        (t["impl"] for t in tools if t["name"] == decision["tool"]), None
    )
    if impl is None:
        return {"ok": False, "reason": "tool not in catalog"}
    if decision["tool"] not in _ALLOWED_TOOLS:
        return {"ok": False, "reason": f"tool not allowed: {decision['tool']}"}
    kind = impl["type"]
    try:
        if kind == "python":
            result = _PY_FUNCS[impl["func"]](decision["args"], pol)
        elif kind == "native":
            result = call_native(impl, decision["args"])
        else:
            return {"ok": False, "reason": f"unknown impl type {kind}"}
        return {"ok": True, "tool": decision["tool"], "result": result}
    except security.SecurityError as e:
        return {"ok": False, "tool": decision["tool"], "blocked": True,
                "reason": f"security: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "tool": decision["tool"], "reason": repr(e)}
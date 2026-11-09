"""Strict, read-only OS monitor tools + dry-run config diff.

Safety rules enforced here (in addition to the input SecurityPolicy):
  * NO autonomous action. Every tool is read-only; the only "config" tool
    produces a diff and NEVER writes to disk.
  * subprocess.run is always invoked with shell=False and a fixed,
    operator-defined argv template. The user never supplies a command or
    command path, and no string is ever passed through a shell, so
    command/argument injection is structurally impossible.
  * Target hosts must be on the operator allowlist (pol.allowed_hosts).
  * Every call is subject to a short timeout (fail-closed on hang).
"""

import difflib
import os
import subprocess

import security


class OsToolError(Exception):
    pass


# Fixed, operator-defined monitor commands (READ-ONLY). The command word and
# all fixed flags are hardcoded here; user input only supplies validated
# arguments appended as literal argv entries.
_MONITOR = {
    "ping": ["ping", "-c", "4", "-W", "3"],
    "ifconfig": ["ip", "addr", "show"],
    "netstat": ["ss", "-tulpn"],
    "ps": ["ps", "aux"],
    "df": ["df", "-h"],
    "uptime": ["uptime"],
}

_TIMEOUT = 15


def safe_run(template, extra_args):
    """Run a fixed monitor command with literal extra args, no shell."""
    cmd = list(template) + [str(a) for a in extra_args]
    try:
        proc = subprocess.run(
            cmd, shell=False, capture_output=True, text=True, timeout=_TIMEOUT
        )
    except FileNotFoundError as e:
        raise OsToolError(f"command not available on this system: {cmd[0]}")
    except subprocess.TimeoutExpired:
        raise OsToolError(f"{cmd[0]} timed out after {_TIMEOUT}s")
    out, err, rc = proc.stdout, proc.stderr, proc.returncode
    if rc != 0 and not out.strip():
        raise OsToolError((err or "").strip() or f"exit code {rc}")
    return (out or err).strip() or f"(exit {rc})"


def safe_host(pol, host):
    host = (host or "").strip()
    if not host or host not in pol.allowed_hosts:
        raise security.SecurityError(f"host not allowed: {host!r}")
    return host


def do_ping(args, pol):
    host = args.get("host") or "localhost"  # default to loopback (on allowlist)
    host = safe_host(pol, host)
    return safe_run(_MONITOR["ping"], [host])


def do_ifconfig(args, pol):
    try:
        return safe_run(_MONITOR["ifconfig"], [])
    except OsToolError:
        return _proc_net_dev()


def do_netstat(args, pol):
    try:
        return safe_run(_MONITOR["netstat"], [])
    except OsToolError:
        return _proc_net_tcp()


def _proc_net_dev():
    """Fallback interface listing from /proc/net/dev (works without `ip`)."""
    try:
        lines = ["interfaces (from /proc/net/dev):", "name rx_bytes tx_bytes state"]
        with open("/proc/net/dev") as f:
            for line in f:
                if ":" not in line:
                    continue
                name, rest = line.split(":", 1)
                parts = rest.split()
                lines.append(f"{name.strip():<8} {parts[0]:>10} {parts[8]:>10} up")
        return "\n".join(lines)
    except OSError:
        raise OsToolError("no interface tool or /proc/net/dev available")


def _proc_net_tcp():
    """Fallback socket listing from /proc/net/tcp (works without `ss`)."""
    try:
        lines = ["listening (from /proc/net/tcp):", "local_address state"]
        with open("/proc/net/tcp") as f:
            next(f, None)
            for line in f:
                parts = line.split()
                if len(parts) < 4:
                    continue
                local, state = parts[1], parts[3]
                if state == "0A":  # LISTEN
                    lines.append(f"{local} LISTEN")
        return "\n".join(lines)
    except OSError:
        raise OsToolError("no socket tool or /proc/net/tcp available")


def do_ps(args, pol):
    return safe_run(_MONITOR["ps"], [])


def do_disk(args, pol):
    return safe_run(_MONITOR["df"], [])


def do_uptime(args, pol):
    return safe_run(_MONITOR["uptime"], [])


def do_config_diff(args, pol):
    """Dry-run only: diff two operator-validated paths. NEVER writes."""
    a = pol.safe_path(args.get("path_a"))
    b = pol.safe_path(args.get("path_b"))
    text_a = open(a, encoding="utf-8").read() if os.path.exists(a) else ""
    text_b = open(b, encoding="utf-8").read() if os.path.exists(b) else ""
    diff = list(difflib.unified_diff(
        text_a.splitlines(), text_b.splitlines(),
        fromfile=os.path.basename(a), tofile=os.path.basename(b), lineterm=""))
    return "\n".join(diff) or "(no differences)"


def do_inspect_dir(args, pol):
    """Read-only composite: list a directory AND dump one file's contents."""
    path = pol.safe_path(args.get("path") or ".")
    listing = "\n".join(
        (e + "/" if os.path.isdir(os.path.join(path, e)) else e)
        for e in sorted(os.listdir(path)))
    fname = (args.get("file") or "").strip()
    if fname:
        ext = os.path.splitext(fname)[1].lower()
        if ext and ext not in pol.allowed_extensions:
            return (f"listing of {path}:\n{listing}\n\n"
                    f"(skipped reading {fname}: extension not allowed)")
        try:
            target = pol.safe_path(os.path.join(args.get("path") or ".", fname))
            text = open(target, encoding="utf-8").read()
        except (security.SecurityError, OSError) as e:
            return (f"listing of {path}:\n{listing}\n\n"
                    f"(could not read {fname}: {e})")
        return (f"listing of {path}:\n{listing}\n\n"
                f"--- contents of {fname} ---\n{text}")
    return f"listing of {path}:\n{listing}"


_OS_TOOLS = {
    "do_ping": do_ping,
    "do_ifconfig": do_ifconfig,
    "do_netstat": do_netstat,
    "do_ps": do_ps,
    "do_disk": do_disk,
    "do_uptime": do_uptime,
    "do_config_diff": do_config_diff,
    "do_inspect_dir": do_inspect_dir,
}
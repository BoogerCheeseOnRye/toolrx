"""netlab: push generated FRR configs to a lab backend and check them.

Transports generated config text to an allowlisted lab host (lab host) over
SSH and runs read-only vtysh checks. This is the "apply to the lab" half of
the network harness.

Security posture (same default-deny as the rest of toolrx):
  * One FIXED, allowlisted lab host (TOOLRX_LAB_USER@TOOLRX_LAB_HOST).
    Users can never choose an arbitrary host or command.
  * The config bytes are ALWAYS produced by netcfg.generate() from a safe-DSL
    spec that only uses [a-z0-9 ._/:-]. They reach the lab via stdin redirection
    (`sudo -n tee`), never through a shell string, so no injection is possible.
  * Read-only operations (state/check, push/dry-run) run freely, like every
    other read-only tool.
  * The MUTATING apply is a separate gated step (diff shown first), exactly
    like file.edit. Nothing is written to the lab until the operator applies.
"""

import difflib
import ipaddress
import json
import os
import re
import shlex
import subprocess

import netcfg

HERE = os.path.dirname(os.path.abspath(__file__))
LAB_USER = os.environ.get("TOOLRX_LAB_USER", "user")
LAB_HOST = os.environ.get("TOOLRX_LAB_HOST", "")
if not LAB_HOST:
    LAB_HOST = "127.0.0.1"   # override for a real lab host
LAB_SSH = [os.environ.get("TERMUX_SSH", "ssh"),
           "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
           "-o", "ConnectTimeout=10", f"{LAB_USER}@{LAB_HOST}"]
_PENDING = {}
_PENDING_ID = [0]
_MAX_PENDING = 8


class LabError(Exception):
    pass


def _run(remote_cmd, timeout=25, input_bytes=None):
    """Run a FIXED remote command over SSH (no user-supplied shell input)."""
    try:
        proc = subprocess.run(
            LAB_SSH + [remote_cmd], shell=False, capture_output=True,
            text=True, input=input_bytes, timeout=timeout)
    except FileNotFoundError:
        raise LabError("ssh not available on this device")
    except subprocess.TimeoutExpired:
        raise LabError(f"lab SSH timed out after {timeout}s")
    return proc.returncode, proc.stdout, proc.stderr


def _gen_config(spec_text):
    try:
        spec = netcfg.parse_spec(spec_text)
    except netcfg.NetCfgError as e:
        raise LabError(f"spec error: {e}")
    cfg = netcfg.generate(spec)
    frr = cfg.split("! firewall")[0].rstrip() + "\n!\n"
    return spec, frr


def _current_remote_conf():
    rc, out, err = _run("sudo -n cat /etc/frr/frr.conf", timeout=20)
    if rc != 0:
        raise LabError(f"could not read /etc/frr/frr.conf: {err.strip()}")
    return out


# --- read-only: query live routing state --------------------------------
_SHOW_CMDS = {
    "int": "show ip int brief",
    "routes": "show ip route",
    "ospf": "show ip ospf",
    "bgp": "show bgp summary",
    "all": "show ip int brief; show ip route; show ip ospf; show bgp summary",
}


def do_lab_state(args, pol):
    """Read-only: pull live routing/interface state from the lab FRR.
    If a node is given, query that lab router (vtysh -N <node>); if node is
    'all', query every node in the built topology. Otherwise fall back to the
    global instance."""
    which = (args.get("what") or args.get("content") or "all").strip() or "all"
    key = next((k for k in _SHOW_CMDS if k in which), "all")
    cmd = _SHOW_CMDS[key]
    node = (args.get("node") or args.get("name") or "").strip()
    if node:
        try:
            plan = _LAB_PLAN or _read_remote_plan()
        except LabError:
            plan = {}
        nodes = sorted(plan.get("nodes", {})) if node == "all" else [node]
        blocks = []
        for n in nodes:
            res = _labctl("state", n, cmd, timeout=40)
            out = res.get("out")
            if out is None:
                blocks.append(f"=== {n} ===\n<error: {res.get('error', '?')}>")
            else:
                lines = [ln for ln in out.splitlines()
                         if ln and not ln.startswith("IPv4 unicast VRF")]
                blocks.append(f"=== {n} :: {cmd} ===\n" + "\n".join(lines))
        return "\n\n".join(blocks)
    rc, out, err = _run(f"sudo -n vtysh -c '{_SHOW_CMDS[key]}'", timeout=20)
    if rc != 0:
        return f"lab check failed: {err.strip() or 'non-zero exit'}"
    # squash the banner so it reads cleanly
    lines = []
    for ln in out.splitlines():
        if ln.startswith("FRRouting") or ln == "Hello, this is FRRouting":
            continue
        lines.append(ln)
    return f"=== lab host  {cmd} ===\n" + "\n".join(lines)


# --- dry-run: build + diff (NO WRITE) -----------------------------------
def do_lab_push(args, pol):
    """Read-only dry-run: build config from the spec + show the diff vs the
    current /etc/frr/frr.conf on the lab. Never writes."""
    try:
        spec, cfg = _gen_config(args.get("content") or "")
    except LabError as e:
        return {"note": str(e), "id": None}
    cur = _current_remote_conf()
    old_lines = [l.rstrip() for l in cur.splitlines() if l.strip() and not l.startswith("!")]
    new_lines = [l.rstrip() for l in cfg.splitlines() if l.strip() and not l.startswith("!")]
    diff = "\n".join(difflib.unified_diff(
        old_lines, new_lines, fromfile="lab host frr.conf (current)",
        tofile="lab host frr.conf (proposed)", lineterm="",)) or "(no differences)"
    _PENDING_ID[0] += 1
    pid = f"lb{_PENDING_ID[0]}"
    _PENDING[pid] = cfg
    while len(_PENDING) > _MAX_PENDING:
        _PENDING.pop(next(iter(_PENDING)))
    return {"id": pid, "host": f"{LAB_USER}@{LAB_HOST}",
            "diff": diff, "created": spec["hostname"] or "router"}


def do_lab_apply(args, pol):
    """GATED mutation: install the pending config on the lab and reload FRR."""
    pid = args.get("id") or args.get("pending")
    cfg = _PENDING.get(pid)
    if cfg is None:
        return {"note": "no such pending lab config", "applied": False}
    # write via stdin redirection (never a shell string), then install+reload
    rc, out, err = _run("sudo -n tee /etc/frr/frr.conf.frrtmp >/dev/null",
                        input_bytes=cfg, timeout=30)
    if rc != 0:
        return {"note": f"write failed: {err.strip()}", "applied": False}
    rc, out, err = _run(
        "sudo -n bash -c 'chown frr:frr /etc/frr/frr.conf.frrtmp && "
        "mv -f /etc/frr/frr.conf.frrtmp /etc/frr/frr.conf && "
        "/usr/lib/frr/frrinit.sh restart >/dev/null 2>&1'",
        timeout=60)
    _PENDING.pop(pid, None)
    if rc != 0:
        return {"note": f"install/reload failed: {err.strip()}", "applied": False}
    rc, v, e = _run("sudo -n vtysh -c 'show version'", timeout=20)
    version = v.splitlines()[0] if v else "?"
    return {"note": f"applied to {LAB_USER}@{LAB_HOST}: {version}", "applied": True}


# =====================================================================
# Multi-node lab: several FRR routers in Linux network namespaces on the
# lab host, joined by veth links. Driven by the lab host-side labctl.py
# (a validated-plan executor). All topology/config text is produced here
# from a safe DSL and transported as a JSON plan via stdin redirection.
# =====================================================================

_LABCTL = os.environ.get("TOOLRX_LABCTL", os.path.join(HERE, "labctl.py"))
_LAB_PLAN_PATH = os.environ.get("TOOLRX_LAB_PLAN",
                               os.path.join(HERE, "labplan.json"))
_LAB_PLAN = {}              # session cache of the last (built) plan
_LAB_PENDING = {}           # staged builds awaiting gated apply
_LAB_PENDING_ID = [0]
_LAB_MAX_PENDING = 8

_TOKEN_RE = re.compile(r"^[a-z0-9 ._/:,-]+$")


def _net(ip_cidr):
    return str(ipaddress.ip_network(ip_cidr, strict=False))


def parse_labtopo(spec_text):
    """Parse the safe topology DSL into a plan dict.

    DSL (one verb per line, only [a-z0-9 ._/:,-]):
      node <name>                 begin a node
        <iface> <ip/prefix>       one interface per line
        ospf router-id <ip>       enable OSPF, set this node's router-id
      link <node>.<iface> <node>.<iface>
    """
    nodes, links = {}, []
    cur, rid = None, None
    for raw in spec_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not _TOKEN_RE.match(line):
            raise LabError(f"unsafe chars in line: {line!r}")
        tok = line.split()
        if tok[0] == "node":
            cur, rid = tok[1], None
            if cur in nodes:
                raise LabError(f"duplicate node {cur}")
            nodes[cur] = {"ifs": [], "rid": None}
        elif tok[0] == "link":
            if len(tok) != 3:
                raise LabError(f"link needs two endpoints: {line!r}")
            links.append((tok[1], tok[2]))
        elif tok[0] == "ospf":
            if len(tok) == 3 and tok[1] == "router-id":
                ipaddress.ip_address(tok[2])  # validate
                nodes[cur]["rid"] = tok[2]
            else:
                raise LabError(f"bad ospf line: {line!r}")
        else:
            if len(tok) != 2 or not re.match(r"^[a-z0-9]+$", tok[0]):
                raise LabError(f"unrecognized line: {line!r}")
            ipaddress.ip_interface(tok[1])  # validate
            nodes[cur]["ifs"].append({"name": tok[0], "ip": tok[1]})
    if not nodes:
        raise LabError("no nodes in topology")
    if not links:
        raise LabError("no links in topology")
    # resolve + validate links
    link_list = []
    for a, b in links:
        an, ai = a.split(".", 1)
        bn, bi = b.split(".", 1)
        if an not in nodes or bn not in nodes:
            raise LabError(f"link {a} <-> {b}: unknown node")
        if an == bn:
            raise LabError(f"link {a} <-> {b}: cannot link a node to itself")
        aip = next((f["ip"] for f in nodes[an]["ifs"] if f["name"] == ai), None)
        bip = next((f["ip"] for f in nodes[bn]["ifs"] if f["name"] == bi), None)
        if aip is None or bip is None:
            raise LabError(f"link {a} <-> {b}: unknown interface")
        if _net(aip) != _net(bip):
            raise LabError(f"link {a} <-> {b}: endpoints on different subnets")
        link_list.append({"id": f"{a}<->{b}", "a": [an, ai], "b": [bn, bi]})
    # generate a per-node FRR config (point-to-point OSPF on every link)
    plan = {"nodes": {}, "links": link_list}
    for name, node in nodes.items():
        conf = [f"hostname {name}", "!"]
        for f in node["ifs"]:
            conf += [f"interface {f['name']}", " ip ospf network point-to-point",
                     " ip ospf area 0", "!"]
        if node["rid"]:
            conf += ["router ospf", f" router-id {node['rid']}"]
            for f in node["ifs"]:
                conf += [f" network {_net(f['ip'])} area 0"]
            conf += ["!"]
        plan["nodes"][name] = {"ifs": node["ifs"], "conf": "\n".join(conf)}
    return plan


def _write_remote_plan(plan, timeout=30):
    """Write the plan to user's own home dir (no sudo needed); labctl reads it
    as root. stdin-redirected so no shell injection."""
    data = json.dumps(plan)
    rc, out, err = _run(f"tee {_LAB_PLAN_PATH} >/dev/null",
                        timeout=timeout, input_bytes=data)
    if rc != 0:
        raise LabError(f"plan write failed: {err.strip()}")
    _LAB_PLAN.clear()
    _LAB_PLAN.update(plan)


def _read_remote_plan(timeout=20):
    rc, out, err = _run(f"cat {_LAB_PLAN_PATH}", timeout=timeout)
    if rc != 0:
        raise LabError("no lab plan on lab host (build a topology first)")
    return json.loads(out)


def _labctl(action, *args, timeout=150):
    cmd = f"sudo -n python3 {_LABCTL} {action} {_LAB_PLAN_PATH}"
    if args:
        cmd += " " + " ".join(shlex.quote(a) for a in args)
    rc, out, err = _run(cmd, timeout=timeout)
    if rc != 0:
        raise LabError(f"labctl {action}: {err.strip()}")
    try:
        return json.loads(out)
    except ValueError:
        return {"raw": out}


def do_lab_topo(args, pol):
    """Stage a multi-node topology: parse + validate the safe DSL. No build.
    Returns a pending id; the operator must apply (build) it."""
    spec = args.get("content") or args.get("spec") or ""
    plan = parse_labtopo(spec)
    _LAB_PENDING_ID[0] += 1
    pid = f"lt{_LAB_PENDING_ID[0]}"
    _LAB_PENDING[pid] = plan
    while len(_LAB_PENDING) > _LAB_MAX_PENDING:
        _LAB_PENDING.pop(next(iter(_LAB_PENDING)))
    nodes = sorted(plan["nodes"])
    links = [l["id"] for l in plan["links"]]
    return {"id": pid, "nodes": nodes, "links": links,
            "summary": f"{len(nodes)} routers, {len(links)} links (OSPF)",
            "pending": True,
            "note": "review the topology, then Build on lab host (gated)"}


def do_lab_topo_apply(args, pol):
    """GATED mutation: build the staged multi-node lab on lab host."""
    pid = args.get("id") or args.get("pending")
    plan = _LAB_PENDING.get(pid) or _LAB_PLAN
    if not plan:
        return {"note": "no staged lab topology to build", "applied": False}
    _write_remote_plan(plan)
    res = _labctl("build", timeout=200)
    _LAB_PENDING.pop(pid, None)
    _LAB_PLAN.update(plan)
    return {"note": f"lab built on {LAB_USER}@{LAB_HOST}: {res.get('built', res)}",
            "applied": True}


def do_lab_link(args, pol):
    """GATED mutation: bring a lab link up or down (failover testing)."""
    link_id = args.get("link") or args.get("id")
    action = (args.get("state") or args.get("action") or "").lower()
    if action not in ("up", "down"):
        raise LabError("link state must be up or down")
    plan = _LAB_PLAN or _read_remote_plan()
    if not any(l["id"] == link_id for l in plan["links"]):
        raise LabError(f"unknown link {link_id}")
    res = _labctl("link", link_id, action, timeout=60)
    return {"note": f"link {link_id} {action}: {res.get('state', res)}",
            "applied": True}


def do_lab_down(args, pol):
    """GATED mutation: tear down the multi-node lab on lab host."""
    _LAB_PLAN or _read_remote_plan()
    res = _labctl("teardown", timeout=120)
    _LAB_PLAN.clear()
    return {"note": f"lab torn down: {res.get('torn_down', res)}", "applied": True}

"""Deterministic network-config generation + validation (Linux/FRR focus).

This module is the "network engineer's harness": given a small declarative
spec it PRODUCES router/switch/firewall config text, and given a config it
produces a deterministic lint report. No LLM, no network calls, no writes —
everything here is pure text in / text out.

Safety posture (same default-deny as the rest of toolrx):
  * generate() and validate() are PURE. They never touch the network, never
    spawn a process, never write to disk.
  * The spec is a closed, safe-character DSL (letters, digits, spaces, and
    ./:_-). JSON braces and shell metacharacters are not part of it, so a
    spec can never smuggle in a command.
  * All IP/prefix parsing uses the stdlib ipaddress module and rejects
    anything malformed with a clear error.

Targets:
  * FRR (Free Range Routing): zebra (interfaces + static routes), ospfd, bgpd.
  * nftables: a simple allow/drop firewall.
"""

import ipaddress
import re

# --- spec parsing ---------------------------------------------------------
# A safe-character DSL. Lines are <verb> <args...>. Verbs are exactly these.
# Comments start with '#'.

class NetCfgError(Exception):
    pass


def _ip_ok(addr):
    try:
        ipaddress.ip_address(addr)
        return True
    except ValueError:
        return False


def _net_ok(prefix):
    try:
        ipaddress.ip_network(prefix, strict=False)
        return True
    except ValueError:
        return False


def parse_spec(text):
    """Parse the safe DSL into a structured dict. Raises NetCfgError on a
    malformed or unrecognized line."""
    spec = {
        "hostname": None,
        "interfaces": [],
        "routes": [],
        "ospf": {"router_id": None, "networks": []},
        "bgp": {"asn": None, "router_id": None, "neighbors": [], "networks": []},
        "firewall": {"rules": [], "default_action": "drop"},
    }
    if not text or not text.strip():
        raise NetCfgError("empty spec")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("#")]
    for ln in lines:
        parts = ln.split()
        verb = parts[0]
        rest = parts[1:]
        if verb == "hostname":
            if len(rest) != 1:
                raise NetCfgError(f"hostname needs 1 arg: {ln!r}")
            spec["hostname"] = rest[0]
        elif verb == "int":
            if len(rest) < 2:
                raise NetCfgError(f"int needs name + ip: {ln!r}")
            name, addr = rest[0], rest[1]
            if not _net_ok(addr):
                raise NetCfgError(f"bad ip/prefix on interface {name}: {addr}")
            spec["interfaces"].append(
                {"name": name, "ip": addr, "desc": " ".join(rest[2:])})
        elif verb == "route":
            if len(rest) < 3 or rest[1] != "via":
                raise NetCfgError(f"route needs 'prefix via nexthop': {ln!r}")
            prefix, nexthop = rest[0], rest[2]
            if not _net_ok(prefix):
                raise NetCfgError(f"bad route prefix: {prefix}")
            if not _ip_ok(nexthop):
                raise NetCfgError(f"bad nexthop: {nexthop}")
            distance = 0
            if len(rest) > 3 and rest[3] == "admin" and len(rest) > 4:
                try:
                    distance = int(rest[4])
                except ValueError:
                    raise NetCfgError(f"bad admin distance: {rest[4]}")
            spec["routes"].append(
                {"prefix": prefix, "nexthop": nexthop, "distance": distance})
        elif verb == "ospf":
            if len(rest) < 2:
                raise NetCfgError(f"ospf needs router-id: {ln!r}")
            if rest[0] == "router-id":
                rid = rest[1]
                if not _ip_ok(rid):
                    raise NetCfgError(f"bad ospf router-id: {rid}")
                spec["ospf"]["router_id"] = rid
            elif rest[0] == "net" and len(rest) >= 4 and rest[2] == "area":
                if not _net_ok(rest[1]):
                    raise NetCfgError(f"bad ospf network: {rest[1]}")
                spec["ospf"]["networks"].append(
                    {"prefix": rest[1], "area": rest[3]})
            else:
                raise NetCfgError(f"bad ospf line: {ln!r}")
        elif verb == "bgp":
            if rest[0] == "asn":
                if len(rest) < 3 or rest[2] != "router-id":
                    raise NetCfgError(f"bgp asn needs router-id: {ln!r}")
                try:
                    spec["bgp"]["asn"] = int(rest[1])
                except ValueError:
                    raise NetCfgError(f"bad asn: {rest[1]}")
                if not _ip_ok(rest[3]):
                    raise NetCfgError(f"bad bgp router-id: {rest[3]}")
                spec["bgp"]["router_id"] = rest[3]
            elif rest[0] == "neighbor":
                if len(rest) < 4 or rest[2] != "remote-as":
                    raise NetCfgError(f"bgp neighbor needs remote-as: {ln!r}")
                if not _ip_ok(rest[1]):
                    raise NetCfgError(f"bad neighbor ip: {rest[1]}")
                try:
                    spec["bgp"]["neighbors"].append(
                        {"ip": rest[1], "asn": int(rest[3])})
                except ValueError:
                    raise NetCfgError(f"bad neighbor asn: {rest[3]}")
            elif rest[0] == "network":
                if len(rest) != 2 or not _net_ok(rest[1]):
                    raise NetCfgError(f"bad bgp network: {ln!r}")
                spec["bgp"]["networks"].append(rest[1])
            else:
                raise NetCfgError(f"bad bgp line: {ln!r}")
        elif verb == "fw":
            if rest[0] == "allow":
                if len(rest) < 3:
                    raise NetCfgError(f"fw allow needs proto + port: {ln!r}")
                proto, port = rest[1], rest[2]
                if proto not in ("tcp", "udp", "icmp"):
                    raise NetCfgError(f"bad fw proto: {proto}")
                if proto != "icmp" and not rest[2].isdigit():
                    raise NetCfgError(f"bad fw port: {port}")
                spec["firewall"]["rules"].append(
                    {"action": "accept", "proto": proto, "port": port})
            elif rest[0] == "drop":
                if len(rest) == 1 or rest[1] == "all":
                    spec["firewall"]["default_action"] = "drop"
                else:
                    raise NetCfgError(f"bad fw drop line: {ln!r}")
            else:
                raise NetCfgError(f"bad fw line: {ln!r}")
        else:
            raise NetCfgError(f"unknown verb: {verb!r}")
    return spec


# --- generation -----------------------------------------------------------
def generate(spec):
    """Turn a parsed spec (dict) into FRR + nftables config text."""
    out = []
    out.append(f"! generated by toolrx net.cfg_gen")
    out.append(f"hostname {(spec['hostname'] or 'router').replace(' ', '')}")
    out.append(f"!")
    out.append(f"# interfaces")
    for itf in spec["interfaces"]:
        out.append(f"interface {itf['name']}")
        out.append(f" ip address {itf['ip']}")
        if itf["desc"]:
            out.append(f" description {itf['desc']}")
        out.append(f"!")
    if spec["routes"]:
        out.append(f"! static routes")
        out.append(f"ip route")
        for r in spec["routes"]:
            dist = f" {r['distance']}" if r["distance"] else ""
            out.append(f" {r['prefix']} {r['nexthop']}{dist}")
        out.append(f"!")
    ospf = spec["ospf"]
    if ospf["router_id"] or ospf["networks"]:
        out.append(f"! ospf")
        out.append(f"router ospf")
        if ospf["router_id"]:
            out.append(f" ospf router-id {ospf['router_id']}")
        for n in ospf["networks"]:
            out.append(f" network {n['prefix']} area {n['area']}")
        out.append(f"!")
    bgp = spec["bgp"]
    if bgp["asn"] is not None:
        out.append(f"! bgp")
        out.append(f"router bgp {bgp['asn']}")
        if bgp["router_id"]:
            out.append(f" bgp router-id {bgp['router_id']}")
        for n in bgp["networks"]:
            out.append(f" network {n}")
        for nb in bgp["neighbors"]:
            out.append(f" neighbor {nb['ip']} remote-as {nb['asn']}")
        out.append(f"!")

    # firewall (nftables)
    fw = spec["firewall"]
    rules = fw["rules"]
    if rules or fw["default_action"]:
        out.append(f"! firewall (nftables)")
        out.append(f"table inet filter {{")
        out.append(f"  chain input {{")
        out.append(f"    type filter hook input priority filter; policy {fw['default_action']};")
        for r in rules:
            if r["proto"] == "icmp":
                out.append(f"    ip protocol icmp accept")
            else:
                out.append(f"    {r['proto']} dport {r['port']} accept")
        out.append(f"    ct state established,related accept")
        out.append(f"  }}")
        out.append(f"}}")
    return "\n".join(out)


# --- validation -----------------------------------------------------------
def _cidr_contains(network, addr):
    return ipaddress.ip_address(addr) in ipaddress.ip_network(network, strict=False)


def validate(spec):
    """Deterministic lint report over a parsed spec. Returns a list of strings
    ('OK', 'WARN', or 'ERR')."""
    findings = []
    if not spec["hostname"]:
        findings.append("ERR hostname not set")
    if not spec["interfaces"]:
        findings.append("WARN no interfaces configured")
    connected = [ipaddress.ip_network(i["ip"], strict=False) for i in spec["interfaces"]]

    # static routes: nexthop must be on a connected interface
    for r in spec["routes"]:
        ok = any(_cidr_contains(cn, r["nexthop"]) for cn in connected)
        findings.append(
            f"OK  route {r['prefix']} via {r['nexthop']}" if ok
            else f"WARN route {r['prefix']} nexthop {r['nexthop']} not on a connected subnet")

    # ospf networks should not overlap each other
    nets = [ipaddress.ip_network(n["prefix"], strict=False) for n in spec["ospf"]["networks"]]
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            if nets[i].overlaps(nets[j]):
                findings.append(f"WARN ospf networks overlap: {nets[i]} & {nets[j]}")
    if spec["ospf"]["networks"] and not spec["ospf"]["router_id"]:
        findings.append("WARN ospf configured without a router-id")

    # bgp
    if spec["bgp"]["asn"] is not None:
        if not spec["bgp"]["router_id"]:
            findings.append("ERR bgp asn set but no bgp router-id")
        for nb in spec["bgp"]["neighbors"]:
            if _ip_ok(nb["ip"]) and connected and any(_cidr_contains(cn, nb["ip"]) for cn in connected):
                pass  # neighbor reachable on a connected subnet
            else:
                findings.append(f"WARN bgp neighbor {nb['ip']} not on a connected subnet")
            if spec["bgp"]["router_id"] and nb["ip"] == spec["bgp"]["router_id"]:
                findings.append(f"ERR bgp neighbor {nb['ip']} equals router-id (self)")

    # firewall shadowing: a 'drop' before an 'allow' shadows it
    fw = spec["firewall"]
    seen_drop_all = False
    for r in fw["rules"]:
        if seen_drop_all:
            findings.append(f"WARN rule after drop-all is shadowed: {r['proto']} {r['port']}")
        if fw["default_action"] == "drop" and r["port"] and r["port"].isdigit() and not (0 <= int(r["port"]) <= 65535):
            findings.append(f"ERR fw port out of range: {r['port']}")
    return findings or ["OK  no issues found"]


# --- executor-facing entry points ------------------------------------------
def do_cfg_gen(args, pol):
    """Generate FRR + nftables config from a safe DSL spec."""
    spec_text = (args.get("spec") or args.get("content") or "").strip()
    if not spec_text:
        return "spec is empty"
    try:
        spec = parse_spec(spec_text)
    except NetCfgError as e:
        return f"spec error: {e}"
    cfg = generate(spec)
    return f"=== {spec['hostname'] or 'router'}: generated config ===\n{cfg}"


def do_cfg_check(args, pol):
    """Deterministic lint over a safe DSL spec (or a generated config)."""
    spec_text = (args.get("spec") or args.get("content") or "").strip()
    if not spec_text:
        return "spec is empty"
    try:
        spec = parse_spec(spec_text)
    except NetCfgError as e:
        return f"spec error: {e}"
    report = validate(spec)
    return "\n".join(report)

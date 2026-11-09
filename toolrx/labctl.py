#!/usr/bin/env python3
"""labctl: build/teardown/manipulate a multi-node FRR lab in Linux network
namespaces on this host. Each node = one netns + one FRR instance.

All node/link/config details come from a JSON PLAN that the phone-side
harness computes from a safe DSL. This script only executes a validated plan;
it never invents topology or config.
"""
import json, os, shutil, subprocess, sys

FRRINIT = "/usr/lib/frr/frrinit.sh"
VTYSHPATH = shutil.which("vtysh") or "/usr/bin/vtysh"

def run(*argv, check=False, timeout=90):
    argv = ["sudo", "-n"] + list(argv)
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ("", f"timed out: {' '.join(argv)}", 124)
    if check and p.returncode != 0:
        raise RuntimeError(f"cmd failed rc={p.returncode}: {' '.join(argv)}\n{p.stderr.strip()}")
    return p.stdout, p.stderr, p.returncode

def ip_netns(*args, check=False):
    return run("ip", "netns", *args, check=check)

def build(plan):
    nodes, links = plan["nodes"], plan["links"]
    teardown(plan)  # idempotent: clean any leftovers first
    for name in nodes:
        ip_netns("add", name, check=True)
        run("ip", "netns", "exec", name, "ip", "link", "set", "lo", "up", check=True)
    for i, link in enumerate(links):
        a_ns, a_if = link["a"]; b_ns, b_if = link["b"]
        va, vb = f"labv{i}a", f"labv{i}b"
        run("ip", "link", "add", va, "type", "veth", "peer", "name", vb, check=True)
        run("ip", "link", "set", va, "netns", a_ns, check=True)
        run("ip", "link", "set", vb, "netns", b_ns, check=True)
        run("ip", "netns", "exec", a_ns, "ip", "link", "set", va, "name", a_if, check=True)
        run("ip", "netns", "exec", b_ns, "ip", "link", "set", vb, "name", b_if, check=True)
        for ns, ifname in ((a_ns, a_if), (b_ns, b_if)):
            node = nodes[ns]
            ip = next((f["ip"] for f in node["ifs"] if f["name"] == ifname), None)
            run("ip", "netns", "exec", ns, "ip", "addr", "add", ip, "dev", ifname, check=True)
            run("ip", "netns", "exec", ns, "ip", "link", "set", "mtu", "1500", "dev", ifname, check=True)
            run("ip", "netns", "exec", ns, "ip", "link", "set", ifname, "up", check=True)
    # write per-node FRR config + daemons file, then start each instance
    for name, node in nodes.items():
        confdir = f"/etc/frr/{name}"
        run("mkdir", "-p", confdir, check=True)
        run("chown", "frr:frr", confdir, check=True)
        run("cp", "/dev/null", f"{confdir}/frr.conf", check=True)  # clear stale
        with open(f"/tmp/{name}.conf", "w") as f:
            f.write(node["conf"] + "\n")
        run("cp", f"/tmp/{name}.conf", f"{confdir}/frr.conf", check=True)
        with open(f"/tmp/{name}.daemons", "w") as f:
            f.write(
                "zebra=yes\nstaticd=yes\nmgmtd=yes\nospfd=yes\nbgpd=yes\n"
                "vtysh_enable=yes\n"
                f'watchfrr_options=" --netns {name}"\n')
        run("cp", f"/tmp/{name}.daemons", f"{confdir}/daemons", check=True)
        for f in ("frr.conf", "daemons"):
            run("chown", "frr:frr", f"{confdir}/{f}", check=True)
            run("chmod", "640", f"{confdir}/{f}", check=True)
        run(FRRINIT, "start", name)
    return {"built": list(nodes), "links": len(links)}

def teardown(plan):
    nodes = plan.get("nodes", {})
    for name in nodes:
        run(FRRINIT, "stop", name)
    for name in nodes:
        ip_netns("del", name)
    for name in nodes:
        run("rm", "-rf", f"/etc/frr/{name}")
    return {"torn_down": list(nodes)}

def link_updown(plan, link_id, action):
    for link in plan["links"]:
        if link["id"] == link_id:
            for ns, ifname in (link["a"], link["b"]):
                run("ip", "netns", "exec", ns, "ip", "link", "set", ifname,
                    "down" if action == "down" else "up", check=True)
            return {"link": link_id, "state": action}
    raise RuntimeError(f"unknown link {link_id}")

def state(plan, node, vcmd):
    if node not in plan["nodes"]:
        raise RuntimeError(f"unknown node {node}")
    out, err, rc = run(VTYSHPATH, "-N", node, "-c", vcmd)
    if rc != 0:
        return {"node": node, "cmd": vcmd, "error": err.strip() or "non-zero exit"}
    lines = [l for l in out.splitlines() if not l.startswith("FRRouting")]
    return {"node": node, "cmd": vcmd, "out": "\n".join(lines)}

def main():
    if len(sys.argv) < 3:
        print("usage: labctl.py <build|teardown|link|state> <plan.json> [link_id] [up|down|cmd]")
        return 1
    action = sys.argv[1]
    with open(sys.argv[2]) as f:
        plan = json.load(f)
    if action == "build":
        print(json.dumps(build(plan)))
    elif action == "teardown":
        print(json.dumps(teardown(plan)))
    elif action == "link":
        link_id, updown = sys.argv[3], sys.argv[4]
        print(json.dumps(link_updown(plan, link_id, updown)))
    elif action == "state":
        node, cmd = sys.argv[3], sys.argv[4]
        print(json.dumps(state(plan, node, cmd)))
    else:
        print(f"unknown action {action}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())

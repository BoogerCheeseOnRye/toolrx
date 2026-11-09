# Network config validator / linter (deterministic)

CHECK, VALIDATE, LINT, REVIEW, VERIFY, or AUDIT a network configuration.
This tool ANSWERS about a config — it does not build one. Prefer it whenever
the user wants to check, validate, lint, review, verify, audit, inspect,
probe, or test a router/switch/firewall config for problems, correctness,
mistakes, or issues.

Checks a network configuration or routing/firewall spec for problems and
prints a plain report, without an LLM. Deterministic and read-only: it only
analyzes text and returns findings; it never changes, installs, or applies
anything.

Use this when the user wants to check, validate, lint, review, verify, audit,
inspect, probe, or test a network configuration: whether interfaces are
addressed, a static route nexthop is reachable, OSPF networks overlap, BGP
router-id or neighbor setup is correct, or firewall rules are shadowed or out
of order. Understands network words like interface, subnet, prefix, route,
nexthop, gateway, asn, autonomous system, bgp neighbor, remote-as, router-id,
ospf area, ospf network, firewall, nftables, allow, drop, shadow, and hostname.

It accepts the same safe DSL as net.cfg_gen (hostname, int, route, ospf, bgp,
fw lines) and emits OK / WARN / ERR findings. Pure analysis; never applies
anything.

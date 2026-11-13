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

Longer requests and phrasings:
Check this network configuration for mistakes and lint the safe DSL.
Validate the router config and report any errors in the specification.
Review the network spec and tell me whether it is well formed.
Lint these interface and routing statements before I apply them.
Audit the config for missing addresses, bad nexthops, or shadowed rules.
Find problems in this firewall and routing configuration.
Verify the OSPF and BGP statements and return OK WARN or ERR findings.
Inspect the configuration for correctness without generating anything new.

Accepts the routing statements, interface statements, firewall statements, and
safe DSL text as input, and reviews them before deployment or before you apply
them. Look for lint these statements, check before applying, pre deployment
review, validate prior to install, audit the routing statements, or verify the
config text. It returns findings only and never stages or applies a lab change.

This is the analysis tool for configuration text the user already has or is
about to deploy. It returns findings about that text: OK, WARN, or ERR. It is
not the generator: it does not produce, emit, compose, or print new
configuration. Ask for a check, lint, validation, review, audit, verification,
or correctness report and this tool answers with findings only.

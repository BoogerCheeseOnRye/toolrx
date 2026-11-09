# Network config generator (Linux / FRR)

Generates a ready-to-review router, switch, or firewall configuration from a
small declarative spec, without an LLM. Deterministic and dry-run: it only
PRINTS the config text, never writes it and never touches the network.

Use this when the user wants to build or generate a network configuration:
OSPF or BGP routing, static routes, interface addressing, subnets, a firewall
policy, or a router/switch/firewall config for Linux, FRR, zebra, ospfd, or
bgpd. Understands network engineering words like interface, subnet, prefix,
route, nexthop, gateway, asn, autonomous system, bgp neighbor, remote-as,
router-id, ospf area, ospf network, advertise, prefix, firewall, nftables,
iptables, allow, drop, tcp, udp, icmp, port, and hostname.

The spec is a simple safe DSL, one line per item:
  hostname r1
  int eth0 10.0.0.1/24 uplink to core
  route 0.0.0.0/0 via 10.0.0.254
  ospf router-id 10.0.0.1
  ospf net 10.0.0.0/24 area 0
  bgp asn 65000 router-id 10.0.0.1
  bgp neighbor 10.0.1.2 remote-as 65001
  bgp network 10.0.0.0/24
  fw allow tcp 22
  fw allow tcp 443
  fw drop all

Generated output covers FRR zebra (interfaces + static routes), ospfd, bgpd,
and an nftables firewall. Read-only, pure text. This tool does NOT apply,
install, or reboot anything.

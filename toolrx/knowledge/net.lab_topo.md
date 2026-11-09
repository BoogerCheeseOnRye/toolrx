# Lab: multi-node topology builder (safe DSL -> staged build)

Takes a multi-node lab topology written in a safe DSL and stages it for a
gated build. This step is read-only: it PARSES and VALIDATES the topology and
returns a pending id; it does NOT create anything yet. A separate gated apply
step actually builds it on the lab host (lab host).

The DSL describes routers and the links between them, one verb per line:
  node <name>                start describing a router (e.g. node r1)
    <iface> <ip/prefix>      one interface per line (e.g. eth0 10.0.1.1/24)
    ospf router-id <ip>      enable OSPF on this router and set its router-id
  link <node>.<iface> <node>.<iface>   connect two interfaces on one subnet

Example of a three-router triangle:
  node r1
    eth0 10.0.1.1/24
    eth1 10.0.2.1/24
    ospf router-id 10.0.0.1
  node r2
    eth0 10.0.1.2/24
    eth1 10.0.3.2/24
    ospf router-id 10.0.0.2
  node r3
    eth0 10.0.2.3/24
    eth1 10.0.3.3/24
    ospf router-id 10.0.0.3
  link r1.eth0 r2.eth0
  link r1.eth1 r3.eth0
  link r2.eth1 r3.eth1

Each node becomes an FRR router in its own Linux network namespace on the lab
host; each link becomes a veth pair joining two namespaces on a shared /24.
Every link runs OSPF point-to-point, so adjacencies form reliably and equal-
cost multipath (ECMP) gives failover + load distribution for free.

Understands words like topology, topology builder, routers, nodes, links,
mesh, triangle, ospf, ecmp, failover, namespace, multi-node, and build lab.
The action is staged (dry-run) and always gated before anything is created.

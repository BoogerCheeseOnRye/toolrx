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

Longer requests and phrasings:
Build a multi node lab topology from this safe DSL with routers and links.
Parse this three router topology and stage it for a gated build.
Create a mesh of nodes and links and validate the topology first.
Describe a network topology with nodes, interfaces, and OSPF and stage it.
Take the node and link DSL and return a pending topology id.
Validate a triangle of routers and links without creating anything.
Stage a multi node namespace topology for later confirmation.
Read the topology description and prepare, but do not build, the lab.

This tool only parses, validates, and stages a topology description, then
returns a pending id. It is the dry run before approval: stage the topology,
validate the mesh first, parse the three router design, prepare the node and
link description, and return a pending topology id. It does not create
namespaces, does not make veth pairs, and does not start any router.

Validate the topology first and stage it before anything runs. A request that
says create a mesh of nodes and links and validate the topology first is still
the staging step: parse the design, check the nodes and links, and return a
pending id. Stage triangle and mesh descriptions, then wait for approval.

This is the staging step, not the apply step. A request belongs here when it
asks to stage a topology, parse a design, validate the mesh, prepare it for
approval, or return a pending topology id. The request may say nothing is
created yet, no namespaces exist yet, no veth pairs are made yet, and no router
is started yet. That is correct: this step is validation and staging only. It
does not instantiate the design, does not bring up infrastructure, and does not
perform the later build. Use it for the dry run, the parse pass, and the validation report that come
before anyone approves the build.

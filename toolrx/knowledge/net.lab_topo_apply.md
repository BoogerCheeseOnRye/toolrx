# Lab: apply (build) a staged multi-node topology on the lab host

GATED mutation. Takes a pending topology id (produced by the lab topology
builder / net.lab_topo) and actually BUILDS it on the lab host (lab host):
creates the network namespaces, the veth links, brings up the interfaces,
writes each node's FRR config under /etc/frr/<node>/, and starts an FRR
instance per node. This is the only step that changes the lab.

Because it is a mutation it is never run automatically from free text: the
operator must confirm the topology and press the gated apply/build action.

Understands words like build, build the lab, apply the topology, bring it up,
create the lab, start the routers, and confirm. Requires a valid pending id.
After building, use the state tool to check OSPF neighbors and routes.

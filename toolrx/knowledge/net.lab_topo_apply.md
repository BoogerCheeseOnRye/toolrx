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

Longer requests and phrasings:
Apply the pending topology build using the id that was returned.
Commit the staged multi node topology and create the namespaces now.
Take the topology id and actually build the lab network from it.
Deploy the validated topology and connect all of the routers.
Instantiate the veth pairs and start one FRR router per node.
Build the lab now from the confirmed pending topology.
Create the namespaces and links for the staged multi node design.
After validation, create the actual routers and connections.

This tool performs the actual creation after approval: build the namespaces,
make the veth pairs, start one FRR router per node, instantiate the pending
topology, and connect the real lab. It consumes a pending topology id and turns
it into running infrastructure. Use it for build now, create the lab, deploy
the confirmed topology, bring up the routers, and instantiate the staged design.

Use this only once the user approves and wants running infrastructure now. The
request is an actual build: instantiate the approved design, create the
namespaces, make the veth pairs, start the FRR routers, bring the lab up,
deploy the confirmed design, and connect the interfaces.

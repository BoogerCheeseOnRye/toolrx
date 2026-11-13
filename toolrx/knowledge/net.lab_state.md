# Lab: read-only live routing state (lab host FRR)

Pulls the CURRENT live routing and interface state from the lab backend
(lab host, an FRR instance reached over SSH) and prints it. Deterministic and
read-only: it only runs vtysh "show" commands and returns their output. It
never changes, applies, or reboots anything.

Use this when the user wants to check, inspect, query, or see the live state
of the lab: the routing table (show ip route), interfaces (show ip int
brief), OSPF neighbors/process (show ip ospf), BGP summary (show bgp
summary), or everything. Understands words like lab, routing table, routes,
interfaces, adjacency, neighbor, ospf, bgp, prefix, and route table.

The "what" argument selects what to show: int, routes, ospf, bgp, or all
(default). Pure query over the allowlisted lab host; never mutates anything.

Longer requests and phrasings:
Show the current state of the network lab, including routes and OSPF.
What is the lab state right now for interfaces, routes, and BGP?
Print the running state of the simulated routers in the lab.
Display the lab routing tables and all interface addresses.
Query the live lab for OSPF neighbors and BGP summary.
Inspect the current namespace state and the live routes.
Read the running router state from the lab without changing it.
What do the lab routers currently report for routes and adjacencies?

This is a read only query of the current live lab state. Ask for the running
state of the topology, the present topology state, current routes, live
interfaces, OSPF neighbors, or BGP summary. It displays the existing state and
does not build, create, apply, stage, or change any part of the topology.

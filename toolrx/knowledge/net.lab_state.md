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
# Lab: link up/down (failover and load-distribution testing)

GATED mutation. Brings a specific link of the multi-node lab up or down. This
is how you exercise routing convergence on a real topology: pull a link down
and watch OSPF re-route around the failure; bring it back up and watch the
equal-cost paths return.

Operates on a link identifier that looks like "r1.eth0<->r2.eth0" (the two
endpoints that were joined). The state argument must be "up" or "down".

Use this for failover testing, link failure, cut a link, break the link,
kill the link, convergence, network resilience, and load distribution. Like
every mutation it is gated: it only runs from the explicit lab controls, not
automatically from free text.

Longer requests and phrasings:
Set the lab link between r1 and r2 to down and report the result.
Bring the specified network link up or down in the lab topology.
Change the state of this link identifier to up in the lab.
Toggle the connection between two router interfaces in the lab.
Cut one link to test failover and OSPF convergence.
Restore a failed link and watch the equal cost paths return.
Bend the state of a single veth connection up or down.
Operate on one link id with an up or down state.

Operates on exactly one link identifier and sets its state to up or down. Look
for toggle one connection, set a single link down, change this link identifier
to up, cut just this connection, break one link, restore that link, or flip the
state of a specific pair of router interfaces. The whole lab and every router
are left alone.

Toggle the connection between two router interfaces, change the connection
between r1 and r2, or flip the connection state for one pair of interfaces.
The words connection, two router interfaces, and between two endpoints point
to a single link operation rather than a state query.

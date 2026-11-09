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

# Lab: tear down the multi-node lab

GATED mutation. Stops every per-node FRR instance, deletes all the network
namespaces, and removes the per-node config directories on the lab host. It
fully undoes a built topology, leaving lab host clean.

Understands words like tear down, teardown, destroy the lab, delete the lab,
stop the lab, remove all the routers, clean up the lab, and undo the lab.
Like every mutation it is gated: it runs from the explicit lab controls, not
automatically from free text.

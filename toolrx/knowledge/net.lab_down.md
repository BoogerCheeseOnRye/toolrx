# Lab: tear down the multi-node lab

GATED mutation. Stops every per-node FRR instance, deletes all the network
namespaces, and removes the per-node config directories on the lab host. It
fully undoes a built topology, leaving lab host clean.

Understands words like tear down, teardown, destroy the lab, delete the lab,
stop the lab, remove all the routers, clean up the lab, and undo the lab.
Like every mutation it is gated: it runs from the explicit lab controls, not
automatically from free text.

Longer requests and phrasings:
Take down the entire lab and remove all of the simulated routers.
Shut down every namespace and link in the network lab.
Tear down the whole lab environment and clean up the topology.
Stop the lab and destroy all of the running router instances.
Remove every node, veth pair, and per node config directory.
Delete the complete lab and leave the lab host clean.
Clean up all routers and links after testing.
Destroy the entire multi node lab in one gated action.

Tears down the entire lab in one action: every namespace, every link, every
router instance, and the whole topology. Look for all links, every node, the
whole lab, the entire environment, all routers, destroy everything, clean up
the complete lab, and remove every namespace at once. The scope is all or
nothing, not a single link or a single router.

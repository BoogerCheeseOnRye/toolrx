# Lab: dry-run push (build + diff, NO WRITE)

Builds a config from a network spec and shows the DIFF against the lab's
current configuration (/etc/frr/frr.conf on lab host), without changing
anything. The is the review step before any apply. Deterministic and
read-only — it prints what WOULD change and never writes.

Use this when the user wants to push, deploy, stage, preview, or review a
config for the lab, or see what would change on the router before applying.
Works with the same safe DSL as net.cfg_gen (hostname, int, route, ospf,
bgp, fw lines). Understands push, deploy, stage, preview, diff, apply to
router, and make this change.

The result is a pending change (id) that is only written if the operator
explicitly applies it via net.lab_apply. Nothing is written by this tool.
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

Longer requests and phrasings:
Push this network specification to the lab as a dry run.
Stage these configuration changes on the lab host without applying.
Send this safe DSL config to the lab and show me the pending result.
Preview what would change if I pushed this lab configuration.
Diff the proposed config against the lab's current FRR file.
Prepare a pending change id for review, with no write.
Show the pending lab diff before anything is committed.
Build and compare a lab config, but do not apply it yet.

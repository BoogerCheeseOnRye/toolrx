# Lab: apply a pending config (GATED mutation)

Applies a previously staged (net.lab_push) config to the lab backend's FRR:
installs /etc/frr/frr.conf on lab host and reloads the FRR daemons. This is
the ONLY net tool that changes anything, so it is gated — it only acts on a
config id produced by the dry-run push, never on arbitrary input.

Use this when the user confirms they want to apply a reviewed config to the
lab router: apply, deploy, push, save, commit, activate, roll out, or write
this change to the router. The config bytes are always regenerated from the
safe DSL, so no injection is possible; the file reaches lab host via stdin
redirection, never a shell string.

Always preceded by net.lab_push so the operator sees the diff first. The
prior /etc/frr/frr.conf is intended to be backed up before applying. This
restarts the FRR daemons.

Longer requests and phrasings:
Apply the pending lab configuration using the id from the push.
Confirm and commit the staged network config to the lab now.
Take the pending configuration id and make it active on the lab.
Deploy the previously staged lab changes with this identifier.
Install the reviewed FRR config and reload the daemons.
Activate the exact pending config, not arbitrary input.
Write the staged configuration to the lab router after confirmation.
Commit the dry run that was prepared earlier.

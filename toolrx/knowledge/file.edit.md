# Edit file tool

Prepares a change to a file inside the sandbox: it shows a dry-run diff of
what would change and holds it for the operator to confirm before anything
is written. Nothing is written until the operator presses Apply in the UI;
an existing file is backed up and can be undone.
Use this when the user wants to write, create, edit, save, update, change,
or append to a file. The target path comes first, then the new contents,
for example "write to notes.txt: hello world" or "create README.md: # Hi".
Read the contents of the change (the diff) before applying. It never writes
on its own.

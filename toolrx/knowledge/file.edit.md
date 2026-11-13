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

Longer requests and phrasings:
Write the following text into a new file called notes dot txt.
Edit the file readme.md and replace its contents with this paragraph.
Save this message into config.json as the new file contents.
Create a file on disk containing the text after the colon.
Update the file with the new body and show a dry run diff first.
Append this paragraph to the existing file and hold it for confirmation.
Prepare a write to a sandbox path, backed up and undoable.
Put this content into a specific file and let me confirm before it applies.

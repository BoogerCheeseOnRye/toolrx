# Read file tool

Opens one specific text file on disk and returns its contents.
Use this when the user asks to show, read, view, dump, cat, open, or print
the contents of a single file, for example "read my notes.txt", "show the
config file", "cat the changelog file", "show the contents of builder.py",
or "open index.html".
The target is a specific file with a name and an extension (.py, .txt, .md,
.html, .json...), not a folder. Reads UTF-8 text and prints it verbatim.

Picking between this and list_dir: if the user wants a specific file's text
contents ("show contents of X", "open X", "read X", "dump X"), use THIS tool.
Only use list_dir when they want the NAMES of the files inside a folder, or
say "list the files" / "what's in this directory".

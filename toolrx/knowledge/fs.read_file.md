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

Longer requests and phrasings:
Open one named text file and show me what is written inside it.
Print the full contents of the file called report.md.
Display the text stored in a single document with a name and extension.
I want to inspect one specific file, not a folder or a list of names.
Show me the exact text inside config.json, verbatim.
Read the body of the changelog file and return everything it contains.
What does the file notes.txt say? Print its contents.
Open readme.md and dump the text so I can review it.

A named file can sit inside a folder, but the request is still about that one
file: return only the text of the named file. Do not print a directory listing
and do not combine it with other files when the user asks what is inside one
specific document. "Contents of the file X" means read X itself, wherever the
folder is. The response is the file body verbatim, not the names around it.

When the request names a file and also mentions the folder it lives in, such as
the contents of the file report.md that is in this folder, read that file. The
folder is only its location. Show the contents of the file X located in this
directory, read the file X inside the folder, and what is inside the named file
in the folder all mean read one file's text.

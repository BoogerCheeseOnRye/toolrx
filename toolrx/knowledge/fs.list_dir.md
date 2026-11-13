# List directory tool

Shows the names of the files and the folder and sub-folder contents inside
a directory on disk.
Use this when a user wants to list, browse, show, or see what is inside a
folder or directory, like "list the files", "list the files on the device",
"what's in this directory", "show me the folder contents", "show the files
on this device". Returns the NAMES of the entries, one per line, directories
ending with a slash. This shows the folder's contents, not the text inside a
file. If the user names one specific file and wants its text, use read_file.

Longer requests and phrasings:
List every file and folder inside this directory for me.
I want to see the names of the entries in the current folder.
Show me what is in this directory, including its sub folders.
Browse the projects folder and tell me what files are sitting in it.
Give me a directory listing with one entry per line.
What files and directories exist under this path?
Show the names of the files on this device, not their contents.
List the folder contents and mark directories with a slash.
Bare listing requests are the common case: list the files, list files, list
the folder, show the files, show the file names, give me the file names, what
files are here, and show me what is in this folder. These ask for names and
entries, not for the text inside any file. When no all or every word is
present, a plain list the files request is this directory listing tool.

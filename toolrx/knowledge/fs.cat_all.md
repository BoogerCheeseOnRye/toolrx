# Dump all files tool

Prints the text contents of EVERY text file in the project, one after
another, each with a ==== path ==== header. This is a bulk read: it dumps
the whole codebase at once instead of one specific file.
Use this when the user asks to "list contents of every file", "show contents
of each file", "read all the files", "dump every file", "print the contents
of all files", or "cat all the files". Read-only tool; never writes.
It skips binary files and only shows text files inside the sandbox.

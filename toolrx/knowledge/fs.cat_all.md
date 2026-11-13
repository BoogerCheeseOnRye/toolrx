# Dump all files tool

Prints the text contents of EVERY text file in the project, one after
another, each with a ==== path ==== header. This is a bulk read: it dumps
the whole codebase at once instead of one specific file.
Use this when the user asks to "show contents of every file", "show contents
of each file", "read all the files", "dump every file", "print the contents
of all files", or "cat all the files". Read-only tool; never writes.
It skips binary files and only shows text files inside the sandbox.

Longer requests and phrasings:
Dump the text of every text file in the workspace at once.
Print the contents of all the files, one after another.
Read every readable text file and show me the whole codebase.
Give me a bulk dump of each file with a path header.
Concatenate all text files in the sandbox and return the result.
Show me all files and their contents in one combined output.
Cat every text file inside this project.
Print the entire set of file contents, not just one file.

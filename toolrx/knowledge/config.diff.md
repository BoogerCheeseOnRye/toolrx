# Config diff tool

Compares a current configuration file against a proposed one and shows
exactly what differs between them, so you can review a change before you
apply it manually.
Use this when the user wants to compare a current config against a proposed
version, show the diff, or review what would change. Needs a pair of file
paths to compare, like "compare builder.py with cli.py", "diff two files",
"show the differences between X and Y", or "what changed between these
files". This tool is dry run only and never writes, edits, or
changes any file on disk. Read-only tool.
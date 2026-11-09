# Run tool on interval module

Starts a live module that runs another tool over and over at a set interval,
pinning the latest output in the chat.
Use this when the user wants something done repeatedly or on a schedule:
"check the disk every 10 seconds", "ping every 5 seconds", "run this every
30s", "set it to do stuff in intervals", "watch the network in intervals".
Optionally set how long it keeps running before stopping: "for 10 minutes",
"for 600 seconds".
Read-only: only read-only tools may be run this way, and it never mutates.

# Run tool on interval module

Starts a live module that runs another tool over and over at a set interval,
pinning the latest output in the chat.
Use this when the user wants something done repeatedly or on a schedule:
"check the disk every 10 seconds", "ping every 5 seconds", "run this every
30s", "set it to do stuff in intervals", "watch the network in intervals".
Optionally set how long it keeps running before stopping: "for 10 minutes",
"for 600 seconds".
Read-only: only read-only tools may be run this way, and it never mutates.

Longer requests and phrasings:
Run the disk tool repeatedly every ten seconds until I stop it.
Start a repeated background run of the uptime check on an interval.
Keep running the memory status tool every five seconds in a loop.
Schedule a read only tool to run again and again with a delay.
Execute this tool periodically and pin the latest output.
Repeat the network check every thirty seconds for ten minutes.
Loop the disk reading and refresh it on a schedule.
Run another read only tool on a timer and show the newest result.

A run request executes another read only tool again and again on a timer. Look
for check repeatedly, have it check again and again, run this tool on a
repeating interval, loop the check, schedule the tool to execute every few
seconds, or monitor a value by rerunning a tool on a schedule. The output is
the latest result of that repeated tool, not a fixed system value widget.

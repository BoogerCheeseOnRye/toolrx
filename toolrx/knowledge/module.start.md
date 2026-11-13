# Start live module tool

Starts a live, pinned monitoring module that tracks a system value and
updates automatically. A module is a small widget pinned in the chat that
refreshes every few seconds with fresh data.
Use this when the user asks to track, watch, or monitor something live,
like "track memory live", "watch disk usage", "monitor memory", "live memory
reading", or "keep an eye on disk space". Optionally set how often it
updates: "update every 5 seconds", "refresh every 10s". Optionally set how
long it runs and then stops: "for 10 minutes", "for 600 seconds", "run for
half a minute".
Read-only monitor; never mutates anything.

Longer requests and phrasings:
Start a memory monitor that refreshes every five seconds.
Begin a background watcher for disk usage and keep it running.
Launch an uptime monitor that updates on an interval.
Create a live widget that tracks a system value and pins it in chat.
Watch memory usage and refresh the reading automatically.
Monitor disk space live and stop after ten minutes.
Start a periodic tracker for one system metric.
Keep an eye on uptime with a refreshing pinned monitor.

A start request creates one live monitor widget for a system value: memory,
disk, or uptime. It is about the monitor itself, pinned and refreshing, not
about running an arbitrary tool on a schedule. Phrases like start a monitor,
launch a live tracker, watch memory, keep an eye on disk, create a refreshing
widget, or monitor uptime belong here.

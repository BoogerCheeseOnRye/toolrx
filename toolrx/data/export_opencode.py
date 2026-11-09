#!/usr/bin/env python3
"""Extract opencode conversation history into a clean, reusable agentic-tool corpus.

Reads the sqlite db at ~/.local/share/opencode/opencode.db and emits JSONL where each
record is one session's message stream in order, with parts flattened. Tool calls are
normalized to {tool, input, output} so they pair naturally with schema-constrained
generation (Needle-style).

Output is written only to the local disk (toolrx/data/). The source data is the user's
own private project history and may contain sensitive material; keep it local.
"""
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    "~/.local/share/opencode/opencode.db")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "corpus.jsonl")
STATS = os.path.join(HERE, "corpus_stats.json")


def _safe(data):
    return data if isinstance(data, str) else ""


def main():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row

    # messages: id, session_id, time_created, data
    msgs = {
        m["id"]: m
        for m in c.execute("select id, session_id, time_created, data from message")
    }
    # parts: id, message_id, session_id, time_created, data
    parts_by_msg = {}
    for p in c.execute("select id, message_id, time_created, data from part"):
        parts_by_msg.setdefault(p["message_id"], []).append(p)

    sessions = {}
    for mid, m in msgs.items():
        sid = m["session_id"]
        sessions.setdefault(sid, []).append((m["time_created"] or 0, mid, m["data"]))

    n_sessions = n_msgs = n_tool = n_char = 0
    with open(OUT, "w") as fh:
        for sid in sorted(sessions):
            ordered = sorted(sessions[sid], key=lambda t: t[0])
            stream = []
            last_ts = 0
            for ts, mid, mdata in ordered:
                try:
                    role = json.loads(mdata).get("role")
                except Exception:
                    role = "unknown"
                msg_parts = sorted(parts_by_msg.get(mid, []), key=lambda p: p["time_created"] or 0)
                flat = []
                for p in msg_parts:
                    try:
                        d = json.loads(p["data"])
                    except Exception:
                        continue
                    ttype = d.get("type")
                    if ttype == "text":
                        flat.append({"type": "text", "text": _safe(d.get("text"))})
                    elif ttype == "tool":
                        st = d.get("state", {}) or {}
                        flat.append({
                            "type": "tool",
                            "tool": _safe(d.get("tool")),
                            "input": st.get("input", ""),
                            "output": st.get("output", ""),
                        })
                        n_tool += 1
                    elif ttype == "reasoning":
                        flat.append({"type": "reasoning", "reasoning": _safe(d.get("text"))})
                    # step-start / step-finish / compaction dropped (noise)
                stream.append({"role": role, "parts": flat})
                last_ts = max(last_ts, ts or 0)
            raw = json.dumps(stream, ensure_ascii=False)
            n_char += len(raw)
            rec = {"session": sid, "n_parts": len(stream), "stream": stream}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_sessions += 1
            n_msgs += len(ordered)

    stats = {
        "sessions": n_sessions,
        "messages": n_msgs,
        "tool_calls": n_tool,
        "chars": n_char,
        "approx_tokens": n_char // 4,
        "out": OUT,
    }
    with open(STATS, "w") as fh:
        fh.write(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
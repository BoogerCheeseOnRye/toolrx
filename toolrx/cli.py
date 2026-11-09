#!/usr/bin/env python3
"""toolrx CLI.

Usage:
    python3 cli.py build [catalog.json]
    python3 cli.py call "<natural language query>"
    python3 cli.py bench
"""

import json
import os
import sys

import router


def _model_path(base):
    return os.path.join(base, "micro_model.json")


def cmd_build(catalog):
    import builder
    builder.build(catalog)


def cmd_call(query):
    base = os.path.dirname(os.path.abspath(__file__))
    m = router.load(_model_path(base))
    decision = router.route(query, m)
    if decision["confidence"] <= 0.12 and decision["margin"] < 0.01:
        print(f"no confident tool for {query!r} (scores={decision['scores']})")
        return

    import executor
    res = executor.execute(decision, m["tools"])
    print(json.dumps(decision, indent=2))
    print(json.dumps(res, indent=2)[:2000])


def cmd_bench():
    base = os.path.dirname(os.path.abspath(__file__))
    m = router.load(_model_path(base))
    cases = [
        "add five and seven",
        "sum 3 4 9",
        "read my notes.txt",
        "cat the changelog",
        "how much memory is free",
        "whats the ram usage",
        "list the files",
        "show the folder contents",
        "order a pizza",
    ]
    for q in cases:
        r = router.route(q, m)
        flag = "OK " if (r["confidence"] > 0.12 or (r["margin"] >= 0.005 and r["confidence"] > 0.05)) else "?? "
        print(f"{flag}{q!r:38} -> {r['tool']:16} conf={r['confidence']:.3f} margin={r['margin']:.3f}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "build":
        cmd_build(sys.argv[2] if len(sys.argv) > 2 else "catalog.json")
    elif cmd == "call":
        cmd_call(sys.argv[2])
    elif cmd == "bench":
        cmd_bench()
    else:
        print(f"unknown command: {cmd}")


if __name__ == "__main__":
    main()
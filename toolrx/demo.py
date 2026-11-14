#!/usr/bin/env python3
"""Step 45: one offline end-to-end demo, measured and reproducible.

`toolrx/demo_harness.js` drives the real browser modules in Node with a fake
catalog fetch, no server, no browser, and no model. This script runs it, prints
a human transcript with the measured timings, and maintains the checked-in
`toolrx/demo_report.json`.

    python3 toolrx/demo.py            # run and print the transcript
    python3 toolrx/demo.py --write    # refresh demo_report.json
    python3 toolrx/demo.py --check    # fail if the report drifted

The checked-in report normalizes `at` and `ms` fields (and the build line's
elapsed milliseconds) so it is byte-for-byte reproducible; the default run
prints the measured numbers instead.
"""

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HARNESS = os.path.join(HERE, "demo_harness.js")
REQUEST = os.path.join(HERE, "demo_request.txt")
REPORT = os.path.join(HERE, "demo_report.json")
COMMANDS = os.path.join(HERE, "web", "commands.json")
SKILLS = os.path.join(HERE, "web", "skills.js")
LIMITS = os.path.join(HERE, "limits.json")

BUILD_MS = re.compile(r"(build · \d+ chars · ~\d+ tokens · )\d+ ms")


def run_harness():
    node = shutil.which("node")
    if not node:
        raise SystemExit("node is required for the demo harness")
    proc = subprocess.run(
        [node, HARNESS, COMMANDS, SKILLS, REQUEST],
        capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr[-4000:] or proc.stdout[-4000:])
    return json.loads(proc.stdout)


def _walk_zero_timings(node):
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key == "at":
                node[key] = 0
            elif key == "ms" and isinstance(value, (int, float)):
                node[key] = 0
            else:
                _walk_zero_timings(value)
    elif isinstance(node, list):
        for item in node:
            _walk_zero_timings(item)


def normalize(raw):
    """Strip the measured timings and re-pin every step text byte."""
    doc = copy.deepcopy(raw)
    doc["timings"] = ("normalized for the checked-in report (at = 0, ms = 0); "
                      "run without --write for measured timings")
    for step in doc.get("steps", []):
        step["text"] = BUILD_MS.sub(r"\g<1>0 ms", step["text"])
        body = step["text"].encode("utf-8")
        step["bytes"] = len(body)
        step["sha"] = hashlib.sha256(body).hexdigest()
    _walk_zero_timings(doc)
    run = doc.get("run") or {}
    budget = run.get("budget") or {}
    ms = budget.get("ms")
    if isinstance(ms, dict):
        ms["used"] = 0
        ms["remaining"] = ms.get("max", 0)
    run["emitted"] = sum(step["bytes"] for step in doc.get("steps", []))
    return doc


def load_report():
    with open(REPORT, encoding="utf-8") as fh:
        return json.load(fh)


def write_report(doc):
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def compare(expected, actual):
    """Return a short list of the first differences between two reports."""
    problems = []
    if expected == actual:
        return problems

    def walk(a, b, path=""):
        if len(problems) >= 8:
            return
        if type(a) is not type(b):
            problems.append(f"{path}: {type(a).__name__} != {type(b).__name__}")
            return
        if isinstance(a, dict):
            for key in sorted(set(a) | set(b)):
                if key not in a:
                    problems.append(f"{path}/{key}: missing from the checked-in report")
                elif key not in b:
                    problems.append(f"{path}/{key}: missing from the fresh run")
                else:
                    walk(a[key], b[key], f"{path}/{key}")
        elif isinstance(a, list):
            if len(a) != len(b):
                problems.append(f"{path}: {len(a)} items != {len(b)} items")
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, f"{path}/{i}")
        elif a != b:
            problems.append(f"{path}: {a!r} != {b!r}")

    walk(expected, actual)
    return problems


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else str(n)


def transcript(doc):
    run = doc["run"]
    plan = doc["plan"]
    budget = plan["budget"]
    project = doc["project"]
    lines = []
    lines.append("toolrx end-to-end demo · offline · no model")
    lines.append(
        f"request  {os.path.basename(REQUEST)} · {fmt(doc['request']['chars'])} chars"
        f" · {doc['request']['steps']} steps · sha {doc['request']['sha256'][:12]}…")
    lines.append(
        f"plan     {plan['steps']}/{budget['maxSteps']} steps"
        f" · {fmt(plan['chars'])}/{fmt(budget['maxChars'])} chars"
        f" · worst case {fmt(budget['worstCaseMs'])}/{fmt(budget['planMs'])} ms"
        f" · {'fits' if budget['fits'] else 'does not fit'}")
    lines.append(
        f"run      {run['steps']} steps · {run['failed']} failed"
        f" · {run['files']} files · {fmt(run['bytes'])} project bytes"
        f" · {fmt(run['written'])} written · {fmt(run['ms'])} ms measured")
    lines.append(f"catalog  {fmt(doc['catalog'])} deterministic commands")
    lines.append("")
    for step in doc["steps"]:
        mark = "✗" if step["error"] else "✓"
        via = (step["via"] or "?")[:20]
        lines.append(
            f"{step['n']:>2} {mark} {via:<20} {fmt(step['bytes']):>7} B  "
            f"{step['ms']:>4} ms  {step['step'][:64]}")
    lines.append("")
    lines.append(
        "decisions exact commands carry no confidence score; "
        "confidence and margin stay null in the report")
    lines.append("")
    lines.append(
        f"project  {project['name']} ({project['slug']}) · {project['kind']}"
        f" · {len(project['files'])} files"
        f" · {sum(f['bytes'] for f in project['files'])} bytes")
    systems = [f["name"] for f in project["files"] if f["name"].startswith("systems/")]
    modules = [f["name"] for f in project["files"]
               if "/" in f["name"] and not f["name"].startswith("systems/")]
    lines.append(f"systems  {len(systems)} · " + ", ".join(
        name.split("/")[-1][:-3] for name in systems))
    lines.append(f"modules  {len(modules)} · " + ", ".join(modules))
    lines.append("")
    ctx = doc["context"]["snapshot"].splitlines()
    lines.append("context  " + (ctx[1] if len(ctx) > 1 else "unavailable"))
    lines.append("         " + (ctx[2] if len(ctx) > 2 else ""))
    expand = doc["continuation"]["expand"]
    cont = doc["continuation"]["continue"]
    undo = doc["undo"]
    lines.append(
        f"expand   {expand['via']} · {expand['plan']['steps']} steps"
        f" · {expand['plan']['pending']} pending"
        f" · {', '.join(expand['plan']['pendingSteps'])}")
    lines.append(
        f"continue {cont['via']} · {cont['plan']['done']}/{cont['plan']['steps']} done"
        f" · {cont['plan']['pending']} pending"
        f" · touched {', '.join(cont['filesTouched'])}")
    lines.append(
        f"undo     {undo['via']} · {'exact' if undo['exact'] else 'DRIFT'}"
        f" · restored {', '.join(undo['filesRestored'])}")
    lines.append("")
    rb = run["budget"]
    lines.append(
        f"headroom files {rb['files']['used']}/{rb['files']['max']}"
        f" · bytes {fmt(rb['bytes']['used'])}/{fmt(rb['bytes']['max'])}"
        f" · steps {rb['steps']['used']}/{rb['steps']['max']}"
        f" · chars {fmt(rb['chars']['used'])}/{fmt(rb['chars']['max'])}"
        f" · context {fmt(rb['context']['used'])}/{fmt(rb['context']['max'])}")
    lines.append(
        "limits   " + " · ".join(
            f"{key} {fmt(value)}" for key, value in doc["limits"].items()
            if key in ("singleChars", "planChars", "planSteps", "stepMs", "planMs",
                       "projectBytes", "contextBytes", "extractChars")))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh the checked-in demo_report.json")
    group.add_argument("--check", action="store_true",
                       help="fail if the checked-in report drifted")
    parser.add_argument("--json", action="store_true",
                        help="print the normalized report instead of the transcript")
    args = parser.parse_args(argv)

    raw = run_harness()
    doc = normalize(raw)

    if args.json:
        print(json.dumps(doc, indent=2, ensure_ascii=False))
        return 0

    if args.write:
        write_report(doc)
        print(f"wrote {os.path.relpath(REPORT, ROOT)} "
              f"({os.path.getsize(REPORT):,} bytes)")
        return 0

    if args.check:
        if not os.path.exists(REPORT):
            print(f"missing {os.path.relpath(REPORT, ROOT)}; run --write", file=sys.stderr)
            return 1
        problems = compare(load_report(), doc)
        if problems:
            print("demo report drifted; run python3 toolrx/demo.py --write",
                  file=sys.stderr)
            for problem in problems:
                print("  " + problem, file=sys.stderr)
            return 1
        print("demo report is current")
        return 0

    print(transcript(raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())

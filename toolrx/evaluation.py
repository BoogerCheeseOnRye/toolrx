#!/usr/bin/env python3
"""Step 69: a public evaluation suite and comparison kit.

`toolrx/evaluation.json` is the only place the measured numbers are written.
This script derives every number from the repository, drives the real browser
modules in Node through `toolrx/evaluation_harness.js`, and keeps one Markdown
block in `README.md` and `COMPARISON.md` and one HTML block in
`docs/pitch.html` byte-identical to the report.

    python3 toolrx/evaluation.py --write   # refresh the report and the blocks
    python3 toolrx/evaluation.py --check   # fail if a number or block drifted

The harness runs each measured program twice, counts a mismatch instead of
trusting a fixture, and proves that no fetch happens after module init. The
report refuses to be written when determinism, the zero-network rule, or the
demo build's own budget checks fail.

No route, command, cap, or allow-listed tool is added. Nothing here calls a
model or touches the network; the fake fetch only reads local files.
"""

import argparse
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
COVERAGE = ROOT / "coverage.json"
DEMO = ROOT / "demo_report.json"
HARNESS = ROOT / "evaluation_harness.js"
COMMANDS = ROOT / "web" / "commands.json"
MODEL = ROOT / "micro_model.json"
REPORT = ROOT / "evaluation.json"
README = REPO / "README.md"
COMPARISON = REPO / "COMPARISON.md"
PITCH = REPO / "docs" / "pitch.html"

BLOCK_START = "<!-- evaluation:start -->"
BLOCK_END = "<!-- evaluation:end -->"
LANES = ("exact", "router", "fallback", "refusal")

sys.path.insert(0, str(ROOT))
import scorecard  # noqa: E402  (same directory; one source for the counts)


def _fail(message):
    raise ValueError("evaluation: " + message)


def _int(value, where):
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(where + " must be an integer")
    if value < 0:
        _fail(where + " must not be negative")
    return value


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _fail("missing source: " + str(path.relative_to(REPO)))
    except json.JSONDecodeError as error:
        _fail("invalid JSON in " + str(path.relative_to(REPO)) + ": "
              + str(error))


def run_harness():
    """Drive the real browser modules twice and return the measured report."""
    node = shutil.which("node")
    if not node:
        _fail("node is required to run the evaluation harness")
    proc = subprocess.run(
        [node, str(HARNESS), str(ROOT / "web"), str(COMMANDS), str(MODEL)],
        cwd=str(REPO), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        _fail("harness failed: " + (proc.stderr.strip() or "no output"))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as error:
        _fail("harness did not print JSON: " + str(error))


def _lanes(entry, where):
    raw = entry.get("lanes")
    if not isinstance(raw, dict):
        _fail(where + ".lanes must be an object")
    return {key: _int(raw.get(key, 0), where + ".lanes." + key) for key in LANES}


def build_report():
    """Read the checked-in reports, run the harness, and return the document."""
    coverage = _load(COVERAGE)
    fixtures = coverage.get("fixtures")
    if not isinstance(fixtures, dict) or not fixtures:
        _fail("coverage.json has no fixtures")
    for name in ("everyday", "routing"):
        if not isinstance(fixtures.get(name), dict):
            _fail("coverage.json is missing fixtures." + name)
    demo = _load(DEMO)
    harness = run_harness()
    metrics = scorecard.metrics()

    lanes = {
        "everyday": _lanes(fixtures["everyday"], "fixtures.everyday"),
        "routing": _lanes(fixtures["routing"], "fixtures.routing"),
    }
    total = {key: 0 for key in LANES}
    for name, entry in fixtures.items():
        for key, value in _lanes(entry, "fixtures." + name).items():
            total[key] += value
    lanes["fixtures"] = total

    plan = demo.get("plan") or {}
    run = demo.get("run") or {}
    budget = run.get("budget") or {}
    steps = budget.get("steps") or {}
    files = budget.get("files") or {}
    context = budget.get("context") or {}
    build = {
        "requestChars": _int(plan.get("chars"), "plan.chars"),
        "planSteps": _int(plan.get("steps"), "plan.steps"),
        "maxSteps": _int(steps.get("max"), "run.budget.steps.max"),
        "executed": _int(run.get("executed"), "run.executed"),
        "failed": _int(run.get("failed"), "run.failed"),
        "files": _int(run.get("files"), "run.files"),
        "maxFiles": _int(files.get("max"), "run.budget.files.max"),
        "bytes": _int(run.get("bytes"), "run.bytes"),
        "contextUsed": _int(context.get("used"), "run.budget.context.used"),
        "contextMax": _int(context.get("max"), "run.budget.context.max"),
        "undo": _int(run.get("undo"), "run.undo"),
        "within": bool(budget.get("within")),
        "over": list(budget.get("over") or []),
    }

    thinking = harness["thinking"]
    repair = harness["repair"]
    rewrite = harness["rewrite"]
    compaction = harness["compaction"]
    programs = thinking["states"] + repair["states"] + rewrite["cases"] + 1
    identical = (
        thinking["deterministic"]
        + repair["deterministic"]
        + (rewrite["cases"] if rewrite["identical"] else 0)
        + (1 if compaction["identical"] else 0)
    )

    return {
        "version": 1,
        "metrics": metrics,
        "lanes": lanes,
        "build": build,
        "determinism": {"programs": programs, "identical": identical},
        "harness": harness,
        "network": harness["network"],
    }


def validate(doc):
    if not isinstance(doc, dict):
        _fail("the report must be an object")
    if doc.get("version") != 1:
        _fail("version must be 1")

    metrics = doc.get("metrics")
    if not isinstance(metrics, dict):
        _fail("metrics must be an object")
    for key in ("catalog", "tests", "caps", "everyday", "routing", "fixtures"):
        _int(metrics.get(key), "metrics." + key)
    if not metrics["catalog"] or not metrics["tests"] or not metrics["caps"]:
        _fail("catalog, tests, and caps must all be positive")

    lanes = doc.get("lanes")
    if not isinstance(lanes, dict):
        _fail("lanes must be an object")
    for name in ("everyday", "routing", "fixtures"):
        entry = lanes.get(name)
        if not isinstance(entry, dict):
            _fail("lanes." + name + " must be an object")
        for key in LANES:
            _int(entry.get(key), "lanes." + name + "." + key)
    if sum(lanes["fixtures"].values()) <= 0:
        _fail("lanes.fixtures must measure at least one case")

    build = doc.get("build")
    if not isinstance(build, dict):
        _fail("build must be an object")
    for key in ("requestChars", "planSteps", "maxSteps", "executed", "failed",
                "files", "maxFiles", "bytes", "contextUsed", "contextMax",
                "undo"):
        _int(build.get(key), "build." + key)
    if build["failed"] != 0:
        _fail("the demo build must have no failed steps")
    if not build["within"] or build["over"]:
        _fail("the demo build must stay inside every budget")
    if build["executed"] != build["planSteps"]:
        _fail("the demo build must execute every planned step")
    if build["planSteps"] > build["maxSteps"] or build["files"] > build["maxFiles"]:
        _fail("the demo build must stay under the step and file caps")
    if build["contextUsed"] > build["contextMax"]:
        _fail("the demo build must stay inside the context cap")

    determinism = doc.get("determinism")
    if not isinstance(determinism, dict):
        _fail("determinism must be an object")
    _int(determinism.get("programs"), "determinism.programs")
    _int(determinism.get("identical"), "determinism.identical")
    if determinism["programs"] <= 0:
        _fail("determinism must measure at least one program")
    if determinism["identical"] != determinism["programs"]:
        _fail("every repeated program must be byte-identical")

    harness = doc.get("harness")
    if not isinstance(harness, dict):
        _fail("harness must be an object")
    for name in ("thinking", "repair"):
        entry = harness.get(name)
        if not isinstance(entry, dict):
            _fail("harness." + name + " must be an object")
        _int(entry.get("states"), "harness." + name + ".states")
        _int(entry.get("deterministic"), "harness." + name + ".deterministic")
        _int(entry.get("mismatches"), "harness." + name + ".mismatches")
        if entry["deterministic"] != entry["states"] or entry["mismatches"]:
            _fail("harness." + name + " must be deterministic")
    rewrite = harness.get("rewrite")
    if not isinstance(rewrite, dict) or rewrite.get("identical") is not True:
        _fail("harness.rewrite must be identical on a second run")
    _int(rewrite.get("cases"), "harness.rewrite.cases")
    _int(rewrite.get("refusals"), "harness.rewrite.refusals")
    compaction = harness.get("compaction")
    if not isinstance(compaction, dict) or compaction.get("identical") is not True:
        _fail("harness.compaction must be identical on a second run")
    _int(compaction.get("runs"), "harness.compaction.runs")
    if compaction["runs"] < 2:
        _fail("harness.compaction must run at least twice")

    if doc.get("network") != 0:
        _fail("measured network calls after init must be zero")
    if harness.get("network") != 0:
        _fail("the harness must report zero network calls after init")
    return doc


def _fmt(value):
    return f"{value:,}"


def _lane_text(lane):
    return " · ".join(_fmt(lane[key]) + " " + key for key in LANES)


def render_markdown(doc):
    m = doc["metrics"]
    lanes = doc["lanes"]
    build = doc["build"]
    det = doc["determinism"]
    harness = doc["harness"]
    rows = [
        "**Reach**",
        "",
        "| Measure | Result |",
        "| --- | --- |",
        f"| Commands in the catalog | {_fmt(m['catalog'])} |",
        f"| Named caps | {m['caps']} |",
        f"| Everyday cases | {_lane_text(lanes['everyday'])} "
        f"({_fmt(m['everyday'])} total) |",
        f"| Router cases | {_lane_text(lanes['routing'])} "
        f"({_fmt(m['routing'])} total) |",
        f"| Fixture cases | {_lane_text(lanes['fixtures'])} "
        f"({_fmt(m['fixtures'])} total) |",
        "",
        f"**Determinism** — {det['identical']} of {det['programs']} repeated "
        "programs produced byte-identical output.",
        "",
        "| Program | Runs | Identical |",
        "| --- | --- | --- |",
        f"| Thinking modes | {harness['thinking']['states']} | "
        f"{harness['thinking']['deterministic']} |",
        f"| Repair rules | {harness['repair']['states']} | "
        f"{harness['repair']['deterministic']} |",
        f"| Plan rewrites | {harness['rewrite']['cases']} | "
        f"{harness['rewrite']['cases'] if harness['rewrite']['identical'] else 0} |",
        f"| Context compactions | {harness['compaction']['runs']} | "
        f"{'yes' if harness['compaction']['identical'] else 'no'} |",
        "",
        "**One end-to-end build**",
        "",
        "| Measure | Result |",
        "| --- | --- |",
        f"| Request | {_fmt(build['requestChars'])} characters |",
        f"| Plan steps | {build['planSteps']} / {build['maxSteps']} |",
        f"| Executed steps | {build['executed']} |",
        f"| Failed steps | {build['failed']} |",
        f"| Files written | {build['files']} / {build['maxFiles']} |",
        f"| Project bytes | {_fmt(build['bytes'])} |",
        f"| Context stored | {_fmt(build['contextUsed'])} / "
        f"{_fmt(build['contextMax'])} bytes |",
        f"| Undo depth | {build['undo']} |",
        f"| Network calls after init | {doc['network']} |",
    ]
    return "\n".join(rows)


def render_html(doc):
    m = doc["metrics"]
    lanes = doc["lanes"]
    build = doc["build"]
    det = doc["determinism"]
    harness = doc["harness"]
    rows = [
        '<div class="row"><span class="tag done">measured</span><p>'
        f"<b>Reach.</b> {_fmt(m['catalog'])} commands, {m['caps']} named caps, "
        f"{_fmt(lanes['everyday']['exact'])} / {_fmt(m['everyday'])} everyday "
        f"phrases exact, {_fmt(lanes['routing']['router'])} / "
        f"{_fmt(m['routing'])} router cases, {_fmt(m['fixtures'])} fixture "
        f"cases ({html.escape(_lane_text(lanes['fixtures']))}).</p></div>",
        '<div class="row"><span class="tag done">measured</span><p>'
        f"<b>Determinism.</b> {det['identical']} of {det['programs']} repeated "
        "programs byte-identical: "
        f"thinking {harness['thinking']['deterministic']} / "
        f"{harness['thinking']['states']}, "
        f"repair {harness['repair']['deterministic']} / "
        f"{harness['repair']['states']}, "
        f"rewrite {harness['rewrite']['cases']} / "
        f"{harness['rewrite']['cases']}, "
        f"compaction {harness['compaction']['runs']} runs.</p></div>",
        '<div class="row"><span class="tag done">measured</span><p>'
        f"<b>One build.</b> {build['planSteps']} / {build['maxSteps']} steps, "
        f"{build['files']} / {build['maxFiles']} files, "
        f"{_fmt(build['bytes'])} project bytes, {build['failed']} failed, "
        f"context {_fmt(build['contextUsed'])} / {_fmt(build['contextMax'])} "
        f"bytes, undo depth {build['undo']}, {doc['network']} network calls "
        "after init.</p></div>",
        '<p class="note"><b>Evaluation report: '
        '<code>toolrx/evaluation.json</code> · reproduce with '
        '<code>python3 toolrx/evaluation.py --write</code> · '
        '<a href="https://github.com/BoogerCheeseOnRye/toolrx/blob/main/'
        'COMPARISON.md">read the honest comparison</a>.</b></p>',
    ]
    return "\n".join(rows)


def _replace_block(text, start, end, body, where):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    found = pattern.findall(text)
    if len(found) != 1:
        _fail("%s needs exactly one %s ... %s block" % (where, start, end))
    return pattern.sub(lambda _match: start + "\n" + body + "\n" + end,
                       text, count=1)


def rendered(doc):
    """Return {path: new text} for every file that quotes the report."""
    markdown = render_markdown(doc)
    readme = _replace_block(README.read_text(encoding="utf-8"),
                            BLOCK_START, BLOCK_END, markdown, "README.md")
    comparison = _replace_block(COMPARISON.read_text(encoding="utf-8"),
                                BLOCK_START, BLOCK_END, markdown,
                                "COMPARISON.md")
    pitch = _replace_block(PITCH.read_text(encoding="utf-8"),
                           BLOCK_START, BLOCK_END, render_html(doc),
                           "docs/pitch.html")
    return {README: readme, COMPARISON: comparison, PITCH: pitch}


def _display(path):
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _serialized(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def write(doc=None):
    doc = validate(doc or build_report())
    outputs = rendered(doc)
    REPORT.write_text(_serialized(doc), encoding="utf-8")
    print("wrote %s" % _display(REPORT))
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8")
        print("wrote %s" % _display(path))


def check(doc=None):
    doc = validate(doc or build_report())
    stale = []
    if REPORT.read_text(encoding="utf-8") != _serialized(doc):
        stale.append(_display(REPORT))
    for path, text in rendered(doc).items():
        if path.read_text(encoding="utf-8") != text:
            stale.append(_display(path))
    if stale:
        print("stale evaluation report or block in: " + ", ".join(stale)
              + "; run toolrx/evaluation.py --write", file=sys.stderr)
        return 1
    print("evaluation is current (%d measured programs, %d commands)"
          % (doc["determinism"]["programs"], doc["metrics"]["catalog"]))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh evaluation.json and the quoted blocks")
    group.add_argument("--check", action="store_true",
                       help="fail if a measured number or block drifted")
    args = parser.parse_args(argv)
    if args.write:
        write()
        return 0
    if args.check:
        return check()
    doc = validate(build_report())
    print(json.dumps(doc, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Step 59: a living LLM-parity scorecard.

`toolrx/scorecard.json` is the only place a capability claim is written. This
script derives every number it quotes from the repository, renders one Markdown
table and one HTML row list, and keeps the blocks in `README.md` and
`docs/pitch.html` byte-identical to the table. It also proves that each cited
evidence path exists and each cited test still exists, so a renamed test or a
drifted count fails instead of quietly leaving a stale claim.

    python3 toolrx/scorecard.py --write   # refresh the README and pitch blocks
    python3 toolrx/scorecard.py --check   # fail if any claim or block drifted

No route, command, or runtime limit is added; the checker only reads checked-in
files and never touches the network.
"""

import argparse
import ast
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
SCORECARD = ROOT / "scorecard.json"
COVERAGE = ROOT / "coverage.json"
LIMITS = ROOT / "limits.json"
README = REPO / "README.md"
PITCH = REPO / "docs" / "pitch.html"
TESTS = REPO / "tests"

STATUSES = ("shipped", "partial", "deferred")
TAGS = {"shipped": "done", "partial": "next", "deferred": "block"}
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TEST_RE = re.compile(r"^\s*def (test_\w+)\s*\(", re.M)

BLOCK_START = "<!-- scorecard:start -->"
BLOCK_END = "<!-- scorecard:end -->"
CATALOG_START = "<!-- scorecard:catalog:start -->"
CATALOG_END = "<!-- scorecard:catalog:end -->"
TESTS_START = "<!-- scorecard:tests:start -->"
TESTS_END = "<!-- scorecard:tests:end -->"


def _fail(message):
    raise ValueError("scorecard: " + message)


def load(path=SCORECARD):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def count_tests():
    """Count `def test_` in the checked-in suite, the same number a run reports."""
    return sum(len(TEST_RE.findall(p.read_text(encoding="utf-8")))
               for p in sorted(TESTS.glob("test_*.py")))


def test_index():
    """Map each test module to its `Class.method` and `function` names."""
    index = {}
    for path in sorted(TESTS.glob("test_*.py")):
        names = set()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        names.add(node.name + "." + item.name)
        index[path.name] = names
    return index


def metrics():
    """Every quoted number, read from the repository rather than stored twice."""
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    limits = json.loads(LIMITS.read_text(encoding="utf-8"))
    fixtures = coverage["fixtures"]
    return {
        "catalog": coverage["catalog"]["count"],
        "tests": count_tests(),
        "caps": len([key for key in limits if key != "version"]),
        "everyday": fixtures["everyday"]["cases"],
        "routing": fixtures["routing"]["cases"],
        "fixtures": sum(entry["cases"] for entry in fixtures.values()),
    }


def _text(value, where):
    if not isinstance(value, str) or not value.strip():
        _fail(where + " must be a non-empty string")
    return value.strip()


def _evidence(entry, where, index):
    if not isinstance(entry, dict):
        _fail(where + " must be an object")
    path = _text(entry.get("path"), where + ".path")
    target = REPO / path
    if not target.exists():
        _fail(where + " cites a missing path: " + path)
    test = entry.get("test")
    if test is None:
        return {"path": path, "test": None}
    test = _text(test, where + ".test")
    if not path.startswith("tests/") or not path.endswith(".py"):
        _fail(where + ".test must cite a tests/*.py file")
    names = index.get(pathlib.Path(path).name, set())
    if test not in names:
        _fail(where + " cites a missing test: " + path + "::" + test)
    return {"path": path, "test": test}


def validate(doc):
    if not isinstance(doc, dict):
        _fail("the table must be an object")
    if doc.get("version") != 1:
        _fail("version must be 1")
    capabilities = doc.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        _fail("capabilities must be a non-empty list")
    index = test_index()
    seen = set()
    out = []
    for position, raw in enumerate(capabilities):
        where = "capabilities[%d]" % position
        if not isinstance(raw, dict):
            _fail(where + " must be an object")
        cap_id = _text(raw.get("id"), where + ".id")
        if not ID_RE.match(cap_id):
            _fail(where + ".id must be a lowercase slug")
        if cap_id in seen:
            _fail("duplicate capability id: " + cap_id)
        seen.add(cap_id)
        status = _text(raw.get("status"), where + ".status")
        if status not in STATUSES:
            _fail(where + ".status must be one of " + ", ".join(STATUSES))
        evidence = raw.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            _fail(where + ".evidence must be a non-empty list")
        clean = [_evidence(item, where + ".evidence[%d]" % i, index)
                 for i, item in enumerate(evidence)]
        if status == "shipped" and not any(item["test"] for item in clean):
            _fail(where + " is shipped but cites no test")
        nxt = raw.get("next")
        if nxt is not None:
            nxt = _text(nxt, where + ".next")
        if status == "deferred" and not nxt:
            _fail(where + " is deferred but names no next move")
        out.append({
            "id": cap_id,
            "label": _text(raw.get("label"), where + ".label"),
            "status": status,
            "claim": _text(raw.get("claim"), where + ".claim"),
            "evidence": clean,
            "gap": _text(raw.get("gap"), where + ".gap"),
            "next": nxt,
        })
    return {"version": 1, "capabilities": out}


def _evidence_text(entry):
    return entry["path"] + ("::" + entry["test"] if entry["test"] else "")


def _metrics_line(m):
    return ("Scorecard metrics: %s commands · %s tests · %s named caps · "
            "%s everyday cases · %s router cases · %s fixture cases."
            % (f"{m['catalog']:,}", f"{m['tests']:,}", m["caps"],
               f"{m['everyday']:,}", f"{m['routing']:,}",
               f"{m['fixtures']:,}"))


def render_markdown(doc, m):
    rows = [
        "| Capability | Status | What ships | Evidence | Honest gap |",
        "| --- | --- | --- | --- | --- |",
    ]
    for cap in doc["capabilities"]:
        evidence = ", ".join("`%s`" % _evidence_text(e) for e in cap["evidence"])
        rows.append("| **%s** | %s | %s | %s | %s |" % (
            cap["label"].replace("|", "\\|"), cap["status"],
            cap["claim"].replace("|", "\\|"), evidence.replace("|", "\\|"),
            cap["gap"].replace("|", "\\|")))
    rows.append("")
    rows.append("_" + _metrics_line(m) + "_")
    return "\n".join(rows)


def render_html(doc, m):
    rows = []
    for cap in doc["capabilities"]:
        evidence = ", ".join(
            "<code>%s</code>" % html.escape(_evidence_text(e))
            for e in cap["evidence"])
        rows.append(
            '<div class="row"><span class="tag %s">%s</span><p><b>%s.</b> %s '
            '<em>Gap:</em> %s <span class="src">%s</span></p></div>'
            % (TAGS[cap["status"]], cap["status"],
               html.escape(cap["label"]), html.escape(cap["claim"]),
               html.escape(cap["gap"]), evidence))
    rows.append('<p class="note"><b>%s</b></p>'
                % html.escape(_metrics_line(m)))
    return "\n".join(rows)


def _replace_block(text, start, end, body, where):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    found = pattern.findall(text)
    if len(found) != 1:
        _fail("%s needs exactly one %s ... %s block" % (where, start, end))
    return pattern.sub(lambda _match: start + "\n" + body + "\n" + end,
                       text, count=1)


def _replace_inline(text, start, end, value, where):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        _fail("%s is missing an inline %s ... %s marker" % (where, start, end))
    return pattern.sub(lambda _match: start + value + end, text)


def rendered(doc, m):
    """Return {path: new text} for the two files that quote the scorecard."""
    readme = README.read_text(encoding="utf-8")
    readme = _replace_block(readme, BLOCK_START, BLOCK_END,
                            render_markdown(doc, m), "README.md")
    pitch = PITCH.read_text(encoding="utf-8")
    pitch = _replace_block(pitch, BLOCK_START, BLOCK_END,
                           render_html(doc, m), "docs/pitch.html")
    pitch = _replace_inline(pitch, CATALOG_START, CATALOG_END,
                            f"{m['catalog']:,}", "docs/pitch.html")
    pitch = _replace_inline(pitch, TESTS_START, TESTS_END,
                            f"{m['tests']:,}", "docs/pitch.html")
    return {README: readme, PITCH: pitch}


def _display(path):
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def write(doc=None, m=None):
    doc = validate(doc or load())
    m = m or metrics()
    for path, text in rendered(doc, m).items():
        path.write_text(text, encoding="utf-8")
        print("wrote %s" % _display(path))


def check(doc=None, m=None):
    doc = validate(doc or load())
    m = m or metrics()
    stale = []
    for path, text in rendered(doc, m).items():
        if path.read_text(encoding="utf-8") != text:
            stale.append(_display(path))
    if stale:
        print("stale scorecard block in: " + ", ".join(stale)
              + "; run toolrx/scorecard.py --write", file=sys.stderr)
        return 1
    print("scorecard is current (%d capabilities, %d tests)"
          % (len(doc["capabilities"]), m["tests"]))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh the README and pitch blocks")
    group.add_argument("--check", action="store_true",
                       help="fail if any claim or block drifted")
    args = parser.parse_args(argv)
    if args.write:
        write()
        return 0
    if args.check:
        return check()
    doc = validate(load())
    print(json.dumps({"capabilities": len(doc["capabilities"]),
                      "metrics": metrics()}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

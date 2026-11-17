#!/usr/bin/env python3
"""Deterministic repair routes (step 54).

One checked-in table, `toolrx/repair.json`, is the only source of the
`repair.plan` routes. It is expanded into catalog entries by
`toolrx/build_commands.py` and exported to `tests/fixtures/repair.json` so the
routes and the fixture cannot drift.

    python3 toolrx/repair.py --write   # refresh the fixture
    python3 toolrx/repair.py --check   # fail if the fixture drifted
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TABLE = ROOT / "repair.json"
FIXTURE = ROOT.parent / "tests" / "fixtures" / "repair.json"


def load(path=TABLE):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _fail(message):
    raise ValueError("repair table: " + message)


def _norm(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def _check_text(value, where):
    if not isinstance(value, str) or not value.strip():
        _fail(where + " must be a non-empty string")
    return value


def _phrases(table):
    if table.get("version") != 1:
        _fail("version must be 1")
    op = _check_text(table.get("op"), "op")
    if op != "repair.plan":
        _fail("op must be repair.plan, not %r" % op)
    summary = _check_text(table.get("summary"), "summary")
    example = _check_text(table.get("example"), "example")
    phrases = table.get("phrases")
    if not isinstance(phrases, list) or not phrases:
        _fail("phrases must be a non-empty list")
    out = []
    seen = {}
    for phrase in phrases:
        text = _check_text(phrase, "phrase")
        key = _norm(text)
        if key in seen:
            _fail("phrase %r already used" % text)
        seen[key] = True
        out.append(text)
    if example not in out:
        _fail("example %r must be one of the phrases" % example)
    return op, summary, example, out


def entries():
    """Unique catalog entries, in table order."""
    table = load()
    op, summary, _example, phrases = _phrases(table)
    for i, text in enumerate(phrases, 1):
        yield {
            "id": "repair.plan.%d" % i,
            "op": op,
            "re": "^" + re.escape(text) + "$",
            "args": {},
            "d": summary,
            "c": "repair",
            "text": text,
        }


def fixture():
    cases = [
        {"text": e["text"], "op": e["op"], "args": e["args"]}
        for e in entries()
    ]
    cases.sort(key=lambda c: c["text"])
    return {
        "version": 1,
        "count": len(cases),
        "op": "repair.plan",
        "cases": cases,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh tests/fixtures/repair.json")
    group.add_argument("--check", action="store_true",
                       help="fail if the fixture drifted")
    args = parser.parse_args(argv)
    doc = fixture()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        print("wrote %s (%d cases)" % (FIXTURE.relative_to(ROOT.parent),
                                       doc["count"]))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("missing fixture; run --write", file=sys.stderr)
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != doc:
            print("repair fixture drifted; run --write", file=sys.stderr)
            return 1
        print("repair fixture is current")
        return 0
    print(json.dumps(doc, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Deterministic thinking routes (step 53).

One checked-in table, `toolrx/thinking.json`, is the only source of the
`think.*` routes. It is expanded into catalog entries by
`toolrx/build_commands.py` and exported to `tests/fixtures/thinking.json` so
the routes and the fixture cannot drift.

    python3 toolrx/thinking.py --write   # refresh the fixture
    python3 toolrx/thinking.py --check   # fail if the fixture drifted
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TABLE = ROOT / "thinking.json"
FIXTURE = ROOT.parent / "tests" / "fixtures" / "thinking.json"

MODES = ("decompose", "reason", "tradeoff", "critique")
CAPTURE = r"(.+)"
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def load(path=TABLE):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _fail(message):
    raise ValueError("thinking table: " + message)


def _norm(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def _check_text(value, where):
    if not isinstance(value, str) or not value.strip():
        _fail(where + " must be a non-empty string")
    return value


def compile_template(text):
    """Return (anchored regex, args) for one route template."""
    names = _PLACEHOLDER.findall(text)
    if len(names) != 1 or names[0] != "topic":
        _fail("template %r must contain exactly one {topic}" % text)
    regex = "^" + text.replace("{topic}", CAPTURE, 1) + "$"
    return regex, {"topic": "$1"}


def _intents(table):
    intents = table.get("intents")
    if not isinstance(intents, dict) or not intents:
        _fail("intents must be a non-empty object")
    out = []
    seen_ops = set()
    for mode in MODES:
        if mode not in intents:
            _fail("missing intent %r" % mode)
    for mode, spec in intents.items():
        if mode not in MODES:
            _fail("unknown intent %r" % mode)
        if not isinstance(spec, dict):
            _fail("intent %r must be an object" % mode)
        op = _check_text(spec.get("op"), mode + ".op")
        if op != "think." + mode:
            _fail("intent %r must map to think.%s, not %r" % (mode, mode, op))
        if op in seen_ops:
            _fail("duplicate op %r" % op)
        seen_ops.add(op)
        templates = spec.get("templates")
        if not isinstance(templates, list) or not templates:
            _fail("intent %r needs at least one template" % mode)
        bare = spec.get("bare", [])
        if not isinstance(bare, list):
            _fail("intent %r bare must be a list" % mode)
        example = _check_text(spec.get("example"), mode + ".example")
        out.append({
            "mode": mode,
            "op": op,
            "summary": _check_text(spec.get("summary"), mode + ".summary"),
            "templates": [_check_text(t, mode + ".template") for t in templates],
            "bare": [_check_text(b, mode + ".bare") for b in bare],
            "example": example,
        })
    return out


def _all():
    table = load()
    if table.get("version") != 1:
        _fail("version must be 1")
    seen = {}
    counts = {}
    for intent in _intents(table):
        mode = intent["mode"]
        for text in intent["templates"]:
            regex, args = compile_template(text)
            key = _norm(text.replace("{topic}", "\x00"))
            if key in seen:
                _fail("template %r already used by %s" % (text, seen[key]))
            seen[key] = mode
            counts[mode] = counts.get(mode, 0) + 1
            yield {
                "id": "think.%s.%d" % (mode, counts[mode]),
                "op": intent["op"],
                "re": regex,
                "args": args,
                "d": intent["summary"],
                "c": "think",
                "text": text.replace("{topic}", intent["example"]),
                "expect": dict(args, topic=intent["example"]),
            }
        for text in intent["bare"]:
            key = _norm(text)
            if key in seen:
                _fail("bare route %r already used by %s" % (text, seen[key]))
            seen[key] = mode
            counts[mode] = counts.get(mode, 0) + 1
            yield {
                "id": "think.%s.%d" % (mode, counts[mode]),
                "op": intent["op"],
                "re": "^" + re.escape(text) + "$",
                "args": {"topic": ""},
                "d": intent["summary"],
                "c": "think",
                "text": text,
                "expect": {"topic": ""},
            }


def entries():
    """Unique catalog entries, in generation order."""
    return _all()


def fixture():
    cases = [
        {"text": e["text"], "op": e["op"], "args": e["expect"],
         "mode": e["op"].split(".", 1)[1]}
        for e in entries()
    ]
    cases.sort(key=lambda c: (c["mode"], c["text"]))
    modes = {}
    for case in cases:
        modes[case["mode"]] = modes.get(case["mode"], 0) + 1
    return {
        "version": 1,
        "count": len(cases),
        "modes": dict(sorted(modes.items())),
        "cases": cases,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh tests/fixtures/thinking.json")
    group.add_argument("--check", action="store_true",
                       help="fail if the fixture drifted")
    args = parser.parse_args(argv)
    doc = fixture()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        print("wrote %s (%d cases, %d modes)"
              % (FIXTURE.relative_to(ROOT.parent), doc["count"],
                 len(doc["modes"])))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("missing fixture; run --write", file=sys.stderr)
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != doc:
            print("thinking fixture drifted; run --write", file=sys.stderr)
            return 1
        print("thinking fixture is current")
        return 0
    print(json.dumps(doc["modes"], indent=2))
    print("%d cases" % doc["count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

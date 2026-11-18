#!/usr/bin/env python3
"""Deterministic response-style routes (step 58).

One checked-in table, `toolrx/style.json`, is the only source of the
`style.set` and `style.show` routes. It is expanded into catalog entries by
`toolrx/build_commands.py` and exported to `tests/fixtures/style.json` so the
routes and the fixture cannot drift.

    python3 toolrx/style.py --write   # refresh the fixture
    python3 toolrx/style.py --check   # fail if the fixture drifted
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TABLE = ROOT / "style.json"
FIXTURE = ROOT.parent / "tests" / "fixtures" / "style.json"

MODES = ("set", "show")
STYLES = ("concise", "explanatory", "tutorial")
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def load(path=TABLE):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _fail(message):
    raise ValueError("style table: " + message)


def _norm(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def _check_text(value, where):
    if not isinstance(value, str) or not value.strip():
        _fail(where + " must be a non-empty string")
    return value


def compile_template(text, styles):
    """Return (anchored regex, args) for one style template."""
    names = _PLACEHOLDER.findall(text)
    if len(names) != 1 or names[0] != "style":
        _fail("template %r must contain exactly one {style}" % text)
    before, after = text.split("{style}", 1)
    regex = ("^" + re.escape(before) + "(" + "|".join(styles) + ")"
             + re.escape(after) + "$")
    return regex, {"style": "$1"}


def _intents(table):
    intents = table.get("intents")
    if not isinstance(intents, dict) or not intents:
        _fail("intents must be a non-empty object")
    for mode in MODES:
        if mode not in intents:
            _fail("missing intent %r" % mode)
    out = []
    seen_ops = set()
    for mode, spec in intents.items():
        if mode not in MODES:
            _fail("unknown intent %r" % mode)
        if not isinstance(spec, dict):
            _fail("intent %r must be an object" % mode)
        op = _check_text(spec.get("op"), mode + ".op")
        if op != "style." + mode:
            _fail("intent %r must map to style.%s, not %r" % (mode, mode, op))
        if op in seen_ops:
            _fail("duplicate op %r" % op)
        seen_ops.add(op)
        templates = spec.get("templates", [])
        bare = spec.get("bare", [])
        if not isinstance(templates, list):
            _fail("intent %r templates must be a list" % mode)
        if not isinstance(bare, list):
            _fail("intent %r bare must be a list" % mode)
        if not templates and not bare:
            _fail("intent %r needs at least one template or bare phrase" % mode)
        example = _check_text(spec.get("example"), mode + ".example")
        styles = spec.get("styles", list(STYLES))
        if not isinstance(styles, list):
            _fail("intent %r styles must be a list" % mode)
        clean = []
        for style in styles:
            name = _check_text(style, mode + ".style").lower()
            if name not in STYLES:
                _fail("intent %r has unknown style %r" % (mode, name))
            if name in clean:
                _fail("intent %r repeats style %r" % (mode, name))
            clean.append(name)
        if mode == "set":
            if tuple(clean) != STYLES:
                _fail("set styles must be exactly %s" % ", ".join(STYLES))
            if example not in clean:
                _fail("set example %r must be one of the styles" % example)
        if not templates and example not in bare:
            _fail("intent %r example %r must be one of its bare phrases"
                  % (mode, example))
        out.append({
            "mode": mode,
            "op": op,
            "summary": _check_text(spec.get("summary"), mode + ".summary"),
            "templates": [_check_text(t, mode + ".template") for t in templates],
            "bare": [_check_text(t, mode + ".bare") for t in bare],
            "example": example,
            "styles": clean,
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
            regex, args = compile_template(text, intent["styles"])
            key = _norm(text.replace("{style}", "\x00"))
            if key in seen:
                _fail("template %r already used by %s" % (text, seen[key]))
            seen[key] = mode
            counts[mode] = counts.get(mode, 0) + 1
            yield {
                "id": "style.%s.%d" % (mode, counts[mode]),
                "op": intent["op"],
                "re": regex,
                "args": args,
                "d": intent["summary"],
                "c": "style",
                "text": text.replace("{style}", intent["example"]),
                "expect": {"style": intent["example"]},
            }
        for text in intent["bare"]:
            key = _norm(text)
            if key in seen:
                _fail("bare route %r already used by %s" % (text, seen[key]))
            seen[key] = mode
            counts[mode] = counts.get(mode, 0) + 1
            yield {
                "id": "style.%s.%d" % (mode, counts[mode]),
                "op": intent["op"],
                "re": "^" + re.escape(text) + "$",
                "args": {},
                "d": intent["summary"],
                "c": "style",
                "text": text,
                "expect": {},
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
    ops = {}
    for case in cases:
        ops[case["op"]] = ops.get(case["op"], 0) + 1
    return {
        "version": 1,
        "count": len(cases),
        "ops": dict(sorted(ops.items())),
        "cases": cases,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh tests/fixtures/style.json")
    group.add_argument("--check", action="store_true",
                       help="fail if the fixture drifted")
    args = parser.parse_args(argv)
    doc = fixture()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        print("wrote %s (%d cases, %d ops)"
              % (FIXTURE.relative_to(ROOT.parent), doc["count"],
                 len(doc["ops"])))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("missing fixture; run --write", file=sys.stderr)
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != doc:
            print("style fixture drifted; run --write", file=sys.stderr)
            return 1
        print("style fixture is current")
        return 0
    print(json.dumps(doc["ops"], indent=2))
    print("%d cases" % doc["count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

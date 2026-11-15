#!/usr/bin/env python3
"""Conversational glue (step 47).

Short replies — confirmations, rejections, corrections, repairs, and
acknowledgements — are exact commands like any other. One checked-in table
feeds both `toolrx/build_commands.py` and `tests/fixtures/conversation.json`.
The handlers live in `toolrx/web/skills.js` because a correction needs the
previous turn; the routes themselves stay inspectable in the catalog.

    python3 toolrx/conversation.py --write   # refresh the fixture
    python3 toolrx/conversation.py --check   # fail if the fixture drifted
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
FIXTURE = ROOT.parent / "tests" / "fixtures" / "conversation.json"

# A confirmation only applies an action that was staged by the previous turn.
CONFIRM = [
    "yes", "yeah", "yep", "yup", "yes please", "do it", "go ahead",
    "go for it", "confirm", "proceed", "ok", "okay", "sure", "alright",
]

# A rejection discards a staged action and never executes it.
REJECT = [
    "no", "nope", "nah", "cancel", "cancel that", "don't", "do not",
    "never mind", "nevermind", "stop that",
]

# Corrections carry the replacement text. The handler either revises the last
# action, stages a build for confirmation, or asks one bounded question.
CORRECT = [
    ("i meant {text}",
     r"^(?:no[, ]+)?(?:i\s+meant|i\s+mean)\s+(.+)$",
     "no, i meant 13 plus 30", "13 plus 30"),
    ("actually {text}", r"^actually[, ]+(.+)$",
     "actually make it 3d", "make it 3d"),
    ("sorry, i meant {text}",
     r"^sorry[, ]+(?:i\s+meant\s+)?(.+)$",
     "sorry, i meant 13 plus 30", "13 plus 30"),
]

REPAIR = [
    "that's wrong", "that is wrong", "that's not right", "that's incorrect",
    "not what i meant", "not what i asked for", "try again",
    "you got that wrong",
]

ACK = [
    "got it", "cool", "nice", "perfect", "great", "sounds good",
    "ok thanks", "nice one", "well done", "good job", "that works",
    "makes sense",
]

SHOW = [
    "show conversation", "show the conversation", "what's in the conversation",
    "what is in the conversation", "conversation",
]

CLEAR = [
    "clear conversation", "clear the conversation", "reset conversation",
    "reset the conversation",
]


def _entry(kind, op, text, pattern, args, expect, desc=None):
    return {
        "family": "conversation",
        "kind": kind,
        "text": text,
        "op": op,
        "re": pattern,
        "args": dict(args),
        "expect": dict(expect),
        "d": desc or text,
        "c": "chat",
    }


def _literal(kind, op, phrases, args=None):
    return [
        _entry(kind, op, phrase, "^" + re.escape(phrase) + "$",
               args or {}, args or {})
        for phrase in phrases
    ]


def _all():
    out = []
    out += _literal("confirm", "conversation.confirm", CONFIRM)
    out += _literal("reject", "conversation.reject", REJECT)
    for display, pattern, sample, captured in CORRECT:
        out.append(_entry("correct", "conversation.correct", sample, pattern,
                          {"text": "$1"}, {"text": captured},
                          desc=display))
    out += _literal("repair", "conversation.repair", REPAIR)
    out += _literal("ack", "chat", ACK)
    out += _literal("show", "conversation.show", SHOW)
    out += _literal("clear", "conversation.clear", CLEAR)
    return out


def entries():
    """Unique catalog entries, in generation order."""
    seen = set()
    counts = {}
    for entry in _all():
        key = re.sub(r"\s+", "", entry["text"].lower())
        if key in seen:
            continue
        seen.add(key)
        n = counts.get(entry["kind"], 0) + 1
        counts[entry["kind"]] = n
        entry["id"] = "conversation.%s.%d" % (entry["kind"], n)
        yield entry


def fixture():
    cases = [
        {"kind": e["kind"], "text": e["text"], "op": e["op"],
         "args": e["expect"]}
        for e in entries()
    ]
    cases.sort(key=lambda c: (c["kind"], c["text"]))
    kinds = {}
    for case in cases:
        kinds[case["kind"]] = kinds.get(case["kind"], 0) + 1
    return {
        "version": 1,
        "count": len(cases),
        "kinds": dict(sorted(kinds.items())),
        "cases": cases,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh tests/fixtures/conversation.json")
    group.add_argument("--check", action="store_true",
                       help="fail if the fixture drifted")
    args = parser.parse_args(argv)
    doc = fixture()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        print("wrote %s (%d cases, %d kinds)"
              % (FIXTURE.relative_to(ROOT.parent), doc["count"],
                 len(doc["kinds"])))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("missing fixture; run --write", file=sys.stderr)
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != doc:
            print("conversation fixture drifted; run --write", file=sys.stderr)
            return 1
        print("conversation fixture is current")
        return 0
    print(json.dumps(doc["kinds"], indent=2))
    print("%d cases" % doc["count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

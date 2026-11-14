#!/usr/bin/env python3
"""Everyday paraphrase layer (step 46).

One table feeds both `toolrx/build_commands.py` (which compiles the catalog)
and the checked-in fixture `tests/fixtures/everyday.json`. Every phrase is
literal or a small capture template, so the exact matcher still wins over the
hashed router.

    python3 toolrx/everyday.py --write   # refresh the fixture
    python3 toolrx/everyday.py --check   # fail if the fixture drifted
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
FIXTURE = ROOT.parent / "tests" / "fixtures" / "everyday.json"

TXT = r"(.+?)"
REST = r"(.+)"
N = (r"(-?(?:\d[\d,]*(?:\.\d+)?|\d*\.\d+|zero|one|two|three|four|five|six|"
     r"seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
     r"seventeen|eighteen|nineteen|twenty))")

IMPERATIVE = ["can you", "could you", "please", "would you",
              "go ahead and", "i'd like you to"]
EXTRACT = ["can you", "could you", "please", "would you", "quickly",
           "go ahead and", "i want you to"]
TEXT = ["can you", "could you", "please", "quickly", "just",
        "go ahead and"]
MEMORY = ["can you", "could you", "please", "quickly", "just"]
QUESTION = ["can you tell me", "could you tell me", "please tell me",
            "quickly tell me", "i'd like to know"]

BUILD_CORES = [
    ("build a platformer", {"kind": "platformer"}),
    ("build a shooter", {"kind": "shooter"}),
    ("build an rpg", {"kind": "rpg"}),
    ("build a tower defense", {"kind": "tower defense"}),
    ("build a calculator", {"kind": "calculator"}),
    ("build a todo list", {"kind": "todo list"}),
    ("build a timer", {"kind": "timer"}),
    ("build a notes app", {"kind": "notes"}),
    ("build a landing page", {"kind": "landing page"}),
    ("build a dashboard", {"kind": "dashboard"}),
    ("build a chart", {"kind": "chart"}),
    ("build a clock", {"kind": "clock"}),
    ("build a maze", {"kind": "maze"}),
    ("build a snake game", {"kind": "snake game"}),
    ("build a racing game", {"kind": "racing game"}),
    ("build a memory game", {"kind": "memory game"}),
    ("build a pomodoro timer", {"kind": "pomodoro timer"}),
    ("build a markdown editor", {"kind": "markdown editor"}),
]

EDIT_CORES = [
    ("add a boss", {"patch": "boss"}),
    ("add a quest", {"patch": "quest"}),
    ("add sound", {"patch": "sound"}),
    ("add day/night", {"patch": "day-night"}),
    ("add double jump", {"patch": "double-jump"}),
    ("add three enemy types", {"patch": "enemy-types"}),
    ("make it harder", {"patch": "harder"}),
    ("make it 3d", {"patch": "three-d"}),
    ("switch to isometric", {"patch": "isometric"}),
]

GROWTH_CORES = [
    ("grow the project", {}),
    ("split the project into modules", {}),
    ("expand the core module", {"module": "core"}),
    ("expand the ui module", {"module": "ui"}),
    ("add the data module", {"module": "data"}),
    ("add the content module", {"module": "content"}),
    ("add a save system", {"system": "save"}),
    ("add a combat system", {"system": "combat"}),
    ("add an inventory system", {"system": "inventory"}),
    ("add a dialogue system", {"system": "dialogue"}),
]

CONTEXT_CORES = [
    ("show context", {}),
    ("show the context", {}),
    ("take a context snapshot", {}),
    ("clear context", {}),
    ("continue from previous", {}),
    ("diff against previous context", {}),
    ("show the context diff", {}),
]

PROJECT_CORES = [
    ("show my projects", {}),
    ("list projects", {}),
    ("show project files", {}),
    ("export this project", {}),
    ("list bundles", {}),
]

MATH = {
    "add": [
        ("what's {a} plus {b}", {"a": "$1", "b": "$2"}),
        ("whats {a} plus {b}", {"a": "$1", "b": "$2"}),
        ("how much is {a} plus {b}", {"a": "$1", "b": "$2"}),
        ("can you add {a} and {b}", {"a": "$1", "b": "$2"}),
        ("could you add {a} and {b}", {"a": "$1", "b": "$2"}),
        ("please add {a} and {b}", {"a": "$1", "b": "$2"}),
        ("i need {a} plus {b}", {"a": "$1", "b": "$2"}),
        ("tell me what {a} plus {b} is", {"a": "$1", "b": "$2"}),
        ("what do you get if you add {a} and {b}", {"a": "$1", "b": "$2"}),
    ],
    "sub": [
        ("what's {a} minus {b}", {"a": "$1", "b": "$2"}),
        ("whats {a} minus {b}", {"a": "$1", "b": "$2"}),
        ("how much is {a} minus {b}", {"a": "$1", "b": "$2"}),
        ("can you subtract {b} from {a}", {"b": "$1", "a": "$2"}),
        ("could you subtract {b} from {a}", {"b": "$1", "a": "$2"}),
        ("please subtract {b} from {a}", {"b": "$1", "a": "$2"}),
        ("i need {a} minus {b}", {"a": "$1", "b": "$2"}),
        ("tell me what {a} minus {b} is", {"a": "$1", "b": "$2"}),
        ("what do you get if you subtract {b} from {a}", {"b": "$1", "a": "$2"}),
    ],
    "mul": [
        ("what's {a} times {b}", {"a": "$1", "b": "$2"}),
        ("whats {a} times {b}", {"a": "$1", "b": "$2"}),
        ("how much is {a} times {b}", {"a": "$1", "b": "$2"}),
        ("can you multiply {a} by {b}", {"a": "$1", "b": "$2"}),
        ("could you multiply {a} by {b}", {"a": "$1", "b": "$2"}),
        ("please multiply {a} by {b}", {"a": "$1", "b": "$2"}),
        ("i need {a} times {b}", {"a": "$1", "b": "$2"}),
        ("tell me what {a} times {b} is", {"a": "$1", "b": "$2"}),
        ("what do you get if you multiply {a} by {b}", {"a": "$1", "b": "$2"}),
    ],
    "div": [
        ("what's {a} divided by {b}", {"a": "$1", "b": "$2"}),
        ("whats {a} divided by {b}", {"a": "$1", "b": "$2"}),
        ("how much is {a} divided by {b}", {"a": "$1", "b": "$2"}),
        ("can you divide {a} by {b}", {"a": "$1", "b": "$2"}),
        ("could you divide {a} by {b}", {"a": "$1", "b": "$2"}),
        ("please divide {a} by {b}", {"a": "$1", "b": "$2"}),
        ("i need {a} divided by {b}", {"a": "$1", "b": "$2"}),
        ("tell me what {a} divided by {b} is", {"a": "$1", "b": "$2"}),
        ("what do you get if you divide {a} by {b}", {"a": "$1", "b": "$2"}),
    ],
}

# Each tuple is (display, regex body, args, sample, expected args). The body
# is the literal phrase with its capture groups, so the generated pattern is
# the prefix plus this body and nothing is silently dropped.
EXTRACT_CORES = [
    ("summarize {text}", "summarize " + TXT, {"text": "$1"},
     "summarize notes.md", {"text": "notes.md"}),
    ("extract the list from {text}", "extract the list from " + TXT,
     {"text": "$1"}, "extract the list from notes.md", {"text": "notes.md"}),
    ("extract the key facts from {text}", "extract the key facts from " + TXT,
     {"text": "$1"}, "extract the key facts from notes.md",
     {"text": "notes.md"}),
    ("extract the headings from {text}", "extract the headings from " + TXT,
     {"text": "$1"}, "extract the headings from notes.md",
     {"text": "notes.md"}),
    ("outline the code in {text}", "outline the code in " + TXT,
     {"text": "$1"}, "outline the code in notes.md", {"text": "notes.md"}),
    ("count the words in {text}", "count the words in " + TXT,
     {"what": "words", "text": "$1"}, "count the words in notes.md",
     {"what": "words", "text": "notes.md"}),
    ("show me the first 5 lines of {text}", "show me the first 5 lines of " + TXT,
     {"n": "5", "text": "$1"}, "show me the first 5 lines of notes.md",
     {"n": "5", "text": "notes.md"}),
    ("diff {a} and {b}", "diff " + TXT + " and " + TXT,
     {"a": "$1", "b": "$2"}, "diff notes.md and README.md",
     {"a": "notes.md", "b": "README.md"}),
]

TEXT_CORES = [
    ("uppercase {text}", "uppercase " + TXT, {"op": "upper", "text": "$1"},
     "uppercase hello world", {"op": "upper", "text": "hello world"}),
    ("lowercase {text}", "lowercase " + TXT, {"op": "lower", "text": "$1"},
     "lowercase HELLO WORLD", {"op": "lower", "text": "HELLO WORLD"}),
    ("slugify {text}", "slugify " + TXT, {"op": "slug", "text": "$1"},
     "slugify hello world", {"op": "slug", "text": "hello world"}),
    ("sort the lines in {text}", "sort the lines in " + TXT,
     {"op": "sortlines", "text": "$1"}, "sort the lines in hello world",
     {"op": "sortlines", "text": "hello world"}),
    ("remove duplicate lines from {text}", "remove duplicate lines from " + TXT,
     {"op": "uniqlines", "text": "$1"},
     "remove duplicate lines from hello world",
     {"op": "uniqlines", "text": "hello world"}),
    ("reverse the words in {text}", "reverse the words in " + TXT,
     {"op": "reversewords", "text": "$1"}, "reverse the words in hello world",
     {"op": "reversewords", "text": "hello world"}),
    ("title case {text}", "title case " + TXT, {"op": "title", "text": "$1"},
     "title case hello world", {"op": "title", "text": "hello world"}),
    # Generic last: "reverse the words in ..." must win before this catches it.
    ("reverse {text}", "reverse " + TXT, {"op": "reverse", "text": "$1"},
     "reverse hello world", {"op": "reverse", "text": "hello world"}),
]

MEMORY_IMPERATIVE = [
    ("remember that my {key} is {value}", "remember that my " + TXT + " is " + TXT,
     {"key": "$1", "value": "$2"},
     "remember that my favourite colour is blue",
     {"key": "favourite colour", "value": "blue"}),
    ("remember {key} is {value}", "remember " + TXT + " is " + TXT,
     {"key": "$1", "value": "$2"},
     "remember favourite colour is blue",
     {"key": "favourite colour", "value": "blue"}),
    ("make a note that {text}", "make a note that " + TXT, {"text": "$1"},
     "make a note that the demo is offline",
     {"text": "the demo is offline"}),
    ("forget my {key}", "forget my " + TXT, {"key": "$1"},
     "forget my favourite colour", {"key": "favourite colour"}),
]
MEMORY_IMPERATIVE_LITERAL = [
    ("show your memory", {}),
    ("clear your memory", {}),
]
MEMORY_QUESTION = [
    ("what you remember about my {key}", "what you remember about my " + TXT,
     {"key": "$1"}, "what you remember about my favourite colour",
     {"key": "favourite colour"}),
    ("what my {key} is", "what my " + TXT + " is", {"key": "$1"},
     "what my favourite colour is", {"key": "favourite colour"}),
]
MEMORY_QUESTION_LITERAL = [
    ("what you have saved", {}),
]

SYSTEM_QUESTION = [
    ("what you can do", {"op": "help"}),
    ("what your limits are", {"op": "limits"}),
    ("what the caps are", {"op": "limits"}),
    ("how big a plan can be", {"op": "limits"}),
    ("what the maximum plan size is", {"op": "limits"}),
    ("what commands you have", {"op": "help"}),
    ("what your name is", {"op": "who"}),
    ("how this works", {"op": "help"}),
]


def _entry(family, op, text, pattern, args, expect, cat, desc=None):
    return {
        "family": family,
        "text": text,
        "op": op,
        "re": pattern,
        "args": dict(args),
        "expect": dict(expect),
        "d": desc or text,
        "c": cat,
    }


def _literal(family, op, cores, forms, cat):
    out = []
    for core, args in cores:
        for form in forms:
            text = form + " " + core
            out.append(_entry(family, op, text, "^" + re.escape(text) + "$",
                              args, args, cat))
    return out


def _captured(family, op, cores, forms, cat):
    out = []
    for display, rx, args, sample, expect in cores:
        for form in forms:
            text = form + " " + display
            pattern = "^" + re.escape(form) + " " + rx + "$"
            sample_text = form + " " + sample
            out.append(_entry(family, op, sample_text, pattern, args, expect, cat,
                              desc=text))
    return out


def _math():
    out = []
    for op, templates in MATH.items():
        for pattern, argmap in templates:
            values = {"a": "12", "b": "30"}
            order = re.findall(r"\{(\w+)\}", pattern)
            expect = {"op": op}
            for name, ref in argmap.items():
                expect[name] = values[order[int(ref[1:]) - 1]]
            sample = pattern.format(**values)
            out.append(_entry("math", "math.binary", sample,
                              "^" + pattern.replace("{a}", N).replace("{b}", N) + "$",
                              dict({"op": op}, **argmap), expect, "math"))
    return out


def _all():
    return (
        _literal("build", "build", BUILD_CORES, IMPERATIVE, "build")
        + _literal("edit", "edit.apply", EDIT_CORES, IMPERATIVE, "edit")
        + _literal("growth", "project.grow", GROWTH_CORES[:2], IMPERATIVE, "edit")
        + _literal("growth", "module.expand", GROWTH_CORES[2:6], IMPERATIVE, "edit")
        + _literal("growth", "system.add", GROWTH_CORES[6:], IMPERATIVE, "edit")
        + _literal("context", "context.show", CONTEXT_CORES[:2], IMPERATIVE, "context")
        + _literal("context", "context.snapshot", CONTEXT_CORES[2:3], IMPERATIVE, "context")
        + _literal("context", "context.clear", CONTEXT_CORES[3:4], IMPERATIVE, "context")
        + _literal("context", "context.continue", CONTEXT_CORES[4:5], IMPERATIVE, "context")
        + _literal("context", "context.diff", CONTEXT_CORES[5:], IMPERATIVE, "context")
        + _literal("projects", "project.list", PROJECT_CORES[:2], IMPERATIVE, "project")
        + _literal("projects", "project.files", PROJECT_CORES[2:3], IMPERATIVE, "project")
        + _literal("projects", "project.export", PROJECT_CORES[3:4], IMPERATIVE, "project")
        + _literal("projects", "workspace.bundles", PROJECT_CORES[4:5], IMPERATIVE, "project")
        + _literal("projects", "memory.context", [("show my current project", {})],
                   IMPERATIVE, "project")
        + _math()
        + _captured("extract", "text.summarize", EXTRACT_CORES[:1], EXTRACT, "text")
        + _captured("extract", "text.list", EXTRACT_CORES[1:2], EXTRACT, "text")
        + _captured("extract", "text.facts", EXTRACT_CORES[2:3], EXTRACT, "text")
        + _captured("extract", "text.headings", EXTRACT_CORES[3:4], EXTRACT, "text")
        + _captured("extract", "text.code", EXTRACT_CORES[4:5], EXTRACT, "text")
        + _captured("extract", "text.count", EXTRACT_CORES[5:6], EXTRACT, "text")
        + _captured("extract", "text.firstlines", EXTRACT_CORES[6:7], EXTRACT, "text")
        + _captured("extract", "text.diff", EXTRACT_CORES[7:], EXTRACT, "text")
        + _captured("text", "text.transform", TEXT_CORES[:4], TEXT, "text")
        + _captured("text", "text.transform", TEXT_CORES[4:], TEXT, "text")
        + _captured("memory", "memory.remember", MEMORY_IMPERATIVE[:2], MEMORY, "memory")
        + _captured("memory", "memory.note", MEMORY_IMPERATIVE[2:3], MEMORY, "memory")
        + _captured("memory", "memory.forget", MEMORY_IMPERATIVE[3:], MEMORY, "memory")
        + _literal("memory", "memory.list", MEMORY_IMPERATIVE_LITERAL[:1], MEMORY, "memory")
        + _literal("memory", "memory.forget", MEMORY_IMPERATIVE_LITERAL[1:], MEMORY, "memory")
        + _captured("memory", "memory.recall", MEMORY_QUESTION, QUESTION, "memory")
        + _literal("memory", "memory.list", MEMORY_QUESTION_LITERAL, QUESTION, "memory")
        + _literal("system", "system", SYSTEM_QUESTION, QUESTION, "misc")
    )


def entries():
    """Unique catalog entries, in generation order."""
    seen = set()
    counts = {}
    for entry in _all():
        key = re.sub(r"\s+", "", entry["text"].lower())
        if key in seen:
            continue
        seen.add(key)
        n = counts.get(entry["family"], 0) + 1
        counts[entry["family"]] = n
        entry["id"] = "everyday.%s.%d" % (entry["family"], n)
        yield entry


def fixture():
    cases = [
        {"family": e["family"], "text": e["text"], "op": e["op"],
         "args": e["expect"]}
        for e in entries()
    ]
    cases.sort(key=lambda c: (c["family"], c["text"]))
    families = {}
    for case in cases:
        families[case["family"]] = families.get(case["family"], 0) + 1
    return {
        "version": 1,
        "count": len(cases),
        "families": dict(sorted(families.items())),
        "cases": cases,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh tests/fixtures/everyday.json")
    group.add_argument("--check", action="store_true",
                       help="fail if the fixture drifted")
    args = parser.parse_args(argv)
    doc = fixture()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        print("wrote %s (%d cases, %d families)"
              % (FIXTURE.relative_to(ROOT.parent), doc["count"],
                 len(doc["families"])))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("missing fixture; run --write", file=sys.stderr)
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != doc:
            print("everyday fixture drifted; run --write", file=sys.stderr)
            return 1
        print("everyday fixture is current")
        return 0
    print(json.dumps(doc["families"], indent=2))
    print("%d cases" % doc["count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

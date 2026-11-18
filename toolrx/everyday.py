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
COMMANDS = ROOT / "web" / "commands.json"

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
    ("compact context", {}),
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

# Step 60: domain packs. Every row is a full phrase with placeholders, an op,
# fixed args, and the display form the docs and fixture report. `_generated`
# escapes the literal text and substitutes the same capture patterns the rest of
# the layer uses, so a pack cannot introduce a second regex dialect.
#
# The base catalog is the authority on what is already covered. Each row here
# was checked against it before it landed: if an earlier command already matches
# the sample phrase, the row is omitted instead of shipping a route that can
# never win. `entries()` re-applies that rule at build time for exact pattern
# duplicates, and `tests/test_everyday.py` fails if any row ever becomes
# shadowed again.
FILE = r"([\w./-]+\.\w+)"
LIST = (r"(-?\d[\d,]*(?:\.\d+)?(?:\s*(?:,|and|;|\s)\s*"
        r"-?\d[\d,]*(?:\.\d+)?)+)")

# Step 60: the domain packs reuse one capture vocabulary. A placeholder that is
# not in this map is a table bug, not a literal brace.
CAPTURE_MAP = {
    "a": N, "b": N, "n": N, "list": LIST, "file": FILE, "path": FILE,
    "text": TXT, "key": TXT, "value": TXT, "slug": TXT,
    "name": TXT, "topic": REST,
}
SAMPLES = {
    "a": "16", "b": "4", "n": "5", "list": "4, 8, 15",
    "file": "notes.md", "path": "notes.md", "text": "notes.md", "key": "favourite colour",
    "value": "blue", "slug": "demo", "name": "my app",
    "topic": "art style",
}


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


def _rx(display):
    out = []
    for part in re.split(r"(\{\w+\})", display):
        match = re.fullmatch(r"\{(\w+)\}", part)
        if not match:
            out.append(re.escape(part))
            continue
        name = match.group(1)
        if name not in CAPTURE_MAP:
            raise ValueError("everyday pack: no capture for %r" % name)
        out.append(CAPTURE_MAP[name])
    return "^" + "".join(out) + "$"


def _sample(display):
    return re.sub(r"\{(\w+)\}",
                  lambda m: SAMPLES.get(m.group(1), m.group(0)), display)


def _expect(args, display):
    values = [SAMPLES[name] for name in re.findall(r"\{(\w+)\}", display)]

    def fill(value):
        if not isinstance(value, str):
            return value
        return re.sub(r"\$(\d+)",
                      lambda m: values[int(m.group(1)) - 1], value)
    return {key: fill(value) for key, value in args.items()}


def _generated(family, rows, cat):
    """Expand (display, op, args) rows into catalog entries and expectations."""
    out = []
    for display, op, args in rows:
        out.append(_entry(family, op, _sample(display), _rx(display),
                          args, _expect(args, display), cat, desc=display))
    return out


# (family, op, args, display) — verified new against the base catalog.
DEPTH = [
    ('math', 'math.unary', {'op': 'round', 'a': '$1'}, 'what is {a} rounded'),
    ('math', 'math.unary', {'op': 'abs', 'a': '$1'}, 'what is the absolute value of {a}'),
    ('math', 'math.unary', {'op': 'fact', 'a': '$1'}, 'what is the factorial of {a}'),
    ('math', 'math.unary', {'op': 'half', 'a': '$1'}, 'what is half of {a}'),
    ('math', 'math.expr', {'expr': '$1^$2'}, 'what is {a} to the power of {b}'),
    ('math', 'math.expr', {'expr': '$1/100*$2'}, 'how much is {a} percent of {b}'),
    ('math', 'math.list', {'op': 'mean', 'list': '$1'}, 'what is the average of {list}'),
    ('math', 'math.list', {'op': 'median', 'list': '$1'}, 'what is the median of {list}'),
    ('math', 'math.list', {'op': 'range', 'list': '$1'}, 'what is the range of {list}'),
    ('math', 'math.list', {'op': 'stdev', 'list': '$1'}, 'what is the standard deviation of {list}'),
    ('math', 'math.list', {'op': 'sum', 'list': '$1'}, 'what is the sum of {list}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'open {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'show me {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'print {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'display {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, "what's in {file}"),
    ('files', 'fs.read_file', {'path': '$1'}, 'what is in {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'show the contents of {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'cat {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'let me see {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'view {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'open up {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'pull up {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'read the file {path}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'print out {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, "show me what's in {file}"),
    ('files', 'fs.list_dir', {}, 'list this folder'),
    ('files', 'fs.list_dir', {}, "what's in this folder"),
    ('files', 'fs.list_dir', {}, 'what is in this folder'),
    ('files', 'fs.list_dir', {}, 'show this directory'),
    ('files', 'fs.list_dir', {}, 'list the files here'),
    ('files', 'fs.list_dir', {}, 'what files are here'),
    ('files', 'fs.list_dir', {}, 'show me the current folder'),
    ('files', 'fs.list_dir', {}, 'browse this directory'),
    ('files', 'fs.list_dir', {}, 'list the directory'),
    ('files', 'fs.list_dir', {}, "what's in the current directory"),
    ('files', 'fs.list_dir', {}, 'show folder contents'),
    ('files', 'fs.list_dir', {}, 'what files are in this folder'),
    ('files', 'fs.list_dir', {}, 'list everything here'),
    ('files', 'fs.list_dir', {}, 'show the working directory'),
    ('files', 'fs.list_dir', {}, 'what is in this directory'),
    ('files', 'fs.list_dir', {}, 'list the current directory'),
    ('growth', 'module.expand', {'module': 'core'}, 'work on the core module'),
    ('growth', 'module.expand', {'module': 'core'}, 'flesh out the core module'),
    ('growth', 'module.expand', {'module': 'core'}, 'extend the core module'),
    ('growth', 'module.expand', {'module': 'ui'}, 'work on the ui module'),
    ('growth', 'module.expand', {'module': 'ui'}, 'flesh out the ui module'),
    ('growth', 'module.expand', {'module': 'ui'}, 'extend the ui module'),
    ('growth', 'module.expand', {'module': 'data'}, 'work on the data module'),
    ('growth', 'module.expand', {'module': 'data'}, 'flesh out the data module'),
    ('growth', 'module.expand', {'module': 'data'}, 'extend the data module'),
    ('growth', 'module.expand', {'module': 'content'}, 'work on the content module'),
    ('growth', 'module.expand', {'module': 'content'}, 'flesh out the content module'),
    ('growth', 'module.expand', {'module': 'content'}, 'extend the content module'),
    ('growth', 'system.add', {'system': 'inventory'}, 'give it a inventory system'),
    ('growth', 'system.add', {'system': 'inventory'}, 'include a inventory system'),
    ('growth', 'system.add', {'system': 'dialogue'}, 'give it a dialogue system'),
    ('growth', 'system.add', {'system': 'dialogue'}, 'include a dialogue system'),
    ('growth', 'system.add', {'system': 'combat'}, 'give it a combat system'),
    ('growth', 'system.add', {'system': 'combat'}, 'include a combat system'),
    ('growth', 'system.add', {'system': 'save'}, 'give it a save system'),
    ('growth', 'system.add', {'system': 'save'}, 'include a save system'),
    ('growth', 'system.add', {'system': 'quests'}, 'give it a quests system'),
    ('growth', 'system.add', {'system': 'quests'}, 'include a quests system'),
    ('growth', 'system.add', {'system': 'crafting'}, 'give it a crafting system'),
    ('growth', 'system.add', {'system': 'crafting'}, 'include a crafting system'),
    ('growth', 'system.add', {'system': 'ui'}, 'give it a ui system'),
    ('growth', 'system.add', {'system': 'ui'}, 'include a ui system'),
    ('growth', 'system.add', {'system': 'audio'}, 'give it a audio system'),
    ('growth', 'system.add', {'system': 'audio'}, 'include a audio system'),
    ('growth', 'system.add', {'system': 'weather'}, 'give it a weather system'),
    ('growth', 'system.add', {'system': 'weather'}, 'include a weather system'),
    ('growth', 'system.add', {'system': 'particles'}, 'give it a particles system'),
    ('growth', 'system.add', {'system': 'particles'}, 'include a particles system'),
    ('growth', 'system.add', {'system': 'ai'}, 'give it a ai system'),
    ('growth', 'system.add', {'system': 'ai'}, 'include a ai system'),
    ('extract', 'text.extract', {'what': 'emails', 'text': '$1'}, 'pull the emails out of {text}'),
    ('extract', 'text.extract', {'what': 'emails', 'text': '$1'}, 'what emails are in {text}'),
    ('extract', 'text.extract', {'what': 'urls', 'text': '$1'}, 'pull the links out of {text}'),
    ('extract', 'text.extract', {'what': 'urls', 'text': '$1'}, 'grab the urls from {text}'),
    ('extract', 'text.extract', {'what': 'urls', 'text': '$1'}, 'what links are in {text}'),
    ('extract', 'text.extract', {'what': 'numbers', 'text': '$1'}, 'pull the numbers out of {text}'),
    ('extract', 'text.extract', {'what': 'numbers', 'text': '$1'}, 'grab the numbers from {text}'),
    ('extract', 'text.count', {'what': 'words', 'text': '$1'}, 'how many words are in {text}'),
    ('extract', 'text.count', {'what': 'words', 'text': '$1'}, "what's the word count of {text}"),
    ('extract', 'text.count', {'what': 'words', 'text': '$1'}, 'count words in {text}'),
    ('extract', 'text.count', {'what': 'chars', 'text': '$1'}, 'how many characters are in {text}'),
    ('extract', 'text.count', {'what': 'chars', 'text': '$1'}, "what's the character count of {text}"),
    ('extract', 'text.count', {'what': 'lines', 'text': '$1'}, 'how many lines are in {text}'),
    ('extract', 'text.firstlines', {'n': '5', 'text': '$1'}, 'print the first 5 lines of {text}'),
    ('extract', 'text.headings', {'text': '$1'}, 'pull the headings out of {text}'),
    ('extract', 'text.headings', {'text': '$1'}, 'grab the headings from {text}'),
    ('extract', 'text.facts', {'text': '$1'}, 'pull the key facts out of {text}'),
    ('extract', 'text.facts', {'text': '$1'}, 'grab the key facts from {text}'),
    ('extract', 'text.list', {'text': '$1'}, 'pull the list out of {text}'),
    ('extract', 'text.list', {'text': '$1'}, 'grab the list from {text}'),
    ('extract', 'text.code', {'text': '$1'}, 'give me an outline of {text}'),
    ('extract', 'text.summarize', {'text': '$1'}, 'give me a summary of {text}'),
    ('extract', 'text.summarize', {'text': '$1'}, 'make a summary of {text}'),
    ('build', 'build', {'kind': 'platformer'}, 'make me a platformer'),
    ('build', 'build', {'kind': 'tower defense'}, 'give me a tower defense'),
    ('build', 'build', {'kind': 'landing page'}, 'spin up a landing page'),
    ('build', 'build', {'kind': 'dashboard'}, 'set up a dashboard'),
    ('build', 'build', {'kind': 'notes'}, 'i want a notes app'),
    ('build', 'build', {'kind': 'timer'}, 'i need a timer'),
    ('build', 'build', {'kind': 'calculator'}, 'can you make a calculator'),
    ('build', 'build', {'kind': 'snake game'}, 'please create a snake game'),
    ('build', 'build', {'kind': 'racing game'}, 'start a new racing game'),
    ('build', 'build', {'kind': 'memory game'}, 'generate a memory game'),
    ('build', 'build', {'kind': 'pomodoro timer'}, 'make a pomodoro timer'),
    ('build', 'build', {'kind': 'clock'}, "i'd like a clock"),
    ('edit', 'edit.apply', {'patch': 'boss'}, 'include a boss'),
    ('edit', 'edit.apply', {'patch': 'boss'}, 'give it a boss'),
    ('edit', 'edit.apply', {'patch': 'boss'}, 'put a boss in it'),
    ('edit', 'edit.apply', {'patch': 'quest'}, 'include a quest'),
    ('edit', 'edit.apply', {'patch': 'quest'}, 'give it a quest'),
    ('edit', 'edit.apply', {'patch': 'sound'}, 'turn on sound'),
    ('edit', 'edit.apply', {'patch': 'sound'}, 'include sound effects'),
    ('edit', 'edit.apply', {'patch': 'day-night'}, 'make it day and night'),
    ('edit', 'edit.apply', {'patch': 'double-jump'}, 'let the player double jump'),
    ('edit', 'edit.apply', {'patch': 'double-jump'}, 'enable double jump'),
    ('edit', 'edit.apply', {'patch': 'enemy-types'}, 'add more enemy types'),
    ('edit', 'edit.apply', {'patch': 'enemy-types'}, 'include multiple enemy types'),
    ('edit', 'edit.apply', {'patch': 'three-d'}, 'switch it to 3d'),
    ('edit', 'edit.apply', {'patch': 'world'}, 'add a new world'),
    ('edit', 'edit.apply', {'patch': 'world'}, 'expand the world'),
    ('edit', 'edit.apply', {'patch': 'world'}, 'add another world'),
    ('projects', 'project.open', {'slug': '$1'}, 'go to project {slug}'),
    ('projects', 'project.export', {}, 'save this project as a bundle'),
    ('projects', 'project.export', {}, 'download this project'),
    ('projects', 'project.files', {}, 'list the files in this project'),
    ('projects', 'project.files', {}, 'show the files of this project'),
    ('projects', 'project.list', {}, 'show all projects'),
    ('context', 'context.show', {}, 'show me the context'),
    ('context', 'context.show', {}, 'context please'),
    ('context', 'context.snapshot', {}, 'take a snapshot of the context'),
    ('context', 'context.clear', {}, 'wipe context'),
    ('context', 'context.continue', {}, 'run the rest'),
    ('context', 'context.diff', {}, 'show what changed in context'),
    ('context', 'context.diff', {}, 'compare context with the previous snapshot'),
    ('memory', 'memory.remember', {'key': '$1', 'value': '$2'}, "don't forget that {key} is {value}"),
    ('memory', 'memory.note', {'text': '$1'}, 'note that {text}'),
    ('memory', 'memory.note', {'text': '$1'}, 'write down that {text}'),
    ('memory', 'memory.note', {'text': '$1'}, 'add a note that {text}'),
    ('memory', 'memory.forget', {'key': '$1'}, 'drop my {key} from memory'),
    ('memory', 'memory.forget', {'key': '$1'}, 'delete my {key}'),
    ('memory', 'memory.list', {}, 'list what you remember'),
    ('memory', 'memory.list', {}, 'show me your memory'),
    ('memory', 'memory.list', {}, 'show me what you remember'),
    ('math', 'math.unary', {'op': 'sqrt', 'a': '$1'}, "what's the square root of {a}"),
    ('math', 'math.unary', {'op': 'sqrt', 'a': '$1'}, 'whats the square root of {a}'),
    ('math', 'math.unary', {'op': 'sqrt', 'a': '$1'}, 'give me the square root of {a}'),
    ('math', 'math.unary', {'op': 'sqrt', 'a': '$1'}, 'find the square root of {a}'),
    ('math', 'math.unary', {'op': 'sqrt', 'a': '$1'}, 'tell me the square root of {a}'),
    ('math', 'math.unary', {'op': 'cbrt', 'a': '$1'}, 'what is the cube root of {a}'),
    ('math', 'math.unary', {'op': 'cbrt', 'a': '$1'}, "what's the cube root of {a}"),
    ('math', 'math.unary', {'op': 'cbrt', 'a': '$1'}, 'give me the cube root of {a}'),
    ('math', 'math.unary', {'op': 'factors', 'a': '$1'}, 'what are the factors of {a}'),
    ('math', 'math.unary', {'op': 'factors', 'a': '$1'}, 'give me the factors of {a}'),
    ('math', 'math.unary', {'op': 'factors', 'a': '$1'}, 'find the factors of {a}'),
    ('math', 'math.unary', {'op': 'primefactors', 'a': '$1'}, 'what are the prime factors of {a}'),
    ('math', 'math.unary', {'op': 'primefactors', 'a': '$1'}, 'give me the prime factors of {a}'),
    ('math', 'math.unary', {'op': 'primefactors', 'a': '$1'}, 'list the prime factors of {a}'),
    ('math', 'math.list', {'op': 'mean', 'list': '$1'}, 'what is the mean of {list}'),
    ('math', 'math.list', {'op': 'mean', 'list': '$1'}, 'give me the average of {list}'),
    ('math', 'math.list', {'op': 'mean', 'list': '$1'}, 'find the average of {list}'),
    ('math', 'math.list', {'op': 'mean', 'list': '$1'}, 'what is the average value of {list}'),
    ('math', 'math.list', {'op': 'median', 'list': '$1'}, 'what is the middle value of {list}'),
    ('math', 'math.list', {'op': 'median', 'list': '$1'}, 'give me the median of {list}'),
    ('math', 'math.list', {'op': 'median', 'list': '$1'}, 'find the median of {list}'),
    ('math', 'math.list', {'op': 'sum', 'list': '$1'}, 'give me the total of {list}'),
    ('math', 'math.list', {'op': 'sum', 'list': '$1'}, 'what do {list} add up to'),
    ('math', 'math.expr', {'expr': '$1+$2'}, 'what is {a} plus {b} exactly'),
    ('math', 'math.expr', {'expr': '$1+$2'}, 'give me {a} plus {b}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'peek at {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'show the file {path}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'open the file {path}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'load {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'fetch {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'dump {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'output {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'give me {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'show me the text in {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'show me the text of {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'read me {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'print the contents of {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'print the file {path}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'display the contents of {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'let me read {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'what does {file} say'),
    ('files', 'fs.read_file', {'path': '$1'}, 'what is inside {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'show the text in {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'open the document {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'read the document {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'show the document {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'give me the contents of {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'read out {file}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'show me the file {path}'),
    ('files', 'fs.read_file', {'path': '$1'}, 'print out the contents of {file}'),
    ('files', 'fs.list_dir', {}, "what's here"),
    ('files', 'fs.list_dir', {}, 'what is here'),
    ('files', 'fs.list_dir', {}, 'list files'),
    ('files', 'fs.list_dir', {}, 'show files'),
    ('files', 'fs.list_dir', {}, 'show the files'),
    ('files', 'fs.list_dir', {}, 'what files are in this directory'),
    ('files', 'fs.list_dir', {}, 'list the contents of this folder'),
    ('files', 'fs.list_dir', {}, 'show the contents of this folder'),
    ('files', 'fs.list_dir', {}, "what's in the directory"),
    ('files', 'fs.list_dir', {}, 'what is in the current folder'),
    ('files', 'fs.list_dir', {}, 'list the current folder'),
    ('files', 'fs.list_dir', {}, 'show me the files here'),
    ('files', 'fs.list_dir', {}, 'show me the files'),
    ('files', 'fs.list_dir', {}, "what's in here"),
    ('files', 'fs.list_dir', {}, 'list the contents'),
    ('files', 'fs.list_dir', {}, 'show the contents'),
    ('files', 'fs.list_dir', {}, 'what files do i have here'),
    ('files', 'fs.list_dir', {}, 'list the folder'),
    ('files', 'fs.list_dir', {}, 'show the folder'),
    ('files', 'fs.list_dir', {}, "what's in the working directory"),
    ('files', 'fs.list_dir', {}, "show me what's here"),
    ('files', 'fs.list_dir', {}, 'list all files'),
    ('files', 'fs.list_dir', {}, 'show all files'),
    ('files', 'fs.list_dir', {}, 'what files are there'),
    ('growth', 'module.expand', {'module': 'core'}, 'develop the core module'),
    ('growth', 'module.expand', {'module': 'core'}, 'add to the core module'),
    ('growth', 'module.expand', {'module': 'core'}, 'make the core module bigger'),
    ('growth', 'module.expand', {'module': 'ui'}, 'develop the ui module'),
    ('growth', 'module.expand', {'module': 'ui'}, 'add to the ui module'),
    ('growth', 'module.expand', {'module': 'ui'}, 'make the ui module bigger'),
    ('growth', 'module.expand', {'module': 'data'}, 'develop the data module'),
    ('growth', 'module.expand', {'module': 'data'}, 'add to the data module'),
    ('growth', 'module.expand', {'module': 'data'}, 'make the data module bigger'),
    ('growth', 'module.expand', {'module': 'content'}, 'develop the content module'),
    ('growth', 'module.expand', {'module': 'content'}, 'add to the content module'),
    ('growth', 'module.expand', {'module': 'content'}, 'make the content module bigger'),
    ('growth', 'system.add', {'system': 'inventory'}, 'add an inventory system to the project'),
    ('growth', 'system.add', {'system': 'inventory'}, 'add inventory mechanics to the project'),
    ('growth', 'system.add', {'system': 'inventory'}, 'give the project an inventory system'),
    ('growth', 'system.add', {'system': 'dialogue'}, 'add a dialogue system to the project'),
    ('growth', 'system.add', {'system': 'dialogue'}, 'add dialogue mechanics to the project'),
    ('growth', 'system.add', {'system': 'dialogue'}, 'give the project a dialogue system'),
    ('growth', 'system.add', {'system': 'combat'}, 'add a combat system to the project'),
    ('growth', 'system.add', {'system': 'combat'}, 'add combat mechanics to the project'),
    ('growth', 'system.add', {'system': 'combat'}, 'give the project a combat system'),
    ('growth', 'system.add', {'system': 'save'}, 'add a save system to the project'),
    ('growth', 'system.add', {'system': 'save'}, 'add save mechanics to the project'),
    ('growth', 'system.add', {'system': 'save'}, 'give the project a save system'),
    ('growth', 'system.add', {'system': 'quests'}, 'add a quest system to the project'),
    ('growth', 'system.add', {'system': 'quests'}, 'add quest mechanics to the project'),
    ('growth', 'system.add', {'system': 'quests'}, 'give the project a quest system'),
    ('growth', 'system.add', {'system': 'crafting'}, 'add a crafting system to the project'),
    ('growth', 'system.add', {'system': 'crafting'}, 'add crafting mechanics to the project'),
    ('growth', 'system.add', {'system': 'crafting'}, 'give the project a crafting system'),
    ('growth', 'system.add', {'system': 'ui'}, 'add a ui system to the project'),
    ('growth', 'system.add', {'system': 'ui'}, 'add ui mechanics to the project'),
    ('growth', 'system.add', {'system': 'ui'}, 'give the project a ui system'),
    ('growth', 'system.add', {'system': 'audio'}, 'add an audio system to the project'),
    ('growth', 'system.add', {'system': 'audio'}, 'add audio mechanics to the project'),
    ('growth', 'system.add', {'system': 'audio'}, 'give the project an audio system'),
    ('growth', 'system.add', {'system': 'weather'}, 'add a weather system to the project'),
    ('growth', 'system.add', {'system': 'weather'}, 'add weather mechanics to the project'),
    ('growth', 'system.add', {'system': 'weather'}, 'give the project a weather system'),
    ('growth', 'system.add', {'system': 'particles'}, 'add a particle system to the project'),
    ('growth', 'system.add', {'system': 'particles'}, 'add particle mechanics to the project'),
    ('growth', 'system.add', {'system': 'particles'}, 'give the project a particle system'),
    ('growth', 'system.add', {'system': 'ai'}, 'add an ai system to the project'),
    ('growth', 'system.add', {'system': 'ai'}, 'add ai mechanics to the project'),
    ('growth', 'system.add', {'system': 'ai'}, 'give the project an ai system'),
    ('extract', 'text.extract', {'what': 'emails', 'text': '$1'}, 'pull out the emails from {text}'),
    ('extract', 'text.extract', {'what': 'emails', 'text': '$1'}, 'get the emails from {text}'),
    ('extract', 'text.extract', {'what': 'emails', 'text': '$1'}, 'extract all emails from {text}'),
    ('extract', 'text.extract', {'what': 'emails', 'text': '$1'}, 'grab all the emails from {text}'),
    ('extract', 'text.extract', {'what': 'emails', 'text': '$1'}, 'show me the emails in {text}'),
    ('extract', 'text.extract', {'what': 'urls', 'text': '$1'}, 'pull out the links from {text}'),
    ('extract', 'text.extract', {'what': 'urls', 'text': '$1'}, 'get the links from {text}'),
    ('extract', 'text.extract', {'what': 'urls', 'text': '$1'}, 'extract all links from {text}'),
    ('extract', 'text.extract', {'what': 'urls', 'text': '$1'}, 'grab all the links from {text}'),
    ('extract', 'text.extract', {'what': 'urls', 'text': '$1'}, 'get the urls out of {text}'),
    ('extract', 'text.extract', {'what': 'urls', 'text': '$1'}, 'show me the links in {text}'),
    ('extract', 'text.extract', {'what': 'numbers', 'text': '$1'}, 'pull out the numbers from {text}'),
    ('extract', 'text.extract', {'what': 'numbers', 'text': '$1'}, 'get the numbers from {text}'),
    ('extract', 'text.extract', {'what': 'numbers', 'text': '$1'}, 'extract all numbers from {text}'),
    ('extract', 'text.extract', {'what': 'numbers', 'text': '$1'}, 'grab all the numbers from {text}'),
    ('extract', 'text.headings', {'text': '$1'}, 'pull out the headings from {text}'),
    ('extract', 'text.headings', {'text': '$1'}, 'list all the headings in {text}'),
    ('extract', 'text.headings', {'text': '$1'}, 'show me the headings in {text}'),
    ('extract', 'text.facts', {'text': '$1'}, 'list all the key facts in {text}'),
    ('extract', 'text.facts', {'text': '$1'}, 'show me the key facts in {text}'),
    ('extract', 'text.count', {'what': 'words', 'text': '$1'}, 'tell me the word count of {text}'),
    ('extract', 'text.count', {'what': 'words', 'text': '$1'}, 'how many words does {text} contain'),
    ('extract', 'text.count', {'what': 'words', 'text': '$1'}, 'how many words does {text} have'),
    ('extract', 'text.count', {'what': 'lines', 'text': '$1'}, 'tell me the line count of {text}'),
    ('extract', 'text.count', {'what': 'lines', 'text': '$1'}, 'how many lines does {text} have'),
    ('extract', 'text.summarize', {'text': '$1'}, 'give me a short summary of {text}'),
    ('extract', 'text.summarize', {'text': '$1'}, 'write a summary of {text}'),
    ('build', 'build', {'kind': 'platformer'}, "let's build a platformer"),
    ('build', 'build', {'kind': 'platformer'}, 'can you build me a platformer'),
    ('build', 'build', {'kind': 'platformer'}, 'i want to build a platformer'),
    ('build', 'build', {'kind': 'platformer'}, "i'd like to build a platformer"),
    ('build', 'build', {'kind': 'shooter'}, "let's build a shooter"),
    ('build', 'build', {'kind': 'shooter'}, 'can you build me a shooter'),
    ('build', 'build', {'kind': 'shooter'}, 'i want to build a shooter'),
    ('build', 'build', {'kind': 'rpg'}, "let's build an rpg"),
    ('build', 'build', {'kind': 'rpg'}, 'can you build me an rpg'),
    ('build', 'build', {'kind': 'rpg'}, 'i want to build an rpg'),
    ('build', 'build', {'kind': 'dashboard'}, "let's build a dashboard"),
    ('build', 'build', {'kind': 'dashboard'}, 'can you build me a dashboard'),
    ('build', 'build', {'kind': 'dashboard'}, 'i want to build a dashboard'),
    ('build', 'build', {'kind': 'landing page'}, "let's build a landing page"),
    ('build', 'build', {'kind': 'landing page'}, 'can you build me a landing page'),
    ('build', 'build', {'kind': 'landing page'}, 'i want to build a landing page'),
    ('edit', 'edit.apply', {'patch': 'boss'}, 'add a big boss'),
    ('edit', 'edit.apply', {'patch': 'boss'}, 'add a boss enemy'),
    ('edit', 'edit.apply', {'patch': 'quest'}, 'add a side quest'),
    ('edit', 'edit.apply', {'patch': 'quest'}, 'add a new quest'),
    ('edit', 'edit.apply', {'patch': 'sound'}, 'add sound to the game'),
    ('edit', 'edit.apply', {'patch': 'sound'}, 'add audio effects'),
    ('edit', 'edit.apply', {'patch': 'sound'}, 'add game audio'),
    ('edit', 'edit.apply', {'patch': 'day-night'}, 'add a day and night cycle'),
    ('edit', 'edit.apply', {'patch': 'day-night'}, 'make it change from day to night'),
    ('edit', 'edit.apply', {'patch': 'harder'}, 'make it harder to play'),
    ('edit', 'edit.apply', {'patch': 'harder'}, 'make the game more difficult'),
    ('edit', 'edit.apply', {'patch': 'three-d'}, 'upgrade it to 3d'),
    ('edit', 'edit.apply', {'patch': 'isometric'}, 'make the view isometric'),
    ('edit', 'edit.apply', {'patch': 'isometric'}, 'change it to isometric'),
    ('projects', 'project.list', {}, 'show me my projects'),
    ('projects', 'project.list', {}, 'list all projects'),
    ('projects', 'project.list', {}, 'which projects do i have'),
    ('projects', 'project.files', {}, 'show this project files'),
    ('projects', 'project.files', {}, 'list this project files'),
    ('projects', 'project.files', {}, 'what is in this project'),
    ('projects', 'project.files', {}, 'show me the project files'),
    ('projects', 'project.export', {}, 'export this project as a bundle'),
    ('projects', 'project.export', {}, 'package this project'),
    ('projects', 'project.export', {}, 'save the project'),
    ('context', 'context.show', {}, 'what does the context say'),
    ('context', 'context.show', {}, 'print the context'),
    ('context', 'context.show', {}, 'give me the context'),
    ('context', 'context.clear', {}, 'erase the context'),
    ('context', 'context.clear', {}, 'throw away the context'),
    ('context', 'context.compact', {}, 'make the context smaller'),
    ('context', 'context.compact', {}, 'reduce the context'),
    ('memory', 'memory.list', {}, 'what facts do you have'),
    ('memory', 'memory.list', {}, 'list your memory'),
    ('memory', 'memory.list', {}, 'show your saved notes'),
    ('memory', 'memory.list', {}, 'what notes do you have'),
    ('memory', 'memory.note', {'text': '$1'}, 'remember the note {text}'),
    ('memory', 'memory.note', {'text': '$1'}, 'save a note about {text}'),
    ('memory', 'memory.note', {'text': '$1'}, 'keep a note that {text}'),
    ('memory', 'memory.forget', {'key': '$1'}, 'remove the memory of my {key}'),
    ('memory', 'memory.forget', {'key': '$1'}, 'delete the note about my {key}'),
]

DEPTH_FAMILIES = ("math", "files", "growth", "extract", "build", "edit",
                  "projects", "context", "memory")
DEPTH_CATS = {"math": "math", "files": "files", "growth": "edit",
              "extract": "text", "build": "build", "edit": "edit",
              "projects": "project", "context": "context", "memory": "memory"}


def _depth_pack():
    groups = {}
    for family, op, args, display in DEPTH:
        groups.setdefault(family, []).append((display, op, args))
    out = []
    for family in DEPTH_FAMILIES:
        out.extend(_generated(family, groups.get(family, []),
                              DEPTH_CATS[family]))
    return out


MATH_WRAPPERS = ["can you tell me", "could you tell me", "please tell me",
                 "do you know"]


def _math():
    out = []
    for op, templates in MATH.items():
        # Prefix the existing "tell me what ..." form so a polite wrapper does
        # not need a second hand-written table. Strip the leading "tell me "
        # first: the wrapper already carries it, and keeping both produced
        # "can you tell me tell me what ...", which no one types. Every wrapper
        # keeps the same capture order and the same expected arguments.
        expanded = list(templates)
        for pattern, argmap in templates:
            if pattern.startswith("tell me what "):
                body = pattern[len("tell me "):]
                for form in MATH_WRAPPERS:
                    expanded.append((form + " " + body, argmap))
        for pattern, argmap in expanded:
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
        + _literal("context", "context.diff", CONTEXT_CORES[5:7], IMPERATIVE, "context")
        + _literal("context", "context.compact", CONTEXT_CORES[7:], IMPERATIVE, "context")
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
        + _depth_pack()
    )


def _pattern_key(pattern):
    """Whitespace-insensitive key shared with `build_commands.add()`."""
    return re.sub(r"\s+", "", pattern.lower().replace("\\ ", " "))


def _base_keys():
    """Pattern keys already shipped before the everyday layer.

    The checked-in catalog is the only honest source here: the everyday layer
    is appended after every original command, so a phrase that the base catalog
    already matches would be shadowed and must not enter the fixture. The build
    passes the live key set instead of re-reading the file.
    """
    if not COMMANDS.exists():
        return set()
    doc = json.loads(COMMANDS.read_text(encoding="utf-8"))
    keys = set()
    for command in doc.get("commands", []):
        if str(command.get("id", "")).startswith("everyday."):
            break
        keys.add(_pattern_key(command["re"]))
    return keys


def entries(exclude=None):
    """Unique catalog entries, in generation order.

    `exclude` is the set of pattern keys already present before this layer.
    Skipping them keeps the fixture identical to the shipped catalog and makes
    the exact lane honest: a redundant phrasing never shadows its own route.
    """
    if exclude is None:
        exclude = _base_keys()
    seen = set()
    counts = {}
    for entry in _all():
        key = _pattern_key(entry["re"])
        if key in exclude or key in seen:
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

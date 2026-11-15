#!/usr/bin/env python3
"""Synonym and paraphrase tables (step 48).

One checked-in table, `toolrx/paraphrase.json`, is the only source of
paraphrase expansion. It is keyed by intent and has two consumers:

* `toolrx/build_commands.py` expands the `exact` templates (with synonyms) into
  catalog routes, so the exact matcher recognises the new phrasings;
* `toolrx/builder.py` appends the `knowledge` lines to the tool's training text
  before the centroid is built, so the hashed router learns the same language.

The table is validated, expanded deterministically, and exported to
`tests/fixtures/paraphrase.json`:

    python3 toolrx/paraphrase.py --write   # refresh the fixture
    python3 toolrx/paraphrase.py --check   # fail if the fixture drifted
"""

import argparse
import hashlib
import itertools
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TABLE = ROOT / "paraphrase.json"
CATALOG = ROOT / "catalog.json"
FIXTURE = ROOT.parent / "tests" / "fixtures" / "paraphrase.json"
EVAL = ROOT.parent / "tests" / "fixtures" / "paraphrase_eval.json"

# Capture patterns mirror the catalog builder. Synonyms expand first, so every
# remaining `{name}` is a capture with a fixed position.
N = (r"(-?(?:\d[\d,]*(?:\.\d+)?|\d*\.\d+|zero|one|two|three|four|five|six|"
     r"seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
     r"seventeen|eighteen|nineteen|twenty))")
TXT = r"(.+?)"
REST = r"(.+)"
LIST_RE = (r"(-?\d[\d,]*(?:\.\d+)?(?:\s*(?:,|and|;|\s)\s*"
           r"-?\d[\d,]*(?:\.\d+)?)+)")
CAPTURES = {
    "a": N,
    "b": N,
    "n": N,
    "text": TXT,
    "text2": TXT,
    "key": TXT,
    "value": TXT,
    "name": TXT,
    "slug": TXT,
    "find": TXT,
    "repl": TXT,
    "list": LIST_RE,
    "topic": REST,
}

MAX_EXACT_PER_INTENT = 64
MAX_EXACT_TOTAL = 512
MAX_KNOWLEDGE_PER_INTENT = 16
_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_CAPTURE_ARG = re.compile(r"^\$(\d+)$")


def load(path=TABLE):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _fail(message):
    raise ValueError("paraphrase table: " + message)


def _check_string(value, where):
    if not isinstance(value, str) or not value.strip():
        _fail(where + " must be a non-empty string")
    return value


def _synonyms(table):
    synonyms = table.get("synonyms")
    if not isinstance(synonyms, dict):
        _fail("synonyms must be an object")
    out = {}
    for key, values in synonyms.items():
        _check_string(key, "synonym key")
        if key in CAPTURES:
            _fail("synonym %r shadows a capture name" % key)
        if not isinstance(values, list) or not values:
            _fail("synonym %r must be a non-empty list" % key)
        seen = []
        for value in values:
            _check_string(value, "synonym %r value" % key)
            if value not in seen:
                seen.append(value)
        out[key] = seen
    return out


def expand(text, synonyms):
    """Expand every synonym placeholder, preserving table order."""
    keys = []
    for key in _PLACEHOLDER.findall(text):
        if key in synonyms and key not in keys:
            keys.append(key)
    if not keys:
        return [text]
    out = []
    for combo in itertools.product(*(synonyms[key] for key in keys)):
        value = text
        for key, choice in zip(keys, combo):
            value = value.replace("{" + key + "}", choice)
        out.append(value)
    return out


def compile_template(text):
    """Return (anchored regex, capture names) for one expanded template."""
    captures = []
    for key in _PLACEHOLDER.findall(text):
        if key in captures:
            _fail("template %r repeats capture {%s}" % (text, key))
        if key not in CAPTURES:
            _fail("template %r has unknown placeholder {%s}" % (text, key))
        captures.append(key)
    regex = text
    for key in captures:
        regex = regex.replace("{" + key + "}", CAPTURES[key], 1)
    return "^" + regex + "$", captures


def _intents(table, synonyms):
    intents = table.get("intents")
    if not isinstance(intents, dict) or not intents:
        _fail("intents must be a non-empty object")
    tools = {tool["name"] for tool in load(CATALOG)["tools"]}
    out = {}
    total = 0
    global_seen = {}
    for key, intent in intents.items():
        _check_string(key, "intent key")
        if not isinstance(intent, dict):
            _fail("intent %r must be an object" % key)
        tool = intent.get("tool")
        if tool is not None:
            _check_string(tool, "intent %r tool" % key)
            if tool not in tools:
                _fail("intent %r names unknown tool %r" % (key, tool))
        exact = intent.get("exact", [])
        knowledge = intent.get("knowledge", [])
        if not isinstance(exact, list):
            _fail("intent %r exact must be a list" % key)
        if not isinstance(knowledge, list):
            _fail("intent %r knowledge must be a list" % key)
        if len(knowledge) > MAX_KNOWLEDGE_PER_INTENT:
            _fail("intent %r has more than %d knowledge lines"
                  % (key, MAX_KNOWLEDGE_PER_INTENT))
        expanded = []
        for template in exact:
            if not isinstance(template, dict):
                _fail("intent %r exact entry must be an object" % key)
            text = _check_string(template.get("text"), "intent %r text" % key)
            op = _check_string(template.get("op"), "intent %r op" % key)
            args = template.get("args", {})
            if not isinstance(args, dict):
                _fail("intent %r args must be an object" % key)
            for arg_key, arg_value in args.items():
                _check_string(arg_key, "intent %r arg name" % key)
                _check_string(arg_value, "intent %r arg value" % key)
            for phrase in expand(text, synonyms):
                regex, captures = compile_template(phrase)
                used = set()
                for arg_key, arg_value in args.items():
                    match = _CAPTURE_ARG.match(arg_value)
                    if not match:
                        continue
                    index = int(match.group(1))
                    if index < 1 or index > len(captures):
                        _fail("intent %r arg %r points at $%d but %r has %d "
                              "captures" % (key, arg_key, index, phrase,
                                            len(captures)))
                    used.add(captures[index - 1])
                missing = [name for name in captures if name not in used]
                if missing:
                    _fail("intent %r template %r never uses capture(s) %s"
                          % (key, phrase, ", ".join(missing)))
                expanded.append({"text": phrase, "op": op,
                                 "args": dict(args), "re": regex,
                                 "captures": captures})
        if len(expanded) > MAX_EXACT_PER_INTENT:
            _fail("intent %r expands to more than %d exact routes"
                  % (key, MAX_EXACT_PER_INTENT))
        total += len(expanded)
        seen = set()
        for item in expanded:
            marker = re.sub(r"\s+", "", item["text"].lower())
            if marker in seen:
                _fail("intent %r expands %r twice" % (key, item["text"]))
            if marker in global_seen:
                _fail("intent %r duplicates %r from %r"
                      % (key, item["text"], global_seen[marker]))
            seen.add(marker)
            global_seen[marker] = key
        for line in knowledge:
            _check_string(line, "intent %r knowledge line" % key)
        out[key] = {"tool": tool, "exact": expanded,
                    "knowledge": list(knowledge)}
    if total > MAX_EXACT_TOTAL:
        _fail("table expands to more than %d exact routes" % MAX_EXACT_TOTAL)
    return out


def table(path=TABLE):
    """Load, validate, and return (raw table, expanded intents)."""
    raw = load(path)
    if raw.get("version") != 1:
        _fail("unsupported version %r" % raw.get("version"))
    synonyms = _synonyms(raw)
    return raw, _intents(raw, synonyms)


def entries(path=TABLE):
    """Yield catalog entries for every expanded exact template."""
    _, intents = table(path)
    counts = {}
    for key, intent in intents.items():
        for item in intent["exact"]:
            counts[key] = counts.get(key, 0) + 1
            yield {
                "id": "paraphrase.%s.%d" % (key, counts[key]),
                "op": item["op"],
                "re": item["re"],
                "args": item["args"],
                "d": item["text"],
                "c": item["op"].split(".")[0],
            }


def knowledge(tool, path=TABLE):
    """Return the paraphrase lines for one router tool, in table order."""
    _, intents = table(path)
    out = []
    for intent in intents.values():
        if intent["tool"] == tool:
            for line in intent["knowledge"]:
                if line not in out:
                    out.append(line)
    return out


def export(path=TABLE):
    """Deterministic export of the table, its expansion, and counts."""
    raw, intents = table(path)
    out = {}
    exact_total = 0
    knowledge_total = 0
    for key in sorted(intents):
        intent = intents[key]
        exact = [
            {"text": item["text"], "op": item["op"],
             "args": dict(sorted(item["args"].items()))}
            for item in intent["exact"]
        ]
        exact.sort(key=lambda item: item["text"])
        lines = list(intent["knowledge"])
        out[key] = {"tool": intent["tool"], "exact": exact,
                    "knowledge": lines}
        exact_total += len(exact)
        knowledge_total += len(lines)
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    return {
        "version": 1,
        "tableSha256": hashlib.sha256(canonical).hexdigest(),
        "synonyms": {key: list(values)
                     for key, values in sorted(_synonyms(raw).items())},
        "intents": out,
        "counts": {
            "intents": len(out),
            "exact": exact_total,
            "knowledge": knowledge_total,
        },
    }


def _fill_args(command, query):
    import coverage
    match = re.match(command["re"], coverage.normalize_query(query), re.I)
    if not match:
        return None
    out = {}
    for key, value in command["args"].items():
        if isinstance(value, str) and _CAPTURE_ARG.match(value):
            out[key] = match.group(int(value[1:]))
        elif isinstance(value, str):
            out[key] = re.sub(r"\$(\d+)",
                              lambda hit: match.group(int(hit.group(1))),
                              value)
        else:
            out[key] = value
    return out


def measure(eval_path=EVAL):
    """Measure the fixed prompt set before and after the table expansion.

    The baseline model is built with ``expand=False``; the expanded model is
    built from the same catalog and knowledge plus the table's knowledge
    lines. Exact-lane prompts measure the exact matcher; router-lane prompts
    measure the hashed router's margin. Both models are built in a temporary
    directory, so the checked-in model cannot skew the result.
    """
    import os
    import shutil
    import statistics
    import tempfile
    import builder
    import coverage
    import router
    import security

    prompts = json.loads(pathlib.Path(eval_path).read_text(encoding="utf-8"))
    if prompts.get("version") != 1:
        _fail("unsupported evaluation version %r" % prompts.get("version"))
    cases = prompts.get("prompts", [])
    commands = json.loads((ROOT / "web" / "commands.json")
                          .read_text(encoding="utf-8"))["commands"]
    base_commands = [c for c in commands
                     if not c["id"].startswith("paraphrase.")]
    policy = security.SecurityPolicy.load()

    temp = tempfile.mkdtemp(prefix="toolrx-paraphrase-")
    try:
        base_dir = os.path.join(temp, "baseline")
        expanded_dir = os.path.join(temp, "expanded")
        for directory in (base_dir, expanded_dir):
            os.makedirs(directory)
            shutil.copy2(CATALOG, os.path.join(directory, "catalog.json"))
            shutil.copytree(ROOT / "knowledge",
                            os.path.join(directory, "knowledge"))
        base_path = builder.build(os.path.join(base_dir, "catalog.json"),
                                  expand=False)
        expanded_path = builder.build(os.path.join(expanded_dir,
                                                   "catalog.json"),
                                      expand=True)
        baseline = router.load(base_path)
        expanded = router.load(expanded_path)
        before_index = coverage.PrefixIndex(base_commands)
        after_index = coverage.PrefixIndex(commands)

        exact_before = exact_after = exact_total = 0
        margins_before = []
        margins_after = []
        router_before = router_after = router_total = 0
        for case in cases:
            lane = case.get("lane")
            query = case["query"]
            if lane == "exact":
                exact_total += 1
                for index, name in ((before_index, "before"),
                                    (after_index, "after")):
                    hit = index.first_match(query)
                    ok = bool(hit and hit["op"] == case.get("op")
                              and _fill_args(hit, query) == case.get("args"))
                    if name == "before":
                        exact_before += ok
                    else:
                        exact_after += ok
            elif lane == "router":
                router_total += 1
                d0 = router.route(policy.normalize(query), baseline)
                d1 = router.route(policy.normalize(query), expanded)
                margins_before.append(d0["margin"])
                margins_after.append(d1["margin"])
                router_before += d0["tool"] == case.get("tool")
                router_after += d1["tool"] == case.get("tool")
            else:
                _fail("unknown evaluation lane %r" % lane)
        return {
            "cases": len(cases),
            "exact": {
                "total": exact_total,
                "before": exact_before,
                "after": exact_after,
                "rate_before": round(exact_before / exact_total, 4)
                if exact_total else 0.0,
                "rate_after": round(exact_after / exact_total, 4)
                if exact_total else 0.0,
            },
            "router": {
                "total": router_total,
                "hits_before": router_before,
                "hits_after": router_after,
                "median_margin_before": round(
                    statistics.median(margins_before), 4),
                "median_margin_after": round(
                    statistics.median(margins_after), 4),
            },
            "model_bytes": {
                "before": os.path.getsize(base_path),
                "after": os.path.getsize(expanded_path),
            },
        }
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh tests/fixtures/paraphrase.json")
    group.add_argument("--check", action="store_true",
                       help="fail if the fixture drifted")
    group.add_argument("--measure", action="store_true",
                       help="measure the fixed prompt set before and after")
    args = parser.parse_args(argv)
    if args.measure:
        print(json.dumps(measure(), indent=2))
        return 0
    doc = export()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        print("wrote %s (%d intents, %d exact, %d knowledge)"
              % (FIXTURE.relative_to(ROOT.parent), doc["counts"]["intents"],
                 doc["counts"]["exact"], doc["counts"]["knowledge"]))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("missing fixture; run --write", file=sys.stderr)
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != doc:
            print("paraphrase fixture drifted; run --write", file=sys.stderr)
            return 1
        print("paraphrase fixture is current")
        return 0
    print(json.dumps(doc["counts"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

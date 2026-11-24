#!/usr/bin/env python3
"""Named plan macros (step 67).

One checked-in table, `toolrx/macros.json`, is the only source of the
`macro.*` routes and the expansion data. A macro is a literal, non-recursive
list of plan steps; it is never expanded again. `toolrx/web/macros.js` is the
byte-identical browser twin, and `tests/fixtures/macros.json` pins both.

The existing plan limits do the work: `planSteps` caps the expanded step count
and `planChars` caps the joined text. A step that invokes another macro is
refused before anything runs, so recursion cannot happen.

    python3 toolrx/macros.py --write   # refresh the fixture
    python3 toolrx/macros.py --check   # fail if the fixture drifted
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TABLE = ROOT / "macros.json"
FIXTURE = ROOT.parent / "tests" / "fixtures" / "macros.json"

DEFAULT_LIMITS = {"steps": 40, "chars": 8000, "single": 2000}

RUN = [
    "run macro {name}",
    "use macro {name}",
    "invoke macro {name}",
    "run the {name} macro",
]
PREVIEW = [
    "preview macro {name}",
    "preview the {name} macro",
    "show macro {name}",
    "expand macro {name}",
]

# A named route is generated for every known macro so the exact phrase wins.
# These generic routes follow them and turn an unknown name into a named
# refusal instead of a router fallback.
GENERIC = [
    ("run", "run macro (.+)", "macro.run"),
    ("use", "use macro (.+)", "macro.run"),
    ("invoke", "invoke macro (.+)", "macro.run"),
    ("run-the", "run the (.+) macro", "macro.run"),
    ("preview", "preview macro (.+)", "macro.preview"),
    ("preview-the", "preview the (.+) macro", "macro.preview"),
    ("show", "show macro (.+)", "macro.preview"),
    ("expand", "expand macro (.+)", "macro.preview"),
]

_MACRO_INVOKE = re.compile(
    r"^\s*(?:(?:run|use|invoke|apply|preview|show|expand)\s+"
    r"(?:the\s+)?macro\b"
    r"|(?:run|use|invoke|apply|preview|show|expand)\s+the\s+.+?\s+macro\s*$"
    r"|macro\b)",
    re.I)
_SPLIT = re.compile(r"\s*(?:\||;|\bthen\b|\n)\s*", re.I)


def load(path=TABLE):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _fail(message):
    raise ValueError("macro table: " + message)


def _norm(text):
    return re.sub(r"\s+", " ", str(text if text is not None else "")).strip().lower()


def _one_line(value, where):
    if not isinstance(value, str) or not value.strip():
        _fail(where + " must be a non-empty string")
    if "\n" in value or "\r" in value:
        _fail(where + " must be one line")
    return value.strip()


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", _norm(text)).strip("-")


def _macros(table):
    raw = table.get("macros")
    if not isinstance(raw, list) or not raw:
        _fail("macros must be a non-empty list")
    out = []
    seen = {}
    for index, spec in enumerate(raw):
        where = "macros[%d]" % index
        if not isinstance(spec, dict):
            _fail(where + " must be an object")
        name = _one_line(spec.get("name"), where + ".name")
        summary = _one_line(spec.get("summary"), where + ".summary")
        steps = spec.get("steps")
        if not isinstance(steps, list) or not steps:
            _fail(where + ".steps must be a non-empty list")
        clean = []
        for step_index, step in enumerate(steps):
            clean.append(_one_line(step, "%s.steps[%d]" % (where, step_index)))
        aliases = spec.get("aliases", [])
        if not isinstance(aliases, list):
            _fail(where + ".aliases must be a list")
        clean_aliases = []
        for alias_index, alias in enumerate(aliases):
            clean_aliases.append(_one_line(
                alias, "%s.aliases[%d]" % (where, alias_index)))
        for phrase in [name] + clean_aliases:
            key = _norm(phrase)
            if key in seen:
                _fail("macro name or alias %r is already used by %s"
                      % (phrase, seen[key]))
            seen[key] = name
        out.append({
            "name": name,
            "aliases": clean_aliases,
            "summary": summary,
            "steps": clean,
        })
    return out


def _phrases(table):
    raw = table.get("list")
    if not isinstance(raw, list) or not raw:
        _fail("list must be a non-empty list of phrases")
    out = []
    seen = set()
    for index, phrase in enumerate(raw):
        text = _one_line(phrase, "list[%d]" % index)
        key = _norm(text)
        if key in seen:
            _fail("duplicate list phrase %r" % text)
        seen.add(key)
        out.append(text)
    return out


def _edits(table):
    raw = table.get("edit")
    if not isinstance(raw, list) or not raw:
        _fail("edit must be a non-empty list of patterns")
    out = []
    seen = set()
    for index, pattern in enumerate(raw):
        text = _one_line(pattern, "edit[%d]" % index)
        try:
            rx = re.compile(text, re.I)
        except re.error as exc:
            _fail("edit[%d] is not a valid pattern: %s" % (index, exc))
        if rx.groups != 1:
            _fail("edit[%d] must capture exactly one step list" % index)
        key = _norm(text)
        if key in seen:
            _fail("duplicate edit pattern %r" % text)
        seen.add(key)
        out.append(text)
    return out


def _entry(entry_id, op, pattern, args, desc, text):
    return {
        "id": entry_id,
        "op": op,
        "re": pattern,
        "args": args,
        "d": desc,
        "c": "macro",
        "text": text,
    }


def _all():
    table = load()
    if table.get("version") != 1:
        _fail("version must be 1")
    macros = _macros(table)
    lists = _phrases(table)
    edits = _edits(table)

    for index, text in enumerate(lists, 1):
        yield _entry(
            "macro.list.%d" % index, "macro.list",
            "^" + re.escape(text) + "$", {},
            "list the named plan macros and their literal steps", text)

    for macro in macros:
        phrases = [macro["name"]] + macro["aliases"]
        for phrase in phrases:
            slug = _slug(phrase)
            for index, template in enumerate(RUN, 1):
                text = template.format(name=phrase)
                yield _entry(
                    "macro.run.%s.%d" % (slug, index), "macro.run",
                    "^" + re.escape(text) + "$",
                    {"name": macro["name"]},
                    "run the %s macro exactly as written" % macro["name"],
                    text)
            for index, template in enumerate(PREVIEW, 1):
                text = template.format(name=phrase)
                yield _entry(
                    "macro.preview.%s.%d" % (slug, index), "macro.preview",
                    "^" + re.escape(text) + "$",
                    {"name": macro["name"]},
                    "preview the exact steps of the %s macro" % macro["name"],
                    text)

    for slug, pattern, op in GENERIC:
        sample = pattern.replace("(.+)", "standard shooter growth")
        yield _entry(
            "macro.%s.any" % slug, op, "^" + pattern + "$",
            {"name": "$1"},
            "name an unknown macro honestly instead of guessing", sample)

    for index, pattern in enumerate(edits, 1):
        sample = pattern.replace("(.+)", "add audio system | add weather system")
        yield _entry(
            "macro.edit.%d" % index, "macro.edit", pattern,
            {"steps": "$1"},
            "edit the staged macro plan without changing the macro", sample)


def entries():
    """Unique catalog entries, in generation order."""
    return _all()


def runtime():
    """The small table the browser needs; routes stay in the catalog."""
    table = load()
    if table.get("version") != 1:
        _fail("version must be 1")
    return {
        "version": 1,
        "macros": [
            {
                "name": macro["name"],
                "aliases": macro["aliases"],
                "summary": macro["summary"],
                "steps": macro["steps"],
            }
            for macro in _macros(table)
        ],
    }


# ---------------------------------------------------------------- expand ---
def _limits(limits):
    raw = limits or {}
    out = {}
    for key, fallback in DEFAULT_LIMITS.items():
        value = raw.get(key, fallback)
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = fallback
        out[key] = max(1, number)
    return out


def _result(ok, name, steps, reason=None, detail="", summary=""):
    clean = [str(step) for step in steps]
    return {
        "ok": bool(ok),
        "name": str(name),
        "summary": str(summary),
        "steps": clean,
        "total": len(clean),
        "chars": len("\n".join(clean)),
        "reason": reason,
        "detail": str(detail),
    }


def _one(text):
    return re.sub(r"\s+", " ", str(text)).strip()


def parse_steps(text):
    """Split an edited list on |, ;, newline, or the word then."""
    raw = str(text if text is not None else "").replace("\r", "")
    return [part.strip() for part in _SPLIT.split(raw) if part.strip()]


def check(name, steps, limits=None):
    """Validate a literal step list against the existing plan limits."""
    lim = _limits(limits)
    clean = [str(step) for step in (steps or [])]
    total = len(clean)
    joined = "\n".join(clean)
    if not total:
        return _result(False, name, clean, "r.macro-empty",
                       "a macro needs at least one step")
    if total > lim["steps"]:
        return _result(False, name, clean, "r.macro-steps",
                       "%d steps > planSteps %d" % (total, lim["steps"]))
    if len(joined) > lim["chars"]:
        return _result(False, name, clean, "r.macro-chars",
                       "%d chars > planChars %d" % (len(joined), lim["chars"]))
    for index, step in enumerate(clean, 1):
        if not step.strip():
            return _result(False, name, clean, "r.macro-empty-step",
                           "step %d is empty" % index)
        if len(step) > lim["single"]:
            return _result(False, name, clean, "r.macro-step-chars",
                           "step %d is %d chars > singleChars %d"
                           % (index, len(step), lim["single"]))
        if _MACRO_INVOKE.match(step):
            return _result(False, name, clean, "r.macro-recursive",
                           "step %d invokes another macro: %s"
                           % (index, _one(step)[:120]))
    return _result(True, name, clean)


def _find(macros, name):
    key = _norm(name)
    for macro in macros:
        for phrase in [macro["name"]] + macro["aliases"]:
            if _norm(phrase) == key:
                return macro
    return None


def expand(table, name, limits=None):
    """Expand one macro literally; never recurse, never execute."""
    macro = _find(_macros(table), name)
    if not macro:
        return _result(False, _one(name), [], "r.macro-missing",
                       'no macro named "%s"' % _one(name)[:120])
    result = check(macro["name"], macro["steps"], limits)
    result["summary"] = macro["summary"]
    return result


def refusal_text(result):
    name = _one(result.get("name") or "macro")
    reason = result.get("reason") or "r.macro-refused"
    detail = _one(result.get("detail") or "the macro could not be expanded")
    return "\n".join([
        "macro · " + name + " · refused · " + reason,
        detail + " · " + reason,
        "nothing was run · r.macro-none",
    ])


def preview_text(result, limits=None):
    if not result.get("ok"):
        return refusal_text(result)
    lim = _limits(limits)
    lines = [
        "macro · " + _one(result["name"]) + " · "
        + str(result["total"]) + " steps · planSteps " + str(lim["steps"])
        + " · r.macro",
    ]
    if result.get("summary"):
        lines.append("summary: " + _one(result["summary"]))
    for index, step in enumerate(result["steps"], 1):
        lines.append("  " + str(index) + ". " + step)
    lines.append("say yes to run exactly these steps, no to cancel, or edit "
                 "the macro plan to change the list · r.macro-preview")
    return "\n".join(lines)


def edit_text(result, limits=None):
    if not result.get("ok"):
        return refusal_text(result)
    lim = _limits(limits)
    lines = [
        "macro plan · " + _one(result["name"]) + " · edited · "
        + str(result["total"]) + " steps · r.macro-edit",
    ]
    for index, step in enumerate(result["steps"], 1):
        lines.append("  " + str(index) + ". " + step)
    lines.append('the macro "' + _one(result["name"])
                 + '" is unchanged · r.macro-immutable')
    lines.append("say yes to run exactly these steps, no to cancel · "
                 "r.macro-preview")
    return "\n".join(lines)


def list_text(table):
    macros = _macros(table)
    lines = [
        "macros · " + str(len(macros))
        + " named · literal, non-recursive expansion · r.macro-list",
    ]
    for macro in macros:
        lines.append("  " + macro["name"] + " · "
                     + str(len(macro["steps"])) + " steps · "
                     + _one(macro["summary"]))
    lines.append("preview macro <name> · run macro <name> · edit the macro "
                 "plan to change a staged list")
    return "\n".join(lines)


# --------------------------------------------------------------- fixture ---
def _state(name, kind, want, macro="", steps=None, limits=None, table=None):
    state = {"name": name, "kind": kind, "macro": macro,
             "limits": _limits(limits), "want": want}
    if steps is not None:
        state["steps"] = list(steps)
    if table is not None:
        state["table"] = table
    return state


def _synth(name, steps):
    return {
        "version": 1,
        "macros": [{
            "name": name,
            "summary": "synthetic test macro",
            "steps": list(steps),
        }],
    }


def fixture():
    table = load()
    if table.get("version") != 1:
        _fail("version must be 1")
    limits = dict(DEFAULT_LIMITS)
    cases = [{"text": entry["text"], "op": entry["op"]}
             for entry in _all()]
    states = []
    for macro in _macros(table):
        result = expand(table, macro["name"], limits)
        states.append(_state(
            "preview-" + _slug(macro["name"]), "preview",
            preview_text(result, limits), macro=macro["name"], limits=limits))
    missing = expand(table, "no such macro", limits)
    states.append(_state(
        "missing", "preview", preview_text(missing, limits),
        macro="no such macro", limits=limits))

    recursive = _synth("recursive", ["add save system",
                                     "run macro recursive"])
    rec_result = expand(recursive, "recursive", limits)
    states.append(_state(
        "recursive", "preview", preview_text(rec_result, limits),
        macro="recursive", limits=limits, table=recursive))

    many = _synth("too many steps", ["add save system"] * 41)
    many_result = expand(many, "too many steps", limits)
    states.append(_state(
        "too-many-steps", "preview", preview_text(many_result, limits),
        macro="too many steps", limits=limits, table=many))

    long_text = _synth("too many chars", ["add save system", "add ui system"])
    long_result = expand(long_text, "too many chars",
                         {"steps": 40, "chars": 20, "single": 2000})
    states.append(_state(
        "too-many-chars", "preview",
        preview_text(long_result, {"steps": 40, "chars": 20, "single": 2000}),
        macro="too many chars", limits={"steps": 40, "chars": 20,
                                        "single": 2000}, table=long_text))

    long_step = _synth("long step", ["add save system"])
    step_result = expand(long_step, "long step",
                         {"steps": 40, "chars": 8000, "single": 5})
    states.append(_state(
        "long-step", "preview",
        preview_text(step_result, {"steps": 40, "chars": 8000, "single": 5}),
        macro="long step", limits={"steps": 40, "chars": 8000, "single": 5},
        table=long_step))

    # An empty step list is valid in the synthetic table shape only for this
    # refusal test; _macros() requires a non-empty list, so build the result
    # directly instead of loading it through expand().
    empty_result = check("empty", [], limits)
    states.append(_state(
        "empty", "check", preview_text(empty_result, limits),
        macro="empty", steps=[], limits=limits))

    edited = check("add inventory + save + ui",
                   ["add audio system", "add weather system"], limits)
    states.append(_state(
        "edited", "edit", edit_text(edited, limits),
        macro="add inventory + save + ui",
        steps=["add audio system", "add weather system"], limits=limits))

    states.append(_state(
        "list", "list", list_text(table), limits=limits))

    ops = {}
    for case in cases:
        ops[case["op"]] = ops.get(case["op"], 0) + 1
    return {
        "version": 1,
        "count": len(cases),
        "ops": ops,
        "table": table,
        "cases": cases,
        "states": states,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="refresh tests/fixtures/macros.json")
    parser.add_argument("--check", action="store_true",
                        help="fail if the fixture drifted")
    args = parser.parse_args(argv)
    doc = fixture()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(doc, indent=2, ensure_ascii=False)
                           + "\n", encoding="utf-8")
        print("wrote %s (%d cases, %d states)"
              % (FIXTURE.relative_to(ROOT.parent), doc["count"],
                 len(doc["states"])))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("macro fixture is missing; run toolrx/macros.py --write")
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != doc:
            print("macro fixture drifted; run toolrx/macros.py --write")
            return 1
        print("macro fixture is current")
        return 0
    print("macros: %d routes, %d macros, %d fixture states"
          % (doc["count"], len(doc["table"]["macros"]), len(doc["states"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

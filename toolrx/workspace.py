#!/usr/bin/env python3
"""Deterministic cross-project workspace index (step 64).

One checked-in table, `toolrx/workspace.json`, is the only source of the
`workspace.*` routes. It is expanded into catalog entries by
`toolrx/build_commands.py` and exported to `tests/fixtures/workspace.json` so
the routes and the rendered answers cannot drift.

The index is derived, never a second copy of the journals. It reads the project
list (slug, name, kind, theme, seed, updated) plus each project's own journal,
and keeps only the newest build line and the sorted topic names. Full entries
stay in their per-project journals, and project context is never read.

    python3 toolrx/workspace.py --write   # refresh the fixture
    python3 toolrx/workspace.py --check   # fail if the fixture drifted
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TABLE = ROOT / "workspace.json"
FIXTURE = ROOT.parent / "tests" / "fixtures" / "workspace.json"

MODES = ("index", "themes", "decisions", "export")
KINDS = ("decision", "rejection", "preference")
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
         "six": 6, "seven": 7, "eight": 8, "nine": 9}
_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_TOPIC = r"(.+?)"
_LIMIT = r"(one|two|three|four|five|six|seven|eight|nine|[1-9])"

STOP = {
    "a", "an", "and", "about", "are", "be", "by", "choose", "chose",
    "decide", "decided", "decision", "did", "do", "for", "have", "in", "is",
    "it", "journal", "of", "on", "or", "our", "reject", "rejected", "said",
    "say", "the", "to", "was", "we", "were", "what", "why",
}


def load(path=TABLE):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _fail(message):
    raise ValueError("workspace table: " + message)


def _one_line(text):
    return re.sub(r"\s+", " ", str("" if text is None else text)).strip()


def _norm(text):
    return _one_line(text).lower()


def _tokens(text):
    return [t for t in re.split(r"[^a-z0-9]+", _norm(text)) if t]


def _keywords(text):
    return [t for t in _tokens(text) if t not in STOP]


def _plural(n, one, many):
    return "%d %s" % (n, one if n == 1 else many)


def _int(value, fallback=0):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return fallback
    return n if n >= 0 else fallback


# ------------------------------------------------------------------ table ---
def compile_template(text):
    """Return (anchored regex, args) for one route template."""
    parts = []
    args = {}
    last = 0
    index = 0
    for match in _PLACEHOLDER.finditer(text):
        parts.append(re.escape(text[last:match.start()]))
        name = match.group(1)
        if name not in ("topic", "limit"):
            _fail("unknown placeholder {%s} in %r" % (name, text))
        if name in args:
            _fail("placeholder {%s} appears twice in %r" % (name, text))
        index += 1
        parts.append(_TOPIC if name == "topic" else _LIMIT)
        args[name] = "$%d" % index
        last = match.end()
    parts.append(re.escape(text[last:]))
    return "^" + "".join(parts) + "$", args


def _intents(table):
    intents = table.get("intents")
    if not isinstance(intents, dict) or not intents:
        _fail("intents must be a non-empty object")
    for mode in MODES:
        if mode not in intents:
            _fail("missing intent %r" % mode)
    out = []
    for mode, spec in intents.items():
        if mode not in MODES:
            _fail("unknown intent %r" % mode)
        if not isinstance(spec, dict):
            _fail("intent %r must be an object" % mode)
        op = str(spec.get("op") or "")
        want = "workspace.export.index" if mode == "export" else "workspace." + mode
        if op != want:
            _fail("intent %r must map to %s, not %r" % (mode, want, op))
        templates = spec.get("templates", [])
        bare = spec.get("bare", [])
        if not isinstance(templates, list) or not isinstance(bare, list):
            _fail("intent %r templates and bare must be lists" % mode)
        if not templates and not bare:
            _fail("intent %r needs at least one template or bare phrase" % mode)
        if mode == "decisions" and not templates:
            _fail("decisions needs templates with {topic}")
        if mode != "decisions" and templates:
            _fail("intent %r must use bare phrases, not templates" % mode)
        example = _one_line(spec.get("example"))
        if not example:
            _fail("intent %r needs an example" % mode)
        if not templates and example not in bare:
            _fail("intent %r example %r must be one of its bare phrases"
                  % (mode, example))
        for text in templates:
            if "{topic}" not in text:
                _fail("template %r must contain {topic}" % text)
        if templates and not any(
                re.match(compile_template(t)[0], example) for t in templates):
            _fail("intent %r example %r does not match any template"
                  % (mode, example))
        out.append({
            "mode": mode,
            "op": op,
            "summary": _one_line(spec.get("summary")),
            "templates": [_one_line(t) for t in templates],
            "bare": [_one_line(b) for b in bare],
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
            key = _norm(text.replace("{topic}", "\x00").replace("{limit}", "\x01"))
            if key in seen:
                _fail("template %r already used by %s" % (text, seen[key]))
            seen[key] = mode
            counts[mode] = counts.get(mode, 0) + 1
            values = {"topic": "art style", "limit": "three"}
            expect = {name: values[name] for name in args}
            sample = text.replace("{topic}", values["topic"]).replace(
                "{limit}", values["limit"])
            yield {
                "id": "workspace.%s.%d" % (mode, counts[mode]),
                "op": intent["op"],
                "re": regex,
                "args": args,
                "d": intent["summary"],
                "c": "workspace",
                "text": sample,
                "expect": expect,
            }
        for text in intent["bare"]:
            key = _norm(text)
            if key in seen:
                _fail("bare route %r already used by %s" % (text, seen[key]))
            seen[key] = mode
            counts[mode] = counts.get(mode, 0) + 1
            yield {
                "id": "workspace.%s.%d" % (mode, counts[mode]),
                "op": intent["op"],
                "re": "^" + re.escape(text) + "$",
                "args": {},
                "d": intent["summary"],
                "c": "workspace",
                "text": text,
                "expect": {},
            }


def entries():
    """Unique catalog entries, in generation order."""
    return _all()


# ------------------------------------------------------------------ caps ---
def _caps(limits=None):
    try:
        import envelope
    except ImportError:  # pragma: no cover - direct script execution
        sys.path.insert(0, str(ROOT))
        import envelope
    data = envelope.load()
    if limits:
        data.update(limits)

    def get(key, fallback):
        try:
            n = int(data.get(key, fallback))
        except (TypeError, ValueError):
            n = fallback
        return max(1, n)

    return {
        "projects": get("workspaceProjects", 24),
        "topics": get("workspaceTopics", 8),
        "rows": get("workspaceRows", 12),
        "bytes": get("workspaceIndexBytes", 8192),
        "chars": get("workspaceChars", 4000),
        "journalText": get("journalText", 240),
    }


# ------------------------------------------------------------------ index ---
def _clean_entry(raw):
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "")
    if kind not in KINDS:
        return None
    topic = _one_line(raw.get("topic"))[:60]
    text = _one_line(raw.get("text"))[:240]
    if not topic or not text:
        return None
    return {
        "seq": _int(raw.get("seq")),
        "kind": kind,
        "topic": topic,
        "text": text,
        "source": _one_line(raw.get("source") or "unknown")[:60],
    }


def _clean_project(raw):
    if not isinstance(raw, dict):
        return None
    slug = _one_line(raw.get("slug"))[:60]
    if not slug:
        return None
    seed = raw.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, (int, float)):
        seed = None
    elif seed < 0:
        seed = None
    else:
        seed = int(seed)
    return {
        "slug": slug,
        "name": _one_line(raw.get("name"))[:60] or slug,
        "kind": _one_line(raw.get("kind"))[:40] or "unknown",
        "theme": "light" if _one_line(raw.get("theme")).lower() == "light" else "dark",
        "seed": seed,
        "updated": _int(raw.get("updated")),
        "journal": [e for e in (_clean_entry(x) for x in (raw.get("journal") or []))
                    if e],
    }


def _clean_projects(raw):
    projects = [p for p in (_clean_project(x) for x in (raw or [])) if p]
    projects.sort(key=lambda p: p["slug"])
    return projects


def export_doc(index):
    return json.dumps(index, ensure_ascii=False, separators=(",", ":"))


def _size(index):
    return len(export_doc(index).encode("utf-8"))


def build(state, limits=None):
    """Build the bounded, deterministic index from the live workspace state."""
    caps = _caps(limits)
    rows = []
    dropped_topics = 0
    for project in _clean_projects((state or {}).get("projects")):
        topics = sorted({e["topic"] for e in project["journal"] if e["topic"]})
        kept = topics[:caps["topics"]]
        dropped_topics += len(topics) - len(kept)
        latest = None
        for entry in project["journal"]:
            if entry["source"] != "build":
                continue
            if latest is None or entry["seq"] >= latest["seq"]:
                latest = entry
        rows.append({
            "slug": project["slug"],
            "name": project["name"],
            "kind": project["kind"],
            "theme": project["theme"],
            "seed": project["seed"],
            "build": _one_line(latest["text"])[:120] if latest else "",
            "topics": kept,
            "updated": project["updated"],
        })
    dropped_projects = max(0, len(rows) - caps["projects"])
    rows = rows[:caps["projects"]]
    doc = {
        "version": 1,
        "projects": rows,
        "dropped": {"projects": dropped_projects, "topics": dropped_topics},
    }
    while rows and _size(doc) > caps["bytes"]:
        rows.pop()
        doc["dropped"]["projects"] += 1
    doc["bytes"] = _size(doc)
    return doc


def import_doc(raw, limits=None):
    """Validate and normalize an exported index. Returns {ok, index|why}."""
    caps = _caps(limits)
    try:
        doc = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return {"ok": False, "why": "the workspace index is not valid JSON"}
    if not isinstance(doc, dict):
        return {"ok": False, "why": "the workspace index is not an object"}
    if doc.get("version") != 1:
        return {"ok": False, "why": "unsupported workspace index version "
                                    + str(doc.get("version"))}
    if not isinstance(doc.get("projects"), list):
        return {"ok": False, "why": "the workspace index has no projects list"}
    dropped = doc.get("dropped") if isinstance(doc.get("dropped"), dict) else {}
    rows = []
    dropped_topics = _int(dropped.get("topics"))
    for raw_project in doc["projects"]:
        if not isinstance(raw_project, dict):
            return {"ok": False, "why": "a workspace index row is not an object"}
        slug = _one_line(raw_project.get("slug"))[:60]
        if not slug:
            return {"ok": False, "why": "a workspace index row has no slug"}
        seed = raw_project.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, (int, float)) or seed < 0:
            seed = None
        else:
            seed = int(seed)
        topics = []
        raw_topics = raw_project.get("topics")
        if not isinstance(raw_topics, list):
            return {"ok": False, "why": "workspace index topics must be a list"}
        for topic in raw_topics:
            text = _one_line(topic)[:60]
            if text and text not in topics:
                topics.append(text)
        topics.sort()
        kept = topics[:caps["topics"]]
        dropped_topics += len(topics) - len(kept)
        rows.append({
            "slug": slug,
            "name": _one_line(raw_project.get("name"))[:60] or slug,
            "kind": _one_line(raw_project.get("kind"))[:40] or "unknown",
            "theme": "light" if _one_line(raw_project.get("theme")).lower() == "light"
            else "dark",
            "seed": seed,
            "build": _one_line(raw_project.get("build"))[:120],
            "topics": kept,
            "updated": _int(raw_project.get("updated")),
        })
    rows.sort(key=lambda p: p["slug"])
    dropped_projects = _int(dropped.get("projects")) + max(0, len(rows) - caps["projects"])
    rows = rows[:caps["projects"]]
    out = {
        "version": 1,
        "projects": rows,
        "dropped": {"projects": dropped_projects, "topics": dropped_topics},
    }
    while rows and _size(out) > caps["bytes"]:
        rows.pop()
        out["dropped"]["projects"] += 1
    out["bytes"] = _size(out)
    return {"ok": True, "index": out}


# ----------------------------------------------------------------- render ---
def _finish(lines, caps):
    text = "\n".join(lines)
    if len(text) <= caps["chars"]:
        return text
    cut = text[:caps["chars"]]
    at = cut.rfind("\n")
    if at > 0:
        cut = cut[:at]
    return cut + "\n… trimmed to workspaceChars (" + str(caps["chars"]) + " chars) · r.trim"


def _seed_text(seed):
    return "n/a" if seed is None else str(seed)


def _render_index(doc, caps):
    projects = doc["projects"]
    if not projects:
        return _finish([
            "workspace index · empty",
            "no projects yet — build something first",
            "writes: no file · r.no-write",
        ], caps)
    topics = sum(len(p["topics"]) for p in projects)
    lines = [
        "workspace index · " + _plural(len(projects), "project", "projects")
        + " · " + _plural(topics, "topic", "topics")
        + " · cap " + str(caps["projects"]) + " projects · "
        + str(caps["bytes"]) + " bytes"
    ]
    for project in projects:
        listed = ", ".join(project["topics"]) if project["topics"] else "none"
        lines.append("  " + project["slug"] + " · " + project["name"] + " · "
                     + project["kind"] + " · " + project["theme"] + " · seed "
                     + _seed_text(project["seed"]) + " · topics " + listed)
        lines.append("    last build: " + (project["build"] or "none"))
    notes = []
    if doc["dropped"]["projects"]:
        notes.append(_plural(doc["dropped"]["projects"], "project", "projects")
                     + " dropped at the workspaceProjects cap")
    if doc["dropped"]["topics"]:
        notes.append(_plural(doc["dropped"]["topics"], "topic", "topics")
                     + " dropped at the workspaceTopics cap")
    lines.append("notes: " + (" · ".join(notes) if notes else "none"))
    lines.append("source: project files + per-project journals · context is never read · r.index")
    lines.append("writes: no file · r.no-write")
    return _finish(lines, caps)


def _render_themes(doc, caps):
    projects = doc["projects"]
    if not projects:
        return _finish([
            "workspace themes · empty",
            "no projects yet — build something first",
            "writes: no file · r.no-write",
        ], caps)
    lines = ["workspace themes · "
             + _plural(len(projects), "project", "projects")]
    shown = projects[:caps["rows"]]
    for project in shown:
        lines.append("  " + project["slug"] + " · " + project["theme"] + " · "
                     + project["kind"] + " · seed " + _seed_text(project["seed"]))
    if len(projects) > len(shown):
        lines.append("  · … " + str(len(projects) - len(shown))
                     + " more projects at the workspaceRows cap")
    lines.append("cap " + str(caps["rows"]) + " rows · workspaceRows · r.themes")
    return _finish(lines, caps)


def _parse_limit(value):
    text = _norm(value)
    if not text:
        return 3
    n = WORDS.get(text)
    if n is None:
        try:
            n = int(text)
        except ValueError:
            n = 3
    return max(1, min(9, n))


def _entry_matches(entry, want, phrase):
    hay = _tokens(entry["topic"] + " " + entry["text"] + " " + entry["source"])
    score = 0
    if not want:
        score = 1
    for token in want:
        if token in hay:
            score += 2
    if phrase and (phrase in _norm(entry["topic"])
                   or phrase in _norm(entry["text"] + " " + entry["source"])):
        score += 4
    return score > 0


def _render_decisions(state, args, caps):
    projects = _clean_projects((state or {}).get("projects"))
    topic = _one_line((args or {}).get("topic"))
    limit = _parse_limit((args or {}).get("limit"))
    if not projects:
        return _finish([
            "workspace decisions · empty",
            "no projects yet — build something first",
            "writes: no file · r.no-write",
        ], caps)
    ordered = sorted(projects, key=lambda p: (-p["updated"], p["slug"]))[:limit]
    want = _keywords(topic)
    phrase = _norm(topic)
    rows = []
    for project in ordered:
        matches = [e for e in project["journal"]
                   if _entry_matches(e, want, phrase)]
        matches.sort(key=lambda e: -e["seq"])
        for entry in matches:
            rows.append((project, entry))
    known = sorted({e["topic"] for p in ordered for e in p["journal"]})[:caps["topics"]]
    if not rows:
        lines = ["workspace decisions · nothing about \"" + topic + "\" yet · "
                 + _plural(len(ordered), "project", "projects") + " searched"]
        if known:
            lines.append("known topics: " + ", ".join(known))
        lines.append("cap " + str(caps["rows"]) + " rows · r.decisions")
        return _finish(lines, caps)
    shown = rows[:caps["rows"]]
    lines = ["workspace decisions · \"" + topic + "\" · last " + str(limit)
             + " builds · " + _plural(len(rows), "match", "matches")]
    for project, entry in shown:
        lines.append("  " + project["slug"] + " · #" + str(entry["seq"]) + " "
                     + entry["kind"] + " · " + entry["topic"] + " · "
                     + entry["text"] + " · via " + entry["source"])
    if len(rows) > len(shown):
        lines.append("  · … " + str(len(rows) - len(shown))
                     + " more matches at the workspaceRows cap")
    lines.append("cap " + str(caps["rows"]) + " rows · searched "
                 + _plural(len(ordered), "project", "projects") + " · r.decisions")
    return _finish(lines, caps)


def render(kind, state, args=None, limits=None):
    caps = _caps(limits)
    if kind == "index":
        return _render_index(build(state, limits), caps)
    if kind == "themes":
        return _render_themes(build(state, limits), caps)
    if kind == "decisions":
        return _render_decisions(state, args or {}, caps)
    raise ValueError("unknown workspace target: " + kind)


# ---------------------------------------------------------------- fixture ---
def _entry(seq, kind, topic, text, source):
    return {"seq": seq, "kind": kind, "topic": topic, "text": text,
            "source": source}


def _state(name, projects, active=""):
    return {"name": name, "active": active, "projects": projects}


def _states():
    return [
        _state("empty", []),
        _state("three-projects", [
            {"slug": "alpha", "name": "Alpha", "kind": "platformer",
             "theme": "dark", "seed": 123, "updated": 3000,
             "journal": [
                 _entry(1, "decision", "art style",
                        "genre platformer · seed 123 · 5 files", "build"),
                 _entry(2, "rejection", "plan budget",
                        "dropped 1 step(s) for steps", "plan.variant"),
             ]},
            {"slug": "beta", "name": "Beta", "kind": "notebook",
             "theme": "light", "seed": 42, "updated": 2000,
             "journal": [
                 _entry(1, "preference", "favorite color", "teal",
                        "memory.remember"),
                 _entry(2, "decision", "art style",
                        "genre notebook · seed 42 · 5 files", "build"),
             ]},
            {"slug": "gamma", "name": "Gamma", "kind": "datadash",
             "theme": "dark", "seed": None, "updated": 1000,
             "journal": [
                 _entry(1, "decision", "art style",
                        "genre datadash · seed 7 · 6 files", "build"),
             ]},
        ], "beta"),
        _state("wide", [
            {"slug": "p%02d" % i, "name": "Project %d" % i,
             "kind": "notes", "theme": "light" if i % 2 else "dark",
             "seed": i, "updated": 1000 - i,
             "journal": [
                 _entry(1, "decision", "topic %d" % (i % 12),
                        "decision number %d" % i, "build"),
                 _entry(2, "preference", "topic %d" % ((i + 1) % 12),
                        "preference number %d" % i, "memory.remember"),
             ]}
            for i in range(30)
        ]),
    ]


def fixture():
    caps = _caps()
    cases = [
        {"text": e["text"], "op": e["op"], "args": e["expect"],
         "mode": e["op"].split(".", 1)[1]}
        for e in entries()
    ]
    cases.sort(key=lambda c: (c["mode"], c["text"]))
    ops = {}
    for case in cases:
        ops[case["op"]] = ops.get(case["op"], 0) + 1
    rendered = []
    for state in _states():
        input = {"active": state["active"], "projects": state["projects"]}
        for kind, args in (
            ("index", {}),
            ("themes", {}),
            ("decisions", {"topic": "art style", "limit": "three"}),
            ("decisions", {"topic": "art style", "limit": "2"}),
            ("decisions", {"topic": "nonsense", "limit": "three"}),
        ):
            rendered.append({
                "name": state["name"],
                "kind": kind,
                "args": args,
                "input": input,
                "want": render(kind, input, args, caps),
            })
    return {
        "version": 1,
        "count": len(cases),
        "ops": dict(sorted(ops.items())),
        "caps": caps,
        "cases": cases,
        "states": rendered,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh tests/fixtures/workspace.json")
    group.add_argument("--check", action="store_true",
                       help="fail if the fixture drifted")
    args = parser.parse_args(argv)
    doc = fixture()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        print("wrote %s (%d cases, %d states)"
              % (FIXTURE.relative_to(ROOT.parent), doc["count"],
                 len(doc["states"])))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("missing fixture; run --write", file=sys.stderr)
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != doc:
            print("workspace fixture drifted; run --write", file=sys.stderr)
            return 1
        print("workspace fixture is current")
        return 0
    print(json.dumps(doc["ops"], indent=2))
    print("%d cases, %d states" % (doc["count"], len(doc["states"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

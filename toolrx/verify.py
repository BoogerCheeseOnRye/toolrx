#!/usr/bin/env python3
"""Deterministic project verification (step 66).

One checked-in table, `toolrx/verify.json`, is the only source of the
`verify.*` routes. It is expanded into catalog entries by
`toolrx/build_commands.py` and exported to `tests/fixtures/verify.json` so the
routes, the rendered states, and the browser program cannot drift.

The renderer here mirrors `toolrx/web/verify.js` byte for byte. It reads only
the state passed in; it never touches a project, a file, or the network.

    python3 toolrx/verify.py --write   # refresh the fixture
    python3 toolrx/verify.py --check   # fail if the fixture drifted
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TABLE = ROOT / "verify.json"
FIXTURE = ROOT.parent / "tests" / "fixtures" / "verify.json"

TARGETS = ("files", "smoke", "report")
INTENTS = {
    "files": ("verify.files", "files", ""),
    "smoke": ("verify.smoke", "smoke", ""),
    "report": ("verify.report", "report", ""),
    "context": ("verify.report.context", "report", "context"),
    "journal": ("verify.report.journal", "report", "journal"),
}

BASE_FILES = ["ARCHITECTURE.md", "README.md", "app.js", "index.html",
              "styles.css"]
RPG_SHARED = ["engine2d.js", "rpg2.js", "worldgen.js"]
THREE_D_ROUTE = {"platformer", "maze", "racer", "explore", "waveshooter",
                 "builder"}
ENGINE_GENRES = {"platformer", "snake", "breakout", "shooter", "racer", "rpg",
                 "twinstick", "roguelike", "towerdefense", "merges",
                 "farmingsim", "rhythm", "waveshooter"}
STARTER_KINDS = {"authapp", "datadash", "notebook", "multipage", "apimock"}
STARTER_FILES = {
    "authapp": ["auth.js"],
    "datadash": ["data.js"],
    "notebook": ["seed-notes.js"],
    "multipage": ["about.html", "contact.html", "docs.html", "site.js"],
    "apimock": ["api.js", "openapi.json"],
}

RULES = {
    "r.project-exists": "the active project is read from the workspace",
    "r.files": "expected files come from the build spec, actual files from the project",
    "r.spec": "the expected list is derived from the stored build spec",
    "r.actual": "the actual list is the project's real file names",
    "r.missing": "missing names are expected files the project does not have",
    "r.extra": "extra names are project files the spec did not promise",
    "r.files-cap": "listed file names are bounded by verifyFiles",
    "r.smoke": "every smoke check is a pure predicate over project file text",
    "r.check-index": "index.html exists and has content",
    "r.check-title": "the index title matches the project name",
    "r.check-styles": "styles.css exists and has content",
    "r.check-entry": "app.js defines a function or an event listener",
    "r.check-order": "local scripts load before app.js",
    "r.check-links": "every local link and script src names a real file",
    "r.check-docs": "README.md and ARCHITECTURE.md have content",
    "r.check-budget": "file count and bytes are within the project budget",
    "r.checks-cap": "checks run are bounded by verifyChecks",
    "r.report": "the report combines the file diff and the smoke checks",
    "r.verdict": "the verdict is ok only when files and checks all pass",
    "r.read-only": "checks read project text only and execute nothing",
    "r.limits": "the report is bounded by verifyReportChars",
    "r.no-write": "verification writes no project file",
    "r.trim": "an over-cap report is trimmed at a line boundary",
}

_RULE = re.compile(r"r\.[a-z][a-z-]*")
_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_ENTRY = re.compile(r"function\s+[A-Za-z_$][A-Za-z0-9_$]*|=>"
                    r"|addEventListener\s*\(")
_SCRIPT = re.compile(r"<script\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"'][^>]*>",
                     re.I)
_TITLE = re.compile(r"<title[^>]*>([\s\S]*?)</title>", re.I)
_LINK = re.compile(r"\b(?:href|src)\s*=\s*[\"']([^\"']+)[\"']", re.I)
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


# ---------------------------------------------------------------- table ---
def load(path=TABLE):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _fail(message):
    raise ValueError("verify table: " + message)


def _norm(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def _check_text(value, where):
    if not isinstance(value, str) or not value.strip():
        _fail(where + " must be a non-empty string")
    return value


def _intents(table):
    intents = table.get("intents")
    if not isinstance(intents, dict) or not intents:
        _fail("intents must be a non-empty object")
    for key in INTENTS:
        if key not in intents:
            _fail("missing intent %r" % key)
    out = []
    for key, spec in intents.items():
        if key not in INTENTS:
            _fail("unknown intent %r" % key)
        if not isinstance(spec, dict):
            _fail("intent %r must be an object" % key)
        op, target, store = INTENTS[key]
        if spec.get("op") != op:
            _fail("intent %r must map to %s, not %r"
                  % (key, op, spec.get("op")))
        if spec.get("target") != target:
            _fail("intent %r must target %s" % (key, target))
        if spec.get("store", "") != store:
            _fail("intent %r must store %r" % (key, store))
        bare = spec.get("bare")
        if not isinstance(bare, list) or not bare:
            _fail("intent %r needs a non-empty bare list" % key)
        example = _check_text(spec.get("example"), key + ".example")
        if example not in bare:
            _fail("intent %r example %r must be one of its bare phrases"
                  % (key, example))
        out.append({
            "intent": key,
            "op": op,
            "target": target,
            "store": store,
            "summary": _check_text(spec.get("summary"), key + ".summary"),
            "example": example,
            "bare": [_check_text(t, key + ".bare") for t in bare],
        })
    return out


def _all():
    table = load()
    if table.get("version") != 1:
        _fail("version must be 1")
    seen = {}
    counts = {}
    for intent in _intents(table):
        key = intent["intent"]
        for text in intent["bare"]:
            norm = _norm(text)
            if norm in seen:
                _fail("route %r already used by %s" % (text, seen[norm]))
            seen[norm] = key
            counts[key] = counts.get(key, 0) + 1
            yield {
                "id": "verify.%s.%d" % (key, counts[key]),
                "op": intent["op"],
                "re": "^" + re.escape(text) + "$",
                "args": {},
                "d": intent["summary"],
                "c": "verify",
                "text": text,
                "expect": {},
            }


def entries():
    """Unique catalog entries, in generation order."""
    return _all()


# --------------------------------------------------------------- render ---
def _number(value, fallback):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return fallback
    if n != n or n < 0:
        return fallback
    return int(n)


def _byte_length(text):
    return len(str("" if text is None else text).encode("utf-8"))


def _trim_to_bytes(text, max_bytes):
    s = str("" if text is None else text)
    if _byte_length(s) <= max_bytes:
        return s
    out = []
    used = 0
    for ch in s:
        size = _byte_length(ch)
        if used + size > max_bytes:
            break
        out.append(ch)
        used += size
    return "".join(out)


def _fmt(n):
    try:
        value = int(round(float(n)))
    except (TypeError, ValueError):
        value = 0
    return format(value, ",")


def _one_line(text):
    return re.sub(r"\s+", " ", str("" if text is None else text)).strip()


def _rule(rule_id):
    return "· " + rule_id


def _limits(input):
    l = (input or {}).get("limits") or {}

    def get(key, fallback):
        return _number(l.get(key), fallback)

    return {
        "files": get("verifyFiles", 32),
        "checks": get("verifyChecks", 8),
        "chars": get("verifyReportChars", 4000),
        "project": get("projectBytes", 524288),
        "projectFiles": get("projectFiles", 32),
    }


def _finish(lines, lim):
    text = "\n".join(lines)
    if _byte_length(text) <= lim["chars"]:
        return text
    note = ("\n… trimmed to " + _fmt(lim["chars"])
            + " chars (verifyReportChars) " + _rule("r.trim"))
    room = lim["chars"] - _byte_length(note)
    if room < 0:
        room = 0
    cut = _trim_to_bytes(text, room)
    newline = cut.rfind("\n")
    if newline > 0:
        cut = cut[:newline]
    return cut + note


def _rules_line(lines):
    seen = []
    for match in _RULE.findall("\n".join(lines)):
        if match not in seen:
            seen.append(match)
    return "rules: " + ", ".join(seen)


def _files_of(project):
    raw = (project or {}).get("files") or {}
    return {str(name): str("" if text is None else text)
            for name, text in raw.items()}


def _wants_content(spec):
    genre = str(spec.get("genre") or spec.get("kind") or "")
    if genre in STARTER_KINDS:
        return False
    counts = spec.get("counts") or {}
    return bool((spec.get("features") or [])
                or counts
                or spec.get("levels")
                or spec.get("size")
                or spec.get("subtheme"))


def expected_files(spec):
    spec = spec or {}
    genre = str(spec.get("genre") or spec.get("kind") or "")
    names = list(BASE_FILES)
    if genre == "rpg":
        names.extend(RPG_SHARED)
    elif spec.get("dim") == "3D" and genre in THREE_D_ROUTE:
        names.append("engine3d.js")
    elif genre in ENGINE_GENRES:
        names.append("engine2d.js")
    if _wants_content(spec):
        names.append("content.js")
    names.extend(STARTER_FILES.get(genre, []))
    for name in spec.get("modules") or []:
        if name:
            names.append(str(name))
    for system in spec.get("systems") or []:
        if system:
            names.append("systems/" + str(system) + ".js")
    seen = set()
    out = []
    for name in names:
        if name not in seen:
            seen.add(name)
            out.append(name)
    out.sort()
    return out


def _decode_entities(text):
    return (str("" if text is None else text)
            .replace("&lt;", "<").replace("&gt;", ">")
            .replace("&quot;", '"').replace("&#39;", "'")
            .replace("&amp;", "&"))


def _title_of(html):
    match = _TITLE.search(str(html or ""))
    return _one_line(_decode_entities(match.group(1))) if match else ""


def _local_path(value):
    name = str("" if value is None else value).strip()
    if not name:
        return ""
    if name.startswith("#"):
        return ""
    if name.startswith("//"):
        return ""
    if _SCHEME.match(name):
        return ""
    name = re.sub(r"[?#].*$", "", name)
    while name.startswith("./"):
        name = name[2:]
    if name.startswith("/"):
        name = name[1:]
    if not name or name == "." or name.endswith("/"):
        return ""
    return name


def _link_names(html):
    out = []
    for match in _LINK.finditer(str(html or "")):
        name = _local_path(match.group(1))
        if name:
            out.append(name)
    return out


def _byte_size(files):
    return sum(_byte_length(text) for text in files.values())


def _check(check_id, passed, label, detail=""):
    return {"id": check_id, "pass": bool(passed), "label": label,
            "detail": detail}


def _smoke_checks(project, files, lim):
    names = sorted(files)
    text = files.get
    html = text("index.html", "")
    checks = []

    checks.append(_check(
        "r.check-index", "index.html" in files and _one_line(html) != "",
        "index.html exists and has content",
        "index.html is missing" if "index.html" not in files
        else ("index.html is empty" if _one_line(html) == "" else "")))

    title = _title_of(html)
    want = _one_line(project.get("name")) + " · toolrx"
    checks.append(_check(
        "r.check-title", title == want, "title matches the project name",
        "no title tag" if not title
        else ("" if title == want else 'found "' + title + '"')))

    checks.append(_check(
        "r.check-styles",
        "styles.css" in files and _one_line(text("styles.css", "")) != "",
        "styles.css has content",
        "styles.css is missing" if "styles.css" not in files
        else ("styles.css is empty"
              if _one_line(text("styles.css", "")) == "" else "")))

    js = text("app.js", "")
    entry = bool(_ENTRY.search(js))
    checks.append(_check(
        "r.check-entry", "app.js" in files and entry,
        "app.js defines a function or event listener",
        "app.js is missing" if "app.js" not in files
        else ("" if entry else "no function or event listener")))

    tags = [(match.group(1), match.start()) for match in _SCRIPT.finditer(html)]
    app_at = -1
    for src, at in tags:
        if _local_path(src) == "app.js":
            app_at = at
            break
    after = []
    if app_at >= 0:
        for src, at in tags:
            name = _local_path(src)
            if at > app_at and name != "app.js":
                after.append(name)
    checks.append(_check(
        "r.check-order", app_at >= 0 and not after, "scripts load before app.js",
        "app.js is not referenced" if app_at < 0
        else ("%d script(s) load after app.js: %s" % (len(after), ", ".join(after))
              if after else "")))

    missing_links = []
    for name in _link_names(html):
        if name not in files and name not in missing_links:
            missing_links.append(name)
    checks.append(_check(
        "r.check-links",
        "index.html" in files and not missing_links,
        "local links resolve to real files",
        "index.html is missing" if "index.html" not in files
        else ("%d missing: %s" % (len(missing_links),
                                  ", ".join(missing_links[:4]))
              if missing_links else "")))

    docs = [name for name in ("README.md", "ARCHITECTURE.md")
            if name not in files or _one_line(files[name]) == ""]
    checks.append(_check(
        "r.check-docs", not docs,
        "README.md and ARCHITECTURE.md have content",
        "missing or empty: " + ", ".join(docs) if docs else ""))

    size = _byte_size(files)
    over_files = lim["projectFiles"] > 0 and len(names) > lim["projectFiles"]
    over_bytes = lim["project"] > 0 and size > lim["project"]
    checks.append(_check(
        "r.check-budget", not over_files and not over_bytes,
        "files and bytes are within budget",
        "files %d/%s · bytes %s/%s"
        % (len(names), _fmt(lim["projectFiles"]), _fmt(size),
           _fmt(lim["project"])) if over_files or over_bytes else ""))

    return checks


def _file_diff(project):
    spec = project.get("spec") or {}
    expected = expected_files(spec)
    files = _files_of(project)
    actual = sorted(files)
    missing = [name for name in expected if name not in actual]
    extra = [name for name in actual if name not in expected]
    return {"expected": expected, "actual": actual, "missing": missing,
            "extra": extra, "files": files}


def _list_lines(label, names, rule_id, lim):
    shown = names[:lim["files"]]
    lines = [label + " (" + str(len(names)) + "): "
             + (" · ".join(shown) if shown else "none") + " " + _rule(rule_id)]
    if len(names) > len(shown):
        lines.append("… %d more %s not listed %s"
                     % (len(names) - len(shown), label, _rule("r.files-cap")))
    return lines


def _budget_line(files, lim):
    return ("budgets: files %d/%s · bytes %s/%s · verify cap %s chars %s"
            % (len(files), _fmt(lim["projectFiles"]), _fmt(_byte_size(files)),
               _fmt(lim["project"]), _fmt(lim["chars"]), _rule("r.limits")))


def _files_text(project, lim):
    diff = _file_diff(project)
    ok = not diff["missing"] and not diff["extra"]
    lines = [
        "verify · files · " + _one_line(project.get("name")) + " · "
        + str(len(diff["expected"])) + " expected · "
        + str(len(diff["actual"])) + " actual · "
        + ("ok" if ok else "fail") + " " + _rule("r.files")
    ]
    lines.extend(_list_lines("expected", diff["expected"], "r.spec", lim))
    lines.extend(_list_lines("actual", diff["actual"], "r.actual", lim))
    lines.extend(_list_lines("missing", diff["missing"], "r.missing", lim))
    lines.extend(_list_lines("extra", diff["extra"], "r.extra", lim))
    lines.append(_budget_line(diff["files"], lim))
    lines.append("writes: no file " + _rule("r.no-write"))
    lines.append(_rules_line(lines))
    return _finish(lines, lim)


def _check_lines(checks):
    return ["  " + ("pass" if c["pass"] else "fail") + " · " + c["label"]
            + (" · " + c["detail"] if c["detail"] else "") + " "
            + _rule(c["id"]) for c in checks]


def _cap_checks(all_checks, lim):
    checks = all_checks[:lim["checks"]]
    return checks, len(all_checks) - len(checks)


def _smoke_text(project, lim):
    files = _files_of(project)
    checks, skipped = _cap_checks(_smoke_checks(project, files, lim), lim)
    passed = sum(1 for c in checks if c["pass"])
    failed = len(checks) - passed
    lines = [
        "verify · smoke · " + _one_line(project.get("name")) + " · "
        + str(len(checks)) + " checks · " + str(passed) + " pass · "
        + str(failed) + " fail · " + ("fail" if failed else "ok") + " "
        + _rule("r.smoke")
    ]
    lines.extend(_check_lines(checks))
    if skipped > 0:
        lines.append("… %d more check(s) not run %s"
                     % (skipped, _rule("r.checks-cap")))
    lines.append("reads: project files only · nothing is executed "
                 + _rule("r.read-only"))
    lines.append(_budget_line(files, lim))
    lines.append("writes: no file " + _rule("r.no-write"))
    lines.append(_rules_line(lines))
    return _finish(lines, lim)


def _report_text(project, lim):
    diff = _file_diff(project)
    checks, skipped = _cap_checks(_smoke_checks(project, diff["files"], lim),
                                  lim)
    passed = sum(1 for c in checks if c["pass"])
    failed = len(checks) - passed
    ok = not diff["missing"] and not diff["extra"] and failed == 0
    lines = [
        "verify · report · " + _one_line(project.get("name")) + " · "
        + str(len(diff["expected"])) + "/" + str(len(diff["actual"]))
        + " files · " + str(passed) + "/" + str(len(checks)) + " checks · "
        + ("ok" if ok else "fail") + " " + _rule("r.report"),
        "files: " + str(len(diff["expected"])) + " expected · "
        + str(len(diff["actual"])) + " actual · "
        + str(len(diff["missing"])) + " missing · "
        + str(len(diff["extra"])) + " extra " + _rule("r.files"),
    ]
    if ok:
        verdict = ("verdict: ok · every expected file is present and every "
                   "smoke check passed")
    else:
        verdict = ("verdict: fail · " + str(len(diff["missing"])) + " missing · "
                   + str(len(diff["extra"])) + " extra · " + str(failed)
                   + " failed checks")
    lines.append(verdict + " " + _rule("r.verdict"))
    lines.extend(_list_lines("missing", diff["missing"], "r.missing", lim))
    lines.extend(_list_lines("extra", diff["extra"], "r.extra", lim))
    lines.extend(_check_lines(checks))
    if skipped > 0:
        lines.append("… %d more check(s) not run %s"
                     % (skipped, _rule("r.checks-cap")))
    lines.append("reads: project files only · nothing is executed "
                 + _rule("r.read-only"))
    lines.append(_budget_line(diff["files"], lim))
    lines.append("writes: no file " + _rule("r.no-write"))
    lines.append(_rules_line(lines))
    return _finish(lines, lim)


def _missing_text(target, lim):
    return _finish([
        "verify · " + target + " · no active project",
        "build something first, then ask again " + _rule("r.project-exists"),
        "writes: no file " + _rule("r.no-write"),
    ], lim)


def render(target, input):
    if target not in TARGETS:
        raise ValueError("unknown verify target: " + target)
    safe = input or {}
    lim = _limits(safe)
    project = safe.get("project")
    if not project or not isinstance(project, dict):
        return _missing_text(target, lim)
    if target == "files":
        return _files_text(project, lim)
    if target == "smoke":
        return _smoke_text(project, lim)
    return _report_text(project, lim)


# --------------------------------------------------------------- fixture ---
def _limits_state(**overrides):
    base = {
        "verifyFiles": 32,
        "verifyChecks": 8,
        "verifyReportChars": 4000,
        "projectBytes": 524288,
        "projectFiles": 32,
    }
    base.update(overrides)
    return base


def _file_text(name):
    if name == "index.html":
        return ("<!doctype html>\n<html lang=\"en\" class=\"dark\">\n<head>\n"
                "<title>{title} · toolrx</title>\n"
                "<link rel=\"stylesheet\" href=\"styles.css\">\n</head>\n"
                "<body>\n<h1>{title}</h1>\n<script src=\"app.js\"></script>\n"
                "</body>\n</html>\n")
    if name == "styles.css":
        return "body{font-family:system-ui;background:#0b1020;color:#e6edf7}\n"
    if name == "app.js":
        return ("function start(){\n  document.body.dataset.ready = \"1\";\n}\n"
                "start();\n")
    if name == "README.md":
        return "# Notes\n\nA small, self-contained project built by toolrx.\n"
    if name == "ARCHITECTURE.md":
        return "# Architecture · Notes\n\nState lives in one place.\n"
    if name == "content.js":
        return "window.toolrxContent = { seed: 7, levels: [] };\n"
    if name == "engine2d.js":
        return "window.toolrxEngine2d = { create: function () { return {}; } };\n"
    if name == "engine3d.js":
        return "window.toolrxEngine3d = { create: function () { return {}; } };\n"
    if name == "worldgen.js":
        return "window.toolrxWorldgen = { generate: function () { return {}; } };\n"
    if name == "rpg2.js":
        return "window.toolrxRpg2 = { create: function () { return {}; } };\n"
    if name == "auth.js":
        return "window.toolrxAuth = { validate: function () { return \"\"; } };\n"
    if name == "data.js":
        return "window.toolrxData = { rows: [] };\n"
    if name == "seed-notes.js":
        return "window.toolrxNotes = [];\n"
    if name == "site.js":
        return "document.documentElement.dataset.site = \"1\";\n"
    if name == "api.js":
        return "window.toolrxMockApi = { routes: [] };\n"
    if name == "openapi.json":
        return "{\"openapi\":\"3.0.0\",\"paths\":{}}\n"
    if name.startswith("systems/"):
        return "window.toolrxSystems = window.toolrxSystems || {};\n"
    if name.startswith(("core/", "ui/", "data/", "content/")):
        return "/* " + name + " */\n"
    return "/* " + name + " */\n"


def _project(name="Notes", slug="notes", kind="notes", spec=None, files=None,
             **overrides):
    names = files if files is not None else list(BASE_FILES)
    base = {
        "name": name,
        "slug": slug,
        "kind": kind,
        "spec": spec if spec is not None else {
            "genre": kind, "kind": kind, "dim": "2D", "features": [],
            "counts": {}, "levels": None, "size": None, "subtheme": "",
            "seed": 123456789,
        },
        "files": {n: _file_text(n).replace("{title}", name) for n in names},
    }
    base.update(overrides)
    return base


def _spec(genre="notes", **overrides):
    base = {
        "genre": genre,
        "kind": genre,
        "dim": "2D",
        "features": [],
        "counts": {},
        "levels": None,
        "size": None,
        "subtheme": "",
        "modules": [],
        "systems": [],
        "seed": 123456789,
    }
    base.update(overrides)
    return base


def states():
    platformer = _spec("platformer", features=["double jump"])
    rpg = _spec("rpg", dim="2D", features=["quests"],
                systems=["inventory", "save"], modules=["core/state.js"])
    three_d = _spec("platformer", dim="3D", features=[])
    auth = _spec("authapp", features=[])
    multipage = _spec("multipage", features=[])

    big_modules = ["mods/m%02d.js" % i for i in range(40)]
    big_spec = _spec("notes", modules=big_modules)

    fail_files = {
        "index.html": ("<!doctype html>\n<html><head><title>Wrong name</title>"
                       "</head><body><a href=\"missing.html\">x</a>\n"
                       "<script src=\"app.js\"></script>\n"
                       "<script src=\"site.js\"></script>\n"
                       "</body></html>\n"),
        "styles.css": "   \n",
        "app.js": "var x = 1;\n",
        "README.md": "\n",
        "ARCHITECTURE.md": "ok\n",
        "site.js": "/* site */\n",
        "debug.log": "noise\n",
    }

    pass_project = _project()
    fail_project = _project(name="Notes", files=list(fail_files))
    fail_project["files"] = fail_files

    empty_project = _project(files=[])

    capped_project = _project(spec=big_spec, files=list(BASE_FILES) + big_modules)

    return [
        {"name": "files-pass", "target": "files",
         "input": {"project": pass_project, "limits": _limits_state()}},
        {"name": "files-missing-extra", "target": "files",
         "input": {"project": _project(
             name="Platformer", slug="platformer", kind="platformer",
             spec=platformer,
             files=list(BASE_FILES) + ["engine2d.js", "debug.log"]),
             "limits": _limits_state()}},
        {"name": "files-rpg", "target": "files",
         "input": {"project": _project(
             name="Verdant Wood RPG", slug="verdant-wood-rpg", kind="rpg",
             spec=rpg,
             files=list(BASE_FILES) + ["engine2d.js", "worldgen.js", "rpg2.js",
                                       "content.js", "core/state.js",
                                       "systems/inventory.js",
                                       "systems/save.js"]),
             "limits": _limits_state()}},
        {"name": "files-3d", "target": "files",
         "input": {"project": _project(
             name="Platformer 3D", slug="platformer-3d", kind="platformer",
             spec=three_d,
             files=list(BASE_FILES) + ["engine3d.js"]),
             "limits": _limits_state()}},
        {"name": "files-auth", "target": "files",
         "input": {"project": _project(
             name="Sign-in starter", slug="authapp", kind="authapp",
             spec=auth, files=list(BASE_FILES) + ["auth.js"]),
             "limits": _limits_state()}},
        {"name": "files-multipage", "target": "files",
         "input": {"project": _project(
             name="Static site", slug="multipage", kind="multipage",
             spec=multipage,
             files=list(BASE_FILES) + ["about.html", "docs.html", "contact.html",
                                       "site.js"]),
             "limits": _limits_state()}},
        {"name": "files-empty", "target": "files",
         "input": {"project": empty_project, "limits": _limits_state()}},
        {"name": "files-missing-project", "target": "files",
         "input": {"project": None, "limits": _limits_state()}},
        {"name": "files-capped", "target": "files",
         "input": {"project": capped_project,
                   "limits": _limits_state(verifyFiles=4)}},
        {"name": "smoke-pass", "target": "smoke",
         "input": {"project": pass_project, "limits": _limits_state()}},
        {"name": "smoke-fail", "target": "smoke",
         "input": {"project": fail_project,
                   "limits": _limits_state(projectBytes=64,
                                           projectFiles=4)}},
        {"name": "smoke-empty", "target": "smoke",
         "input": {"project": empty_project, "limits": _limits_state()}},
        {"name": "smoke-missing-project", "target": "smoke",
         "input": {"project": None, "limits": _limits_state()}},
        {"name": "smoke-capped", "target": "smoke",
         "input": {"project": pass_project,
                   "limits": _limits_state(verifyChecks=3)}},
        {"name": "report-pass", "target": "report",
         "input": {"project": pass_project, "limits": _limits_state()}},
        {"name": "report-fail", "target": "report",
         "input": {"project": fail_project,
                   "limits": _limits_state(projectBytes=64,
                                           projectFiles=4)}},
        {"name": "report-empty", "target": "report",
         "input": {"project": empty_project, "limits": _limits_state()}},
        {"name": "report-missing-project", "target": "report",
         "input": {"project": None, "limits": _limits_state()}},
        {"name": "report-trimmed", "target": "report",
         "input": {"project": capped_project,
                   "limits": _limits_state(verifyFiles=32,
                                           verifyReportChars=700)}},
    ]


def fixture():
    cases = [
        {"text": entry["text"], "op": entry["op"],
         "intent": entry["id"].split(".")[1]}
        for entry in entries()
    ]
    cases.sort(key=lambda case: (case["op"], case["text"]))
    targets = {}
    for case in cases:
        targets[case["op"]] = targets.get(case["op"], 0) + 1
    rendered = []
    for state in states():
        rendered.append({
            "name": state["name"],
            "target": state["target"],
            "input": state["input"],
            "want": render(state["target"], state["input"]),
        })
    return {
        "version": 1,
        "count": len(cases),
        "ops": dict(sorted(targets.items())),
        "cases": cases,
        "states": rendered,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh tests/fixtures/verify.json")
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
            print("missing verify fixture; run --write", file=sys.stderr)
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != doc:
            print("verify fixture drifted; run --write", file=sys.stderr)
            return 1
        print("verify fixture is current")
        return 0
    print(json.dumps(doc["ops"], indent=2))
    print("%d cases, %d states" % (doc["count"], len(doc["states"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

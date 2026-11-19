#!/usr/bin/env python3
"""Deterministic project and plan explanations (step 61).

One checked-in table, `toolrx/explain.json`, is the only source of the
`explain.*` routes. It is expanded into catalog entries by
`toolrx/build_commands.py` and exported to `tests/fixtures/explain.json` so the
routes, the rendered states, and the browser program cannot drift.

The renderer here mirrors `toolrx/web/explain.js` byte for byte. It reads only
the state passed in; it never touches a project, a file, or the network.

    python3 toolrx/explain.py --write   # refresh the fixture
    python3 toolrx/explain.py --check   # fail if the fixture drifted
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
TABLE = ROOT / "explain.json"
FIXTURE = ROOT.parent / "tests" / "fixtures" / "explain.json"

TARGETS = ("project", "plan", "theme")
_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_RULE = re.compile(r"r\.[a-z][a-z-]*")


def load(path=TABLE):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _fail(message):
    raise ValueError("explain table: " + message)


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
    out = []
    seen_ops = set()
    for name, spec in intents.items():
        if not isinstance(spec, dict):
            _fail("intent %r must be an object" % name)
        op = _check_text(spec.get("op"), name + ".op")
        if not op.startswith("explain."):
            _fail("intent %r must map to an explain.* op, not %r" % (name, op))
        if op in seen_ops:
            _fail("duplicate op %r" % op)
        seen_ops.add(op)
        target = _check_text(spec.get("target", "project"), name + ".target")
        if target not in TARGETS:
            _fail("intent %r target must be one of %s" % (name, ", ".join(TARGETS)))
        bare = spec.get("bare", [])
        if not isinstance(bare, list) or not bare:
            _fail("intent %r needs at least one bare route" % name)
        out.append({
            "name": name,
            "op": op,
            "target": target,
            "summary": _check_text(spec.get("summary"), name + ".summary"),
            "example": _check_text(spec.get("example"), name + ".example"),
            "bare": [_check_text(b, name + ".bare") for b in bare],
        })
    return out


def _all():
    table = load()
    if table.get("version") != 1:
        _fail("version must be 1")
    seen = {}
    counts = {}
    for intent in _intents(table):
        name = intent["name"]
        for text in intent["bare"]:
            key = _norm(text)
            if key in seen:
                _fail("route %r already used by %s" % (text, seen[key]))
            seen[key] = name
            counts[name] = counts.get(name, 0) + 1
            yield {
                "id": "explain.%s.%d" % (name, counts[name]),
                "op": intent["op"],
                "target": intent["target"],
                "re": "^" + re.escape(text) + "$",
                "args": {},
                "d": intent["summary"],
                "c": "explain",
                "text": text,
                "expect": {},
            }


def entries():
    """Unique catalog entries, in generation order."""
    return _all()


# ---------------------------------------------------------------- render ---
def _number(value, fallback):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return fallback
    if n != n or n < 0:
        return fallback
    return int(n) if n.is_integer() else n


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


def _quote(text):
    return '"' + _one_line(text)[:120] + '"'


def _plural(n, one, many):
    return "%d %s" % (n, one if n == 1 else many)


def _rule(rule_id):
    return "· " + rule_id


def _limits(input):
    l = input.get("limits") or {}

    def get(key, fallback):
        return _number(l.get(key), fallback)

    return {
        "chars": get("explainChars", 8000),
        "files": get("explainFiles", 24),
        "edits": get("explainEdits", 8),
        "project": get("projectBytes", 524288),
        "projectFiles": get("projectFiles", 32),
        "context": get("contextBytes", 8192),
        "planChars": get("planChars", 8000),
        "planSteps": get("planSteps", 40),
        "stepMs": get("stepMs", 4000),
        "planMs": get("planMs", 160000),
        "journalEntries": get("journalEntries", 24),
        "journalBytes": get("journalBytes", 4096),
        "journalText": get("journalText", 240),
    }


def _finish(lines, lim):
    text = "\n".join(lines)
    if _byte_length(text) <= lim["chars"]:
        return text
    note = "\n… trimmed to " + _fmt(lim["chars"]) + " chars (explainChars) " + _rule("r.trim")
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


def _file_role(name):
    n = str(name or "")
    if n == "index.html":
        return "entry page"
    if n == "styles.css":
        return "styles"
    if n == "app.js":
        return "behavior"
    if n == "README.md":
        return "readme"
    if n == "ARCHITECTURE.md":
        return "architecture"
    if n.startswith("systems/"):
        return "system"
    if n.startswith("core/"):
        return "state module"
    if n.startswith("ui/"):
        return "render module"
    if n.startswith("data/"):
        return "data module"
    if n.startswith("content/"):
        return "content module"
    if n.endswith(".css"):
        return "styles"
    if n.endswith(".js"):
        return "script"
    if n.endswith(".html") or n.endswith(".htm"):
        return "page"
    if n.endswith(".json"):
        return "data"
    if n.endswith(".md"):
        return "notes"
    return "file"


def _seed_text(project):
    return str(project["seed"]) if project.get("seed") is not None else "none"


def _seed_rule(project):
    return "r.seed" if project.get("seed") is not None else "r.seed-missing"


def _theme_word(source):
    if source == "prompt":
        return "prompt"
    if source == "seed":
        return "seed"
    if source == "spec":
        return "build spec"
    return "default"


def _theme_rule(source):
    if source == "prompt":
        return "r.theme-prompt"
    if source == "seed":
        return "r.theme-seed"
    if source == "spec":
        return "r.theme-spec"
    return "r.theme-default"


def _theme_line(project):
    page = "light" if project.get("theme") == "light" else "dark"
    name = _one_line(project.get("themeName") or "")
    if not name:
        return ("theme: " + page + " · no named theme · default page class "
                + _rule("r.theme-default"))
    source = project.get("themeSource") or "default"
    return ("theme: " + page + " · named " + _quote(name) + " · from the "
            + _theme_word(source) + " " + _rule(_theme_rule(source)))


def _file_lines(lines, files, lim):
    shown = files[:lim["files"]]
    lines.append("files (%d shown of %d): %s"
                 % (len(shown), len(files), _rule("r.files-listed")))
    for file in shown:
        lines.append("  " + file["name"] + " · " + _fmt(file.get("bytes", 0))
                     + " bytes · " + _fmt(file.get("lines", 0)) + " lines · sha "
                     + str(file.get("sha") or "") + " · " + _file_role(file["name"])
                     + " " + _rule("r.roles"))
    if len(files) > len(shown):
        lines.append("… %d more file(s) not listed %s"
                     % (len(files) - len(shown), _rule("r.files-cap")))


def _edit_line(lines, project, lim):
    edits = project.get("edits") or []
    shown = edits[max(0, len(edits) - lim["edits"]):]
    labels = [_one_line(edit.get("label") or edit.get("id") or "edit")
              for edit in shown]
    lines.append("edits (%d): %s %s"
                 % (len(edits), " · ".join(labels) if labels else "none",
                    _rule("r.edits")))
    if len(edits) > len(shown):
        lines.append("… %d older edit(s) not listed %s"
                     % (len(edits) - len(shown), _rule("r.edits-cap")))


def _journal_line(input):
    journal = input.get("journal") or {}
    entries = journal.get("entries") or []
    summary = journal.get("summary") or {}
    limit = journal.get("limit") or {}
    if not entries:
        return ("journal: empty · 0/" + _fmt(_number(limit.get("entries"), 24))
                + " entries " + _rule("r.journal-empty"))
    latest = entries[-1]
    decisions = _number(summary.get("decisions"), 0)
    rejections = _number(summary.get("rejections"), 0)
    preferences = _number(summary.get("preferences"), 0)
    return ("journal: %d/%s entries · %d decision%s · %d rejection%s · "
            "%d preference%s · latest #%s %s · %s %s"
            % (len(entries), _fmt(_number(limit.get("entries"), 24)),
               decisions, "" if decisions == 1 else "s",
               rejections, "" if rejections == 1 else "s",
               preferences, "" if preferences == 1 else "s",
               _number(latest.get("seq"), 0), latest.get("kind"),
               _one_line(latest.get("topic")), _rule("r.journal")))


def _project_risks(input, project, files, lim):
    risks = []
    context = input.get("context") or {}
    size = _number(project.get("bytes"), 0)
    if not files:
        risks.append(("the project has no files", "r.risk-empty"))
    if lim["project"] > 0 and size * 100 >= lim["project"] * 80:
        risks.append(("project is at %d%% of projectBytes"
                      % round((size / lim["project"]) * 100), "r.risk-budget"))
    if lim["projectFiles"] > 0 and len(files) * 100 >= lim["projectFiles"] * 80:
        risks.append(("files are at %d%% of projectFiles"
                      % round((len(files) / lim["projectFiles"]) * 100),
                      "r.risk-files"))
    context_bytes = _number(context.get("bytes"), 0)
    if lim["context"] > 0 and context_bytes * 100 >= lim["context"] * 80:
        risks.append(("context is at %d%% of contextBytes"
                      % round((context_bytes / lim["context"]) * 100),
                      "r.risk-context"))
    if project.get("seed") is None:
        risks.append(("no seed is stored in the build spec", "r.risk-seed"))
    if not any(file["name"] == "ARCHITECTURE.md" for file in files):
        risks.append(("the project has no ARCHITECTURE.md",
                      "r.risk-architecture"))
    if not ((input.get("journal") or {}).get("entries") or []):
        risks.append(("the journal is empty", "r.risk-journal"))
    plan = input.get("plan")
    if plan and _number(plan.get("failedAt"), -1) >= 0:
        risks.append(("the last plan has an error at step %d"
                      % (_number(plan.get("failedAt"), 0) + 1), "r.risk-plan"))
    return risks


def _project_explain(input):
    lim = _limits(input)
    project = input.get("project")
    if not project:
        return _finish([
            "explain · project · no active project",
            "build something first, then ask again " + _rule("r.project-exists"),
            "writes: no file " + _rule("r.no-write"),
        ], lim)
    files = sorted(project.get("files") or [], key=lambda file: file["name"])
    systems = [file["name"] for file in files
               if str(file["name"]).startswith("systems/")]
    context = input.get("context") or {}
    lines = [
        "explain · project · " + _one_line(project.get("name")) + " · "
        + _plural(len(files), "file", "files") + " · seed "
        + _seed_text(project) + " " + _rule("r.project-exists"),
        "project: " + _one_line(project.get("name")) + " ("
        + _one_line(project.get("slug")) + ") · kind "
        + _one_line(project.get("kind") or "unknown") + " · "
        + _fmt(_number(project.get("bytes"), 0)) + "/" + _fmt(lim["project"])
        + " bytes " + _rule("r.budget-project"),
        _theme_line(project),
    ]
    _file_lines(lines, files, lim)
    lines.append("systems (%d): %s %s"
                 % (len(systems), " · ".join(systems) if systems else "none",
                    _rule("r.systems")))
    _edit_line(lines, project, lim)
    lines.append("seed: " + _seed_text(project) + " · "
                 + ("from the build spec" if project.get("seed") is not None
                    else "no build spec seed is stored") + " "
                 + _rule(_seed_rule(project)))
    lines.append("budgets: files %d/%s · project %s/%s bytes · context %s/%s "
                 "bytes · explain cap %s chars %s"
                 % (len(files), _fmt(lim["projectFiles"]),
                    _fmt(_number(project.get("bytes"), 0)), _fmt(lim["project"]),
                    _fmt(_number(context.get("bytes"), 0)), _fmt(lim["context"]),
                    _fmt(lim["chars"]), _rule("r.limits")))
    lines.append(_journal_line(input))
    risks = _project_risks(input, project, files, lim)
    lines.append("risks (%d):" % len(risks))
    if not risks:
        lines.append("  none " + _rule("r.risk-none"))
    else:
        for text, rule_id in risks:
            lines.append("  · " + text + " " + _rule(rule_id))
    lines.append("writes: no file " + _rule("r.no-write"))
    lines.append(_rules_line(lines))
    return _finish(lines, lim)


def _plan_chars(steps):
    return _byte_length("\n".join(str(step.get("text") or "") for step in steps))


def _plan_risks(plan, steps, lim):
    risks = []
    failed = [step for step in steps if step.get("status") == "error"]
    pending = [step for step in steps if step.get("status") == "pending"]
    router = [step for step in steps if not step.get("exact")]
    seen = {}
    duplicates = []
    for step in steps:
        key = _one_line(step.get("text")).lower()
        if key in seen:
            duplicates.append(step.get("text"))
        seen[key] = True
    if failed:
        risks.append(("step %d failed" % (steps.index(failed[0]) + 1),
                      "r.risk-plan"))
    if pending:
        risks.append((_plural(len(pending), "pending step", "pending steps")
                      + " not run", "r.plan-status"))
    if router:
        risks.append((("%d step has" % len(router) if len(router) == 1
                       else "%d steps have" % len(router)) + " no exact route",
                      "r.plan-router"))
    if duplicates:
        risks.append(("repeated step " + _quote(duplicates[0]), "r.plan-steps"))
    if len(steps) > lim["planSteps"]:
        risks.append(("steps %d/%s" % (len(steps), _fmt(lim["planSteps"])),
                      "r.risk-plan"))
    chars = _plan_chars(steps)
    if chars > lim["planChars"]:
        risks.append(("chars %s/%s" % (_fmt(chars), _fmt(lim["planChars"])),
                      "r.risk-plan"))
    if len(steps) * lim["stepMs"] > lim["planMs"]:
        risks.append(("worst-case time %s s/%s s"
                      % (_fmt((len(steps) * lim["stepMs"]) / 1000),
                         _fmt(lim["planMs"] / 1000)), "r.risk-plan"))
    return risks


def _plan_explain(input):
    lim = _limits(input)
    plan = input.get("plan")
    steps = (plan or {}).get("steps") or []
    if not plan or not steps:
        return _finish([
            "explain · plan · no plan to explain",
            "run a plan first, then ask again " + _rule("r.plan-exists"),
            "writes: no file " + _rule("r.no-write"),
        ], lim)
    done = sum(1 for step in steps if step.get("status") == "done")
    failed = sum(1 for step in steps if step.get("status") == "error")
    pending = sum(1 for step in steps if step.get("status") == "pending")
    chars = _plan_chars(steps)
    time = len(steps) * lim["stepMs"]
    lines = [
        "explain · plan · " + _one_line(plan.get("from") or "plan") + " · "
        + _plural(len(steps), "step", "steps") + " · %d done · %d error · "
        % (done, failed) + "%d pending " % pending + _rule("r.plan-exists"),
        "plan: %d/%s steps · chars %s/%s · time %s s/%s s %s"
        % (len(steps), _fmt(lim["planSteps"]), _fmt(chars), _fmt(lim["planChars"]),
           _fmt(time / 1000), _fmt(lim["planMs"] / 1000), _rule("r.plan-steps")),
    ]
    for index, step in enumerate(steps):
        lines.append("  %d. %s · %s · %s %s"
                     % (index + 1, _one_line(step.get("text")),
                        "exact " + _one_line(step.get("op") or "command")
                        if step.get("exact") else "router",
                        _one_line(step.get("status") or "pending"),
                        _rule("r.plan-status" if step.get("exact") else "r.plan-router")))
    failed_at = _number(plan.get("failedAt"), -1)
    if 0 <= failed_at < len(steps):
        lines.append("failure: step %d · %s %s"
                     % (failed_at + 1,
                        _one_line(plan.get("errorText") or "no error text recorded"),
                        _rule("r.plan-failure")))
    else:
        lines.append("failure: none recorded " + _rule("r.plan-status"))
    lines.append("budgets: steps %d/%s · chars %s/%s · time %s s/%s s · "
                 "explain cap %s chars %s"
                 % (len(steps), _fmt(lim["planSteps"]), _fmt(chars),
                    _fmt(lim["planChars"]), _fmt(time / 1000),
                    _fmt(lim["planMs"] / 1000), _fmt(lim["chars"]),
                    _rule("r.limits")))
    risks = _plan_risks(plan, steps, lim)
    lines.append("risks (%d):" % len(risks))
    if not risks:
        lines.append("  none " + _rule("r.risk-none"))
    else:
        for text, rule_id in risks:
            lines.append("  · " + text + " " + _rule(rule_id))
    lines.append("writes: no file " + _rule("r.no-write"))
    lines.append(_rules_line(lines))
    return _finish(lines, lim)


def _theme_explain(input):
    lim = _limits(input)
    project = input.get("project")
    if not project:
        return _finish([
            "explain · theme · no active project",
            "build something first, then ask again " + _rule("r.project-exists"),
            "writes: no file " + _rule("r.no-write"),
        ], lim)
    context = input.get("context") or {}
    name = _one_line(project.get("themeName") or "")
    source = project.get("themeSource") or "default"
    page = "light" if project.get("theme") == "light" else "dark"
    lines = [
        "explain · theme · " + _one_line(project.get("name")) + " · seed "
        + _seed_text(project) + " " + _rule("r.project-exists"),
        "page: " + page + " · the html class sets the light/dark page theme "
        + _rule("r.theme"),
    ]
    if name:
        lines.append("named: " + _quote(name) + " · from the " + _theme_word(source)
                     + " " + _rule(_theme_rule(source)))
    else:
        lines.append("named: none · no theme word was stored in the build spec "
                     + _rule("r.theme-default"))
    if source == "prompt":
        lines.append("why: the prompt named " + _quote(name)
                     + ", so the build spec stored that theme "
                     + _rule("r.theme-prompt"))
    elif source == "seed":
        lines.append("why: the prompt did not name a theme, so the build used "
                     "the pack chosen by seed " + _seed_text(project) + " "
                     + _rule("r.theme-seed"))
    elif source == "spec":
        lines.append("why: the build spec stores the theme, but neither the "
                     "prompt nor the seed explains it " + _rule("r.theme-spec"))
    else:
        lines.append("why: no theme word was stored, so the page uses the "
                     "default " + page + " class " + _rule("r.theme-default"))
    lines.append("seed: " + _seed_text(project) + " · "
                 + ("the build spec seed chooses seeded content and can choose "
                    "the theme pack" if project.get("seed") is not None
                    else "no seed stored in the build spec") + " "
                 + _rule(_seed_rule(project)))
    if project.get("art") or project.get("subtheme"):
        lines.append("style: " + " · ".join(filter(None, [
            _one_line(project.get("art") or ""),
            _one_line(project.get("subtheme") or ""),
        ])) + " " + _rule("r.theme-spec"))
    if project.get("specLine"):
        lines.append("spec: " + _one_line(project.get("specLine")))
    lines.append("budgets: project %s/%s bytes · context %s/%s bytes · "
                 "explain cap %s chars %s"
                 % (_fmt(_number(project.get("bytes"), 0)), _fmt(lim["project"]),
                    _fmt(_number(context.get("bytes"), 0)), _fmt(lim["context"]),
                    _fmt(lim["chars"]), _rule("r.limits")))
    lines.append("writes: no file " + _rule("r.no-write"))
    lines.append(_rules_line(lines))
    return _finish(lines, lim)


def render(target, input):
    if target == "project":
        return _project_explain(input or {})
    if target == "plan":
        return _plan_explain(input or {})
    if target == "theme":
        return _theme_explain(input or {})
    raise ValueError("unknown explain target: " + target)


# --------------------------------------------------------------- fixture ---
def _limits_state():
    return {
        "explainChars": 8000,
        "explainFiles": 24,
        "explainEdits": 8,
        "projectBytes": 524288,
        "projectFiles": 32,
        "contextBytes": 8192,
        "planChars": 8000,
        "planSteps": 40,
        "stepMs": 4000,
        "planMs": 160000,
        "journalEntries": 24,
        "journalBytes": 4096,
        "journalText": 240,
    }


def _file(name, bytes_, lines, sha):
    return {"name": name, "bytes": bytes_, "lines": lines, "sha": sha}


def _journal(entries):
    summary = {"entries": len(entries), "decisions": 0, "rejections": 0,
               "preferences": 0, "dropped": 0}
    for entry in entries:
        summary[entry["kind"] + "s"] += 1
    return {
        "entries": entries,
        "summary": summary,
        "limit": {"entries": 24, "bytes": 4096, "text": 240},
    }


def _project(**overrides):
    base = {
        "slug": "notes",
        "name": "Notes",
        "kind": "notes",
        "desc": "a quiet place to write",
        "theme": "dark",
        "themeName": "",
        "themeSource": "default",
        "art": "",
        "subtheme": "",
        "seed": 123456789,
        "specLine": "spec · 2D app · notes · flat · seed 123456789",
        "files": [
            _file("ARCHITECTURE.md", 2400, 70, "a1b2c3d4"),
            _file("README.md", 1800, 50, "e5f6a7b8"),
            _file("app.js", 6400, 210, "11223344"),
            _file("index.html", 4200, 120, "55667788"),
            _file("styles.css", 900, 35, "99aabbcc"),
        ],
        "edits": [],
        "bytes": 15700,
    }
    base.update(overrides)
    return base


def _plan(**overrides):
    if "from_" in overrides:
        overrides["from"] = overrides.pop("from_")
    base = {
        "from": "last run",
        "steps": [
            {"text": "build a platformer game", "op": "build", "exact": True,
             "status": "done"},
            {"text": "add a boss", "op": "edit.apply", "exact": True,
             "status": "error"},
            {"text": "add a quest", "op": "edit.apply", "exact": True,
             "status": "pending"},
        ],
        "failedAt": 1,
        "errorText": "no boss in this genre",
    }
    base.update(overrides)
    return base


def states():
    basic_journal = _journal([
        {"seq": 1, "kind": "decision", "topic": "art style",
         "text": "use pixel art", "source": "build"},
        {"seq": 2, "kind": "rejection", "topic": "cloud api",
         "text": "keep it offline", "source": "think.tradeoff"},
        {"seq": 3, "kind": "preference", "topic": "seed",
         "text": "use the same seed", "source": "conversation.correct"},
    ])
    return [
        {
            "name": "project-basic",
            "target": "project",
            "input": {
                "project": _project(),
                "plan": _plan(),
                "journal": basic_journal,
                "context": {"bytes": 1024, "max": 8192},
                "limits": _limits_state(),
            },
        },
        {
            "name": "project-no-seed",
            "target": "project",
            "input": {
                "project": _project(
                    seed=None, themeName="", themeSource="default",
                    files=[
                        _file("README.md", 400, 12, "aaaa1111"),
                        _file("index.html", 900, 30, "bbbb2222"),
                    ],
                    edits=[],
                    bytes=1300,
                ),
                "plan": None,
                "journal": _journal([]),
                "context": {"bytes": 0, "max": 8192},
                "limits": _limits_state(),
            },
        },
        {
            "name": "project-missing",
            "target": "project",
            "input": {
                "project": None,
                "plan": None,
                "journal": _journal([]),
                "context": {"bytes": 0, "max": 8192},
                "limits": _limits_state(),
            },
        },
        {
            "name": "project-capped",
            "target": "project",
            "input": {
                "project": _project(
                    name="Big project",
                    files=[_file("file-%02d.js" % i, 100 + i, 5 + i,
                                 "sha%04d" % i) for i in range(30)],
                    edits=[{"id": "edit-%d" % i, "label": "edit %d" % i}
                           for i in range(12)],
                    bytes=12345,
                ),
                "plan": None,
                "journal": basic_journal,
                "context": {"bytes": 1024, "max": 8192},
                "limits": _limits_state(),
            },
        },
        {
            "name": "project-trimmed",
            "target": "project",
            "input": {
                "project": _project(
                    name="A very long project name that should force the cap",
                    desc="a long description " * 80,
                    files=[_file("file-%02d.js" % i, 100 + i, 5 + i,
                                 "sha%04d" % i) for i in range(30)],
                    edits=[{"id": "edit-%d" % i, "label": "edit %d" % i}
                           for i in range(12)],
                    bytes=12345,
                ),
                "plan": None,
                "journal": basic_journal,
                "context": {"bytes": 1024, "max": 8192},
                "limits": dict(_limits_state(), explainChars=700),
            },
        },
        {
            "name": "project-at-risk",
            "target": "project",
            "input": {
                "project": _project(
                    files=[_file("index.html", 500000, 10, "ffff0000")],
                    edits=[],
                    bytes=500000,
                ),
                "plan": _plan(),
                "journal": _journal([]),
                "context": {"bytes": 8000, "max": 8192},
                "limits": _limits_state(),
            },
        },
        {
            "name": "plan-basic",
            "target": "plan",
            "input": {
                "project": _project(),
                "plan": _plan(),
                "journal": basic_journal,
                "context": {"bytes": 1024, "max": 8192},
                "limits": _limits_state(),
            },
        },
        {
            "name": "plan-missing",
            "target": "plan",
            "input": {
                "project": _project(),
                "plan": None,
                "journal": basic_journal,
                "context": {"bytes": 1024, "max": 8192},
                "limits": _limits_state(),
            },
        },
        {
            "name": "plan-router",
            "target": "plan",
            "input": {
                "project": _project(),
                "plan": _plan(
                    from_="active plan",
                    steps=[
                        {"text": "do something unusual", "op": "router",
                         "exact": False, "status": "pending"},
                        {"text": "do something unusual", "op": "router",
                         "exact": False, "status": "pending"},
                    ],
                    failedAt=-1,
                    errorText="",
                ),
                "journal": basic_journal,
                "context": {"bytes": 1024, "max": 8192},
                "limits": _limits_state(),
            },
        },
        {
            "name": "theme-prompt",
            "target": "theme",
            "input": {
                "project": _project(
                    name="Neon RPG",
                    kind="rpg",
                    desc="a neon cyberpunk rpg",
                    theme="dark",
                    themeName="Neon",
                    themeSource="prompt",
                    art="pixel",
                    subtheme="rain",
                    seed=987654321,
                    specLine="spec · 2D top-down · rpg · pixel · Neon · rain · seed 987654321",
                ),
                "plan": _plan(),
                "journal": basic_journal,
                "context": {"bytes": 1024, "max": 8192},
                "limits": _limits_state(),
            },
        },
        {
            "name": "theme-seed",
            "target": "theme",
            "input": {
                "project": _project(
                    name="Quiet Harbor RPG",
                    kind="rpg",
                    desc="an rpg with no theme words",
                    theme="dark",
                    themeName="Rain City",
                    themeSource="seed",
                    art="pixel",
                    subtheme="",
                    seed=42,
                    specLine="spec · 2D top-down · rpg · pixel · Rain City · seed 42",
                ),
                "plan": _plan(),
                "journal": basic_journal,
                "context": {"bytes": 1024, "max": 8192},
                "limits": _limits_state(),
            },
        },
        {
            "name": "theme-default",
            "target": "theme",
            "input": {
                "project": _project(
                    name="Notes",
                    kind="notes",
                    desc="a quiet place to write",
                    theme="light",
                    themeName="",
                    themeSource="default",
                    art="flat",
                    subtheme="",
                    seed=7,
                    specLine="spec · 2D app · notes · flat · seed 7",
                ),
                "plan": None,
                "journal": _journal([]),
                "context": {"bytes": 0, "max": 8192},
                "limits": _limits_state(),
            },
        },
        {
            "name": "theme-missing",
            "target": "theme",
            "input": {
                "project": None,
                "plan": None,
                "journal": _journal([]),
                "context": {"bytes": 0, "max": 8192},
                "limits": _limits_state(),
            },
        },
    ]


def fixture():
    cases = [
        {"text": entry["text"], "op": entry["op"], "args": entry["expect"],
         "target": entry["target"]}
        for entry in entries()
    ]
    cases.sort(key=lambda case: (case["op"], case["text"]))
    targets = {}
    for case in cases:
        targets[case["target"]] = targets.get(case["target"], 0) + 1
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
        "targets": dict(sorted(targets.items())),
        "cases": cases,
        "states": rendered,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true",
                       help="refresh tests/fixtures/explain.json")
    group.add_argument("--check", action="store_true",
                       help="fail if the fixture drifted")
    args = parser.parse_args(argv)
    doc = fixture()
    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        print("wrote %s (%d cases, %d states, %d targets)"
              % (FIXTURE.relative_to(ROOT.parent), doc["count"],
                 len(doc["states"]), len(doc["targets"])))
        return 0
    if args.check:
        if not FIXTURE.exists():
            print("missing fixture; run --write", file=sys.stderr)
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != doc:
            print("explain fixture drifted; run --write", file=sys.stderr)
            return 1
        print("explain fixture is current")
        return 0
    print(json.dumps(doc["targets"], indent=2))
    print("%d cases, %d states" % (doc["count"], len(doc["states"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

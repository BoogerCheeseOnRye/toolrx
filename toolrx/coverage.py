#!/usr/bin/env python3
"""Deterministic coverage report for the command library and fixture suite.

The report answers two questions without a model call:

* how much of the catalog can ever fire (pure literals, duplicate ids, and
  literals that an earlier command already shadows), and
* how every long-form fixture family resolves: exact command, router, chat
  fallback, or an intentional refusal.

Run it to print the table, ``--write`` to refresh ``toolrx/coverage.json``, and
``--check`` to fail when the checked-in report drifts from the catalog. The
dead-literal audit is included in both modes; it is cheap because a pure
literal can only be shadowed by a command whose literal prefix matches it.

    python3 toolrx/coverage.py
    python3 toolrx/coverage.py --write
    python3 toolrx/coverage.py --check
"""
import argparse
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMMANDS = HERE / "web" / "commands.json"
MODEL = HERE / "micro_model.json"
FIXTURES = ROOT / "tests" / "fixtures" / "longform.json"
REPORT = HERE / "coverage.json"

sys.path.insert(0, str(HERE))

import longform  # noqa: E402
import router  # noqa: E402
import security  # noqa: E402

FAMILIES = ("routing", "plans", "builds", "growth", "context", "refusals")
DEFAULT_CONFIDENCE = 0.50
DEFAULT_MARGIN = 0.02
_METACHARS = ".^$*+?()[]{}|"
_NUMBER_WORDS = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
)
_NUMERIC_PREFIXES = ["-", "."] + [str(d) for d in range(10)] + list(_NUMBER_WORDS)
_NUMBER_TOKEN = re.compile(r"\b(?:" + "|".join(_NUMBER_WORDS) + r")\b")

_UNIT_STOPWORDS = {
    "to", "into", "in", "are", "is", "equals", "what", "how", "many",
    "convert", "of", "a", "an", "the",
}
_WORD = re.compile(r"[a-z]+|\d+")
# Keep in sync with the command-shaped guard in toolrx/web/skills.js
# chatReply(). When it matches, chat declines and the browser uses the router
# result even if confidence is below the conversation threshold.
_CHAT_DECLINE = re.compile(
    r"^(?:read|list|write|delete|remove|open|show|run|convert|calculate|calc|"
    r"count|find|search|define|summarize|build|make|create|plan|blueprint|new|"
    r"rename|multiply|divide|add|subtract|square|uppercase|lowercase|reverse|"
    r"hash|encode|decode)\b",
    re.I,
)


def _unit_tokens(cmd):
    """Literal unit words a units command requires, or ``None``.

    Every conversion names at least one source/target unit, so a query with
    none of those words cannot match. This keeps a prompt like "one of the
    background monitors" from compiling hundreds of conversion regexes just
    because it starts with the number word "one".
    """
    if cmd["c"] != "units":
        return None
    tokens = set()
    for group in re.findall(r"\(\?:([^()]*)\)", cmd["re"]):
        for alt in group.split("|"):
            alt = alt.strip().lower()
            if re.fullmatch(r"[a-z][a-z ]*", alt) and alt not in _UNIT_STOPWORDS:
                tokens.add(alt)
                tokens.update(part for part in alt.split() if part)
    for key in ("from", "to"):
        value = str(cmd.get("args", {}).get(key, "")).lower()
        if value:
            tokens.add(value)
    return tokens or None


def _has_number(text):
    low = str(text or "").lower()
    return any(ch.isdigit() for ch in low) or bool(_NUMBER_TOKEN.search(low))


def _numeric_after(text):
    """True when a numeric command could still match ``text``.

    This is deliberately conservative. A number may sit after an arbitrary
    literal prefix (``how many cups in 2 liters``), so the only safe skip is
    when the query contains no digit and no number word at all.
    """
    return _has_number(text)


# --------------------------------------------------------------- matching ---
def normalize_query(text):
    """Mirror toolrx/web/skills.js match() before a regex is tried."""
    q = re.sub(r"\s+", " ", str(text or "")).strip()
    q = re.sub(r"[?!]+$", "", q)
    return re.sub(r"\.$", "", q)


def _trie_node():
    return {"items": [], "children": {}}


class PrefixIndex:
    """First-match lookup without compiling the whole catalog.

    Every command is filed under the literal prefixes its regex must start
    with. A query walks the trie once, then only the commands on that path are
    compiled and tested in catalog order. The result is identical to scanning
    every command, but a coverage run compiles hundreds of patterns instead of
    all of them.
    """

    def __init__(self, commands):
        self.commands = commands
        self.root = _trie_node()
        self._compiled = {}
        self._literals = [literal_text(cmd) for cmd in commands]
        self._needs_number = ["\\d[\\d,]*" in cmd["re"] for cmd in commands]
        self._unit_tokens = [_unit_tokens(cmd) for cmd in commands]
        for index, cmd in enumerate(commands):
            seen = set()
            for prefix in leading_prefixes(cmd["re"]):
                key = prefix.lower()
                if key in seen:
                    continue
                seen.add(key)
                node = self.root
                for ch in key:
                    node = node["children"].setdefault(ch, _trie_node())
                node["items"].append((index, key))

    def candidates(self, text):
        """Map command index to the longest literal prefix it matched."""
        node = self.root
        found = dict(self.root["items"])
        for ch in text.lower():
            node = node["children"].get(ch)
            if node is None:
                break
            for index, prefix in node["items"]:
                found[index] = prefix
        return found

    def unit_ok(self, index, text):
        tokens = self._unit_tokens[index]
        return tokens is None or bool(tokens & set(_WORD.findall(text.lower())))

    def rx(self, index):
        rx = self._compiled.get(index)
        if rx is None:
            rx = re.compile(self.commands[index]["re"], re.I)
            self._compiled[index] = rx
        return rx

    def first_match(self, query):
        q = normalize_query(query)
        if not q:
            return None
        low = q.lower()
        candidates = self.candidates(q)
        for index in sorted(candidates):
            if self._needs_number[index] and not _numeric_after(q):
                continue
            if not self.unit_ok(index, q):
                continue
            literal = self._literals[index]
            if literal is not None:
                if literal.lower() == low:
                    return self.commands[index]
                continue
            if self.rx(index).match(q):
                return self.commands[index]
        return None


def _group_alternatives(pattern, start):
    """Parse a simple ``(?:a|b|c)`` group into literal alternatives.

    Returns ``(alternatives, closing_index)`` or ``(None, index)`` when the
    group is not a plain literal alternation. A failed parse is safe: the
    caller keeps the prefix it already proved.
    """
    alts, current, i = [], "", start
    while i < len(pattern):
        ch = pattern[i]
        if ch == "\\":
            if i + 1 < len(pattern) and not pattern[i + 1].isalnum():
                current += pattern[i + 1]
                i += 2
                continue
            return None, i
        if ch == "|":
            alts.append(current)
            current = ""
            i += 1
            continue
        if ch == ")":
            alts.append(current)
            return alts, i
        if ch in "([":
            return None, i
        if ch in _METACHARS:
            return None, i
        current += ch
        i += 1
    return None, i


def leading_prefixes(pattern):
    """Literal prefixes every match of ``pattern`` must start with.

    The list is conservative: ``[""]`` means "no useful prefix, always test".
    It is used only to skip impossible candidates in the dead-literal audit,
    never to decide a match.
    """
    if not pattern.startswith("^"):
        return [""]
    # The numeric envelope is shared by math and unit patterns and starts with
    # an optional sign. Its first character is still knowable, which keeps
    # those commands out of the always-test bucket.
    if pattern.startswith("^(-?"):
        return list(_NUMERIC_PREFIXES)
    i, prefixes = 1, [""]
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("(?:", i):
            alts, close = _group_alternatives(pattern, i + 3)
            if alts is None:
                return prefixes or [""]
            if close + 1 < len(pattern) and pattern[close + 1] in "?*":
                return [""]
            prefixes = [prefix + alt for prefix in prefixes for alt in alts]
            i = close + 1
            continue
        if ch == "\\":
            if i + 1 < len(pattern) and not pattern[i + 1].isalnum():
                prefixes = [prefix + pattern[i + 1] for prefix in prefixes]
                i += 2
                continue
            break
        if ch in _METACHARS:
            if ch in "?*":
                prefixes = [prefix[:-1] for prefix in prefixes]
            break
        prefixes = [prefix + ch for prefix in prefixes]
        i += 1
    return prefixes or [""]


_LITERAL_CACHE = {}


def literal_text(cmd):
    """Return the one string a pure-literal command can match, or ``None``."""
    pattern = cmd["re"]
    if pattern in _LITERAL_CACHE:
        return _LITERAL_CACHE[pattern]
    result = _literal_text_uncached(pattern)
    _LITERAL_CACHE[pattern] = result
    return result


def _literal_text_uncached(pattern):
    if not (pattern.startswith("^") and pattern.endswith("$")):
        return None
    body = pattern[1:-1]
    if any(ch in body for ch in "()[]?*+|{}^$"):
        return None
    out, i = [], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\":
            if i + 1 >= len(body):
                return None
            nxt = body[i + 1]
            if nxt.isalnum():
                return None
            out.append(nxt)
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


# ------------------------------------------------------------------ audit ---
def _pattern_key(pattern):
    return re.sub(r"\s+", "", pattern.lower().replace("\\ ", " "))


def catalog_stats(commands, model_path=MODEL):
    ids = [cmd["id"] for cmd in commands]
    keys = {}
    for cmd in commands:
        key = _pattern_key(cmd["re"])
        keys[key] = keys.get(key, 0) + 1
    categories = {}
    for cmd in commands:
        categories[cmd["c"]] = categories.get(cmd["c"], 0) + 1
    return {
        "count": len(commands),
        "categories": dict(sorted(categories.items())),
        "pure_literals": sum(1 for cmd in commands if literal_text(cmd) is not None),
        "duplicate_ids": len(ids) - len(set(ids)),
        "duplicate_patterns": sum(count - 1 for count in keys.values() if count > 1),
        "model_bytes": Path(model_path).stat().st_size,
    }


def dead_literal_audit(commands, index=None):
    """Find pure literals that an earlier command already shadows.

    A pure literal matches exactly one string. If any earlier command matches
    that same string, the literal can never be the first match and is dead.
    The prefix index supplies only commands whose literal prefix is a prefix
    of the candidate text, so the audit stays linear in the catalog.
    """
    index = index or PrefixIndex(commands)
    dead = []
    for position, cmd in enumerate(commands):
        text = literal_text(cmd)
        if text is None:
            continue
        candidates = index.candidates(text)
        for other_index in sorted(candidates):
            if other_index >= position:
                break
            if (index._needs_number[other_index]
                    and not _numeric_after(text)):
                continue
            if not index.unit_ok(other_index, text):
                continue
            other_literal = index._literals[other_index]
            if other_literal is not None:
                if other_literal.lower() == text.lower():
                    dead.append({
                        "id": cmd["id"],
                        "shadowed_by": commands[other_index]["id"],
                        "text": text,
                    })
                    break
                continue
            if index.rx(other_index).match(text):
                dead.append({
                    "id": cmd["id"],
                    "shadowed_by": commands[other_index]["id"],
                    "text": text,
                })
                break
    return dead


# ---------------------------------------------------------------- fixtures ---
def _family_floor(fixtures, family):
    spec = fixtures.get("families", {}).get(family, {})
    return (float(spec.get("minConfidence", DEFAULT_CONFIDENCE)),
            float(spec.get("minMargin", DEFAULT_MARGIN)))


def _case_units(family, case, floor):
    """Yield ``(label, query, (min_confidence, min_margin))`` for one case."""
    label = case.get("family") or family
    if family == "routing":
        yield label, case["query"], floor
    elif family == "plans":
        case_floor = (float(case.get("minConfidence", floor[0])),
                      float(case.get("minMargin", floor[1])))
        for step in longform.split_info(case["query"])["steps"]:
            yield label, step, case_floor
    elif family == "builds":
        yield label, case["query"], floor
    elif family == "growth":
        yield "base", case["base"], floor
        for step in case["steps"]:
            yield label, step["query"], floor
    elif family == "context":
        for key in ("base", "plan", "expand", "continue", "edit",
                    "otherProject", "returnCommand"):
            if not case.get(key):
                continue
            value = case[key]
            if key == "plan":
                for step in longform.split_info(value)["steps"]:
                    yield "plan", step, floor
            else:
                yield key, value, floor
    elif family == "refusals":
        yield "refusals", case["query"], floor


def _new_bucket():
    return {
        "cases": 0,
        "units": 0,
        "lanes": {"exact": 0, "router": 0, "fallback": 0, "refusal": 0},
        "confidence": [],
        "margin": [],
    }


def _stats(values):
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    return {
        "n": n,
        "min": round(ordered[0], 4),
        "p10": round(ordered[max(0, int(round(0.1 * (n - 1))))], 4),
        "median": round(statistics.median(ordered), 4),
        "max": round(ordered[-1], 4),
    }


def _finalize(bucket):
    return {
        "cases": bucket["cases"],
        "units": bucket["units"],
        "lanes": bucket["lanes"],
        "confidence": _stats(bucket["confidence"]),
        "margin": _stats(bucket["margin"]),
    }


def fixture_coverage(fixtures, commands, model, policy, index=None):
    index = index or PrefixIndex(commands)
    report = {}
    for family in FAMILIES:
        floor = _family_floor(fixtures, family)
        family_bucket = _new_bucket()
        sub = {}
        for case in fixtures.get(family, []):
            family_bucket["cases"] += 1
            units = list(_case_units(family, case, floor))
            for label in sorted({unit[0] for unit in units}):
                sub.setdefault(label, _new_bucket())["cases"] += 1
            for label, query, unit_floor in units:
                bucket = sub.setdefault(label, _new_bucket())
                bucket["units"] += 1
                family_bucket["units"] += 1
                if family == "refusals":
                    lane, decision = "refusal", None
                else:
                    hit = index.first_match(query)
                    if hit is not None:
                        lane, decision = "exact", None
                    else:
                        clean = policy.normalize(query)
                        decision = router.route(clean, model)
                        if (decision["confidence"] >= unit_floor[0]
                                and decision["margin"] >= unit_floor[1]):
                            lane = "router"
                        elif _CHAT_DECLINE.match(query.strip()):
                            # Command-shaped text makes chat decline, so the
                            # browser still uses the router result (often an
                            # intentional error such as a missing file).
                            lane = "router"
                        else:
                            lane = "fallback"
                bucket["lanes"][lane] += 1
                family_bucket["lanes"][lane] += 1
                if decision is not None:
                    bucket["confidence"].append(decision["confidence"])
                    bucket["margin"].append(decision["margin"])
                    family_bucket["confidence"].append(decision["confidence"])
                    family_bucket["margin"].append(decision["margin"])
        report[family] = _finalize(family_bucket)
        report[family]["subfamilies"] = {
            label: _finalize(bucket) for label, bucket in sorted(sub.items())
        }
        if family == "refusals":
            report[family]["reasons"] = {
                case["reason"]: sum(1 for other in fixtures.get(family, [])
                                    if other.get("reason") == case["reason"])
                for case in fixtures.get(family, [])
            }
    return report


# ------------------------------------------------------------------ report ---
def build_report(full=True):
    commands = json.loads(COMMANDS.read_text(encoding="utf-8"))["commands"]
    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    model = router.load(str(MODEL))
    policy = security.SecurityPolicy.load()
    index = PrefixIndex(commands)
    catalog = catalog_stats(commands)
    if full:
        dead = dead_literal_audit(commands, index)
        catalog["dead_literals"] = len(dead)
        audit = {"mode": "full", "dead_literals": len(dead),
                 "examples": dead[:10]}
    else:
        catalog["dead_literals"] = None
        audit = {"mode": "quick", "dead_literals": None, "examples": []}
    return {
        "version": 1,
        "catalog": catalog,
        "fixtures": fixture_coverage(fixtures, commands, model, policy, index),
        "audit": audit,
    }


def write_report(report, path=REPORT):
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def check(full=True, path=REPORT):
    if not path.exists():
        return False, [f"missing report: {path}"]
    saved = json.loads(path.read_text(encoding="utf-8"))
    current = build_report(full=full)
    problems = []
    for side, name in ((saved, "saved"), (current, "current")):
        if side.get("version") != 1:
            problems.append(f"{name} report version is not 1")
    saved_catalog = dict(saved.get("catalog", {}))
    current_catalog = dict(current.get("catalog", {}))
    saved_dead = saved_catalog.pop("dead_literals", None)
    current_catalog.pop("dead_literals", None)
    if saved_catalog != current_catalog:
        problems.append("catalog section drifted; run --write")
    if saved.get("fixtures") != current.get("fixtures"):
        problems.append("fixture coverage drifted; run --write")
    if saved_dead not in (0, None):
        problems.append(f"checked-in report has {saved_dead} dead literal(s)")
    if full:
        if saved.get("audit") != current.get("audit"):
            problems.append("dead-literal audit drifted; run --write")
    elif saved.get("audit", {}).get("mode") != "full":
        problems.append("checked-in report is not a full audit; run --write")
    return not problems, problems


def print_table(report):
    catalog = report["catalog"]
    dead = catalog.get("dead_literals")
    dead_text = "not audited" if dead is None else str(dead)
    print(f"catalog: {catalog['count']:,} commands, "
          f"{catalog['pure_literals']:,} pure literals, "
          f"{catalog['duplicate_ids']} duplicate ids, "
          f"{catalog['duplicate_patterns']} duplicate patterns, "
          f"{dead_text} dead literals")
    for family in FAMILIES:
        row = report["fixtures"][family]
        lanes = row["lanes"]
        print(f"\n{family}: {row['cases']} cases, {row['units']} units "
              f"(exact {lanes['exact']}, router {lanes['router']}, "
              f"fallback {lanes['fallback']}, refusal {lanes['refusal']})")
        for label, sub in row["subfamilies"].items():
            lanes = sub["lanes"]
            stats = sub["margin"]
            margin = "" if stats is None else (
                f" margin min {stats['min']:.3f} / median {stats['median']:.3f}")
            print(f"  {label:24} {sub['units']:3} units  "
                  f"exact {lanes['exact']:3}  router {lanes['router']:3}  "
                  f"fallback {lanes['fallback']:3}  "
                  f"refusal {lanes['refusal']:3}{margin}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="refresh toolrx/coverage.json")
    parser.add_argument("--check", action="store_true",
                        help="fail if the checked-in report drifted")
    parser.add_argument("--json", action="store_true",
                        help="print the report as JSON")
    args = parser.parse_args(argv)
    if args.check:
        ok, problems = check(full=True)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 0 if ok else 1
    report = build_report(full=True)
    if args.write:
        write_report(report)
        print(f"wrote {REPORT}")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_table(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

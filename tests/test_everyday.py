#!/usr/bin/env python3
"""Contract tests for the everyday paraphrase layer (step 46).

`toolrx/everyday.py` is the only source of everyday phrasings. It feeds the
generated catalog and `tests/fixtures/everyday.json`, so these tests compare the
fixture against the exact matcher the Pages build ships. No model, no network.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COMMANDS = os.path.join(ROOT, "toolrx", "web", "commands.json")
FIXTURE = os.path.join(HERE, "fixtures", "everyday.json")
EVERYDAY = os.path.join(ROOT, "toolrx", "everyday.py")
NODE = shutil.which("node")

MIN_CASES = 500
MIN_FAMILIES = 10
EXACT_FLOOR = 0.90


def _normalize(q):
    q = re.sub(r"\s+", " ", q).strip()
    q = re.sub(r"[?!]+$", "", q)
    return re.sub(r"\.$", "", q)


class EverydayLayerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(COMMANDS, encoding="utf-8") as f:
            cls.catalog = json.load(f)
        with open(FIXTURE, encoding="utf-8") as f:
            cls.fixture = json.load(f)
        cls.commands = cls.catalog["commands"]
        cls.compiled = [(c, re.compile(c["re"], re.I)) for c in cls.commands]

    def first(self, query):
        q = _normalize(query)
        for command, rx in self.compiled:
            if rx.match(q):
                return command
        return None

    def args_for(self, command, query):
        """Expand $n placeholders exactly like web/skills.js applyArgs()."""
        m = re.match(command["re"], _normalize(query), re.I)
        self.assertIsNotNone(m, query)

        def fill(value):
            if not isinstance(value, str):
                return value
            if re.fullmatch(r"\$\d+", value):
                return m.group(int(value[1:])) or ""
            return re.sub(r"\$(\d+)",
                          lambda hit: m.group(int(hit.group(1))) or "", value)
        return {k: fill(v) for k, v in command["args"].items()}

    def test_fixture_is_large_and_covers_ten_families(self):
        cases = self.fixture["cases"]
        self.assertEqual(self.fixture["version"], 1)
        self.assertEqual(self.fixture["count"], len(cases))
        self.assertGreaterEqual(len(cases), MIN_CASES)
        families = {}
        for case in cases:
            families[case["family"]] = families.get(case["family"], 0) + 1
        self.assertGreaterEqual(len(families), MIN_FAMILIES)
        self.assertEqual(self.fixture["families"], dict(sorted(families.items())))
        # Every family carries real weight, not a token one or two cases.
        self.assertTrue(all(n >= 30 for n in families.values()), families)

    def test_fixture_is_current(self):
        proc = subprocess.run([sys.executable, EVERYDAY, "--check"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        self.assertIn("current", proc.stdout)

    def test_every_case_resolves_to_its_exact_command(self):
        failures, exact = [], 0
        for case in self.fixture["cases"]:
            hit = self.first(case["text"])
            if hit is None:
                failures.append((case["text"], "no match"))
                continue
            if hit["op"] in ("chat", "router", "none"):
                failures.append((case["text"], "fallback: " + hit["op"]))
                continue
            if not hit["id"].startswith("everyday."):
                failures.append((case["text"], "shadowed by " + hit["id"]))
                continue
            if hit["op"] != case["op"]:
                failures.append((case["text"], "op %s != %s"
                                 % (hit["op"], case["op"])))
                continue
            args = self.args_for(hit, case["text"])
            if args != case["args"]:
                failures.append((case["text"], "args %r != %r"
                                 % (args, case["args"])))
                continue
            exact += 1
        self.assertFalse(failures, failures[:10])
        self.assertGreaterEqual(exact / len(self.fixture["cases"]), EXACT_FLOOR)
        self.assertEqual(exact, len(self.fixture["cases"]))

    def test_every_case_is_a_new_catalog_entry(self):
        ids = {c["id"]: c for c in self.commands}
        for case in self.fixture["cases"]:
            hit = self.first(case["text"])
            self.assertIsNotNone(hit, case["text"])
            self.assertIn(hit["id"], ids)
            self.assertTrue(hit["id"].startswith("everyday."), hit["id"])

    def test_catalog_ids_and_patterns_are_unique(self):
        ids, patterns = set(), set()
        for command in self.commands:
            self.assertNotIn(command["id"], ids, command["id"])
            ids.add(command["id"])
            key = re.sub(r"\s+", "", command["re"].lower().replace("\\ ", " "))
            self.assertNotIn(key, patterns, command["re"])
            patterns.add(key)
        everyday = [c for c in self.commands if c["id"].startswith("everyday.")]
        self.assertEqual(len(everyday), len(self.fixture["cases"]))

    def test_everyday_catalog_matches_the_table(self):
        sys.path.insert(0, os.path.join(ROOT, "toolrx"))
        try:
            import everyday  # noqa: WPS433 (local module under test)
        finally:
            sys.path.pop(0)
        table = list(everyday.entries())
        self.assertEqual(len(table), len(self.fixture["cases"]))
        by_id = {c["id"]: c for c in self.commands if c["id"].startswith("everyday.")}
        self.assertEqual(set(by_id), {e["id"] for e in table})
        for entry in table:
            shipped = by_id[entry["id"]]
            self.assertEqual(shipped["op"], entry["op"])
            self.assertEqual(shipped["re"], entry["re"])
            self.assertEqual(shipped["args"], entry["args"])
            self.assertEqual(shipped["c"], entry["c"])

    @unittest.skipUnless(NODE, "node is not installed")
    def test_js_plan_preview_resolves_every_case_exactly(self):
        script = r"""
const fs = require('fs');
const COMMANDS = process.argv[1], LIMITS = process.argv[2];
const SKILLS = process.argv[3], FIXTURE = process.argv[4];
global.self = global;
global.fetch = () => Promise.resolve({
  ok: true,
  json: () => Promise.resolve(JSON.parse(fs.readFileSync(COMMANDS, 'utf8'))),
});
const store = {};
global.localStorage = {
  getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.CustomEvent = class { constructor(type, opts) { this.type = type; this.detail = opts && opts.detail; } };
global.dispatchEvent = () => {};
global.toolrxRouter = { load: () => ({}), route: () => ({ tool: 'none', args: {}, confidence: 0 }) };
eval(fs.readFileSync(LIMITS, 'utf8'));
eval(fs.readFileSync(SKILLS, 'utf8'));
(async () => {
  await self.toolrxSkills.init('commands.json');
  const cases = JSON.parse(fs.readFileSync(FIXTURE, 'utf8')).cases;
  const rows = cases.map(c => {
    const p = self.toolrxSkills.planPreview(c.text);
    const step = p.steps.length === 1 ? p.steps[0] : {};
    return { text: c.text, op: c.op, via: step.via || 'multi',
             exact: !!step.exact, steps: p.steps.length, blocked: !!p.blocked };
  });
  const bad = rows.filter(r => !r.exact || r.blocked || r.steps !== 1
                               || r.via !== r.op);
  console.log(JSON.stringify({ total: rows.length,
                               exact: rows.filter(r => r.exact).length,
                               bad: bad.slice(0, 10) }));
})().catch(e => { console.error(e.stack || e); process.exit(1); });
"""
        proc = subprocess.run(
            [NODE, "-e", script, COMMANDS,
             os.path.join(ROOT, "toolrx", "web", "limits.js"),
             os.path.join(ROOT, "toolrx", "web", "skills.js"), FIXTURE],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
        result = json.loads(proc.stdout)
        self.assertEqual(result["total"], len(self.fixture["cases"]))
        self.assertEqual(result["exact"], result["total"])
        self.assertFalse(result["bad"], result["bad"])

    def test_docs_quote_the_current_catalog_count(self):
        count = self.catalog["count"]
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        with open(os.path.join(ROOT, "docs", "pitch.html"), encoding="utf-8") as f:
            pitch = f.read()
        self.assertIn("`toolrx/build_commands.py` (`toolrx/web/commands.json`, %s patterns:"
                      % f"{count:,}", readme)
        self.assertIn("<b>%s</b> commands" % f"{count:,}", pitch)
        self.assertIn("<div class=\"v\">%s</div><div class=\"k\">deterministic commands"
                      % f"{count:,}", pitch)


if __name__ == "__main__":
    unittest.main()

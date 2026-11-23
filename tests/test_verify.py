#!/usr/bin/env python3
"""Step 66: deterministic project verification helpers.

`toolrx/verify.json` is the only source of the `verify.*` routes; it feeds the
catalog and `tests/fixtures/verify.json`. `toolrx/web/verify.js` is the pure
program and `toolrx/verify.py` is its byte-identical Python twin. These tests
check the table, then drive the real modules in Node: every state renders
byte-identically twice, expected files match real `templates.project()` output,
missing and extra names are exact, smoke checks cover pass/fail/empty cases,
the report is bounded, both stores round-trip, and no verify route touches the
network.
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
CORE = os.path.join(ROOT, "toolrx")
WEB = os.path.join(CORE, "web")
FIXTURE = os.path.join(HERE, "fixtures", "verify.json")
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import envelope  # noqa: E402
import verify  # noqa: E402

JS = r"""
const fs = require('fs');
const path = require('path');
const WEB = process.argv[1];
const COMMANDS = process.argv[2];
const MODEL = process.argv[3];
const FIXTURE = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));

global.self = global;
let fetches = 0;
global.fetch = (url) => {
  fetches += 1;
  const name = String(url).split('/').pop();
  const file = name === 'model.json' ? MODEL
    : name === 'commands.json' ? COMMANDS
    : path.join(WEB, name);
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(JSON.parse(fs.readFileSync(file, 'utf8'))),
  });
};
const store = {};
global.localStorage = {
  getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.CustomEvent = class {
  constructor(type, opts) { this.type = type; this.detail = opts && opts.detail; }
};
global.dispatchEvent = () => {};

for (const name of [
  'blake2b.js', 'router.js', 'limits.js', 'budget.js', 'planrewrite.js',
  'thinking.js', 'explain.js', 'verify.js', 'repair.js', 'trace.js',
  'journal.js', 'workspace.js', 'events.js', 'style.js', 'context.js',
  'skills.js', 'templates.js', 'patches.js', 'engine2d.js',
  'engine2d.embed.js', 'engine3d.js', 'engine3d.embed.js', 'worldgen.js',
  'worldgen.embed.js', 'rpg2.js', 'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

const ask = async q => {
  const list = await self.toolrxWeb.prompt(q);
  const r = list[list.length - 1] || {};
  return { step: r.step, text: String(r.text || ''), via: r.via || '',
           error: !!r.error };
};

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const out = { routes: [], pure: {}, chat: {}, templates: [], growth: {},
                threeD: {}, limits: {}, fetches: 0 };
  const V = self.toolrxVerify;
  const T = self.toolrxTemplates;
  const P = self.toolrxPatches;

  out.limits.files = self.toolrxLimits.verifyFiles;
  out.limits.checks = self.toolrxLimits.verifyChecks;
  out.limits.chars = self.toolrxLimits.verifyReportChars;

  FIXTURE.cases.forEach(c => {
    const hit = self.toolrxSkills.match(c.text);
    out.routes.push({ text: c.text, want: c.op, got: hit ? hit.op : null });
  });

  FIXTURE.states.forEach(state => {
    const first = V.run(state.target, state.input);
    const second = V.run(state.target, state.input);
    out.pure[state.name] = { first, second, want: state.want };
  });

  // Expected-file derivation must match the real multi-file build for every
  // genre, 3D route, content spec, and starter. This is the drift pin.
  const cases = [
    ['calculator', 'a calculator'],
    ['todo', 'a todo list'],
    ['notes', 'a notes app'],
    ['platformer', 'a platformer game'],
    ['platformer', 'a 3d platformer game'],
    ['maze', 'a maze game'],
    ['maze', 'a 3d maze'],
    ['racer', 'a 3d racer'],
    ['explore', 'a low poly island'],
    ['waveshooter', 'a wave shooter'],
    ['builder', 'a block builder'],
    ['snake', 'a 3d snake'],
    ['snake', 'a snake game'],
    ['shooter', 'a top down shooter'],
    ['rpg', 'an rpg with 10 quests'],
    ['rpg', 'a neon cyberpunk rpg'],
    ['authapp', 'a sign in starter'],
    ['datadash', 'a data dashboard'],
    ['notebook', 'a notebook'],
    ['multipage', 'a static site'],
    ['apimock', 'an api mock'],
    ['tetris', 'tetris'],
    ['breakout', 'breakout'],
    ['pong', 'pong'],
    ['2048', '2048'],
    ['minesweeper', 'minesweeper'],
    ['adventure', 'a text adventure'],
    ['typing', 'a typing test'],
    ['social', 'a tiny social feed'],
    ['blog', 'a journal'],
    ['forum', 'a forum'],
    ['chat', 'a chat app'],
    ['research', 'research note'],
    ['twinstick', 'a twin stick shooter'],
    ['roguelike', 'a roguelike'],
    ['towerdefense', 'a tower defense game'],
    ['merges', 'a merge game'],
    ['farmingsim', 'a farming sim'],
    ['cardbattler', 'a card battler'],
    ['rhythm', 'a rhythm game'],
    ['landing', 'a landing page'],
    ['markdown', 'a markdown editor'],
    ['expenses', 'an expense tracker'],
    ['clock', 'a clock'],
    ['converter', 'a unit converter'],
    ['chart', 'a bar chart'],
    ['dashboard', 'a metrics dashboard'],
    ['memory', 'a memory game'],
    ['tictactoe', 'tic tac toe'],
    ['timer', 'a countdown timer'],
    ['pomodoro', 'a pomodoro'],
    ['stopwatch', 'a stopwatch'],
  ];
  cases.forEach(([kind, desc]) => {
    const built = T.project(kind, desc, { theme: 'dark' });
    const expected = V.expectedFiles(built.spec);
    const actual = Object.keys(built.files).sort();
    out.templates.push({
      kind, desc, expected, actual,
      missing: expected.filter(n => actual.indexOf(n) < 0),
      extra: actual.filter(n => expected.indexOf(n) < 0),
      spec: built.spec,
    });
  });

  const base = T.project('platformer', 'a platformer game', { theme: 'dark' });
  const grown = P.grow({ kind: base.kind, desc: 'a platformer game',
    files: base.files, spec: base.spec, edits: [] }, 'systems',
    ['inventory', 'save']);
  const grownExpected = V.expectedFiles(grown.spec);
  const grownActual = Object.keys(grown.files).sort();
  out.growth.systems = {
    ok: grown.ok,
    expected: grownExpected,
    actual: grownActual,
    missing: grownExpected.filter(n => grownActual.indexOf(n) < 0),
    extra: grownActual.filter(n => grownExpected.indexOf(n) < 0),
    spec: grown.spec,
  };

  const grownMod = P.grow({ kind: base.kind, desc: 'a platformer game',
    files: base.files, spec: base.spec, edits: [] }, 'module', 'core');
  const modExpected = V.expectedFiles(grownMod.spec);
  const modActual = Object.keys(grownMod.files).sort();
  out.growth.module = {
    ok: grownMod.ok,
    expected: modExpected,
    actual: modActual,
    missing: modExpected.filter(n => modActual.indexOf(n) < 0),
    extra: modActual.filter(n => modExpected.indexOf(n) < 0),
    spec: grownMod.spec,
  };

  const three = P.apply('three-d', { kind: base.kind, desc: 'a platformer game',
    files: base.files, spec: base.spec, edits: [] }, { arg: '' });
  if (three.ok) {
    const tExpected = V.expectedFiles(three.spec);
    const tActual = Object.keys(three.files).sort();
    out.threeD = {
      ok: true, expected: tExpected, actual: tActual,
      missing: tExpected.filter(n => tActual.indexOf(n) < 0),
      extra: tActual.filter(n => tExpected.indexOf(n) < 0),
      spec: three.spec,
    };
  } else {
    out.threeD = { ok: false, message: three.message };
  }

  self.toolrxWeb.reset();
  out.chat.noProject = await ask('verify the project files');
  out.chat.build = await ask('build a calculator');
  const fetchBefore = fetches;
  out.chat.files = await ask('verify the project files');
  out.chat.smoke = await ask('run the project smoke checks');
  out.chat.report = await ask('verify this project');
  out.chat.reportAgain = await ask('verify this project');
  out.chat.fetches = fetches - fetchBefore;
  out.chat.contextStore = await ask('verify this project in context');
  out.chat.contextStored = self.toolrxContext.get('calculator', 'verify', 'report');
  out.chat.journalStore = await ask('verify this project in the journal');
  out.chat.journalStored = self.toolrxJournal.query('calculator', 'verify report').matches;
  out.chat.journalAnswer = await ask('what did we decide about verify report');

  console.log(JSON.stringify(out));
})().catch(e => {
  console.error(e && e.stack || String(e));
  process.exit(1);
});
"""


class TableTest(unittest.TestCase):
    def test_table_is_valid_and_unique(self):
        table = verify.load()
        self.assertEqual(table["version"], 1)
        entries = list(verify.entries())
        self.assertEqual(len(entries), 48)
        ids = [entry["id"] for entry in entries]
        self.assertEqual(len(ids), len(set(ids)))
        patterns = [entry["re"] for entry in entries]
        self.assertEqual(len(patterns), len(set(patterns)))
        for entry in entries:
            self.assertEqual(entry["c"], "verify")
            self.assertTrue(entry["op"].startswith("verify."))
            self.assertIn(entry["op"].split(".")[1], ("files", "smoke", "report"))

    def test_fixture_is_current(self):
        doc = verify.fixture()
        self.assertTrue(os.path.exists(FIXTURE),
                        "run python3 toolrx/verify.py --write")
        with open(FIXTURE, encoding="utf-8") as fh:
            current = json.load(fh)
        self.assertEqual(current, doc,
                         "verify fixture drifted: run python3 toolrx/verify.py --write")
        self.assertEqual(doc["count"], len(doc["cases"]))
        self.assertEqual(doc["ops"], {
            "verify.files": 14,
            "verify.report": 11,
            "verify.report.context": 6,
            "verify.report.journal": 6,
            "verify.smoke": 11,
        })

    def test_three_caps_are_in_the_envelope(self):
        data = envelope.load()
        self.assertEqual(data["verifyFiles"], 32)
        self.assertEqual(data["verifyChecks"], 8)
        self.assertEqual(data["verifyReportChars"], 4000)
        self.assertEqual(len(envelope._RANGES), 56)


@unittest.skipUnless(NODE, "node is not installed")
class BrowserVerifyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", JS, WEB, os.path.join(WEB, "commands.json"),
             os.path.join(CORE, "micro_model.json"), FIXTURE],
            capture_output=True, text=True, timeout=240)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-4000:])
        cls.out = json.loads(proc.stdout)
        with open(FIXTURE, encoding="utf-8") as fh:
            cls.fixture = json.load(fh)

    def test_every_route_resolves_to_its_verify_op(self):
        for route in self.out["routes"]:
            self.assertEqual(route["got"], route["want"], route["text"])

    def test_python_and_javascript_render_the_same_bytes(self):
        for state in self.fixture["states"]:
            pure = self.out["pure"][state["name"]]
            self.assertEqual(pure["first"], state["want"], state["name"])
            self.assertEqual(pure["second"], state["want"], state["name"])

    def test_every_state_is_byte_identical_on_a_second_run(self):
        for name, pure in self.out["pure"].items():
            self.assertEqual(pure["first"], pure["second"], name)

    def test_expected_files_match_every_real_build(self):
        for case in self.out["templates"]:
            self.assertEqual(case["missing"], [],
                             (case["kind"], case["desc"], case["spec"]))
            self.assertEqual(case["extra"], [],
                             (case["kind"], case["desc"], case["spec"]))
            self.assertIn("index.html", case["expected"])
            self.assertIn("README.md", case["expected"])
            self.assertIn("ARCHITECTURE.md", case["expected"])

    def test_expected_files_follow_growth_and_the_3d_route(self):
        for key in ("systems", "module"):
            grown = self.out["growth"][key]
            self.assertTrue(grown["ok"], key)
            self.assertEqual(grown["missing"], [], key)
            self.assertEqual(grown["extra"], [], key)
        self.assertTrue(self.out["threeD"]["ok"])
        self.assertIn("engine3d.js", self.out["threeD"]["expected"])
        self.assertNotIn("engine2d.js", self.out["threeD"]["expected"])
        self.assertEqual(self.out["threeD"]["missing"], [])
        self.assertEqual(self.out["threeD"]["extra"], [])

    def test_missing_and_extra_names_are_exact(self):
        state = self.out["pure"]["files-missing-extra"]["first"]
        self.assertIn("missing (1): content.js", state)
        self.assertIn("extra (1): debug.log", state)
        empty = self.out["pure"]["files-empty"]["first"]
        for name in ("ARCHITECTURE.md", "README.md", "app.js", "index.html",
                     "styles.css"):
            self.assertIn(name, empty)
        self.assertIn("5 expected · 0 actual · fail", empty)

    def test_smoke_covers_pass_fail_and_empty(self):
        passed = self.out["pure"]["smoke-pass"]["first"]
        self.assertIn("8 checks · 8 pass · 0 fail · ok", passed)
        failed = self.out["pure"]["smoke-fail"]["first"]
        self.assertIn("1 pass · 7 fail · fail", failed)
        self.assertIn('found "Wrong name"', failed)
        self.assertIn("1 script(s) load after app.js: site.js", failed)
        self.assertIn("1 missing: missing.html", failed)
        empty = self.out["pure"]["smoke-empty"]["first"]
        self.assertIn("1 pass · 7 fail · fail", empty)
        self.assertIn("index.html is missing", empty)
        missing = self.out["pure"]["smoke-missing-project"]["first"]
        self.assertIn("no active project", missing)

    def test_report_is_deterministic_bounded_and_keeps_the_verdict(self):
        trimmed = self.out["pure"]["report-trimmed"]["first"]
        self.assertLessEqual(len(trimmed.encode("utf-8")), 700)
        self.assertIn("trimmed to 700 chars (verifyReportChars)", trimmed)
        self.assertIn("verdict:", trimmed)
        self.assertIn("r.trim", trimmed)
        self.assertEqual(trimmed, self.out["pure"]["report-trimmed"]["second"])
        report = self.out["pure"]["report-pass"]["first"]
        self.assertIn("5/5 files · 8/8 checks · ok", report)
        self.assertIn("verdict: ok", report)
        self.assertIn("reads: project files only", report)

    def test_caps_are_named_in_the_output(self):
        capped = self.out["pure"]["files-capped"]["first"]
        self.assertIn("41 more expected not listed", capped)
        self.assertIn("r.files-cap", capped)
        self.assertIn("verify cap 4,000 chars", capped)
        checks = self.out["pure"]["smoke-capped"]["first"]
        self.assertIn("5 more check(s) not run", checks)
        self.assertIn("r.checks-cap", checks)

    def test_chat_verifies_the_active_project_without_a_network(self):
        self.assertIn("no active project", self.out["chat"]["noProject"]["text"])
        self.assertEqual(self.out["chat"]["files"]["via"], "verify.files")
        self.assertIn("5 expected · 5 actual · ok",
                      self.out["chat"]["files"]["text"])
        self.assertEqual(self.out["chat"]["smoke"]["via"], "verify.smoke")
        self.assertIn("8 checks · 8 pass", self.out["chat"]["smoke"]["text"])
        self.assertEqual(self.out["chat"]["report"]["via"], "verify.report")
        self.assertIn("verdict: ok", self.out["chat"]["report"]["text"])
        self.assertEqual(self.out["chat"]["report"]["text"],
                         self.out["chat"]["reportAgain"]["text"])
        self.assertEqual(self.out["chat"]["fetches"], 0)

    def test_context_and_journal_stores_round_trip(self):
        self.assertEqual(self.out["chat"]["contextStore"]["via"],
                         "verify.report.context")
        self.assertIn("stored in context · verify/report",
                      self.out["chat"]["contextStore"]["text"])
        self.assertIsNotNone(self.out["chat"]["contextStored"])
        self.assertIn("verdict: ok", self.out["chat"]["contextStored"])
        self.assertEqual(self.out["chat"]["journalStore"]["via"],
                         "verify.report.journal")
        self.assertIn("stored in journal · verify/report",
                      self.out["chat"]["journalStore"]["text"])
        self.assertTrue(self.out["chat"]["journalStored"])
        self.assertIn("verify report", self.out["chat"]["journalAnswer"]["text"])

    def test_the_program_is_pure(self):
        with open(os.path.join(WEB, "verify.js"), encoding="utf-8") as fh:
            source = fh.read()
        for marker in ("fetch(", "XMLHttpRequest", "localStorage",
                       "document.", "window.", "Date(", "Math.random"):
            self.assertNotIn(marker, source)
        self.assertNotRegex(source, re.compile(r"\beval\s*\("))


if __name__ == "__main__":
    unittest.main()

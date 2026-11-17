#!/usr/bin/env python3
"""Step 54: bounded plan repair.

`toolrx/repair.json` is the only source of the `repair.plan` routes; it feeds
the catalog and `tests/fixtures/repair.json`. `toolrx/web/repair.js` is the
pure rule module. These tests check the table, each rule, the staged suffix,
the two-pass cap, the original-plan record, undo, and the no-network promise.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORE = os.path.join(ROOT, "toolrx")
WEB = os.path.join(CORE, "web")
FIXTURE = os.path.join(HERE, "fixtures", "repair.json")
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import repair  # noqa: E402

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
  'thinking.js', 'repair.js', 'skills.js', 'templates.js', 'context.js',
  'lang.js', 'patches.js', 'engine2d.js', 'engine2d.embed.js', 'engine3d.js',
  'engine3d.embed.js', 'worldgen.js', 'worldgen.embed.js', 'rpg2.js',
  'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

const R = self.toolrxRepair;
const lim = {
  planSteps: 40, planChars: 8000, planVariantBytes: 9216,
};
const step = (text, op, exact) => ({ text, op: op || 'router', exact: exact !== false });

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const out = { routes: [], pure: {}, chat: {} };

  FIXTURE.cases.forEach(c => {
    const hit = self.toolrxSkills.match(c.text);
    out.routes.push({ text: c.text, want: c.op, got: hit ? hit.op : null });
  });

  const base = {
    steps: [step('build a platformer game', 'build'),
            step('divide 4 by 0', 'math.binary'),
            step('add a theme toggle', 'project.themeToggle')],
    failedAt: 1,
    errorText: 'division by zero',
    passes: 0,
    maxPasses: 2,
    limits: lim,
    originalSteps: 3,
  };
  const pure = (extra) => R.plan(Object.assign({}, base, extra || {}));
  out.pure.math = pure();
  out.pure.mathAgain = pure();
  out.pure.mathText = R.text(out.pure.math);
  out.pure.none = pure({ failedAt: -1 });
  out.pure.cap = pure({ passes: 2 });
  out.pure.capText = R.text(out.pure.cap);
  out.pure.route = pure({ steps: [step('read missing.txt', 'router', false),
                                  step('add a theme toggle', 'project.themeToggle')],
                          failedAt: 0 });
  out.pure.kind = pure({
    steps: [step('build a platformer game', 'build'),
            step('add a boss', 'edit.apply'),
            step('add a theme toggle', 'project.themeToggle')],
    errorText: 'not edited · bosses are wired for shooter, twin-stick; '
      + 'try: build a compatible starter first, or say undo',
  });
  out.pure.kindText = R.text(out.pure.kind);
  out.pure.missing = pure({
    steps: [step('build a platformer game', 'build'),
            step('count the words in missing.txt', 'text.count'),
            step('add a theme toggle', 'project.themeToggle')],
    errorText: 'no such file: missing.txt',
  });
  out.pure.dependency = pure({
    steps: [step('build a platformer game', 'build'),
            step('divide 4 by 0', 'math.binary'),
            step('make it dark', 'project.theme')],
  });
  out.pure.empty = pure({
    steps: [step('build a platformer game', 'build'),
            step('divide 4 by 0', 'math.binary')],
    failedAt: 1,
  });
  out.pure.retry = pure({ errorText: 'step timed out after 4000 ms' });
  out.pure.retryDefault = pure({ errorText: 'boom' });
  out.pure.steps = pure({
    steps: [step('build a platformer game', 'build'),
            step('divide 4 by 0', 'math.binary')].concat(
      Array.from({ length: 45 }, (_, i) =>
        step('list the files ' + i, 'fs.list_dir'))),
    failedAt: 1,
  });
  out.pure.chars = pure({
    steps: [step('build a platformer game', 'build'),
            step('divide 4 by 0', 'math.binary'),
            step('x'.repeat(9000), 'router')],
    failedAt: 1,
  });
  out.pure.record = R.record(out.pure.math, {
    steps: base.steps, originalSteps: base.steps,
    errorText: base.errorText,
  }, { maxText: 2000, maxBytes: 9216 });
  out.pure.recordTooBig = R.record(out.pure.math, {
    steps: base.steps, originalSteps: base.steps,
    errorText: base.errorText,
  }, { maxText: 2000, maxBytes: 64 });

  const ask = async q => (await self.toolrxWeb.prompt(q)).map(r => ({
    step: r.step, text: r.text, via: r.via || '', error: !!r.error,
  }));
  const fetchBefore = fetches;

  // Revise, accept, and undo.
  self.toolrxWeb.reset();
  out.chat.initial = await ask('build a platformer game; divide 4 by 0; add a theme toggle');
  out.chat.lastRun = self.toolrxWeb.lastRun();
  out.chat.appBefore = self.toolrxWeb.projectFile('platformer', 'app.js');
  out.chat.repair = (await ask('repair this plan'))[0];
  out.chat.pending = self.toolrxWeb.memory('conversation').pending;
  out.chat.record = self.toolrxWeb.memory('planRepair');
  out.chat.yes = (await ask('yes'))[0];
  out.chat.appAfter = self.toolrxWeb.projectFile('platformer', 'app.js');
  out.chat.recordAfterYes = self.toolrxWeb.memory('planRepair');
  out.chat.lastRunAfterYes = self.toolrxWeb.lastRun();
  out.chat.undo = (await ask('undo'))[0];
  out.chat.appUndo = self.toolrxWeb.projectFile('platformer', 'app.js');

  // Kind-gated patch: refuse, do not stage.
  self.toolrxWeb.reset();
  await ask('build a platformer game; add a boss; add a theme toggle');
  out.chat.kind = (await ask('repair this plan'))[0];
  out.chat.kindPending = self.toolrxWeb.memory('conversation').pending;
  out.chat.kindRecord = self.toolrxWeb.memory('planRepair');

  // Two accepted passes, then the cap.
  self.toolrxWeb.reset();
  await ask('build a platformer game; divide 4 by 0; divide 5 by 0; '
    + 'divide 6 by 0; add a theme toggle');
  out.chat.cap1 = (await ask('repair this plan'))[0];
  out.chat.capYes1 = (await ask('yes'))[0];
  out.chat.cap2 = (await ask('repair this plan'))[0];
  out.chat.capYes2 = (await ask('yes'))[0];
  out.chat.cap3 = (await ask('repair this plan'))[0];
  out.chat.capRecord = self.toolrxWeb.memory('planRepair');
  out.chat.capPending = self.toolrxWeb.memory('conversation').pending;

  // No keeps the project and clears the staged repair.
  self.toolrxWeb.reset();
  await ask('build a platformer game; divide 4 by 0; add a theme toggle');
  out.chat.noRepair = (await ask('repair this plan'))[0];
  out.chat.no = (await ask('no'))[0];
  out.chat.noRecord = self.toolrxWeb.memory('planRepair');
  out.chat.noAgain = (await ask('repair this plan'))[0];

  out.chat.fetches = fetches - fetchBefore;
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is not installed")
class RepairTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", JS, WEB,
             os.path.join(WEB, "commands.json"),
             os.path.join(ROOT, "toolrx", "micro_model.json"),
             FIXTURE],
            capture_output=True, text=True, timeout=240,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-4000:])
        cls.out = json.loads(proc.stdout)

    # ------------------------------------------------------------- table ---
    def test_fixture_is_current(self):
        with open(FIXTURE, encoding="utf-8") as fh:
            current = json.load(fh)
        self.assertEqual(current, repair.fixture(),
                         "repair fixture drifted; run toolrx/repair.py --write")

    def test_every_route_resolves_to_repair(self):
        self.assertTrue(self.out["routes"])
        for case in self.out["routes"]:
            self.assertEqual(case["got"], "repair.plan", case)

    # -------------------------------------------------------------- pure ---
    def test_math_failure_revises_to_the_suffix(self):
        out = self.out["pure"]["math"]
        self.assertEqual(out["kind"], "revise")
        self.assertEqual(out["rule"], "r.repair-math")
        self.assertEqual([s["text"] for s in out["steps"]],
                         ["add a theme toggle"])
        self.assertEqual(out["dropped"], ["divide 4 by 0"])
        self.assertEqual(out["failedAt"], 1)
        self.assertEqual(out["passes"], 0)
        self.assertEqual(self.out["pure"]["math"], self.out["pure"]["mathAgain"])

    def test_repair_text_names_the_rule_and_the_suffix(self):
        text = self.out["pure"]["mathText"]
        self.assertIn("repair · pass 1 of 2 · source last run", text)
        self.assertIn('failed: step 2 · "divide 4 by 0" · division by zero',
                      text)
        self.assertIn("revised plan (1 step): · r.repair-suffix", text)
        self.assertIn("1. add a theme toggle · exact project.themeToggle",
                      text)
        self.assertIn("completed: the 1 step(s) before the failure are not rerun",
                      text)
        self.assertIn("original: 3 step(s) kept", text)
        self.assertIn("r.repair-math", text)

    def test_no_failure_is_none(self):
        out = self.out["pure"]["none"]
        self.assertEqual(out["kind"], "none")
        self.assertEqual(out["rule"], "r.no-failure")

    def test_two_pass_cap_refuses(self):
        out = self.out["pure"]["cap"]
        self.assertEqual(out["kind"], "refuse")
        self.assertEqual(out["rule"], "r.repair-cap")
        self.assertIn("cap reached", self.out["pure"]["capText"])
        self.assertNotIn("pass 3 of 2", self.out["pure"]["capText"])

    def test_no_exact_route_is_refused(self):
        out = self.out["pure"]["route"]
        self.assertEqual(out["kind"], "refuse")
        self.assertEqual(out["rule"], "r.repair-route")

    def test_kind_gate_is_refused_with_compatible_starters(self):
        out = self.out["pure"]["kind"]
        self.assertEqual(out["kind"], "refuse")
        self.assertEqual(out["rule"], "r.repair-kind")
        text = self.out["pure"]["kindText"]
        self.assertIn("wired for shooter, twin-stick", text)
        self.assertIn("build a compatible starter first", text)
        self.assertIn("repair: none", text)
        self.assertNotIn("revised plan", text)

    def test_missing_input_is_dropped(self):
        out = self.out["pure"]["missing"]
        self.assertEqual(out["kind"], "revise")
        self.assertEqual(out["rule"], "r.repair-missing")
        self.assertEqual([s["text"] for s in out["steps"]],
                         ["add a theme toggle"])

    def test_dependency_on_the_failed_result_is_refused(self):
        out = self.out["pure"]["dependency"]
        self.assertEqual(out["kind"], "refuse")
        self.assertEqual(out["rule"], "r.repair-dependency")
        self.assertIn("depends on the failed result", out["reason"])

    def test_dropping_the_last_step_refuses(self):
        out = self.out["pure"]["empty"]
        self.assertEqual(out["kind"], "refuse")
        self.assertEqual(out["rule"], "r.repair-empty")

    def test_transient_and_unknown_errors_retry_the_failed_step(self):
        timed = self.out["pure"]["retry"]
        self.assertEqual(timed["kind"], "retry")
        self.assertEqual(timed["rule"], "r.repair-timeout")
        self.assertEqual([s["text"] for s in timed["steps"]],
                         ["divide 4 by 0", "add a theme toggle"])
        unknown = self.out["pure"]["retryDefault"]
        self.assertEqual(unknown["kind"], "retry")
        self.assertEqual(unknown["rule"], "r.repair-retry")

    def test_revised_plan_obeys_the_step_and_character_caps(self):
        self.assertEqual(self.out["pure"]["steps"]["rule"], "r.repair-steps")
        self.assertEqual(self.out["pure"]["chars"]["rule"], "r.repair-chars")

    def test_record_is_bounded_and_keeps_the_original(self):
        doc = self.out["pure"]["record"]
        self.assertEqual(doc["kind"], "repair")
        self.assertEqual([s["text"] for s in doc["original"]],
                         ["build a platformer game", "divide 4 by 0",
                          "add a theme toggle"])
        self.assertEqual([s["text"] for s in doc["steps"]],
                         ["add a theme toggle"])
        self.assertIsNone(self.out["pure"]["recordTooBig"])

    # -------------------------------------------------------------- chat ---
    def test_failed_middle_step_stages_the_suffix(self):
        chat = self.out["chat"]
        self.assertEqual(chat["initial"][-1]["via"], "math.binary")
        self.assertIn('repair: say "repair this plan"', chat["initial"][-1]["text"])
        self.assertEqual(chat["repair"]["via"], "repair.plan")
        self.assertIn("revised plan (1 step)", chat["repair"]["text"])
        self.assertEqual(chat["pending"]["kind"], "repair")
        self.assertEqual(chat["pending"]["steps"], ["add a theme toggle"])
        self.assertEqual(chat["record"]["passes"], 1)

    def test_yes_runs_only_the_changed_suffix(self):
        chat = self.out["chat"]
        self.assertEqual(chat["yes"]["via"], "project.themeToggle")
        self.assertFalse(chat["yes"]["error"])
        self.assertNotEqual(chat["appBefore"], chat["appAfter"])
        self.assertEqual(chat["lastRunAfterYes"]["plan"]["steps"],
                         ["add a theme toggle"])
        self.assertEqual(chat["lastRunAfterYes"]["plan"]["failedAt"], -1)
        self.assertIsNone(chat["recordAfterYes"])

    def test_undo_restores_the_project_after_the_repair(self):
        chat = self.out["chat"]
        self.assertIn("undid", chat["undo"]["text"].lower())
        self.assertEqual(chat["appUndo"], chat["appBefore"])

    def test_kind_gate_refuses_without_staging(self):
        chat = self.out["chat"]
        self.assertIn("r.repair-kind", chat["kind"]["text"])
        self.assertIn("build a compatible starter first", chat["kind"]["text"])
        self.assertIsNone(chat["kindPending"])
        self.assertIsNone(chat["kindRecord"])

    def test_two_passes_then_the_cap(self):
        chat = self.out["chat"]
        self.assertIn("pass 1 of 2", chat["cap1"]["text"])
        self.assertTrue(chat["capYes1"]["error"])
        self.assertIn("pass 2 of 2", chat["cap2"]["text"])
        self.assertTrue(chat["capYes2"]["error"])
        self.assertIn("cap reached", chat["cap3"]["text"])
        self.assertIn("r.repair-cap", chat["cap3"]["text"])
        self.assertIsNone(chat["capPending"])
        self.assertEqual(chat["capRecord"]["passes"], 2)

    def test_no_clears_the_repair_and_keeps_the_failed_plan(self):
        chat = self.out["chat"]
        self.assertEqual(chat["no"]["via"], "conversation.reject")
        self.assertIn("nothing was run", chat["no"]["text"])
        self.assertIsNone(chat["noRecord"])
        self.assertIn("pass 1 of 2", chat["noAgain"]["text"])

    def test_last_run_carries_the_plan_and_the_error(self):
        last = self.out["chat"]["lastRun"]
        self.assertEqual(last["plan"]["steps"],
                         ["build a platformer game", "divide 4 by 0",
                          "add a theme toggle"])
        self.assertEqual(last["plan"]["failedAt"], 1)
        self.assertIn("division by zero", last["plan"]["errorText"])
        self.assertTrue(last["repair"]["available"])
        self.assertEqual(last["repair"]["pending"], 1)

    def test_repair_never_touches_the_network(self):
        self.assertEqual(self.out["chat"]["fetches"], 0,
                         "a repair route made a network call")
        with open(os.path.join(WEB, "repair.js"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotRegex(source, r"\bfetch\s*\(")
        self.assertNotIn("import(", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

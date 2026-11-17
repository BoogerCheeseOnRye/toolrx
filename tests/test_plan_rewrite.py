#!/usr/bin/env python3
"""Step 52: budget-aware plan rewriting.

`toolrx/web/planrewrite.js` turns an over-budget plan into one deterministic
compacted variant. These tests drive the pure module for every budget kind and
then run the real chat path in Node: the variant is staged, `yes` runs exactly
its steps, and `no` leaves the project untouched.
"""

import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB = os.path.join(ROOT, "toolrx", "web")
NODE = shutil.which("node")

JS = r"""
const fs = require('fs');
const path = require('path');
const WEB = process.argv[1];
const COMMANDS = process.argv[2];
const MODEL = process.argv[3];

global.self = global;
global.fetch = (url) => {
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
  'blake2b.js', 'router.js', 'limits.js', 'budget.js', 'planrewrite.js', 'thinking.js', 'repair.js',
  'skills.js', 'templates.js', 'context.js', 'lang.js', 'patches.js',
  'engine2d.js', 'engine2d.embed.js', 'engine3d.js', 'engine3d.embed.js',
  'worldgen.js', 'worldgen.embed.js', 'rpg2.js', 'rpg2.embed.js',
  'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

const R = self.toolrxPlanRewrite;
const step = (text, via, exact) => ({ text, via, exact: exact !== false });
const base = {
  stepMs: 4000, planMs: 160000, maxChars: 8000, maxSteps: 40,
  contextBytes: 0, contextMax: 8192, projectBytes: 0, projectMax: 524288,
  buildBytes: 65536, editBytes: 4096,
};
const rewrite = extra => R.rewrite(Object.assign({}, base, extra));

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const out = { pure: {} };

  out.pure.none = rewrite({ steps: [step('list the files', 'fs.list_dir')] });
  out.pure.steps = rewrite({
    steps: Array.from({ length: 45 }, (_, i) =>
      step('read notes ' + i + '.txt', 'fs.read_file')),
  });
  out.pure.time = rewrite({
    planMs: 10000,
    steps: Array.from({ length: 5 }, (_, i) =>
      step('read notes ' + i + '.txt', 'fs.read_file')),
  });
  out.pure.chars = rewrite({
    maxChars: 300,
    steps: [step('build a platformer game', 'build'),
            step('x'.repeat(400), 'router', false)],
  });
  out.pure.context = rewrite({
    contextBytes: 7800,
    steps: [step('build a platformer game', 'build'),
            step('read notes.txt', 'fs.read_file')],
  });
  out.pure.project = rewrite({
    projectBytes: 470000,
    steps: [step('build a platformer game', 'build'),
            step('read notes.txt', 'fs.read_file')],
  });
  out.pure.stuck = rewrite({
    contextBytes: 9000,
    steps: [step('read notes.txt', 'fs.read_file')],
  });

  const sample = {
    name: 'compact-steps',
    over: ['steps'],
    steps: [step('build a platformer game', 'build')],
    dropped: [{ text: 'read notes.txt', via: 'fs.read_file', why: 'steps' }],
  };
  out.record = {
    ok: R.variantRecord(sample, 'build a platformer game', {
      maxText: 2000, maxBytes: 9216,
    }),
    tiny: R.variantRecord(sample, 'build a platformer game', {
      maxText: 2000, maxBytes: 10,
    }),
    capped: R.variantRecord({
      name: 'compact-many',
      over: ['steps'],
      steps: [step('s'.repeat(20), 'router')],
      dropped: Array.from({ length: 45 }, (_, i) => ({
        text: 'd' + i, via: 'router', why: 'steps',
      })),
    }, 'many', { maxText: 4, maxBytes: 9216 }),
  };

  const projectMap = () => {
    const p = self.toolrxWeb.project();
    if (!p) return { slug: null, files: {} };
    const files = {};
    p.files.slice().sort().forEach(n => { files[n] = self.toolrxWeb.projectFile(p.slug, n); });
    return { slug: p.slug, files: files };
  };
  const ask = async q => (await self.toolrxWeb.prompt(q)).map(r => ({
    step: r.step, text: r.text, via: r.via || '', error: !!r.error,
    variant: r.variant || null, confirmed: r.confirmed || null,
  }));

  // 41 successful steps: the variant keeps 40 and `yes` runs exactly those.
  self.toolrxWeb.reset();
  const many = Array.from({ length: 41 }, () => 'list the files').join('; ');
  const beforeMany = projectMap();
  out.staged = (await ask(many))[0];
  out.pending = (await ask('show conversation'))[0].text;
  const accepted = await ask('yes');
  out.accepted = {
    count: accepted.length,
    errors: accepted.filter(r => r.error).length,
    vias: Array.from(new Set(accepted.map(r => r.via))),
    project: projectMap(),
    lastRun: self.toolrxWeb.lastRun(),
  };
  out.beforeMany = beforeMany;

  // Refusal writes no project files.
  self.toolrxWeb.reset();
  const beforeNo = projectMap();
  out.refusedStage = (await ask(many))[0];
  out.refused = (await ask('no'))[0];
  out.afterNo = projectMap();
  out.beforeNo = beforeNo;

  // A project near its byte cap drops the build step and keeps the read.
  self.toolrxWeb.reset();
  await ask('build a platformer game');
  try { localStorage.setItem('toolrx.project.budget', '60000'); } catch (e) {}
  const projectQuery = 'build a shooter game; list the files';
  out.projectPreview = self.toolrxWeb.planPreview(projectQuery);
  out.projectStage = (await ask(projectQuery))[0];
  const projectBefore = projectMap();
  const projectAccepted = await ask('yes');
  out.projectAccepted = {
    count: projectAccepted.length,
    project: projectMap(),
    before: projectBefore,
    lastRun: self.toolrxWeb.lastRun(),
  };
  try { localStorage.removeItem('toolrx.project.budget'); } catch (e) {}

  // A lowered plan timeout keeps only the steps that fit.
  self.toolrxWeb.reset();
  try { localStorage.setItem('toolrx.plan.timeout', '10000'); } catch (e) {}
  const timeQuery = 'list the files; show the uptime; multiply 6 and 7; '
    + 'count the words in notes.txt; list the files';
  out.timePreview = self.toolrxWeb.planPreview(timeQuery);
  out.timeStage = (await ask(timeQuery))[0];
  const timeAccepted = await ask('yes');
  out.timeAccepted = {
    count: timeAccepted.length,
    errors: timeAccepted.filter(r => r.error).length,
    lastRun: self.toolrxWeb.lastRun(),
  };
  try { localStorage.removeItem('toolrx.plan.timeout'); } catch (e) {}

  // Over the character cap: one variant, no silent truncation.
  self.toolrxWeb.reset();
  out.charsPreview = self.toolrxWeb.planPreview('word '.repeat(1700));
  out.charsStage = (await ask('word '.repeat(1700)))[0];

  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is not installed")
class PlanRewriteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", JS, WEB,
             os.path.join(WEB, "commands.json"),
             os.path.join(ROOT, "toolrx", "micro_model.json")],
            capture_output=True, text=True, timeout=180,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-4000:])
        cls.out = json.loads(proc.stdout)

    def test_a_plan_that_fits_is_not_rewritten(self):
        p = self.out["pure"]["none"]
        self.assertFalse(p["needed"])
        self.assertTrue(p["fits"])
        self.assertEqual(p["dropped"], [])

    def test_step_budget_keeps_the_highest_value_steps(self):
        p = self.out["pure"]["steps"]
        self.assertTrue(p["needed"])
        self.assertTrue(p["fits"])
        self.assertEqual(p["name"], "compact-steps-time")
        self.assertIn("steps", p["over"])
        self.assertEqual(len(p["steps"]), 40)
        self.assertEqual(len(p["dropped"]), 5)
        self.assertEqual(p["after"]["steps"], 40)
        self.assertLessEqual(p["after"]["time"], 160000)

    def test_time_budget_keeps_only_what_fits(self):
        p = self.out["pure"]["time"]
        self.assertTrue(p["fits"])
        self.assertEqual(p["name"], "compact-time")
        self.assertEqual(len(p["steps"]), 2)
        self.assertLessEqual(p["after"]["time"], 10000)

    def test_character_budget_drops_whole_steps(self):
        p = self.out["pure"]["chars"]
        self.assertTrue(p["fits"])
        self.assertEqual(p["name"], "compact-chars")
        self.assertEqual(len(p["steps"]), 1)
        self.assertLessEqual(p["after"]["chars"], 300)
        self.assertTrue(p["dropped"][0]["why"])

    def test_context_budget_uses_the_stored_plan_estimate(self):
        p = self.out["pure"]["context"]
        self.assertTrue(p["fits"])
        self.assertEqual(p["name"], "compact-context")
        self.assertLessEqual(p["after"]["context"], 8192)
        self.assertTrue(any(b["key"] == "context" and b["estimated"]
                            for b in p["afterBars"]))

    def test_project_budget_uses_the_declared_write_estimate(self):
        p = self.out["pure"]["project"]
        self.assertTrue(p["fits"])
        self.assertEqual(p["name"], "compact-project")
        self.assertEqual([s["via"] for s in p["steps"]], ["fs.read_file"])
        self.assertLessEqual(p["after"]["project"], 524288)
        self.assertTrue(any(b["key"] == "project" and b["estimated"]
                            for b in p["afterBars"]))

    def test_a_budget_already_over_its_cap_is_refused_honestly(self):
        p = self.out["pure"]["stuck"]
        self.assertTrue(p["needed"])
        self.assertFalse(p["fits"])
        self.assertIn("context is already over its cap", p["reason"])
        self.assertEqual(p["steps"], [])

    def test_variant_record_is_bounded_by_plan_variant_bytes(self):
        r = self.out["record"]
        self.assertEqual(r["ok"]["version"], 1)
        self.assertEqual(len(r["ok"]["steps"]), 1)
        self.assertEqual(len(r["ok"]["dropped"]), 1)
        self.assertIsNone(r["tiny"], "a record over planVariantBytes must be refused")
        capped = r["capped"]
        self.assertEqual(len(capped["dropped"]), 40, "dropped entries are capped at 40")
        self.assertEqual(capped["steps"][0]["text"], "ssss",
                         "step text is bounded by the caller's maxText")

    def test_over_budget_prompt_stages_one_named_variant(self):
        s = self.out["staged"]
        self.assertEqual(s["via"], "plan.variant")
        self.assertFalse(s["error"])
        self.assertIn("plan variant", s["text"])
        self.assertIn("before:", s["text"])
        self.assertIn("after:", s["text"])
        self.assertTrue(s["variant"]["over"])
        self.assertEqual(s["variant"]["steps"], 40)
        self.assertIn("compacted plan", self.out["pending"])

    def test_accepting_runs_exactly_the_listed_steps(self):
        a = self.out["accepted"]
        self.assertEqual(a["count"], 40)
        self.assertEqual(a["errors"], 0)
        self.assertEqual(len(a["vias"]), 1)
        self.assertIn("list_dir", a["vias"][0])
        self.assertEqual(a["lastRun"]["planned"], 40)
        self.assertEqual(a["lastRun"]["steps"], 40)

    def test_refusing_leaves_the_project_untouched(self):
        self.assertEqual(self.out["beforeNo"], self.out["afterNo"])
        self.assertEqual(self.out["refused"]["via"], "conversation.reject")
        self.assertIn("nothing was run", self.out["refused"]["text"])

    def test_project_over_budget_drops_the_build_and_accepts_the_read(self):
        preview = self.out["projectPreview"]
        self.assertTrue(preview["blocked"])
        self.assertIn("project", preview["variant"]["over"])
        self.assertEqual([s["text"] for s in preview["variant"]["steps"]],
                         ["list the files"])
        a = self.out["projectAccepted"]
        self.assertEqual(a["count"], 1)
        self.assertEqual(a["before"], a["project"])
        self.assertEqual(a["project"]["slug"], "platformer")
        self.assertEqual(a["lastRun"]["planned"], 1)

    def test_lowered_timeout_keeps_only_the_steps_that_fit(self):
        preview = self.out["timePreview"]
        self.assertTrue(preview["blocked"])
        self.assertIn("time", preview["variant"]["over"])
        self.assertEqual(len(preview["variant"]["steps"]), 2)
        a = self.out["timeAccepted"]
        self.assertEqual(a["count"], 2)
        self.assertEqual(a["errors"], 0)
        self.assertEqual(a["lastRun"]["planned"], 2)

    def test_character_over_budget_is_a_variant_not_a_silent_cut(self):
        preview = self.out["charsPreview"]
        self.assertTrue(preview["blocked"])
        self.assertIn("8000", preview["reason"])
        self.assertTrue(preview["variant"]["fits"])
        self.assertLessEqual(len(preview["variant"]["steps"]), 4)
        self.assertEqual(self.out["charsStage"]["via"], "plan.variant")
        self.assertIn("dropped", self.out["charsStage"]["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

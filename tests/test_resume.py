#!/usr/bin/env python3
"""Step 57: error recovery and partial-result continuation.

`toolrx/resume.json` is the only source of the `repair.resume` routes; it feeds
the catalog and `tests/fixtures/resume.json`. `toolrx/web/repair.js` holds the
pure `resume`/`resumeText` rules. These tests check the table, every guard, the
pending-only run, the shared pass cap, build/patch/context recovery, the offer
line, and the no-network promise.
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
FIXTURE = os.path.join(HERE, "fixtures", "resume.json")
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import resume  # noqa: E402

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
  'thinking.js', 'repair.js', 'trace.js', 'journal.js', 'skills.js',
  'templates.js', 'context.js', 'lang.js', 'patches.js', 'engine2d.js',
  'engine2d.embed.js', 'engine3d.js', 'engine3d.embed.js', 'worldgen.js',
  'worldgen.embed.js', 'rpg2.js', 'rpg2.embed.js', 'sandbox.js',
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
            step('add a boss', 'edit.apply'),
            step('add a theme toggle', 'project.themeToggle')],
    failedAt: 1,
    errorText: 'not edited · bosses are wired for shooter, twin-stick; '
      + 'try: build a compatible starter first, or say undo',
    passes: 0,
    maxPasses: 2,
    limits: lim,
    hasProject: true,
    pendingNeedsProject: false,
    originalSteps: 3,
  };
  const pure = (extra) => R.resume(Object.assign({}, base, extra || {}));
  out.pure.ok = pure();
  out.pure.okAgain = pure();
  out.pure.okText = R.resumeText(out.pure.ok);
  out.pure.none = pure({ steps: [], failedAt: -1 });
  out.pure.nofail = pure({ failedAt: -1 });
  out.pure.last = pure({ failedAt: 2 });
  out.pure.cap = pure({ passes: 2 });
  out.pure.capText = R.resumeText(out.pure.cap);
  out.pure.build = pure({
    steps: [step('build a platformer game', 'build'),
            step('add a theme toggle', 'project.themeToggle')],
    failedAt: 0,
  });
  out.pure.buildText = R.resumeText(out.pure.build);
  out.pure.noproject = pure({ hasProject: false, pendingNeedsProject: true });
  out.pure.dependency = pure({
    steps: [step('build a platformer game', 'build'),
            step('divide 4 by 0', 'math.binary'),
            step('read the result', 'fs.read_file')],
    failedAt: 1,
    errorText: 'division by zero',
  });
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
  out.pure.record = R.record(out.pure.ok, {
    steps: base.steps, originalSteps: base.steps, errorText: base.errorText,
  }, { kind: 'resume', maxText: 2000, maxBytes: 9216 });
  out.pure.recordTooBig = R.record(out.pure.ok, {
    steps: base.steps, originalSteps: base.steps, errorText: base.errorText,
  }, { kind: 'resume', maxText: 2000, maxBytes: 64 });

  const ask = async q => (await self.toolrxWeb.prompt(q)).map(r => ({
    step: r.step, text: r.text, via: r.via || '', error: !!r.error,
    resumed: !!r.resumed, errorText: r.errorText,
  }));
  const fetchBefore = fetches;

  // Build completes, a kind-gated patch fails, resume runs only the patch.
  self.toolrxWeb.reset();
  out.chat.initial = await ask('build a platformer game; add a boss; add a theme toggle');
  out.chat.slug = self.toolrxWeb.project().slug;
  out.chat.htmlBefore = self.toolrxWeb.projectFile(out.chat.slug, 'index.html');
  out.chat.resume = await ask('resume the plan');
  out.chat.htmlAfter = self.toolrxWeb.projectFile(out.chat.slug, 'index.html');
  out.chat.lastRun = self.toolrxWeb.lastRun();
  out.chat.recordAfter = self.toolrxWeb.memory('planRepair');
  out.chat.slugAfter = self.toolrxWeb.project().slug;

  // A missing input fails, then resume runs the pending theme toggle.
  self.toolrxWeb.reset();
  await ask('build a platformer game; read missing.txt; add a theme toggle');
  out.chat.context = await ask('resume');
  out.chat.contextHtml = self.toolrxWeb.projectFile(
    self.toolrxWeb.project().slug, 'index.html');

  // A pending step that reads the failed result is refused.
  self.toolrxWeb.reset();
  await ask('build a platformer game; divide 4 by 0; read the result');
  out.chat.dependency = (await ask('resume'))[0];

  // A pending step that needs a project is refused when none is open.
  self.toolrxWeb.reset();
  await ask('divide 4 by 0; add a theme toggle');
  out.chat.noproject = (await ask('resume'))[0];

  // Resume shares the two-pass cap with repair.
  self.toolrxWeb.reset();
  await ask('build a platformer game; divide 4 by 0; divide 5 by 0; '
    + 'divide 6 by 0; add a theme toggle');
  out.chat.cap1 = (await ask('resume'))[0];
  out.chat.cap2 = (await ask('resume'))[0];
  out.chat.cap3 = (await ask('resume'))[0];
  out.chat.capRecord = self.toolrxWeb.memory('planRepair');

  // A resumed failure keeps the real error, not the resume header.
  self.toolrxWeb.reset();
  await ask('build a platformer game; divide 4 by 0; divide 5 by 0; add a theme toggle');
  out.chat.failedResume = (await ask('resume'))[0];
  out.chat.failedRun = self.toolrxWeb.lastRun();

  // A cancelled build is retried, not skipped; the previous project stays.
  self.toolrxWeb.reset();
  await ask('build a todo app');
  out.chat.previous = self.toolrxWeb.project().slug;
  self.toolrxWeb.cancelBuild();
  out.chat.buildFail = (await ask('build a platformer game; add a theme toggle'))[0];
  out.chat.buildResume = (await ask('resume'))[0];
  out.chat.previousAfter = self.toolrxWeb.project();
  out.chat.previousFile = self.toolrxWeb.projectFile(out.chat.previous, 'index.html');

  // An in-plan resume step is refused with a clear message.
  self.toolrxWeb.reset();
  out.chat.inPlan = (await ask('build a platformer game; resume'))[1];
  out.chat.inPlanRun = self.toolrxWeb.lastRun();

  out.chat.fetches = fetches - fetchBefore;
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is not installed")
class ResumeTest(unittest.TestCase):
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
        self.assertEqual(current, resume.fixture(),
                         "resume fixture drifted; run toolrx/resume.py --write")

    def test_every_route_resolves_to_resume(self):
        self.assertTrue(self.out["routes"])
        for case in self.out["routes"]:
            self.assertEqual(case["got"], "repair.resume", case)

    def test_table_rejects_a_bad_phrase(self):
        table = {"version": 1, "op": "repair.resume", "summary": "s",
                 "example": "resume", "phrases": ["resume", "resume"]}
        with self.assertRaises(ValueError):
            resume._phrases(table)

    # -------------------------------------------------------------- pure ---
    def test_pending_suffix_is_the_only_plan(self):
        out = self.out["pure"]["ok"]
        self.assertEqual(out["kind"], "resume")
        self.assertEqual(out["rule"], "r.resume-pending")
        self.assertEqual([s["text"] for s in out["steps"]],
                         ["add a theme toggle"])
        self.assertEqual(out["skipped"], ["add a boss"])
        self.assertEqual(out["failedAt"], 1)
        self.assertEqual(out["passes"], 0)
        self.assertEqual(self.out["pure"]["ok"], self.out["pure"]["okAgain"])

    def test_resume_text_names_the_skip_and_the_suffix(self):
        text = self.out["pure"]["okText"]
        self.assertIn("resume · pass 1 of 2 · run the pending suffix", text)
        self.assertIn('skipped: step 2 · "add a boss"', text)
        self.assertIn("pending plan (1 step): · r.resume-suffix", text)
        self.assertIn("1. add a theme toggle · exact project.themeToggle",
                      text)
        self.assertIn("completed: the 1 step(s) before the failure are not "
                      "rerun", text)
        self.assertIn("original: 3 step(s) kept", text)
        self.assertIn("r.resume-skip", text)

    def test_guards_are_ordered_and_named(self):
        pure = self.out["pure"]
        self.assertEqual(pure["none"]["rule"], "r.resume-none")
        self.assertEqual(pure["nofail"]["rule"], "r.resume-nofail")
        self.assertEqual(pure["last"]["rule"], "r.resume-last")
        self.assertEqual(pure["cap"]["rule"], "r.resume-cap")
        self.assertEqual(pure["build"]["rule"], "r.resume-build")
        self.assertEqual(pure["noproject"]["rule"], "r.resume-noproject")
        self.assertEqual(pure["dependency"]["rule"], "r.resume-dependency")
        self.assertEqual(pure["steps"]["rule"], "r.resume-steps")
        self.assertEqual(pure["chars"]["rule"], "r.resume-chars")

    def test_refusals_say_nothing_was_run(self):
        for name in ("capText", "buildText"):
            text = self.out["pure"][name]
            self.assertIn("resume: none · nothing was run", text)
            self.assertIn("r.resume-none", text)
        self.assertIn("cap reached", self.out["pure"]["capText"])
        self.assertIn("previous project is still open",
                      self.out["pure"]["buildText"])

    def test_dependency_names_the_pending_step(self):
        out = self.out["pure"]["dependency"]
        self.assertIn('"read the result"', out["reason"])
        self.assertIn("wrong answer", out["reason"])

    def test_resume_record_is_bounded_and_names_the_skip(self):
        doc = self.out["pure"]["record"]
        self.assertEqual(doc["kind"], "resume")
        self.assertEqual(doc["name"], "resume-1")
        self.assertEqual(doc["skipped"], ["add a boss"])
        self.assertEqual([s["text"] for s in doc["steps"]],
                         ["add a theme toggle"])
        self.assertEqual([s["text"] for s in doc["original"]],
                         ["build a platformer game", "add a boss",
                          "add a theme toggle"])
        self.assertIsNone(self.out["pure"]["recordTooBig"])

    # -------------------------------------------------------------- chat ---
    def test_kind_gated_patch_is_skipped_and_the_patch_runs(self):
        chat = self.out["chat"]
        self.assertEqual(chat["initial"][-1]["via"], "edit.apply")
        self.assertTrue(chat["initial"][-1]["error"])
        self.assertIn('or "resume" to run the 1 pending step(s)',
                      chat["initial"][-1]["text"])
        self.assertEqual(chat["resume"][0]["via"], "project.themeToggle")
        self.assertFalse(chat["resume"][0]["error"])
        self.assertTrue(chat["resume"][0]["resumed"])
        self.assertIn("resume · pass 1 of 2", chat["resume"][0]["text"])
        self.assertNotIn("themeToggle", chat["htmlBefore"])
        self.assertIn("themeToggle", chat["htmlAfter"])

    def test_resume_runs_only_the_pending_suffix(self):
        chat = self.out["chat"]
        self.assertEqual(chat["lastRun"]["plan"]["steps"],
                         ["add a theme toggle"])
        self.assertEqual(chat["lastRun"]["plan"]["failedAt"], -1)
        self.assertIsNone(chat["recordAfter"])
        self.assertEqual(chat["slugAfter"], chat["slug"])
        self.assertEqual(chat["lastRun"]["trace"]["via"], "repair.resume")
        self.assertEqual(chat["lastRun"]["trace"]["rule"], "r.resume-pending")

    def test_missing_input_failure_resumes(self):
        chat = self.out["chat"]
        self.assertEqual(len(chat["context"]), 1)
        self.assertEqual(chat["context"][0]["via"], "project.themeToggle")
        self.assertFalse(chat["context"][0]["error"])
        self.assertIn("themeToggle", chat["contextHtml"])

    def test_pending_dependency_is_refused(self):
        out = self.out["chat"]["dependency"]
        self.assertTrue(out["error"])
        self.assertEqual(out["via"], "repair.resume")
        self.assertIn("r.resume-dependency", out["text"])
        self.assertIn("nothing was run", out["text"])

    def test_pending_project_step_without_a_project_is_refused(self):
        out = self.out["chat"]["noproject"]
        self.assertTrue(out["error"])
        self.assertEqual(out["via"], "repair.resume")
        self.assertIn("r.resume-noproject", out["text"])
        self.assertIn("build a starter first", out["text"])

    def test_resume_and_repair_share_the_cap(self):
        chat = self.out["chat"]
        self.assertIn("pass 1 of 2", chat["cap1"]["text"])
        self.assertTrue(chat["cap1"]["error"])
        self.assertIn("pass 2 of 2", chat["cap2"]["text"])
        self.assertTrue(chat["cap2"]["error"])
        self.assertIn("cap reached", chat["cap3"]["text"])
        self.assertIn("r.resume-cap", chat["cap3"]["text"])
        self.assertEqual(chat["capRecord"]["kind"], "resume")
        self.assertEqual(chat["capRecord"]["passes"], 2)

    def test_a_resumed_failure_keeps_the_real_error(self):
        chat = self.out["chat"]
        self.assertTrue(chat["failedResume"]["error"])
        self.assertIn("resume · pass 1 of 2", chat["failedResume"]["text"])
        self.assertIn("division by zero", chat["failedRun"]["plan"]["errorText"])
        self.assertNotIn("resume ·", chat["failedRun"]["plan"]["errorText"])

    def test_failed_build_is_refused_and_the_previous_project_stays(self):
        chat = self.out["chat"]
        self.assertTrue(chat["buildFail"]["error"])
        self.assertEqual(chat["buildResume"]["via"], "repair.resume")
        self.assertTrue(chat["buildResume"]["error"])
        self.assertIn("r.resume-build", chat["buildResume"]["text"])
        self.assertEqual(chat["previousAfter"]["slug"], chat["previous"])
        self.assertIn("<html", chat["previousFile"].lower())

    def test_in_plan_resume_is_refused(self):
        chat = self.out["chat"]
        self.assertIn("only works as its own turn", chat["inPlan"]["text"])
        self.assertEqual(chat["inPlanRun"]["plan"]["steps"],
                         ["build a platformer game", "resume"])

    def test_resume_never_touches_the_network(self):
        self.assertEqual(self.out["chat"]["fetches"], 0,
                         "a resume route made a network call")
        with open(os.path.join(WEB, "repair.js"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotRegex(source, r"\bfetch\s*\(")
        self.assertNotIn("import(", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

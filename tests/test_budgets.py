#!/usr/bin/env python3
"""Step 36: hard step/plan budgets, preview reporting, and run headroom.

The Python plan runner and the browser sandbox must agree on the envelope:
every step gets a wall-clock cap, a plan gets a total cap, the preview names the
cap that would stop it, and the final run report exposes the remaining room.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORE = os.path.join(ROOT, "toolrx")
WEB = os.path.join(CORE, "web")
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import longform  # noqa: E402
import pipeline  # noqa: E402
import security  # noqa: E402

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
  'blake2b.js', 'router.js', 'skills.js', 'templates.js', 'context.js',
  'lang.js', 'patches.js', 'engine2d.js', 'engine2d.embed.js', 'engine3d.js',
  'engine3d.embed.js', 'worldgen.js', 'worldgen.embed.js', 'rpg2.js',
  'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  self.toolrxWeb.reset();
  const out = {};

  const plan = 'read notes.txt then count the words';
  out.preview = self.toolrxSkills.planPreview(plan);
  out.previewNoTime = self.toolrxSkills.planPreview(plan,
    { stepMs: 1000, planMs: 1500 });
  out.many = self.toolrxSkills.planPreview(
    Array.from({ length: 40 }, (_, i) => (i + 1) + '. read notes.txt').join('\n'));
  out.limits = self.toolrxWeb.limits();
  out.webPreview = self.toolrxWeb.planPreview(plan);

  const slow = {
    limits: { stepMs: 25, planMs: 5000 },
    fallback: () => new Promise(resolve => setTimeout(
      () => resolve({ text: 'late', error: false, via: 'test.slow' }), 120)),
  };
  out.timeout = await self.toolrxSkills.runPrompt(
    'zzzznotacommand then count the words', slow);

  self.toolrxWeb.reset();
  await self.toolrxWeb.prompt('build a short platformer game');
  const p = self.toolrxWeb.project();
  out.build = {
    last: self.toolrxWeb.lastRun(),
    bytes: self.toolrxWeb.projectBytes(),
    files: p.files.length,
    limits: self.toolrxWeb.limits(),
  };

  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


class PythonPlanBudgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pol = security.SecurityPolicy.load()

    def test_policy_carries_the_time_envelope(self):
        self.assertEqual(self.pol.max_step_ms, 4000)
        self.assertEqual(self.pol.max_plan_ms, 160000)

    def test_successful_plan_reports_budget_and_headroom(self):
        out = pipeline.process("list the files then show the uptime")
        self.assertFalse(out["blocked"], out)
        report = out.get("report")
        self.assertIsNotNone(report)
        self.assertEqual(report["steps"], 2)
        self.assertEqual(report["errors"], 0)
        self.assertTrue(report["ok"])
        self.assertEqual(report["budget"]["stepMs"], self.pol.max_step_ms)
        self.assertEqual(report["budget"]["planMs"], self.pol.max_plan_ms)
        self.assertGreaterEqual(report["ms"], 0)
        self.assertLessEqual(report["ms"], report["budget"]["planMs"])
        self.assertEqual(report["budget"]["remainingMs"],
                         max(0, report["budget"]["planMs"] - report["ms"]))

    def test_plan_wall_budget_stops_before_the_first_step(self):
        pol = security.SecurityPolicy.load()
        pol.max_plan_ms = 0
        info = {"steps": ["list the files", "show the uptime"]}
        with mock.patch.object(pipeline, "_run_step") as run:
            out = pipeline.process_plan("list the files show the uptime", pol, info)
        run.assert_not_called()
        self.assertTrue(out["blocked"])
        self.assertIn("plan wall budget", out["reason"])
        self.assertEqual(out["report"]["steps"], 1)
        self.assertFalse(out["report"]["ok"])

    def test_step_over_its_cap_is_reported_as_a_timeout(self):
        pol = security.SecurityPolicy.load()
        pol.max_step_ms = 1

        def slow(*_args, **_kwargs):
            time.sleep(0.02)
            return {"blocked": False, "reason": None, "decision": {},
                    "result": {"ok": True, "result": "done"}}

        info = {"steps": ["list the files", "show the uptime"]}
        with mock.patch.object(pipeline, "_run_step", side_effect=slow):
            out = pipeline.process_plan("list the files show the uptime", pol, info)
        self.assertTrue(out["blocked"])
        self.assertIn("timed out", out["reason"])
        self.assertEqual(out["report"]["steps"], 1)
        self.assertGreaterEqual(out["report"]["ms"], 1)


@unittest.skipUnless(NODE, "node is not installed")
class BrowserBudgetTest(unittest.TestCase):
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

    def test_preview_reports_the_active_envelope(self):
        p = self.out["preview"]
        self.assertFalse(p["blocked"], p)
        self.assertEqual(p["budget"]["steps"], 2)
        self.assertEqual(p["budget"]["maxSteps"], 40)
        self.assertEqual(p["budget"]["stepMs"], 4000)
        self.assertEqual(p["budget"]["planMs"], 160000)
        self.assertEqual(p["budget"]["worstCaseMs"], 8000)
        self.assertTrue(p["budget"]["fits"])

    def test_plan_wall_budget_refuses_at_preview_time(self):
        p = self.out["previewNoTime"]
        self.assertTrue(p["blocked"])
        self.assertIn("plan wall budget", p["reason"])
        self.assertEqual(p["budget"]["worstCaseMs"], 2000)
        self.assertFalse(p["budget"]["timeFits"])
        self.assertEqual(p["steps"], [])

    def test_a_full_plan_still_fits_the_default_wall_budget(self):
        p = self.out["many"]
        self.assertFalse(p["blocked"], p)
        self.assertEqual(p["budget"]["steps"], 40)
        self.assertEqual(p["budget"]["worstCaseMs"], 160000)
        self.assertTrue(p["budget"]["fits"])

    def test_limits_and_web_preview_expose_the_same_caps(self):
        limits = self.out["limits"]
        self.assertEqual(limits["stepTimeout"], 4000)
        self.assertEqual(limits["planTimeout"], 160000)
        self.assertEqual(limits["planChars"], 8000)
        self.assertEqual(limits["planSteps"], 40)
        preview = self.out["webPreview"]
        self.assertFalse(preview["blocked"], preview)
        self.assertEqual(preview["budget"]["project"]["files"]["max"],
                         limits["files"])
        self.assertEqual(preview["budget"]["project"]["bytes"]["max"],
                         limits["project"])

    def test_a_slow_step_times_out_and_stops_the_plan(self):
        steps = self.out["timeout"]
        self.assertEqual(len(steps), 1, steps)
        self.assertTrue(steps[0]["error"], steps[0])
        self.assertEqual(steps[0]["via"], "budget.timeout", steps[0])
        self.assertIn("step timed out", steps[0]["text"])
        self.assertGreaterEqual(steps[0]["ms"], 25)

    def test_build_reports_budget_headroom(self):
        build = self.out["build"]
        last = build["last"]
        self.assertTrue(last["ok"], last)
        budget = last["budget"]
        self.assertTrue(budget["within"], budget)
        self.assertEqual(budget["files"]["used"], build["files"])
        self.assertEqual(budget["files"]["max"], build["limits"]["files"])
        self.assertEqual(budget["bytes"]["used"], build["bytes"])
        self.assertEqual(budget["bytes"]["max"], build["limits"]["project"])
        self.assertEqual(budget["ms"]["max"], build["limits"]["planTimeout"])
        self.assertEqual(budget["ms"]["stepMs"], build["limits"]["stepTimeout"])
        self.assertGreaterEqual(budget["ms"]["used"], 0)
        self.assertLessEqual(budget["ms"]["used"], budget["ms"]["max"])
        self.assertEqual(budget["over"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

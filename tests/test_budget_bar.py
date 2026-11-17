#!/usr/bin/env python3
"""Step 50: one five-budget bar for preview, live plans, and the last run.

The browser ships `toolrx/web/budget.js` as the single model for characters,
steps, context bytes, project bytes, and time. These tests drive the real
modules in Node and compare every bar number with the budget object the report
already exposes, then compare the caps with the Python envelope.
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
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import envelope  # noqa: E402

ORDER = ["chars", "steps", "context", "project", "time"]

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
  'blake2b.js', 'router.js', 'limits.js', 'budget.js', 'planrewrite.js', 'thinking.js', 'repair.js', 'skills.js',
  'templates.js', 'context.js', 'lang.js', 'patches.js', 'engine2d.js',
  'engine2d.embed.js', 'engine3d.js', 'engine3d.embed.js', 'worldgen.js',
  'worldgen.embed.js', 'rpg2.js', 'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  self.toolrxWeb.reset();
  const out = {};

  out.pure = self.toolrxBudget.bars({
    chars: { used: 7000, max: 8000 },
    steps: { used: 41, max: 40 },
    context: { used: 1024, max: 8192 },
    project: { used: 524288, max: 524288 },
    time: { used: 150000, max: 160000 },
  });

  const query = 'read notes.txt then count the words';
  out.query = query;
  out.preview = self.toolrxWeb.planPreview(query);

  self.toolrxWeb.reset();
  await self.toolrxWeb.prompt('build a short platformer game');
  const project = self.toolrxWeb.project();
  out.afterBuild = {
    bytes: self.toolrxWeb.projectBytes(),
    files: project.files.length,
    preview: self.toolrxWeb.planPreview(query),
  };

  self.toolrxWeb.reset();
  const routed = await self.toolrxWeb.prompt('list the files then show the uptime');
  out.run = {
    last: self.toolrxWeb.lastRun(),
    report: self.toolrxWeb.report(),
    results: routed.length,
  };
  out.limits = self.toolrxWeb.limits();
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is not installed")
class BudgetBarTest(unittest.TestCase):
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
        cls.data = envelope.load()

    def test_model_lists_five_budgets_in_a_fixed_order(self):
        pure = self.out["pure"]
        self.assertEqual([bar["key"] for bar in pure], ORDER)
        self.assertEqual([bar["label"] for bar in pure],
                         ["characters", "steps", "context", "project", "time"])

    def test_levels_and_readouts_are_honest(self):
        pure = {bar["key"]: bar for bar in self.out["pure"]}
        self.assertEqual(pure["chars"]["level"], "warn")
        self.assertEqual(pure["chars"]["readout"], "7,000 chars / 8,000 chars")
        self.assertEqual(pure["chars"]["remaining"], 1000)
        self.assertEqual(pure["steps"]["level"], "over")
        self.assertTrue(pure["steps"]["over"])
        self.assertEqual(pure["steps"]["readout"], "41 steps / 40 steps")
        self.assertEqual(pure["steps"]["remaining"], 0)
        self.assertEqual(pure["context"]["level"], "ok")
        self.assertEqual(pure["context"]["readout"], "1.0 KB / 8.0 KB")
        self.assertEqual(pure["project"]["level"], "warn")
        self.assertEqual(pure["project"]["readout"], "512 KB / 512 KB")
        self.assertEqual(pure["project"]["remaining"], 0)
        self.assertEqual(pure["time"]["level"], "warn")
        self.assertEqual(pure["time"]["readout"], "150 s / 160 s")
        self.assertEqual(pure["time"]["remaining"], 10000)

    def test_preview_bar_numbers_match_the_budget(self):
        preview = self.out["preview"]
        self.assertFalse(preview["blocked"], preview)
        budget = preview["budget"]
        bars = {bar["key"]: bar for bar in budget["bars"]}
        self.assertEqual(list(bars), ORDER)
        query = self.out["query"]
        self.assertEqual(bars["chars"]["used"], len(query))
        self.assertEqual(bars["chars"]["max"], budget["maxChars"])
        self.assertEqual(bars["steps"]["used"], budget["steps"])
        self.assertEqual(bars["steps"]["max"], budget["maxSteps"])
        self.assertEqual(bars["context"]["used"], budget["context"]["used"])
        self.assertEqual(bars["context"]["max"], budget["context"]["max"])
        self.assertEqual(bars["project"]["used"],
                         budget["project"]["bytes"]["used"])
        self.assertEqual(bars["project"]["max"],
                         budget["project"]["bytes"]["max"])
        self.assertEqual(bars["time"]["used"], budget["worstCaseMs"])
        self.assertEqual(bars["time"]["max"], budget["planMs"])

    def test_preview_caps_match_the_python_envelope(self):
        budget = self.out["preview"]["budget"]
        bars = {bar["key"]: bar for bar in budget["bars"]}
        self.assertEqual(bars["chars"]["max"], self.data["planChars"])
        self.assertEqual(bars["steps"]["max"], self.data["planSteps"])
        self.assertEqual(bars["context"]["max"], self.data["contextBytes"])
        self.assertEqual(bars["project"]["max"], self.data["projectBytes"])
        self.assertEqual(bars["time"]["max"], self.data["planMs"])

    def test_preview_reads_the_active_project_size(self):
        after = self.out["afterBuild"]
        self.assertGreater(after["bytes"], 0)
        self.assertGreater(after["files"], 0)
        bars = {bar["key"]: bar for bar in
                after["preview"]["budget"]["bars"]}
        self.assertEqual(bars["project"]["used"], after["bytes"])
        self.assertEqual(bars["project"]["max"], self.data["projectBytes"])
        self.assertEqual(bars["project"]["remaining"],
                         self.data["projectBytes"] - after["bytes"])

    def test_run_bar_numbers_match_the_last_run_report(self):
        run = self.out["run"]
        last = run["last"]
        self.assertEqual(run["results"], 2)
        self.assertEqual(run["report"], last["budget"])
        bars = {bar["key"]: bar for bar in last["budget"]["bars"]}
        self.assertEqual(list(bars), ORDER)
        self.assertEqual(bars["chars"]["used"], last["chars"])
        self.assertEqual(bars["chars"]["max"], self.data["planChars"])
        self.assertEqual(bars["steps"]["used"], last["steps"])
        self.assertEqual(bars["steps"]["max"], self.data["planSteps"])
        self.assertEqual(bars["context"]["used"], last["contextBytes"])
        self.assertEqual(bars["context"]["max"], self.data["contextBytes"])
        self.assertEqual(bars["project"]["used"],
                         last["budget"]["bytes"]["used"])
        self.assertEqual(bars["project"]["max"], self.data["projectBytes"])
        self.assertEqual(bars["time"]["used"], last["ms"])
        self.assertEqual(bars["time"]["max"], self.data["planMs"])
        self.assertEqual(last["budget"]["over"], [])


if __name__ == "__main__":
    unittest.main()

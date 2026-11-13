#!/usr/bin/env python3
"""Step 37 browser suite: builds, growth, and context from the shared fixtures.

Runs the real in-tab sandbox in Node (no server, no network): the same router,
command library, templates, and patch engine that GitHub Pages loads. The
fixture file is the same one ``test_envelope.py`` reads, so both runtimes assert
the same structural outcomes. The step-35 complex build and five-patch undo
fidelity checks stay here as permanent regressions.
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
FIXTURES = os.path.join(HERE, "fixtures", "longform.json")

JS = r"""
const fs = require('fs');
const path = require('path');
const WEB = process.argv[1];
const COMMANDS = process.argv[2];
const MODEL = process.argv[3];
const FIX = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));

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
  'blake2b.js', 'router.js', 'limits.js', 'skills.js', 'templates.js', 'context.js', 'lang.js',
  'patches.js', 'engine2d.js', 'engine2d.embed.js', 'engine3d.js',
  'engine3d.embed.js', 'worldgen.js', 'worldgen.embed.js', 'rpg2.js',
  'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

function bytes(map) {
  return Object.keys(map).reduce((n, k) => n + Buffer.byteLength(map[k], 'utf8'), 0);
}
function snapshot() {
  const p = self.toolrxWeb.project();
  if (!p) return {};
  const out = {};
  p.files.slice().sort().forEach(name => {
    out[name] = self.toolrxWeb.projectFile(p.slug, name);
  });
  return out;
}
function planOf() {
  const raw = JSON.parse(self.toolrxWeb.contextRaw() || '{}');
  const entry = (raw.entries || []).find(e => e.kind === 'plan' && e.key === 'last');
  return entry ? JSON.parse(entry.text) : null;
}
function kindsOf() {
  const raw = JSON.parse(self.toolrxWeb.contextRaw() || '{}');
  return (raw.entries || []).map(e => e.kind).sort();
}

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  self.toolrxWeb.reset();
  const out = { fixture: { builds: {}, growth: {}, context: {} } };

  const desc = 'a huge space rpg with crafting, 6 quests, 3 levels, 12 enemies, '
    + '8 npcs, 4 items, sub-theme nebula, 96x96 world, day night cycle, sound and a boss';
  const spec = self.toolrxTemplates.spec('rpg', desc);
  out.spec = {
    kind: spec.kind,
    features: spec.features,
    counts: spec.counts,
    levels: spec.levels,
    size: spec.size,
    subtheme: spec.subtheme,
  };
  const built = await self.toolrxWeb.prompt('build ' + desc);
  const p = self.toolrxWeb.project();
  out.build = {
    steps: built.length,
    errors: built.filter(r => r.error).length,
    files: p.files.slice().sort(),
    bytes: self.toolrxWeb.projectBytes(),
    limits: self.toolrxWeb.limits(),
    hasContent: p.files.indexOf('content.js') >= 0,
    previewHasContent: /toolrxContent/.test(self.toolrxWeb.preview().html),
    lastRun: self.toolrxWeb.lastRun(),
  };

  self.toolrxWeb.reset();
  await self.toolrxWeb.prompt('build a top-down shooter with pixel art and sound');
  const before = snapshot();
  out.patches = {
    base: { files: Object.keys(before).length, bytes: bytes(before) },
    steps: [],
    undo: [],
  };
  const sequence = ['add three enemy types', 'add a boss', 'add a quest',
                    'add sound', 'make it harder'];
  for (const query of sequence) {
    const res = await self.toolrxWeb.prompt(query);
    const now = snapshot();
    out.patches.steps.push({
      query: query,
      ok: !res[0].error,
      via: res[0].via || '',
      files: Object.keys(now).length,
      bytes: bytes(now),
      undo: self.toolrxWeb.lastRun().undo,
      text: String(res[0].text || '').slice(0, 100),
    });
  }
  const patched = snapshot();
  out.patches.after = { files: Object.keys(patched).length, bytes: bytes(patched) };
  for (let i = 0; i < sequence.length; i++) {
    const res = await self.toolrxWeb.prompt('undo');
    const now = snapshot();
    out.patches.undo.push({
      ok: !res[0].error,
      files: Object.keys(now).length,
      bytes: bytes(now),
      sameAsBefore: JSON.stringify(now) === JSON.stringify(before),
      undo: self.toolrxWeb.lastRun().undo,
    });
  }
  out.patches.restored = JSON.stringify(snapshot()) === JSON.stringify(before);
  out.patches.initial = { files: Object.keys(before).length, bytes: bytes(before) };

  /* --------------------------------------------------- fixture builds -- */
  for (const c of FIX.builds) {
    self.toolrxWeb.reset();
    const first = await self.toolrxWeb.prompt(c.query);
    const a = snapshot();
    const firstProject = self.toolrxWeb.project();
    const firstKind = firstProject.kind;
    const firstBytes = self.toolrxWeb.projectBytes();
    self.toolrxWeb.reset();
    const second = await self.toolrxWeb.prompt(c.query);
    const b = snapshot();
    out.fixture.builds[c.name] = {
      steps: first.length,
      errors: first.filter(r => r.error).length,
      secondSteps: second.length,
      kind: firstKind,
      files: firstProject.files.slice().sort(),
      bytes: firstBytes,
      same: JSON.stringify(a) === JSON.stringify(b),
      limits: self.toolrxWeb.limits(),
    };
  }

  /* --------------------------------------------------- fixture growth -- */
  for (const c of FIX.growth) {
    self.toolrxWeb.reset();
    await self.toolrxWeb.prompt(c.base);
    const baseMap = snapshot();
    const baseKind = self.toolrxWeb.project().kind;
    let prev = baseMap;
    const steps = [];
    for (const s of c.steps) {
      const res = await self.toolrxWeb.prompt(s.query);
      const now = snapshot();
      const added = Object.keys(now).filter(k => !(k in prev)).sort();
      steps.push({
        query: s.query,
        via: res[0].via || '',
        ok: !res[0].error,
        added: added,
        bytes: bytes(now),
        undo: self.toolrxWeb.lastRun().undo,
        text: String(res[0].text || '').slice(0, 120),
      });
      prev = now;
    }
    const after = snapshot();
    for (let i = 0; i < c.steps.length; i++) await self.toolrxWeb.prompt('undo');
    out.fixture.growth[c.name] = {
      baseKind: baseKind,
      baseFiles: Object.keys(baseMap).sort(),
      baseBytes: bytes(baseMap),
      steps: steps,
      afterBytes: bytes(after),
      restored: JSON.stringify(snapshot()) === JSON.stringify(baseMap),
      undoAfter: self.toolrxWeb.lastRun().undo,
    };
  }

  /* -------------------------------------------------- fixture context -- */
  for (const c of FIX.context) {
    if (c.name === 'project-isolation') {
      self.toolrxWeb.reset();
      await self.toolrxWeb.prompt(c.base);
      await self.toolrxWeb.prompt(c.edit);
      const activeKind = self.toolrxWeb.project().kind;
      const before = kindsOf();
      await self.toolrxWeb.prompt(c.otherProject);
      const otherProject = self.toolrxWeb.project();
      const other = kindsOf();
      await self.toolrxWeb.prompt(c.returnCommand);
      const back = kindsOf();
      out.fixture.context[c.name] = {
        activeKind: activeKind,
        before: before,
        otherSlug: otherProject ? otherProject.slug : '',
        other: other,
        back: back,
      };
      continue;
    }
    self.toolrxWeb.reset();
    await self.toolrxWeb.prompt(c.base);
    const planRun = await self.toolrxWeb.prompt(c.plan);
    const afterPlan = planOf();
    const record = {
      planSteps: afterPlan ? afterPlan.steps : [],
      statusAfterPlan: afterPlan ? afterPlan.status : [],
      planRun: planRun.map(r => ({ via: r.via || '', error: !!r.error })),
    };
    if (c.expand) {
      const expanded = await self.toolrxWeb.prompt(c.expand);
      const afterExpand = planOf();
      record.expandText = String(expanded[0].text || '').slice(0, 240);
      record.stepsAfterExpand = afterExpand ? afterExpand.steps : [];
      record.statusAfterExpand = afterExpand ? afterExpand.status : [];
    }
    const contRun = await self.toolrxWeb.prompt(c.continue);
    const afterCont = planOf();
    record.continueVia = contRun[0].via || '';
    record.continueText = String(contRun[0].text || '').slice(0, 500);
    record.continuedCount = contRun.length;
    record.statusAfterContinue = afterCont ? afterCont.status : [];
    out.fixture.context[c.name] = record;
  }

  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is not installed")
class EnvelopeBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", JS, WEB,
             os.path.join(WEB, "commands.json"),
             os.path.join(ROOT, "toolrx", "micro_model.json"),
             FIXTURES],
            capture_output=True, text=True, timeout=360,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-4000:])
        cls.out = json.loads(proc.stdout)
        with open(FIXTURES, encoding="utf-8") as fh:
            cls.fixtures = json.load(fh)

    def test_complex_build_honours_the_spec_and_budget(self):
        spec = self.out["spec"]
        self.assertEqual(spec["kind"], "rpg")
        self.assertEqual(spec["counts"]["quests"], 6)
        self.assertEqual(spec["counts"]["levels"], 3)
        self.assertEqual(spec["counts"]["enemies"], 12)
        self.assertEqual(spec["counts"]["npcs"], 8)
        self.assertEqual(spec["counts"]["items"], 4)
        self.assertEqual(spec["levels"], 3)
        self.assertEqual(spec["size"], 96)
        self.assertEqual(spec["subtheme"], "nebula")
        for feature in ("crafting", "day night cycle", "sound"):
            self.assertIn(feature, spec["features"])

        build = self.out["build"]
        self.assertGreaterEqual(build["steps"], 1)
        self.assertEqual(build["errors"], 0)
        self.assertTrue(build["hasContent"])
        self.assertTrue(build["previewHasContent"])
        self.assertLessEqual(len(build["files"]), build["limits"]["files"])
        self.assertLessEqual(build["bytes"], build["limits"]["project"])
        self.assertGreater(build["bytes"], 10000)
        self.assertEqual(build["lastRun"]["errors"], 0)
        self.assertEqual(build["lastRun"]["files"], len(build["files"]))
        self.assertEqual(build["lastRun"]["bytes"], build["bytes"])

    def test_five_patches_apply_and_undo_byte_exactly(self):
        patch = self.out["patches"]
        self.assertEqual(len(patch["steps"]), 5)
        for i, step in enumerate(patch["steps"]):
            self.assertTrue(step["ok"], step)
            self.assertGreaterEqual(step["files"], 5, step)
            self.assertEqual(step["undo"], i + 1, step)
        self.assertGreater(patch["after"]["bytes"], patch["base"]["bytes"])
        self.assertGreaterEqual(patch["after"]["files"], patch["base"]["files"])

        self.assertEqual(len(patch["undo"]), 5)
        for i, step in enumerate(patch["undo"]):
            self.assertTrue(step["ok"], step)
            self.assertEqual(step["undo"], 4 - i, step)
        self.assertTrue(patch["restored"])
        self.assertEqual(patch["after"]["files"], patch["initial"]["files"])

    def test_fixture_builds_are_single_step_reproducible_and_inside_budget(self):
        for case in self.fixtures["builds"]:
            got = self.out["fixture"]["builds"][case["name"]]
            self.assertEqual(got["steps"], 1, case["name"])
            self.assertEqual(got["secondSteps"], 1, case["name"])
            self.assertEqual(got["errors"], 0, case["name"])
            self.assertEqual(got["kind"], case["kind"], case["name"])
            self.assertEqual(got["files"], case["files"], case["name"])
            self.assertGreaterEqual(got["bytes"], case["minBytes"], case["name"])
            self.assertTrue(got["same"], case["name"])
            self.assertLessEqual(len(got["files"]), got["limits"]["files"])
            self.assertLessEqual(got["bytes"], got["limits"]["project"])

    def test_fixture_growth_adds_real_files_and_undo_restores(self):
        for case in self.fixtures["growth"]:
            got = self.out["fixture"]["growth"][case["name"]]
            self.assertEqual(got["baseKind"], case["baseKind"], case["name"])
            self.assertEqual(len(got["steps"]), len(case["steps"]), case["name"])
            for i, (step, expected) in enumerate(zip(got["steps"],
                                                     case["steps"])):
                self.assertTrue(step["ok"], (case["name"], step))
                self.assertEqual(step["via"], expected["via"],
                                 (case["name"], i))
                self.assertEqual(step["added"], sorted(expected["adds"]),
                                 (case["name"], i))
                self.assertEqual(step["undo"], i + 1, (case["name"], i))
                if expected.get("bytesGrow"):
                    self.assertGreater(step["bytes"], got["baseBytes"],
                                       (case["name"], i))
            self.assertTrue(got["restored"], case["name"])
            self.assertEqual(got["undoAfter"], 0, case["name"])

    def test_context_continuation_runs_only_the_pending_suffix(self):
        case = next(c for c in self.fixtures["context"]
                    if c["name"] == "continue-after-failure")
        got = self.out["fixture"]["context"]["continue-after-failure"]
        self.assertEqual(got["planSteps"], case["plan"].split(" then "))
        self.assertEqual(got["statusAfterPlan"], case["statusAfterPlan"])
        self.assertEqual(got["continueVia"], "context.continue")
        self.assertIn("1 step run", got["continueText"])
        self.assertIn("add a boss", got["continueText"])
        self.assertNotIn("read missing", got["continueText"])
        self.assertEqual(got["statusAfterContinue"], case["statusAfterContinue"])

    def test_context_expansion_appends_pending_steps(self):
        case = next(c for c in self.fixtures["context"]
                    if c["name"] == "expand-then-continue")
        got = self.out["fixture"]["context"]["expand-then-continue"]
        plain = case["plan"].split(" then ")
        self.assertEqual(got["statusAfterPlan"], case["statusAfterPlan"])
        self.assertEqual(got["stepsAfterExpand"], plain + [case["expandedStep"]])
        self.assertEqual(got["statusAfterExpand"],
                         ["done", "done", "pending"])
        self.assertEqual(got["continueVia"], "context.continue")
        self.assertIn(case["expandedStep"], got["continueText"])
        self.assertEqual(got["statusAfterContinue"], case["statusAfterContinue"])

    def test_context_never_leaks_across_projects(self):
        case = next(c for c in self.fixtures["context"]
                    if c["name"] == "project-isolation")
        got = self.out["fixture"]["context"]["project-isolation"]
        self.assertEqual(got["activeKind"], "platformer")
        self.assertIn("file", got["before"])
        self.assertIn("edit", got["before"])
        self.assertEqual(got["other"], case["otherEntries"])
        for kind in case["returnEntries"]:
            self.assertIn(kind, got["back"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

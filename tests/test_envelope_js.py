#!/usr/bin/env python3
"""Step 35 browser envelope: complex builds and five-patch undo fidelity.

Runs the real in-tab sandbox in Node (no server, no network): the same router,
command library, templates, and patch engine that GitHub Pages loads. The build
must stay within the project budget, and five stacked patches must each apply
and then undo back to the byte-identical starting project.
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
  'blake2b.js', 'router.js', 'skills.js', 'templates.js', 'context.js', 'lang.js',
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

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  self.toolrxWeb.reset();
  const out = {};

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
             os.path.join(ROOT, "toolrx", "micro_model.json")],
            capture_output=True, text=True, timeout=180,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-4000:])
        cls.out = json.loads(proc.stdout)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)

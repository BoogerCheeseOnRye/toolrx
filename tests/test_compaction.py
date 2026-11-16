#!/usr/bin/env python3
"""Step 51: deterministic context compaction.

The browser context store must compact in one fixed policy order, keep the
active plan and build spec, record every dropped or summarized entry, stay
inside its byte cap, and produce byte-identical output when run twice. These
tests drive `toolrx/web/context.js` directly in Node, with a fake summarizer
that stands in for the step-44 extractor.
"""

import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORE = os.path.join(ROOT, "toolrx")
WEB = os.path.join(CORE, "web")
NODE = shutil.which("node")

JS = r"""
const fs = require('fs');
const path = require('path');
const WEB = process.argv[1];

global.self = global;
const store = {};
global.localStorage = {
  getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
for (const name of ['limits.js', 'context.js']) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}
const C = self.toolrxContext;

const summarize = text => String(text == null ? '' : text)
  .split(/\n+/).map(line => line.trim()).filter(Boolean)
  .slice(0, 3).map(line => '- ' + line);

const plan = C.stable({
  version: 1,
  steps: ['add sound', 'read missing.txt', 'add a boss'],
  status: ['done', 'error', 'pending'],
});

const entries = () => ([
  { kind: 'file', key: 'engine2d.js',
    text: 'engine2d.js · 91 bytes · 4 lines · sha 0123456789abcdef · shared engine' },
  { kind: 'spec', key: 'active',
    text: 'spec · 2D top-down · shooter · pixel · medium · seed 7' },
  { kind: 'file', key: 'index.html',
    text: 'index.html · 1767 bytes · 21 lines · sha abcdef0123456789 · <!doctype html>' },
  { kind: 'file', key: 'app.js',
    text: 'app.js · 3680 bytes · 59 lines · sha 1234567890abcdef · var cv=...' },
  { kind: 'file', key: 'styles.css',
    text: 'styles.css · 3116 bytes · 3 lines · sha fedcba9876543210 · :root{--bg:#0b1020}' },
  { kind: 'file', key: 'README.md',
    text: 'README.md · 1424 bytes · 57 lines · sha 9f3a1c7e5b2d4806 · Top-down shooter' },
  { kind: 'edit', key: 'last', text: '{"labels":["boss"],"ids":["boss"]}' },
  { kind: 'result', key: 'last',
    text: 'query: add a boss\nvia: edit.apply\n'
      + 'The boss walks the level. It fires every two seconds. '
      + 'It drops a key when defeated. It respawns after ten seconds. '
      + 'The level ends when the key is used.' },
  { kind: 'session', key: 'rolling',
    text: Array.from({ length: 12 }, (_, i) =>
      (i % 4 === 3 ? '✗' : '✓') + ' step ' + i + ' did something useful').join('\n') },
  { kind: 'plan', key: 'last', text: plan },
]);

function seed(slug, cap) {
  localStorage.setItem('toolrx.context.cap', '8192');
  C.clear(slug);
  C.setMany(slug, entries(), { summarize });
  localStorage.setItem('toolrx.context.cap', String(cap));
}

function state(slug) {
  return {
    raw: C.raw(slug),
    stored: C.byteLength(C.raw(slug)),
    plan: C.get(slug, 'plan', 'last'),
    spec: C.get(slug, 'spec', 'active'),
    sessionText: C.get(slug, 'session', 'rolling'),
    notes: C.notes(slug),
  };
}

const out = {};

// Explicit compaction: deterministic, idempotent, plan and spec survive.
seed('explicit', 700);
const before = state('explicit');
const first = C.compact('explicit', { summarize });
const afterOne = state('explicit');
const second = C.compact('explicit', { summarize });
const afterTwo = state('explicit');
out.explicit = {
  before: before,
  first: first,
  second: second,
  afterOne: afterOne,
  afterTwo: afterTwo,
  same: afterOne.raw === afterTwo.raw,
  changed: before.raw !== afterOne.raw,
};

// Two independent runs from the same seed must agree byte for byte. The
// project slug is part of the stored bytes, so reuse one scope and clear it.
seed('determinism', 700);
C.compact('determinism', { summarize });
const determinismA = C.raw('determinism');
seed('determinism', 700);
C.compact('determinism', { summarize });
const determinismB = C.raw('determinism');
out.determinism = {
  a: determinismA,
  b: determinismB,
  same: determinismA === determinismB,
};

// Automatic compaction: triggered by a write near the cap, and it must keep
// the plan and spec even while dropping everything else.
localStorage.setItem('toolrx.context.cap', '600');
C.clear('automatic');
C.setMany('automatic', entries(), { summarize });
const auto = state('automatic');
out.automatic = {
  state: auto,
  report: (() => {
    try {
      return JSON.parse(localStorage.getItem(
        'toolrx.context.v1.automatic.compact') || 'null');
    } catch (e) { return null; }
  })(),
};

// A tiny cap still enforces the cap and keeps both protected entries.
seed('tiny', 256);
const tiny = C.compact('tiny', { summarize });
const tinyState = state('tiny');
out.tiny = { result: tiny, state: tinyState };

// A deliberately oversized session proves older rows are summarized first.
localStorage.setItem('toolrx.context.cap', '8192');
C.clear('session');
C.setMany('session', [
  { kind: 'plan', key: 'last', text: plan },
  { kind: 'spec', key: 'active', text: 'spec · test' },
  { kind: 'session', key: 'rolling',
    text: Array.from({ length: 40 }, (_, i) =>
      '✓ step ' + i + ' with a reasonably long description').join('\n') },
], { summarize });
localStorage.setItem('toolrx.context.cap', '900');
const sessionBefore = state('session');
const sessionCompact = C.compact('session', { summarize });
const sessionAfter = state('session');
out.session = {
  before: sessionBefore,
  compact: sessionCompact,
  after: sessionAfter,
};

console.log(JSON.stringify(out));
"""


@unittest.skipUnless(NODE, "node is not installed")
class CompactionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([NODE, "-e", JS, WEB],
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-4000:])
        cls.out = json.loads(proc.stdout)

    def test_explicit_compaction_is_idempotent(self):
        e = self.out["explicit"]
        self.assertTrue(e["changed"], e["first"]["text"])
        self.assertTrue(e["same"], "two compactions must be byte-identical")
        self.assertIn("context compact", e["first"]["text"])
        self.assertIn("nothing to compact", e["second"]["text"])
        self.assertEqual(e["second"]["actions"], [])

    def test_explicit_compaction_keeps_the_plan_and_spec(self):
        e = self.out["explicit"]
        self.assertTrue(e["afterOne"]["plan"], "the plan must survive")
        self.assertTrue(e["afterOne"]["spec"], "the spec must survive")
        self.assertEqual(e["afterOne"]["plan"], e["before"]["plan"])
        self.assertEqual(e["afterOne"]["spec"], e["before"]["spec"])

    def test_every_compaction_action_appears_in_the_notes(self):
        e = self.out["explicit"]
        actions = e["first"]["actions"]
        self.assertTrue(actions)
        noted = {(n["kind"], n["key"], n["why"]) for n in e["afterOne"]["notes"]}
        for action in actions:
            self.assertIn((action["kind"], action["key"], action["why"]), noted)
            self.assertGreaterEqual(action["bytes"], 0)
        for note in e["afterOne"]["notes"]:
            self.assertIn(note["why"],
                          ("trimmed", "evicted", "summarized", "dropped"))

    def test_explicit_compaction_enforces_the_cap(self):
        e = self.out["explicit"]
        self.assertLessEqual(e["afterOne"]["stored"], 700)
        self.assertLessEqual(e["afterTwo"]["stored"], 700)

    def test_two_runs_from_the_same_state_are_byte_identical(self):
        d = self.out["determinism"]
        self.assertTrue(d["same"])
        self.assertTrue(d["a"])

    def test_automatic_compaction_keeps_the_plan_and_enforces_the_cap(self):
        a = self.out["automatic"]
        self.assertTrue(a["state"]["plan"], "automatic compaction kept no plan")
        self.assertTrue(a["state"]["spec"], "automatic compaction kept no spec")
        self.assertLessEqual(a["state"]["stored"], 600)
        self.assertIsNotNone(a["report"])
        self.assertTrue(a["report"]["actions"])
        self.assertLessEqual(a["report"]["after"]["stored"], 600)
        for action in a["report"]["actions"]:
            self.assertIn(action["why"],
                          ("trimmed", "evicted", "summarized", "dropped"))

    def test_tiny_cap_keeps_plan_and_spec_and_enforces_the_cap(self):
        t = self.out["tiny"]
        self.assertTrue(t["state"]["plan"], "the plan must survive a tiny cap")
        self.assertTrue(t["state"]["spec"], "the spec must survive a tiny cap")
        self.assertLessEqual(t["state"]["stored"], 256)
        self.assertTrue(t["result"]["actions"])

    def test_older_session_rows_are_summarized_before_dropping(self):
        s = self.out["session"]
        self.assertTrue(s["compact"]["actions"])
        kinds = {(a["kind"], a["why"]) for a in s["compact"]["actions"]}
        self.assertIn(("session", "summarized"), kinds)
        self.assertTrue(s["after"]["plan"])
        self.assertTrue(s["after"]["spec"])
        self.assertLessEqual(s["after"]["stored"], 900)
        self.assertIn("older steps summarized", s["after"]["sessionText"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

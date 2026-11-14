#!/usr/bin/env python3
"""Step 44: deterministic extractors for long intermediates.

Runs the real browser module in Node. The fixture file pins every output byte;
the remaining tests cover the named caps, the honest empty/short replies, the
previous-step chain, and determinism across runs.
"""

import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NODE = shutil.which("node")
SKILLS = os.path.join(ROOT, "toolrx", "web", "skills.js")
COMMANDS = os.path.join(ROOT, "toolrx", "web", "commands.json")
FIXTURES = os.path.join(HERE, "fixtures", "extractors.json")

JS = r"""
const fs = require('fs');
const path = require('path');
global.self = global;
global.fetch = () => Promise.resolve({
  ok: true,
  json: () => Promise.resolve(JSON.parse(fs.readFileSync(process.argv[1], 'utf8'))),
});
const store = {};
global.localStorage = {
  getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.dispatchEvent = () => {};
const WEB = path.dirname(process.argv[2]);
eval(fs.readFileSync(path.join(WEB, 'limits.js'), 'utf8'));
eval(fs.readFileSync(process.argv[2], 'utf8'));

const fixture = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const S = self.toolrxSkills;
const out = {};

function ctx(files) {
  const map = files || {};
  return {
    fs: {
      exists: p => Object.prototype.hasOwnProperty.call(map, p),
      read: p => map[p],
      write: (p, c) => { map[p] = String(c); return 'wrote ' + p; },
      list: () => Object.keys(map).join('\n'),
    },
  };
}

const run = (op, args) => S.exec({ op: op, args: args || {} }, ctx());

(async () => {
  await S.init('commands.json');
  const docs = fixture.documents;

  // Fixture outputs, plus a second and third run to prove determinism.
  out.fixture = {};
  out.repeat = {};
  for (const [name, op, args] of [
    ['list', 'text.list', { text: docs.list }],
    ['facts', 'text.facts', { text: docs.facts }],
    ['code', 'text.code', { text: docs.code }],
    ['diff', 'text.diff', { a: docs.diffLeft, b: docs.diffRight }],
  ]) {
    const first = (await run(op, args)).text;
    const again = (await run(op, args)).text;
    out.fixture[name] = first;
    out.repeat[name] = first === again;
  }

  // Honest empty and short inputs.
  out.empty = {};
  for (const [name, op] of [['list', 'text.list'], ['facts', 'text.facts'],
                            ['code', 'text.code']]) {
    out.empty[name] = (await run(op, { text: '' })).text;
  }
  out.short = {};
  out.short.list = (await run('text.list', { text: 'plain prose only' })).text;
  out.short.facts = (await run('text.facts', { text: '- one\n- two' })).text;
  out.short.code = (await run('text.code', { text: 'just prose' })).text;
  out.short.diffLeft = (await run('text.diff', { a: '', b: 'x' })).text;
  out.short.diffRight = (await run('text.diff', { a: 'x', b: '' })).text;
  out.short.diffBoth = (await run('text.diff', { a: '', b: '' })).text;
  out.short.diffSame = (await run('text.diff', { a: 'one\ntwo', b: 'one\ntwo' })).text;

  // A file path resolves through ctx.fs, and the previous result feeds the
  // next step without a model: facts are bullets, so the list extractor reads
  // them back as items.
  const chain = await S.runPrompt(
    'extract the key facts from notes.md then extract the list',
    ctx({ 'notes.md': docs.facts }));
  out.chain = chain.map(r => ({ via: r.via, text: r.text, error: !!r.error }));

  // Input cap: extractChars. The list is longer than 8000 chars, so the input
  // is cut and the note says so; the output cap then trims to 200 items.
  const longList = Array.from({ length: 1500 }, (_, i) => '- item ' + i).join('\n');
  const capped = (await run('text.list', { text: longList })).text;
  out.inputCap = {
    length: longList.length,
    hasNote: capped.includes('(input truncated at 8000 of ' + longList.length + ' chars)'),
    lines: capped.split('\n').length,
    first: capped.split('\n')[0],
    last: capped.split('\n').slice(-2)[0],
  };

  // Output cap: extractItems, with an explicit footer.
  const many = Array.from({ length: 250 }, (_, i) => '- item ' + i).join('\n');
  const trimmed = (await run('text.list', { text: many })).text.split('\n');
  out.outputCap = {
    lines: trimmed.length,
    footer: trimmed[trimmed.length - 1],
    lastItem: trimmed[trimmed.length - 2],
  };

  // Diff caps: lines per side, then changed lines.
  const wide = Array.from({ length: 401 }, (_, i) => 'line ' + i).join('\n');
  try {
    await run('text.diff', { a: wide, b: 'line 0' });
    out.diffLines = null;
  } catch (e) {
    out.diffLines = e.message;
  }
  const left = Array.from({ length: 300 }, (_, i) => 'left ' + i).join('\n');
  const right = Array.from({ length: 300 }, (_, i) => 'right ' + i).join('\n');
  const changed = (await run('text.diff', { a: left, b: right })).text.split('\n');
  out.diffChanged = {
    header: changed[0],
    lines: changed.length,
    footer: changed[changed.length - 1],
  };

  // The limits are exposed through the same envelope as every other cap.
  out.limits = {
    chars: self.toolrxLimits.extractChars,
    items: self.toolrxLimits.extractItems,
    diff: self.toolrxLimits.diffLines,
  };
  out.limitsText = S.limitsText();
  console.log(JSON.stringify(out));
})();
"""


@unittest.skipUnless(NODE, "node is not installed")
class ExtractorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURES, encoding="utf-8") as fh:
            cls.fixture = json.load(fh)
        proc = subprocess.run([NODE, "-e", JS, COMMANDS, SKILLS, FIXTURES],
                              capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-3000:] or proc.stdout[-3000:])
        cls.out = json.loads(proc.stdout)

    def test_fixture_outputs_are_byte_exact(self):
        for name, expected in self.fixture["expected"].items():
            self.assertEqual(self.out["fixture"][name], expected, name)

    def test_extractors_are_deterministic(self):
        self.assertEqual(self.out["repeat"],
                         {"list": True, "facts": True, "code": True, "diff": True})

    def test_empty_and_short_inputs_are_honest(self):
        self.assertEqual(self.out["empty"]["list"],
                         "nothing to extract — the text is empty")
        self.assertEqual(self.out["empty"]["facts"],
                         "nothing to extract — the text is empty")
        self.assertEqual(self.out["empty"]["code"],
                         "nothing to extract — the text is empty")
        self.assertEqual(self.out["short"]["list"], "(no list items found)")
        self.assertEqual(self.out["short"]["facts"], "(no key facts found)")
        self.assertEqual(self.out["short"]["code"],
                         "(no functions or classes found)")
        self.assertIn("left side is empty", self.out["short"]["diffLeft"])
        self.assertIn("right side is empty", self.out["short"]["diffRight"])
        self.assertIn("both sides are empty", self.out["short"]["diffBoth"])
        self.assertEqual(self.out["short"]["diffSame"],
                         "no changes · 2 lines identical")

    def test_previous_step_feeds_the_next(self):
        chain = self.out["chain"]
        self.assertEqual([r["via"] for r in chain], ["text.facts", "text.list"])
        self.assertFalse(chain[0]["error"] or chain[1]["error"])
        facts = [line[2:] for line in chain[0]["text"].split("\n")]
        self.assertEqual(chain[1]["text"], "\n".join(facts))
        self.assertIn("The bridge is 240 metres long.", chain[1]["text"])

    def test_input_cap_is_named(self):
        cap = self.out["inputCap"]
        self.assertGreater(cap["length"], 8000)
        self.assertTrue(cap["hasNote"], cap)
        self.assertEqual(cap["first"], "item 0")
        self.assertIn("(showing first 200 of", cap["last"])

    def test_output_cap_is_named(self):
        cap = self.out["outputCap"]
        self.assertEqual(cap["footer"], "(showing first 200 of 250 list items)")
        self.assertEqual(cap["lastItem"], "item 199")
        self.assertEqual(cap["lines"], 201)

    def test_diff_caps_are_named(self):
        self.assertIn("capped at 400 lines per side", self.out["diffLines"])
        self.assertIn("left has 401", self.out["diffLines"])
        changed = self.out["diffChanged"]
        self.assertEqual(changed["header"], "diff · 300 added · 300 removed · 0 unchanged")
        self.assertEqual(changed["footer"], "(showing first 200 of 600 changed lines)")
        self.assertEqual(changed["lines"], 202)

    def test_limits_are_in_the_shared_envelope(self):
        self.assertEqual(self.out["limits"],
                         {"chars": 8000, "items": 200, "diff": 400})
        text = self.out["limitsText"]
        for key in ("extractChars", "extractItems", "diffLines"):
            self.assertIn(key, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

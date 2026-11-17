#!/usr/bin/env python3
"""Step 53: deterministic thinking programs.

`toolrx/thinking.json` is the only source of the `think.*` routes; it feeds the
catalog and `tests/fixtures/thinking.json`. `toolrx/web/thinking.js` is the pure
program. These tests check the table, then drive the real modules in Node:
every mode is byte-identical on a second run, every cap is named, every finding
names its rule, and no thinking route touches the network.
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
FIXTURE = os.path.join(HERE, "fixtures", "thinking.json")
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import thinking  # noqa: E402

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
  'thinking.js', 'repair.js', 'trace.js', 'skills.js', 'templates.js', 'context.js', 'lang.js',
  'patches.js', 'engine2d.js', 'engine2d.embed.js', 'engine3d.js',
  'engine3d.embed.js', 'worldgen.js', 'worldgen.embed.js', 'rpg2.js',
  'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

const T = self.toolrxThinking;
const lim = {
  planChars: 8000, planSteps: 40, stepMs: 4000, planMs: 160000,
  contextMax: 8192, projectMax: 524288, projectFiles: 32,
  buildBytes: 65536, editBytes: 4096, readFileBytes: 8000,
  readTotalBytes: 24000, thinkChars: 4000, thinkGoals: 8, thinkRules: 12,
};
const step = (text, op, exact, status) => ({
  text, op: op || 'router', exact: exact !== false, status: status || 'pending',
});

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const out = { routes: [], pure: {}, chat: {} };

  // The fixture must resolve to the same op and topic through the real matcher.
  FIXTURE.cases.forEach(c => {
    const hit = self.toolrxSkills.match(c.text);
    out.routes.push({
      text: c.text,
      want: c.op,
      got: hit ? hit.op : null,
      topic: hit && hit.args ? hit.args.topic : null,
      wantTopic: c.args.topic,
    });
  });

  const decomposeInput = {
    text: 'build a platformer game; add a boss',
    source: 'literal',
    literal: true,
    goals: [
      { text: 'build a platformer game', op: 'build', exact: true },
      { text: 'add a boss', op: 'edit.apply', exact: true },
    ],
    limits: lim,
  };
  out.pure.decompose = T.run('decompose', decomposeInput);
  out.pure.decomposeAgain = T.run('decompose', decomposeInput);
  out.pure.decomposeCapped = T.run('decompose', Object.assign({}, decomposeInput, {
    goals: Array.from({ length: 20 }, (_, i) =>
      ({ text: 'list the files ' + i, op: 'fs.list_dir', exact: true })),
    limits: Object.assign({}, lim, { thinkGoals: 3 }),
  }));
  out.pure.decomposeTruncated = T.run('decompose', Object.assign({}, decomposeInput, {
    text: 'x'.repeat(50),
    limits: Object.assign({}, lim, { thinkChars: 10 }),
  }));
  out.pure.decomposeListing = T.run('decompose', Object.assign({}, decomposeInput, {
    text: 'cap 8192 bytes\nstored: 3068 bytes',
    source: 'context',
    literal: false,
    goals: [
      { text: 'cap 8192 bytes', op: 'router', exact: false },
      { text: 'stored: 3068 bytes', op: 'router', exact: false },
    ],
  }));
  out.pure.decomposeEmpty = T.run('decompose', { text: '', source: 'none', limits: lim });

  const reasonInput = Object.assign({}, decomposeInput, {
    goals: [
      { text: 'build a platformer game', op: 'build', exact: true },
      { text: 'list the files', op: 'fs.list_dir', exact: true },
      { text: 'read notes.txt', op: 'fs.read_file', exact: true },
      { text: 'multiply 6 and 7', op: 'math.binary', exact: true },
    ],
  });
  out.pure.reason = T.run('reason', reasonInput);
  out.pure.reasonAgain = T.run('reason', reasonInput);
  out.pure.reasonEmpty = T.run('reason', { text: '', source: 'none', limits: lim });

  const trade = text => ({
    text, source: 'literal', literal: true, limits: lim,
  });
  out.pure.tradeoff = T.run('tradeoff', trade('offline canvas vs cloud api'));
  out.pure.tradeoffAgain = T.run('tradeoff', trade('offline canvas vs cloud api'));
  out.pure.tradeoffTie = T.run('tradeoff', trade('small tool vs simple tool'));
  out.pure.tradeoffNone = T.run('tradeoff', trade('apples vs pears'));
  out.pure.tradeoffOne = T.run('tradeoff', trade('a tiny local tool'));
  out.pure.tradeoffMany = T.run('tradeoff', trade('fast vs slow vs remote'));
  out.pure.tradeoffEmpty = T.run('tradeoff', { text: '', source: 'none', limits: lim });

  const crit = (plan, extra) => T.run('critique', Object.assign({
    text: plan.steps.map(s => s.text).join('\n'),
    source: 'active plan',
    literal: false,
    plan: { steps: plan.steps },
    contextBytes: 0,
    project: null,
    limits: lim,
  }, extra || {}));
  out.pure.critiqueClean = crit({ steps: [
    step('list the files', 'fs.list_dir', true, 'done'),
    step('multiply 6 and 7', 'math.binary', true, 'done'),
  ]});
  out.pure.critiqueFailed = crit({ steps: [
    step('build a platformer game', 'build', true, 'done'),
    step('add a boss', 'edit.apply', true, 'error'),
    step('list the files', 'fs.list_dir', true, 'pending'),
  ]});
  out.pure.critiqueMany = crit({ steps: [
    step('list the files', 'fs.list_dir', true, 'done'),
    step('list the files', 'fs.list_dir', true, 'pending'),
    step('frobnicate the widget', 'router', false, 'pending'),
  ]});
  out.pure.critiqueOver = crit({ steps: Array.from({ length: 45 }, (_, i) =>
    step('read notes ' + i + '.txt', 'fs.read_file', true, 'pending')) });
  out.pure.critiqueProject = crit({ steps: [
    step('build a platformer game', 'build', true, 'pending'),
  ] }, { project: { slug: 'p', kind: 'platformer', files: ['a'], bytes: 500000 } });
  out.pure.critiqueContext = crit({ steps: [
    step('list the files', 'fs.list_dir', true, 'pending'),
  ] }, { contextBytes: 9000 });
  out.pure.critiqueRules = crit({ steps: Array.from({ length: 45 }, (_, i) =>
    step('read notes ' + i + '.txt', 'fs.read_file', true, 'pending')) },
    { limits: Object.assign({}, lim, { thinkRules: 4 }) });
  out.pure.critiqueEmpty = T.run('critique', {
    text: '', source: 'none', plan: { steps: [] }, limits: lim,
  });
  out.pure.critiqueAgain = crit({ steps: [
    step('build a platformer game', 'build', true, 'done'),
    step('add a boss', 'edit.apply', true, 'error'),
  ] });

  // The chat path resolves sources and runs the real handlers.
  const ask = async q => (await self.toolrxWeb.prompt(q)).map(r => ({
    step: r.step, text: r.text, via: r.via || '', error: !!r.error,
  }));
  const fetchBefore = fetches;
  self.toolrxWeb.reset();
  out.chat.empty = (await ask('think'))[0];
  out.chat.emptyReason = (await ask('reason'))[0];
  out.chat.emptyTradeoff = (await ask('pros and cons of'))[0];
  out.chat.emptyCritique = (await ask('critique'))[0];
  out.chat.decompose = (await ask('think about build a platformer game'))[0];
  out.chat.decomposeAgain = (await ask('think about build a platformer game'))[0];
  out.chat.reason = (await ask('reason step by step about build a platformer game'))[0];
  out.chat.tradeoff = (await ask('analyze the trade-offs of offline canvas vs cloud api'))[0];
  out.chat.fetches = fetches - fetchBefore;

  await ask('write notes.txt with hello world');
  out.chat.file = (await ask('think about notes.txt'))[0];

  self.toolrxWeb.reset();
  await ask('build a platformer game');
  out.chat.context = (await ask('think about the context'))[0];
  out.chat.previous = (await ask('reason about the previous result'))[0];
  await ask('add a boss');
  out.chat.critique = (await ask('critique this plan'))[0];

  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is not installed")
class ThinkingTest(unittest.TestCase):
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
        self.assertEqual(current, thinking.fixture(),
                         "thinking fixture drifted; run toolrx/thinking.py --write")

    def test_fixture_covers_four_modes(self):
        with open(FIXTURE, encoding="utf-8") as fh:
            doc = json.load(fh)
        self.assertEqual(sorted(doc["modes"]), ["critique", "decompose",
                                                "reason", "tradeoff"])
        for mode, count in doc["modes"].items():
            self.assertGreaterEqual(count, 4, mode)
        texts = [c["text"] for c in doc["cases"]]
        self.assertEqual(len(texts), len(set(texts)), "duplicate thinking route")

    def test_every_route_resolves_to_its_intent(self):
        for case in self.out["routes"]:
            self.assertEqual(case["got"], case["want"], case)
            self.assertEqual(case["topic"], case["wantTopic"], case)

    # -------------------------------------------------------------- pure ---
    def test_decompose_is_byte_identical_and_rule_tagged(self):
        first = self.out["pure"]["decompose"]
        self.assertEqual(first, self.out["pure"]["decomposeAgain"])
        self.assertIn("think · decompose · source literal", first)
        self.assertIn("goals (2 shown of 2): · r.split", first)
        self.assertIn("1. build a platformer game · exact build · r.route-exact", first)
        self.assertIn("order: 1 → 2 · request order · r.order", first)
        self.assertIn("next: build a platformer game · r.next-first", first)
        for line in first.splitlines()[1:]:
            self.assertRegex(line, r"r\.[a-z-]+|→|^  \d+\.|^goals|^order|^checks|^next|^rules")

    def test_decompose_names_every_cap(self):
        capped = self.out["pure"]["decomposeCapped"]
        self.assertIn("goals (3 shown of 20)", capped)
        self.assertIn("17 more goal(s) counted but not listed · r.goal-cap", capped)
        truncated = self.out["pure"]["decomposeTruncated"]
        self.assertIn("input truncated to 10 characters of 50 · r.input-cap",
                      truncated)

    def test_a_listing_is_not_treated_as_a_request(self):
        listing = self.out["pure"]["decomposeListing"]
        self.assertIn("this source is a listing, not a request · r.route-router",
                      listing)

    def test_reason_walks_each_step_with_its_own_check(self):
        text = self.out["pure"]["reason"]
        self.assertEqual(text, self.out["pure"]["reasonAgain"])
        self.assertIn('step 1 · "build a platformer game"', text)
        self.assertIn("check: writes about 65,536 bytes · project 0/524,288 bytes · r.build-cost", text)
        self.assertIn("check: reads up to 8,000 bytes · all reads 24,000 bytes · r.read-cost", text)
        self.assertIn("check: exact arithmetic · no project write · r.math-cost", text)
        self.assertIn("conclusion: 4 step(s) fit every checked limit", text)

    def test_tradeoff_only_asserts_matched_criteria(self):
        text = self.out["pure"]["tradeoff"]
        self.assertEqual(text, self.out["pure"]["tradeoffAgain"])
        self.assertIn("criteria (1 matched of 4):", text)
        self.assertIn("offline · A better · B worse · r.offline", text)
        self.assertIn('recommendation: "offline canvas"', text)
        self.assertNotIn("speed ·", text)

    def test_tradeoff_ties_and_refusals_are_explicit(self):
        tie = self.out["pure"]["tradeoffTie"]
        self.assertIn("tiebreak · r.first-listed", tie)
        none = self.out["pure"]["tradeoffNone"]
        self.assertIn("recommendation: none", none)
        self.assertIn("r.no-match", none)
        one = self.out["pure"]["tradeoffOne"]
        self.assertIn("one option is not a trade-off", one)
        many = self.out["pure"]["tradeoffMany"]
        self.assertIn("using the first two of 3", many)

    def test_critique_passes_a_clean_plan(self):
        text = self.out["pure"]["critiqueClean"]
        self.assertIn("findings (0):", text)
        self.assertIn("repair: none · r.repair-none", text)

    def test_critique_repairs_a_failed_step_first(self):
        text = self.out["pure"]["critiqueFailed"]
        self.assertIn("fail failed steps · \"add a boss\" · r.failed-step", text)
        self.assertIn('repair: rerun only "add a boss"', text)
        self.assertIn("· r.repair-failed", text)
        self.assertIn("3 step(s) · 1 done · 1 error · 1 pending", text)

    def test_critique_finds_duplicates_and_unknown_routes(self):
        text = self.out["pure"]["critiqueMany"]
        self.assertIn("fail repeated steps", text)
        self.assertIn("· r.duplicate", text)
        self.assertIn("repair: remove the repeated step · r.repair-duplicate", text)

    def test_critique_names_each_over_budget(self):
        over = self.out["pure"]["critiqueOver"]
        self.assertIn("fail step count · 45/40 · r.steps-cap", over)
        self.assertIn("drop 5 step(s)", over)
        project = self.out["pure"]["critiqueProject"]
        self.assertIn("fail project bytes", project)
        self.assertIn("r.repair-project", project)
        context = self.out["pure"]["critiqueContext"]
        self.assertIn("fail context bytes · 9,000/8,192 · r.context-cap", context)
        self.assertIn("repair: compact context first · r.repair-context", context)

    def test_critique_obeys_think_rules(self):
        text = self.out["pure"]["critiqueRules"]
        self.assertIn("passed: 2 of 4 checks", text)
        self.assertIn("skipped: 7 check(s) beyond thinkRules", text)

    def test_empty_input_returns_one_clear_message(self):
        for mode in ("decompose", "reason", "tradeoff"):
            text = self.out["pure"][mode + "Empty"]
            self.assertIn("nothing to work on", text)
            self.assertIn("give me a topic, a file, the previous result, "
                          "the active plan, or the context", text)
        self.assertIn("nothing to critique", self.out["pure"]["critiqueEmpty"])

    # -------------------------------------------------------------- chat ---
    def test_chat_routes_reach_the_handlers(self):
        chat = self.out["chat"]
        self.assertEqual(chat["decompose"]["via"], "think.decompose")
        self.assertEqual(chat["reason"]["via"], "think.reason")
        self.assertEqual(chat["tradeoff"]["via"], "think.tradeoff")
        self.assertEqual(chat["critique"]["via"], "think.critique")
        self.assertEqual(chat["decompose"]["text"], chat["decomposeAgain"]["text"])

    def test_chat_resolves_each_source(self):
        chat = self.out["chat"]
        self.assertIn("source file notes.txt", chat["file"]["text"])
        self.assertIn("source context", chat["context"]["text"])
        self.assertIn("source previous result", chat["previous"]["text"])
        self.assertIn("source last run", chat["critique"]["text"])
        self.assertIn('"add a boss"', chat["critique"]["text"])

    def test_chat_empty_routes_are_clear(self):
        chat = self.out["chat"]
        for key in ("empty", "emptyReason", "emptyTradeoff"):
            self.assertIn("nothing to work on", chat[key]["text"])
        self.assertIn("nothing to critique", chat["emptyCritique"]["text"])

    def test_thinking_routes_never_touch_the_network(self):
        self.assertEqual(self.out["chat"]["fetches"], 0,
                         "a thinking route made a network call")
        with open(os.path.join(WEB, "thinking.js"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotRegex(source, r"\bfetch\s*\(")
        self.assertNotIn("import(", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

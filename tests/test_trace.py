#!/usr/bin/env python3
"""Step 55: reasoning traces in context and observability.

A thinking or repair pass stores one bounded `trace/last` entry beside the
plan it examined. These tests cover the pure record, the decision and rule
readers, storage and reload, the last-run summary, the context snapshot,
trace-first compaction, the orphan-trace invariant, and the no-network
promise.
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

JS = r"""
const fs = require('fs');
const path = require('path');
const WEB = process.argv[1];
const COMMANDS = process.argv[2];
const MODEL = process.argv[3];

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
  'thinking.js', 'repair.js', 'trace.js', 'skills.js', 'templates.js',
  'context.js', 'lang.js', 'patches.js', 'engine2d.js', 'engine2d.embed.js',
  'engine3d.js', 'engine3d.embed.js', 'worldgen.js', 'worldgen.embed.js',
  'rpg2.js', 'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const C = self.toolrxContext;
  const T = self.toolrxTrace;
  const out = { pure: {}, chat: {}, limits: {} };
  out.limits.traceBytes = self.toolrxLimits.traceBytes;

  const big = T.record({
    via: 'think.reason', text: 'x'.repeat(5000), decision: 'reason',
    rule: 'r.split', source: 'literal',
  }, { maxText: 2000, maxBytes: 2048 });
  out.pure.big = big;
  out.pure.tooBig = T.record({
    via: 'x', text: 'y', planSteps: Array(40).fill('z'.repeat(240)),
  }, { maxText: 10, maxBytes: 64 });
  out.pure.decisionCritique = T.decisionOf(
    'think.critique',
    'x\nrepair: rerun only "a" · r.repair-failed\ny');
  out.pure.ruleCritique = T.decisionRuleOf(
    'think.critique',
    'x\nrepair: rerun only "a" · r.repair-failed\ny');
  out.pure.decisionTradeoff = T.decisionOf(
    'think.tradeoff', 'recommendation: offline canvas · r.offline');
  out.pure.decisionDecompose = T.decisionOf(
    'think.decompose', 'goals (1 shown of 2)');
  out.pure.matchesNone = T.matches(T.withPlan({ planSha: '' }, ''), 'abc');
  out.pure.matchesSame = T.matches({ planSha: 'abc' }, 'abc');
  out.pure.matchesDiff = T.matches({ planSha: 'abc' }, 'def');
  out.pure.text = T.text(big);

  const ask = async q => (await self.toolrxWeb.prompt(q)).map(r => ({
    step: r.step, text: r.text, via: r.via || '', error: !!r.error,
  }));
  const fetchBefore = fetches;

  // Build, fail, then critique the real plan.
  self.toolrxWeb.reset();
  out.chat.initial = await ask('build a platformer game; divide 4 by 0; add a theme toggle');
  out.chat.critique = (await ask('critique this plan'))[0];
  const traceRaw = C.get('platformer', 'trace', 'last');
  out.chat.trace = traceRaw ? JSON.parse(traceRaw) : null;
  out.chat.planRaw = C.get('platformer', 'plan', 'last');
  out.chat.planSha = C.fingerprint(out.chat.planRaw);
  out.chat.lastRun = self.toolrxWeb.lastRun();
  out.chat.snapshot = C.snapshot('platformer').text;
  out.chat.show = C.show('platformer');

  // Reload: the trace is read back from raw localStorage only.
  const rawKey = 'toolrx.context.v1.platformer';
  const saved = store[rawKey];
  delete store[rawKey];
  store[rawKey] = saved;
  out.chat.reloaded = C.get('platformer', 'trace', 'last');

  // Repair stores its own trace for the same plan.
  out.chat.repair = (await ask('repair this plan'))[0];
  out.chat.repairTrace = JSON.parse(C.get('platformer', 'trace', 'last'));
  out.chat.repairLastRun = self.toolrxWeb.lastRun();

  // A low cap drops the trace first and keeps the plan.
  store['toolrx.context.cap'] = '900';
  out.chat.lowCompact = C.compact('platformer', {});
  out.chat.lowTrace = C.get('platformer', 'trace', 'last');
  out.chat.lowPlan = C.get('platformer', 'plan', 'last');
  delete store['toolrx.context.cap'];

  // Orphan: remove the plan, then compact. The trace must not survive alone.
  self.toolrxWeb.reset();
  await ask('build a platformer game; divide 4 by 0; add a theme toggle');
  await ask('critique this plan');
  out.chat.orphanBefore = !!C.get('platformer', 'trace', 'last');
  C.remove('platformer', 'plan', 'last');
  out.chat.orphanPlanGone = !C.get('platformer', 'plan', 'last');
  out.chat.orphanTraceStill = !!C.get('platformer', 'trace', 'last');
  out.chat.orphanCompact = C.compact('platformer', {});
  out.chat.orphanAfter = !!C.get('platformer', 'trace', 'last');
  out.chat.orphanNotes = C.notes('platformer');

  // With a healthy plan, an ordinary compaction leaves the trace and plan.
  self.toolrxWeb.reset();
  await ask('build a platformer game; divide 4 by 0; add a theme toggle');
  await ask('critique this plan');
  out.chat.normalCompact = C.compact('platformer', {});
  out.chat.normalTrace = !!C.get('platformer', 'trace', 'last');
  out.chat.normalPlan = !!C.get('platformer', 'plan', 'last');

  // A literal decomposition has no stored plan and stays independent.
  self.toolrxWeb.reset();
  out.chat.decompose = (await ask('think about build a platformer game'))[0];
  out.chat.decomposeTrace = JSON.parse(C.get('scratch', 'trace', 'last'));

  out.chat.fetches = fetches - fetchBefore;
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is not installed")
class TraceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", JS, WEB,
             os.path.join(WEB, "commands.json"),
             os.path.join(ROOT, "toolrx", "micro_model.json")],
            capture_output=True, text=True, timeout=240,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-4000:])
        cls.out = json.loads(proc.stdout)

    # -------------------------------------------------------------- limits ---
    def test_trace_bytes_is_a_declared_limit(self):
        self.assertEqual(self.out["limits"]["traceBytes"], 2048)
        data = envelope.load()
        self.assertEqual(data["traceBytes"], 2048)

    # ---------------------------------------------------------------- pure ---
    def test_record_is_bounded_and_names_the_trim(self):
        doc = self.out["pure"]["big"]
        self.assertEqual(doc["kind"], "trace")
        self.assertEqual(doc["key"], "last")
        self.assertTrue(doc["trimmed"])
        self.assertLessEqual(
            len(json.dumps(doc, separators=(",", ":")).encode("utf-8")), 2048)
        self.assertIn("… [trimmed]", doc["text"])
        self.assertIsNone(self.out["pure"]["tooBig"])

    def test_decision_and_rule_are_read_from_the_output(self):
        self.assertEqual(self.out["pure"]["decisionCritique"], 'rerun only "a"')
        self.assertEqual(self.out["pure"]["ruleCritique"], "r.repair-failed")
        self.assertEqual(self.out["pure"]["decisionTradeoff"], "offline canvas")
        self.assertEqual(self.out["pure"]["decisionDecompose"],
                         "decompose 2 goal(s)")

    def test_plan_matching_is_explicit(self):
        self.assertTrue(self.out["pure"]["matchesNone"])
        self.assertTrue(self.out["pure"]["matchesSame"])
        self.assertFalse(self.out["pure"]["matchesDiff"])

    def test_trace_text_names_the_rule_and_the_cap(self):
        text = self.out["pure"]["text"]
        self.assertIn("trace · think.reason · reason · r.split", text)
        self.assertIn("r.trace-decision", text)
        self.assertIn("trimmed", text)
        self.assertIn("r.trace-trim", text)

    # ---------------------------------------------------------------- chat ---
    def test_critique_stores_a_trace_tied_to_the_plan(self):
        chat = self.out["chat"]
        self.assertEqual(chat["critique"]["via"], "think.critique")
        trace = chat["trace"]
        self.assertIsNotNone(trace)
        self.assertEqual(trace["via"], "think.critique")
        self.assertEqual(trace["rule"], "r.repair-failed")
        self.assertIn("rerun only", trace["decision"])
        self.assertEqual(trace["source"], "active plan")
        self.assertEqual(trace["planSha"], chat["planSha"])
        self.assertEqual(trace["planSteps"],
                         ["build a platformer game", "divide 4 by 0",
                          "add a theme toggle"])

    def test_last_run_names_the_trace(self):
        trace = self.out["chat"]["lastRun"]["trace"]
        self.assertEqual(trace["via"], "think.critique")
        self.assertEqual(trace["rule"], "r.repair-failed")
        self.assertIn("rerun only", trace["decision"])
        self.assertEqual(trace["planSha"], self.out["chat"]["planSha"])

    def test_snapshot_and_listing_show_the_trace(self):
        snap = self.out["chat"]["snapshot"]
        self.assertIn("trace: think.critique", snap)
        self.assertIn("r.repair-failed", snap)
        self.assertIn("plan " + self.out["chat"]["planSha"][:12], snap)
        show = self.out["chat"]["show"]
        self.assertIn("last trace", show)
        self.assertIn("r.repair-failed", show)

    def test_trace_survives_a_reload(self):
        reloaded = self.out["chat"]["reloaded"]
        self.assertTrue(reloaded)
        doc = json.loads(reloaded)
        self.assertEqual(doc["rule"], "r.repair-failed")
        self.assertEqual(doc["planSha"], self.out["chat"]["planSha"])

    def test_repair_stores_its_own_trace(self):
        trace = self.out["chat"]["repairTrace"]
        self.assertEqual(trace["via"], "repair.plan")
        self.assertEqual(trace["decision"], "revise")
        self.assertEqual(trace["rule"], "r.repair-math")
        self.assertEqual(trace["planSha"], self.out["chat"]["planSha"])
        self.assertEqual(self.out["chat"]["repairLastRun"]["trace"]["rule"],
                         "r.repair-math")

    def test_trace_is_dropped_before_the_plan(self):
        chat = self.out["chat"]
        actions = chat["lowCompact"]["actions"]
        self.assertTrue(actions)
        self.assertEqual(actions[0]["kind"], "trace")
        self.assertEqual(actions[0]["why"], "dropped")
        self.assertFalse(chat["lowTrace"])
        self.assertTrue(chat["lowPlan"])

    def test_an_orphan_trace_is_dropped_with_a_note(self):
        chat = self.out["chat"]
        self.assertTrue(chat["orphanBefore"])
        self.assertTrue(chat["orphanPlanGone"])
        self.assertTrue(chat["orphanTraceStill"])
        self.assertFalse(chat["orphanAfter"])
        kinds = [(a["kind"], a["key"], a["why"])
                 for a in chat["orphanCompact"]["actions"]]
        self.assertIn(("trace", "last", "dropped"), kinds)
        self.assertTrue(any(n["kind"] == "trace" and n["why"] == "dropped"
                            for n in chat["orphanNotes"]))

    def test_compaction_keeps_a_trace_beside_its_plan(self):
        chat = self.out["chat"]
        self.assertEqual(chat["normalCompact"]["actions"], [])
        self.assertTrue(chat["normalTrace"])
        self.assertTrue(chat["normalPlan"])

    def test_a_literal_trace_has_no_plan(self):
        trace = self.out["chat"]["decomposeTrace"]
        self.assertEqual(trace["via"], "think.decompose")
        self.assertEqual(trace["planSha"], "")
        self.assertEqual(trace["planSteps"], ["build a platformer game"])
        self.assertIn("decompose", trace["decision"])

    def test_trace_never_touches_the_network(self):
        self.assertEqual(self.out["chat"]["fetches"], 0,
                         "a trace route made a network call")
        with open(os.path.join(WEB, "trace.js"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotRegex(source, r"\bfetch\s*\(")
        self.assertNotIn("import(", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Contract tests for the conversational glue layer (step 47).

`toolrx/conversation.py` is the only source of the short conversational routes.
It feeds the generated catalog and `tests/fixtures/conversation.json`. The
previous-turn behaviour lives in `web/skills.js`; the Node harness below drives
the real code and checks that a confirmation applies a staged action exactly
once, an ambiguous confirmation changes nothing, and the same transcript
produces the same replies.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COMMANDS = os.path.join(ROOT, "toolrx", "web", "commands.json")
FIXTURE = os.path.join(HERE, "fixtures", "conversation.json")
CONVERSATION = os.path.join(ROOT, "toolrx", "conversation.py")
NODE = shutil.which("node")

MIN_CASES = 40
MIN_KINDS = 7


def _normalize(q):
    q = re.sub(r"\s+", " ", q).strip()
    q = re.sub(r"[?!]+$", "", q)
    return re.sub(r"\.$", "", q)


class ConversationFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(COMMANDS, encoding="utf-8") as f:
            cls.catalog = json.load(f)
        with open(FIXTURE, encoding="utf-8") as f:
            cls.fixture = json.load(f)
        cls.commands = cls.catalog["commands"]
        cls.compiled = [(c, re.compile(c["re"], re.I)) for c in cls.commands]

    def first(self, query):
        q = _normalize(query)
        for command, rx in self.compiled:
            if rx.match(q):
                return command
        return None

    def args_for(self, command, query):
        m = re.match(command["re"], _normalize(query), re.I)
        self.assertIsNotNone(m, query)

        def fill(value):
            if not isinstance(value, str):
                return value
            if re.fullmatch(r"\$\d+", value):
                return m.group(int(value[1:])) or ""
            return re.sub(r"\$(\d+)",
                          lambda hit: m.group(int(hit.group(1))) or "", value)
        return {k: fill(v) for k, v in command["args"].items()}

    def test_fixture_is_current(self):
        proc = subprocess.run([sys.executable, CONVERSATION, "--check"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        self.assertIn("current", proc.stdout)

    def test_fixture_covers_the_short_turn_kinds(self):
        cases = self.fixture["cases"]
        self.assertEqual(self.fixture["version"], 1)
        self.assertEqual(self.fixture["count"], len(cases))
        self.assertGreaterEqual(len(cases), MIN_CASES)
        kinds = {}
        for case in cases:
            kinds[case["kind"]] = kinds.get(case["kind"], 0) + 1
        self.assertGreaterEqual(len(kinds), MIN_KINDS)
        self.assertEqual(self.fixture["kinds"], dict(sorted(kinds.items())))
        self.assertTrue(all(n >= 3 for n in kinds.values()), kinds)

    def test_every_case_resolves_to_its_own_exact_route(self):
        failures = []
        for case in self.fixture["cases"]:
            hit = self.first(case["text"])
            if hit is None:
                failures.append((case["text"], "no match"))
                continue
            if not hit["id"].startswith("conversation."):
                failures.append((case["text"], "shadowed by " + hit["id"]))
                continue
            if hit["op"] != case["op"]:
                failures.append((case["text"], "op %s != %s"
                                 % (hit["op"], case["op"])))
                continue
            args = self.args_for(hit, case["text"])
            if args != case["args"]:
                failures.append((case["text"], "args %r != %r"
                                 % (args, case["args"])))
        self.assertFalse(failures, failures[:10])

    def test_catalog_matches_the_table(self):
        sys.path.insert(0, os.path.join(ROOT, "toolrx"))
        try:
            import conversation  # noqa: WPS433 (local module under test)
        finally:
            sys.path.pop(0)
        table = list(conversation.entries())
        self.assertEqual(len(table), len(self.fixture["cases"]))
        by_id = {c["id"]: c for c in self.commands
                 if c["id"].startswith("conversation.")}
        self.assertEqual(set(by_id), {e["id"] for e in table})
        for entry in table:
            shipped = by_id[entry["id"]]
            self.assertEqual(shipped["op"], entry["op"])
            self.assertEqual(shipped["re"], entry["re"])
            self.assertEqual(shipped["args"], entry["args"])
            self.assertEqual(shipped["c"], entry["c"])


@unittest.skipUnless(NODE, "node is not installed")
class ConversationBehaviourTest(unittest.TestCase):
    JS = r"""
const fs = require('fs');
const path = require('path');
const WEB = process.argv[1];
global.self = global;
global.fetch = () => Promise.resolve({
  ok: true,
  json: () => Promise.resolve(JSON.parse(fs.readFileSync(path.join(WEB, 'commands.json'), 'utf8'))),
});
const store = {};
global.localStorage = {
  getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.CustomEvent = class { constructor(type, opts) { this.type = type; this.detail = opts && opts.detail; } };
global.dispatchEvent = () => {};
global.toolrxRouter = { load: () => ({}), route: () => ({ tool: 'none', args: {}, confidence: 0 }) };
eval(fs.readFileSync(path.join(WEB, 'limits.js'), 'utf8'));
eval(fs.readFileSync(path.join(WEB, 'skills.js'), 'utf8'));

(async () => {
  await self.toolrxSkills.init('commands.json');
  const make = () => {
    const memory = {};
    const files = {};
    const state = { builds: 0, lastKind: '' };
    const ctx = {
      prev: '', fs: {
        exists: p => p in files, read: p => files[p],
        write: (p, c) => { files[p] = String(c); return 'wrote ' + p; },
        list: () => Object.keys(files).join('\n'),
      },
      preview: () => '', theme: () => true,
      build: (kind, desc) => {
        state.builds++;
        state.lastKind = kind;
        return 'built ' + kind + (desc ? ' with ' + desc : '')
          + ' · build #' + state.builds;
      },
      project: { new: n => 'created ' + n, list: () => 'proj-a',
                 open: s => 'opened ' + s, rename: (s, n) => 'renamed',
                 remove: s => 'deleted ' + s, files: () => 'index.html' },
      chat: (who, text) => text, history: () => [],
      memory: {
        get: k => memory[k],
        set: (k, v) => { memory[k] = v; return v; },
        remove: k => { delete memory[k]; },
        clear: () => { Object.keys(memory).forEach(k => delete memory[k]); },
        keys: () => Object.keys(memory),
      },
      web: {},
      fallback: async step => ({ text: 'fallback:' + step, error: false,
                                 via: 'router.test' }),
    };
    const run = async q => {
      const res = await self.toolrxSkills.runPrompt(q, ctx);
      return res.map(r => ({ step: r.step, text: r.text, error: !!r.error,
                             via: r.via || '', confirmed: r.confirmed || '',
                             revised: r.revised || '' }));
    };
    return { memory, state, ctx, run };
  };

  const transcript = [
    'build a shooter',
    'no, i meant a platformer',
    'yes',
    'yes',
    'no',
    'add 12 and 30',
    'no, i meant 13 plus 30',
    "that's wrong",
    'show conversation',
    'clear conversation',
    'show conversation',
    'actually zzz nonsense',
    'yes',
    'no',
    'got it',
  ];
  const runAll = async () => {
    const env = make();
    const rows = [];
    for (const q of transcript) {
      rows.push({ q: q, r: await env.run(q), builds: env.state.builds,
                  lastKind: env.state.lastKind });
    }
    return { rows: rows, state: env.state, memory: env.memory,
             limits: self.toolrxSkills.limits };
  };
  const first = await runAll();
  const second = await runAll();

  const capEnv = make();
  for (let i = 0; i < 20; i++) {
    await capEnv.run('make a note that ' + 'x'.repeat(900) + ' ' + i);
  }
  const capShow = await capEnv.run('show conversation');
  const cap = {
    show: capShow[0].text,
    stored: capEnv.memory.conversation,
    limits: self.toolrxSkills.limits,
    bytes: JSON.stringify(capEnv.memory.conversation).length,
  };

  // Inspecting must not discard a staged action, and a meta turn must not
  // replace the last real action that a repair refers to.
  const metaEnv = make();
  const meta = { steps: [] };
  meta.steps.push(await metaEnv.run('build a shooter'));
  meta.steps.push(await metaEnv.run('no, i meant a platformer'));
  meta.steps.push(await metaEnv.run('show conversation'));
  meta.steps.push(await metaEnv.run('yes'));
  meta.builds = metaEnv.state.builds;
  meta.lastKind = metaEnv.state.lastKind;

  const repairEnv = make();
  meta.repair = [];
  meta.repair.push(await repairEnv.run('add 12 and 30'));
  meta.repair.push(await repairEnv.run('got it'));
  meta.repair.push(await repairEnv.run("that's wrong"));

  console.log(JSON.stringify({ first: first, second: second, cap: cap,
                               meta: meta }));
})().catch(e => { console.error(e.stack || e); process.exit(1); });
"""

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", cls.JS, os.path.join(ROOT, "toolrx", "web")],
            capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-4000:])
        cls.out = json.loads(proc.stdout)

    def row(self, transcript, index):
        return transcript["rows"][index]

    def test_correction_stages_a_build_and_yes_runs_it_once(self):
        t = self.out["first"]
        self.assertEqual(self.row(t, 0)["r"][0]["via"], "build")
        self.assertEqual(self.row(t, 0)["builds"], 1)
        correction = self.row(t, 1)
        self.assertEqual(correction["r"][0]["via"], "conversation.correct")
        self.assertIn("build a platformer", correction["r"][0]["text"])
        self.assertIn("say yes", correction["r"][0]["text"].lower())
        self.assertEqual(correction["builds"], 1, "a correction must not build yet")
        yes = self.row(t, 2)
        self.assertEqual(yes["r"][0]["via"], "build")
        self.assertEqual(yes["r"][0]["confirmed"], "build a platformer")
        self.assertEqual(yes["builds"], 2)
        self.assertEqual(yes["lastKind"], "platformer")

    def test_a_second_confirmation_changes_nothing(self):
        t = self.out["first"]
        second = self.row(t, 3)
        self.assertEqual(second["r"][0]["via"], "conversation.confirm")
        self.assertIn("nothing is pending", second["r"][0]["text"].lower())
        self.assertEqual(second["builds"], 2, "a confirmation must never re-run")
        reject = self.row(t, 4)
        self.assertEqual(reject["r"][0]["via"], "conversation.reject")
        self.assertIn("nothing to cancel", reject["r"][0]["text"].lower())
        self.assertEqual(reject["builds"], 2)

    def test_math_correction_revises_the_last_action_immediately(self):
        t = self.out["first"]
        first = self.row(t, 5)
        self.assertEqual(first["r"][0]["text"], "42")
        revised = self.row(t, 6)
        self.assertEqual(revised["r"][0]["via"], "math.binary")
        self.assertEqual(revised["r"][0]["text"], "43")
        self.assertEqual(revised["r"][0]["revised"], "no, i meant 13 plus 30")

    def test_repair_is_bounded_and_does_not_rerun(self):
        t = self.out["first"]
        repair = self.row(t, 7)
        self.assertEqual(repair["r"][0]["via"], "conversation.repair")
        self.assertIn("last action", repair["r"][0]["text"].lower())
        self.assertIn("nothing was re-run", repair["r"][0]["text"].lower())
        self.assertEqual(repair["builds"], 2)

    def test_conversation_is_inspectable_and_clearable(self):
        t = self.out["first"]
        show = self.row(t, 8)["r"][0]
        self.assertEqual(show["via"], "conversation.show")
        self.assertIn("cap 12 turns · 4096 bytes", show["text"])
        self.assertIn("pending: none", show["text"])
        self.assertIn("1. you: build a shooter", show["text"])
        cleared = self.row(t, 9)["r"][0]
        self.assertEqual(cleared["via"], "conversation.clear")
        self.assertIn("memory facts, notes, projects, and context are untouched",
                      cleared["text"])
        after = self.row(t, 10)["r"][0]
        self.assertIn("1. you: clear conversation", after["text"])

    def test_ambiguous_correction_and_confirmation_change_nothing(self):
        t = self.out["first"]
        ambiguous = self.row(t, 11)
        self.assertEqual(ambiguous["r"][0]["via"], "conversation.correct")
        self.assertIn("couldn't map", ambiguous["r"][0]["text"].lower())
        self.assertIn("nothing was changed", ambiguous["r"][0]["text"].lower())
        self.assertEqual(ambiguous["builds"], 2)
        confirm = self.row(t, 12)
        self.assertEqual(confirm["r"][0]["via"], "conversation.confirm")
        self.assertIn("nothing has been applied yet",
                      confirm["r"][0]["text"].lower())
        self.assertEqual(confirm["builds"], 2)
        reject = self.row(t, 13)
        self.assertEqual(reject["r"][0]["via"], "conversation.reject")
        self.assertIn("cancelled", reject["r"][0]["text"].lower())
        self.assertEqual(reject["builds"], 2)

    def test_acknowledgement_is_an_exact_chat_route(self):
        ack = self.row(self.out["first"], 14)["r"][0]
        self.assertEqual(ack["via"], "chat")
        self.assertTrue(ack["text"].strip())

    def test_inspection_preserves_a_staged_action(self):
        meta = self.out["meta"]
        show = meta["steps"][2][0]
        self.assertEqual(show["via"], "conversation.show")
        self.assertIn("pending: build a platformer", show["text"])
        self.assertIn("say yes", show["text"].lower())
        yes = meta["steps"][3][0]
        self.assertEqual(yes["via"], "build")
        self.assertEqual(yes["confirmed"], "build a platformer")
        self.assertEqual(meta["builds"], 2)
        self.assertEqual(meta["lastKind"], "platformer")

    def test_repair_names_the_last_real_action_after_a_meta_turn(self):
        meta = self.out["meta"]
        repair = meta["repair"][2][0]
        self.assertEqual(repair["via"], "conversation.repair")
        self.assertIn('The last action was "add 12 and 30"', repair["text"])
        self.assertNotIn("got it", repair["text"])

    def test_the_same_transcript_produces_the_same_replies(self):
        self.assertEqual(self.out["first"]["rows"], self.out["second"]["rows"])
        self.assertEqual(self.out["first"]["memory"], self.out["second"]["memory"])

    def test_conversation_cap_is_explicit_and_enforced(self):
        cap = self.out["cap"]
        limits = cap["limits"]
        self.assertEqual(limits["single"], 2000)
        self.assertIn("cap 12 turns · 4096 bytes", cap["show"])
        self.assertLessEqual(len(cap["stored"]["turns"]), 12)
        self.assertLessEqual(cap["bytes"], 4096)
        self.assertGreater(cap["stored"]["dropped"], 0)
        self.assertIn("dropped " + str(cap["stored"]["dropped"]), cap["show"])


if __name__ == "__main__":
    unittest.main()

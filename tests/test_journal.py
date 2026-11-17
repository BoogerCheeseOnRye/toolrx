#!/usr/bin/env python3
"""Step 56: per-project decision journal and multi-turn memory.

`toolrx/journal.json` is the only source of the `journal.*` routes; it feeds the
catalog and `tests/fixtures/journal.json`. `toolrx/web/journal.js` is the pure,
bounded store. These tests cover the pure add/query/text/evict path, the real
build -> art-style question, plan-variant and repair rejections, preferences,
the bundle round-trip, project isolation, and the no-network promise.
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
FIXTURE = os.path.join(HERE, "fixtures", "journal.json")
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import envelope  # noqa: E402
import journal  # noqa: E402

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

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const fetchBefore = fetches;
  const J = self.toolrxJournal;
  const out = { limits: {}, routes: [], pure: {}, chat: {}, bundle: {},
                isolation: {} };
  out.limits.entries = self.toolrxLimits.journalEntries;
  out.limits.bytes = self.toolrxLimits.journalBytes;
  out.limits.text = self.toolrxLimits.journalText;

  FIXTURE.cases.forEach(c => {
    const hit = self.toolrxSkills.match(c.text);
    out.routes.push({ text: c.text, want: c.op, got: hit ? hit.op : null });
  });

  const ask = async q => {
    const list = await self.toolrxWeb.prompt(q);
    const r = list[list.length - 1] || {};
    return {
      step: r.step, text: String(r.text || ''), via: r.via || '',
      error: !!r.error, variant: r.variant || null,
    };
  };

  // ------------------------------------------------------------- pure ---
  out.pure.add = J.add('alpha', {
    kind: 'decision', topic: 'art style',
    text: 'pixel art, 2D side-scroller', source: 'build', n: 1,
  });
  out.pure.dup = J.add('alpha', {
    kind: 'decision', topic: 'art style',
    text: 'pixel art, 2D side-scroller', source: 'build', n: 2,
  });
  out.pure.reject = J.add('alpha', {
    kind: 'rejection', topic: 'plan budget',
    text: 'dropped 2 steps for steps', source: 'plan.variant',
  });
  out.pure.pref = J.add('alpha', {
    kind: 'preference', topic: 'favorite color', text: 'teal',
    source: 'memory.remember',
  });
  out.pure.invalid = J.add('alpha', {
    kind: 'nonsense', topic: 'x', text: 'y', source: 'test',
  });
  out.pure.text = J.text('alpha');
  out.pure.answer = J.answer('alpha', 'the art style');
  out.pure.miss = J.answer('alpha', 'the colour scheme');
  out.pure.empty = J.answer('empty-project', 'anything');
  out.pure.exported = J.exportFor('alpha');
  out.pure.imported = J.importFor('beta', out.pure.exported);
  out.pure.betaText = J.text('beta');
  out.pure.alphaCount = J.read('alpha').entries.length;
  out.pure.betaCount = J.read('beta').entries.length;
  for (let i = 0; i < 30; i++) {
    J.add('gamma', {
      kind: 'decision', topic: 'topic ' + i,
      text: 'decision number ' + i, source: 'test',
    });
  }
  const gamma = J.read('gamma');
  out.pure.evict = {
    entries: gamma.entries.length,
    dropped: gamma.dropped,
    notes: gamma.notes.length,
    text: J.text('gamma'),
  };
  out.pure.cleared = J.clear('beta');
  out.pure.betaAfterClear = J.read('beta').entries.length;

  // ------------------------------------------------------------- chat ---
  self.toolrxWeb.reset();
  out.chat.build = await ask('build a platformer game');
  out.chat.query = await ask('what did we decide about the art style?');
  out.chat.show = await ask('show journal');

  // A staged compacted plan records a rejection with the dropped step.
  self.toolrxWeb.reset();
  const many = Array.from({ length: 41 }, () => 'list the files').join('; ');
  out.chat.variant = await ask(many);
  out.chat.variantQuery = await ask('what did we reject about the plan budget?');

  // A preference is a journal entry too.
  out.chat.remember = await ask('remember my favorite color is teal');
  out.chat.prefQuery = await ask('what did we decide about the favorite color?');

  // A kind-gated repair refusal is a rejection.
  self.toolrxWeb.reset();
  await ask('build a platformer game; add a boss; add a theme toggle');
  out.chat.kindRepair = await ask('repair this plan');
  out.chat.kindQuery = await ask('what did we reject about the repair?');

  // ----------------------------------------------------------- bundle ---
  self.toolrxWeb.reset();
  await ask('build a platformer game');
  await ask('what did we decide about the art style?');
  const exported = await ask('export this project');
  out.bundle.export = exported;
  const bundles = JSON.parse(store['toolrx.bundles.v1'] || '{"items":{}}');
  const key = Object.keys(bundles.items)[0];
  const doc = JSON.parse(bundles.items[key].text);
  out.bundle.docJournal = doc.project.journal || [];
  self.toolrxWeb.reset();
  out.bundle.afterReset = J.read('platformer').entries.length;
  out.bundle.import = await ask('import the project from platformer.toolrx.json');
  out.bundle.afterImport = J.read('platformer').entries.length;
  out.bundle.query = await ask('what did we decide about the art style?');

  // -------------------------------------------------------- isolation ---
  self.toolrxWeb.reset();
  await ask('build a platformer game');
  const firstSlug = self.toolrxWeb.project().slug;
  await ask('build a todo app');
  const secondSlug = self.toolrxWeb.project().slug;
  out.isolation.firstSlug = firstSlug;
  out.isolation.secondSlug = secondSlug;
  out.isolation.first = J.read(firstSlug).entries.length;
  out.isolation.second = J.read(secondSlug).entries.length;
  out.isolation.firstTopics = J.topics(firstSlug);
  out.isolation.secondTopics = J.topics(secondSlug);
  out.isolation.activeQuery = await ask('what did we decide about the art style?');
  out.isolation.activeText = J.text(secondSlug);

  out.fetches = fetches - fetchBefore;
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is not installed")
class JournalTest(unittest.TestCase):
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

    # ------------------------------------------------------------ table ---
    def test_fixture_matches_the_table(self):
        doc = journal.fixture()
        with open(FIXTURE, encoding="utf-8") as fh:
            current = json.load(fh)
        self.assertEqual(current, doc)
        self.assertEqual(current["count"], len(current["cases"]))
        self.assertEqual(set(current["ops"]),
                         {"journal.show", "journal.query", "journal.clear"})

    def test_every_route_resolves_to_its_own_op(self):
        for row in self.out["routes"]:
            self.assertEqual(row["got"], row["want"], row["text"])

    # ----------------------------------------------------------- limits ---
    def test_journal_limits_are_declared(self):
        self.assertEqual(self.out["limits"]["entries"], 24)
        self.assertEqual(self.out["limits"]["bytes"], 4096)
        self.assertEqual(self.out["limits"]["text"], 240)
        data = envelope.load()
        self.assertEqual(data["journalEntries"], 24)
        self.assertEqual(data["journalBytes"], 4096)
        self.assertEqual(data["journalText"], 240)

    # ------------------------------------------------------------- pure ---
    def test_add_and_dedupe(self):
        pure = self.out["pure"]
        self.assertTrue(pure["add"]["ok"])
        self.assertFalse(pure["add"]["duplicate"])
        self.assertTrue(pure["dup"]["duplicate"])
        self.assertEqual(pure["alphaCount"], 3)
        self.assertFalse(pure["invalid"]["ok"])

    def test_text_names_the_caps_and_notes(self):
        text = self.out["pure"]["text"]
        self.assertIn("journal · 3 entries", text)
        self.assertIn("1 decision", text)
        self.assertIn("1 rejection", text)
        self.assertIn("1 preference", text)
        self.assertIn("cap 24 entries · 4096 bytes", text)
        self.assertIn("notes: none", text)

    def test_query_returns_the_matching_entry(self):
        answer = self.out["pure"]["answer"]
        self.assertIn('1 match for "the art style"', answer)
        self.assertIn("#1 decision · art style", answer)
        self.assertIn("via build", answer)
        miss = self.out["pure"]["miss"]
        self.assertIn('nothing about "the colour scheme" yet', miss)
        self.assertIn("known topics:", miss)
        self.assertIn("journal · empty", self.out["pure"]["empty"])

    def test_export_import_round_trips_and_stays_separate(self):
        pure = self.out["pure"]
        self.assertEqual(pure["alphaCount"], 3)
        self.assertEqual(pure["betaCount"], 3)
        self.assertIn("journal · 3 entries", pure["betaText"])
        self.assertTrue(pure["cleared"])
        self.assertEqual(pure["betaAfterClear"], 0)

    def test_the_entry_cap_evicts_with_a_note(self):
        evict = self.out["pure"]["evict"]
        self.assertEqual(evict["entries"], 24)
        self.assertEqual(evict["dropped"], 6)
        self.assertGreater(evict["notes"], 0)
        self.assertIn("dropped 6", evict["text"])
        self.assertIn("notes (oldest first):", evict["text"])
        self.assertIn("entry cap", evict["text"])

    # ------------------------------------------------------------- chat ---
    def test_a_build_records_an_art_style_decision(self):
        chat = self.out["chat"]
        self.assertEqual(chat["build"]["via"], "build")
        answer = chat["query"]
        self.assertEqual(answer["via"], "journal.query")
        self.assertIn("art style", answer["text"])
        self.assertIn("genre platformer", answer["text"])
        self.assertIn("seed ", answer["text"])
        self.assertIn("via build", answer["text"])
        self.assertIn("journal · 1 entry", chat["show"]["text"])
        self.assertIn("cap 24 entries", chat["show"]["text"])

    def test_a_plan_variant_records_a_rejection(self):
        chat = self.out["chat"]
        self.assertEqual(chat["variant"]["via"], "plan.variant")
        self.assertIn("plan budget", chat["variantQuery"]["text"])
        self.assertIn("rejection", chat["variantQuery"]["text"])
        self.assertIn("dropped 1 step(s)", chat["variantQuery"]["text"])
        self.assertIn("via plan.variant", chat["variantQuery"]["text"])

    def test_a_remembered_fact_is_a_preference(self):
        chat = self.out["chat"]
        self.assertEqual(chat["remember"]["via"], "memory.remember")
        self.assertIn("preference · favorite color · teal",
                      chat["prefQuery"]["text"])
        self.assertIn("via memory.remember", chat["prefQuery"]["text"])

    def test_a_repair_refusal_is_a_rejection(self):
        chat = self.out["chat"]
        self.assertEqual(chat["kindRepair"]["via"], "repair.plan")
        self.assertIn("r.repair-kind", chat["kindRepair"]["text"])
        self.assertIn("rejection · repair · refuse · r.repair-kind",
                      chat["kindQuery"]["text"])

    # ----------------------------------------------------------- bundle ---
    def test_the_project_bundle_round_trips_the_journal(self):
        bundle = self.out["bundle"]
        self.assertEqual(bundle["export"]["via"], "project.export")
        self.assertTrue(bundle["docJournal"])
        self.assertEqual(bundle["docJournal"][0]["kind"], "decision")
        self.assertEqual(bundle["afterReset"], 0)
        self.assertEqual(bundle["import"]["via"], "project.import")
        self.assertEqual(bundle["afterImport"], len(bundle["docJournal"]))
        self.assertIn("art style", bundle["query"]["text"])

    # -------------------------------------------------------- isolation ---
    def test_projects_never_share_a_journal(self):
        iso = self.out["isolation"]
        self.assertNotEqual(iso["firstSlug"], iso["secondSlug"])
        self.assertEqual(iso["first"], 1)
        self.assertEqual(iso["second"], 1)
        self.assertIn("art style", iso["firstTopics"])
        self.assertIn("art style", iso["secondTopics"])
        self.assertIn("genre todo", iso["activeQuery"]["text"])
        self.assertIn("genre todo", iso["activeText"])

    # ---------------------------------------------------------- network ---
    def test_the_journal_never_touches_the_network(self):
        self.assertEqual(self.out["fetches"], 0,
                         "a journal route made a network call")
        with open(os.path.join(WEB, "journal.js"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotRegex(source, r"\bfetch\s*\(")
        self.assertNotIn("import(", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

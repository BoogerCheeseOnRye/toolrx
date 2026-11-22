#!/usr/bin/env python3
"""Step 65: operator event stream, replay, and the last-run bundle.

`toolrx/events.json` is the only source of the `events.*` routes; it feeds the
catalog and `tests/fixtures/events.json`. `toolrx/web/events.js` is the pure,
bounded store. These tests cover the store's caps and duplicate handling, the
routes, the real compaction/rewrite/repair/resume/refusal stream, one-shot
replay, the export/import round-trip through `parseBundle`, and the dashboard's
keyboard-reachable text alternatives.
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
FIXTURE = os.path.join(HERE, "fixtures", "events.json")
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import envelope  # noqa: E402
import events  # noqa: E402

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
  'thinking.js', 'explain.js', 'repair.js', 'trace.js', 'journal.js',
  'workspace.js', 'events.js', 'style.js', 'context.js', 'skills.js',
  'templates.js', 'context.js', 'patches.js', 'engine2d.js',
  'engine2d.embed.js', 'engine3d.js', 'engine3d.embed.js', 'worldgen.js',
  'worldgen.embed.js', 'rpg2.js', 'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

const ask = async q => {
  const list = await self.toolrxWeb.prompt(q);
  const r = list[list.length - 1] || {};
  return { step: r.step, text: String(r.text || ''), via: r.via || '',
           error: !!r.error, variant: r.variant || null,
           replay: r.replay || null };
};

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const fetchBefore = fetches;
  const E = self.toolrxEvents;
  const out = { limits: {}, pure: {}, routes: [], chat: {}, bundle: {},
                dashboard: {}, fetches: 0 };

  out.limits.entries = self.toolrxLimits.eventEntries;
  out.limits.bytes = self.toolrxLimits.eventBytes;
  out.limits.text = self.toolrxLimits.eventText;

  // ------------------------------------------------------------- pure store ---
  E.clear('pure-test');
  for (let i = 0; i < 40; i++) {
    E.add('pure-test', { kind: 'compact', route: 'context.auto',
                         text: 'reason ' + i, at: 1000 + i });
  }
  const capped = E.summary('pure-test');
  out.pure.count = capped.count;
  out.pure.dropped = capped.dropped;
  out.pure.first = capped.entries[0].seq;
  out.pure.last = capped.entries[capped.entries.length - 1].seq;
  out.pure.text = E.text('pure-test');
  out.pure.duplicate = E.add('pure-test', {
    kind: 'compact', route: 'context.auto',
    text: capped.entries[capped.entries.length - 1].text, at: 2000,
  });
  out.pure.invalid = E.add('pure-test', {
    kind: 'unknown', route: 'context.auto', text: 'nope', at: 2001,
  });
  const exported = E.exportFor('pure-test');
  E.clear('pure-test');
  out.pure.imported = E.importFor('pure-test', exported);
  out.pure.roundtrip = JSON.stringify(E.exportFor('pure-test'))
    === JSON.stringify(exported);
  // The byte cap, not just the entry count, must drop and report.
  E.clear('byte-test');
  for (let i = 0; i < 32; i++) {
    E.add('byte-test', { kind: 'rewrite', route: 'plan.variant',
                         text: 'x'.repeat(230) + String(i).padStart(10, '0'),
                         at: 3000 + i });
  }
  const bytes = E.summary('byte-test');
  out.pure.bytesCount = bytes.count;
  out.pure.bytesDropped = bytes.dropped;
  out.pure.bytesText = E.text('byte-test');
  out.pure.trimmed = bytes.entries.every(e => e.text.length <= 240);
  E.clear('byte-test');

  // --------------------------------------------------------------- routes ---
  FIXTURE.cases.forEach(c => {
    const hit = self.toolrxSkills.match(c.text);
    out.routes.push({ text: c.text, want: c.op, got: hit ? hit.op : null });
  });

  // ------------------------------------------------------------ real chat ---
  self.toolrxWeb.reset();
  E.clear('scratch');
  await ask('convert 1 km to mi then convert 2 km to mi');
  const run = self.toolrxWeb.lastRun();
  out.chat.planOk = !!(run && run.ok);
  out.chat.planSteps = run && run.plan ? run.plan.steps.length : 0;

  const replay1 = await ask('replay the last plan');
  const afterReplay = self.toolrxWeb.lastRun();
  out.chat.replay1 = { via: replay1.via, error: replay1.error,
                       replayedAt: afterReplay && afterReplay.replayedAt,
                       ok: afterReplay && afterReplay.ok,
                       text: replay1.text };
  const replay2 = await ask('replay the last plan');
  out.chat.replay2 = { via: replay2.via, error: replay2.error,
                       text: replay2.text };

  // A plan over the step cap is rewritten into a bounded variant.
  const long = Array.from({ length: 50 },
    (_, i) => 'convert ' + (i + 1) + ' km to mi').join(' then ');
  const rewritten = await ask(long);
  out.chat.rewrite = { via: rewritten.via, error: rewritten.error,
                       variant: rewritten.variant,
                       text: rewritten.text.slice(0, 240) };

  // Force a real auto-compaction through the sandbox's context write path.
  store['toolrx.context.cap'] = '65536';
  self.toolrxContext.setMany('scratch', Array.from({ length: 8 }, (_, i) => ({
    kind: 'file', key: 'f' + i, text: 'y'.repeat(500),
  })));
  store['toolrx.context.cap'] = '2048';
  await ask('convert 3 km to mi');
  delete store['toolrx.context.cap'];

  // A failed plan feeds repair, resume, and refusal events.
  await ask('open the file missing.txt then convert 1 km to mi');
  const failed = self.toolrxWeb.lastRun();
  out.chat.failed = failed ? failed.failed : -1;
  await ask('repair this plan');
  await ask('open the file missing.txt then convert 1 km to mi');
  await ask('resume');
  await ask('open the file missing.txt');

  const summary = self.toolrxWeb.events();
  out.chat.kinds = summary.entries.map(e => e.kind);
  out.chat.routes = summary.entries.map(e => e.route);
  out.chat.hasStamp = summary.entries.every(e => e.at > 0);
  out.chat.eventsText = self.toolrxWeb.eventsText();
  out.chat.count = summary.count;
  out.chat.cap = summary.cap;

  // --------------------------------------------------------------- bundle ---
  const exp = await ask('export the last run');
  out.bundle.export = exp.text;
  const bundles = JSON.parse(store['toolrx.bundles.v1'] || '{"items":{}}');
  const key = Object.keys(bundles.items).find(k => k.indexOf('events-') === 0);
  const doc = JSON.parse(bundles.items[key].text);
  out.bundle.format = doc.format;
  out.bundle.version = doc.version;
  out.bundle.hasRun = !!doc.lastRun;
  out.bundle.eventCount = doc.events.length;
  out.bundle.journalCount = doc.journal.length;
  out.bundle.project = doc.project;

  const slug = doc.project || 'scratch';
  E.clear(slug);
  self.toolrxJournal.clear(slug);
  const imp = await ask('import events from ' + key);
  out.bundle.importText = imp.text;
  out.bundle.importedEvents = self.toolrxWeb.events().count;
  out.bundle.importedJournal = self.toolrxJournal.exportFor(slug).length;
  out.bundle.importedRun = !!self.toolrxWeb.lastRun();
  out.bundle.importedRunAt = self.toolrxWeb.lastRun()
    ? self.toolrxWeb.lastRun().at : 0;

  const badFormat = JSON.parse(JSON.stringify(doc));
  badFormat.format = 'toolrx.nope';
  try { self.toolrxWeb.importEvents(JSON.stringify(badFormat));
        out.bundle.badFormat = ''; }
  catch (e) { out.bundle.badFormat = e.message; }

  const badEvents = JSON.parse(JSON.stringify(doc));
  badEvents.events = 'not a list';
  try { self.toolrxWeb.importEvents(JSON.stringify(badEvents));
        out.bundle.badEvents = ''; }
  catch (e) { out.bundle.badEvents = e.message; }

  const badRun = JSON.parse(JSON.stringify(doc));
  badRun.lastRun = { at: 'not a number' };
  try { self.toolrxWeb.importEvents(JSON.stringify(badRun));
        out.bundle.badRun = ''; }
  catch (e) { out.bundle.badRun = e.message; }

  // ------------------------------------------------------------- dashboard ---
  out.dashboard.html = fs.readFileSync(path.join(WEB, '..', 'dashboard.html'),
                                       'utf8');
  out.dashboard.sw = fs.readFileSync(path.join(WEB, 'sw.js'), 'utf8');

  out.fetches = fetches - fetchBefore;
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is not installed")
class EventsTest(unittest.TestCase):
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
        doc = events.fixture()
        with open(FIXTURE, encoding="utf-8") as fh:
            current = json.load(fh)
        self.assertEqual(current, doc)
        self.assertEqual(current["count"], len(current["cases"]))
        self.assertEqual(set(current["ops"]),
                         {"events.show", "events.replay",
                          "events.export", "events.import"})

    def test_every_route_resolves_to_its_own_op(self):
        for row in self.out["routes"]:
            self.assertEqual(row["got"], row["want"], row["text"])

    # ----------------------------------------------------------- limits ---
    def test_event_limits_are_declared(self):
        self.assertEqual(self.out["limits"]["entries"], 32)
        self.assertEqual(self.out["limits"]["bytes"], 8192)
        self.assertEqual(self.out["limits"]["text"], 240)
        data = envelope.load()
        self.assertEqual(data["eventEntries"], 32)
        self.assertEqual(data["eventBytes"], 8192)
        self.assertEqual(data["eventText"], 240)
        self.assertEqual(len(envelope._RANGES), 53)

    # ------------------------------------------------------------- pure ---
    def test_entry_cap_drops_oldest_and_reports_it(self):
        self.assertEqual(self.out["pure"]["count"], 32)
        self.assertEqual(self.out["pure"]["dropped"], 8)
        self.assertEqual(self.out["pure"]["first"], 9)
        self.assertEqual(self.out["pure"]["last"], 40)
        self.assertIn("dropped 8 older event(s)", self.out["pure"]["text"])

    def test_duplicate_and_invalid_events_are_honest(self):
        self.assertTrue(self.out["pure"]["duplicate"]["duplicate"])
        self.assertFalse(self.out["pure"]["invalid"]["ok"])
        self.assertIn("known kind", self.out["pure"]["invalid"]["why"])

    def test_export_import_round_trips(self):
        self.assertTrue(self.out["pure"]["imported"]["ok"])
        self.assertTrue(self.out["pure"]["roundtrip"])

    def test_byte_cap_drops_and_keeps_text_bounded(self):
        self.assertLess(self.out["pure"]["bytesCount"], 32)
        self.assertGreater(self.out["pure"]["bytesDropped"], 0)
        self.assertTrue(self.out["pure"]["trimmed"])
        self.assertIn("eventEntries/eventBytes cap",
                      self.out["pure"]["bytesText"])

    # ------------------------------------------------------------- chat ---
    def test_one_shot_replay_runs_and_then_refuses(self):
        first = self.out["chat"]["replay1"]
        self.assertTrue(self.out["chat"]["planOk"])
        self.assertGreaterEqual(self.out["chat"]["planSteps"], 2)
        self.assertFalse(first["error"])
        self.assertEqual(first["via"], "events.replay")
        self.assertTrue(first["ok"])
        self.assertTrue(first["replayedAt"])
        second = self.out["chat"]["replay2"]
        self.assertTrue(second["error"])
        self.assertEqual(second["via"], "events.replay")
        self.assertIn("already replayed once", second["text"])

    def test_rewrite_event_quotes_the_stored_reason(self):
        self.assertEqual(self.out["chat"]["rewrite"]["via"], "plan.variant")
        self.assertIn("rewrite", self.out["chat"]["kinds"])
        self.assertIn("over steps", self.out["chat"]["eventsText"])
        self.assertIn("dropped", self.out["chat"]["eventsText"])

    def test_every_stream_kind_comes_from_a_stored_record(self):
        kinds = self.out["chat"]["kinds"]
        for kind in ("compact", "rewrite", "repair", "resume", "refusal"):
            self.assertIn(kind, kinds)
        self.assertTrue(self.out["chat"]["hasStamp"])
        self.assertIn("event stream · project: scratch",
                      self.out["chat"]["eventsText"])
        self.assertIn("cap 32 entries · 8192 bytes · 240 chars",
                      self.out["chat"]["eventsText"])
        self.assertIn("context.auto", self.out["chat"]["routes"])
        self.assertIn("repair.plan", self.out["chat"]["routes"])
        self.assertIn("repair.resume", self.out["chat"]["routes"])

    def test_events_are_bounded(self):
        self.assertLessEqual(self.out["chat"]["count"],
                             self.out["chat"]["cap"]["entries"])
        self.assertEqual(self.out["chat"]["cap"]["entries"], 32)

    # ----------------------------------------------------------- bundle ---
    def test_export_is_the_events_format(self):
        self.assertEqual(self.out["bundle"]["format"], "toolrx.events")
        self.assertEqual(self.out["bundle"]["version"], 1)
        self.assertTrue(self.out["bundle"]["hasRun"])
        self.assertGreaterEqual(self.out["bundle"]["eventCount"], 5)
        self.assertGreaterEqual(self.out["bundle"]["journalCount"], 1)

    def test_export_import_restores_events_and_journal(self):
        self.assertIn("imported events", self.out["bundle"]["importText"])
        self.assertGreaterEqual(self.out["bundle"]["importedEvents"], 5)
        self.assertGreaterEqual(self.out["bundle"]["importedJournal"], 1)
        self.assertTrue(self.out["bundle"]["importedRun"])
        self.assertGreater(self.out["bundle"]["importedRunAt"], 0)

    def test_import_validates_through_parse_bundle(self):
        self.assertIn("unsupported bundle format",
                      self.out["bundle"]["badFormat"])
        self.assertIn("invalid event stream", self.out["bundle"]["badEvents"])
        self.assertIn("without a timestamp", self.out["bundle"]["badRun"])

    # -------------------------------------------------------- dashboard ---
    def test_dashboard_panel_is_keyboard_reachable_with_text_alternatives(self):
        html = self.out["dashboard"]["html"]
        self.assertIn('<script src="web/events.js"></script>', html)
        self.assertIn("headroom warning · ", html)
        self.assertIn("CAP_FOR_BAR", html)
        self.assertIn("why compacted / rewritten · ", html)
        self.assertIn("operator event stream and actions", html)
        self.assertIn("replay last plan once", html)
        self.assertIn("export last run + journal", html)
        self.assertIn("aria-live','polite'", html)
        self.assertIn("aria-label','operator events, oldest first'", html)
        self.assertIn("no operator events yet", html)

    def test_offline_shell_ships_the_event_module(self):
        sw = self.out["dashboard"]["sw"]
        self.assertIn('const CACHE = "toolrx-shell-v18-r12";', sw)
        self.assertIn('"./web/events.js"', sw)

    def test_no_network_on_the_default_path(self):
        self.assertEqual(self.out["fetches"], 0)


if __name__ == "__main__":
    unittest.main()

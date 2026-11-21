#!/usr/bin/env python3
"""Step 64: cross-project workspace index and workspace journal.

`toolrx/workspace.json` is the only source of the `workspace.*` routes; it feeds
the catalog and `tests/fixtures/workspace.json`. `toolrx/web/workspace.js` is the
pure, bounded twin of `toolrx/workspace.py`. These tests cover the table, the
Python/JS parity, the named caps, empty and capped states, cross-project theme
and decision queries, deletion, context isolation, and the byte-identical
workspace bundle index.
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
FIXTURE = os.path.join(HERE, "fixtures", "workspace.json")
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import envelope  # noqa: E402
import workspace  # noqa: E402

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
  'workspace.js', 'style.js', 'context.js', 'skills.js', 'templates.js',
  'patches.js', 'engine2d.js', 'engine2d.embed.js', 'engine3d.js',
  'engine3d.embed.js', 'worldgen.js', 'worldgen.embed.js', 'rpg2.js',
  'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

const ask = async q => {
  const list = await self.toolrxWeb.prompt(q);
  const r = list[list.length - 1] || {};
  return { step: r.step, text: String(r.text || ''), via: r.via || '',
           error: !!r.error };
};

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const fetchBefore = fetches;
  const W = self.toolrxWorkspace;
  const out = { limits: {}, js: {}, routes: [], build: {}, empty: {},
                chat: {}, deletion: {}, isolation: {}, bundle: {},
                fetches: 0 };

  out.limits.projects = self.toolrxLimits.workspaceProjects;
  out.limits.topics = self.toolrxLimits.workspaceTopics;
  out.limits.rows = self.toolrxLimits.workspaceRows;
  out.limits.bytes = self.toolrxLimits.workspaceIndexBytes;
  out.limits.chars = self.toolrxLimits.workspaceChars;
  out.limits.journalText = self.toolrxLimits.journalText;

  // ----------------------------------------------------- JS fixture parity ---
  out.js.states = FIXTURE.states.length;
  out.js.mismatches = [];
  FIXTURE.states.forEach(s => {
    const got = W.render(s.kind, s.input, s.args);
    if (got !== s.want) {
      out.js.mismatches.push({ name: s.name, kind: s.kind, args: s.args,
                               want: s.want, got: got });
    }
  });

  // --------------------------------------------------------------- routes ---
  FIXTURE.cases.forEach(c => {
    const hit = self.toolrxSkills.match(c.text);
    out.routes.push({ text: c.text, want: c.op, got: hit ? hit.op : null });
  });

  // ------------------------------------------------------- capped build ---
  const wide = { active: '', projects: [] };
  for (let i = 0; i < 30; i++) {
    const journal = [];
    for (let t = 0; t < 12; t++) {
      journal.push({ seq: t + 1, kind: 'decision', topic: 'topic ' + t,
                     text: 'decision ' + i + ' ' + t, source: 'build' });
    }
    wide.projects.push({
      slug: 'p' + String(i).padStart(2, '0'), name: 'P' + i, kind: 'notes',
      theme: i % 2 ? 'light' : 'dark', seed: i, updated: 1000 - i,
      journal: journal,
    });
  }
  const built = W.build(wide);
  const builtText = W.exportDoc(built);
  const imported = W.importDoc(builtText);
  out.build.projects = built.projects.length;
  out.build.droppedProjects = built.dropped.projects;
  out.build.droppedTopics = built.dropped.topics;
  out.build.topicsPerProject = built.projects[0].topics.length;
  out.build.bytes = built.bytes;
  out.build.roundtrip = imported.ok && W.exportDoc(imported.index) === builtText;
  out.build.text = W.render('index', wide);

  // Names like "__proto__" must behave as ordinary topics, not as JS internals.
  const weirdState = { projects: [{
    slug: 'x', name: 'X', kind: 'notes', theme: 'dark', seed: 1, updated: 1,
    journal: [
      { seq: 1, kind: 'decision', topic: '__proto__', text: 'a', source: 'build' },
      { seq: 2, kind: 'decision', topic: 'constructor', text: 'b', source: 'build' },
      { seq: 3, kind: 'decision', topic: 'toString', text: 'c', source: 'build' },
    ],
  }] };
  out.build.weirdTopics = W.build(weirdState).projects[0].topics;
  out.build.weirdDecisions = W.render('decisions', weirdState,
                                      { topic: 'constructor', limit: 'three' });

  // ---------------------------------------------------------------- empty ---
  out.empty.index = W.render('index', { projects: [] });
  out.empty.themes = W.render('themes', { projects: [] });
  out.empty.decisions = W.render('decisions', { projects: [] },
                                 { topic: 'art style', limit: 'three' });

  // ------------------------------------------------------------ real chat ---
  await ask('build a platformer game');
  const firstSlug = self.toolrxWeb.project().slug;
  await ask('build a todo app');
  const secondSlug = self.toolrxWeb.project().slug;
  out.chat.themes = await ask('what themes have i used across projects');
  out.chat.decisions = await ask('show decisions about art style in the last three builds');
  out.chat.index = await ask('show the workspace index');
  out.chat.journal = await ask('what did we decide about the art style?');

  // ------------------------------------------------------------- deletion ---
  self.toolrxWeb.deleteProject(firstSlug);
  out.deletion.text = (await ask('show the workspace index')).text;
  out.deletion.goneSlug = firstSlug;
  out.deletion.stillSlug = secondSlug;

  // ------------------------------------------------------------ isolation ---
  self.toolrxWeb.reset();
  await ask('build a platformer game');
  const secretSlug = self.toolrxWeb.project().slug;
  self.toolrxContext.set(secretSlug, 'fact', 'secret', 'ZEBRA-SECRET');
  await ask('build a todo app');
  out.isolation.stored = self.toolrxContext.get(secretSlug, 'fact', 'secret');
  out.isolation.themes = (await ask('what themes have i used across projects')).text;
  out.isolation.decisions = (await ask('show decisions about art style in the last three builds')).text;
  out.isolation.index = (await ask('show the workspace index')).text;

  // --------------------------------------------------------------- bundle ---
  self.toolrxWeb.reset();
  await ask('build a platformer game');
  await ask('build a todo app');
  out.bundle.export = await ask('export the workspace with the index');
  const bundles = JSON.parse(store['toolrx.bundles.v1'] || '{"items":{}}');
  const key = Object.keys(bundles.items).find(k => k === 'workspace.toolrx.json');
  const doc = JSON.parse(bundles.items[key].text);
  out.bundle.hasIndex = !!doc.index;
  out.bundle.slugs = doc.index ? doc.index.projects.map(p => p.slug) : [];
  const firstIndex = W.exportDoc(doc.index);
  self.toolrxWeb.reset();
  out.bundle.import = await ask('import the workspace from ' + key);
  await ask('export the workspace with the index');
  const again = JSON.parse(store['toolrx.bundles.v1']).items[key].text;
  const rebuilt = JSON.parse(again).index;
  out.bundle.roundtrip = W.exportDoc(rebuilt) === firstIndex;
  out.bundle.rebuilt = rebuilt;

  // A stale index is refused before anything is written.
  self.toolrxWeb.reset();
  const tampered = JSON.parse(JSON.stringify(doc));
  tampered.index.projects[0].theme =
    tampered.index.projects[0].theme === 'light' ? 'dark' : 'light';
  try {
    self.toolrxWeb.importWorkspace(JSON.stringify(tampered));
    out.bundle.staleError = '';
  } catch (e) {
    out.bundle.staleError = e.message;
  }

  out.fetches = fetches - fetchBefore;
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is not installed")
class WorkspaceTest(unittest.TestCase):
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
        doc = workspace.fixture()
        with open(FIXTURE, encoding="utf-8") as fh:
            current = json.load(fh)
        self.assertEqual(current, doc)
        self.assertEqual(current["count"], len(current["cases"]))
        self.assertEqual(set(current["ops"]),
                         {"workspace.index", "workspace.themes",
                          "workspace.decisions", "workspace.export.index"})

    def test_the_javascript_twin_matches_every_state(self):
        self.assertEqual(self.out["js"]["states"], 15)
        self.assertEqual(self.out["js"]["mismatches"], [])

    def test_every_route_resolves_to_its_own_op(self):
        for row in self.out["routes"]:
            self.assertEqual(row["got"], row["want"], row["text"])

    def test_workspace_routes_precede_journal_routes(self):
        with open(os.path.join(WEB, "commands.json"), encoding="utf-8") as fh:
            commands = json.load(fh)["commands"]
        first_workspace = min(
            i for i, c in enumerate(commands) if c["op"].startswith("workspace.")
        )
        first_journal = min(
            i for i, c in enumerate(commands) if c["op"] == "journal.query"
        )
        self.assertLess(first_workspace, first_journal)
        # A plain journal question still reaches the journal, not the index.
        self.assertEqual(self.out["chat"]["journal"]["via"], "journal.query")

    # ----------------------------------------------------------- limits ---
    def test_workspace_limits_are_declared(self):
        data = envelope.load()
        self.assertEqual(self.out["limits"]["projects"], 24)
        self.assertEqual(self.out["limits"]["topics"], 8)
        self.assertEqual(self.out["limits"]["rows"], 12)
        self.assertEqual(self.out["limits"]["bytes"], 8192)
        self.assertEqual(self.out["limits"]["chars"], 4000)
        self.assertEqual(data["workspaceProjects"], 24)
        self.assertEqual(data["workspaceTopics"], 8)
        self.assertEqual(data["workspaceRows"], 12)
        self.assertEqual(data["workspaceIndexBytes"], 8192)
        self.assertEqual(data["workspaceChars"], 4000)
        self.assertEqual(len(envelope._RANGES), 50)

    # ------------------------------------------------------------- caps ---
    def test_the_project_and_topic_caps_are_explicit(self):
        build = self.out["build"]
        self.assertEqual(build["projects"], 24)
        self.assertEqual(build["droppedProjects"], 6)
        self.assertEqual(build["topicsPerProject"], 8)
        self.assertEqual(build["droppedTopics"], 4 * 30)
        self.assertTrue(build["roundtrip"])
        self.assertIn("dropped at the workspaceProjects cap", build["text"])
        self.assertIn("dropped at the workspaceTopics cap", build["text"])

    def test_js_internal_names_are_ordinary_topics(self):
        build = self.out["build"]
        self.assertEqual(build["weirdTopics"],
                         ["__proto__", "constructor", "toString"])
        self.assertIn("constructor", build["weirdDecisions"])
        self.assertIn("decision · constructor", build["weirdDecisions"])

    def test_the_empty_workspace_is_honest(self):
        empty = self.out["empty"]
        for text in (empty["index"], empty["themes"], empty["decisions"]):
            self.assertIn("empty", text)
            self.assertIn("no projects yet", text)
            self.assertIn("writes: no file", text)

    # ------------------------------------------------------------- chat ---
    def test_cross_project_themes_are_deterministic(self):
        themes = self.out["chat"]["themes"]
        self.assertEqual(themes["via"], "workspace.themes")
        self.assertIn("workspace themes · 2 projects", themes["text"])
        self.assertIn("platformer · dark · platformer", themes["text"])
        self.assertIn("todo-list · dark · todo", themes["text"])
        self.assertIn("cap 12 rows · workspaceRows", themes["text"])

    def test_cross_project_decisions_are_deterministic(self):
        decisions = self.out["chat"]["decisions"]
        self.assertEqual(decisions["via"], "workspace.decisions")
        self.assertIn('workspace decisions · "art style" · last 3 builds', decisions["text"])
        self.assertIn("2 matches", decisions["text"])
        self.assertIn("decision · art style", decisions["text"])
        self.assertIn("via build", decisions["text"])

    def test_the_index_names_every_project_and_cap(self):
        index = self.out["chat"]["index"]
        self.assertEqual(index["via"], "workspace.index")
        self.assertIn("workspace index · 2 projects", index["text"])
        self.assertIn("cap 24 projects · 8192 bytes", index["text"])
        self.assertIn("platformer · Platformer", index["text"])
        self.assertIn("todo-list · Todo list", index["text"])
        self.assertIn("source: project files + per-project journals", index["text"])
        self.assertIn("context is never read", index["text"])

    # ---------------------------------------------------------- deletion ---
    def test_a_deleted_project_leaves_the_index(self):
        deletion = self.out["deletion"]
        self.assertNotIn(deletion["goneSlug"], deletion["text"])
        self.assertIn(deletion["stillSlug"], deletion["text"])
        self.assertIn("workspace index · 1 project", deletion["text"])

    # --------------------------------------------------------- isolation ---
    def test_context_never_leaks_into_the_index(self):
        isolation = self.out["isolation"]
        self.assertEqual(isolation["stored"], "ZEBRA-SECRET")
        for text in (isolation["themes"], isolation["decisions"],
                     isolation["index"]):
            self.assertNotIn("ZEBRA-SECRET", text)

    # ------------------------------------------------------------ bundle ---
    def test_the_workspace_bundle_carries_the_index_only_on_request(self):
        bundle = self.out["bundle"]
        self.assertEqual(bundle["export"]["via"], "workspace.export.index")
        self.assertIn("index included", bundle["export"]["text"])
        self.assertTrue(bundle["hasIndex"])
        self.assertEqual(bundle["slugs"], ["platformer", "todo-list"])

    def test_the_index_reimports_byte_identically(self):
        bundle = self.out["bundle"]
        self.assertEqual(bundle["import"]["via"], "workspace.import")
        self.assertTrue(bundle["roundtrip"])
        self.assertGreater(bundle["rebuilt"]["bytes"], 0)
        self.assertLessEqual(bundle["rebuilt"]["bytes"], 8192)

    def test_a_stale_index_is_refused(self):
        self.assertIn("does not match its projects",
                      self.out["bundle"]["staleError"])

    # ------------------------------------------------------- python pure ---
    def test_import_doc_preserves_the_dropped_topic_count(self):
        doc = workspace.build({"projects": [
            {"slug": "a", "name": "A", "kind": "notes", "theme": "dark",
             "seed": 1, "updated": 1,
             "journal": [{"seq": i, "kind": "decision", "topic": "t%d" % i,
                          "text": "x", "source": "build"} for i in range(12)]},
        ]})
        self.assertEqual(doc["dropped"]["topics"], 4)
        checked = workspace.import_doc(workspace.export_doc(doc))
        self.assertTrue(checked["ok"])
        self.assertEqual(workspace.export_doc(checked["index"]),
                         workspace.export_doc(doc))

    # ---------------------------------------------------------- network ---
    def test_the_workspace_never_touches_the_network(self):
        self.assertEqual(self.out["fetches"], 0,
                         "a workspace route made a network call")
        for name in ("workspace.js", "workspace.py"):
            with open(os.path.join(WEB if name.endswith(".js") else CORE, name),
                      encoding="utf-8") as fh:
                source = fh.read()
            self.assertNotIn("XMLHttpRequest", source)
            self.assertNotRegex(source, r"\bfetch\s*\(")
            self.assertNotIn("import(", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

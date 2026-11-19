#!/usr/bin/env python3
"""Step 61: deterministic project, plan, and theme explanations.

`toolrx/explain.json` is the only source of the `explain.*` routes; it feeds the
catalog and `tests/fixtures/explain.json`. `toolrx/web/explain.js` is the pure
program and `toolrx/explain.py` is its byte-identical Python twin. These tests
check the table, then drive the real modules in Node: every state renders
byte-identically twice, every named file exists, every cap is named, missing
state refuses honestly, and no explain route touches the network.
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
CORE = os.path.join(ROOT, "toolrx")
WEB = os.path.join(CORE, "web")
FIXTURE = os.path.join(HERE, "fixtures", "explain.json")
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import explain  # noqa: E402

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
  'style.js', 'skills.js', 'templates.js', 'context.js', 'lang.js',
  'patches.js', 'engine2d.js', 'engine2d.embed.js', 'engine3d.js',
  'engine3d.embed.js', 'worldgen.js', 'worldgen.embed.js', 'rpg2.js',
  'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const out = { routes: [], pure: {}, chat: {} };
  const T = self.toolrxExplain;

  FIXTURE.cases.forEach(c => {
    const hit = self.toolrxSkills.match(c.text);
    out.routes.push({
      text: c.text,
      want: c.op,
      got: hit ? hit.op : null,
    });
  });

  FIXTURE.states.forEach(state => {
    const first = T.run(state.target, state.input);
    const second = T.run(state.target, state.input);
    out.pure[state.name] = { first, second, want: state.want };
  });

  const ask = async q => (await self.toolrxWeb.prompt(q)).map(r => ({
    step: r.step, text: r.text, via: r.via || '', error: !!r.error,
  }));

  self.toolrxWeb.reset();
  out.chat.noProject = (await ask('explain this project'))[0];
  out.chat.noPlan = (await ask('explain the last plan'))[0];
  out.chat.build = (await ask('build a platformer game'))[0];
  const fetchBefore = fetches;
  out.chat.project = (await ask('explain this project'))[0];
  out.chat.projectAgain = (await ask('explain this project'))[0];
  out.chat.theme = (await ask('why did this build pick that theme'))[0];
  out.chat.plan = (await ask('explain the last plan'))[0];
  out.chat.fetches = fetches - fetchBefore;
  out.chat.contextStore = (await ask('explain this project in context'))[0];
  out.chat.contextStored = self.toolrxContext.get('platformer', 'explain', 'project');
  out.chat.journalStore = (await ask('explain this project in the journal'))[0];
  out.chat.journalStored = self.toolrxJournal.query('platformer', 'explain project').matches;
  out.chat.journalAnswer = (await ask('what did we decide about explain project'))[0];

  console.log(JSON.stringify(out));
})().catch(e => {
  console.error(e && e.stack || String(e));
  process.exit(1);
});
"""


class TableTest(unittest.TestCase):
    def test_table_is_valid_and_unique(self):
        table = explain.load()
        self.assertEqual(table["version"], 1)
        entries = list(explain.entries())
        self.assertGreater(len(entries), 40)
        ids = [entry["id"] for entry in entries]
        self.assertEqual(len(ids), len(set(ids)))
        patterns = [entry["re"] for entry in entries]
        self.assertEqual(len(patterns), len(set(patterns)))
        for entry in entries:
            self.assertEqual(entry["c"], "explain")
            self.assertTrue(entry["op"].startswith("explain."))
            self.assertIn(entry["target"], explain.TARGETS)

    def test_fixture_is_current(self):
        doc = explain.fixture()
        self.assertTrue(os.path.exists(FIXTURE), "run python3 toolrx/explain.py --write")
        with open(FIXTURE, encoding="utf-8") as fh:
            current = json.load(fh)
        self.assertEqual(current, doc,
                         "explain fixture drifted: run python3 toolrx/explain.py --write")
        self.assertEqual(doc["count"], len(doc["cases"]))
        self.assertEqual(doc["targets"],
                         {"plan": 14, "project": 22, "theme": 16})


@unittest.skipUnless(NODE, "node is not installed")
class BrowserExplainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", JS, WEB, os.path.join(WEB, "commands.json"),
             os.path.join(CORE, "micro_model.json"), FIXTURE],
            capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-4000:])
        cls.out = json.loads(proc.stdout)
        with open(FIXTURE, encoding="utf-8") as fh:
            cls.fixture = json.load(fh)

    def test_every_route_resolves_to_its_explain_op(self):
        for route in self.out["routes"]:
            self.assertEqual(route["got"], route["want"], route["text"])

    def test_python_and_javascript_render_the_same_bytes(self):
        for state in self.fixture["states"]:
            pure = self.out["pure"][state["name"]]
            self.assertEqual(pure["first"], state["want"], state["name"])
            self.assertEqual(pure["second"], state["want"], state["name"])

    def test_every_state_is_byte_identical_on_a_second_run(self):
        for name, pure in self.out["pure"].items():
            self.assertEqual(pure["first"], pure["second"], name)

    def test_project_output_names_real_files_and_systems(self):
        for state in self.fixture["states"]:
            if state["target"] != "project" or not state["input"]["project"]:
                continue
            project = state["input"]["project"]
            names = {file["name"] for file in project["files"]}
            text = self.out["pure"][state["name"]]["first"]
            for line in text.split("\n"):
                match = re.match(r"^  (\S+) · [\d,]+ bytes · [\d,]+ lines · sha ",
                                 line)
                if match:
                    self.assertIn(match.group(1), names, line)
            systems = [name for name in names if name.startswith("systems/")]
            system_lines = [line for line in text.split("\n")
                            if line.startswith("systems (")]
            if not system_lines:
                continue  # a trimmed state may end before the systems line
            for name in systems:
                self.assertIn(name, system_lines[0])
            for name in re.findall(r"systems/[A-Za-z0-9_.-]+", system_lines[0]):
                self.assertIn(name, names)

    def test_every_named_cap_and_seed_is_reported(self):
        project = self.out["pure"]["project-basic"]["first"]
        self.assertIn("seed 123456789", project)
        self.assertIn("files 5/32", project)
        self.assertIn("project 15,700/524,288 bytes", project)
        self.assertIn("context 1,024/8,192 bytes", project)
        self.assertIn("explain cap 8,000 chars", project)
        plan = self.out["pure"]["plan-basic"]["first"]
        self.assertIn("steps 3/40", plan)
        self.assertIn("chars 46/8,000", plan)
        self.assertIn("time 12 s/160 s", plan)
        self.assertIn("explain cap 8,000 chars", plan)

    def test_missing_project_and_plan_refuse_honestly(self):
        project = self.out["pure"]["project-missing"]["first"]
        self.assertIn("no active project", project)
        self.assertIn("r.project-exists", project)
        plan = self.out["pure"]["plan-missing"]["first"]
        self.assertIn("no plan to explain", plan)
        self.assertIn("r.plan-exists", plan)
        theme = self.out["pure"]["theme-missing"]["first"]
        self.assertIn("no active project", theme)
        self.assertIn("r.project-exists", theme)

    def test_trimming_names_the_explain_cap(self):
        text = self.out["pure"]["project-trimmed"]["first"]
        self.assertIn("… trimmed to 700 chars (explainChars) · r.trim", text)
        self.assertLessEqual(len(text.encode("utf-8")), 700)

    def test_every_rule_used_exists_in_the_rule_table(self):
        with open(os.path.join(WEB, "explain.js"), encoding="utf-8") as fh:
            source = fh.read()
        table = set(re.findall(r'"(r\.[a-z][a-z-]*)"\s*:', source))
        self.assertGreater(len(table), 20)
        for name, pure in self.out["pure"].items():
            used = set(re.findall(r"r\.[a-z][a-z-]*", pure["first"]))
            self.assertTrue(used, name)
            self.assertEqual(used - table, set(), name)

    def test_chat_routes_reach_the_handlers(self):
        chat = self.out["chat"]
        self.assertEqual(chat["noProject"]["via"], "explain.project")
        self.assertEqual(chat["noPlan"]["via"], "explain.plan")
        self.assertEqual(chat["project"]["via"], "explain.project")
        self.assertEqual(chat["theme"]["via"], "explain.theme")
        self.assertEqual(chat["plan"]["via"], "explain.plan")

    def test_chat_project_and_plan_are_stable(self):
        chat = self.out["chat"]
        self.assertEqual(chat["project"]["text"], chat["projectAgain"]["text"])
        self.assertIn("seed ", chat["project"]["text"])
        self.assertIn("writes: no file", chat["project"]["text"])
        self.assertIn("build a platformer game", chat["plan"]["text"])
        self.assertNotIn("explain this project", chat["plan"]["text"])

    def test_store_routes_write_only_the_bounded_stores(self):
        chat = self.out["chat"]
        self.assertIn("stored in context · explain/project", chat["contextStore"]["text"])
        self.assertIn("explain · project", chat["contextStored"])
        self.assertIn("stored in journal · explain/project", chat["journalStore"]["text"])
        self.assertTrue(chat["journalStored"])
        self.assertEqual(chat["journalStored"][0]["topic"], "explain project")
        self.assertIn("explain project", chat["journalAnswer"]["text"])

    def test_explain_routes_never_touch_the_network(self):
        self.assertEqual(self.out["chat"]["fetches"], 0,
                         "an explain route made a network call")
        with open(os.path.join(WEB, "explain.js"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotRegex(source, r"\bfetch\s*\(")
        self.assertNotIn("import(", source)
        self.assertNotIn("localStorage", source)


class PythonRendererTest(unittest.TestCase):
    def test_renderer_is_byte_identical_twice(self):
        for state in explain.states():
            first = explain.render(state["target"], state["input"])
            second = explain.render(state["target"], state["input"])
            self.assertEqual(first, second, state["name"])

    def test_project_renderer_names_only_real_files(self):
        for state in explain.states():
            if state["target"] != "project":
                continue
            project = state["input"].get("project")
            if not project:
                continue
            names = {file["name"] for file in project["files"]}
            text = explain.render("project", state["input"])
            for line in text.split("\n"):
                match = re.match(r"^  (\S+) · [\d,]+ bytes · [\d,]+ lines · sha ",
                                 line)
                if match:
                    self.assertIn(match.group(1), names, line)

    def test_renderer_never_writes_a_file(self):
        for state in explain.states():
            text = explain.render(state["target"], state["input"])
            self.assertTrue(
                "writes: no file · r.no-write" in text
                or "… trimmed to " in text,
                state["name"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

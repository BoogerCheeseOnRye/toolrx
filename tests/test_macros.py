#!/usr/bin/env python3
"""Step 67: named plan macros.

`toolrx/macros.json` is the only source of the `macro.*` routes and the
expansion data. `toolrx/web/macros.js` is the pure browser twin of
`toolrx/macros.py`. These tests check the table, then drive the real modules in
Node: every fixture state renders byte-identically twice, previews stage the
exact steps without writing, a staged list can be edited without changing the
macro, recursion and over-cap expansions refuse with named reasons, and no
macro route touches the network.
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
FIXTURE = os.path.join(HERE, "fixtures", "macros.json")
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import envelope  # noqa: E402
import macros  # noqa: E402

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
  'thinking.js', 'explain.js', 'verify.js', 'macros.js', 'repair.js',
  'trace.js', 'journal.js', 'workspace.js', 'events.js', 'style.js',
  'context.js', 'skills.js', 'templates.js', 'patches.js', 'engine2d.js',
  'engine2d.embed.js', 'engine3d.js', 'engine3d.embed.js', 'worldgen.js',
  'worldgen.embed.js', 'rpg2.js', 'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

const ask = async q => {
  const list = await self.toolrxWeb.prompt(q);
  return list.map(r => ({
    step: r.step, text: String(r.text || ''), via: r.via || '',
    error: !!r.error,
  }));
};

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const out = { routes: [], pure: {}, macros: {}, chat: {}, fetches: 0 };
  const M = self.toolrxMacros;
  const limits = {
    steps: self.toolrxLimits.planSteps,
    chars: self.toolrxLimits.planChars,
    single: self.toolrxLimits.singleChars,
  };

  FIXTURE.cases.forEach(c => {
    const hit = self.toolrxSkills.match(c.text);
    out.routes.push({ text: c.text, want: c.op, got: hit ? hit.op : null });
  });

  FIXTURE.states.forEach(state => {
    const table = state.table || FIXTURE.table;
    const render = () => {
      if (state.kind === 'list') return M.listText(table);
      if (state.kind === 'edit') {
        return M.editText(M.check(state.macro, state.steps, state.limits),
                          state.limits);
      }
      if (state.kind === 'check') {
        return M.previewText(M.check(state.macro, state.steps, state.limits),
                             state.limits);
      }
      return M.previewText(M.expand(table, state.macro, state.limits),
                           state.limits);
    };
    out.pure[state.name] = { first: render(), second: render(),
                             want: state.want };
  });

  out.macros.names = FIXTURE.table.macros.map(m => m.name);
  out.macros.expanded = FIXTURE.table.macros.map(m => {
    const first = M.expand(FIXTURE.table, m.name, limits);
    const second = M.expand(FIXTURE.table, m.name, limits);
    return { name: m.name, steps: m.steps, first, second };
  });

  self.toolrxWeb.reset();
  const fetchBefore = fetches;
  out.chat.build = await ask('build a shooter');
  out.chat.bytesBefore = self.toolrxWeb.projectBytes();
  out.chat.preview = await ask('preview macro standard shooter growth');
  out.chat.bytesAfterPreview = self.toolrxWeb.projectBytes();
  out.chat.previewAgain = await ask('preview macro standard shooter growth');
  out.chat.run = await ask('run macro standard shooter growth');
  out.chat.list = await ask('show macros');
  out.chat.missing = await ask('preview macro no such macro');
  out.chat.editNoPending = await ask('edit the macro plan to add save system');
  out.chat.preview2 = await ask('preview macro add inventory + save + ui');
  out.chat.edit = await ask(
    'edit the macro plan to add audio system | add weather system');
  out.chat.yes = await ask('yes');
  out.chat.runOriginal = await ask('run macro add inventory + save + ui');
  out.chat.preview3 = await ask('preview macro polish pass');
  out.chat.cancel = await ask('no');
  out.chat.conversation = await ask('show conversation');
  out.chat.fetches = fetches - fetchBefore;
  console.log(JSON.stringify(out));
})().catch(e => {
  console.error(e && e.stack || String(e));
  process.exit(1);
});
"""


class TableTest(unittest.TestCase):
    def test_table_is_valid_and_unique(self):
        table = macros.load()
        self.assertEqual(table["version"], 1)
        self.assertEqual(len(table["macros"]), 5)
        entries = list(macros.entries())
        self.assertEqual(len(entries), 60)
        ids = [entry["id"] for entry in entries]
        self.assertEqual(len(ids), len(set(ids)))
        patterns = [entry["re"] for entry in entries]
        self.assertEqual(len(patterns), len(set(patterns)))
        for entry in entries:
            self.assertEqual(entry["c"], "macro")
            self.assertTrue(entry["op"].startswith("macro."))

    def test_fixture_is_current(self):
        doc = macros.fixture()
        self.assertTrue(os.path.exists(FIXTURE),
                        "run python3 toolrx/macros.py --write")
        with open(FIXTURE, encoding="utf-8") as fh:
            current = json.load(fh)
        self.assertEqual(current, doc,
                         "macro fixture drifted: run python3 toolrx/macros.py --write")
        self.assertEqual(doc["count"], len(doc["cases"]))
        self.assertEqual(doc["ops"], {
            "macro.edit": 6,
            "macro.list": 6,
            "macro.preview": 24,
            "macro.run": 24,
        })

    def test_no_new_cap_and_no_new_tool(self):
        data = envelope.load()
        self.assertEqual(data["planSteps"], 40)
        self.assertEqual(data["planChars"], 8000)
        self.assertEqual(len(envelope._RANGES), 56)
        self.assertFalse([key for key in data if key.startswith("macro")])
        runtime = macros.runtime()
        self.assertEqual(runtime["version"], 1)
        self.assertEqual([m["name"] for m in runtime["macros"]],
                         [m["name"] for m in macros.load()["macros"]])


@unittest.skipUnless(NODE, "node is not installed")
class BrowserMacroTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", JS, WEB, os.path.join(WEB, "commands.json"),
             os.path.join(CORE, "micro_model.json"), FIXTURE],
            capture_output=True, text=True, timeout=240)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-4000:])
        cls.out = json.loads(proc.stdout)
        with open(FIXTURE, encoding="utf-8") as fh:
            cls.fixture = json.load(fh)

    def test_every_route_resolves_to_its_macro_op(self):
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

    def test_every_macro_expands_literally_twice(self):
        for item in self.out["macros"]["expanded"]:
            self.assertTrue(item["first"]["ok"], item["name"])
            self.assertEqual(item["first"], item["second"], item["name"])
            self.assertEqual(item["first"]["steps"], item["steps"], item["name"])
            self.assertEqual(item["first"]["total"], len(item["steps"]),
                             item["name"])

    def test_preview_stages_the_exact_steps_without_writing(self):
        chat = self.out["chat"]
        self.assertEqual(chat["bytesBefore"], chat["bytesAfterPreview"])
        preview = chat["preview"][-1]
        self.assertEqual(preview["via"], "macro.preview")
        self.assertFalse(preview["error"])
        for step in self.fixture["table"]["macros"][0]["steps"]:
            self.assertIn(step, preview["text"])
        self.assertIn("r.macro-preview", preview["text"])
        self.assertEqual(chat["previewAgain"][-1]["text"], preview["text"])

    def test_run_expands_exactly_and_never_replans(self):
        chat = self.out["chat"]
        steps = self.fixture["table"]["macros"][0]["steps"]
        self.assertEqual(len(chat["run"]), len(steps))
        self.assertEqual([r["step"] for r in chat["run"]], steps)
        self.assertIn("macro · standard shooter growth · 3 steps",
                      chat["run"][0]["text"])
        self.assertFalse(any(r["error"] for r in chat["run"]))
        self.assertNotIn("macro.run", [r["via"] for r in chat["run"]])

    def test_list_names_every_macro(self):
        last = self.out["chat"]["list"][-1]
        self.assertEqual(last["via"], "macro.list")
        for name in self.out["macros"]["names"]:
            self.assertIn(name, last["text"])

    def test_missing_and_unstaged_refusals_are_named(self):
        chat = self.out["chat"]
        missing = chat["missing"][-1]
        self.assertTrue(missing["error"])
        self.assertIn("r.macro-missing", missing["text"])
        unstaged = chat["editNoPending"][-1]
        self.assertTrue(unstaged["error"])
        self.assertIn("r.macro-pending", unstaged["text"])

    def test_edit_changes_only_the_staged_list(self):
        chat = self.out["chat"]
        edited = ["add audio system", "add weather system"]
        edit = chat["edit"][-1]
        self.assertEqual(edit["via"], "macro.edit")
        self.assertFalse(edit["error"])
        for step in edited:
            self.assertIn(step, edit["text"])
        self.assertIn("r.macro-immutable", edit["text"])
        self.assertEqual([r["step"] for r in chat["yes"]], edited)
        self.assertFalse(any(r["error"] for r in chat["yes"]))
        original = self.fixture["table"]["macros"][1]["steps"]
        self.assertEqual([r["step"] for r in chat["runOriginal"]], original)
        self.assertEqual(len(chat["runOriginal"]), len(original))

    def test_reject_cancels_the_staged_macro(self):
        chat = self.out["chat"]
        self.assertIn("nothing was run", chat["cancel"][-1]["text"].lower())
        self.assertIn("pending: none", chat["conversation"][-1]["text"])

    def test_no_network_on_the_default_path(self):
        self.assertEqual(self.out["chat"]["fetches"], 0)


if __name__ == "__main__":
    unittest.main()

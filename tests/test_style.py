#!/usr/bin/env python3
"""Step 58: adaptive response style.

`toolrx/style.json` is the only source of the `style.set` and `style.show`
routes; it feeds the catalog and `tests/fixtures/style.json`. The pure module
`toolrx/web/style.js` wraps an already-executed exact result. These tests check
the table, the pure wrapper, the cap, persistence, the three styles, unchanged
refusals, identical files, and the no-network promise.
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
FIXTURE = os.path.join(HERE, "fixtures", "style.json")
NODE = shutil.which("node")

sys.path.insert(0, CORE)

import style  # noqa: E402

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
  'thinking.js', 'repair.js', 'trace.js', 'journal.js', 'style.js',
  'skills.js', 'templates.js', 'context.js', 'lang.js', 'patches.js',
  'engine2d.js', 'engine2d.embed.js', 'engine3d.js', 'engine3d.embed.js',
  'worldgen.js', 'worldgen.embed.js', 'rpg2.js', 'rpg2.embed.js', 'sandbox.js',
]) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

const S = self.toolrxStyle;
const base = {
  step: '12 plus 30', text: '42', via: 'math.binary',
  desc: '{a} plus {b}', exact: true, error: false,
};

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const out = { routes: [], pure: {}, chat: {} };

  FIXTURE.cases.forEach(c => {
    const hit = self.toolrxSkills.match(c.text);
    out.routes.push({
      text: c.text, want: c.op, got: hit ? hit.op : null,
      wantArgs: c.args, gotArgs: hit ? hit.args : null,
    });
  });

  out.pure.normalize = S.STYLES.map(name => S.normalize(name));
  out.pure.upper = S.normalize('EXPLANATORY');
  out.pure.unknown = S.normalize('verbose');
  out.pure.concise = S.apply([base], 'concise', { maxChars: 600 })[0];
  out.pure.explanatory = S.apply([base], 'explanatory', { maxChars: 600 })[0];
  out.pure.explanatoryAgain = S.apply([base], 'explanatory', { maxChars: 600 })[0];
  out.pure.tutorial = S.apply([base], 'tutorial', { maxChars: 600 })[0];
  out.pure.trim = S.apply([base], 'tutorial', { maxChars: 80 })[0];
  out.pure.tiny = S.apply([base], 'tutorial', { maxChars: 8 })[0];
  const errorResult = Object.assign({}, base, {
    text: 'division by zero', error: true, exact: false,
  });
  out.pure.error = S.apply([errorResult], 'tutorial', { maxChars: 600 })[0];
  out.pure.errorSame = out.pure.error.text === errorResult.text;
  const chatResult = Object.assign({}, base, { via: 'chat', exact: true });
  out.pure.chat = S.apply([chatResult], 'tutorial', { maxChars: 600 })[0];
  out.pure.chatSame = out.pure.chat.text === chatResult.text;
  const routerResult = Object.assign({}, base, {
    via: 'router.math.sum', exact: false,
  });
  out.pure.router = S.apply([routerResult], 'tutorial', { maxChars: 600 })[0];
  out.pure.routerSame = out.pure.router.text === routerResult.text;
  const plan = [base, Object.assign({}, base, {
    step: 'add a theme toggle', text: 'added', via: 'project.themeToggle',
    desc: 'add a theme toggle',
  })];
  plan.plan = ['12 plus 30', 'add a theme toggle'];
  plan.failedAt = -1;
  const wrappedPlan = S.apply(plan, 'explanatory', { maxChars: 600 });
  out.pure.multi = {
    count: wrappedPlan.length,
    plan: wrappedPlan.plan,
    failedAt: wrappedPlan.failedAt,
    texts: wrappedPlan.map(r => r.text),
    vias: wrappedPlan.map(r => r.via),
  };
  out.pure.show = S.showText('tutorial', { maxChars: 600 });
  out.pure.set = S.setText('explanatory', { maxChars: 600 });

  const ask = async q => (await self.toolrxWeb.prompt(q)).map(r => ({
    step: r.step, text: String(r.text || ''), via: r.via || '',
    error: !!r.error, exact: !!r.exact, style: r.style || null,
  }));
  const fetchBefore = fetches;

  // Default is concise, so the exact output is unchanged.
  localStorage.removeItem('toolrx.reply.style');
  self.toolrxWeb.reset();
  out.chat.defaultStyle = self.toolrxWeb.style();
  out.chat.concise = (await ask('12 plus 30'))[0];
  out.chat.showConcise = (await ask('show style'))[0];
  out.chat.matchMath = self.toolrxSkills.match('12 plus 30');
  out.chat.matchBuild = self.toolrxSkills.match('build a platformer game');
  out.chat.badRoute = self.toolrxSkills.match('style verbose');

  await ask('style explanatory');
  out.chat.explanatory = (await ask('12 plus 30'))[0];
  out.chat.showExplanatory = (await ask('show style'))[0];
  await ask('style tutorial');
  out.chat.tutorial = (await ask('12 plus 30'))[0];
  out.chat.active = self.toolrxWeb.style();
  out.chat.stored = localStorage.getItem('toolrx.reply.style');

  // Simulate a reload by writing the persisted key directly.
  localStorage.setItem('toolrx.reply.style', 'explanatory');
  out.chat.afterReload = self.toolrxWeb.style();
  out.chat.afterReloadAsk = (await ask('12 plus 30'))[0];

  // Refusals are byte-identical under every style.
  await ask('style explanatory');
  out.chat.refusalExplanatory = (await ask('divide 4 by 0'))[0];
  await ask('style concise');
  out.chat.refusalConcise = (await ask('divide 4 by 0'))[0];

  // The same build under each style writes the same files.
  const buildOnce = async (name) => {
    self.toolrxWeb.reset();
    await ask('style ' + name);
    const r = (await ask('build a platformer game'))[0];
    const p = self.toolrxWeb.project();
    return {
      via: r.via, error: !!r.error, style: r.style,
      slug: p && p.slug, files: p && p.files,
    };
  };
  out.chat.builds = {
    concise: await buildOnce('concise'),
    explanatory: await buildOnce('explanatory'),
    tutorial: await buildOnce('tutorial'),
  };
  out.chat.limits = self.toolrxWeb.limits();

  out.chat.fetches = fetches - fetchBefore;
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is not installed")
class StyleTest(unittest.TestCase):
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
        self.assertEqual(current, style.fixture(),
                         "style fixture drifted; run toolrx/style.py --write")

    def test_every_route_resolves_with_its_arguments(self):
        self.assertTrue(self.out["routes"])
        for case in self.out["routes"]:
            self.assertEqual(case["got"], case["want"], case)
            self.assertEqual(case["gotArgs"], case["wantArgs"], case)

    def test_table_rejects_an_unknown_style(self):
        table = {
            "version": 1,
            "intents": {
                "set": {
                    "op": "style.set", "summary": "s", "example": "loud",
                    "styles": ["loud"], "templates": ["style {style}"],
                },
                "show": {
                    "op": "style.show", "summary": "s", "example": "show style",
                    "templates": [], "bare": ["show style"],
                },
            },
        }
        with self.assertRaises(ValueError):
            style._intents(table)

    # -------------------------------------------------------------- pure ---
    def test_normalize_accepts_only_the_three_styles(self):
        self.assertEqual(self.out["pure"]["normalize"],
                         ["concise", "explanatory", "tutorial"])
        self.assertEqual(self.out["pure"]["upper"], "explanatory")
        self.assertIsNone(self.out["pure"]["unknown"])

    def test_concise_adds_nothing(self):
        out = self.out["pure"]["concise"]
        self.assertEqual(out["text"], "42")
        self.assertEqual(out["via"], "math.binary")
        self.assertEqual(out["style"]["rule"], "r.style-concise")
        self.assertEqual(out["style"]["added"], 0)

    def test_explanatory_wraps_without_changing_the_result(self):
        out = self.out["pure"]["explanatory"]
        self.assertTrue(out["text"].startswith(
            "style · explanatory · math.binary\n\n42"))
        self.assertIn("why: the exact math.binary command ran locally", out["text"])
        self.assertIn("no model and no network", out["text"])
        self.assertEqual(out["via"], "math.binary")
        self.assertEqual(out["exact"], True)
        self.assertEqual(out["desc"], "{a} plus {b}")
        self.assertNotIn("{a}", out["text"])
        self.assertLessEqual(out["style"]["added"], 600)
        self.assertFalse(out["style"]["trimmed"])
        self.assertEqual(out, self.out["pure"]["explanatoryAgain"])

    def test_tutorial_adds_one_next_step(self):
        out = self.out["pure"]["tutorial"]
        self.assertTrue(out["text"].startswith(
            "style · tutorial · math.binary\n\n42"))
        self.assertIn('try next: change the input, or chain another step', out["text"])
        self.assertIn('say "show limits"', out["text"])
        self.assertEqual(out["style"]["rule"], "r.style-tutorial")
        self.assertLessEqual(out["style"]["added"], 600)

    def test_wrapper_is_capped_and_the_inner_text_survives(self):
        trim = self.out["pure"]["trim"]
        self.assertTrue(trim["style"]["trimmed"])
        self.assertEqual(trim["style"]["rule"], "r.style-trim")
        self.assertIn("42", trim["text"])
        self.assertIn("r.style-trim", trim["text"])
        self.assertLessEqual(trim["style"]["added"], 80)
        tiny = self.out["pure"]["tiny"]
        self.assertIn("42", tiny["text"])
        self.assertLessEqual(tiny["style"]["added"], 8)

    def test_errors_chat_and_router_results_are_never_wrapped(self):
        pure = self.out["pure"]
        self.assertTrue(pure["errorSame"])
        self.assertIsNone(pure["error"].get("style"))
        self.assertTrue(pure["chatSame"])
        self.assertIsNone(pure["chat"].get("style"))
        self.assertTrue(pure["routerSame"])
        self.assertIsNone(pure["router"].get("style"))

    def test_plan_metadata_survives_the_wrapper(self):
        multi = self.out["pure"]["multi"]
        self.assertEqual(multi["count"], 2)
        self.assertEqual(multi["plan"], ["12 plus 30", "add a theme toggle"])
        self.assertEqual(multi["failedAt"], -1)
        self.assertEqual(multi["vias"], ["math.binary", "project.themeToggle"])
        for text in multi["texts"]:
            self.assertIn("style · explanatory", text)

    def test_show_and_set_text_name_the_cap_and_the_invariant(self):
        self.assertIn("style · tutorial · wrapper on", self.out["pure"]["show"])
        self.assertIn("wrapper cap 600 chars", self.out["pure"]["show"])
        self.assertIn("never depend on style", self.out["pure"]["show"])
        self.assertIn("style · explanatory · on", self.out["pure"]["set"])
        self.assertIn("do not change", self.out["pure"]["set"])

    # -------------------------------------------------------------- chat ---
    def test_default_is_concise(self):
        chat = self.out["chat"]
        self.assertEqual(chat["defaultStyle"], "concise")
        self.assertEqual(chat["concise"]["text"], "42")
        self.assertEqual(chat["concise"]["via"], "math.binary")
        self.assertEqual(chat["concise"]["style"]["rule"], "r.style-concise")
        self.assertIn("style · concise · wrapper off", chat["showConcise"]["text"])

    def test_explanatory_and_tutorial_change_only_the_wrapper(self):
        chat = self.out["chat"]
        self.assertTrue(chat["explanatory"]["text"].startswith(
            "style · explanatory · math.binary"))
        self.assertIn("42", chat["explanatory"]["text"])
        self.assertIn("why: the exact math.binary command ran locally",
                      chat["explanatory"]["text"])
        self.assertTrue(chat["tutorial"]["text"].startswith(
            "style · tutorial · math.binary"))
        self.assertIn("try next:", chat["tutorial"]["text"])
        for name in ("concise", "explanatory", "tutorial"):
            self.assertEqual(chat[name]["via"], "math.binary", name)
        self.assertIn("style · explanatory · wrapper on",
                      chat["showExplanatory"]["text"])

    def test_style_persists_across_a_reload(self):
        chat = self.out["chat"]
        self.assertEqual(chat["active"], "tutorial")
        self.assertEqual(chat["stored"], "tutorial")
        self.assertEqual(chat["afterReload"], "explanatory")
        self.assertTrue(chat["afterReloadAsk"]["text"].startswith(
            "style · explanatory · math.binary"))

    def test_refusals_are_byte_identical_under_every_style(self):
        chat = self.out["chat"]
        self.assertTrue(chat["refusalExplanatory"]["error"])
        self.assertTrue(chat["refusalConcise"]["error"])
        self.assertEqual(chat["refusalExplanatory"]["text"],
                         chat["refusalConcise"]["text"])
        self.assertEqual(chat["refusalExplanatory"]["via"],
                         chat["refusalConcise"]["via"])
        self.assertIsNone(chat["refusalExplanatory"]["style"])

    def test_unknown_style_does_not_route(self):
        self.assertIsNone(self.out["chat"]["badRoute"])

    def test_same_build_writes_the_same_files_under_every_style(self):
        builds = self.out["chat"]["builds"]
        self.assertFalse(builds["concise"]["error"])
        self.assertEqual(builds["concise"]["via"], "build")
        self.assertEqual(builds["explanatory"]["via"], "build")
        self.assertEqual(builds["tutorial"]["via"], "build")
        self.assertEqual(builds["concise"]["files"], builds["explanatory"]["files"])
        self.assertEqual(builds["concise"]["files"], builds["tutorial"]["files"])
        self.assertEqual(builds["explanatory"]["style"]["name"], "explanatory")
        self.assertEqual(builds["tutorial"]["style"]["name"], "tutorial")

    def test_the_cap_is_the_named_limit(self):
        self.assertEqual(self.out["chat"]["limits"]["style"], 600)

    def test_style_never_touches_the_network(self):
        self.assertEqual(self.out["chat"]["fetches"], 0,
                         "a style route made a network call")
        with open(os.path.join(WEB, "style.js"), encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("XMLHttpRequest", source)
        self.assertNotRegex(source, r"\bfetch\s*\(")
        self.assertNotIn("import(", source)
        self.assertNotIn("localStorage", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

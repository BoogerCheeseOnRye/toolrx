#!/usr/bin/env python3
"""Behaviour tests for the browser skills + build templates.

The Pages build runs `toolrx/web/skills.js` directly, so this exercises the real
code in Node: command matching, multi-step planning, `prev` threading, and the
deterministic HTML templates. No server and no browser required.
"""

import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NODE = shutil.which("node")

JS = r"""
const fs = require('fs');
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
global.CustomEvent = class { constructor(type, opts) { this.type = type; this.detail = opts && opts.detail; } };
global.dispatchEvent = () => {};
global.toolrxRouter = { load: () => ({}), route: () => ({ tool: 'none', args: {}, confidence: 0 }) };
eval(fs.readFileSync(process.argv[2], 'utf8'));
eval(fs.readFileSync(process.argv[3], 'utf8'));
eval(fs.readFileSync(process.argv[4], 'utf8'));

(async () => {
  await self.toolrxSkills.init('commands.json');
  const files = { 'notes.txt': 'one two three four five' };
  const state = { html: '', kind: '', theme: 'dark', files: {} };
  const memory = {};
  const ctx = {
    fs: {
      exists: p => Object.prototype.hasOwnProperty.call(files, p),
      read: p => files[p],
      write: (p, c) => { files[p] = String(c); return 'wrote ' + p; },
      list: () => Object.keys(files).join('\n'),
    },
    preview: () => state.html,
    theme: t => { state.theme = t; return true; },
    build: (kind, desc) => {
      const p = self.toolrxTemplates.project(kind, desc, { theme: state.theme });
      state.html = p.html;
      state.kind = p.kind;
      state.files = p.files;
      Object.keys(p.files).forEach(k => { files['projects/' + p.slug + '/' + k] = p.files[k]; });
      return 'built ' + Object.keys(p.files).join(',');
    },
    architecture: (kind, desc) => self.toolrxTemplates.architecture(kind, desc, { theme: state.theme }),
    blueprint: (kind, desc) => ({ text: self.toolrxTemplates.brief(kind, desc) }),
    project: {
      new: n => 'created ' + n, list: () => 'proj-a\nproj-b', open: s => 'opened ' + s,
      rename: (s, n) => 'renamed ' + s + ' to ' + n, remove: s => 'deleted ' + s,
      files: () => 'index.html\nstyles.css\napp.js',
    },
    chat: (who, text) => text, history: () => [{ who: 'toolrx', text: 'earlier' }],
    memory: { get: k => memory[k], set: (k, v) => { memory[k] = v; return v; } },
    web: {
      search: async q => ({ text: 'summary about ' + q + '.', source: 'https://en.wikipedia.org/wiki/' + q }),
      define: async w => ({ text: w + ': a test definition', source: 'https://dictionaryapi.dev/' }),
      weather: async p => ({ text: p + ': 7°C · clear', source: 'https://open-meteo.com/' }),
      answer: async q => ({ text: 'instant answer for ' + q, source: 'https://duckduckgo.com/' }),
    },
    fallback: async step => {
      const m = /^read\s+(.+)$/i.exec(step);
      const text = m && files[m[1]] ? files[m[1]] : ('fallback:' + step);
      return { text: text, error: false, via: 'router.test' };
    },
  };
  const run = async q => {
    const res = await self.toolrxSkills.runPrompt(q, ctx);
    return res.map(r => ({
      step: r.step, text: r.text, error: !!r.error, via: r.via || '',
      tool: r.tool || '', args: r.args || null, source: r.source || '',
    }));
  };
  const out = {};
  out.count = self.toolrxSkills.count();
  out.multiply = await run('multiply 67 and 420');
  out.square = await run('square 67');
  out.chain = await run('convert 5 km to miles then square the result');
  out.read = await run('read notes.txt then count the words');
  out.pronoun = await run('capital of france then uppercase it');
  out.steps = self.toolrxSkills.splitPrompt('one then two; three -> four');
  out.build = await run('build a calculator app');
  out.buildHtml = state.html;
  out.calcFiles = Object.keys(state.files).sort();
  state.html = '';
  out.build2 = await run('build a calculator app');
  out.buildSame = out.buildHtml === state.html;
  state.html = '';
  out.buildTodo = await run('build me a todo list');
  out.todoHtml = state.html;
  out.games = {};
  for (const kind of ['rpg', 'platformer', 'snake', 'breakout', 'pong', '2048',
                      'minesweeper', 'tetris', 'maze', 'adventure', 'typing']) {
    const r = await run('build a ' + kind + ' game');
    out.games[kind] = { kind: state.kind, files: Object.keys(state.files).sort(),
                        html: state.html.length, ok: !r[0].error };
  }
  out.sites = {};
  for (const [q, kind] of [['build a social media website', 'social'],
                           ['build a blog', 'blog'],
                           ['build a forum website', 'forum'],
                           ['build a chat app', 'chat']]) {
    const r = await run(q);
    out.sites[kind] = { kind: state.kind, files: Object.keys(state.files).sort(),
                        html: state.html.length, ok: !r[0].error };
  }
  out.plan = await run('plan an rpg');
  out.blueprint = await run('blueprint a todo app');
  out.newProject = await run('new project notes');
  out.listProjects = await run('list projects');
  out.openProject = await run('open project notes');
  out.deleteProject = await run('delete this project');
  out.showFiles = await run('show project files');
  out.chatHello = await run('hello');
  out.chatFeel = await run('i feel anxious');
  out.chatName = await run('remember my name is ada');
  out.chatWho = await run('what is my name');
  out.chatJoke = await run('tell me a joke');
  out.chatGreetings = ['hi', 'hello', 'hey'].map(q => self.toolrxSkills.chat(q, ctx));
  out.chatUnknown = self.toolrxSkills.chat('blorp wobble', ctx);
  out.chatFeelings = ['i am stuck', 'i feel anxious', 'i am tired', 'i feel lost']
    .map(q => self.toolrxSkills.chat(q, ctx));
  out.variants = {};
  for (const q of ['build a tetris game with 3d elements',
                   'build an rpg based on king arthur',
                   'build an rpg based on india']) {
    const r = await run(q);
    out.variants[q] = {
      ok: !r[0].error, via: r[0].via || '',
      kind: state.kind,
      html: state.html,
      title: ((state.html.match(/<h1>([^<]*)<\/h1>/) || [])[1] || ''),
      files: Object.keys(state.files).sort(),
      css: state.files['styles.css'] || '',
      js: state.files['app.js'] || '',
    };
  }
  // Real sandbox rename flow: build one RPG, then refer to it by a stale name
  // and by "it". The same project must be re-themed, not duplicated.
  await self.toolrxWeb.init('model.json');
  self.toolrxWeb.reset();
  out.sandbox = {};
  const h1 = html => ((String(html).match(/<h1>([^<]*)<\/h1>/) || [])[1] || '');
  out.sandbox.build = (await self.toolrxWeb.prompt('build an rpg based on king arthur'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  let p = self.toolrxWeb.project();
  out.sandbox.first = { slug: p.slug, name: p.name, h1: h1(p.html), desc: p.desc };
  out.sandbox.stale = (await self.toolrxWeb.prompt('change the name from verdant wood rpg to india'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  p = self.toolrxWeb.project();
  out.sandbox.afterStale = {
    slug: p.slug, name: p.name, h1: h1(p.html), desc: p.desc,
    css: self.toolrxWeb.projectFile(p.slug, 'styles.css'),
    js: self.toolrxWeb.projectFile(p.slug, 'app.js'),
  };
  out.sandbox.pronoun = (await self.toolrxWeb.prompt('rename it to camelot'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  p = self.toolrxWeb.project();
  out.sandbox.afterPronoun = { slug: p.slug, name: p.name, h1: h1(p.html), desc: p.desc };
  out.wiki = await run('wikipedia ada lovelace');
  out.define = await run('define serendipity');
  out.weather = await run('weather in reykjavik');
  out.summaryChain = await run('wikipedia ada lovelace then summarize it');
  console.log(JSON.stringify(out));
})();
"""


@unittest.skipUnless(NODE, "node is not installed")
class SkillsBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", JS,
             os.path.join(ROOT, "toolrx", "web", "commands.json"),
             os.path.join(ROOT, "toolrx", "web", "skills.js"),
             os.path.join(ROOT, "toolrx", "web", "templates.js"),
             os.path.join(ROOT, "toolrx", "web", "sandbox.js")],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-3000:])
        cls.out = json.loads(proc.stdout)

    def test_library_loaded(self):
        self.assertGreaterEqual(self.out["count"], 2500)

    def test_math_prompts(self):
        self.assertEqual(self.out["multiply"][0]["text"], "28140")
        self.assertEqual(self.out["square"][0]["text"], "4489")
        self.assertFalse(self.out["multiply"][0]["error"])

    def test_multi_step_threads_previous_output(self):
        steps = self.out["chain"]
        self.assertEqual(len(steps), 2)
        self.assertIn("3.1068", steps[0]["text"])
        value = float(steps[1]["text"])
        self.assertAlmostEqual(value, 3.1068559612 ** 2, places=4)

    def test_previous_file_feeds_text_count(self):
        steps = self.out["read"]
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[1]["text"], "5 words")

    def test_pronoun_uses_previous_result(self):
        steps = self.out["pronoun"]
        self.assertEqual(steps[0]["text"], "Paris")
        self.assertEqual(steps[1]["text"], "PARIS")

    def test_planner_splits_on_semicolon_and_arrow(self):
        self.assertEqual(self.out["steps"], ["one", "two", "three", "four"])

    def test_build_produces_a_real_page(self):
        self.assertTrue(self.out["buildHtml"].startswith("<!doctype html>"))
        self.assertIn("<title>Calculator", self.out["buildHtml"])
        self.assertIn("</html>", self.out["buildHtml"])
        self.assertIn("<title>Todo list", self.out["todoHtml"])
        self.assertFalse(self.out["build"][0]["error"])

    def test_build_is_deterministic(self):
        self.assertTrue(self.out["buildSame"], "same prompt produced a different page")

    def test_build_writes_a_multi_file_project(self):
        files = self.out["calcFiles"]
        self.assertEqual(files, ["ARCHITECTURE.md", "README.md", "app.js", "index.html", "styles.css"])
        # styles and script must be linked, not inlined
        html = self.out["buildHtml"]
        self.assertIn('href="styles.css"', html)
        self.assertIn('src="app.js"', html)
        self.assertNotIn("<style>", html)

    def test_games_build_with_real_files(self):
        expected = {"rpg", "platformer", "snake", "breakout", "pong", "2048",
                    "minesweeper", "tetris", "maze", "adventure", "typing"}
        for name in expected:
            g = self.out["games"][name]
            self.assertTrue(g["ok"], name)
            self.assertEqual(g["kind"], name, name)
            self.assertIn("index.html", g["files"], name)
            self.assertIn("app.js", g["files"], name)
            self.assertGreater(g["html"], 1000, name)

    def test_3d_build_variant_has_real_3d_markers(self):
        v = self.out["variants"]["build a tetris game with 3d elements"]
        self.assertTrue(v["ok"])
        self.assertEqual(v["kind"], "tetris")
        self.assertEqual(v["title"], "Tetris 3D")
        self.assertIn("perspective", v["css"])
        self.assertIn("rotateX", v["css"])
        # the renderer extrudes each block with highlight and shadow faces
        self.assertIn("D3=true", v["js"])
        self.assertIn("rgba(255,255,255,.34)", v["js"])

    def test_rpg_settings_produce_different_previews(self):
        arthur = self.out["variants"]["build an rpg based on king arthur"]
        india = self.out["variants"]["build an rpg based on india"]
        self.assertEqual(arthur["kind"], "rpg")
        self.assertEqual(india["kind"], "rpg")
        self.assertEqual(arthur["title"], "Camelot RPG")
        self.assertEqual(india["title"], "Bharata RPG")
        self.assertNotEqual(arthur["html"], india["html"])
        self.assertIn("Black Knight", arthur["js"])
        self.assertIn("Asura King", india["js"])
        self.assertIn("#2f5d43", arthur["css"] + arthur["js"])
        self.assertIn("#3f6b4a", india["css"] + india["js"])

    def test_sandbox_rename_rethemes_the_same_project(self):
        s = self.out["sandbox"]
        self.assertEqual(s["build"][0]["via"], "build")
        self.assertEqual(s["first"]["slug"], "camelot-rpg")
        self.assertEqual(s["first"]["h1"], "Camelot RPG")
        self.assertEqual(s["stale"][0]["via"], "project.rename")
        # stale old name falls back to the active project, not a new project
        self.assertEqual(s["afterStale"]["slug"], s["first"]["slug"])
        self.assertEqual(s["afterStale"]["name"], "India")
        self.assertEqual(s["afterStale"]["h1"], "Bharata RPG")
        self.assertIn("Asura King", s["afterStale"]["js"])
        # "it" resolves to the active project and re-themes again
        self.assertEqual(s["pronoun"][0]["via"], "project.rename")
        self.assertEqual(s["afterPronoun"]["slug"], s["first"]["slug"])
        self.assertEqual(s["afterPronoun"]["name"], "Camelot")
        self.assertEqual(s["afterPronoun"]["h1"], "Camelot RPG")

    def test_site_templates_build(self):
        for name in ("social", "blog", "forum", "chat"):
            s = self.out["sites"][name]
            self.assertTrue(s["ok"], name)
            self.assertEqual(s["kind"], name, name)
            self.assertIn("index.html", s["files"], name)
            self.assertIn("ARC" + "HITECTURE.md", s["files"], name)

    def test_architecture_and_blueprint(self):
        plan = self.out["plan"][0]
        self.assertFalse(plan["error"])
        self.assertIn("build order", plan["text"])
        self.assertIn("state", plan["text"])
        self.assertIn("modules", self.out["blueprint"][0]["text"].lower())
        self.assertIn("state", self.out["blueprint"][0]["text"].lower())

    def test_project_commands(self):
        self.assertEqual(self.out["newProject"][0]["via"], "project.new")
        self.assertEqual(self.out["listProjects"][0]["via"], "project.list")
        self.assertEqual(self.out["openProject"][0]["via"], "project.open")
        self.assertEqual(self.out["deleteProject"][0]["via"], "project.delete")
        self.assertEqual(self.out["showFiles"][0]["via"], "project.files")
        self.assertIn("index.html", self.out["showFiles"][0]["text"])

    def test_chat_is_conversational_and_remembers_a_name(self):
        self.assertEqual(self.out["chatHello"][0]["via"], "chat")
        self.assertTrue(self.out["chatHello"][0]["text"].strip())
        self.assertEqual(self.out["chatFeel"][0]["via"], "chat")
        self.assertIn("anxious", self.out["chatFeel"][0]["text"].lower())
        self.assertIn("Ada", self.out["chatName"][0]["text"])
        self.assertIn("Ada", self.out["chatWho"][0]["text"])
        self.assertTrue(self.out["chatJoke"][0]["text"].strip())

    def test_casual_greetings_are_not_therapy_flavored(self):
        for text in self.out["chatGreetings"]:
            low = text.lower()
            self.assertNotIn("but listening", low)
            self.assertNotIn("what's on your mind", low)
            self.assertNotIn("what is on your mind", low)
            self.assertTrue(any(w in low for w in ("build", "make", "tool")), text)

    def test_unknown_chat_is_practical_not_a_reflection(self):
        text = self.out["chatUnknown"]
        self.assertIn("matching command", text.lower())
        self.assertIn("build", text.lower())
        self.assertNotIn("what's underneath", text.lower())
        self.assertNotIn("say more", text.lower())

    def test_feeling_replies_are_always_well_formed(self):
        for text in self.out["chatFeelings"]:
            self.assertTrue(text.strip())
            self.assertNotIn("undefined", text.lower())

    def test_web_results_carry_a_source(self):
        wiki = self.out["wiki"][0]
        self.assertEqual(wiki["via"], "web.search")
        self.assertIn("ada lovelace", wiki["text"])
        self.assertTrue(wiki["source"].startswith("https://"))
        self.assertEqual(self.out["define"][0]["via"], "web.define")
        self.assertEqual(self.out["weather"][0]["via"], "web.weather")
        chain = self.out["summaryChain"]
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[1]["via"], "text.summarize")
        self.assertIn("summary about ada lovelace", chain[1]["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

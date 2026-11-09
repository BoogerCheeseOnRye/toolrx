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
eval(fs.readFileSync(process.argv[2], 'utf8'));
eval(fs.readFileSync(process.argv[3], 'utf8'));

(async () => {
  await self.toolrxSkills.init('commands.json');
  const files = { 'notes.txt': 'one two three four five' };
  const state = { html: '', kind: '', theme: 'dark' };
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
      state.html = self.toolrxTemplates.build(kind, desc, { theme: state.theme });
      state.kind = kind;
      return 'built ' + state.html.length + ' bytes';
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
      tool: r.tool || '', args: r.args || null,
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
  state.html = '';
  out.build2 = await run('build a calculator app');
  out.buildSame = out.buildHtml === state.html;
  state.html = '';
  out.buildTodo = await run('build me a todo list');
  out.todoHtml = state.html;
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
             os.path.join(ROOT, "toolrx", "web", "templates.js")],
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


if __name__ == "__main__":
    unittest.main(verbosity=2)

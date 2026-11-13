#!/usr/bin/env python3
"""Behaviour tests for the project store in `toolrx/web/sandbox.js`.

Runs the real browser module in Node with a localStorage stub, so export/import
and the flat workspace mirror are exercised without a browser.
"""

import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NODE = shutil.which("node")
SANDBOX = os.path.join(ROOT, "toolrx", "web", "sandbox.js")

JS = r"""
const fs = require('fs');
global.self = global;
const store = {};
global.localStorage = {
  getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.CustomEvent = class { constructor(type, opts) { this.type = type; this.detail = opts && opts.detail; } };
global.dispatchEvent = () => {};
global.fetch = () => Promise.reject(new Error('network disabled in tests'));
eval(fs.readFileSync(require('path').join(require('path').dirname(process.argv[1]), 'limits.js'), 'utf8'));
eval(fs.readFileSync(process.argv[1], 'utf8'));

const api = self.toolrxWeb;
const out = {};

out.seedProjects = api.projects().length;
out.imported = api.importProject(JSON.stringify({
  format: 'toolrx.project', version: 1,
  project: {
    name: 'Notes', kind: 'notes', desc: 'a test project',
    files: {
      'index.html': '<!doctype html><html><body><h1>Notes</h1></body></html>',
      'styles.css': 'body{font:16px sans-serif}',
      'README.md': '# Notes',
    },
  },
}));
out.active = api.project();
out.list = api.projects();
out.exported = api.exportProject(out.active.slug);

out.second = api.importProject(JSON.stringify({
  name: 'Notes', files: { 'index.html': '<html><body>second</body></html>' },
}));
out.slugs = api.projects().map(p => p.slug).sort();

out.traversal = api.importProject(JSON.stringify({
  name: 'Sneaky', files: { '../../evil.txt': 'x', 'a/b/index.html': '<p>ok</p>' },
}));
out.traversalFiles = api.projects().find(p => p.slug === 'sneaky').files.sort();

out.bad = null;
try { api.importProject('{oops'); } catch (e) { out.bad = e.message; }
out.empty = null;
try { api.importProject('{}'); } catch (e) { out.empty = e.message; }
out.big = null;
try {
  api.importProject(JSON.stringify({ name: 'Big', files: { 'a.txt': 'x'.repeat(200001) } }));
} catch (e) { out.big = e.message; }

out.missing = null;
try { api.exportProject('does-not-exist'); } catch (e) { out.missing = e.message; }

console.log(JSON.stringify(out));
"""


@unittest.skipUnless(NODE, "node is required for the sandbox bridge test")
class SandboxBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([NODE, "-e", JS, SANDBOX], capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr or proc.stdout)
        cls.out = json.loads(proc.stdout)

    def test_import_creates_a_real_project(self):
        self.assertEqual(self.out["seedProjects"], 0)
        self.assertIn("imported", self.out["imported"])
        active = self.out["active"]
        self.assertEqual(active["slug"], "notes")
        self.assertEqual(active["name"], "Notes")
        self.assertEqual(active["kind"], "notes")
        self.assertEqual(active["files"], ["README.md", "index.html", "styles.css"])
        self.assertIn("<h1>Notes</h1>", active["html"])

    def test_export_is_a_portable_document(self):
        doc = json.loads(self.out["exported"])
        self.assertEqual(doc["format"], "toolrx.project")
        self.assertEqual(doc["version"], 1)
        self.assertEqual(doc["project"]["name"], "Notes")
        self.assertEqual(doc["project"]["kind"], "notes")
        self.assertIn("index.html", doc["project"]["files"])
        self.assertIn("README.md", doc["project"]["files"])

    def test_import_never_overwrites(self):
        self.assertIn("notes-2", self.out["slugs"])
        self.assertIn("notes", self.out["slugs"])

    def test_import_sanitizes_file_names(self):
        self.assertEqual(self.out["traversalFiles"], ["evil.txt", "index.html"])

    def test_import_failures_are_explicit(self):
        self.assertIn("valid JSON", self.out["bad"])
        self.assertIn("no project files", self.out["empty"])
        self.assertIn("larger than", self.out["big"])
        self.assertIn("no such project", self.out["missing"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

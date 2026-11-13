#!/usr/bin/env python3
"""Behaviour tests for the project store and the portability bundles.

Runs the real browser modules in Node with a localStorage stub, so export,
import, the workspace bundle, and the flat workspace mirror are exercised
without a browser.
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
CONTEXT = os.path.join(ROOT, "toolrx", "web", "context.js")
LIMITS = os.path.join(ROOT, "toolrx", "web", "limits.js")

JS = r"""
const fs = require('fs');
const path = require('path');
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
const web = path.dirname(process.argv[1]);
eval(fs.readFileSync(path.join(web, 'limits.js'), 'utf8'));
eval(fs.readFileSync(path.join(web, 'context.js'), 'utf8'));
eval(fs.readFileSync(process.argv[1], 'utf8'));

const api = self.toolrxWeb;
const C = self.toolrxContext;
const out = {};
const doc = (project, version) => JSON.stringify({
  format: 'toolrx.project', version: version === undefined ? 2 : version,
  project: project,
});
const refusal = fn => {
  try { fn(); return null; } catch (e) { return e.message; }
};

out.seedProjects = api.projects().length;

// 1. A legacy v1 document still imports, and re-export is v2 with the plan,
// seed, context, limits, and settings attached.
out.imported = api.importProject(doc({
  name: 'Notes', kind: 'notes', desc: 'a test project',
  spec: { kind: 'notes', seed: 42, theme: 'dark' },
  files: {
    'index.html': '<!doctype html><html><body><h1>Notes</h1></body></html>',
    'styles.css': 'body{font:16px sans-serif}',
    'README.md': '# Notes',
  },
}, 1));
out.active = api.project();
out.list = api.projects();
C.set(out.active.slug, 'plan', 'last', C.stable({
  version: 1, steps: ['add a footer', 'add a theme toggle'],
  status: ['done', 'pending'],
}));
C.set(out.active.slug, 'result', 'last', 'query: add a footer\nvia: edit.apply\nok');
out.exported = api.exportProject(out.active.slug);
out.doc = JSON.parse(out.exported);
out.exportVersion = out.doc.version;
out.exportFormat = out.doc.format;
out.projectKeys = Object.keys(out.doc.project).sort();
out.exportSeed = out.doc.project.seed;
out.exportPlan = out.doc.project.plan;
out.exportContext = out.doc.project.context;
out.exportLimits = out.doc.limits.bundleBytes;
out.exportSettings = out.doc.settings;

// 2. Import never overwrites: the same name lands on a fresh slug.
out.second = api.importProject(doc({
  name: 'Notes', files: { 'index.html': '<html><body>second</body></html>' },
}));
out.slugs = api.projects().map(p => p.slug).sort();

// 3. Refusals are named, and a refused document writes nothing.
out.traversal = refusal(() => api.importProject(JSON.stringify({
  name: 'Sneaky', files: { '../../evil.txt': 'x' },
})));
out.nested = refusal(() => api.importProject(JSON.stringify({
  name: 'Nested', files: { 'a/b/index.html': '<p>ok</p>' },
})));
out.absolute = refusal(() => api.importProject(JSON.stringify({
  name: 'Absolute', files: { '/etc/passwd': 'x' },
})));
out.backslash = refusal(() => api.importProject(JSON.stringify({
  name: 'Backslash', files: { 'a\\b.txt': 'x' },
})));
out.badVersion = refusal(() => api.importProject(doc({
  name: 'Future', files: { 'a.txt': 'x' },
}, 9)));
out.badFormat = refusal(() => api.importProject(JSON.stringify({
  format: 'toolrx.snapshot', version: 1, files: { 'a.txt': 'x' },
})));
out.oversized = refusal(() => api.importProject(JSON.stringify({
  name: 'Big', files: { 'a.txt': 'x'.repeat(200001) },
})));
out.hugeBundle = refusal(() => api.importProject('x'.repeat(2_100_000)));
out.sneakyFiles = api.projects().filter(p => /sneaky|nested|absolute|backslash|future/.test(p.slug));

out.bad = refusal(() => api.importProject('{oops'));
out.empty = refusal(() => api.importProject('{}'));
out.missing = refusal(() => api.exportProject('does-not-exist'));

// 4. A three-project workspace round-trips byte-exactly, with context, the
// active plan, and settings.
api.reset();
['Alpha', 'Beta', 'Gamma'].forEach((name, i) => {
  api.importProject(doc({
    name: name,
    files: {
      'index.html': '<!doctype html><p>' + name + ' ' + i + '</p>',
      'app.js': 'console.log("' + name + '");',
    },
  }));
});
const alpha = api.projects().find(p => p.slug === 'alpha');
api.openProject('beta');
C.set('beta', 'result', 'last', 'query: beta\nvia: edit.apply\nbeta result');
C.set('beta', 'plan', 'last', C.stable({
  version: 1, steps: ['one', 'two'], status: ['done', 'done'],
}));
localStorage.setItem('toolrx.project.budget', '1048576');
out.workspaceText = api.exportWorkspace();
out.workspaceDoc = JSON.parse(out.workspaceText);
out.workspaceFormat = out.workspaceDoc.format;
out.workspaceVersion = out.workspaceDoc.version;
out.workspaceActive = out.workspaceDoc.active;
out.workspaceSlugs = out.workspaceDoc.projects.map(p => p.slug).sort();
out.workspaceHasPlan = !!out.workspaceDoc.projects.find(p => p.slug === 'beta').plan;
out.workspaceContext = out.workspaceDoc.projects
  .find(p => p.slug === 'beta').context.length;
out.workspaceBudget = out.workspaceDoc.settings.projectBytes;

const fileList = () => api.projects().map(p => p.files.map(f =>
  p.slug + '/' + f + '=' + api.projectFile(p.slug, f))).flat().sort();
const beforeFiles = fileList();
const beforeBetaContext = C.read('beta').entries
  .map(e => e.kind + ':' + e.key + ':' + e.text).sort();
const beforePlan = C.get('beta', 'plan', 'last');

api.reset();
out.importedWorkspace = api.importWorkspace(out.workspaceText);
const afterFiles = fileList();
out.filesMatch = JSON.stringify(beforeFiles) === JSON.stringify(afterFiles);
out.activeAfter = api.project().slug;
out.workspacePlanAfter = C.get('beta', 'plan', 'last');
out.workspacePlanSame = out.workspacePlanAfter === beforePlan;
out.workspaceContextAfter = C.read('beta').entries
  .map(e => e.kind + ':' + e.key + ':' + e.text).sort();
out.contextSame = JSON.stringify(out.workspaceContextAfter) === JSON.stringify(beforeBetaContext);
out.workspaceFilesMirrored = api.project().files.length;

// 5. A single project package reproduces its files from the seed.
api.reset();
const packageText = out.workspaceDoc.projects.find(p => p.slug === 'beta');
out.packageImport = api.importProject(JSON.stringify({
  format: 'toolrx.project', version: 2, project: packageText,
}));
out.packageFiles = api.project().files.sort();
out.packagePlan = C.get('beta', 'plan', 'last') === beforePlan;

// 6. Workspace import is all-or-none and refuses duplicates.
api.reset();
const good = JSON.parse(out.workspaceText);
good.projects[1].files['../../evil.txt'] = 'x';
out.workspaceRefusal = refusal(() => api.importWorkspace(JSON.stringify(good)));
out.workspaceUntouched = api.projects().length;

api.reset();
api.importProject(doc({ name: 'Beta', files: { 'index.html': '<p>b</p>' } }));
out.duplicate = refusal(() => api.importWorkspace(out.workspaceText));
out.duplicateUntouched = api.projects().map(p => p.slug).sort();

api.reset();
const dupe = JSON.parse(out.workspaceText);
dupe.projects[2].slug = 'alpha';
out.duplicateInside = refusal(() => api.importWorkspace(JSON.stringify(dupe)));
out.duplicateInsideUntouched = api.projects().length;

out.crossProject = refusal(() => api.importProject(out.workspaceText));
out.crossWorkspace = refusal(() => api.importWorkspace(doc({
  name: 'Single', files: { 'a.txt': 'x' },
})));

// 7. Bundles saved in the tab are named, listed, re-importable, and capped.
api.reset();
api.importProject(doc({ name: 'Portable', files: { 'index.html': '<p>p</p>' } }));
out.bundleExport = api.exportProjectBundle('portable');
out.bundleList = api.bundles();
out.bundleBytes = JSON.parse(localStorage.getItem('toolrx.bundles.v1')).items['portable.toolrx.json'].bytes;
// A bundle is a saved artifact, so reset clears the workspace but keeps it.
api.reset();
out.bundleKept = api.bundles();
out.bundleImport = api.importProjectNamed('portable.toolrx.json');
out.bundleSlugs = api.projects().map(p => p.slug).sort();
out.missingBundle = refusal(() => api.importProjectNamed('nope.toolrx.json'));

console.log(JSON.stringify(out));
"""


@unittest.skipUnless(NODE, "node is required for the sandbox bridge test")
class SandboxBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([NODE, "-e", JS, SANDBOX],
                              capture_output=True, text=True, timeout=120)
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

    def test_export_is_a_portable_v2_document(self):
        self.assertEqual(self.out["exportFormat"], "toolrx.project")
        self.assertEqual(self.out["exportVersion"], 2)
        for key in ("slug", "name", "kind", "desc", "created", "updated",
                    "spec", "seed", "files", "plan", "context"):
            self.assertIn(key, self.out["projectKeys"])
        self.assertEqual(self.out["exportSeed"], 42)
        self.assertEqual(self.out["exportPlan"]["steps"],
                         ["add a footer", "add a theme toggle"])
        self.assertEqual(self.out["exportPlan"]["status"], ["done", "pending"])
        kinds = {entry["kind"] for entry in self.out["exportContext"]}
        self.assertIn("plan", kinds)
        self.assertIn("result", kinds)
        self.assertEqual(self.out["exportLimits"], 2097152)
        self.assertIn("projectBytes", self.out["exportSettings"])

    def test_import_never_overwrites(self):
        self.assertIn("notes-2", self.out["slugs"])
        self.assertIn("notes", self.out["slugs"])

    def test_traversal_and_nested_paths_are_refused(self):
        self.assertIn("plain names", self.out["traversal"])
        self.assertIn("../../evil.txt", self.out["traversal"])
        self.assertIn("folder path", self.out["nested"])
        self.assertIn("absolute path", self.out["absolute"])
        self.assertIn("backslash", self.out["backslash"])
        self.assertEqual(self.out["sneakyFiles"], [])

    def test_unknown_versions_and_formats_are_named(self):
        self.assertIn("unsupported toolrx.project version 9", self.out["badVersion"])
        self.assertIn("reads 1–2", self.out["badVersion"])
        self.assertIn("unsupported bundle format", self.out["badFormat"])
        self.assertIn("toolrx.snapshot", self.out["badFormat"])

    def test_oversized_input_is_refused(self):
        self.assertIn("over the", self.out["oversized"])
        self.assertIn("131072-byte file cap", self.out["oversized"])
        self.assertIn("bundle cap", self.out["hugeBundle"])

    def test_import_failures_are_explicit(self):
        self.assertIn("valid JSON", self.out["bad"])
        self.assertIn("no project files", self.out["empty"])
        self.assertIn("no such project", self.out["missing"])
        self.assertIn("workspace bundle", self.out["crossProject"])
        self.assertIn("single project bundle", self.out["crossWorkspace"])

    def test_workspace_round_trips_byte_exactly(self):
        self.assertEqual(self.out["workspaceFormat"], "toolrx.workspace")
        self.assertEqual(self.out["workspaceVersion"], 1)
        self.assertEqual(self.out["workspaceSlugs"], ["alpha", "beta", "gamma"])
        self.assertEqual(self.out["workspaceActive"], "beta")
        self.assertTrue(self.out["workspaceHasPlan"])
        self.assertGreaterEqual(self.out["workspaceContext"], 2)
        self.assertEqual(self.out["workspaceBudget"], 1048576)
        self.assertTrue(self.out["filesMatch"])
        self.assertEqual(self.out["activeAfter"], "beta")
        self.assertTrue(self.out["workspacePlanSame"])
        self.assertTrue(self.out["contextSame"])
        self.assertGreater(self.out["workspaceFilesMirrored"], 0)
        self.assertIn("imported workspace", self.out["importedWorkspace"])

    def test_project_package_reproduces_files_and_plan(self):
        self.assertIn("imported", self.out["packageImport"])
        self.assertEqual(self.out["packageFiles"], ["app.js", "index.html"])
        self.assertTrue(self.out["packagePlan"])

    def test_workspace_import_is_all_or_none(self):
        self.assertIn("plain names", self.out["workspaceRefusal"])
        self.assertEqual(self.out["workspaceUntouched"], 0)
        self.assertIn("already has", self.out["duplicate"])
        self.assertEqual(self.out["duplicateUntouched"], ["beta"])
        self.assertIn("duplicate project slug", self.out["duplicateInside"])
        self.assertEqual(self.out["duplicateInsideUntouched"], 0)

    def test_named_bundles_are_capped_listed_and_survive_reset(self):
        self.assertIn("bundle portable.toolrx.json", self.out["bundleExport"])
        self.assertIn("portable.toolrx.json", self.out["bundleList"])
        self.assertGreater(self.out["bundleBytes"], 0)
        self.assertIn("portable.toolrx.json", self.out["bundleKept"])
        self.assertIn("imported", self.out["bundleImport"])
        self.assertEqual(self.out["bundleSlugs"], ["portable"])
        self.assertIn("no bundle named", self.out["missingBundle"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

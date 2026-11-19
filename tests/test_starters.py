#!/usr/bin/env python3
"""Behaviour tests for the step 62 starter library.

The real templates run in Node. These tests prove the same prompt and seed
produce byte-identical files, every starter has a previewable entry point and
an ARCHITECTURE.md, extra scripts load before app.js, the existing file and
size caps hold, and the exact build routes exist in the catalog. No network
and no browser are involved.
"""

import json
import os
import re
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NODE = shutil.which("node")

LIMITS = json.load(open(os.path.join(ROOT, "toolrx", "limits.json"), encoding="utf-8"))
CATALOG = json.load(open(os.path.join(ROOT, "toolrx", "web", "commands.json"),
                         encoding="utf-8"))

CASES = [
    ("authapp", "build an auth app", "authapp",
     ["index.html", "styles.css", "app.js", "auth.js", "README.md", "ARCHITECTURE.md"],
     ["auth.js"]),
    ("authapp-web", "build a web app with an auth stub", "authapp",
     ["index.html", "styles.css", "app.js", "auth.js", "README.md", "ARCHITECTURE.md"],
     ["auth.js"]),
    ("datadash", "build a data dashboard", "datadash",
     ["index.html", "styles.css", "app.js", "data.js", "README.md", "ARCHITECTURE.md"],
     ["data.js"]),
    ("notebook", "build a note-taking app", "notebook",
     ["index.html", "styles.css", "app.js", "seed-notes.js", "README.md", "ARCHITECTURE.md"],
     ["seed-notes.js"]),
    ("multipage", "build a multi-page static site", "multipage",
     ["index.html", "about.html", "docs.html", "contact.html", "styles.css",
      "site.js", "app.js", "README.md", "ARCHITECTURE.md"],
     ["about.html", "docs.html", "contact.html", "site.js"]),
    ("apimock", "build an api mock", "apimock",
     ["index.html", "styles.css", "app.js", "api.js", "openapi.json",
      "README.md", "ARCHITECTURE.md"],
     ["api.js", "openapi.json"]),
    ("notes-regression", "build a notes app", "notes",
     ["index.html", "styles.css", "app.js", "README.md", "ARCHITECTURE.md"], []),
    ("dashboard-regression", "build a dashboard", "dashboard",
     ["index.html", "styles.css", "app.js", "README.md", "ARCHITECTURE.md"], []),
]

ROUTES = [
    ("build an auth app", "auth app"),
    ("build a web app with an auth stub", "web app"),
    ("build a data dashboard", "data dashboard"),
    ("build a note-taking app", "note-taking app"),
    ("build a multi-page static site", "multi-page static site"),
    ("build an api mock", "api mock"),
]

JS = r"""
const fs = require('fs');
global.self = global;
eval(fs.readFileSync(process.env.TEMPLATES, 'utf8'));
const T = self.toolrxTemplates;
const cases = JSON.parse(process.env.STARTER_CASES);
const out = {};
for (const c of cases) {
  const a = T.project(c.kind, c.desc, { theme: 'dark' });
  const b = T.project(c.kind, c.desc, { theme: 'dark' });
  const s1 = T.project(c.kind, c.desc + ' seed 1', { theme: 'dark' });
  const s2 = T.project(c.kind, c.desc + ' seed 2', { theme: 'dark' });
  out[c.name] = {
    kind: a.kind,
    title: a.title,
    seed: a.spec.seed,
    files: a.files,
    same: JSON.stringify(a.files) === JSON.stringify(b.files),
    seedA: s1.spec.seed,
    seedB: s2.spec.seed,
    seedDiff: Object.keys(s1.files).filter(f => s1.files[f] !== s2.files[f]),
  };
}
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(NODE, "node is not installed")
class StarterLibraryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = [{"name": name, "kind": kind, "desc": desc}
                     for name, desc, kind, _, _ in CASES]
        proc = subprocess.run(
            [NODE, "-e", JS],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
            env=dict(os.environ,
                     TEMPLATES=os.path.join(ROOT, "toolrx", "web", "templates.js"),
                     STARTER_CASES=json.dumps(cls.cases)),
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr or proc.stdout)
        cls.out = json.loads(proc.stdout)

    def test_every_starter_canonicalizes_to_its_kind(self):
        for name, desc, kind, _, _ in CASES:
            with self.subTest(name=name):
                self.assertEqual(self.out[name]["kind"], kind)

    def test_same_prompt_and_seed_are_byte_identical(self):
        for name, _, _, _, _ in CASES:
            with self.subTest(name=name):
                self.assertTrue(self.out[name]["same"],
                                "two identical builds must produce identical files")

    def test_expected_files_exist(self):
        for name, _, _, files, _ in CASES:
            with self.subTest(name=name):
                have = self.out[name]["files"]
                for f in files:
                    self.assertIn(f, have)

    def test_each_starter_has_an_architecture_and_readme(self):
        for name, _, _, files, extras in CASES:
            with self.subTest(name=name):
                have = self.out[name]["files"]
                arch = have["ARCHITECTURE.md"]
                readme = have["README.md"]
                self.assertIn("## Build spec", arch)
                self.assertIn("## Files", arch)
                self.assertIn("## Build spec", readme)
                for f in files:
                    if f in ("README.md", "ARCHITECTURE.md"):
                        continue
                    self.assertIn("`" + f + "`", arch)
                for f in extras:
                    self.assertIn("`" + f + "`", readme)

    def test_extra_scripts_load_before_app_js(self):
        for name, _, _, _, extras in CASES:
            with self.subTest(name=name):
                html = self.out[name]["files"]["index.html"]
                self.assertIn('<link rel="stylesheet" href="styles.css">', html)
                app_at = html.index('src="app.js"')
                for f in extras:
                    if not f.endswith(".js"):
                        continue
                    tag = 'src="' + f + '"'
                    self.assertIn(tag, html)
                    self.assertLess(html.index(tag), app_at,
                                    f + " must load before app.js")

    def test_multipage_pages_share_the_stylesheet_and_script(self):
        files = self.out["multipage"]["files"]
        for page in ("about.html", "docs.html", "contact.html"):
            with self.subTest(page=page):
                html = files[page]
                self.assertIn('<link rel="stylesheet" href="styles.css">', html)
                self.assertIn('<script src="site.js"></script>', html)
                self.assertIn('data-page="' + page.replace(".html", "") + '"', html)

    def test_seed_changes_seeded_content(self):
        for name, _, _, _, _ in CASES:
            if name.endswith("regression"):
                continue
            with self.subTest(name=name):
                self.assertNotEqual(self.out[name]["seedA"], self.out[name]["seedB"])
                self.assertTrue(self.out[name]["seedDiff"],
                                "a different explicit seed must change at least one file")

    def test_files_stay_inside_the_named_caps(self):
        for name, _, _, _, _ in CASES:
            files = self.out[name]["files"]
            with self.subTest(name=name):
                self.assertLessEqual(len(files), LIMITS["projectFiles"])
                total = sum(len(v) for v in files.values())
                self.assertLessEqual(total, LIMITS["projectBytes"])
                for f, body in files.items():
                    self.assertLessEqual(len(body), LIMITS["projectFileBytes"], f)

    def test_generated_files_never_touch_the_network(self):
        banned = ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon",
                  "http://", "https://")
        for name, _, _, _, _ in CASES:
            for f, body in self.out[name]["files"].items():
                if f in ("README.md", "ARCHITECTURE.md"):
                    continue
                low = body.lower()
                for token in banned:
                    with self.subTest(name=name, file=f, token=token):
                        self.assertNotIn(token.lower(), low)

    def test_exact_build_routes_exist(self):
        commands = CATALOG["commands"]
        for text, kind in ROUTES:
            with self.subTest(text=text):
                found = [c for c in commands
                         if c["op"] == "build"
                         and re.fullmatch(c["re"], text)]
                self.assertTrue(found, "no build route for: " + text)
                self.assertIn(kind, [c["args"].get("kind") for c in found])


if __name__ == "__main__":
    unittest.main()

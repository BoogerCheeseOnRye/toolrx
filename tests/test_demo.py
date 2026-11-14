#!/usr/bin/env python3
"""Step 45: the offline end-to-end demo is measured and reproducible.

The checked-in `toolrx/demo_report.json` is produced by the real browser
modules in Node. These tests run the freshness check and then assert the
promises the demo makes: one long request fits the plan envelope, every step
matches a deterministic command and succeeds, the project has modules and
systems, the bundle is one step, the continuation runs only the pending step,
and undo restores the exact bytes.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPORT = os.path.join(ROOT, "toolrx", "demo_report.json")
LIMITS = os.path.join(ROOT, "toolrx", "limits.json")
DEMO = os.path.join(ROOT, "toolrx", "demo.py")
README = os.path.join(ROOT, "README.md")
PITCH = os.path.join(ROOT, "docs", "pitch.html")

SYSTEMS = ["ai", "audio", "combat", "crafting", "dialogue", "inventory",
           "particles", "quests", "save", "ui", "weather"]
MODULES = ["content/seed.js", "core/state.js", "data/seed.js", "ui/render.js"]
CONTINUED = "change the page title to Station Defense Continued"


class DemoReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(REPORT, encoding="utf-8") as fh:
            cls.report = json.load(fh)
        with open(LIMITS, encoding="utf-8") as fh:
            cls.limits = json.load(fh)

    def test_report_is_current(self):
        proc = subprocess.run([sys.executable, DEMO, "--check"],
                              capture_output=True, text=True, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("current", proc.stdout)

    def test_request_and_plan_fit_the_envelope(self):
        request = self.report["request"]
        plan = self.report["plan"]
        budget = plan["budget"]
        self.assertGreaterEqual(request["chars"], 3000)
        self.assertLessEqual(request["chars"], 6000)
        self.assertEqual(plan["chars"], request["chars"])
        self.assertEqual(plan["steps"], request["steps"])
        self.assertLessEqual(request["steps"], self.limits["planSteps"])
        self.assertTrue(plan["plan"])
        self.assertFalse(plan["blocked"])
        self.assertFalse(plan["overLimit"])
        self.assertTrue(budget["fits"])
        self.assertEqual(budget["maxChars"], self.limits["planChars"])
        self.assertEqual(budget["maxSteps"], self.limits["planSteps"])
        self.assertLessEqual(budget["worstCaseMs"], budget["planMs"])
        self.assertRegex(request["sha256"], r"^[0-9a-f]{64}$")

    def test_every_step_is_deterministic_and_successful(self):
        steps = self.report["steps"]
        self.assertEqual(len(steps), self.report["request"]["steps"])
        for i, step in enumerate(steps, 1):
            self.assertEqual(step["n"], i)
            self.assertFalse(step["error"], step["step"])
            self.assertTrue(step["via"], step["step"])
            self.assertNotRegex(step["via"],
                                r"^(?:router\.|chat$|none$|limit$|budget\.)")
            self.assertIn("confidence", step)
            self.assertIn("margin", step)
            body = step["text"].encode("utf-8")
            self.assertEqual(step["bytes"], len(body), step["step"])
            self.assertEqual(step["sha"], hashlib.sha256(body).hexdigest())
        run = self.report["run"]
        self.assertTrue(run["ok"])
        self.assertEqual(run["failed"], 0)
        self.assertEqual(run["steps"], len(steps))
        self.assertEqual(run["planned"], len(steps))
        self.assertTrue(run["budget"]["within"])
        self.assertEqual(run["budget"]["over"], [])

    def test_project_has_modules_systems_and_one_patch_bundle(self):
        project = self.report["project"]
        self.assertEqual(project["slug"], "top-down-shooter")
        self.assertEqual(project["kind"], "shooter")
        names = [f["name"] for f in project["files"]]
        self.assertEqual(len(names), 22)
        self.assertEqual(len(set(names)), len(names))
        for module in MODULES:
            self.assertIn(module, names)
        for system in SYSTEMS:
            self.assertIn("systems/" + system + ".js", names)
        self.assertEqual(sum(f["bytes"] for f in project["files"]),
                         self.report["run"]["bytes"])
        self.assertEqual(self.report["run"]["files"], len(names))

        steps = {step["n"]: step for step in self.report["steps"]}
        self.assertEqual(steps[1]["via"], "build")
        bundle = steps[4]
        self.assertEqual(bundle["via"], "edit.apply.many")
        self.assertIn("boss + quest + sound + day/night + three enemy types",
                      bundle["text"])
        self.assertIn("changed: ARCHITECTURE.md, README.md, app.js, index.html, styles.css",
                      bundle["text"])
        self.assertIn("one undo reverts the whole bundle", bundle["text"])

    def test_extractors_read_the_project_files(self):
        vias = [step["via"] for step in self.report["steps"]]
        for via in ("text.summarize", "text.headings", "text.facts", "text.list",
                    "text.code", "text.diff", "text.firstlines", "text.count"):
            self.assertIn(via, vias, via)
        for step in self.report["steps"]:
            if step["via"].startswith("text."):
                self.assertTrue(step["text"].strip(), step["step"])
                self.assertNotIn("no such file", step["text"].lower(), step["step"])
        # The code outline actually found declarations in the project's app.js.
        outline = [s for s in self.report["steps"] if s["via"] == "text.code"][0]
        self.assertRegex(outline["text"], r"(?:function|class|const|def) ")

    def test_continuation_runs_only_the_pending_step(self):
        continuation = self.report["continuation"]
        expand = continuation["expand"]
        self.assertEqual(expand["via"], "context.expand")
        self.assertFalse(expand["error"])
        self.assertEqual(expand["plan"]["steps"], self.report["request"]["steps"] + 1)
        self.assertEqual(expand["plan"]["pending"], 1)
        self.assertEqual(expand["plan"]["pendingSteps"], [CONTINUED])
        self.assertEqual(expand["plan"]["error"], 0)
        self.assertIn("1 new step", expand["text"])

        cont = continuation["continue"]
        self.assertEqual(cont["via"], "context.continue")
        self.assertFalse(cont["error"])
        self.assertEqual(cont["plan"]["steps"], self.report["request"]["steps"] + 1)
        self.assertEqual(cont["plan"]["pending"], 0)
        self.assertEqual(cont["plan"]["error"], 0)
        self.assertEqual(cont["plan"]["done"], cont["plan"]["steps"])
        self.assertIn("1 step run", cont["text"])
        self.assertIn("0 still pending", cont["text"])
        self.assertEqual(cont["filesTouched"],
                         ["ARCHITECTURE.md", "README.md", "index.html"])
        self.assertIn("Station Defense Continued", cont["text"])

    def test_undo_is_byte_exact(self):
        undo = self.report["undo"]
        self.assertEqual(undo["via"], "edit.undo")
        self.assertFalse(undo["error"])
        self.assertTrue(undo["exact"])
        self.assertEqual(undo["filesRestored"],
                         ["ARCHITECTURE.md", "README.md", "index.html"])
        self.assertIn('undid "page title"', undo["text"])

    def test_context_and_limits_are_the_shared_envelope(self):
        self.assertEqual(self.report["limits"], self.limits)
        self.assertIn("source toolrx/limits.json", self.report["limitsText"])
        for key in self.limits:
            self.assertIn(key, self.report["limitsText"])
        self.assertIn("pending plan: 0 steps", self.report["context"]["snapshot"])
        self.assertIn("context snapshot", self.report["context"]["snapshot"])
        self.assertIn("cap 8192 bytes", self.report["context"]["report"]["text"])
        # The checked-in report carries normalized timings only.
        self.assertIn("normalized", self.report["timings"])
        self.assertEqual(self.report["run"]["ms"], 0)
        self.assertEqual(self.report["run"]["at"], 0)
        self.assertTrue(all(step["ms"] == 0 for step in self.report["steps"]))
        self.assertEqual(self.report["run"]["budget"]["ms"]["used"], 0)
        self.assertEqual(self.report["run"]["budget"]["ms"]["remaining"],
                         self.report["run"]["budget"]["ms"]["max"])

    def test_docs_quote_the_measured_numbers(self):
        with open(README, encoding="utf-8") as fh:
            readme = fh.read()
        with open(PITCH, encoding="utf-8") as fh:
            pitch = fh.read()
        numbers = {
            "request": f"{self.report['request']['chars']:,}",
            "steps": f"{self.report['request']['steps']} steps",
            "files": f"{self.report['project'] and len(self.report['project']['files'])} files",
            "bytes": f"{self.report['run']['bytes']:,}",
            "catalog": f"{self.report['catalog']:,}",
        }
        for name, value in numbers.items():
            self.assertIn(value, readme, name)
            self.assertIn(value, pitch, name)
        self.assertIn("python3 toolrx/demo.py", readme)
        self.assertIn("demo_report.json", readme)
        self.assertRegex(pitch, r"[Ee]nd-to-end (?:long )?demo|one offline demo")

    def test_pitch_test_count_is_plausible(self):
        with open(PITCH, encoding="utf-8") as fh:
            pitch = fh.read()
        match = re.search(r'<div class="v">(\d+)</div><div class="k">automated tests</div>',
                          pitch)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 357)


if __name__ == "__main__":
    unittest.main(verbosity=2)

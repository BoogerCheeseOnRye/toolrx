#!/usr/bin/env python3
"""Step 69: the public evaluation suite and comparison kit.

These tests drive the real harness once, then pin every measured section to its
source file: the coverage report, the demo report, and the harness output. They
also prove that the checked-in report is current, that the README, comparison,
and pitch quote the same bytes, that a stale report or a stale block is caught,
and that the comparison names the honest gaps. No server, browser, model, or
network call is used; the harness's fake fetch only reads local files.
"""

import copy
import io
import json
import os
import pathlib
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORE = os.path.join(ROOT, "toolrx")
REPORT = os.path.join(CORE, "evaluation.json")
COVERAGE = os.path.join(CORE, "coverage.json")
DEMO = os.path.join(CORE, "demo_report.json")
README = os.path.join(ROOT, "README.md")
COMPARISON = os.path.join(ROOT, "COMPARISON.md")
PITCH = os.path.join(ROOT, "docs", "pitch.html")

sys.path.insert(0, CORE)

import evaluation  # noqa: E402


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def block(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return text


class EvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = evaluation.build_report()
        cls.coverage = read_json(COVERAGE)
        cls.demo = read_json(DEMO)

    def test_report_is_current(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = evaluation.check(self.report)
        self.assertEqual(code, 0, err.getvalue())

    def test_report_validates(self):
        self.assertEqual(evaluation.validate(copy.deepcopy(self.report)),
                         self.report)

    def test_every_measured_section_matches_its_source(self):
        report = self.report
        metrics = report["metrics"]
        fixtures = self.coverage["fixtures"]

        self.assertEqual(metrics["catalog"], self.coverage["catalog"]["count"])
        self.assertEqual(metrics["everyday"], fixtures["everyday"]["cases"])
        self.assertEqual(metrics["routing"], fixtures["routing"]["cases"])
        self.assertEqual(metrics["fixtures"],
                         sum(entry["cases"] for entry in fixtures.values()))

        for name in ("everyday", "routing"):
            self.assertEqual(report["lanes"][name], fixtures[name]["lanes"])
        total = {key: 0 for key in evaluation.LANES}
        for entry in fixtures.values():
            for key in total:
                total[key] += entry["lanes"][key]
        self.assertEqual(report["lanes"]["fixtures"], total)

        build = report["build"]
        run = self.demo["run"]
        budget = run["budget"]
        self.assertEqual(build["requestChars"], self.demo["plan"]["chars"])
        self.assertEqual(build["planSteps"], self.demo["plan"]["steps"])
        self.assertEqual(build["maxSteps"], budget["steps"]["max"])
        self.assertEqual(build["executed"], run["executed"])
        self.assertEqual(build["failed"], run["failed"])
        self.assertEqual(build["files"], run["files"])
        self.assertEqual(build["maxFiles"], budget["files"]["max"])
        self.assertEqual(build["bytes"], run["bytes"])
        self.assertEqual(build["contextUsed"], budget["context"]["used"])
        self.assertEqual(build["contextMax"], budget["context"]["max"])
        self.assertEqual(build["undo"], run["undo"])
        self.assertTrue(build["within"])
        self.assertEqual(build["over"], [])

    def test_determinism_is_byte_identical_and_offline(self):
        harness = self.report["harness"]
        for name in ("thinking", "repair"):
            self.assertEqual(harness[name]["deterministic"],
                             harness[name]["states"])
            self.assertEqual(harness[name]["mismatches"], 0)
            self.assertEqual(harness[name]["names"], [])
        self.assertTrue(harness["rewrite"]["identical"])
        self.assertTrue(harness["compaction"]["identical"])
        self.assertGreaterEqual(harness["compaction"]["runs"], 2)
        self.assertEqual(self.report["determinism"]["identical"],
                         self.report["determinism"]["programs"])
        self.assertEqual(self.report["network"], 0)
        self.assertEqual(harness["network"], 0)
        self.assertGreaterEqual(harness["fetches"], harness["network"])

    def test_every_section_renders(self):
        markdown = evaluation.render_markdown(self.report)
        for needle in ("Reach", "Determinism", "One end-to-end build",
                       "Commands in the catalog", "Named caps",
                       "Everyday cases", "Fixture cases", "Thinking modes",
                       "Repair rules", "Plan rewrites", "Context compactions",
                       "Network calls after init"):
            self.assertIn(needle, markdown)
        page = evaluation.render_html(self.report)
        for needle in ("Reach.", "Determinism.", "One build.",
                       "Evaluation report", "COMPARISON.md"):
            self.assertIn(needle, page)

    def test_readme_comparison_and_pitch_quote_the_same_report(self):
        start, end = evaluation.BLOCK_START, evaluation.BLOCK_END
        bodies = {}
        for name, path in (("readme", README), ("comparison", COMPARISON)):
            text = block(path)
            self.assertEqual(text.count(start), 1, name)
            self.assertEqual(text.count(end), 1, name)
            bodies[name] = text.split(start, 1)[1].split(end, 1)[0].strip()
        self.assertEqual(bodies["readme"], bodies["comparison"])
        self.assertEqual(bodies["comparison"],
                         evaluation.render_markdown(self.report).strip())
        page = block(PITCH)
        self.assertEqual(page.count(start), 1)
        self.assertEqual(page.count(end), 1)
        self.assertIn(evaluation.render_html(self.report).strip(), page)

    def test_comparison_names_at_least_three_honest_gaps(self):
        text = block(COMPARISON)
        gaps = ("Conversational breadth", "General terminal work",
                "Generation quality", "No learning", "Single-user and local",
                "Not a benchmark")
        for gap in gaps:
            self.assertIn(gap, text)
        numbered = re.findall(r"^\d+\. \*\*", text, re.M)
        self.assertGreaterEqual(len(numbered), 3)

    def test_missing_fixture_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "coverage.json"
            path.write_text(json.dumps({
                "catalog": {"count": 1},
                "fixtures": {"routing": {"cases": 1, "lanes": {}}},
            }), encoding="utf-8")
            with mock.patch.object(evaluation, "COVERAGE", path):
                with self.assertRaises(ValueError) as caught:
                    evaluation.build_report()
        self.assertIn("missing fixtures.everyday", str(caught.exception))

    def test_stale_report_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = pathlib.Path(tmp) / "evaluation.json"
            stale.write_text('{"version": 1}\n', encoding="utf-8")
            err = io.StringIO()
            with mock.patch.object(evaluation, "REPORT", stale), \
                    redirect_stderr(err):
                code = evaluation.check(self.report)
        self.assertEqual(code, 1)
        self.assertIn("stale", err.getvalue())

    def test_missing_or_duplicate_block_is_rejected(self):
        start, end = evaluation.BLOCK_START, evaluation.BLOCK_END
        with self.assertRaises(ValueError):
            evaluation._replace_block("no markers", start, end, "x", "test")
        twice = start + "\na\n" + end + "\n" + start + "\nb\n" + end
        with self.assertRaises(ValueError):
            evaluation._replace_block(twice, start, end, "x", "test")
        fresh = evaluation._replace_block(start + "\nold\n" + end,
                                          start, end, "fresh", "test")
        self.assertIn("fresh", fresh)
        self.assertNotIn("old", fresh)

    def test_a_report_that_breaks_a_rule_is_refused(self):
        bad = copy.deepcopy(self.report)
        bad["network"] = 1
        with self.assertRaises(ValueError):
            evaluation.validate(bad)
        bad = copy.deepcopy(self.report)
        bad["determinism"]["identical"] -= 1
        with self.assertRaises(ValueError):
            evaluation.validate(bad)
        bad = copy.deepcopy(self.report)
        bad["build"]["failed"] = 1
        with self.assertRaises(ValueError):
            evaluation.validate(bad)
        bad = copy.deepcopy(self.report)
        bad["build"]["contextUsed"] = bad["build"]["contextMax"] + 1
        with self.assertRaises(ValueError):
            evaluation.validate(bad)


if __name__ == "__main__":
    unittest.main()

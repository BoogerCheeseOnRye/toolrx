#!/usr/bin/env python3
"""Step 59: the LLM-parity scorecard.

`toolrx/scorecard.json` is the only place a capability claim is written.
`toolrx/scorecard.py` derives every quoted number from the repository and keeps
the README and pitch blocks byte-identical to that table. These tests prove the
schema, the evidence links, the derived metrics, both generated blocks, and
that a drift in any of them fails.
"""

import copy
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORE = os.path.join(ROOT, "toolrx")
sys.path.insert(0, CORE)

import scorecard  # noqa: E402

README = os.path.join(ROOT, "README.md")
PITCH = os.path.join(ROOT, "docs", "pitch.html")
COVERAGE = os.path.join(CORE, "coverage.json")
LIMITS = os.path.join(CORE, "limits.json")


class ScorecardTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = scorecard.load()
        cls.doc = scorecard.validate(cls.raw)
        cls.metrics = scorecard.metrics()

    def test_every_capability_has_a_status_evidence_and_an_honest_gap(self):
        self.assertEqual(len(self.doc["capabilities"]), 10)
        for cap in self.doc["capabilities"]:
            self.assertIn(cap["status"], scorecard.STATUSES, cap["id"])
            self.assertTrue(cap["evidence"], cap["id"])
            self.assertTrue(cap["gap"].strip(), cap["id"])
            self.assertTrue(cap["claim"].strip(), cap["id"])
            self.assertTrue(cap["label"].strip(), cap["id"])

    def test_ids_are_unique_slugs(self):
        ids = [cap["id"] for cap in self.doc["capabilities"]]
        self.assertEqual(len(ids), len(set(ids)))
        for cap_id in ids:
            self.assertRegex(cap_id, scorecard.ID_RE)

    def test_shipped_capabilities_cite_a_real_test(self):
        for cap in self.doc["capabilities"]:
            if cap["status"] == "shipped":
                self.assertTrue(any(e["test"] for e in cap["evidence"]),
                                cap["id"])

    def test_every_evidence_path_and_test_exists(self):
        index = scorecard.test_index()
        for cap in self.doc["capabilities"]:
            for entry in cap["evidence"]:
                self.assertTrue(os.path.exists(os.path.join(ROOT, entry["path"])),
                                entry["path"])
                if entry["test"]:
                    name = os.path.basename(entry["path"])
                    self.assertIn(entry["test"], index[name], entry)

    def test_metrics_are_derived_from_the_repository(self):
        coverage = json.load(open(COVERAGE, encoding="utf-8"))
        limits = json.load(open(LIMITS, encoding="utf-8"))
        fixtures = coverage["fixtures"]
        self.assertEqual(self.metrics["catalog"], coverage["catalog"]["count"])
        self.assertEqual(self.metrics["tests"], scorecard.count_tests())
        self.assertEqual(self.metrics["caps"],
                         len([k for k in limits if k != "version"]))
        self.assertEqual(self.metrics["everyday"],
                         fixtures["everyday"]["cases"])
        self.assertEqual(self.metrics["routing"], fixtures["routing"]["cases"])
        self.assertEqual(self.metrics["fixtures"],
                         sum(v["cases"] for v in fixtures.values()))

    def test_unknown_status_is_rejected(self):
        doc = copy.deepcopy(self.raw)
        doc["capabilities"][0]["status"] = "maybe"
        with self.assertRaises(ValueError):
            scorecard.validate(doc)

    def test_duplicate_id_is_rejected(self):
        doc = copy.deepcopy(self.raw)
        doc["capabilities"][1]["id"] = doc["capabilities"][0]["id"]
        with self.assertRaises(ValueError):
            scorecard.validate(doc)

    def test_missing_test_is_rejected(self):
        doc = copy.deepcopy(self.raw)
        doc["capabilities"][0]["evidence"][1]["test"] = "SplitterTest.test_gone"
        with self.assertRaises(ValueError):
            scorecard.validate(doc)

    def test_empty_gap_is_rejected(self):
        doc = copy.deepcopy(self.raw)
        doc["capabilities"][0]["gap"] = "  "
        with self.assertRaises(ValueError):
            scorecard.validate(doc)

    def test_shipped_without_a_test_is_rejected(self):
        doc = copy.deepcopy(self.raw)
        doc["capabilities"][0]["evidence"] = [{"path": "toolrx/web/skills.js"}]
        with self.assertRaises(ValueError):
            scorecard.validate(doc)


class ScorecardDocsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = scorecard.validate(scorecard.load())
        cls.metrics = scorecard.metrics()
        cls.readme = open(README, encoding="utf-8").read()
        cls.pitch = open(PITCH, encoding="utf-8").read()

    def test_both_blocks_are_current(self):
        self.assertEqual(scorecard.check(), 0)

    def test_readme_has_one_generated_table(self):
        self.assertEqual(self.readme.count(scorecard.BLOCK_START), 1)
        self.assertEqual(self.readme.count(scorecard.BLOCK_END), 1)
        for cap in self.doc["capabilities"]:
            self.assertIn("| **%s** | %s |" % (cap["label"], cap["status"]),
                          self.readme)

    def test_pitch_has_one_generated_row_list(self):
        self.assertEqual(self.pitch.count(scorecard.BLOCK_START), 1)
        self.assertEqual(self.pitch.count(scorecard.BLOCK_END), 1)
        for cap in self.doc["capabilities"]:
            self.assertIn("<b>%s.</b>" % cap["label"], self.pitch)
            self.assertIn('class="tag %s">%s</span>'
                          % (scorecard.TAGS[cap["status"]], cap["status"]),
                          self.pitch)

    def test_pitch_counts_are_marker_bound(self):
        catalog = re.findall(
            re.escape(scorecard.CATALOG_START) + r"(.*?)"
            + re.escape(scorecard.CATALOG_END), self.pitch, re.S)
        tests = re.findall(
            re.escape(scorecard.TESTS_START) + r"(.*?)"
            + re.escape(scorecard.TESTS_END), self.pitch, re.S)
        self.assertGreaterEqual(len(catalog), 4)
        self.assertEqual(tests, ["%s" % f"{self.metrics['tests']:,}"])
        for value in catalog:
            self.assertEqual(value, f"{self.metrics['catalog']:,}")

    def test_metrics_line_quotes_every_derived_number(self):
        line = scorecard._metrics_line(self.metrics)
        for value in (f"{self.metrics['catalog']:,}",
                      f"{self.metrics['tests']:,}",
                      str(self.metrics["caps"]),
                      f"{self.metrics['everyday']:,}",
                      f"{self.metrics['routing']:,}",
                      f"{self.metrics['fixtures']:,}"):
            self.assertIn(value, line)
        self.assertIn(line, self.readme)

    def test_a_stale_block_fails_the_check(self):
        stale = self.readme.replace("| **Planning** | shipped |",
                                    "| **Planning** | partial |")
        self.assertNotEqual(stale, self.readme)
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            readme = pathlib.Path(tmp) / "README.md"
            pitch = pathlib.Path(tmp) / "pitch.html"
            readme.write_text(stale, encoding="utf-8")
            pitch.write_text(self.pitch, encoding="utf-8")
            old_readme, old_pitch = scorecard.README, scorecard.PITCH
            scorecard.README, scorecard.PITCH = readme, pitch
            try:
                self.assertEqual(scorecard.check(), 1)
            finally:
                scorecard.README, scorecard.PITCH = old_readme, old_pitch

    def test_checker_only_reads_checked_in_files(self):
        source = open(os.path.join(CORE, "scorecard.py"),
                      encoding="utf-8").read()
        self.assertNotIn("urllib", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("socket", source)
        self.assertNotRegex(source, r"\bfetch\s*\(")
        self.assertNotIn("http://", source)
        self.assertNotIn("https://", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)

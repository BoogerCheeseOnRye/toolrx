#!/usr/bin/env python3
"""Contract tests for the personal library catalog."""

import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from toolrx import library  # noqa: E402


class LibraryCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = library.load()

    def test_catalog_validates(self):
        self.assertEqual(library.validate(self.data), [])

    def test_coverage_counts(self):
        stats = library.summary(self.data)
        self.assertEqual(stats["records"], 10)
        self.assertEqual(stats["parts"], 13)
        self.assertEqual(stats["files"], 22)
        self.assertGreaterEqual(stats["programming"].get("cpp", 0), 7)

    def test_records_are_metadata_only(self):
        for rec in self.data["records"]:
            self.assertFalse(rec["rights"]["redistributable"], rec["id"])
            for key in ("text", "content", "body", "extracted_text"):
                self.assertNotIn(key, rec, rec["id"])

    def test_procedural_set_is_one_book_with_all_parts(self):
        rec = next(r for r in self.data["records"]
                   if r["id"] == "procedural-content-generation")
        files = [p["file"] for p in rec["parts"]]
        self.assertEqual(len(files), 13)
        for n in range(1, 13):
            self.assertIn(f"chapter{n:02d}.pdf", files)
        self.assertIn("interviews.pdf", files)

    def test_reading_paths_resolve(self):
        ids = {r["id"] for r in self.data["records"]}
        for rec in self.data["records"]:
            for target in rec["reading"].get("next") or []:
                self.assertIn(target, ids, rec["id"])

    def test_index_is_derived_and_searchable(self):
        index = library.build_index(self.data)
        self.assertEqual(len(index["documents"]), 10)
        self.assertIn("cpp-complete-guide", index["postings"]["cpp"])
        self.assertIn("procedural-content-generation", index["postings"]["pcg"])
        self.assertEqual(index["stats"]["records"], 10)

    def test_cli_check_passes(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "toolrx", "library.py"), "check"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("ok · 10 records", proc.stdout)

    def test_invalid_record_is_rejected(self):
        broken = {"version": 1, "records": [dict(self.data["records"][0])]}
        broken["records"][0]["reading"] = {"next": ["missing-book"]}
        self.assertTrue(library.validate(broken))
        broken = {"version": 1, "records": [dict(self.data["records"][0])]}
        broken["records"][0]["rights"] = {"status": "personal-copy",
                                          "redistributable": False}
        broken["records"][0]["text"] = "not allowed"
        self.assertTrue(any("non-redistributable" in e for e in library.validate(broken)))


if __name__ == "__main__":
    unittest.main(verbosity=2)

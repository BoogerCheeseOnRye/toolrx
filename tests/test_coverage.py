#!/usr/bin/env python3
"""Step 41: the coverage report is checked in and reproducible.

The report is the measurement that justifies catalog changes. These tests pin
its shape, its lane arithmetic, and the floors the roadmap promises: no
long-form family falls to chat fallback, and the minimum routing margin stays
above the step-34 floor.
"""

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORE = os.path.join(ROOT, "toolrx")
sys.path.insert(0, CORE)

import coverage  # noqa: E402

REPORT = os.path.join(CORE, "coverage.json")
COMMANDS = os.path.join(CORE, "web", "commands.json")


class CoverageReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(COMMANDS, encoding="utf-8") as fh:
            cls.commands = json.load(fh)["commands"]
        with open(REPORT, encoding="utf-8") as fh:
            cls.saved = json.load(fh)
        cls.report = coverage.build_report(full=True)

    def test_report_is_reproducible(self):
        self.assertEqual(
            json.loads(json.dumps(self.report, sort_keys=True)), self.saved)

    def test_catalog_metrics_match_the_generated_library(self):
        catalog = self.report["catalog"]
        self.assertEqual(catalog["count"], len(self.commands))
        self.assertEqual(catalog["duplicate_ids"], 0)
        self.assertEqual(catalog["duplicate_patterns"], 0)
        self.assertEqual(catalog["pure_literals"],
                         sum(1 for cmd in self.commands
                             if coverage.literal_text(cmd) is not None))
        counts = {}
        for cmd in self.commands:
            counts[cmd["c"]] = counts.get(cmd["c"], 0) + 1
        self.assertEqual(catalog["categories"], counts)

    def test_no_dead_literals(self):
        self.assertEqual(self.saved["audit"]["mode"], "full")
        self.assertEqual(self.saved["audit"]["dead_literals"], 0)
        self.assertEqual(self.saved["catalog"]["dead_literals"], 0)

    def test_every_fixture_family_is_reported(self):
        for family in coverage.FAMILIES:
            self.assertIn(family, self.saved["fixtures"])
            row = self.saved["fixtures"][family]
            self.assertGreater(row["cases"], 0)
            self.assertGreater(row["units"], 0)
            self.assertEqual(sum(row["lanes"].values()), row["units"])
            self.assertGreater(len(row["subfamilies"]), 0)
            for label, sub in row["subfamilies"].items():
                self.assertEqual(sum(sub["lanes"].values()), sub["units"], label)

    def test_no_family_falls_to_chat_fallback(self):
        for family in coverage.FAMILIES:
            lanes = self.saved["fixtures"][family]["lanes"]
            self.assertEqual(lanes["fallback"], 0, family)

    def test_router_margins_stay_above_the_step_34_floor(self):
        for family in coverage.FAMILIES:
            for label, sub in self.saved["fixtures"][family]["subfamilies"].items():
                stats = sub["margin"]
                if stats is None:
                    continue
                self.assertGreaterEqual(stats["min"], 0.019, f"{family}/{label}")

    def test_routing_and_plan_confidence_meet_their_floors(self):
        routing = self.saved["fixtures"]["routing"]["confidence"]
        plans = self.saved["fixtures"]["plans"]["confidence"]
        self.assertIsNotNone(routing)
        self.assertIsNotNone(plans)
        self.assertGreaterEqual(routing["min"], 0.50)
        self.assertGreaterEqual(plans["min"], 0.35)

    def test_builds_and_growth_resolve_exactly(self):
        for family in ("builds", "growth"):
            row = self.saved["fixtures"][family]
            self.assertEqual(row["lanes"]["exact"], row["units"], family)
            self.assertEqual(row["lanes"]["router"], 0, family)
            self.assertEqual(row["lanes"]["fallback"], 0, family)

    def test_dead_literal_audit_finds_a_shadow(self):
        commands = [
            {"id": "generic", "re": "^build a (.+) game$", "op": "build",
             "args": {}, "d": "build a {kind} game", "c": "build"},
            {"id": "literal", "re": "^build a rpg game$", "op": "build",
             "args": {}, "d": "build a rpg game", "c": "build"},
        ]
        dead = coverage.dead_literal_audit(commands)
        self.assertEqual([item["id"] for item in dead], ["literal"])
        self.assertEqual(dead[0]["shadowed_by"], "generic")

    def test_dead_literal_audit_keeps_a_live_literal(self):
        commands = [
            {"id": "literal", "re": "^hello world$", "op": "echo",
             "args": {}, "d": "hello world", "c": "misc"},
        ]
        self.assertEqual(coverage.dead_literal_audit(commands), [])

    def test_prefix_index_matches_a_full_scan(self):
        # The trie is an optimisation, not a second matcher. Exercise the
        # shapes that could fool a prefix parser: alternations, optional
        # groups, numeric envelopes, escaped spaces, and pure literals.
        def cmd(cid, pattern, category="misc"):
            return {"id": cid, "re": pattern, "op": "test", "args": {},
                    "d": cid, "c": category}

        commands = [
            cmd("generic-build", r"^build a (.+) game$"),
            cmd("literal-build", r"^build a rpg game$"),
            cmd("generic-reverse", r"^reverse (.+?)$"),
            cmd("literal-reverse", r"^reverse\ it$"),
            cmd("weekday", r"^(?:what is|what's|whats)\s+(-?(?:\d[\d,]*|one|two))\s+(?:km|kilometers)$"),
            cmd("convert", r"^convert\s+(-?(?:\d[\d,]*|one|two))\s+(?:km|kilometers)\s+(?:to|into)\s+(?:mi|miles)$"),
            cmd("add", r"^add (-?(?:\d[\d,]*|one|two)) and (-?(?:\d[\d,]*|one|two))$"),
            cmd("help", r"^help\s+(.+)$"),
            cmd("why", r"^(?:why|really|and|so)[.!?]?$"),
            cmd("feeling", r"^i (?:am|'m) feeling (.+)$"),
            cmd("date", r"^today's date$"),
            cmd("time", r"^what is the time$"),
            cmd("hello", r"^hello world$"),
        ]
        compiled = [(item, re.compile(item["re"], re.I)) for item in commands]
        index = coverage.PrefixIndex(commands)
        for query in (
            "build a rpg game",
            "build a huge space rpg game with crafting and 6 quests",
            "reverse it",
            "reverse hello",
            "what is 5 km",
            "what's 2 kilometers",
            "what is inside",
            "convert 5 km to miles",
            "convert one kilometer into miles",
            "add 2 and 3",
            "add sound",
            "help me",
            "why",
            "i'm feeling tired",
            "today's date",
            "what is the time",
            "hello",
            "hello world",
        ):
            expected = next((item for item, rx in compiled
                             if rx.match(coverage.normalize_query(query))), None)
            got = index.first_match(query)
            self.assertEqual(got and got["id"], expected and expected["id"], query)


if __name__ == "__main__":
    unittest.main(verbosity=2)

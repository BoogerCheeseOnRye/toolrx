#!/usr/bin/env python3
"""Step 37 long-form suite: the fixture file is the source of truth.

Every family in ``tests/fixtures/longform.json`` declares its prompt, its
expected structure, and its floors. This module checks the contract and the
cases Python can execute (routing, plans, refusals). ``test_envelope_js.py``
reads the same file and executes the browser families (builds, growth, and
context) in the real in-tab workspace.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(os.path.dirname(HERE), "toolrx")
sys.path.insert(0, CORE)

import longform  # noqa: E402
import pipeline  # noqa: E402
import router  # noqa: E402
import security  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "longform.json")
FAMILIES = ("routing", "plans", "builds", "growth", "context", "refusals")


class FixtureContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURES, encoding="utf-8") as fh:
            cls.fixtures = json.load(fh)

    def test_suite_size_and_family_coverage(self):
        total = sum(len(self.fixtures[name]) for name in FAMILIES)
        self.assertGreaterEqual(total, 48)
        self.assertLessEqual(total, 80)
        for name in FAMILIES:
            self.assertTrue(self.fixtures[name], name)
        for case in self.fixtures["routing"] + self.fixtures["plans"]:
            self.assertIn("family", case, case.get("name") or case.get("tool"))

    def test_at_least_six_prompts_exceed_four_thousand_characters(self):
        long_cases = [case for name in ("routing", "plans", "builds")
                      for case in self.fixtures[name]
                      if len(case["query"]) > 4000]
        self.assertGreaterEqual(len(long_cases), 6)

    def test_every_family_declares_a_minimum_length(self):
        for name in ("routing", "plans", "builds", "growth", "context"):
            self.assertGreaterEqual(self.fixtures["families"][name]["minChars"],
                                    500, name)

    def test_build_growth_and_context_cases_carry_expectations(self):
        for case in self.fixtures["builds"]:
            self.assertGreaterEqual(len(case["query"]), 500, case["name"])
            self.assertTrue(case["kind"], case["name"])
            self.assertTrue(case["files"], case["name"])
            self.assertTrue(case["deterministic"], case["name"])
        for case in self.fixtures["growth"]:
            self.assertGreaterEqual(len(case["base"]), 500, case["name"])
            self.assertTrue(case["steps"], case["name"])
            for step in case["steps"]:
                self.assertTrue(step["query"], case["name"])
                self.assertTrue(step["via"], case["name"])
        for case in self.fixtures["context"]:
            self.assertGreaterEqual(len(case["base"]), 500, case["name"])
            self.assertTrue(case.get("plan") or case.get("edit"), case["name"])


class LongPromptRoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURES, encoding="utf-8") as fh:
            cls.fixtures = json.load(fh)
        cls.model = router.load(os.path.join(CORE, "micro_model.json"))
        cls.policy = security.SecurityPolicy.load()
        cls.floor = cls.fixtures["families"]["routing"]

    def test_long_prompts_route_accurately(self):
        misses = []
        for case in self.fixtures["routing"]:
            self.assertGreaterEqual(len(case["query"]), self.floor["minChars"],
                                    case["tool"])
            clean = self.policy.normalize(case["query"])
            got = router.route(clean, self.model)
            if got["tool"] != case["tool"]:
                misses.append((case["tool"], got["tool"], case["query"][:80]))
        self.assertEqual(misses, [])

    def test_long_prompt_margins_are_not_degenerate(self):
        weak = []
        low_conf = []
        for case in self.fixtures["routing"]:
            clean = self.policy.normalize(case["query"])
            got = router.route(clean, self.model)
            if got["margin"] < self.floor["minMargin"]:
                weak.append((case["tool"], round(got["margin"], 4)))
            if got["confidence"] < self.floor["minConfidence"]:
                low_conf.append((case["tool"], round(got["confidence"], 4)))
        self.assertEqual(weak, [])
        self.assertEqual(low_conf, [])


class LongPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURES, encoding="utf-8") as fh:
            cls.fixtures = json.load(fh)
        cls.model = router.load(os.path.join(CORE, "micro_model.json"))
        cls.policy = security.SecurityPolicy.load()
        cls.floor = cls.fixtures["families"]["plans"]

    def test_plans_split_cleanly_and_route_in_order(self):
        for case in self.fixtures["plans"]:
            query = case["query"]
            self.assertGreaterEqual(len(query), self.floor["minChars"],
                                    case["name"])
            info = longform.split_info(query)
            ok, _, reason = self.policy.sanitize_plan(query)
            self.assertTrue(ok, (case["name"], reason))
            self.assertTrue(longform.is_plan(query), case["name"])
            self.assertFalse(info["overLimit"], case["name"])
            self.assertGreaterEqual(len(info["steps"]), 1, case["name"])
            got = [router.route(step, self.model) for step in info["steps"]]
            tools = [hit["tool"] for hit in got]
            if case.get("chunked"):
                # One over-long step is cut into chunks, and every chunk keeps
                # the same intent.
                self.assertGreater(len(info["steps"]), 1, case["name"])
                self.assertEqual(set(tools), set(case["tools"]), case["name"])
            else:
                self.assertEqual(tools, case["tools"], case["name"])
            for hit in got:
                self.assertGreaterEqual(hit["confidence"],
                                        case["minConfidence"], case["name"])
                self.assertGreaterEqual(hit["margin"], case["minMargin"],
                                        case["name"])

    def test_numbered_plan_is_inspectable_before_running(self):
        case = next(c for c in self.fixtures["plans"]
                    if c["name"] == "numbered-ops")
        info = longform.split_info(case["query"])
        self.assertEqual(info["total"], len(case["tools"]))
        self.assertFalse(info["truncated"])


class RefusalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURES, encoding="utf-8") as fh:
            cls.fixtures = json.load(fh)

    def test_hostile_and_oversized_prompts_are_refused(self):
        for case in self.fixtures["refusals"]:
            out = pipeline.process(case["query"])
            self.assertTrue(out["blocked"], case["name"])
            self.assertIn(case["reason"], out["reason"], case["name"])
            self.assertFalse((out.get("result") or {}).get("ok"), case["name"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

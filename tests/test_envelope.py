#!/usr/bin/env python3
"""Step 35 envelope: long prompts, plans, and refusal fixtures.

The routing fixtures are 500-2,000+ character prompts written the way a person
would actually phrase a request. They must route accurately with a healthy
margin, plans must split in order and route every step, and hostile or oversized
input must still be refused before execution.
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


class LongPromptRoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURES, encoding="utf-8") as fh:
            cls.fixtures = json.load(fh)
        cls.model = router.load(os.path.join(CORE, "micro_model.json"))
        cls.policy = security.SecurityPolicy.load()

    def test_at_least_twenty_long_prompts(self):
        self.assertGreaterEqual(len(self.fixtures["routing"]), 20)
        for case in self.fixtures["routing"]:
            self.assertGreaterEqual(len(case["query"]), 500, case["tool"])

    def test_long_prompts_route_accurately(self):
        misses = []
        for case in self.fixtures["routing"]:
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
            if got["margin"] < 0.02:
                weak.append((case["tool"], round(got["margin"], 4)))
            if got["confidence"] < 0.50:
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

    def test_plans_split_cleanly_and_route_in_order(self):
        for case in self.fixtures["plans"]:
            query = case["query"]
            info = longform.split_info(query)
            ok, _, reason = self.policy.sanitize_plan(query)
            self.assertTrue(ok, (case["name"], reason))
            self.assertTrue(longform.is_plan(query), case["name"])
            self.assertFalse(info["overLimit"], case["name"])
            self.assertGreaterEqual(len(info["steps"]), 1, case["name"])
            got = [router.route(step, self.model)["tool"] for step in info["steps"]]
            if case.get("chunked"):
                # One over-long step is cut into chunks, and every chunk keeps
                # the same intent.
                self.assertGreater(len(info["steps"]), 1, case["name"])
                self.assertEqual(set(got), set(case["tools"]), case["name"])
            else:
                self.assertEqual(got, case["tools"], case["name"])

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

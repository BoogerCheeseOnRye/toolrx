#!/usr/bin/env python3
"""Contract tests for the synonym/paraphrase table (step 48).

`toolrx/paraphrase.json` is the only source of paraphrase expansion. The exact
matcher gets its `exact` templates through `toolrx/build_commands.py`; the
hashed router gets the same table's `knowledge` lines through
`toolrx/builder.py`. These tests pin the export, prove every new route is
reachable and captures the right arguments, prove the builder consumes the
knowledge lines, and measure the fixed prompt set before and after expansion.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORE = os.path.join(ROOT, "toolrx")
sys.path.insert(0, CORE)

import builder  # noqa: E402
import coverage  # noqa: E402
import paraphrase  # noqa: E402

COMMANDS = os.path.join(CORE, "web", "commands.json")
TABLE = os.path.join(CORE, "paraphrase.json")
FIXTURE = os.path.join(HERE, "fixtures", "paraphrase.json")
EVAL = os.path.join(HERE, "fixtures", "paraphrase_eval.json")

SAMPLES = {
    "list": "5 and 7",
    "a": "5",
    "b": "7",
    "n": "2",
    "text": "the quick brown fox",
    "text2": "fox brown quick the",
    "key": "favourite colour",
    "value": "blue",
    "name": "beta",
    "slug": "alpha",
    "find": "a",
    "repl": "b",
    "topic": "x",
}


def concrete(template):
    out = template
    for key, value in SAMPLES.items():
        out = out.replace("{" + key + "}", value)
    return out


def expected_args(template, args):
    captures = paraphrase.compile_template(template)[1]
    values = {index + 1: SAMPLES[name] for index, name in enumerate(captures)}
    out = {}
    for key, value in args.items():
        match = paraphrase._CAPTURE_ARG.match(value)
        out[key] = values[int(match.group(1))] if match else value
    return out


class TableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(COMMANDS, encoding="utf-8") as handle:
            cls.commands = json.load(handle)["commands"]
        with open(FIXTURE, encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        with open(EVAL, encoding="utf-8") as handle:
            cls.eval = json.load(handle)
        cls.table = paraphrase.load()
        cls.entries = list(paraphrase.entries())
        cls.index = coverage.PrefixIndex(cls.commands)

    def test_fixture_is_current(self):
        proc = subprocess.run([sys.executable, os.path.join(CORE,
                                                           "paraphrase.py"),
                               "--check"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        self.assertIn("current", proc.stdout)

    def test_export_round_trips(self):
        self.assertEqual(paraphrase.export(), self.fixture)
        self.assertEqual(self.fixture["version"], 1)
        self.assertEqual(self.fixture["tableSha256"],
                         paraphrase.export()["tableSha256"])

    def test_counts_match_the_expansion(self):
        counts = self.fixture["counts"]
        self.assertEqual(counts["intents"], len(self.table["intents"]))
        self.assertEqual(counts["exact"], len(self.entries))
        knowledge = sum(len(intent["knowledge"])
                        for intent in self.table["intents"].values())
        self.assertEqual(counts["knowledge"], knowledge)
        self.assertGreaterEqual(counts["intents"], 20)
        self.assertGreaterEqual(counts["exact"], 50)
        self.assertGreaterEqual(counts["knowledge"], 40)
        self.assertLessEqual(counts["exact"], paraphrase.MAX_EXACT_TOTAL)

    def test_synonyms_expand_deterministically(self):
        synonyms = paraphrase._synonyms(self.table)
        first = paraphrase.expand("tally {list}", synonyms)
        second = paraphrase.expand("tally {list}", synonyms)
        self.assertEqual(first, second)
        self.assertEqual(first, ["tally {list}"])
        expanded = paraphrase.expand("{sum} {list}", synonyms)
        self.assertEqual(expanded, ["tally {list}", "add up {list}",
                                    "sum up {list}"])

    def test_catalog_matches_the_table_exactly(self):
        shipped = [command for command in self.commands
                   if command["id"].startswith("paraphrase.")]
        self.assertEqual(shipped, self.entries)

    def test_every_route_is_new_and_captures_the_right_arguments(self):
        failures = []
        for entry in self.entries:
            query = concrete(entry["d"])
            hit = self.index.first_match(query)
            if hit is None:
                failures.append((entry["id"], query, "no match"))
                continue
            if hit["id"] != entry["id"]:
                failures.append((entry["id"], query,
                                 "shadowed by " + hit["id"]))
                continue
            got = paraphrase._fill_args(hit, query)
            want = expected_args(entry["d"], entry["args"])
            if got != want:
                failures.append((entry["id"], query, got, want))
        self.assertFalse(failures, failures[:10])

    def test_knowledge_lines_are_used_by_the_builder(self):
        with open(os.path.join(CORE, "catalog.json"), encoding="utf-8") as handle:
            catalog = json.load(handle)
        names = [tool["name"] for tool in catalog["tools"]]
        self.assertTrue(any(paraphrase.knowledge(name) for name in names))
        for name in names:
            lines = paraphrase.knowledge(name)
            self.assertEqual(len(lines), len(set(lines)), name)

    def test_evaluation_fixture_is_well_formed(self):
        self.assertEqual(self.eval["version"], 1)
        prompts = self.eval["prompts"]
        self.assertGreaterEqual(len(prompts), 30)
        lanes = {}
        for case in prompts:
            lanes[case["lane"]] = lanes.get(case["lane"], 0) + 1
            self.assertTrue(case["query"].strip())
            self.assertTrue(case["tool"])
            if case["lane"] == "exact":
                self.assertTrue(case["op"])
                self.assertIsInstance(case["args"], dict)
            elif case["lane"] == "router":
                self.assertNotIn("op", case)
        self.assertEqual(lanes, {"exact": 22, "router": 10})


class ValidationTest(unittest.TestCase):
    def write(self, table):
        directory = tempfile.mkdtemp(prefix="toolrx-paraphrase-table-")
        self.addCleanup(shutil.rmtree, directory, True)
        path = os.path.join(directory, "paraphrase.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(table, handle)
        return path

    def base(self):
        with open(TABLE, encoding="utf-8") as handle:
            return json.load(handle)

    def assertRejected(self, table, needle):
        with self.assertRaises(ValueError) as caught:
            paraphrase.table(self.write(table))
        self.assertIn(needle, str(caught.exception))

    def test_unknown_placeholder_is_rejected(self):
        table = self.base()
        table["intents"]["project.list"]["exact"].append(
            {"text": "do the {bogus} thing", "op": "project.list", "args": {}})
        self.assertRejected(table, "unknown placeholder")

    def test_duplicate_capture_is_rejected(self):
        table = self.base()
        table["intents"]["memory.note"]["exact"].append(
            {"text": "say {text} and {text}", "op": "memory.note",
             "args": {"text": "$1"}})
        self.assertRejected(table, "repeats capture")

    def test_unknown_tool_is_rejected(self):
        table = self.base()
        table["intents"]["fs.list_dir"]["tool"] = "fs.nope"
        self.assertRejected(table, "unknown tool")

    def test_bad_capture_index_is_rejected(self):
        table = self.base()
        table["intents"]["memory.note"]["exact"].append(
            {"text": "say {text}", "op": "memory.note",
             "args": {"text": "$2"}})
        self.assertRejected(table, "points at $2")

    def test_unused_capture_is_rejected(self):
        table = self.base()
        table["intents"]["memory.note"]["exact"].append(
            {"text": "say {text}", "op": "memory.note", "args": {}})
        self.assertRejected(table, "never uses capture")

    def test_duplicate_phrase_across_intents_is_rejected(self):
        table = self.base()
        table["intents"]["project.list"]["exact"].append(
            {"text": "jot down that {text}", "op": "project.list",
             "args": {"text": "$1"}})
        self.assertRejected(table, "duplicates")

    def test_knowledge_cap_is_enforced(self):
        table = self.base()
        table["intents"]["fs.list_dir"]["knowledge"] = [
            "line %d" % index
            for index in range(paraphrase.MAX_KNOWLEDGE_PER_INTENT + 1)
        ]
        self.assertRejected(table, "more than")


class BuilderExpansionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(CORE, "catalog.json"), encoding="utf-8") as handle:
            cls.catalog = json.load(handle)

    def test_expansion_changes_only_tools_with_knowledge(self):
        plain, _, _ = builder.count_docs(self.catalog, CORE, expand=False)
        expanded, _, _ = builder.count_docs(self.catalog, CORE, expand=True)
        for tool in self.catalog["tools"]:
            name = tool["name"]
            if paraphrase.knowledge(name):
                self.assertNotEqual(plain[name], expanded[name], name)
            else:
                self.assertEqual(plain[name], expanded[name], name)

    def test_expansion_is_deterministic(self):
        first = builder.count_docs(self.catalog, CORE, expand=True)
        second = builder.count_docs(self.catalog, CORE, expand=True)
        self.assertEqual(first, second)


class MeasurementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metrics = paraphrase.measure()

    def test_exact_hit_rate_improves(self):
        exact = self.metrics["exact"]
        self.assertEqual(exact["total"], 22)
        self.assertEqual(exact["before"], 0)
        self.assertEqual(exact["after"], exact["total"])
        self.assertGreater(exact["rate_after"], exact["rate_before"])

    def test_router_median_margin_does_not_drop(self):
        router = self.metrics["router"]
        self.assertEqual(router["total"], 10)
        self.assertGreaterEqual(router["median_margin_after"],
                                router["median_margin_before"])
        self.assertGreaterEqual(router["hits_after"], router["hits_before"])

    def test_model_grows_only_from_the_table(self):
        sizes = self.metrics["model_bytes"]
        self.assertGreater(sizes["after"], sizes["before"])
        # The step-34 model cap is 1.5x the pre-expansion baseline.
        self.assertLessEqual(sizes["after"], 541042)


if __name__ == "__main__":
    unittest.main(verbosity=2)

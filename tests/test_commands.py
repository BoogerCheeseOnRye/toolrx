#!/usr/bin/env python3
"""Contract tests for the generated deterministic command library.

`toolrx/web/commands.json` is what the static Pages build actually matches
against, so it is worth testing directly: every pattern must compile, the
library must stay large, and the first matching entry must be the intended one.
"""

import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COMMANDS = os.path.join(ROOT, "toolrx", "web", "commands.json")


def _normalize(q):
    q = re.sub(r"\s+", " ", q).strip()
    q = re.sub(r"[?!]+$", "", q)
    return re.sub(r"\.$", "", q)


class CommandLibraryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(COMMANDS, encoding="utf-8") as f:
            cls.data = json.load(f)
        cls.commands = cls.data["commands"]
        # Compile once: re's LRU cache is far smaller than the library, so
        # re.match(pattern, ...) in a loop would recompile thousands of times.
        cls.compiled = [(c, re.compile(c["re"], re.I)) for c in cls.commands]

    def first(self, query):
        q = _normalize(query)
        for c, rx in self.compiled:
            if rx.match(q):
                return c
        return None

    def test_library_is_large(self):
        self.assertGreaterEqual(self.data["count"], 2500)
        self.assertGreaterEqual(len(self.commands), 2500)

    def test_every_pattern_compiles(self):
        for c in self.commands:
            try:
                re.compile(c["re"], re.I)
            except re.error as e:  # pragma: no cover - failure detail
                self.fail(f"{c['id']}: {e}")

    def test_ids_are_unique(self):
        ids = [c["id"] for c in self.commands]
        self.assertEqual(len(ids), len(set(ids)))

    def test_common_prompts_match_intended_handler(self):
        cases = {
            "multiply 67 and 420": ("math.binary", "mul"),
            "square 67": ("math.unary", "square"),
            "double 67": ("math.unary", "double"),
            "factors of 84": ("math.unary", "factors"),
            "is 91 divisible by 7": ("math.binary", "divisible"),
            "convert 5 km to miles": ("unit.convert", "km"),
            "5 km in mi": ("unit.convert", "km"),
            "what is 20% of 250": ("math.binary", "pct_of"),
            "count the words": ("text.count", "words"),
            "reverse it": ("text.transform", "reverse"),
            "uppercase it": ("text.transform", "upper"),
            "capital of france": ("fact.capital", None),
            "what is the chemical symbol for gold": ("fact.symbol", None),
            "how many days in february": ("date.op", "daysin"),
            "what day is it": ("date.op", "dayname"),
            "build a calculator app": ("build", "calculator"),
            "build me a todo list": ("build", "todo list"),
            "build an rpg": ("build", "rpg"),
            "build a snake game": ("build", "snake"),
            "build a 2048 game": ("build", "2048"),
            "build a tetris game with 3d elements": ("build", "tetris"),
            "build an rpg based on king arthur": ("build", "rpg"),
            "build an rpg based on india": ("build", "rpg"),
            "build an rpg set in space": ("build", "rpg"),
            "build a social media website": ("build", "social"),
            "build a forum website": ("build", "forum"),
            "plan an rpg": ("plan", None),
            "blueprint a todo app": ("blueprint", None),
            "new project notes": ("project.new", None),
            "list projects": ("project.list", None),
            "show project files": ("project.files", None),
            "open project notes": ("project.open", None),
            "delete project notes": ("project.delete", None),
            "change the name from verdant wood rpg to india": ("project.rename", None),
            "rename project rpg to india": ("project.rename", None),
            "rename it to camelot": ("project.rename", None),
            "change the project name to bharata": ("project.rename", None),
            "call this project india": ("project.rename", None),
            "change the page title to camelot field notes": ("project.title", None),
            "add a theme toggle": ("project.themeToggle", None),
            "make this project light": ("project.theme", None),
            "add a footer note saying offline copy for ada": ("project.note", None),
            "remember my favorite color is teal": ("memory.remember", None),
            "remember that the launch code is 42": ("memory.remember", None),
            "make a note that the meeting moved to friday": ("memory.note", None),
            "what is my favorite color": ("memory.recall", None),
            "what do you remember about my dog": ("memory.recall", None),
            "what do you remember": ("memory.list", None),
            "forget my favorite color": ("memory.forget", None),
            "forget everything": ("memory.forget", None),
            "what did i build last": ("memory.context", None),
            "what was i working on": ("memory.context", None),
            "hello": ("chat", None),
            "i feel overwhelmed": ("chat", None),
            "tell me a joke": ("chat", None),
            "what is my name": ("chat", None),
            "wikipedia ada lovelace": ("web.search", None),
            "define serendipity": ("web.define", None),
            "weather in reykjavik": ("web.weather", None),
            "summarize it": ("text.summarize", None),
        }
        for query, (op, arg) in cases.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], op, query)
            if arg is not None:
                joined = json.dumps(hit["args"])
                self.assertIn(arg, joined, f"{query}: {hit['id']} {hit['args']}")

    def test_build_variants_capture_the_modifier(self):
        cases = {
            "build a tetris game with 3d elements": ("tetris", "3d elements"),
            "build an rpg based on king arthur": ("rpg", "king arthur"),
            "build an rpg based on india": ("rpg", "india"),
            "build an rpg set in space": ("rpg", "space"),
        }
        for query, (kind, desc) in cases.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], "build", query)
            self.assertEqual(hit["args"].get("kind"), kind, query)
            self.assertEqual(hit["args"].get("desc"), "$1", query)

    def test_unit_breadth(self):
        cats = self.data["categories"]
        self.assertGreaterEqual(cats.get("units", 0), 1800)
        self.assertGreaterEqual(cats.get("build", 0), 300)

    def test_pronoun_forms_exist(self):
        for q in ("sort it", "remove duplicate lines", "slugify it",
                  "reverse the lines", "double it", "square the result"):
            self.assertIsNotNone(self.first(q), q)


if __name__ == "__main__":
    unittest.main(verbosity=2)

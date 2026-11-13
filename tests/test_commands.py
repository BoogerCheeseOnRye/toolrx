#!/usr/bin/env python3
"""Contract tests for the generated deterministic command library.

`toolrx/web/commands.json` is what the static Pages build actually matches
against, so it is worth testing directly: every pattern must compile, the
library must stay large, and the first matching entry must be the intended one.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
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

    def args_for(self, command, query):
        """Expand $n placeholders exactly like web/skills.js applyArgs()."""
        m = re.match(command["re"], _normalize(query), re.I)
        self.assertIsNotNone(m, query)

        def fill(value):
            if not isinstance(value, str):
                return value
            if re.fullmatch(r"\$\d+", value):
                return m.group(int(value[1:])) or ""
            return re.sub(r"\$(\d+)",
                          lambda hit: m.group(int(hit.group(1))) or "", value)
        return {k: fill(v) for k, v in command["args"].items()}

    def test_library_is_large(self):
        # The floor is a regression guard, not a target: step 41 removed
        # literal patterns that could never be the first match.
        self.assertGreaterEqual(self.data["count"], 11000)
        self.assertGreaterEqual(len(self.commands), 11000)
        self.assertEqual(self.data["count"], len(self.commands))

    def test_patterns_are_unique(self):
        seen, duplicates = set(), set()
        for c in self.commands:
            # `re.escape` writes a literal space as `\ `; normalise it so the
            # check sees the same duplicate the generator sees.
            key = re.sub(r"\s+", "", c["re"].lower().replace("\\ ", " "))
            if key in seen:
                duplicates.add(key)
            seen.add(key)
        self.assertFalse(duplicates, sorted(duplicates)[:5])

    def test_category_counts_match_the_catalog(self):
        counts = {}
        for c in self.commands:
            counts[c["c"]] = counts.get(c["c"], 0) + 1
        self.assertEqual(self.data["categories"], counts)

    def test_catalog_regenerates_byte_identically(self):
        script = os.path.join(ROOT, "toolrx", "build_commands.py")
        with tempfile.TemporaryDirectory() as tmp:
            blobs = []
            for i in range(2):
                out = os.path.join(tmp, f"commands{i}.json")
                env = dict(os.environ, TOOLRX_COMMANDS_OUT=out)
                subprocess.run([sys.executable, script], env=env, check=True,
                               capture_output=True, timeout=120)
                with open(out, "rb") as fh:
                    blobs.append(fh.read())
            self.assertEqual(blobs[0], blobs[1], "generator is not deterministic")
            generated = json.loads(blobs[0])
            self.assertEqual(generated["count"], self.data["count"])
            self.assertEqual(generated["commands"], self.commands)

    def test_bundles_and_growth_route_with_arguments(self):
        bundle = self.first("add double jump and sound and a quest")
        self.assertIsNotNone(bundle)
        self.assertEqual(bundle["op"], "edit.apply.many")
        args = self.args_for(bundle, "add double jump and sound and a quest")
        self.assertIn("double jump", args["list"])
        self.assertIn("sound", args["list"])
        self.assertIn("a quest", args["list"])

        comma = self.first("add a boss, sound and a quest")
        self.assertEqual(comma["op"], "edit.apply.many")
        self.assertIn("a boss", self.args_for(comma, "add a boss, sound and a quest")["list"])

        single = self.first("add sound")
        self.assertEqual(single["op"], "edit.apply")

        growth = {
            "grow project": ("project.grow", {}),
            "expand module core": ("module.expand", {"module": "core"}),
            "add crafting system": ("system.add", {"system": "crafting"}),
            "add a save system": ("system.add", {"system": "save"}),
        }
        for query, (op, expected) in growth.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], op, query)
            self.assertEqual(self.args_for(hit, query), expected, query)

    def test_context_commands_route_with_exact_arguments(self):
        exact = {
            "what is in context": "context.show",
            "show context": "context.show",
            "context": "context.show",
            "clear context": "context.clear",
            "clear all context": "context.clear.all",
            "continue from previous": "context.continue",
            "resume the last plan": "context.continue",
            "apply the same changes to the other files": "context.apply_others",
        }
        for query, op in exact.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], op, query)

        expand = self.first("expand the last plan with add day/night")
        self.assertIsNotNone(expand)
        self.assertEqual(expand["op"], "context.expand")
        self.assertEqual(self.args_for(expand, "expand the last plan with add day/night"),
                         {"more": "add day/night"})

    def test_project_bundles_route_with_exact_arguments(self):
        exact = {
            "export this project": ("project.export", {}),
            "export the project": ("project.export", {}),
            "export the active project": ("project.export", {}),
            "export project": ("project.export", {}),
            "export the workspace": ("workspace.export", {}),
            "export all projects": ("workspace.export", {}),
            "list bundles": ("workspace.bundles", {}),
            "show bundles": ("workspace.bundles", {}),
        }
        for query, (op, expected) in exact.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], op, query)
            self.assertEqual(self.args_for(hit, query), expected, query)

        named = {
            "export project notes": ("project.export", {"slug": "notes"}),
            "export the project verdant wood": ("project.export",
                                                {"slug": "verdant wood"}),
            "import the project from notes.toolrx.json":
                ("project.import", {"bundle": "notes.toolrx.json"}),
            "import the workspace from workspace.toolrx.json":
                ("workspace.import", {"bundle": "workspace.toolrx.json"}),
        }
        for query, (op, expected) in named.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], op, query)
            self.assertEqual(self.args_for(hit, query), expected, query)

    def test_multi_system_growth_routes_in_one_step(self):
        cases = {
            "add inventory and dialogue and save systems":
                "inventory and dialogue and save",
            "add the ui and audio and weather systems":
                "ui and audio and weather",
            "add inventory and dialogue systems":
                "inventory and dialogue",
            "add inventory and dialogue and combat and save and quests "
            "and crafting and ui and audio and weather and particles and ai systems":
                "inventory and dialogue and combat and save and quests "
                "and crafting and ui and audio and weather and particles and ai",
        }
        for query, expected in cases.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], "system.add.many", query)
            self.assertEqual(self.args_for(hit, query), {"list": expected}, query)
        single = self.first("add crafting system")
        self.assertEqual(single["op"], "system.add")
        self.assertEqual(self.args_for(single, "add crafting system"),
                         {"system": "crafting"})

    def test_long_compositional_prompts_keep_kind_and_modifiers(self):
        cases = {
            "build a huge space rpg game with crafting":
                ("rpg", ["huge space", "crafting"]),
            "build a small cyberpunk platformer game":
                ("platformer", ["small cyberpunk"]),
            "build a medieval roguelike game with quests":
                ("roguelike", ["medieval", "quests"]),
            "build an epic underwater farming sim with weather":
                ("farming sim", ["epic underwater", "weather"]),
            "build a sprawling astral exploration game with dialogue trees":
                ("exploration", ["sprawling astral", "dialogue trees"]),
            "build a pirate tower defense game":
                ("tower defense", ["pirate"]),
            "build a pixel art tetris game":
                ("tetris", ["pixel art"]),
            "build a large maze game":
                ("maze", ["large"]),
        }
        for query, (kind, words) in cases.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], "build", query)
            args = self.args_for(hit, query)
            self.assertEqual(args.get("kind"), kind, query)
            desc = args.get("desc", "")
            for word in words:
                self.assertIn(word, desc, f"{query}: {desc!r}")

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
            "build a twin-stick shooter game": ("build", "twin-stick shooter"),
            "build a roguelike game": ("build", "roguelike"),
            "build a tower defense game": ("build", "tower defense"),
            "build a match-3 puzzle game": ("build", "match-3 puzzle"),
            "build a farming sim game": ("build", "farming sim"),
            "build a card battler game": ("build", "card battler"),
            "build a rhythm game": ("build", "rhythm game"),
            "build a low-poly exploration game": ("build", "low-poly exploration"),
            "build a wave shooter game": ("build", "wave shooter"),
            "build a block builder game": ("build", "block builder"),
            "build a tetris game with 3d elements": ("build", "tetris"),
            "build an rpg based on king arthur": ("build", "rpg"),
            "build a page about it": ("build.web", None),
            "make a website about it": ("build.web", None),
            "build a page about ada lovelace": ("build.web", None),
            "turn that into a page": ("build.web", None),
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

    def test_library_and_language_commands(self):
        cases = {
            "library stats": ("library.stats", None),
            "find a book about shaders": ("library.find", "$1"),
            "list books by language c++": ("library.language", "$1"),
            "what should i read next": ("library.next", None),
            "library gaps": ("library.gaps", None),
            "list beginner books": ("library.level", "$1"),
            "what language is this": ("lang.detect", None),
            "what programming language is this: int main(){}": ("lang.detect", "$1"),
            "what natural language is this: hola amigos": ("lang.detect", "$1"),
            "reply in spanish": ("lang.reply", "$1"),
            "switch to japanese": ("lang.reply", "$1"),
            "reply language": ("lang.reply", None),
            "back to english": ("lang.reply", "en"),
        }
        for query, (op, arg) in cases.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], op, query)
            if arg is not None:
                values = [hit["args"].get(k) for k in ("text", "topic", "lang", "level", "id")]
                self.assertIn(arg, values, query)
        self.assertIn("library", self.data)
        self.assertEqual(self.data["library"]["stats"]["records"], 10)

    def test_composable_edit_commands(self):
        cases = {
            "add double jump": "double-jump",
            "give it a double jump": "double-jump",
            "add three enemy types": "enemy-types",
            "add a boss": "boss",
            "add a quest": "quest",
            "add day/night": "day-night",
            "add sound": "sound",
            "make it harder": "harder",
            "switch to isometric": "isometric",
            "make it 3d": "three-d",
        }
        for query, patch in cases.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], "edit.apply", query)
            self.assertEqual(hit["args"].get("patch"), patch, query)

        for query, size in (("make the world 96x96", "96"),
                            ("make the world 120 by 120", "120"),
                            ("grow the world to 64x64", "64")):
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], "edit.apply", query)
            self.assertEqual(hit["args"].get("patch"), "world", query)
            self.assertEqual(hit["args"].get("arg"), "$1", query)
            m = re.match(hit["re"], query, re.I)
            self.assertIsNotNone(m, query)
            self.assertEqual(m.group(1), size, query)

        for query in ("undo", "undo that", "undo the last edit", "revert"):
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], "edit.undo", query)

        # `switch to {lang}` is intentionally broad, so edits must stay ahead
        # of it in the catalog or "switch to isometric" would set a language.
        self.assertEqual(self.first("switch to spanish")["op"], "lang.reply")
        self.assertGreaterEqual(self.data["categories"].get("edit", 0), 40)

    def test_optional_llm_commands(self):
        cases = {
            "llm status": ("llm.status", None),
            "llm settings": ("llm.status", None),
            "llm on": ("llm.on", None),
            "turn off the llm": ("llm.off", None),
            "clear the llm cache": ("llm.cache", None),
            "apply the llm patch": ("llm.apply", None),
            "install the llm patch": ("llm.apply", None),
            "discard the llm patch": ("llm.discard", None),
            "reject the llm patch": ("llm.discard", None),
        }
        for query, (op, arg) in cases.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], op, query)

        hit = self.first("llm plan a cozy mail route")
        self.assertEqual(hit["op"], "llm.plan")
        m = re.match(hit["re"], "llm plan a cozy mail route", re.I)
        self.assertEqual(m.group(1), "a cozy mail route")

        hit = self.first("llm patch app.js with make the player faster")
        self.assertEqual(hit["op"], "llm.patch")
        m = re.match(hit["re"], "llm patch app.js with make the player faster", re.I)
        self.assertEqual(m.group(1), "app.js")
        self.assertEqual(m.group(2), "make the player faster")

        # The generative commands must not shadow deterministic builds/edits.
        self.assertEqual(self.first("build a platformer game")["op"], "build")
        self.assertEqual(self.first("add double jump")["op"], "edit.apply")
        self.assertGreaterEqual(self.data["categories"].get("llm", 0), 25)

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

    def test_target_free_text_commands_beat_generic_patterns(self):
        # These are exact, target-free commands. The generic "reverse {text}"
        # shape must not capture "the lines" as literal text.
        expected = {
            "reverse the lines": "reverselines",
            "reverse the line order": "reverselines",
            "reverse the words": "reversewords",
            "indent the lines": "indent",
            "uppercase it": "upper",
        }
        for query, op in expected.items():
            hit = self.first(query)
            self.assertIsNotNone(hit, query)
            self.assertEqual(hit["op"], "text.transform", query)
            self.assertEqual(self.args_for(hit, query).get("op"), op, query)


if __name__ == "__main__":
    unittest.main(verbosity=2)

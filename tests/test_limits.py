#!/usr/bin/env python3
"""Step 38: one numeric envelope for Python and the browser.

`toolrx/limits.json` is the checked-in source of truth. Python reads it through
`toolrx/envelope.py`; the browser reads the generated `toolrx/web/limits.js`.
These tests prove the generator is current, both runtimes expose the same
values, the `limits` command reports them, and no module has quietly grown a
private copy of a cap.
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
WEB = os.path.join(CORE, "web")
sys.path.insert(0, CORE)

import envelope  # noqa: E402
import gen_limits  # noqa: E402

LIMITS_JSON = os.path.join(CORE, "limits.json")
LIMITS_JS = os.path.join(WEB, "limits.js")
COMMANDS = os.path.join(WEB, "commands.json")
NODE = shutil.which("node")

# Active caps that must never be assigned a literal again. Range clamps (for
# operator overrides) are allowed to be literal; these names are not.
DUPLICATED = re.compile(
    r"\b(?:SINGLE_MAX|PLAN_MAX|PLAN_STEPS|MAX_BLOCK|MAX_OUT|MAX_FILE|"
    r"MAX_TOTAL|MAX_PROJECT_FILE|MAX_PROJECT|MAX_PROJECT_FILES|"
    r"BUILD_TIMEOUT|STEP_TIMEOUT|PLAN_TIMEOUT|UNDO_DEFAULT)\s*=\s*\d"
)
CONTEXT_LITERAL = re.compile(r"\bvar\s+LIMIT\s*=\s*\d")
POLICY_KEYS = ("max_len", "max_plan_len", "max_plan_steps",
               "max_step_ms", "max_plan_ms")


class EnvelopeSourceTest(unittest.TestCase):
    def test_limits_json_is_valid_and_complete(self):
        data = envelope.load()
        self.assertEqual(data["version"], 1)
        for key in envelope._RANGES:
            self.assertIn(key, data)
            self.assertIsInstance(data[key], int, key)

    def test_ranges_are_enforced(self):
        base = envelope.load()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "limits.json")
            bad = dict(base, singleChars=0)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(bad, fh)
            with self.assertRaises(ValueError):
                envelope.load(path)

            missing = dict(base)
            missing.pop("contextBytes")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(missing, fh)
            with self.assertRaises(ValueError):
                envelope.load(path)

            version = dict(base, version=2)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(version, fh)
            with self.assertRaises(ValueError):
                envelope.load(path)

    def test_python_table_names_every_cap(self):
        data = envelope.load()
        text = envelope.table()
        self.assertIn("toolrx/limits.json", text)
        for key in envelope._RANGES:
            self.assertIn(key, text)
            self.assertIn(str(data[key]), text)


class GeneratedJavascriptTest(unittest.TestCase):
    def test_generated_module_is_current(self):
        expected = gen_limits.render(envelope.load())
        with open(LIMITS_JS, encoding="utf-8") as fh:
            actual = fh.read()
        self.assertEqual(actual, expected,
                         "toolrx/web/limits.js is stale: run python3 toolrx/gen_limits.py")

    def test_generated_module_carries_the_same_values(self):
        with open(LIMITS_JS, encoding="utf-8") as fh:
            text = fh.read()
        match = re.search(r"Object\.freeze\((\{.*?\})\);", text, re.S)
        self.assertIsNotNone(match, "limits.js does not define a frozen object")
        self.assertEqual(json.loads(match.group(1)), envelope.load())

    def test_browser_has_no_private_numeric_copy(self):
        offenders = []
        for name in os.listdir(CORE):
            if not name.endswith(".py"):
                continue
            path = os.path.join(CORE, name)
            with open(path, encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, 1):
                    if DUPLICATED.search(line):
                        offenders.append(f"{name}:{line_no}")
        for name in os.listdir(WEB):
            if not name.endswith(".js") or name == "limits.js":
                continue
            path = os.path.join(WEB, name)
            with open(path, encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, 1):
                    if DUPLICATED.search(line) or CONTEXT_LITERAL.search(line):
                        offenders.append(f"web/{name}:{line_no}")
        self.assertEqual(offenders, [])

    def test_policy_keeps_allowlists_only(self):
        with open(os.path.join(CORE, "policy.json"), encoding="utf-8") as fh:
            policy = json.load(fh)
        for key in POLICY_KEYS:
            self.assertNotIn(key, policy)
        with open(os.path.join(CORE, "security.py"), encoding="utf-8") as fh:
            src = fh.read()
        for key in POLICY_KEYS:
            self.assertNotIn(f'policy.get("{key}"', src)


class LimitsCommandTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(COMMANDS, encoding="utf-8") as fh:
            cls.data = json.load(fh)

    def test_catalog_exposes_limits(self):
        hits = [c for c in self.data["commands"]
                if c["op"] == "system" and c.get("args", {}).get("op") == "limits"]
        patterns = {c["re"] for c in hits}
        self.assertIn(r"^limits$", patterns)
        self.assertIn(r"^show\ limits$", patterns)

    def test_catalog_count_is_current(self):
        self.assertEqual(self.data["count"], len(self.data["commands"]))
        self.assertEqual(self.data["count"], 12504)


@unittest.skipUnless(NODE, "node is not installed")
class BrowserLimitsTest(unittest.TestCase):
    JS = r"""
const fs = require('fs');
const path = require('path');
const WEB = process.argv[1];
global.self = global;
const store = {};
global.localStorage = {
  getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.dispatchEvent = () => {};
for (const name of ['limits.js', 'skills.js', 'context.js', 'sandbox.js']) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}
console.log(JSON.stringify({
  limits: self.toolrxSkills.limits,
  web: self.toolrxWeb.limits(),
  context: self.toolrxContext.LIMIT,
  text: self.toolrxSkills.limitsText(),
}));
"""

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([NODE, "-e", cls.JS, WEB],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-3000:])
        cls.out = json.loads(proc.stdout)

    def test_browser_values_match_the_python_envelope(self):
        data = envelope.load()
        self.assertEqual(self.out["limits"], {
            "single": data["singleChars"], "plan": data["planChars"],
            "steps": data["planSteps"], "block": data["blockBytes"],
            "stepMs": data["stepMs"], "planMs": data["planMs"],
        })
        self.assertEqual(self.out["context"], data["contextBytes"])
        web = self.out["web"]
        self.assertEqual(web["file"], data["projectFileBytes"])
        self.assertEqual(web["project"], data["projectBytes"])
        self.assertEqual(web["files"], data["projectFiles"])
        self.assertEqual(web["timeout"], data["buildMs"])
        self.assertEqual(web["readFile"], data["readFileBytes"])
        self.assertEqual(web["readTotal"], data["readTotalBytes"])
        self.assertEqual(web["stepTimeout"], data["stepMs"])
        self.assertEqual(web["planTimeout"], data["planMs"])

    def test_browser_limits_text_names_the_source_and_caps(self):
        data = envelope.load()
        text = self.out["text"]
        self.assertIn("toolrx/limits.json", text)
        self.assertIn("web/limits.js", text)
        for key in envelope._RANGES:
            self.assertIn(key, text)
            self.assertIn(str(data[key]), text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

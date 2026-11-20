#!/usr/bin/env python3
"""Step 63: one bounded pure-compute program, identical in both runtimes.

`toolrx/compute.py` is the Python twin of the compute block in
`toolrx/web/skills.js`. The checked-in fixture is generated from Python and
replayed through Node, so a change to either side that moves a byte, a cap, or
an operation count fails here. The tests also prove the deny list is closed,
that a refusal names the cap it hit, and that the wall clock can stop a script.
"""

import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORE = os.path.join(ROOT, "toolrx")
WEB = os.path.join(CORE, "web")
FIXTURE = os.path.join(HERE, "fixtures", "compute.json")
SKILLS = os.path.join(WEB, "skills.js")
NODE = shutil.which("node")
sys.path.insert(0, CORE)

import compute  # noqa: E402
import envelope  # noqa: E402

JS = r"""
const fs = require('fs');
const path = require('path');
const WEB = process.argv[1];
const FIXTURE = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
global.self = global;
global.fetch = () => Promise.resolve({
  ok: true,
  json: () => Promise.resolve(JSON.parse(fs.readFileSync(path.join(WEB, 'commands.json'), 'utf8'))),
});
global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
eval(fs.readFileSync(path.join(WEB, 'limits.js'), 'utf8'));
eval(fs.readFileSync(path.join(WEB, 'skills.js'), 'utf8'));

(async () => {
  await self.toolrxSkills.init('commands.json');
  const out = {};
  const base = self.toolrxSkills.computeLimits();
  out.caps = base;
  out.fixtureCaps = FIXTURE.caps;
  out.results = FIXTURE.cases.map(c => {
    const limits = Object.assign({}, base, c.limits || {});
    const r = self.toolrxSkills.compute(c.src, limits);
    const got = { src: c.src, ok: r.ok };
    if (r.ok) got.text = r.text;
    else { got.error = r.error; got.cap = r.cap; }
    got.ops = r.ops; got.vars = r.vars; got.statements = r.statements;
    return got;
  });
  out.route = self.toolrxSkills.match('compute let x = 2 | x * 3');
  out.pipeKept = self.toolrxSkills.splitPrompt('compute let x = 2 | x * 3');
  out.semicolonSplit = self.toolrxSkills.splitPrompt('compute 1; compute 2');
  try {
    await self.toolrxSkills.exec({ op: 'math.expr', args: { expr: 'fetch(1)' } });
    out.denyExec = 'no error';
  } catch (e) { out.denyExec = String(e.message || e); }
  try {
    await self.toolrxSkills.exec({ op: 'math.expr', args: { expr: '1' + '+1'.repeat(250) } });
    out.capExec = 'no error';
  } catch (e) { out.capExec = String(e.message || e); }
  // No network is needed once the command table is loaded.
  delete global.fetch;
  out.offline = self.toolrxSkills.compute('2 + 2');
  const ticks = [0, 0, 100];
  const slow = self.toolrxSkills.compute('1 + 2', Object.assign({}, base),
    () => ticks.shift());
  out.slow = { ok: slow.ok, error: slow.error, cap: slow.cap };
  const exact = [0, 50, 50, 50];
  const fine = self.toolrxSkills.compute('1 + 2', Object.assign({}, base),
    () => exact.shift());
  out.exact = { ok: fine.ok, text: fine.text };
  console.log(JSON.stringify(out));
})();
"""


def load_fixture():
    with open(FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)


class ComputePythonTest(unittest.TestCase):
    def test_caps_come_from_the_envelope(self):
        limits = envelope.load()
        self.assertEqual(compute.caps(), {
            "chars": limits["computeChars"],
            "statements": limits["computeStatements"],
            "ops": limits["computeOps"],
            "vars": limits["computeVars"],
            "ms": limits["computeMs"],
            "resultChars": limits["computeResultChars"],
        })

    def test_fixture_is_current(self):
        with open(FIXTURE, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), compute.fixture())

    def test_cli_check(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(CORE, "compute.py"), "--check"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("is current", proc.stdout)

    def test_arithmetic_and_locals(self):
        cases = {
            "16/100*4": "0.64",
            "2 + 3 * 4": "14",
            "2 ^ 3 ^ 2": "512",
            "-2 ^ 2": "-4",
            "7 % -3": "1",
            "-7 % 3": "-1",
            "let x = 2 | x * 3": "6",
            "let a = 1 | let b = 2 | a + b": "3",
            "x = 5 | x + 1": "6",
            "# note\n1 + 2": "3",
            "1e-7": "1e-7",
            "1.5e3": "1500",
        }
        for source, want in cases.items():
            out = compute.run(source)
            self.assertTrue(out["ok"], (source, out))
            self.assertEqual(out["text"], want, source)

    def test_strings_arrays_and_booleans(self):
        cases = {
            'upper("ada")': "ADA",
            'title("hello world")': "Hello World",
            'join(["a","b"], "-")': "a-b",
            'slice("hello", -3)': "llo",
            'length("héllo")': "5",
            "sort([3,1,2])": "[1, 2, 3]",
            "unique([1,1,2])": "[1, 2]",
            "sum([1,2,3])": "6",
            "[1,2] == [1,2]": "true",
            "true and false": "false",
            "not true": "false",
            "null": "null",
            '"a" + 1': "a1",
        }
        for source, want in cases.items():
            out = compute.run(source)
            self.assertTrue(out["ok"], (source, out))
            self.assertEqual(out["text"], want, source)

    def test_every_refusal_names_its_cap(self):
        cases = [
            ("1|2|3", {"statements": 2}, "computeStatements"),
            ("1+2+3", {"ops": 2}, "computeOps"),
            ("let a=1 | let b=2", {"vars": 1}, "computeVars"),
            ("1+2", {"chars": 2}, "computeChars"),
            ('repeat("ab", 3)', {"resultChars": 4}, "computeResultChars"),
        ]
        for source, limits, cap in cases:
            out = compute.run(source, limits)
            self.assertFalse(out["ok"], source)
            self.assertEqual(out["cap"], cap, source)
            self.assertIn(cap, out["error"], source)
            self.assertIn("compute refused:", out["error"], source)

    def test_source_cap_counts_code_points(self):
        out = compute.run("é" * 3, {"chars": 2})
        self.assertFalse(out["ok"])
        self.assertIn("source is 3 chars", out["error"])

    def test_wall_clock_refuses(self):
        def clock_at(values):
            state = {"i": 0}

            def tick():
                value = values[min(state["i"], len(values) - 1)]
                state["i"] += 1
                return value

            return tick

        out = compute.run("1 + 2", clock=clock_at([0, 0, 100]))
        self.assertFalse(out["ok"])
        self.assertEqual(out["cap"], "computeMs")
        self.assertIn("computeMs", out["error"])
        fine = compute.run("1 + 2", clock=clock_at([0, 50, 50, 50]))
        self.assertTrue(fine["ok"], fine)
        self.assertEqual(fine["text"], "3")

    def test_deny_list_is_closed(self):
        for name in sorted(compute.DENY):
            for source in (name, name + "(1)"):
                out = compute.run(source)
                self.assertFalse(out["ok"], source)
                self.assertIn("compute refused:", out["error"], source)
                self.assertIn("is not available in compute", out["error"], source)

    def test_unknown_names_refuse_before_evaluation(self):
        for source, message in [
            ("unknownname", "unknown name unknownname"),
            ("a.b", 'unexpected "."'),
            ("1 +", 'expected a value near "end"'),
            ("not 1", "not needs a boolean"),
            ("1/0", "division by zero"),
            ("sqrt(-1)", "square root of a negative number"),
        ]:
            out = compute.run(source)
            self.assertFalse(out["ok"], source)
            self.assertIn(message, out["error"], source)

    def test_no_dynamic_code_in_the_compute_block(self):
        with open(SKILLS, encoding="utf-8") as handle:
            source = handle.read()
        start = source.index("/* ------------------------------------------------------- expressions --- */")
        end = source.index("/* ------------------------------------------------------------ utils --- */")
        block = source[start:end]
        for token in ("eval(", "new Function", "Function(", "import(",
                      "document.", "window.", "fetch(", "XMLHttpRequest",
                      "localStorage", "setTimeout(", "require("):
            self.assertNotIn(token, block, token)
        for name in ("eval", "fetch", "document", "localstorage", "settimeout"):
            self.assertIn('"' + name + '"', block, name)


@unittest.skipUnless(NODE, "node is not installed")
class ComputeParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", JS, WEB, FIXTURE],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-3000:])
        cls.out = json.loads(proc.stdout)
        cls.fixture = load_fixture()

    def test_caps_match_limits_js(self):
        self.assertEqual(self.out["caps"], self.fixture["caps"])

    def test_fixture_replays_byte_for_byte(self):
        want = []
        for case in self.fixture["cases"]:
            entry = {"src": case["src"], "ok": case["ok"]}
            if case["ok"]:
                entry["text"] = case["text"]
            else:
                entry["error"] = case["error"]
                entry["cap"] = case["cap"]
            entry["ops"] = case["ops"]
            entry["vars"] = case["vars"]
            entry["statements"] = case["statements"]
            want.append(entry)
        self.assertEqual(self.out["results"], want)

    def test_compute_route_survives_plan_splitting(self):
        self.assertEqual(self.out["route"]["op"], "math.expr")
        self.assertEqual(self.out["route"]["args"]["expr"], "let x = 2 | x * 3")
        self.assertEqual(self.out["pipeKept"], ["compute let x = 2 | x * 3"])
        self.assertEqual(len(self.out["semicolonSplit"]), 2)

    def test_handler_surfaces_refusals(self):
        self.assertIn("compute refused:", self.out["denyExec"])
        self.assertIn("computeOps", self.out["capExec"])

    def test_compute_needs_no_network(self):
        self.assertTrue(self.out["offline"]["ok"])
        self.assertEqual(self.out["offline"]["text"], "4")

    def test_wall_clock_matches(self):
        self.assertFalse(self.out["slow"]["ok"])
        self.assertEqual(self.out["slow"]["cap"], "computeMs")
        self.assertTrue(self.out["exact"]["ok"])
        self.assertEqual(self.out["exact"]["text"], "3")


class ComputeCatalogTest(unittest.TestCase):
    def test_catalog_has_the_compute_route(self):
        with open(os.path.join(WEB, "commands.json"), encoding="utf-8") as handle:
            commands = json.load(handle)
        if isinstance(commands, dict):
            commands = commands.get("commands", [])
        hits = [c for c in commands
                if c.get("op") == "math.expr" and "compute" in c.get("re", "")]
        self.assertTrue(hits, "no compute route in commands.json")

    def test_build_source_declares_the_route(self):
        with open(os.path.join(CORE, "build_commands.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("(?:calculate|compute|evaluate|work out|solve)", source)


if __name__ == "__main__":
    unittest.main()

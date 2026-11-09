#!/usr/bin/env python3
"""Repo hygiene + UI contract tests (stdlib unittest).

These are the guardrails for publishing: no real device identifiers, no
phone-specific paths, no training UI by default, no Grok mark, and a context
bar that stays hidden until a model supplies a window.
"""

import os
import re
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Markers that must never appear in a publishable tree. Built from fragments so
# this guard file does not itself contain the literal strings it forbids.
FORBIDDEN = [
    "/mnt/" + "storage",
    "/mnt/" + "v10",
    "/data/data/" + "com.termux",
    "/sd" + "card",
    "Re" + "vvl",
    "ASUS " + "E2" + "00HA",
    "god" + "box",
]
# Android serials are ~16 upper-case alphanumerics mixing digits and letters.
SERIAL_RE = re.compile(r"\b(?=[0-9A-Z]{16}\b)(?=[0-9A-Z]*[0-9])[0-9A-Z]+\b")
SKIP_DIRS = {".git", "__pycache__", "node_modules", "data", "logs", "run", "preview", ".venv"}


def _tracked_files():
    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files"],
                             capture_output=True, text=True, timeout=30)
        return [f for f in out.stdout.splitlines() if f]
    except Exception:
        return []


def _walk_source():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith((".py", ".html", ".json", ".md", ".sh", ".txt")):
                yield os.path.join(dirpath, fn)


class RepoHygieneTest(unittest.TestCase):
    def test_forbidden_strings_absent_from_tracked_files(self):
        hits = []
        for rel in _tracked_files():
            path = os.path.join(ROOT, rel)
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for needle in FORBIDDEN:
                if needle in text:
                    hits.append(f"{rel}: {needle}")
            for m in SERIAL_RE.finditer(text):
                hits.append(f"{rel}: serial-like {m.group(0)}")
        self.assertEqual(hits, [], f"personal/device data in repo: {hits}")

    def test_local_device_state_is_not_tracked(self):
        tracked = set(_tracked_files())
        for rel in ("toolrx/devices.json", "toolrx/devnames.json",
                    "toolrx/tasks.json", "harness-devices.json"):
            self.assertNotIn(rel, tracked, f"{rel} must stay local/gitignored")

    def test_example_device_configs_exist(self):
        for rel in ("toolrx/devices.example.json", "harness-devices.example.json"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), rel)

    def test_no_hardcoded_serial_in_server(self):
        # Android serials are ~16 upper-case alphanumerics that mix digits and
        # letters; plain words like PYTHONUNBUFFERED must not trip this.
        src = open(os.path.join(ROOT, "toolrx", "server.py"), encoding="utf-8").read()
        self.assertNotRegex(src, r"\b(?=[0-9A-Z]{16}\b)(?=[0-9A-Z]*[0-9])[0-9A-Z]+\b")


class DashboardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = open(os.path.join(ROOT, "toolrx", "dashboard.html"), encoding="utf-8").read()

    def test_no_grok_mark(self):
        self.assertNotIn("BOT_HEAD", self.html)
        self.assertNotIn("Grok", self.html)
        self.assertNotIn("229.54", self.html)

    def test_mascot_present(self):
        self.assertIn('id="botmark"', self.html)
        self.assertIn('id="botPose"', self.html)
        self.assertIn("GAZE_X", self.html)
        self.assertIn("blinkT", self.html)

    def test_context_bar_hidden_by_default(self):
        self.assertIn(".ctxbar{display:none", self.html)
        self.assertIn("if(!total)", self.html)

    def test_training_hidden_by_default(self):
        self.assertIn("#trainwrap #traincard,#trainwrap #modelcard{display:none}", self.html)
        self.assertIn("trainingEnabled", self.html)

    def test_host_card_uses_dynamic_cpu(self):
        self.assertIn("d.cpu", self.html)
        self.assertNotIn("Atom x5-Z8350", self.html)

    def test_local_models_are_discovered(self):
        # command center lists real local backends/models, not a fake cluster
        self.assertIn("/models/local", self.html)
        self.assertIn("cmLocalModel", self.html)
        self.assertNotIn("Android cluster (needle)", self.html)

    def test_wireguard_lives_in_command_center(self):
        self.assertIn('id="cmWg"', self.html)
        self.assertNotIn('id="wgDot"', self.html)

    def test_single_host_hides_cluster_controls(self):
        self.assertIn("d.kind!=='host'", self.html)
        self.assertIn('id="clusterStart"', self.html)

    def test_pages_copy_matches_dashboard(self):
        pages = os.path.join(ROOT, "docs", "index.html")
        self.assertTrue(os.path.exists(pages), "run python3 docs/build.py")
        self.assertEqual(self.html, open(pages, encoding="utf-8").read(),
                         "docs/index.html is stale: run python3 docs/build.py")

    def test_static_fallback_present(self):
        self.assertIn("staticMode", self.html)
        self.assertIn("browserHost", self.html)

    def test_no_phone_paths_in_training_options(self):
        # training is hidden, but its options should not leak a phone path
        self.assertNotIn("/sd" + "card/", self.html)


if __name__ == "__main__":
    unittest.main(verbosity=2)

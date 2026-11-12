#!/usr/bin/env python3
"""Repo hygiene + UI contract tests (stdlib unittest).

These are the guardrails for publishing: no real device identifiers, no
phone-specific paths, no training UI by default, no Grok mark, and a context
bar that stays hidden until a model supplies a window.
"""

import json
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

    def test_in_browser_router_is_wired_up(self):
        # Pages must run the router, not show a dead demo
        self.assertIn('src="web/router.js"', self.html)
        self.assertIn('src="web/sandbox.js"', self.html)
        self.assertIn('src="web/skills.js"', self.html)
        self.assertIn('src="web/templates.js"', self.html)
        self.assertIn("toolrxWeb", self.html)
        self.assertIn("clientMode", self.html)
        self.assertNotIn("static demo</b>", self.html)

    def test_command_library_and_preview_are_wired(self):
        self.assertIn("toolrxSkills.init('web/commands.json')", self.html)
        self.assertIn("toolrxWeb.prompt", self.html)
        self.assertIn("srcdoc", self.html)
        self.assertIn("toolrxWeb.onPreview", self.html)
        # the preview pane must not be hidden just because the page is static
        self.assertNotIn("body.client-demo #previewPane", self.html)
        self.assertNotIn("body.static-demo #previewPane", self.html)

    def test_composer_tracks_the_dynamic_viewport(self):
        self.assertIn("height:100dvh", self.html)
        self.assertIn("interactive-widget=resizes-content", self.html)
        self.assertIn("viewport-fit=cover", self.html)

    def test_mobile_preview_is_reachable(self):
        self.assertIn("pvMobile", self.html)
        self.assertIn("#previewPane.mobile-show", self.html)
        self.assertIn("body.static-demo #pvMobile", self.html)

    def test_projects_are_manageable_from_the_composer(self):
        self.assertIn('id="projBtn"', self.html)
        self.assertIn('id="projModal"', self.html)
        self.assertIn("openProjects", self.html)
        self.assertIn("renderProjectList", self.html)
        self.assertIn("newProject", self.html)
        self.assertIn("deleteProject", self.html)
        self.assertIn("refreshProjectChip", self.html)

    def test_project_files_have_an_editor(self):
        self.assertIn('id="fileModal"', self.html)
        self.assertIn('id="fileText"', self.html)
        self.assertIn('id="fileSave"', self.html)
        self.assertIn("openFileEditor", self.html)
        self.assertIn("writeProjectFile", self.html)
        self.assertIn("projectFile", self.html)

    def test_project_export_import_ui(self):
        self.assertIn('id="pjImport"', self.html)
        self.assertIn('id="pjFile"', self.html)
        self.assertIn("exportProject", self.html)
        self.assertIn("importProject", self.html)
        sandbox = open(os.path.join(ROOT, "toolrx", "web", "sandbox.js"),
                       encoding="utf-8").read()
        for marker in ("function exportProject", "function importProject",
                       "MAX_IMPORT_FILE", "safeImportName", "uniqueSlug(name)"):
            self.assertIn(marker, sandbox)

    def test_dialogs_are_keyboard_accessible(self):
        for marker in ('role="dialog"', 'aria-modal="true"',
                       'aria-labelledby="pjTitle"', 'aria-labelledby="fileTitle"',
                       'aria-labelledby="cpTitle"', 'aria-live="polite"',
                       "prefers-reduced-motion", "function openDialog",
                       "function closeDialog", "offsetParent",
                       "stopImmediatePropagation"):
            self.assertIn(marker, self.html)

    def test_command_catalog_ui(self):
        for marker in ('id="cmdBtn"', 'id="cmdPalette"', 'id="cpInput"',
                       'id="cpCat"', "function renderCatalog",
                       "function openCmdPalette", "toolrxSkills.catalog"):
            self.assertIn(marker, self.html)

    def test_library_panel_ui(self):
        for marker in ('id="libBtn"', 'id="libModal"', 'id="libInput"',
                       'id="libLevel"', 'id="libLang"', 'id="libStatus"',
                       "function libRender", "function openLibrary",
                       "toolrxSkills.libraryPanel", "toolrx.library.status",
                       "next up", "status: "):
            self.assertIn(marker, self.html)

    def test_chat_messages_show_measured_throughput(self):
        for marker in ("function tokenMeta", "tok/s", "characters ÷ 4",
                       "not model inference", "r.ms"):
            self.assertIn(marker, self.html)
        skills = open(os.path.join(ROOT, "toolrx", "web", "skills.js"),
                      encoding="utf-8").read()
        self.assertIn("result.ms = Math.max(0, Math.round(clock() - started))", skills)

    def test_conversation_memory_is_explicit_and_local(self):
        sandbox = open(os.path.join(ROOT, "toolrx", "web", "sandbox.js"),
                       encoding="utf-8").read()
        skills = open(os.path.join(ROOT, "toolrx", "web", "skills.js"),
                      encoding="utf-8").read()
        self.assertIn('remember("last_build"', sandbox)
        self.assertIn("clearMemory", sandbox)
        for op in ("memory.remember", "memory.note", "memory.recall",
                   "memory.list", "memory.forget", "memory.context"):
            self.assertIn(op, skills)

    def test_chat_results_render_as_conversation(self):
        self.assertIn("toolrx · chat", self.html)
        self.assertIn(".lbl.chat", self.html)
        self.assertIn("r.source", self.html)

    def test_mobile_layout(self):
        self.assertIn("@media(max-width:900px)", self.html)
        self.assertIn('id="drawerBackdrop"', self.html)
        self.assertIn('id="devClose"', self.html)
        self.assertIn("env(safe-area-inset-bottom)", self.html)

    def test_pages_web_assets_match(self):
        for name in ("blake2b.js", "router.js", "sandbox.js", "skills.js",
                     "templates.js", "lang.js", "i18n.json",
                     "engine2d.js", "engine2d.embed.js",
                     "engine3d.js", "engine3d.embed.js", "worldgen.js",
                     "worldgen.embed.js", "rpg2.js", "rpg2.embed.js",
                     "commands.json"):
            src = os.path.join(ROOT, "toolrx", "web", name)
            out = os.path.join(ROOT, "docs", "web", name)
            self.assertTrue(os.path.exists(out), "run python3 docs/build.py")
            self.assertEqual(open(src, "rb").read(), open(out, "rb").read(),
                             f"docs/web/{name} is stale")
        model = os.path.join(ROOT, "toolrx", "micro_model.json")
        out = os.path.join(ROOT, "docs", "web", "model.json")
        self.assertTrue(os.path.exists(out), "run python3 docs/build.py")
        self.assertEqual(open(model, "rb").read(), open(out, "rb").read(),
                         "docs/web/model.json is stale")

    def test_engine_embed_matches_source(self):
        for name, var in (("engine2d", "toolrxEngine2dSource"),
                          ("engine3d", "toolrxEngine3dSource"),
                          ("worldgen", "toolrxWorldgenSource"),
                          ("rpg2", "toolrxRpg2Source")):
            src = open(os.path.join(ROOT, "toolrx", "web", name + ".js"),
                       encoding="utf-8").read()
            embed = open(os.path.join(ROOT, "toolrx", "web", name + ".embed.js"),
                         encoding="utf-8").read()
            m = re.search(var + r' = (".*");', embed)
            self.assertTrue(m, "run python3 toolrx/embed_engine.py")
            self.assertEqual(json.loads(m.group(1)), src, name + " embed is stale")

    def test_engine_loads_before_templates(self):
        marks = ['src="web/engine2d.js"', 'src="web/engine2d.embed.js"',
                 'src="web/engine3d.js"', 'src="web/engine3d.embed.js"',
                 'src="web/worldgen.js"', 'src="web/worldgen.embed.js"',
                 'src="web/rpg2.js"', 'src="web/rpg2.embed.js"',
                 'src="web/templates.js"']
        for mark in marks:
            self.assertIn(mark, self.html)
        order = [self.html.index(m) for m in marks]
        self.assertEqual(order, sorted(order))

    def test_offline_cache_includes_the_engines(self):
        sw = open(os.path.join(ROOT, "toolrx", "web", "sw.js"),
                  encoding="utf-8").read()
        self.assertIn("toolrx-shell-v8", sw)
        self.assertIn("./web/engine2d.js", sw)
        self.assertIn("./web/engine2d.embed.js", sw)
        self.assertIn("./web/engine3d.js", sw)
        self.assertIn("./web/engine3d.embed.js", sw)
        self.assertIn("./web/worldgen.js", sw)
        self.assertIn("./web/worldgen.embed.js", sw)
        self.assertIn("./web/rpg2.js", sw)
        self.assertIn("./web/rpg2.embed.js", sw)
        self.assertIn("./web/lang.js", sw)
        self.assertIn("./web/i18n.json", sw)

    def test_offline_app_is_installable_and_cached(self):
        for rel in ("toolrx/web/sw.js", "toolrx/web/manifest.webmanifest",
                    "toolrx/web/icon.svg", "docs/sw.js", "docs/manifest.webmanifest",
                    "docs/icon.svg"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), rel)
        for name in ("sw.js", "manifest.webmanifest", "icon.svg"):
            src = open(os.path.join(ROOT, "toolrx", "web", name), "rb").read()
            out = open(os.path.join(ROOT, "docs", name), "rb").read()
            self.assertEqual(src, out, f"docs/{name} is stale")
        manifest = json.loads(open(os.path.join(ROOT, "toolrx", "web", "manifest.webmanifest"),
                                   encoding="utf-8").read())
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "./")
        self.assertTrue(manifest["icons"])
        sw = open(os.path.join(ROOT, "toolrx", "web", "sw.js"), encoding="utf-8").read()
        for marker in ("addEventListener(\"install\"", "addEventListener(\"activate\"",
                       "addEventListener(\"fetch\"", "caches.match", "skipWaiting",
                       "./web/commands.json", "./web/model.json"):
            self.assertIn(marker, sw)
        self.assertIn('rel="manifest"', self.html)
        self.assertIn("registerOffline", self.html)
        self.assertIn("serviceWorker.register", self.html)

    def test_no_phone_paths_in_training_options(self):
        # training is hidden, but its options should not leak a phone path
        self.assertNotIn("/sd" + "card/", self.html)


if __name__ == "__main__":
    unittest.main(verbosity=2)

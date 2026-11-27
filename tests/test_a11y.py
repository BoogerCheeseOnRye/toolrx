#!/usr/bin/env python3
"""Step 68: accessibility and mobile polish.

These tests audit the shipped shell rather than a mock. The HTML is the real
`toolrx/dashboard.html`; the budget status words are driven in Node through the
real `toolrx/web/budget.js`. They pin the mobile composer, the focus contracts
for the drawers and dialogs, reduced-motion handling, status text alternatives,
and the offline/install story. They do not start a server, a browser, or a
network call.
"""

import json
import os
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HTML = os.path.join(ROOT, "toolrx", "dashboard.html")
BUDGET = os.path.join(ROOT, "toolrx", "web", "budget.js")
NODE = shutil.which("node")

with open(HTML, encoding="utf-8") as fh:
    PAGE = fh.read()

BUDGET_JS = r"""
const fs = require('fs');
global.self = global;
eval(fs.readFileSync(process.argv[1], 'utf8'));
const B = self.toolrxBudget;
const bars = B.bars({
  chars:   { used: 10,  max: 100 },
  steps:   { used: 85,  max: 100 },
  context: { used: 101, max: 100 },
  project: { used: 0,   max: 0 },
  time:    { used: 50,  max: 100 },
});
console.log(JSON.stringify({ bars, warn: B.WARN_AT, order: B.ORDER }));
"""


class MobileShellTest(unittest.TestCase):
    def test_viewport_handles_notches_and_the_keyboard(self):
        self.assertIn("viewport-fit=cover", PAGE)
        self.assertIn("interactive-widget=resizes-content", PAGE)
        self.assertIn("env(safe-area-inset-bottom)", PAGE)
        self.assertIn("env(safe-area-inset-left)", PAGE)
        self.assertIn("env(safe-area-inset-right)", PAGE)

    def test_composer_is_phone_friendly(self):
        self.assertIn('enterkeyhint="send"', PAGE)
        self.assertIn('autocapitalize="sentences"', PAGE)
        self.assertIn('autocomplete="off"', PAGE)
        self.assertIn('spellcheck="true"', PAGE)
        self.assertIn("font-size:16px", PAGE)
        self.assertIn("@media(max-width:380px)", PAGE)

    def test_shell_never_forces_a_horizontal_scroll(self):
        self.assertIn("overflow-x:hidden", PAGE)
        self.assertIn("max-width:100vw", PAGE)
        self.assertIn("main,.workspace,.panes,.pane,.composer,.hintrow{min-width:0;max-width:100%}",
                      PAGE)
        self.assertIn("overflow-wrap:anywhere", PAGE)
        self.assertIn("#budgetBar.on{grid-template-columns:repeat(2,minmax(0,1fr))}", PAGE)


class FocusContractTest(unittest.TestCase):
    def test_global_focus_ring_is_visible(self):
        self.assertIn(":focus-visible{outline:2px solid var(--accent)", PAGE)
        self.assertIn("outline-offset:2px", PAGE)

    def test_device_drawer_traps_and_returns_focus(self):
        for marker in ("let drawerReturn=null", "function openDrawer()",
                       "function closeDrawer()", "drawerReturn=document.activeElement",
                       "back.focus()", "aria-expanded",
                       "devices.setAttribute('aria-hidden'",
                       "devices.removeAttribute('inert')",
                       "devices.setAttribute('inert','')"):
            self.assertIn(marker, PAGE)

    def test_device_detail_moves_focus_to_its_close_button(self):
        for marker in ("let detailReturn=null", "detailReturn=document.activeElement",
                       "close.focus()", 'aria-label="close device details"',
                       "el.setAttribute('aria-hidden','true')"):
            self.assertIn(marker, PAGE)

    def test_quality_drawer_is_a_real_dialog(self):
        for marker in ('id="qc" role="dialog" aria-label="quality curves"',
                       'aria-hidden="true" inert',
                       "window.openQualityCurves=function",
                       "window.closeQualityCurves=function",
                       "qcReturn=document.activeElement", "qcBtn.setAttribute('aria-expanded'",
                       'aria-label="close quality curves"'):
            self.assertIn(marker, PAGE)

    def test_dialogs_keep_their_existing_trap_and_escape(self):
        for marker in ("function openDialog", "function closeDialog",
                       "dialogReturn", "stopImmediatePropagation",
                       "if(e.key!=='Tab') return", "offsetParent"):
            self.assertIn(marker, PAGE)

    def test_clickable_cards_are_keyboard_controls(self):
        for marker in ("card.tabIndex=0", "card.setAttribute('role','button')",
                       "card.setAttribute('aria-pressed'",
                       "card.addEventListener('keydown'",
                       "if(e.target!==card) return",
                       "el.tabIndex=0",
                       "el.setAttribute('aria-label','training cycle')",
                       "el.onkeydown=e=>{",
                       'id="botSlot" role="button" tabindex="0"',
                       "slot.addEventListener('keydown'"):
            self.assertIn(marker, PAGE)

    def test_context_meter_is_a_labelled_progressbar(self):
        for marker in ('id="ctxprog" role="progressbar"',
                       'aria-valuetext="0 used of 0"',
                       "prog.setAttribute('aria-valuenow'",
                       "prog.setAttribute('aria-valuetext'",
                       "context tokens used"):
            self.assertIn(marker, PAGE)

    def test_chart_png_labels_are_keyboard_reachable(self):
        for marker in ("b.setAttribute('role','button')",
                       "b.setAttribute('tabindex','0')",
                       "b.setAttribute('aria-label','download '",
                       "b.onkeydown=e=>{ if(e.key==='Enter'"):
            self.assertIn(marker, PAGE)


class StatusTextTest(unittest.TestCase):
    @unittest.skipUnless(NODE, "node is not installed")
    def test_every_bar_has_a_status_in_words(self):
        proc = subprocess.run([NODE, "-e", BUDGET_JS, BUDGET],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-4000:])
        out = json.loads(proc.stdout)
        bars = {bar["key"]: bar for bar in out["bars"]}
        self.assertEqual(bars["chars"]["level"], "ok")
        self.assertEqual(bars["chars"]["status"], "within cap")
        self.assertEqual(bars["steps"]["level"], "warn")
        self.assertEqual(bars["steps"]["status"], "near cap")
        self.assertEqual(bars["context"]["level"], "over")
        self.assertEqual(bars["context"]["status"], "over cap")
        self.assertTrue(bars["context"]["over"])
        self.assertEqual(bars["project"]["level"], "ok")
        self.assertEqual(bars["project"]["status"], "within cap")
        for bar in out["bars"]:
            self.assertIn(bar["status"], ("within cap", "near cap", "over cap"))
            self.assertEqual(bar["status"] == "over cap", bar["over"])

    def test_the_ui_prints_the_status_word(self):
        for marker in ("const status=b.status||", 'class="bg-status"',
                       "+status+'", "aria-valuetext=", "near cap", "over cap",
                       "within cap"):
            self.assertIn(marker, PAGE)

    def test_build_and_run_status_are_announced(self):
        self.assertIn('id="buildStatus" role="status" aria-live="polite"', PAGE)
        self.assertIn('id="lastRunDetail" aria-live="polite"', PAGE)
        self.assertIn("el.setAttribute('aria-expanded'", PAGE)


class ReducedMotionTest(unittest.TestCase):
    def test_decorative_motion_stops(self):
        self.assertIn("@media(prefers-reduced-motion:reduce)", PAGE)
        for marker in ("animation:none !important", "#botmark", "#botPose",
                       ".devcard .flow::before", ".cm-bot .mark",
                       ".bg-fill,.ctxprog>div,.devcard,.pane{transition:none"):
            self.assertIn(marker, PAGE)

    def test_mascot_script_honours_reduced_motion(self):
        for marker in ("matchMedia('(prefers-reduced-motion: reduce)')",
                       "if(!reduce) requestAnimationFrame(frame)",
                       "if(reduce) frame(performance.now())"):
            self.assertIn(marker, PAGE)

    def test_progress_still_updates_without_animation(self):
        # The bar keeps its width transition suppressed, not its width update.
        self.assertIn(".bg-fill{height:100%;width:0;", PAGE)
        self.assertIn("transition:width .3s", PAGE)


class OfflineStoryTest(unittest.TestCase):
    def test_empty_state_explains_offline_and_install(self):
        for marker in ("offline: after this first load the page needs no network",
                       "airplane mode", "install app", "offline-ready chip"):
            self.assertIn(marker, PAGE)

    def test_install_prompt_is_opt_in_and_quiet(self):
        for marker in ('id="installBtn"', "beforeinstallprompt",
                       "installEvent.prompt()", "appinstalled",
                       "installEvent=null", "btn.style.display='none'"):
            self.assertIn(marker, PAGE)

    def test_network_chip_states_are_spoken(self):
        for marker in ('id="netChip"', 'role="status" aria-live="polite"',
                       "offline · still works", "installed · offline-ready",
                       "window.addEventListener('online',updateNetChip)",
                       "window.addEventListener('offline',updateNetChip)"):
            self.assertIn(marker, PAGE)


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}


class Tree(HTMLParser):
    """Record each id's tag and its ancestor ids, so a lost `>` cannot hide.

    A string marker such as `id="qcX"` still matches when the opening tag is
    malformed and the child becomes an attribute, so this parser checks the
    real nesting instead.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.tags = {}
        self.parents = {}
        self.all_ids = []

    def handle_starttag(self, tag, attrs):
        ident = dict(attrs).get("id")
        if ident:
            self.all_ids.append(ident)
            self.tags[ident] = tag
            self.parents[ident] = [name for _, name in self.stack if name]
        if tag not in VOID:
            self.stack.append((tag, ident))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return


class ShellMarkupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = Tree()
        cls.tree.feed(PAGE)
        cls.tree.close()

    def test_drawers_really_contain_their_children(self):
        self.assertEqual(self.tree.tags.get("qc"), "div")
        self.assertEqual(self.tree.tags.get("devices"), "aside")
        self.assertIn("qc", self.tree.parents.get("qcX", []))
        self.assertIn("devices", self.tree.parents.get("devlist", []))
        self.assertIn("previewPane", self.tree.parents.get("buildStatus", []))

    def test_ids_are_unique(self):
        self.assertEqual(len(self.tree.all_ids), len(set(self.tree.all_ids)))

    def test_install_and_network_controls_are_in_the_composer(self):
        self.assertEqual(self.tree.tags.get("installBtn"), "button")
        self.assertEqual(self.tree.tags.get("netChip"), "span")
        self.assertEqual(self.tree.tags.get("q"), "textarea")
        self.assertEqual(self.tree.tags.get("logo"), "button")
        self.assertEqual(self.tree.tags.get("qcBtn"), "button")

    def test_primary_controls_have_explicit_types_and_names(self):
        for marker in ('id="logo" type="button"', 'id="qcBtn" type="button"',
                       'id="devClose" type="button"',
                       'aria-label="open devices drawer"',
                       'aria-controls="devices"', 'aria-controls="qc"'):
            self.assertIn(marker, PAGE)

    def test_offline_registration_stays_guarded(self):
        self.assertIn("navigator.serviceWorker.register('sw.js'", PAGE)
        self.assertIn("location.protocol!=='https:'", PAGE)
        self.assertIn("location.hostname!=='localhost'", PAGE)


if __name__ == "__main__":
    unittest.main()

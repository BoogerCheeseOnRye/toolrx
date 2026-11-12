#!/usr/bin/env python3
"""Behaviour tests for the optional LLM adapter.

`toolrx/web/llm.js` is the only code that may ever open a network request, and
only after the user saves an endpoint and enables it. These tests run it in Node
with a fake fetch: the disabled path must make zero requests, deterministic
prompts must win, malformed responses must be rejected, and the cache must never
carry the API key.
"""

import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NODE = shutil.which("node")

JS = r"""
const fs = require('fs');
const path = require('path');
const ROOT = process.argv[1];
const WEB = path.join(ROOT, 'toolrx', 'web');
const COMMANDS = JSON.parse(fs.readFileSync(path.join(WEB, 'commands.json'), 'utf8'));

global.self = global;
const store = {};
global.localStorage = {
  getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.CustomEvent = class { constructor(type, opts) { this.type = type; this.detail = opts && opts.detail; } };
global.dispatchEvent = () => {};
global.toolrxRouter = { load: () => ({}), route: () => ({ tool: 'none', args: {}, confidence: 0 }) };

// Fake transport. Model/commands loads are bookkeeping; only requests to the
// configured endpoint are counted as real LLM traffic.
const calls = [];
let handler = null;
function reply(payload, status) {
  const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
  return {
    ok: status === undefined || (status >= 200 && status < 300),
    status: status || 200,
    headers: { get: () => String(text.length) },
    text: async () => text,
  };
}
function envelope(content) {
  return { choices: [{ message: { role: 'assistant', content: content } }] };
}
global.fetch = async (url, opts) => {
  const u = String(url);
  if (u.indexOf('model.json') >= 0) {
    return { ok: true, status: 200, headers: { get: () => null },
      json: async () => ({}), text: async () => '{}' };
  }
  if (u.indexOf('commands.json') >= 0) {
    return { ok: true, status: 200, headers: { get: () => null },
      json: async () => COMMANDS, text: async () => JSON.stringify(COMMANDS) };
  }
  calls.push({ url: u, opts: opts || {} });
  if (!handler) throw new Error('unexpected LLM request: ' + u);
  return handler(u, opts || {});
};

for (const f of ['engine2d.js', 'engine3d.js', 'templates.js', 'patches.js',
                 'lang.js', 'llm.js', 'skills.js', 'sandbox.js']) {
  eval(fs.readFileSync(path.join(WEB, f), 'utf8'));
}

const L = self.toolrxLlm;
const out = {};
const resetKeys = () => {
  localStorage.removeItem('toolrx.llm.cache');
  localStorage.removeItem('toolrx.llm.pending');
};
function configureLLM(extra) {
  return L.configure(Object.assign({
    enabled: true,
    endpoint: 'https://llm.test/v1/chat/completions',
    model: 'test-model',
    key: '',
    timeoutMs: 1000,
    maxResponse: 65536,
    maxCalls: 8,
  }, extra || {}));
}
function resetLLM(extra) {
  resetKeys();
  L.resetBudget();
  return configureLLM(extra);
}
async function failure(fn) {
  try { await fn(); return null; }
  catch (e) { return String(e && e.message ? e.message : e); }
}

(async () => {
  // Defaults: no endpoint, no enabled flag, no requests.
  out.defaults = {
    enabled: L.config().enabled,
    endpoint: L.config().endpoint,
    calls: L.calls(),
    cache: L.cacheSize(),
    status: L.statusText(),
  };
  out.disabled = {
    plan: await failure(() => L.plan('a cozy mail route')),
    patch: await failure(() => L.patch('app.js', 'add a marker', { content: 'var x=1;\n' })),
    requests: calls.length,
  };
  // A known deterministic prompt never reaches the adapter, even when enabled.
  resetLLM();
  const beforeDet = calls.length;
  const det = await L.plan('build a platformer game');
  out.deterministic = {
    source: det.source, genre: det.genre, text: det.text,
    requests: calls.length - beforeDet,
  };

  // Valid plan -> strict schema -> cache. The same prompt with different
  // casing/punctuation hits the cache without another request.
  resetLLM();
  handler = () => reply(envelope('{"genre":"farmingsim","dim":"2D","why":"a short route loop"}'));
  const planA = await L.plan('a cozy mail route');
  const planB = await L.plan('A cozy mail route.');
  const req = calls[calls.length - 1];
  const body = JSON.parse(req.opts.body);
  out.plan = {
    source: planA.source, genre: planA.genre, why: planA.why,
    text: planA.text, calls: planA.calls, cache: L.cacheSize(),
    secondSource: planB.source, secondText: planB.text,
    requests: calls.length, url: req.url,
    model: body.model, temperature: body.temperature,
    responseFormat: body.response_format && body.response_format.type,
    system: body.messages[0].content, user: body.messages[1].content,
  };

  out.invalidJson = { error: await (async () => {
    resetLLM();
    handler = () => reply(envelope('I think a farm sim is a good fit'));
    return failure(() => L.plan('a quiet fishing village'));
  })(), cache: L.cacheSize() };

  resetLLM();
  handler = () => reply(envelope('not json at all'));
  out.invalidJsonRaw = {
    error: await failure(() => L.plan('a lighthouse mystery')),
    cache: L.cacheSize(),
  };

  resetLLM();
  handler = () => reply(envelope('```json\n{"genre":"platformer","why":"fenced"}\n```'));
  const fenced = await L.plan('a tiny tea shop');
  out.fenced = { source: fenced.source, genre: fenced.genre, why: fenced.why };

  out.schema = {};
  for (const [name, content] of Object.entries({
    unknownGenre: '{"genre":"bullet-hell"}',
    extraKey: '{"genre":"platformer","confidence":0.9}',
    badDim: '{"genre":"platformer","dim":"4D"}',
    badGenreType: '{"genre":42}',
    badWhy: '{"genre":"platformer","why":{"text":"no"}}',
  })) {
    resetLLM();
    handler = () => reply(envelope(content));
    out.schema[name] = await failure(() => L.plan('a space station mystery'));
  }

  out.endpoints = {};
  for (const [name, url] of Object.entries({
    httpPublic: 'http://api.example.com/v1/chat',
    httpsOk: 'https://api.example.com/v1/chat/completions',
    localHost: 'http://localhost:11434/v1/chat/completions',
    localIp: 'http://127.0.0.1:11434/v1/chat/completions',
    localV6: 'http://[::1]:11434/v1/chat/completions',
    scheme: 'javascript:alert(1)',
    credentials: 'https://user:pass@api.example.com/v1',
    notUrl: 'api.example.com',
  })) {
    try { out.endpoints[name] = { ok: true, value: L.configure({ endpoint: url }).endpoint }; }
    catch (e) { out.endpoints[name] = { ok: false, error: e.message }; }
  }

  // Timeout and size budgets abort before the response is trusted.
  resetLLM({ timeoutMs: 40 });
  handler = (u, o) => new Promise((resolve, reject) => {
    if (o.signal) o.signal.addEventListener('abort', () => {
      const e = new Error('aborted'); e.name = 'AbortError'; reject(e);
    });
  });
  const started = Date.now();
  out.timeout = { error: await failure(() => L.plan('a quiet fishing village')), ms: Date.now() - started };

  resetLLM({ maxResponse: 1024 });
  handler = () => reply(envelope('{"genre":"platformer","why":"' + 'x'.repeat(2000) + '"}'));
  out.oversize = { error: await failure(() => L.plan('a quiet fishing village')) };

  resetLLM({ maxCalls: 1 });
  handler = () => reply(envelope('{"genre":"platformer","why":"budget"}'));
  const firstBudget = await L.plan('a lighthouse mystery');
  const requestsBefore = calls.length;
  out.budget = {
    first: firstBudget.source,
    second: await failure(() => L.plan('a tiny tea shop')),
    requests: calls.length - requestsBefore,
  };

  // Patch generation: only the requested file, only a unified diff.
  const project = self.toolrxTemplates.project('platformer', 'build a platformer game', {});
  const app = project.files['app.js'];
  const appLines = app.endsWith('\n') ? app.slice(0, -1).split('\n') : app.split('\n');
  const appendDiff = line => '@@ -' + appLines.length + ',0 +' + (appLines.length + 1)
    + ',1 @@\n+' + line + '\n';
  resetLLM();
  handler = () => reply(envelope(JSON.stringify({ file: 'app.js', diff: appendDiff('// llm marker') })));
  const patch = await L.patch('app.js', 'append a marker', { content: app });
  const applied = L.applyDiff(app, patch.diff, 'app.js');
  out.patch = {
    source: patch.source, file: patch.file, hunks: L.parseDiff(patch.diff, 'app.js').length,
    text: patch.text, changed: applied !== app,
    marker: applied.indexOf('// llm marker') >= 0,
    tail: applied.endsWith('\n'),
    cache: L.cacheSize(),
    cached: (await L.patch('app.js', 'append a marker', { content: app })).source,
  };

  resetLLM();
  handler = () => reply(envelope(JSON.stringify({ file: 'styles.css', diff: appendDiff('x') })));
  out.patchBadFile = await failure(() => L.patch('app.js', 'wrong file', { content: app }));

  resetLLM();
  handler = () => reply(envelope(JSON.stringify({ file: 'app.js', diff: 'just some text' })));
  out.patchBadDiff = await failure(() => L.patch('app.js', 'no hunk', { content: app }));

  resetLLM();
  handler = () => reply(envelope(JSON.stringify({ file: 'app.js', diff: appendDiff('x'), extra: 1 })));
  out.patchExtraKey = await failure(() => L.patch('app.js', 'extra key', { content: app }));

  resetLLM();
  out.patchTooBig = await failure(() => L.patch('app.js', 'big', { content: 'x'.repeat(31000) }));

  const base = 'one\ntwo\nthree\n';
  const tryDiff = (content, diff) => {
    try { return { ok: true, text: L.applyDiff(content, diff, 'app.js') }; }
    catch (e) { return { ok: false, error: e.message }; }
  };
  out.diff = {
    replace: tryDiff(base, '@@ -2,1 +2,1 @@\n-two\n+TWO\n'),
    insert: tryDiff(base, '@@ -3,0 +4,1 @@\n+four\n'),
    empty: tryDiff('', '@@ -0,0 +1,1 @@\n+hello\n'),
    pastEof: tryDiff(base, '@@ -9,1 +9,1 @@\n-x\n+y\n'),
    contextMismatch: tryDiff(base, '@@ -1,1 +1,1 @@\n-nope\n+y\n'),
    headerMismatch: tryDiff(base, '--- a/other.js\n+++ b/other.js\n@@ -1,1 +1,1 @@\n-one\n+ONE\n'),
    noNewline: tryDiff('a\nb', '@@ -2,1 +2,1 @@\n-b\n+B\n'),
    overlap: tryDiff(base, '@@ -2,1 +2,1 @@\n-two\n+TWO\n@@ -1,1 +1,1 @@\n-one\n+ONE\n'),
  };

  out.names = {};
  for (const name of ['app.js', '../escape.js', '/etc/passwd', 'sub/app.js', '.env', 'a b.js', '']) {
    try { out.names[name || '(empty)'] = { ok: true, value: L.safeFileName(name) }; }
    catch (e) { out.names[name || '(empty)'] = { ok: false, error: e.message }; }
  }

  // The key is sent, stored in config, and absent from the cache/status text.
  resetLLM({ key: 'test-key-not-real' });
  handler = () => reply(envelope('{"genre":"platformer","why":"key test"}'));
  await L.plan('a lighthouse mystery');
  const auth = calls[calls.length - 1].opts.headers.Authorization;
  const cacheRaw = localStorage.getItem('toolrx.llm.cache');
  const pendRaw = localStorage.getItem('toolrx.llm.pending');
  out.secret = {
    auth: auth,
    status: L.statusText(),
    cacheHasKey: String(cacheRaw).indexOf('test-key-not-real') >= 0,
    pendingHasKey: String(pendRaw).indexOf('test-key-not-real') >= 0,
    hasKey: L.status().hasKey,
  };
  out.cacheClear = { before: L.cacheSize(), text: L.clearCache(), after: L.cacheSize() };

  // ---- sandbox integration: generate, apply, undo, discard, staleness ----
  await self.toolrxWeb.init('model.json');
  await self.toolrxSkills.init('commands.json');
  const run = async q => (await self.toolrxWeb.prompt(q))
    .map(r => ({ via: r.via || '', text: r.text || '', error: !!r.error }));
  const snap = () => {
    const p = self.toolrxWeb.project();
    const files = {};
    p.files.forEach(f => { files[f] = self.toolrxWeb.projectFile(p.slug, f); });
    return { slug: p.slug, files: files, html: p.html };
  };

  self.toolrxWeb.reset();
  resetLLM();
  const build = await run('build a platformer game');
  const original = snap();
  handler = () => {
    const lines = original.files['app.js'].split('\n');
    const n = original.files['app.js'].endsWith('\n') ? lines.length - 1 : lines.length;
    return reply(envelope(JSON.stringify({
      file: 'app.js', diff: '@@ -' + n + ',0 +' + (n + 1) + ',1 @@\n+// applied by llm\n',
    })));
  };
  const generated = await run('llm patch app.js with append a marker comment');
  const afterGenerate = snap();
  const noWrite = afterGenerate.files['app.js'] === original.files['app.js'];
  const pendingStatus = await run('llm status');
  const applyRun = await run('apply the llm patch');
  const afterApply = snap();
  const restoredRun = await run('undo');
  const afterUndo = snap();
  const emptyApply = await run('apply the llm patch');

  out.sandbox = {
    buildVia: build[0].via,
    generateVia: generated[0].via, generateText: generated[0].text,
    pendingInStatus: pendingStatus[0].text,
    noWrite: noWrite,
    applyVia: applyRun[0].via, applyText: applyRun[0].text,
    marker: afterApply.files['app.js'].indexOf('// applied by llm') >= 0,
    preview: afterApply.html.indexOf('// applied by llm') >= 0,
    filesSame: JSON.stringify(Object.keys(afterApply.files)) === JSON.stringify(Object.keys(original.files)),
    undoText: restoredRun[0].text,
    lossless: Object.keys(original.files).every(k => original.files[k] === afterUndo.files[k]),
    emptyApply: emptyApply[0].text,
  };

  // Discard leaves the project untouched.
  resetLLM();
  handler = () => {
    const lines = original.files['app.js'].split('\n');
    const n = original.files['app.js'].endsWith('\n') ? lines.length - 1 : lines.length;
    return reply(envelope(JSON.stringify({
      file: 'app.js', diff: '@@ -' + n + ',0 +' + (n + 1) + ',1 @@\n+// discarded marker\n',
    })));
  };
  const second = snap();
  const gen2 = await run('llm patch app.js with add a comment');
  const discard = await run('discard the llm patch');
  out.discard = {
    via: discard[0].via, text: discard[0].text,
    unchanged: second.files['app.js'] === snap().files['app.js'],
    status: (await run('llm status'))[0].text,
  };

  // A patch generated against old content is refused instead of fuzzed.
  resetLLM();
  handler = () => reply(envelope(JSON.stringify({
    file: 'app.js', diff: '@@ -1,1 +1,1 @@\n-' + original.files['app.js'].split('\n')[0] + '\n+// replaced\n',
  })));
  const gen3 = await run('llm patch app.js with replace the first line');
  const p3 = self.toolrxWeb.project();
  self.toolrxWeb.writeProjectFile(p3.slug, 'app.js', original.files['app.js'] + '// moved on\n');
  const stale = await run('apply the llm patch');
  await run('discard the llm patch');
  out.stale = { generate: gen3[0].text, apply: stale[0].text, error: stale[0].error };

  // Off means off: a playground prompt refuses before any request.
  const off = await run('llm off');
  const requestsBeforeOff = calls.length;
  const offPlan = await run('llm plan a cozy mail route');
  const on = await run('llm on');
  out.toggle = {
    off: off[0].text, plan: offPlan[0].text, planError: offPlan[0].error,
    requests: calls.length - requestsBeforeOff, on: on[0].text,
  };

  console.log(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


@unittest.skipUnless(NODE, "node is required for the JS tests")
class LlmAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", JS, ROOT],
            capture_output=True, text=True, timeout=180,
        )
        if proc.returncode != 0:
            raise AssertionError("node harness failed:\n" + proc.stdout + "\n" + proc.stderr)
        cls.out = json.loads(proc.stdout)

    # ------------------------------------------------------------ defaults --
    def test_defaults_are_off_and_quiet(self):
        d = self.out["defaults"]
        self.assertFalse(d["enabled"])
        self.assertEqual(d["endpoint"], "")
        self.assertEqual(d["calls"], 0)
        self.assertEqual(d["cache"], 0)
        self.assertIn("off", d["status"])
        self.assertIn("deterministic", d["status"])
        self.assertEqual(self.out["disabled"]["requests"], 0)

    def test_disabled_adapter_refuses_before_fetching(self):
        d = self.out["disabled"]
        self.assertIn("off", d["plan"])
        self.assertIn("off", d["patch"])

    def test_known_prompts_stay_deterministic(self):
        d = self.out["deterministic"]
        self.assertEqual(d["source"], "deterministic")
        self.assertEqual(d["genre"], "platformer")
        self.assertEqual(d["requests"], 0)
        self.assertIn("no request sent", d["text"])

    # ---------------------------------------------------------------- plan --
    def test_valid_plan_is_cached(self):
        p = self.out["plan"]
        self.assertEqual(p["source"], "llm")
        self.assertEqual(p["genre"], "farmingsim")
        self.assertEqual(p["why"], "a short route loop")
        self.assertEqual(p["calls"], 1)
        self.assertEqual(p["cache"], 1)
        self.assertEqual(p["secondSource"], "cache")
        self.assertIn("cache hit", p["secondText"])
        self.assertEqual(p["requests"], 1)
        self.assertEqual(p["model"], "test-model")
        self.assertEqual(p["temperature"], 0)
        self.assertEqual(p["responseFormat"], "json_object")
        self.assertIn("farmingsim", p["system"])
        self.assertIn("a cozy mail route", p["user"])
        self.assertIn("farming sim", p["text"])

    def test_invalid_json_is_rejected_and_not_cached(self):
        self.assertIn("JSON", self.out["invalidJson"]["error"])
        self.assertEqual(self.out["invalidJson"]["cache"], 0)
        self.assertIn("JSON", self.out["invalidJsonRaw"]["error"])
        self.assertEqual(self.out["invalidJsonRaw"]["cache"], 0)

    def test_one_fenced_json_object_is_accepted(self):
        f = self.out["fenced"]
        self.assertEqual(f["source"], "llm")
        self.assertEqual(f["genre"], "platformer")

    def test_schema_violations_are_rejected(self):
        s = self.out["schema"]
        self.assertIn("allow-list", s["unknownGenre"])
        self.assertIn("unexpected key", s["extraKey"])
        self.assertIn("2D or 3D", s["badDim"])
        self.assertIn("missing a genre", s["badGenreType"])
        self.assertIn("why must be a string", s["badWhy"])

    # ------------------------------------------------------------ endpoints --
    def test_endpoint_must_be_https_or_localhost(self):
        e = self.out["endpoints"]
        self.assertFalse(e["httpPublic"]["ok"])
        self.assertIn("https", e["httpPublic"]["error"])
        self.assertTrue(e["httpsOk"]["ok"])
        self.assertTrue(e["localHost"]["ok"])
        self.assertTrue(e["localIp"]["ok"])
        self.assertTrue(e["localV6"]["ok"])
        for name in ("scheme", "credentials", "notUrl"):
            self.assertFalse(e[name]["ok"], name)

    def test_budgets_timeouts_and_size_caps(self):
        t = self.out["timeout"]
        self.assertIn("timed out", t["error"])
        self.assertLess(t["ms"], 5000)
        self.assertIn("too large", self.out["oversize"]["error"])
        b = self.out["budget"]
        self.assertEqual(b["first"], "llm")
        self.assertIn("budget reached", b["second"])
        self.assertEqual(b["requests"], 0)

    # --------------------------------------------------------------- patch --
    def test_patch_is_strict_and_applies(self):
        p = self.out["patch"]
        self.assertEqual(p["source"], "llm")
        self.assertEqual(p["file"], "app.js")
        self.assertEqual(p["hunks"], 1)
        self.assertTrue(p["changed"])
        self.assertTrue(p["marker"])
        self.assertTrue(p["tail"])
        self.assertEqual(p["cached"], "cache")
        self.assertEqual(p["cache"], 1)

    def test_patch_validation_rejects_mismatches(self):
        self.assertIn("instead of app.js", self.out["patchBadFile"])
        self.assertIn("hunk", self.out["patchBadDiff"])
        self.assertIn("unexpected key", self.out["patchExtraKey"])
        self.assertIn("too large", self.out["patchTooBig"])

    def test_unified_diff_applier(self):
        d = self.out["diff"]
        self.assertEqual(d["replace"]["text"], "one\nTWO\nthree\n")
        self.assertEqual(d["insert"]["text"], "one\ntwo\nthree\nfour\n")
        self.assertEqual(d["empty"]["text"], "hello\n")
        self.assertFalse(d["empty"].get("ok") is False)
        self.assertIn("past the end", d["pastEof"]["error"])
        self.assertIn("does not apply", d["contextMismatch"]["error"])
        self.assertIn("names other.js", d["headerMismatch"]["error"])
        self.assertEqual(d["noNewline"]["text"], "a\nB")
        self.assertIn("overlap", d["overlap"]["error"])

    def test_file_names_stay_inside_the_project(self):
        n = self.out["names"]
        self.assertTrue(n["app.js"]["ok"])
        for name in ("../escape.js", "/etc/passwd", "sub/app.js", ".env", "a b.js"):
            self.assertFalse(n[name]["ok"], name)
        self.assertFalse(n["(empty)"]["ok"])

    def test_key_is_used_but_never_cached(self):
        s = self.out["secret"]
        self.assertEqual(s["auth"], "Bearer test-key-not-real")
        self.assertTrue(s["hasKey"])
        self.assertFalse(s["cacheHasKey"])
        self.assertFalse(s["pendingHasKey"])
        self.assertNotIn("test-key-not-real", s["status"])
        self.assertIn("key saved", s["status"])
        c = self.out["cacheClear"]
        self.assertEqual(c["before"], 1)
        self.assertEqual(c["after"], 0)
        self.assertIn("cleared", c["text"])

    # ------------------------------------------------------------- sandbox --
    def test_sandbox_generate_apply_undo(self):
        s = self.out["sandbox"]
        self.assertEqual(s["buildVia"], "build")
        self.assertEqual(s["generateVia"], "llm.patch")
        self.assertIn("nothing written yet", s["generateText"])
        self.assertTrue(s["noWrite"])
        self.assertIn("pending patch: app.js", s["pendingInStatus"])
        self.assertEqual(s["applyVia"], "llm.apply")
        self.assertTrue(s["marker"])
        self.assertTrue(s["preview"])
        self.assertTrue(s["filesSame"])
        self.assertIn("undid", s["undoText"])
        self.assertTrue(s["lossless"])
        self.assertIn("no llm patch to apply", s["emptyApply"])

    def test_sandbox_discard_and_staleness(self):
        d = self.out["discard"]
        self.assertEqual(d["via"], "llm.discard")
        self.assertTrue(d["unchanged"])
        self.assertIn("no files were written", d["text"])
        st = self.out["stale"]
        self.assertTrue(st["error"], st)
        self.assertIn("changed since", st["apply"])
        self.assertNotIn("pending patch", self.out["discard"]["status"])

    def test_llm_on_off_commands(self):
        t = self.out["toggle"]
        self.assertIn("off", t["off"])
        self.assertTrue(t["planError"])
        self.assertIn("off", t["plan"])
        self.assertEqual(t["requests"], 0)
        self.assertIn("on", t["on"])


class LlmSourceTest(unittest.TestCase):
    def test_llm_js_is_valid_javascript(self):
        if not NODE:
            self.skipTest("node is required")
        src = os.path.join(ROOT, "toolrx", "web", "llm.js")
        proc = subprocess.run([NODE, "--check", src], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_no_eval_or_hidden_network(self):
        with open(os.path.join(ROOT, "toolrx", "web", "llm.js"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("eval(", src)
        self.assertNotIn("new Function", src)
        self.assertNotIn("XMLHttpRequest", src)
        self.assertIn('fetch(c.endpoint', src)
        self.assertIn('"toolrx.llm.config"', src)


if __name__ == "__main__":
    unittest.main()

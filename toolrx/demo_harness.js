#!/usr/bin/env node
/* Offline end-to-end demo harness (step 45).
 *
 * Loads the same browser modules the Pages build ships, with a fake fetch for
 * the catalog and model, and a localStorage shim. It runs one long request
 * through `toolrxWeb.prompt`, expands the stored plan, continues the pending
 * step from context, and undoes it again. The JSON on stdout is the raw
 * transcript; `toolrx/demo.py` normalizes timings and writes the checked-in
 * report.
 *
 * No network, no server, no browser, no model.
 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

global.self = global;
const COMMANDS = process.argv[2];
const SKILLS = process.argv[3];
const REQUEST = process.argv[4];

global.fetch = () => Promise.resolve({
  ok: true,
  json: () => Promise.resolve(JSON.parse(fs.readFileSync(COMMANDS, 'utf8'))),
});
const store = {};
global.localStorage = {
  getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.CustomEvent = class {
  constructor(type, opts) { this.type = type; this.detail = opts && opts.detail; }
};
global.dispatchEvent = () => {};
global.toolrxRouter = {
  load: () => ({}),
  route: () => ({ tool: 'none', args: {}, confidence: 0 }),
};

const WEB = path.dirname(SKILLS);
eval(fs.readFileSync(path.join(WEB, 'limits.js'), 'utf8'));
eval(fs.readFileSync(SKILLS, 'utf8'));
eval(fs.readFileSync(path.join(WEB, 'templates.js'), 'utf8'));
for (const name of ['engine2d.js', 'engine2d.embed.js', 'engine3d.js',
                    'engine3d.embed.js', 'worldgen.js', 'worldgen.embed.js',
                    'rpg2.js', 'rpg2.embed.js', 'patches.js', 'context.js',
                    'sandbox.js']) {
  eval(fs.readFileSync(path.join(WEB, name), 'utf8'));
}

function sha(text) {
  return crypto.createHash('sha256').update(String(text)).digest('hex');
}

function projectState(W) {
  const p = W.project();
  if (!p) return null;
  const doc = JSON.parse(W.exportProject(p.slug));
  const plan = doc.project.plan || null;
  const status = plan ? (plan.status || []) : [];
  const files = p.files.slice().sort().map(name => {
    const body = W.projectFile(p.slug, name);
    return { name: name, bytes: Buffer.byteLength(body), sha: sha(body) };
  });
  return {
    slug: p.slug,
    name: p.name,
    kind: p.kind,
    files: files,
    specSha: sha(JSON.stringify(doc.project.spec || null)),
    plan: plan ? {
      steps: plan.steps.length,
      done: status.filter(s => s === 'done').length,
      pending: status.filter(s => s === 'pending').length,
      error: status.filter(s => s === 'error').length,
      pendingSteps: plan.steps.filter((_, i) => status[i] === 'pending'),
    } : null,
  };
}

function touched(before, after) {
  if (!before || !after) return [];
  const left = {};
  before.files.forEach(f => { left[f.name] = f.sha; });
  const right = {};
  after.files.forEach(f => { right[f.name] = f.sha; });
  const names = new Set(Object.keys(left).concat(Object.keys(right)));
  return Array.from(names).filter(n => left[n] !== right[n]).sort();
}

function stepRows(results) {
  return results.map((r, i) => ({
    n: i + 1,
    step: String(r.step || ''),
    via: String(r.via || ''),
    desc: String(r.desc || ''),
    error: !!r.error,
    confidence: typeof r.confidence === 'number' ? r.confidence : null,
    margin: typeof r.margin === 'number' ? r.margin : null,
    ms: typeof r.ms === 'number' ? r.ms : 0,
    bytes: Buffer.byteLength(String(r.text || '')),
    sha: sha(String(r.text || '')),
    text: String(r.text || ''),
  }));
}

function runRow(last) {
  if (!last) return null;
  return {
    at: last.at || 0,
    chars: last.chars,
    planned: last.planned,
    steps: last.steps,
    executed: last.executed,
    failed: last.failed,
    ok: !!last.ok,
    via: last.via,
    confidence: last.confidence,
    margin: last.margin,
    distribution: last.distribution || null,
    ms: last.ms,
    bytes: last.bytes,
    written: last.written,
    emitted: last.emitted,
    files: last.files,
    filesTouched: last.filesTouched || [],
    contextBytes: last.contextBytes,
    undo: last.undo,
    budget: last.budget || null,
  };
}

function sortedLimits() {
  const out = {};
  Object.keys(self.toolrxLimits).sort().forEach(k => { out[k] = self.toolrxLimits[k]; });
  return out;
}

(async () => {
  await self.toolrxSkills.init('commands.json');
  await self.toolrxWeb.init('model.json');
  const W = self.toolrxWeb;
  const S = self.toolrxSkills;
  W.reset();

  const request = fs.readFileSync(REQUEST, 'utf8').trim();
  const preview = S.planPreview(request, { stepMs: 4000, planMs: 160000 });
  const results = await W.prompt(request);
  const bigRun = runRow(W.lastRun());
  const afterRun = projectState(W);
  const contextAfterRun = W.contextSnapshot();

  const expand = await W.prompt('expand the last plan with change the page title to Station Defense Continued');
  const afterExpand = projectState(W);

  const cont = await W.prompt('continue from previous');
  const afterContinue = projectState(W);
  const contextAfterContinue = W.contextSnapshot();

  const undo = await W.prompt('undo');
  const afterUndo = projectState(W);

  const report = {
    version: 1,
    request: {
      chars: request.length,
      steps: preview.total,
      sha256: sha(request),
    },
    catalog: S.count(),
    limits: sortedLimits(),
    limitsText: S.limitsText(),
    plan: {
      chars: request.length,
      steps: preview.total,
      plan: !!preview.plan,
      blocked: !!preview.blocked,
      overLimit: !!preview.overLimit,
      reason: preview.reason || null,
      budget: preview.budget || null,
    },
    run: bigRun,
    steps: stepRows(results),
    project: afterRun,
    context: {
      snapshot: contextAfterRun,
      report: W.context(),
      afterContinue: contextAfterContinue,
    },
    continuation: {
      expand: {
        via: expand[0] && expand[0].via,
        error: !!(expand[0] && expand[0].error),
        text: (expand[0] && expand[0].text) || '',
        plan: afterExpand && afterExpand.plan,
      },
      continue: {
        via: cont[0] && cont[0].via,
        error: !!(cont[0] && cont[0].error),
        text: (cont[0] && cont[0].text) || '',
        plan: afterContinue && afterContinue.plan,
        filesTouched: touched(afterRun, afterContinue),
      },
    },
    undo: {
      via: undo[0] && undo[0].via,
      error: !!(undo[0] && undo[0].error),
      text: (undo[0] && undo[0].text) || '',
      exact: !!afterUndo && !!afterRun
        && JSON.stringify(afterUndo.files) === JSON.stringify(afterRun.files)
        && afterUndo.specSha === afterRun.specSha,
      filesRestored: touched(afterContinue, afterUndo),
    },
  };
  console.log(JSON.stringify(report));
})().catch(err => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});

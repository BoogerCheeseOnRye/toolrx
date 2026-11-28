/* toolrx evaluation harness (step 69).
 *
 * Drives the real browser modules in Node with a fake catalog fetch, no
 * server, no browser, and no model. Every measured program runs twice and the
 * harness compares the two serialized results, so the checked-in report quotes
 * a real determinism check instead of trusting a fixture's `want` field.
 *
 * The fake fetch only reads local files; `network` in the output counts calls
 * made after module initialization, which must stay at zero.
 */
"use strict";

const fs = require("fs");
const path = require("path");

const WEB = process.argv[2];
const COMMANDS = process.argv[3];
const MODEL = process.argv[4];

global.self = global;
let fetches = 0;
global.fetch = (url) => {
  fetches += 1;
  const name = String(url).split("/").pop();
  const file = name === "model.json" ? MODEL
    : name === "commands.json" ? COMMANDS
    : path.join(WEB, name);
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(JSON.parse(fs.readFileSync(file, "utf8"))),
  });
};
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

for (const name of [
  "blake2b.js", "router.js", "limits.js", "budget.js", "planrewrite.js",
  "thinking.js", "repair.js", "trace.js", "journal.js", "skills.js",
  "templates.js", "context.js", "lang.js", "patches.js", "engine2d.js",
  "engine2d.embed.js", "engine3d.js", "engine3d.embed.js", "worldgen.js",
  "worldgen.embed.js", "rpg2.js", "rpg2.embed.js", "sandbox.js",
]) {
  eval(fs.readFileSync(path.join(WEB, name), "utf8"));
}

const clone = value => JSON.parse(JSON.stringify(value));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function determinism(entries) {
  let deterministic = 0;
  const mismatches = [];
  entries.forEach(entry => {
    if (same(entry.first, entry.second)) deterministic += 1;
    else mismatches.push(entry.name);
  });
  return {
    states: entries.length,
    deterministic: deterministic,
    mismatches: mismatches.length,
    names: mismatches,
  };
}

const lim = {
  planChars: 8000, planSteps: 40, stepMs: 4000, planMs: 160000,
  contextMax: 8192, projectMax: 524288, projectFiles: 32,
  buildBytes: 65536, editBytes: 4096, readFileBytes: 8000,
  readTotalBytes: 24000, thinkChars: 4000, thinkGoals: 8, thinkRules: 12,
};
const step = (text, op, exact, status) => ({
  text, op: op || "router", exact: exact !== false, status: status || "pending",
});

(async () => {
  await self.toolrxSkills.init("commands.json");
  await self.toolrxWeb.init("model.json");
  const before = fetches;
  const out = { version: 1 };

  /* ---- thinking: five modes, each run twice --------------------------- */
  const T = self.toolrxThinking;
  const decompose = {
    text: "build a platformer game; add a boss",
    source: "literal", literal: true,
    goals: [
      { text: "build a platformer game", op: "build", exact: true },
      { text: "add a boss", op: "edit.apply", exact: true },
    ],
    limits: lim,
  };
  const reason = Object.assign({}, decompose, {
    goals: [
      { text: "build a platformer game", op: "build", exact: true },
      { text: "list the files", op: "fs.list_dir", exact: true },
      { text: "read notes.txt", op: "fs.read_file", exact: true },
      { text: "multiply 6 and 7", op: "math.binary", exact: true },
    ],
  });
  const tradeoff = { text: "offline canvas vs cloud api", source: "literal",
                     literal: true, limits: lim };
  const critique = (steps, extra) => Object.assign({
    text: steps.map(s => s.text).join("\n"),
    source: "active plan", literal: false,
    plan: { steps: steps }, contextBytes: 0, project: null, limits: lim,
  }, extra || {});
  const critiqueFailed = critique([
    step("build a platformer game", "build", true, "done"),
    step("add a boss", "edit.apply", true, "error"),
    step("list the files", "fs.list_dir", true, "pending"),
  ]);
  const critiqueOver = critique(Array.from({ length: 45 }, (_, i) =>
    step("read notes " + i + ".txt", "fs.read_file", true, "pending")));
  const thinkInputs = [
    ["decompose", "decompose", decompose],
    ["reason", "reason", reason],
    ["tradeoff", "tradeoff", tradeoff],
    ["critique-failed", "critique", critiqueFailed],
    ["critique-over", "critique", critiqueOver],
  ];
  out.thinking = determinism(thinkInputs.map(([name, mode, input]) => ({
    name: name,
    first: T.run(mode, clone(input)),
    second: T.run(mode, clone(input)),
  })));
  out.thinking.modes = thinkInputs.length;

  /* ---- repair: five recorded failures, each run twice ----------------- */
  const R = self.toolrxRepair;
  const repairBase = {
    steps: [step("build a platformer game", "build"),
            step("divide 4 by 0", "math.binary"),
            step("add a theme toggle", "project.themeToggle")],
    failedAt: 1,
    errorText: "division by zero",
    passes: 0, maxPasses: 2,
    limits: { planSteps: 40, planChars: 8000, planVariantBytes: 9216 },
    originalSteps: 3,
  };
  const repairInputs = [
    ["math", {}],
    ["kind", {
      steps: [step("build a platformer game", "build"),
              step("add a boss", "edit.apply"),
              step("add a theme toggle", "project.themeToggle")],
      errorText: "not edited · bosses are wired for shooter, twin-stick; "
        + "try: build a compatible starter first, or say undo",
    }],
    ["missing", {
      steps: [step("build a platformer game", "build"),
              step("count the words in missing.txt", "text.count"),
              step("add a theme toggle", "project.themeToggle")],
      errorText: "no such file: missing.txt",
    }],
    ["empty", {
      steps: [step("build a platformer game", "build"),
              step("divide 4 by 0", "math.binary")],
    }],
    ["many", {
      steps: [step("build a platformer game", "build"),
              step("divide 4 by 0", "math.binary")].concat(
        Array.from({ length: 45 }, (_, i) =>
          step("list the files " + i, "fs.list_dir"))),
    }],
  ];
  out.repair = determinism(repairInputs.map(([name, extra]) => {
    const input = Object.assign({}, repairBase, extra);
    const first = R.plan(clone(input));
    const second = R.plan(clone(input));
    return { name: name, first: first, second: second };
  }));
  out.repair.rules = repairInputs.length;

  /* ---- compaction: two runs from one seed ----------------------------- */
  const C = self.toolrxContext;
  const summarize = text => String(text == null ? "" : text)
    .split(/\n+/).map(line => line.trim()).filter(Boolean)
    .slice(0, 3).map(line => "- " + line);
  const plan = C.stable({
    version: 1,
    steps: ["add sound", "read missing.txt", "add a boss"],
    status: ["done", "error", "pending"],
  });
  const entries = () => ([
    { kind: "file", key: "engine2d.js",
      text: "engine2d.js · 91 bytes · 4 lines · sha 0123456789abcdef · shared engine" },
    { kind: "spec", key: "active",
      text: "spec · 2D top-down · shooter · pixel · medium · seed 7" },
    { kind: "file", key: "index.html",
      text: "index.html · 1767 bytes · 21 lines · sha abcdef0123456789 · <!doctype html>" },
    { kind: "file", key: "app.js",
      text: "app.js · 3680 bytes · 59 lines · sha 1234567890abcdef · var cv=..." },
    { kind: "file", key: "styles.css",
      text: "styles.css · 3116 bytes · 3 lines · sha fedcba9876543210 · :root{--bg:#0b1020}" },
    { kind: "file", key: "README.md",
      text: "README.md · 1424 bytes · 57 lines · sha 9f3a1c7e5b2d4806 · Top-down shooter" },
    { kind: "edit", key: "last", text: '{"labels":["boss"],"ids":["boss"]}' },
    { kind: "result", key: "last",
      text: "query: add a boss\nvia: edit.apply\n"
        + "The boss walks the level. It fires every two seconds. "
        + "It drops a key when defeated. It respawns after ten seconds. "
        + "The level ends when the key is used." },
    { kind: "session", key: "rolling",
      text: Array.from({ length: 12 }, (_, i) =>
        (i % 4 === 3 ? "✗" : "✓") + " step " + i + " did something useful").join("\n") },
    { kind: "plan", key: "last", text: plan },
  ]);
  const seed = () => {
    localStorage.setItem("toolrx.context.cap", "8192");
    C.clear("eval");
    C.setMany("eval", entries(), { summarize });
    localStorage.setItem("toolrx.context.cap", "700");
  };
  seed();
  const rawBefore = C.raw("eval");
  C.compact("eval", { summarize });
  const rawA = C.raw("eval");
  const notesA = C.notes("eval");
  seed();
  C.compact("eval", { summarize });
  const rawB = C.raw("eval");
  const counts = { trimmed: 0, summarized: 0, dropped: 0, evicted: 0 };
  notesA.forEach(note => {
    if (Object.prototype.hasOwnProperty.call(counts, note.why)) {
      counts[note.why] += 1;
    }
  });
  out.compaction = {
    runs: 2,
    identical: rawA === rawB,
    changed: rawBefore !== rawA,
    stored: C.byteLength(rawA),
    cap: 700,
    entries: entries().length,
    trimmed: counts.trimmed,
    summarized: counts.summarized,
    dropped: counts.dropped,
    evicted: counts.evicted,
    planKept: !!C.get("eval", "plan", "last"),
    specKept: !!C.get("eval", "spec", "active"),
  };

  /* ---- plan rewrite: seven cases, each run twice ---------------------- */
  const P = self.toolrxPlanRewrite;
  const rstep = (text, via, exact) => ({ text, via, exact: exact !== false });
  const rbase = {
    stepMs: 4000, planMs: 160000, maxChars: 8000, maxSteps: 40,
    contextBytes: 0, contextMax: 8192, projectBytes: 0, projectMax: 524288,
    buildBytes: 65536, editBytes: 4096,
  };
  const rw = extra => P.rewrite(Object.assign({}, rbase, extra));
  const rewriteCases = [
    ["fits", { steps: [rstep("list the files", "fs.list_dir")] }],
    ["steps", { steps: Array.from({ length: 45 }, (_, i) =>
      rstep("read notes " + i + ".txt", "fs.read_file")) }],
    ["time", { planMs: 10000,
      steps: Array.from({ length: 5 }, (_, i) =>
        rstep("read notes " + i + ".txt", "fs.read_file")) }],
    ["chars", { maxChars: 300,
      steps: [rstep("build a platformer game", "build"),
              rstep("x".repeat(400), "router", false)] }],
    ["context", { contextBytes: 7800,
      steps: [rstep("build a platformer game", "build"),
              rstep("read notes.txt", "fs.read_file")] }],
    ["project", { projectBytes: 470000,
      steps: [rstep("build a platformer game", "build"),
              rstep("read notes.txt", "fs.read_file")] }],
    ["stuck", { contextBytes: 9000,
      steps: [rstep("read notes.txt", "fs.read_file")] }],
  ];
  let rewriteIdentical = true;
  let needed = 0, fits = 0, refusals = 0, dropped = 0;
  const overKinds = new Set();
  rewriteCases.forEach(([name, extra]) => {
    const a = rw(extra);
    const b = rw(extra);
    if (!same(a, b)) rewriteIdentical = false;
    if (a.needed) needed += 1;
    if (a.needed && a.fits) fits += 1;
    if (a.needed && !a.fits) refusals += 1;
    dropped += a.dropped.length;
    a.over.forEach(kind => overKinds.add(kind));
  });
  out.rewrite = {
    cases: rewriteCases.length,
    identical: rewriteIdentical,
    needed: needed,
    variants: fits,
    refusals: refusals,
    dropped: dropped,
    overKinds: Array.from(overKinds).sort(),
  };

  /* ---- network proof --------------------------------------------------- */
  out.network = fetches - before;
  out.fetches = fetches;
  console.log(JSON.stringify(out));
})().catch(error => {
  console.error(error && error.stack || String(error));
  process.exit(1);
});

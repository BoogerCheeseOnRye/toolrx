/* toolrx in-browser sandbox.
 *
 * GitHub Pages has no Python server, so the dashboard runs the same
 * deterministic router in the tab (router.js) and executes the tools that
 * make sense in a browser against a small virtual workspace kept in
 * localStorage. Anything that needs a real socket or a real machine reports
 * that honestly instead of pretending.
 *
 * Exposes: self.toolrxWeb = { init, ready, run, files, reset }
 */
(function (root) {
  "use strict";

  const FS_KEY = "toolrx.web.fs.v1";
  const PROJECTS_KEY = "toolrx.projects.v1";
  const CHAT_KEY = "toolrx.chat.v1";
  const MEMORY_KEY = "toolrx.memory.v1";
  const LASTRUN_KEY = "toolrx.lastRun.v1";
  const BUNDLE_KEY = "toolrx.bundles.v1";
  /* All numeric caps come from toolrx/limits.json via web/limits.js. Read/cat
   * caps are for chat-sized output; project write caps are separate and
   * deliberately larger. Loading without the limits file is a wiring bug. */
  const LIMITS = (function () {
    if (!root.toolrxLimits) {
      throw new Error("toolrx/web/limits.js must load before sandbox.js");
    }
    return root.toolrxLimits;
  })();
  const MAX_FILE = LIMITS.readFileBytes;
  const MAX_TOTAL = LIMITS.readTotalBytes;
  const MAX_PROJECT_FILE = LIMITS.projectFileBytes;
  const MAX_PROJECT = LIMITS.projectBytes;
  const MAX_PROJECT_FILES = LIMITS.projectFiles;
  const BUILD_TIMEOUT = LIMITS.buildMs;        // ms, configurable
  const STEP_TIMEOUT = LIMITS.stepMs;          // ms per plan step, configurable
  const PLAN_TIMEOUT = LIMITS.planMs;          // ms for a whole plan, configurable
  const PROGRESS_MS = 250;
  const PROGRESS_BYTES = 32768;

  const SEED = {
    "notes.txt":
      "# toolrx scratch notes\n\n" +
      "- routing is hashed n-grams over 27 allow-listed tools\n" +
      "- confidence is the cosine score of the winning centroid\n" +
      "- try: \"add 12 and 30\", \"read notes.txt\", \"list the files in data\"\n" +
      "- file.edit writes into this virtual workspace (localStorage)\n",
    "README.md":
      "# in-browser workspace\n\n" +
      "This sandbox lives entirely in your browser. Edits persist in\n" +
      "localStorage and never leave the tab. The router is the same model\n" +
      "that runs under `python3 toolrx/server.py`.\n",
    "data/metrics.json":
      '{"runs": [12, 30, 7, 41], "unit": "ms", "router": "micro"}\n',
    "src/hello.py":
      'def hello():\n    return "routed without a transformer"\n',
  };

  let model = null;
  let loadedAt = 0;
  let rt = null;

  /* Preview state: the build templates render into here, and the dashboard
   * mirrors it into the iframe with srcdoc (no server round trip). */
  let preview = { html: "", kind: "", desc: "", title: "", theme: "dark", at: 0 };
  let previewListeners = [];

  function snapshotPreview() {
    return {
      html: preview.html, kind: preview.kind, desc: preview.desc,
      title: preview.title, theme: preview.theme, at: preview.at,
    };
  }

  function notifyPreview() {
    const state = snapshotPreview();
    previewListeners.forEach(function (fn) {
      try { fn(state); } catch (e) { /* a bad listener must not break a build */ }
    });
    try {
      root.dispatchEvent(new CustomEvent("toolrx:preview", { detail: state }));
    } catch (e) { /* very old browsers */ }
  }

  /* ----------------------------------------------------------- progress -- */
  /* Builds report phase boundaries and file checkpoints. A listener can show
   * status while a large project is being written, and the final event carries
   * characters, estimated tokens, elapsed time, and peak bytes. Events are
   * best-effort: a bad listener never breaks a build. */
  let progressListeners = [];
  let lastProgress = null;
  let buildSeq = 0;
  let cancelPending = false;

  function notifyProgress(evt) {
    const state = Object.assign({ at: Date.now() }, evt);
    state.partial = evt.partial !== false;
    lastProgress = state;
    progressListeners.forEach(function (fn) {
      try { fn(state); } catch (e) { /* ignore */ }
    });
    try {
      root.dispatchEvent(new CustomEvent("toolrx:progress", { detail: state }));
    } catch (e) { /* very old browsers */ }
    return state;
  }

  function bytesOf(text) {
    const C = root.toolrxContext;
    if (C && C.byteLength) return C.byteLength(text);
    return String(text == null ? "" : text).length;
  }

  function projectBytes(p) {
    const map = (p && p.files) || {};
    return Object.keys(map).reduce(function (n, k) { return n + bytesOf(map[k]); }, 0);
  }

  function projectBudget() {
    let n = MAX_PROJECT;
    try {
      const raw = root.localStorage && root.localStorage.getItem("toolrx.project.budget");
      const parsed = parseInt(raw, 10);
      if (!isNaN(parsed)) n = parsed;
    } catch (e) { /* private mode */ }
    return Math.max(16384, Math.min(2097152, n));
  }

  function configMs(key, fallback, min, max) {
    let n = fallback;
    try {
      const raw = root.localStorage && root.localStorage.getItem(key);
      const parsed = parseInt(raw, 10);
      if (!isNaN(parsed)) n = parsed;
    } catch (e) { /* private mode */ }
    return Math.max(min, Math.min(max, n));
  }

  function buildTimeout() {
    return configMs("toolrx.build.timeout", BUILD_TIMEOUT, 250, 30000);
  }

  function stepTimeout() {
    return configMs("toolrx.step.timeout", STEP_TIMEOUT, 250, 30000);
  }

  function planTimeout() {
    return configMs("toolrx.plan.timeout", PLAN_TIMEOUT, 250, 600000);
  }

  function planLimits() {
    const L = root.toolrxSkills && root.toolrxSkills.limits;
    return {
      chars: (L && L.plan) || LIMITS.planChars,
      steps: (L && L.steps) || LIMITS.planSteps,
      block: (L && L.block) || LIMITS.blockBytes,
      stepMs: stepTimeout(),
      planMs: planTimeout(),
    };
  }

  /* All-or-none size check used before a build or edit is written. */
  function budgetCheck(map) {
    const files = map || {};
    const names = Object.keys(files);
    const budget = projectBudget();
    let total = 0, big = null;
    names.forEach(function (name) {
      const size = bytesOf(files[name]);
      total += size;
      if (!big && size > MAX_PROJECT_FILE) big = { name: name, bytes: size };
    });
    let why = "";
    if (names.length > MAX_PROJECT_FILES) {
      why = "too many files (" + names.length + ", max " + MAX_PROJECT_FILES + ")";
    } else if (big) {
      why = "file " + big.name + " is " + big.bytes + " bytes (max " + MAX_PROJECT_FILE + ")";
    } else if (total > budget) {
      why = "the project would be " + total + " bytes (budget " + budget + ")";
    }
    return { ok: !why, why: why, total: total, budget: budget,
      files: names.length, peak: total };
  }

  /* ---------------------------------------------------------- projects ---- */
  /* A project is a small folder of real files (index.html, styles.css, app.js,
   * README.md, ARCHITECTURE.md) plus the bundled page used for the preview.
   * Projects live in localStorage next to the workspace; the flat workspace
   * mirrors them under projects/<slug>/ so fs tools can read them too. */
  function readProjects() {
    try {
      const raw = root.localStorage.getItem(PROJECTS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.items && typeof parsed.items === "object") {
          return { active: parsed.active || "", items: parsed.items };
        }
      }
    } catch (e) { /* private mode */ }
    return { active: "", items: {} };
  }

  function writeProjects() {
    try {
      root.localStorage.setItem(PROJECTS_KEY, JSON.stringify({ active: projects.active, items: projects.items }));
    } catch (e) { /* storage full or disabled */ }
    // Keep the active project's context in step with its real files. This is
    // the single capture point for builds, edits, growth, undo, themes, and
    // imports; context is per project and never leaves the tab.
    captureProjectContext(projects.active ? projects.items[projects.active] : null);
  }

  let projects = readProjects();

  function slugify(s) {
    return String(s || "project").toLowerCase().replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "").slice(0, 40) || "project";
  }

  function uniqueSlug(base) {
    let slug = slugify(base), n = 2;
    while (projects.items[slug]) slug = slugify(base) + "-" + n++;
    return slug;
  }

  function projectList() {
    return Object.keys(projects.items).map(function (k) {
      const p = projects.items[k];
      return {
        slug: k, name: p.name, kind: p.kind, desc: p.desc,
        files: Object.keys(p.files || {}), updated: p.updated, active: k === projects.active,
      };
    }).sort(function (a, b) { return (b.updated || 0) - (a.updated || 0); });
  }

  function newProject(name) {
    const slug = uniqueSlug(name || "untitled");
    const item = {
      slug: slug, name: String(name || "Untitled project").slice(0, 60),
      kind: "notes", desc: "", files: {}, bundled: "", created: Date.now(), updated: Date.now(),
    };
    projects.items[slug] = item;
    projects.active = slug;
    writeProjects();
    return item;
  }

  function activeProject() {
    return projects.active ? projects.items[projects.active] || null : null;
  }

  function findProject(ref) {
    let raw = String(ref === undefined || ref === null ? "" : ref).trim().replace(/\s+/g, " ");
    let low = raw.toLowerCase();
    if (!low || /^(?:this|the|my|current|active|it|that)(?:\s+project)?$/.test(low)) {
      return projects.active ? projects.items[projects.active] || null : null;
    }
    // "the project verdant wood", "my project notes" → bare project reference
    low = low.replace(/^(?:the|my|this|current|active)\s+project\s+/, "")
             .replace(/^(?:the|my|this)\s+/, "");
    const s = slugify(low);
    if (projects.items[s]) return projects.items[s];
    for (const k in projects.items) {
      const p = projects.items[k];
      if (String(p.name || "").toLowerCase() === low || slugify(p.name) === s) return p;
    }
    for (const k in projects.items) {
      const p = projects.items[k];
      const name = String(p.name || "").toLowerCase();
      if (name.indexOf(low) !== -1 || k.indexOf(s) !== -1) return p;
    }
    return null;
  }

  function openProject(slug) {
    const p = findProject(slug);
    if (!p) throw new Error("no such project: " + slug);
    projects.active = p.slug;
    writeProjects();
    // Prefer the project files over the cached bundle so edits always show.
    const html = bundleProject(p) || p.bundled;
    if (html) {
      p.bundled = html;
      preview = {
        html: html, kind: p.kind, desc: p.desc,
        title: p.name, theme: htmlTheme(p.files["index.html"]) || preview.theme, at: Date.now(),
      };
      notifyPreview();
    }
    return "opened " + p.name + " (" + p.slug + ") · " + Object.keys(p.files || {}).length + " files";
  }

  function renameProject(slug, name) {
    let p = findProject(slug);
    let viaActive = false;
    if (!p && projects.active) {
      // "change the name from verdant wood rpg to india" can refer to the
      // active project even if its name moved on. Prefer the project the user
      // is looking at over refusing the rename.
      p = activeProject();
      viaActive = !!p;
    }
    if (!p) throw new Error("no such project: " + slug);
    const label = String(name || p.name).trim().slice(0, 60);
    const pretty = /^[a-z][a-z0-9-]*$/.test(label)
      ? label.charAt(0).toUpperCase() + label.slice(1) : label;
    const before = p.name;
    p.name = pretty || p.name;
    let themed = false;
    const t = root.toolrxTemplates;
    // Renaming an RPG to a known setting also re-themes its files + preview.
    if (t && p.kind === "rpg" && /arthur|camelot|knight|india|bharat|sanskrit|space|sci-?fi|noir|detective|greek|olympus|japan|samurai|sakura|egypt|nile|pharaoh|ocean|abyss|atlantis|west|cowboy|frontier|cyber|neon|frost|snow|winter|volcan|lava|magma|ember|fung|mushroom|spore|sky|cloud|aether|clock|gear|brass|dream|sleep|reverie|plague|blight|archipelago|pirate|island|verdant|forest|astral|\bstars?\b|comet/i.test(label)) {
      try {
        const built = t.project("rpg", label, { theme: preview.theme });
        p.files = built.files;
        p.bundled = bundleProject(p);
        p.desc = label;
        themed = true;
      } catch (e) { /* keep the old files if re-theming fails */ }
    }
    p.updated = Date.now();
    projects.active = p.slug;
    writeProjects();
    if (p.slug === projects.active) {
      if (p.bundled) {
        preview = {
          html: p.bundled, kind: p.kind, desc: p.desc,
          title: p.name, theme: preview.theme, at: Date.now(),
        };
        notifyPreview();
      }
      writeProjectFiles(p);
    }
    return "renamed \"" + before + "\" → \"" + p.name + "\" · " + p.slug
      + (viaActive ? "\n(the old name was not found; renamed the active project)" : "")
      + (themed ? "\npreview re-themed for the new name" : "");
  }

  function deleteProject(slug) {
    const p = findProject(slug);
    if (!p) throw new Error("no such project: " + slug);
    const s = p.slug;
    delete projects.items[s];
    for (const f in files) {
      if (f.indexOf("projects/" + s + "/") === 0) delete files[f];
    }
    if (projects.active === s) projects.active = Object.keys(projects.items)[0] || "";
    writeProjects();
    writeFS(files);
    const C = contextModule();
    if (C) C.clear(s);
    return "deleted " + p.name + " · " + (projects.active ? "active is now " + projects.active : "no projects left");
  }

  /* ------------------------------------------------------- portability ---- */
  /* A bundle is a versioned JSON document and never touches the network. A
   * project bundle carries the plan, the file map, the build spec (and its
   * seed), the per-project context, the envelope it was written under, and the
   * operator settings. A workspace bundle carries every project plus the
   * active slug. Import validates the whole document before writing anything
   * and refuses unknown versions, traversal paths, duplicate slugs, and
   * oversized bundles by name. */

  function bundleKey(name) {
    const raw = String(name == null ? "" : name).trim() || "bundle";
    const stem = /\.toolrx\.json$/.test(raw)
      ? raw.slice(0, -".toolrx.json".length) : raw;
    return slugify(stem).slice(0, 60) + ".toolrx.json";
  }

  function readBundles() {
    try {
      const raw = root.localStorage && root.localStorage.getItem(BUNDLE_KEY);
      const parsed = raw ? JSON.parse(raw) : null;
      if (parsed && parsed.items && typeof parsed.items === "object") return parsed;
    } catch (e) { /* private mode */ }
    return { items: {} };
  }

  function saveBundle(name, text) {
    const body = String(text == null ? "" : text);
    const bytes = bytesOf(body);
    if (bytes > LIMITS.bundleBytes) {
      throw new Error("that bundle is " + bytes + " bytes, over the "
        + LIMITS.bundleBytes + "-byte bundle cap");
    }
    const key = bundleKey(name);
    const all = readBundles();
    all.items[key] = { text: body, at: Date.now(), bytes: bytes };
    try { root.localStorage.setItem(BUNDLE_KEY, JSON.stringify(all)); }
    catch (e) { throw new Error("this browser refused to store the bundle (storage is full)"); }
    const back = readBundles();
    if (!back.items[key] || back.items[key].text !== body) {
      throw new Error("this browser did not keep the bundle (storage is full)");
    }
    return key;
  }

  function readBundle(name) {
    const key = bundleKey(name);
    const item = readBundles().items[key];
    if (!item) {
      throw new Error("no bundle named \"" + key + "\" — export one first (say: list bundles)");
    }
    return item.text;
  }

  function bundleList() {
    const items = readBundles().items;
    const keys = Object.keys(items).sort();
    if (!keys.length) return "no bundles yet — say: export this project";
    return keys.map(function (key) {
      const item = items[key];
      return key + "  ·  " + (item.bytes || 0).toLocaleString() + " B  ·  "
        + new Date(item.at || 0).toISOString().slice(0, 19) + "Z";
    }).join("\n");
  }

  function settingsSnapshot() {
    return {
      projectBytes: projectBudget(),
      undoDepth: undoDepth(),
      stepMs: stepTimeout(),
      planMs: planTimeout(),
    };
  }

  /* Settings are stored as given; the readers clamp them, so a bundle can
   * never smuggle a value past the envelope. */
  function applySettings(src) {
    if (!src || typeof src !== "object") return;
    const put = function (key, value) {
      const n = parseInt(value, 10);
      if (!isFinite(n)) return;
      try { root.localStorage.setItem(key, String(n)); } catch (e) { /* ignore */ }
    };
    put("toolrx.project.budget", src.projectBytes);
    put("toolrx.undo.depth", src.undoDepth);
    put("toolrx.step.timeout", src.stepMs);
    put("toolrx.plan.timeout", src.planMs);
  }

  function projectPayload(p) {
    const C = contextModule();
    const state = C ? C.read(p.slug) : null;
    const plan = readLastPlan(p.slug);
    return {
      slug: p.slug,
      name: p.name, kind: p.kind, desc: p.desc,
      created: p.created || null, updated: p.updated || null,
      spec: p.spec || null,
      seed: p.spec && p.spec.seed != null ? (p.spec.seed >>> 0) : null,
      files: Object.assign({}, p.files || {}),
      plan: plan && Array.isArray(plan.steps)
        ? { version: 1, steps: plan.steps.slice(), status: (plan.status || []).slice() }
        : null,
      context: state ? state.entries.map(function (entry) {
        return { kind: entry.kind, key: entry.key, text: entry.text };
      }) : [],
    };
  }

  function projectDoc(p) {
    return {
      format: "toolrx.project",
      version: 2,
      exported: new Date().toISOString(),
      project: projectPayload(p),
      limits: Object.assign({}, LIMITS),
      settings: settingsSnapshot(),
    };
  }

  function exportProject(ref) {
    const p = findProject(ref);
    if (!p) throw new Error("no such project: " + ref);
    return JSON.stringify(projectDoc(p), null, 2);
  }

  function exportWorkspace() {
    return JSON.stringify({
      format: "toolrx.workspace",
      version: 1,
      exported: new Date().toISOString(),
      active: projects.active || "",
      projects: Object.keys(projects.items).sort().map(function (slug) {
        return projectPayload(projects.items[slug]);
      }),
      limits: Object.assign({}, LIMITS),
      settings: settingsSnapshot(),
    }, null, 2);
  }

  function checkBundleVersion(doc, format, low, high) {
    const version = parseInt(doc.version, 10);
    if (!isFinite(version)) throw new Error(format + " bundle has no version");
    if (version < low || version > high) {
      throw new Error("unsupported " + format + " version " + version
        + " (this build reads " + low + (high === low ? "" : "–" + high) + ")");
    }
  }

  function parseBundle(text) {
    const body = String(text == null ? "" : text);
    if (bytesOf(body) > LIMITS.bundleBytes) {
      throw new Error("that bundle is " + bytesOf(body) + " bytes, over the "
        + LIMITS.bundleBytes + "-byte bundle cap");
    }
    let raw;
    try { raw = JSON.parse(body); }
    catch (e) { throw new Error("that file is not valid JSON"); }
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      throw new Error("that file is not a toolrx bundle");
    }
    const format = raw.format ? String(raw.format) : "";
    if (format && format !== "toolrx.project" && format !== "toolrx.workspace") {
      throw new Error("unsupported bundle format \"" + format
        + "\" (this build reads toolrx.project and toolrx.workspace)");
    }
    if (format === "toolrx.workspace") {
      checkBundleVersion(raw, "toolrx.workspace", 1, 1);
      return { kind: "workspace", doc: raw };
    }
    if (format === "toolrx.project") {
      checkBundleVersion(raw, "toolrx.project", 1, 2);
      const project = raw.project && typeof raw.project === "object" ? raw.project : null;
      if (!project) throw new Error("that bundle has no project inside it");
      return { kind: "project", doc: raw, project: project };
    }
    // Documents written before the format field are single-project v1.
    const project = raw.project && typeof raw.project === "object" ? raw.project : raw;
    return { kind: "project", doc: raw, project: project };
  }

  function safeImportName(name) {
    return String(name || "").replace(/[^A-Za-z0-9._-]/g, "-")
      .replace(/^[.-]+/, "").slice(0, 80);
  }

  function importFileReason(name) {
    const raw = String(name == null ? "" : name);
    if (!raw.trim()) return "an empty name";
    if (/[\u0000-\u001f]/.test(raw)) return "control characters";
    if (raw.indexOf("\\") !== -1) return "a backslash path";
    if (/^[A-Za-z]:/.test(raw)) return "an absolute Windows path";
    if (raw.charAt(0) === "/") return "an absolute path";
    if (raw === "." || raw === "..") return "a relative path";
    if (raw.indexOf("/") !== -1) return "a folder path";
    return null;
  }

  function stageFiles(map) {
    if (!map || typeof map !== "object" || Array.isArray(map)) {
      throw new Error("no project files found in that JSON");
    }
    const out = {};
    Object.keys(map).forEach(function (orig) {
      const reason = importFileReason(orig);
      if (reason) {
        throw new Error("refused \"" + orig
          + "\": project files must be plain names, not " + reason);
      }
      let name = safeImportName(orig);
      if (!name) {
        throw new Error("refused \"" + orig + "\": the name is empty after sanitising");
      }
      const base = name;
      let n = 2;
      while (out[name]) name = n++ + "-" + base;
      const body = String(map[orig] === undefined || map[orig] === null ? "" : map[orig]);
      const bytes = bytesOf(body);
      if (bytes > MAX_PROJECT_FILE) {
        throw new Error("\"" + base + "\" is " + bytes + " bytes, over the "
          + MAX_PROJECT_FILE + "-byte file cap");
      }
      out[name] = body;
    });
    if (!Object.keys(out).length) throw new Error("the project has no files");
    return out;
  }

  function stageContext(list) {
    if (!Array.isArray(list)) return [];
    const out = [];
    list.forEach(function (entry) {
      if (!entry || typeof entry !== "object") return;
      const kind = String(entry.kind == null ? "" : entry.kind).slice(0, 40);
      const key = String(entry.key == null ? "" : entry.key).slice(0, 80);
      if (!/^[a-z][a-z0-9.]*$/.test(kind) || !key) return;
      out.push({ kind: kind, key: key, text: String(entry.text == null ? "" : entry.text) });
    });
    return out;
  }

  function stagePlan(plan) {
    if (!plan || typeof plan !== "object" || !Array.isArray(plan.steps)) return null;
    const steps = plan.steps.map(function (s) { return String(s == null ? "" : s); });
    if (!steps.length) return null;
    const limit = planLimits().steps;
    if (steps.length > limit) {
      throw new Error("that plan has " + steps.length + " steps, over the "
        + limit + "-step cap");
    }
    const status = Array.isArray(plan.status) ? plan.status : [];
    return {
      version: 1,
      steps: steps,
      status: steps.map(function (_, i) {
        const s = String(status[i] || "");
        return s === "done" || s === "error" ? s : "pending";
      }),
    };
  }

  function stageProject(src, slug) {
    if (!src || typeof src !== "object") throw new Error("that project is not an object");
    const files = stageFiles(src.files);
    const budget = budgetCheck(files);
    if (!budget.ok) {
      throw new Error("that project is too large to import (" + budget.why + ")");
    }
    const name = String(src.name || "Imported project").trim().slice(0, 60) || "Imported project";
    const p = {
      slug: slug, name: name,
      kind: String(src.kind || "imported").slice(0, 40),
      desc: String(src.desc || "").slice(0, 300),
      files: files, bundled: "", created: Date.now(), updated: Date.now(),
    };
    if (src.spec && typeof src.spec === "object") p.spec = src.spec;
    return { project: p, context: stageContext(src.context), plan: stagePlan(src.plan) };
  }

  function restoreProjectContext(slug, context, plan) {
    const C = contextModule();
    if (!C) return;
    if (context && context.length) C.setMany(slug, context);
    if (plan) C.set(slug, "plan", "last", C.stable(plan));
  }

  function installProject(staged) {
    const p = staged.project;
    projects.items[p.slug] = p;
    projects.active = p.slug;
    p.bundled = bundleProject(p);
    writeProjects();
    writeProjectFiles(p);
    restoreProjectContext(p.slug, staged.context, staged.plan);
    if (p.bundled) {
      preview = {
        html: p.bundled, kind: p.kind, desc: p.desc, title: p.name,
        theme: htmlTheme(p.files["index.html"]) || preview.theme, at: Date.now(),
      };
      notifyPreview();
    }
  }

  function importProject(text) {
    return importProjectDoc(parseBundle(text));
  }

  function importProjectDoc(parsed) {
    if (parsed.kind === "workspace") {
      throw new Error("that is a workspace bundle — say: import the workspace from <bundle>");
    }
    const name = String(parsed.project.name || "Imported project").trim().slice(0, 60)
      || "Imported project";
    const staged = stageProject(parsed.project, uniqueSlug(name));
    installProject(staged);
    return "imported \"" + staged.project.name + "\" → projects/" + staged.project.slug
      + " (" + Object.keys(staged.project.files).length + " files"
      + (staged.plan ? " + plan" : "") + ")";
  }

  function importWorkspace(text) {
    return importWorkspaceDoc(parseBundle(text));
  }

  function importWorkspaceDoc(parsed) {
    if (parsed.kind !== "workspace") {
      throw new Error("that is a single project bundle — say: import the project from <bundle>");
    }
    const list = Array.isArray(parsed.doc.projects) ? parsed.doc.projects : [];
    if (!list.length) throw new Error("that workspace has no projects");
    const seen = {};
    const staged = list.map(function (src, i) {
      const label = src && (src.slug || src.name) ? String(src.slug || src.name) : "project " + (i + 1);
      const slug = slugify(label);
      if (seen[slug]) {
        throw new Error("duplicate project slug \"" + slug + "\" in that workspace");
      }
      seen[slug] = true;
      if (projects.items[slug]) {
        throw new Error("this workspace already has \"" + slug
          + "\" — delete it first or rename the bundle");
      }
      return stageProject(src, slug);
    });
    // All-or-none: snapshot the workspace, then restore it on any failure.
    const before = {
      active: projects.active,
      items: JSON.parse(JSON.stringify(projects.items)),
      files: Object.assign({}, files),
    };
    try {
      staged.forEach(function (s) { projects.items[s.project.slug] = s.project; });
      const want = String(parsed.doc.active || "");
      projects.active = staged.some(function (s) { return s.project.slug === want; })
        ? want : staged[0].project.slug;
      staged.forEach(function (s) { s.project.bundled = bundleProject(s.project); });
      writeProjects();
      staged.forEach(function (s) {
        writeProjectFiles(s.project);
        restoreProjectContext(s.project.slug, s.context, s.plan);
      });
      applySettings(parsed.doc.settings);
      const check = readProjects();
      const lost = staged.filter(function (s) { return !check.items[s.project.slug]; });
      if (lost.length) throw new Error("this browser did not keep the workspace (storage is full)");
    } catch (e) {
      projects = { active: before.active, items: before.items };
      files = before.files;
      writeFS(files);
      writeProjects();
      staged.forEach(function (s) {
        const C = contextModule();
        if (C) C.clear(s.project.slug);
      });
      throw e;
    }
    const p = activeProject();
    if (p && p.bundled) {
      preview = {
        html: p.bundled, kind: p.kind, desc: p.desc, title: p.name,
        theme: htmlTheme(p.files["index.html"]) || preview.theme, at: Date.now(),
      };
      notifyPreview();
    }
    return "imported workspace · " + staged.length + " project"
      + (staged.length === 1 ? "" : "s") + " · active " + projects.active;
  }

  function importBundle(text) {
    const parsed = parseBundle(text);
    return parsed.kind === "workspace"
      ? importWorkspaceDoc(parsed) : importProjectDoc(parsed);
  }

  function shortSha(text) {
    return root.blake2bHex ? root.blake2bHex(String(text), null, 8) : "n/a";
  }

  function exportProjectBundle(ref) {
    const p = findProject(ref);
    if (!p) throw new Error("no such project: " + ref);
    const text = exportProject(p.slug);
    const key = saveBundle(p.slug, text);
    return "exported \"" + p.name + "\" · " + Object.keys(p.files || {}).length + " files · "
      + bytesOf(text).toLocaleString() + " B · seed "
      + (p.spec && p.spec.seed != null ? (p.spec.seed >>> 0) : "n/a")
      + "\nbundle " + key + " saved in this tab · sha " + shortSha(text)
      + "\ndownload it from Projects → export, or import it with: import the project from "
      + key;
  }

  function exportWorkspaceBundle() {
    const text = exportWorkspace();
    const key = saveBundle("workspace", text);
    const n = Object.keys(projects.items).length;
    return "exported workspace · " + n + " project" + (n === 1 ? "" : "s") + " · "
      + bytesOf(text).toLocaleString() + " B · sha " + shortSha(text)
      + "\nbundle " + key + " saved in this tab"
      + "\nimport it with: import the workspace from " + key;
  }

  function importProjectNamed(name) {
    return importProject(readBundle(name));
  }

  function importWorkspaceNamed(name) {
    return importWorkspace(readBundle(name));
  }

  function filesForProject(p) {
    const out = [];
    for (const name in p.files) out.push(name);
    return out.sort();
  }

  function writeProjectFiles(p) {
    // mirror into the flat workspace so read/list/count commands see the files
    for (const f in files) {
      if (f.indexOf("projects/" + p.slug + "/") === 0) delete files[f];
    }
    for (const name in p.files) {
      files["projects/" + p.slug + "/" + name] = p.files[name];
    }
    writeFS(files);
  }

  function escHtml(s) {
    return String(s === undefined || s === null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function htmlTheme(html) {
    const m = /<html\b[^>]*\bclass\s*=\s*["']([^"']*)["']/i.exec(String(html || ""));
    return m && /\blight\b/i.test(m[1]) ? "light" : "dark";
  }

  function setHtmlTheme(html, theme) {
    const cls = theme === "light" ? "light" : "dark";
    return String(html || "").replace(/<html\b([^>]*)>/i, function (_, attrs) {
      if (/\bclass\s*=\s*(["']).*?\1/i.test(attrs)) {
        return "<html" + attrs.replace(/\bclass\s*=\s*(["']).*?\1/i, 'class="' + cls + '"') + ">";
      }
      return "<html" + attrs + ' class="' + cls + '">';
    });
  }

  /* Re-inline styles.css and app.js so a project edited as separate files can
   * still render inside the sandboxed preview iframe (which has no base URL). */
  function bundleProject(p) {
    const f = (p && p.files) || {};
    let html = String(f["index.html"] || "");
    if (!html) return "";
    const css = String(f["styles.css"] || "");
    html = html.replace(/<link\b[^>]*href\s*=\s*["']styles\.css["'][^>]*>/i, function () {
      return "<style>\n" + css + "\n</style>";
    });
    // Inline every project-local script the page references, in place, so the
    // preview needs no base URL and the order of shared runtimes, modules,
    // content, and app code is preserved. Nested module paths are allowed;
    // absolute URLs and parent traversal are not.
    html = html.replace(
      /<script\b([^>]*)\bsrc\s*=\s*["']([^"']+\.js)["'][^>]*>\s*<\/script>/gi,
      function (tag, attrs, src) {
        const clean = src.replace(/^\.\//, "");
        if (/^(?:[a-z]+:)?\/\//i.test(clean) || clean.indexOf("..") >= 0
            || clean.indexOf("\\") >= 0) return tag;
        const body = String(f[clean] || f[src] || "");
        if (!body && clean !== "app.js") return tag;
        return "<script>\n" + body + "\n</script>";
      });
    html = html.replace(/offline · (?:separate files|self-contained)/g, "offline · project preview");
    return html;
  }

  function refreshProject(p, theme) {
    if (!p) return "";
    const nextTheme = theme === "light" || theme === "dark"
      ? theme : htmlTheme((p.files || {})["index.html"]);
    const html = bundleProject(p);
    if (html) p.bundled = html;
    p.updated = Date.now();
    writeProjects();
    writeProjectFiles(p);
    if (p.slug === projects.active && p.bundled) {
      preview = {
        html: p.bundled, kind: p.kind, desc: p.desc,
        title: preview.title || p.name, theme: nextTheme, at: Date.now(),
      };
      notifyPreview();
    }
    return p.bundled || "";
  }

  function projectForEdit(ref) {
    const p = findProject(ref);
    if (!p) throw new Error("no active project — build something first");
    if (!p.files || !p.files["index.html"]) {
      throw new Error("this project has no page yet — build something first");
    }
    return p;
  }

  function editProjectTitle(ref, name) {
    const p = projectForEdit(ref);
    const title = String(name || "").replace(/\s+/g, " ").trim().slice(0, 80);
    if (!title) throw new Error("say what the page title should be");
    const before = ((p.files["index.html"].match(/<h1\b[^>]*>([\s\S]*?)<\/h1>/i) || [])[1] || "")
      .replace(/<[^>]*>/g, "").trim();
    let html = p.files["index.html"];
    let changed = false;
    html = html.replace(/<title>[\s\S]*?<\/title>/i, function () {
      changed = true;
      return "<title>" + escHtml(title) + " · toolrx</title>";
    });
    html = html.replace(/<h1\b([^>]*)>[\s\S]*?<\/h1>/i, function (_, attrs) {
      changed = true;
      return "<h1" + attrs + ">" + escHtml(title) + "</h1>";
    });
    if (!changed) throw new Error("this page has no title element to change");
    p.files["index.html"] = html;
    if (p.files["README.md"]) {
      p.files["README.md"] = p.files["README.md"].replace(/^# [^\n]*/m, "# " + title);
    }
    if (p.files["ARCHITECTURE.md"]) {
      p.files["ARCHITECTURE.md"] = p.files["ARCHITECTURE.md"].replace(/^# Architecture · [^\n]*/m,
        "# Architecture · " + title);
    }
    preview.title = title;
    refreshProject(p);
    return 'page title "' + before + '" → "' + title + '" · edited projects/' + p.slug
      + "/index.html\npreview re-bundled from the project files";
  }

  function setProjectTheme(ref, name) {
    const p = projectForEdit(ref);
    const theme = String(name || "").toLowerCase() === "light" ? "light" : "dark";
    p.files["index.html"] = setHtmlTheme(p.files["index.html"], theme);
    preview.title = preview.title || p.name;
    refreshProject(p, theme);
    files["site/index.html"] = p.bundled;
    writeFS(files);
    return p.name + " is now " + theme + " · edited projects/" + p.slug
      + "/index.html (other files untouched)";
  }

  function addThemeToggle(ref) {
    const p = projectForEdit(ref);
    const hasButton = /id\s*=\s*["']themeToggle["']/i.test(p.files["index.html"]);
    const js = p.files["app.js"] || "";
    const hasScript = /getElementById\(\s*["']themeToggle["']\s*\)/.test(js);
    if (hasButton && hasScript) {
      return p.name + " already has a theme toggle · nothing changed";
    }
    if (!hasButton) {
      p.files["index.html"] = p.files["index.html"].replace(/<h1\b([^>]*)>[\s\S]*?<\/h1>/i,
        function (m) {
          return m + '\n<button type="button" id="themeToggle" class="btn ghost" '
            + 'style="align-self:flex-start;margin-top:8px">◐ theme</button>';
        });
    }
    if (!hasScript) {
      p.files["app.js"] = js + [
        "",
        "(function () {",
        "  var b = document.getElementById('themeToggle');",
        "  if (!b) return;",
        "  b.addEventListener('click', function () {",
        "    var root = document.documentElement;",
        "    root.classList.toggle('light');",
        "    b.textContent = root.classList.contains('light') ? '☾ dark' : '◐ theme';",
        "  });",
        "})();",
        ""
      ].join("\n");
    }
    preview.title = preview.title || p.name;
    refreshProject(p);
    return "added a working theme toggle to " + p.name + " · edited index.html + app.js\n"
      + "preview re-bundled from the project files";
  }

  function addFooterNote(ref, text) {
    const p = projectForEdit(ref);
    const note = String(text || "").replace(/\s+/g, " ").trim().slice(0, 160);
    if (!note) throw new Error("say what the footer note should say");
    const block = '<div id="projectNote" class="muted small" '
      + 'style="max-width:980px;margin:14px auto 0;text-align:center">'
      + escHtml(note) + "</div>\n";
    let html = p.files["index.html"];
    let replaced = false;
    if (/<div\b[^>]*id\s*=\s*["']projectNote["'][^>]*>[\s\S]*?<\/div>\s*/i.test(html)) {
      html = html.replace(/<div\b[^>]*id\s*=\s*["']projectNote["'][^>]*>[\s\S]*?<\/div>\s*/i, block);
      replaced = true;
    } else if (/<footer\b/i.test(html)) {
      html = html.replace(/<footer\b/i, block + "<footer");
    } else {
      html = html.replace(/<\/body>/i, block + "</body>");
    }
    p.files["index.html"] = html;
    preview.title = preview.title || p.name;
    refreshProject(p);
    return (replaced ? "updated" : "added") + ' the footer note on ' + p.name
      + ': "' + note + '"\npreview re-bundled from the project files';
  }

  function writeProjectFile(ref, name, content) {
    const p = findProject(ref);
    if (!p) throw new Error("no active project — build something first");
    const n = String(name || "").replace(/^\/+/, "");
    if (!(n in (p.files || {}))) throw new Error("no such file in project: " + n);
    const text = String(content === undefined || content === null ? "" : content);
    if (bytesOf(text) > MAX_PROJECT_FILE) {
      throw new Error("file exceeds " + MAX_PROJECT_FILE + " bytes — previous project kept");
    }
    const next = copyFiles(p.files);
    next[n] = text;
    const budget = budgetCheck(next);
    if (!budget.ok) {
      throw new Error("not written · " + budget.why + " — previous project kept");
    }
    p.files[n] = text;
    p.updated = Date.now();
    refreshProject(p);
    return "wrote projects/" + p.slug + "/" + n + " (" + bytesOf(text) + " bytes)\n"
      + "preview re-bundled from the project files";
  }

  function installBuilt(built, desc) {
    const started = Date.now();
    const token = ++buildSeq;
    const names = Object.keys(built.files || {});
    const total = projectBytes(built);
    const budget = budgetCheck(built.files || {});
    const timeout = buildTimeout();
    const stats = { chars: total, tokens: Math.ceil(total / 4) };

    notifyProgress({
      phase: "spec", token: token, project: "", done: 0, total: names.length,
      files: [], bytes: total, budget: budget.budget, chars: total,
      tokens: stats.tokens, ms: 0, peak: total, partial: true,
    });

    if (cancelPending) {
      cancelPending = false;
      notifyProgress({ phase: "cancelled", token: token, project: "", done: 0,
        total: names.length, files: [], bytes: total, budget: budget.budget,
        chars: total, tokens: stats.tokens, ms: Date.now() - started,
        peak: total, partial: true });
      throw new Error("build cancelled — previous project kept");
    }
    if (!budget.ok) {
      notifyProgress({ phase: "error", token: token, project: "", done: 0,
        total: names.length, files: [], bytes: total, budget: budget.budget,
        chars: total, tokens: stats.tokens, ms: Date.now() - started,
        peak: total, partial: true });
      throw new Error("not built · " + budget.why + " — previous project kept");
    }

    // File checkpoints: one per file or every ~32 KB, whichever comes first.
    let acc = 0, lastAt = started, lastBytes = 0;
    for (let i = 0; i < names.length; i++) {
      if (Date.now() - started > timeout) {
        notifyProgress({ phase: "error", token: token, project: "", done: i,
          total: names.length, files: names.slice(0, i), bytes: acc,
          budget: budget.budget, chars: acc, tokens: Math.ceil(acc / 4),
          ms: Date.now() - started, peak: acc, partial: true });
        throw new Error("build timed out after " + timeout + " ms — previous project kept");
      }
      acc += bytesOf(built.files[names[i]]);
      const due = i === names.length - 1
        || acc - lastBytes >= PROGRESS_BYTES
        || Date.now() - lastAt >= PROGRESS_MS;
      if (due) {
        notifyProgress({ phase: "files", token: token, project: "", done: i + 1,
          total: names.length, files: names.slice(0, i + 1), bytes: acc,
          budget: budget.budget, chars: acc, tokens: Math.ceil(acc / 4),
          ms: Date.now() - started, peak: acc, partial: true });
        lastAt = Date.now();
        lastBytes = acc;
      }
    }

    // Reuse a project with the same kind, description, and generated title.
    // Default RPG builds advance the seed, so a new title is a new project.
    let p = null;
    for (const k in projects.items) {
      const it = projects.items[k];
      if (it.kind === built.kind && it.desc === String(desc || "")
          && it.name === built.title) { p = it; break; }
    }
    if (!p) {
      p = newProject(built.title);
      p.kind = built.kind;
      p.desc = String(desc || "");
      p.slug = p.slug; // set on creation
    }
    p.name = built.title;
    p.kind = built.kind;
    p.files = built.files;
    p.spec = built.spec || null;
    p.edits = [];
    p.history = [];
    p.bundled = bundleProject(p);
    p.updated = Date.now();
    if (!p.created) p.created = p.updated;
    projects.active = p.slug;
    notifyProgress({ phase: "bundle", token: token, project: p.slug,
      done: names.length, total: names.length, files: names, bytes: total,
      bundleBytes: bytesOf(p.bundled), budget: budget.budget,
      chars: total, tokens: stats.tokens, ms: Date.now() - started,
      peak: Math.max(total, bytesOf(p.bundled)), partial: true });
    if (cancelPending) {
      cancelPending = false;
      notifyProgress({ phase: "cancelled", token: token, project: p.slug,
        done: names.length, total: names.length, files: names, bytes: total,
        bundleBytes: bytesOf(p.bundled), budget: budget.budget,
        chars: total, tokens: stats.tokens, ms: Date.now() - started,
        peak: Math.max(total, bytesOf(p.bundled)), partial: true });
      throw new Error("build cancelled — previous project kept");
    }
    writeProjects();
    writeProjectFiles(p);
    preview = {
      html: p.bundled, kind: built.kind, desc: String(desc || ""),
      title: built.title, theme: preview.theme === "light" ? "light" : "dark", at: Date.now(),
    };
    notifyPreview();
    remember("last_build", {
      title: built.title, kind: built.kind, desc: String(desc || ""),
      slug: p.slug, theme: preview.theme, at: Date.now(),
    });
    const ms = Date.now() - started;
    const peak = Math.max(total, bytesOf(p.bundled));
    notifyProgress({ phase: "done", token: token, project: p.slug,
      done: names.length, total: names.length, files: names, bytes: total,
      bundleBytes: bytesOf(p.bundled), budget: budget.budget,
      chars: total, tokens: stats.tokens, ms: ms, peak: peak, partial: false });
    const fileNames = filesForProject(p);
    return (built.specLine ? built.specLine + "\n" : "")
      + 'built "' + built.title + '" → projects/' + p.slug + " (" + fileNames.length + " files)\n"
      + "  " + fileNames.join(" · ") + "\n"
      + "preview updated · active project: " + p.slug + "\n"
      + "build · " + total + " chars · ~" + stats.tokens + " tokens · "
      + ms + " ms · peak " + peak + " bytes · budget " + budget.budget + "\n"
      + "try: show project files · read projects/" + p.slug + "/ARCHITECTURE.md";
  }

  function buildProject(kind, desc) {
    const t = root.toolrxTemplates;
    if (!t || !t.project) throw new Error("build templates are not loaded");
    const theme = preview.theme === "light" ? "light" : "dark";
    return installBuilt(t.project(kind, desc, { theme: theme }), desc);
  }

  function buildWebPage(info) {
    const t = root.toolrxTemplates;
    if (!t || !t.webPage) throw new Error("build templates are not loaded");
    const theme = preview.theme === "light" ? "light" : "dark";
    const built = t.webPage(Object.assign({}, info, { theme: theme }));
    const desc = "web page: " + built.title;
    return installBuilt(built, desc);
  }

  /* ---------------------------------------------------- composable edits -- */
  /* Every patch snapshots the project first, so undo restores the exact files
   * that existed before it — including files added or removed by a rebuild. */
  function copyFiles(files) {
    const out = {};
    for (const k in (files || {})) out[k] = files[k];
    return out;
  }

  /* Undo depth is configurable and defaults to 16 full-file snapshots. */
  const UNDO_DEFAULT = LIMITS.undoDepth;
  function undoDepth() {
    let n = UNDO_DEFAULT;
    try {
      const raw = root.localStorage && root.localStorage.getItem("toolrx.undo.depth");
      const parsed = parseInt(raw, 10);
      if (!isNaN(parsed)) n = parsed;
    } catch (e) { /* private mode */ }
    return Math.max(1, Math.min(64, n));
  }

  function pushProjectHistory(p, label) {
    if (!p.history) p.history = [];
    p.history.push({
      label: String(label || "edit"),
      files: copyFiles(p.files),
      spec: JSON.parse(JSON.stringify(p.spec || null)),
      edits: (p.edits || []).slice(),
      name: p.name,
      desc: p.desc,
      at: Date.now(),
    });
    const depth = undoDepth();
    if (p.history.length > depth) p.history = p.history.slice(-depth);
  }

  function editReport(before, after, res) {
    const changed = [];
    const names = new Set(Object.keys(before).concat(Object.keys(after)));
    names.forEach(function (n) {
      if (before[n] !== after[n]) changed.push(n);
    });
    changed.sort();
    const t = root.toolrxTemplates;
    const lines = ['edited "' + res.name + '" · ' + res.label];
    if (t && t.specLine) lines.push(t.specLine(res.spec));
    if (res.fn) lines.push(res.fn + " now carries the change");
    lines.push("changed: " + (changed.length ? changed.join(", ") : "no files"));
    if (res.note) lines.push(res.note);
    lines.push("preview re-bundled · active project: " + res.slug + " · say undo to revert");
    return lines.join("\n");
  }

  function applyProjectEdit(patch, arg) {
    const p = projectForEdit();
    const P = root.toolrxPatches;
    if (!P) throw new Error("edit patches are not loaded");
    const t = root.toolrxTemplates;
    const spec = p.spec || (t && t.spec ? t.spec(p.kind, p.desc) : null);
    const before = copyFiles(p.files);
    const res = P.apply(patch, {
      kind: p.kind, desc: p.desc, files: before, spec: spec, edits: p.edits || [],
    }, { arg: arg });
    if (!res.ok) {
      return {
        text: 'not edited · ' + res.message
          + "\ntry: build a compatible starter first, or say undo",
        error: true,
      };
    }
    const budget = budgetCheck(res.files);
    if (!budget.ok) {
      return {
        text: "not edited · " + budget.why + " — previous project kept",
        error: true,
      };
    }
    pushProjectHistory(p, res.label);
    p.files = res.files;
    p.spec = res.spec;
    p.edits = res.edits;
    p.bundled = bundleProject(p);
    p.updated = Date.now();
    writeProjects();
    writeProjectFiles(p);
    preview = {
      html: p.bundled, kind: p.kind, desc: p.desc,
      title: p.name, theme: preview.theme === "light" ? "light" : "dark", at: Date.now(),
    };
    notifyPreview();
    setEditContext(p.slug, { ids: [patch], labels: [res.label], arg: arg || "" });
    return editReport(before, p.files, {
      name: p.name, label: res.label, spec: p.spec, fn: res.fn,
      note: res.note, slug: p.slug,
    });
  }

  /* A bundle of two to five patches applies to one working copy and is written
   * only if every patch fits. One history entry means one undo reverts all. */
  function applyProjectEdits(list) {
    const p = projectForEdit();
    const P = root.toolrxPatches;
    if (!P || !P.resolve) throw new Error("edit patches are not loaded");
    const parts = String(list || "").split(/\s*,\s*|\s+and\s+/)
      .map(function (s) { return s.trim(); }).filter(Boolean);
    const ids = parts.map(function (s) { return P.resolve(s); });
    if (ids.length < 2 || ids.length > 5) {
      return 'not edited · give two to five edits, e.g. "add double jump and sound"';
    }
    const unknown = parts.filter(function (_, i) { return !ids[i]; });
    if (unknown.length) {
      return "not edited · unknown edit: " + unknown.join(", ");
    }
    const before = copyFiles(p.files);
    const applied = applyIdsToProject(p, ids, "");
    if (!applied.ok) {
      return {
        text: "not edited · " + applied.message
          + "\nnothing changed: the bundle applies all or none.",
        error: true,
      };
    }
    const files = applied.files;
    const spec = applied.spec;
    const edits = applied.edits;
    const labels = applied.labels;
    const budget = budgetCheck(files);
    if (!budget.ok) {
      return {
        text: "not edited · " + budget.why + " — previous project kept",
        error: true,
      };
    }
    pushProjectHistory(p, "bundle: " + labels.join(" + "));
    p.files = files;
    p.spec = spec;
    p.edits = edits;
    p.bundled = bundleProject(p);
    p.updated = Date.now();
    writeProjects();
    writeProjectFiles(p);
    preview = {
      html: p.bundled, kind: p.kind, desc: p.desc,
      title: p.name, theme: preview.theme === "light" ? "light" : "dark", at: Date.now(),
    };
    notifyPreview();
    setEditContext(p.slug, { ids: ids, labels: labels, arg: "" });
    const changed = [];
    const names = new Set(Object.keys(before).concat(Object.keys(p.files)));
    names.forEach(function (n) { if (before[n] !== p.files[n]) changed.push(n); });
    changed.sort();
    const t = root.toolrxTemplates;
    const lines = ['edited "' + p.name + '" · ' + labels.join(" + ")];
    if (t && t.specLine) lines.push(t.specLine(p.spec));
    lines.push("changed: " + (changed.length ? changed.join(", ") : "no files"));
    lines.push("preview re-bundled · active project: " + p.slug
      + " · one undo reverts the whole bundle");
    return lines.join("\n");
  }

  /* Grow the active project with real module files (or one named module or
   * system). Files are additive; app.js is only ever appended to. */
  function applyGrowth(which, name) {
    const p = projectForEdit();
    const P = root.toolrxPatches;
    if (!P || !P.grow) throw new Error("project growth is not loaded");
    const before = copyFiles(p.files);
    const res = P.grow({
      kind: p.kind, desc: p.desc, files: before, spec: p.spec, edits: p.edits || [],
    }, which, name);
    if (!res.ok) {
      return {
        text: "not grown · " + res.message
          + "\ntry: grow project, expand module core, or add crafting system",
        error: true,
      };
    }
    const budget = budgetCheck(res.files);
    if (!budget.ok) {
      return {
        text: "not grown · " + budget.why + " — previous project kept",
        error: true,
      };
    }
    pushProjectHistory(p, res.label);
    p.files = res.files;
    p.spec = res.spec;
    p.bundled = bundleProject(p);
    p.updated = Date.now();
    writeProjects();
    writeProjectFiles(p);
    preview = {
      html: p.bundled, kind: p.kind, desc: p.desc,
      title: p.name, theme: preview.theme === "light" ? "light" : "dark", at: Date.now(),
    };
    notifyPreview();
    const changed = [];
    const names = new Set(Object.keys(before).concat(Object.keys(p.files)));
    names.forEach(function (n) { if (before[n] !== p.files[n]) changed.push(n); });
    changed.sort();
    const t = root.toolrxTemplates;
    const lines = ['grew "' + p.name + '" · ' + res.label];
    if (t && t.specLine) lines.push(t.specLine(p.spec));
    lines.push("added: " + res.added.join(", "));
    if (res.skipped && res.skipped.length) {
      lines.push("already present: " + res.skipped.join(", "));
    }
    lines.push("changed: " + changed.join(", "));
    lines.push("preview re-bundled · active project: " + p.slug
      + " · say undo to remove the growth");
    return lines.join("\n");
  }

  function growActiveProject(which, name) {
    return applyGrowth(which, name);
  }

  function growActiveSystems(list) {
    return applyGrowth("systems", list);
  }

  function undoProjectEdit() {
    const p = projectForEdit("this project");
    if (!p.history || !p.history.length) {
      return "nothing to undo — this project has no recorded edits";
    }
    const snap = p.history.pop();
    const before = copyFiles(p.files);
    p.files = snap.files;
    p.spec = snap.spec;
    p.edits = snap.edits;
    if (snap.name) p.name = snap.name;
    if (snap.desc !== undefined) p.desc = snap.desc;
    p.bundled = bundleProject(p);
    p.updated = Date.now();
    writeProjects();
    writeProjectFiles(p);
    preview = {
      html: p.bundled, kind: p.kind, desc: p.desc,
      title: p.name, theme: preview.theme === "light" ? "light" : "dark", at: Date.now(),
    };
    notifyPreview();
    const changed = [];
    const names = new Set(Object.keys(before).concat(Object.keys(p.files)));
    names.forEach(function (n) { if (before[n] !== p.files[n]) changed.push(n); });
    return 'undid "' + snap.label + '" · restored ' + changed.length + " files"
      + (changed.length ? " (" + changed.sort().join(", ") + ")" : "")
      + "\npreview re-bundled · active project: " + p.slug;
  }

  /* ------------------------------------------------------ optional llm --- */
  /* The adapter is never required: these helpers only run when the user asks
   * for an LLM plan/patch, and the module itself refuses unless it is enabled.
   * A pending patch is stored in localStorage, never written to a file until
   * `apply the llm patch` is called, and installing it pushes the same
   * full-file history snapshot that `undo` already understands. */
  function llmModule() {
    const L = root.toolrxLlm;
    if (!L) throw new Error("the optional LLM adapter is not loaded");
    return L;
  }

  function llmStatus() {
    return llmModule().statusText();
  }

  function llmEnable(on) {
    return llmModule().enable(!!on);
  }

  function llmCacheClear() {
    return llmModule().clearCache();
  }

  async function llmPlan(prompt) {
    const L = llmModule();
    const r = await L.plan(prompt);
    return r.text;
  }

  async function llmPatch(file, instruction) {
    const L = llmModule();
    const p = projectForEdit();
    const name = L.safeFileName(file);
    if (!Object.prototype.hasOwnProperty.call(p.files, name)) {
      throw new Error("no " + name + " in " + p.slug
        + " — files: " + Object.keys(p.files).sort().join(", "));
    }
    const content = p.files[name];
    const r = await L.patch(name, instruction, { content: content, kind: p.kind });
    L.setPending({
      file: name, diff: r.diff, instruction: String(instruction || ""),
      beforeHash: L.hash(content), slug: p.slug, at: Date.now(),
    });
    return r.text + "\nnothing written yet — the pending patch is stored in this browser";
  }

  function llmApply() {
    const L = llmModule();
    const pending = L.pending();
    if (!pending) {
      return "there is no llm patch to apply — say llm patch app.js with <instruction> first";
    }
    const p = projectForEdit();
    if (pending.slug && pending.slug !== p.slug) {
      throw new Error("the pending patch was generated for project " + pending.slug
        + ", not " + p.slug + " — discard it and generate another");
    }
    const before = p.files[pending.file];
    if (before == null) {
      throw new Error(pending.file + " is no longer in " + p.slug + " — regenerate the patch");
    }
    if (L.hash(before) !== pending.beforeHash) {
      throw new Error(pending.file + " changed since the patch was generated — regenerate it");
    }
    const next = L.applyDiff(before, pending.diff, pending.file);
    if (next === before) throw new Error("the patch would not change " + pending.file);
    pushProjectHistory(p, "llm patch " + pending.file);
    p.files[pending.file] = next;
    p.bundled = bundleProject(p);
    p.updated = Date.now();
    writeProjects();
    writeProjectFiles(p);
    preview = {
      html: p.bundled, kind: p.kind, desc: p.desc,
      title: p.name, theme: preview.theme === "light" ? "light" : "dark", at: Date.now(),
    };
    notifyPreview();
    L.clearPending();
    return 'applied the llm patch · ' + pending.file
      + "\ninstruction: " + (pending.instruction || "(none)")
      + "\nchanged: " + pending.file + " (the model does not edit the build spec)"
      + "\npreview re-bundled · active project: " + p.slug + " · say undo to revert";
  }

  function llmDiscard() {
    const L = llmModule();
    const pending = L.pending();
    if (!pending) return "there is no llm patch to discard";
    L.clearPending();
    return "discarded the llm patch for " + pending.file + " — no files were written";
  }

  /* ------------------------------------------------------------- chat ----- */
  let chatLog = (function () {
    try {
      const raw = root.localStorage.getItem(CHAT_KEY);
      if (raw) {
        const p = JSON.parse(raw);
        if (Array.isArray(p)) return p.slice(-80);
      }
    } catch (e) { /* ignore */ }
    return [];
  })();

  function writeChat() {
    try { root.localStorage.setItem(CHAT_KEY, JSON.stringify(chatLog.slice(-80))); }
    catch (e) { /* ignore */ }
  }

  function chatAppend(who, text) {
    chatLog.push({ who: String(who || "toolrx"), text: String(text == null ? "" : text), at: Date.now() });
    if (chatLog.length > 80) chatLog = chatLog.slice(-80);
    writeChat();
    return text;
  }

  function chatHistory() { return chatLog.slice(); }

  let memory = (function () {
    try {
      const raw = root.localStorage.getItem(MEMORY_KEY);
      if (raw) {
        const p = JSON.parse(raw);
        if (p && typeof p === "object") return p;
      }
    } catch (e) { /* ignore */ }
    return {};
  })();

  function remember(key, value) {
    if (value === undefined) return memory[key];
    memory[key] = value;
    try { root.localStorage.setItem(MEMORY_KEY, JSON.stringify(memory)); } catch (e) { /* ignore */ }
    return value;
  }

  function forgetKey(key) {
    delete memory[key];
    try { root.localStorage.setItem(MEMORY_KEY, JSON.stringify(memory)); } catch (e) { /* ignore */ }
  }

  function clearMemory() {
    memory = {};
    try { root.localStorage.removeItem(MEMORY_KEY); } catch (e) { /* ignore */ }
  }

  /* ----------------------------------------------------------- last run -- */
  /* Step 35 observability: the dashboard shows the envelope of the most recent
   * prompt (size, steps, errors, confidence, margin, time, bytes, files, undo
   * depth). This is local UI state only; it never enters a network payload. */
  let lastRun = readLastRun();

  function readLastRun() {
    try {
      const raw = root.localStorage && root.localStorage.getItem(LASTRUN_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (e) {
      return null;
    }
  }

  function distribution(values) {
    const nums = (values || []).filter(function (v) {
      return typeof v === "number" && isFinite(v);
    }).sort(function (a, b) { return a - b; });
    if (!nums.length) return null;
    const pick = function (q) {
      return nums[Math.max(0, Math.min(nums.length - 1,
        Math.round(q * (nums.length - 1))))];
    };
    const mid = Math.floor(nums.length / 2);
    const median = nums.length % 2
      ? nums[mid] : (nums[mid - 1] + nums[mid]) / 2;
    const round = function (v) { return Math.round(v * 10000) / 10000; };
    return {
      n: nums.length,
      min: round(nums[0]),
      p10: round(pick(0.10)),
      median: round(median),
      p90: round(pick(0.90)),
      max: round(nums[nums.length - 1]),
    };
  }

  function recordRun(query, results, started, meta) {
    const list = Array.isArray(results) ? results : [];
    if (!list.length) return null;
    meta = meta || {};
    const text = list.map(function (r) { return r && r.text ? r.text : ""; })
      .filter(Boolean).join("\n");
    const last = list[list.length - 1] || {};
    const p = activeProject();
    const fileMap = (p && p.files) || files || {};
    const built = list.some(function (r) { return /^build(?:\.|$)/.test(String(r && r.via || "")); });
    const projectSize = p ? projectBytes(p)
      : Object.keys(fileMap).reduce(function (n, k) { return n + bytesOf(fileMap[k]); }, 0);
    const via = list.length === 1
      ? String(last.via || "")
      : "plan:" + list.length + ":" + String(last.via || "steps");
    const elapsed = Math.max(0, Math.round(now() - started));
    const usedBytes = built ? projectSize : bytesOf(text);
    const usedFiles = Object.keys(fileMap).length;
    const maxBytes = projectBudget();
    const plan = planLimits();
    const stepsDetail = list.map(function (r, i) {
      const item = r || {};
      const number = function (v) {
        return typeof v === "number" && isFinite(v) ? v : null;
      };
      return {
        n: i + 1,
        step: String(item.step || "").replace(/\s+/g, " ").slice(0, 240),
        via: String(item.via || "").slice(0, 80),
        ms: number(item.ms) == null ? null : Math.max(0, Math.round(item.ms)),
        confidence: number(item.confidence),
        margin: number(item.margin),
        bytes: bytesOf(item.text || ""),
        error: !!item.error,
      };
    });
    const confidenceStats = distribution(stepsDetail.map(function (s) { return s.confidence; }));
    const marginStats = distribution(stepsDetail.map(function (s) { return s.margin; }));
    const failed = list.filter(function (r) { return r && r.error; }).length;
    const planned = Number.isFinite(meta.planned) ? meta.planned
      : (list[0] && list[0].planLength) || list.length;
    const beforeFiles = meta.beforeFiles || {};
    const touched = Object.keys(fileMap).filter(function (name) {
      return beforeFiles[name] !== fileMap[name];
    }).sort();
    const beforeBytes = Number.isFinite(meta.beforeBytes) ? meta.beforeBytes : 0;
    const contextBytes = typeof meta.contextBytes === "number" && isFinite(meta.contextBytes)
      ? Math.max(0, Math.round(meta.contextBytes)) : null;
    const emitted = stepsDetail.reduce(function (n, s) { return n + s.bytes; }, 0);
    const budget = {
      files: { used: usedFiles, max: MAX_PROJECT_FILES,
               remaining: Math.max(0, MAX_PROJECT_FILES - usedFiles) },
      bytes: { used: usedBytes, max: maxBytes,
               remaining: Math.max(0, maxBytes - usedBytes) },
      ms: { used: elapsed, max: plan.planMs, stepMs: plan.stepMs,
            remaining: Math.max(0, plan.planMs - elapsed) },
      steps: { used: list.length, max: plan.steps,
               remaining: Math.max(0, plan.steps - list.length) },
      chars: { used: String(query == null ? "" : query).length,
               max: plan.chars,
               remaining: Math.max(0, plan.chars - String(query == null ? "" : query).length) },
      context: { used: contextBytes == null ? 0 : contextBytes,
                 max: LIMITS.contextBytes,
                 remaining: contextBytes == null ? LIMITS.contextBytes
                   : Math.max(0, LIMITS.contextBytes - contextBytes) },
      within: usedFiles <= MAX_PROJECT_FILES && usedBytes <= maxBytes
        && elapsed <= plan.planMs && list.length <= plan.steps
        && (contextBytes == null || contextBytes <= LIMITS.contextBytes),
      over: [],
    };
    if (usedFiles > MAX_PROJECT_FILES) budget.over.push("files");
    if (usedBytes > maxBytes) budget.over.push("bytes");
    if (elapsed > plan.planMs) budget.over.push("ms");
    if (list.length > plan.steps) budget.over.push("steps");
    if (contextBytes != null && contextBytes > LIMITS.contextBytes) budget.over.push("context");
    lastRun = {
      version: 2,
      at: Date.now(),
      chars: String(query == null ? "" : query).length,
      planned: planned,
      steps: list.length,
      executed: list.length,
      failed: failed,
      errors: failed,
      via: via.slice(0, 160),
      // Keep the scalars the chip already reads, and add the full spread.
      confidence: confidenceStats ? confidenceStats.min : null,
      margin: marginStats ? marginStats.min : null,
      distribution: { confidence: confidenceStats, margin: marginStats },
      ms: elapsed,
      bytes: usedBytes,
      written: Math.max(0, projectSize - beforeBytes),
      emitted: emitted,
      files: usedFiles,
      filesTouched: touched,
      contextBytes: contextBytes,
      peakContextBytes: contextBytes,
      undo: p && p.history ? p.history.length : 0,
      ok: failed === 0,
      stepsDetail: stepsDetail,
      budget: budget,
    };
    try {
      root.localStorage.setItem(LASTRUN_KEY, JSON.stringify(lastRun));
    } catch (e) { /* storage full or disabled; keep the in-memory value */ }
    return lastRun;
  }

  /* Snapshot of the workspace before a prompt, so the run record can name the
   * files it touched and the bytes it actually wrote rather than guessing. */
  function runSnapshot() {
    const p = activeProject();
    const map = (p && p.files) || files || {};
    return {
      files: Object.assign({}, map),
      bytes: Object.keys(map).reduce(function (n, k) { return n + bytesOf(map[k]); }, 0),
    };
  }

  function contextStoredBytes() {
    const C = contextModule();
    if (!C || !C.report) return null;
    try {
      const report = C.report(contextScope());
      return report && typeof report.stored === "number" ? report.stored : null;
    } catch (e) {
      return null;
    }
  }

  /* ------------------------------------------------------------- context -- */
  /* Working memory is deliberately small and printable: the last result, the
   * last plan, the active spec, one summary + hash per file, and a rolling
   * session list. Every entry is scoped by project slug in localStorage and is
   * never included in a network request. */
  function contextModule() { return root.toolrxContext || null; }

  function contextScope() { return projects.active || "scratch"; }

  function firstMeaningfulLine(text) {
    const lines = String(text == null ? "" : text).split(/\n/);
    for (const raw of lines) {
      let line = raw.trim();
      if (!line) continue;
      line = line.replace(/^\/\*+\s*/, "").replace(/\s*\*\/\s*$/, "")
        .replace(/^#+\s*/, "").replace(/^\/\/\s*/, "").trim();
      if (line) return line.length > 80 ? line.slice(0, 77) + "…" : line;
    }
    return "empty";
  }

  function fileSummary(name, text) {
    const C = contextModule();
    const body = String(text == null ? "" : text);
    const bytes = C ? C.byteLength(body) : body.length;
    const lines = body ? body.split("\n").length : 0;
    const hash = root.blake2bHex
      ? root.blake2bHex(body, null, 8)
      : (C ? C.fingerprint(body) : String(bytes));
    return name + " · " + bytes + " bytes · " + lines + " lines · sha " + hash
      + " · " + firstMeaningfulLine(body);
  }

  function captureProjectContext(p, force) {
    const C = contextModule();
    if (!C || !p) return;
    if (!force && p.slug !== projects.active) return;
    const t = root.toolrxTemplates;
    if (p.spec) {
      const line = t && t.specLine ? t.specLine(p.spec) : C.stable(p.spec);
      C.set(p.slug, "spec", "active", line);
    } else {
      C.remove(p.slug, "spec", "active");
    }
    const fileMap = p.files || {};
    const items = Object.keys(fileMap).sort().map(function (name) {
      return { kind: "file", key: name, text: fileSummary(name, fileMap[name]) };
    });
    C.setMany(p.slug, items, { kind: "file" });
  }

  function setEditContext(slug, record) {
    const C = contextModule();
    if (!C) return;
    C.set(slug, "edit", "last", C.stable(record || {}));
  }

  function isContextMeta(via) {
    return /^context\.(?:show|clear|clear\.all|expand|continue)$/.test(String(via || ""));
  }

  function notePromptContext(query, results) {
    const C = contextModule();
    if (!C) return;
    const slug = contextScope();
    const list = Array.isArray(results) ? results : [];
    const last = list.filter(function (r) { return r && r.text; }).slice(-1)[0] || null;
    const via = last ? String(last.via || "") : "";
    const quiet = /^context\.(?:show|clear|clear\.all)$/.test(via);

    if (last && !quiet) {
      const head = "query: " + String(query).replace(/\s+/g, " ").slice(0, 240)
        + "\nvia: " + (last.via || "router");
      C.set(slug, "result", "last", head + "\n" + last.text);
      // The rolling session keeps the last dozen steps, newest at the bottom.
      if (!isContextMeta(via)) {
        const previous = C.get(slug, "session", "rolling");
        const rows = previous ? previous.split("\n").filter(Boolean) : [];
        list.forEach(function (r) {
          const mark = r.error ? "✗" : "✓";
          rows.push(mark + " " + String(r.step || "").replace(/\s+/g, " ").slice(0, 160));
        });
        C.set(slug, "session", "rolling", rows.slice(-12).join("\n"));
      }
    }

    const skills = root.toolrxSkills;
    const preview = skills && skills.planPreview
      ? skills.planPreview(query, { stepMs: stepTimeout(), planMs: planTimeout() })
      : null;
    if (preview && !preview.blocked && preview.plan && !isContextMeta(via)) {
      const plan = {
        version: 1,
        steps: preview.steps.map(function (s) { return s.text; }),
        status: preview.steps.map(function (_, i) {
          const r = list[i];
          return r ? (r.error ? "error" : "done") : "pending";
        }),
      };
      C.set(slug, "plan", "last", C.stable(plan));
    }
  }

  function planNote(slug) {
    const C = contextModule();
    if (!C || !C.notes) return null;
    return C.notes(slug).filter(function (note) {
      return note.kind === "plan" && note.key === "last";
    })[0] || null;
  }

  function planIssue(note) {
    return { issue: note || {
      kind: "plan", key: "last", bytes: 0, why: "trimmed",
    } };
  }

  function readLastPlan(slug) {
    const C = contextModule();
    if (!C) return null;
    const raw = C.get(slug, "plan", "last");
    if (!raw) {
      const note = planNote(slug);
      return note ? planIssue(note) : null;
    }
    try {
      const plan = JSON.parse(raw);
      if (!plan || !Array.isArray(plan.steps)) {
        return planIssue(planNote(slug));
      }
      plan.status = Array.isArray(plan.status) ? plan.status : [];
      plan.steps.forEach(function (_, i) {
        if (plan.status[i] !== "done" && plan.status[i] !== "error"
            && plan.status[i] !== "pending") plan.status[i] = "pending";
      });
      return plan;
    } catch (e) {
      return planIssue(planNote(slug));
    }
  }

  function planIssueText(plan, action) {
    const why = plan.issue.why === "trimmed" ? "trimmed" : "evicted";
    return "the stored plan was " + why + " from context ("
      + plan.issue.bytes + " bytes) · rebuild the plan, then " + action;
  }

  function planLines(plan) {
    return plan.steps.map(function (step, i) {
      const status = plan.status[i] || "pending";
      const mark = status === "done" ? "✓" : (status === "error" ? "✗" : "·");
      return (i + 1) + ". " + mark + " " + step;
    });
  }

  function contextShow() {
    const C = contextModule();
    if (!C) return "context is unavailable in this browser";
    return C.report(contextScope()).text;
  }

  function contextRaw() {
    const C = contextModule();
    return C ? C.raw(contextScope()) : "";
  }

  function contextSnapshot() {
    const C = contextModule();
    if (!C) return "context is unavailable in this browser";
    return C.snapshot(contextScope()).text;
  }

  function contextDiff() {
    const C = contextModule();
    if (!C) return "context is unavailable in this browser";
    return C.diff(contextScope()).text;
  }

  function contextClear(all) {
    const C = contextModule();
    if (!C) return "context is unavailable in this browser";
    if (all) {
      const n = C.clearAll();
      return "cleared context for " + n + " project" + (n === 1 ? "" : "s")
        + "\nmemory notes and chat history are separate";
    }
    const slug = contextScope();
    C.clear(slug);
    return "context cleared · project: " + slug
      + "\nmemory notes and chat history are separate";
  }

  async function contextContinue() {
    const C = contextModule();
    const slug = contextScope();
    const skills = root.toolrxSkills;
    if (!C || !skills) return "context is unavailable in this browser";
    const plan = readLastPlan(slug);
    if (!plan) {
      return "no previous plan in context · build a multi-step plan first, "
        + "then say what is in context";
    }
    if (plan.issue) return planIssueText(plan, "continue");
    const indexes = plan.status.map(function (status, i) {
      return status === "pending" ? i : -1;
    }).filter(function (i) { return i >= 0; });
    if (!indexes.length) {
      const errors = plan.status.filter(function (s) { return s === "error"; }).length;
      return "nothing left to continue · " + plan.steps.length + "/"
        + plan.steps.length + " steps resolved"
        + (errors ? " (" + errors + " error" + (errors === 1 ? "" : "s") + ")" : "");
    }
    const steps = indexes.map(function (i) { return plan.steps[i]; });
    const results = await skills.runPrompt(steps.join("\n"), promptContext());
    results.forEach(function (r, i) {
      plan.status[indexes[i]] = r.error ? "error" : "done";
    });
    C.set(slug, "plan", "last", C.stable(plan));
    const prior = C.get(slug, "session", "rolling");
    const rows = prior ? prior.split("\n").filter(Boolean) : [];
    results.forEach(function (r) {
      rows.push((r.error ? "✗ " : "✓ ") + String(r.step || "").slice(0, 160));
    });
    C.set(slug, "session", "rolling", rows.slice(-12).join("\n"));
    const remaining = plan.status.filter(function (s) { return s !== "done"; }).length;
    const lines = ["continued the last plan · " + results.length + " step"
      + (results.length === 1 ? "" : "s") + " run · " + remaining + " still pending"];
    results.forEach(function (r) {
      lines.push("", r.step, r.text || "");
    });
    return lines.join("\n").trim();
  }

  function contextExpand(more) {
    const C = contextModule();
    const slug = contextScope();
    const skills = root.toolrxSkills;
    if (!C || !skills) return "context is unavailable in this browser";
    const plan = readLastPlan(slug);
    if (!plan) {
      return "no last plan to expand · build a multi-step plan first, "
        + "then say expand the last plan with …";
    }
    if (plan.issue) return planIssueText(plan, "expand");
    const text = String(more || "").trim();
    if (!text) return "nothing to add · say expand the last plan with <steps>";
    const info = skills.splitPromptInfo(text);
    const maxSteps = (skills.limits && skills.limits.steps) || 40;
    if (info.overLimit || plan.steps.length + info.steps.length > maxSteps) {
      return "not expanded · the plan would exceed " + maxSteps + " steps";
    }
    info.steps.forEach(function (step) {
      plan.steps.push(step);
      plan.status.push("pending");
    });
    C.set(slug, "plan", "last", C.stable(plan));
    return ["expanded the last plan · " + info.steps.length + " new step"
      + (info.steps.length === 1 ? "" : "s") + " · " + plan.steps.length + " total"]
      .concat(planLines(plan))
      .concat(["", "say continue from previous to run the pending steps"])
      .join("\n");
  }

  /* Apply the last recorded patch or bundle to every other project. Each
   * project is all-or-none and gets its own undo entry; incompatible projects
   * are reported instead of being rewritten. */
  function applyIdsToProject(p, ids, arg) {
    const P = root.toolrxPatches;
    if (!P) return { ok: false, message: "edit patches are not loaded" };
    let files = copyFiles(p.files);
    let spec = p.spec ? JSON.parse(JSON.stringify(p.spec)) : null;
    let edits = (p.edits || []).slice();
    const labels = [];
    for (const id of ids) {
      const res = P.apply(id, {
        kind: p.kind, desc: p.desc, files: copyFiles(files),
        spec: JSON.parse(JSON.stringify(spec || null)), edits: edits.slice(),
      }, { arg: arg });
      if (!res.ok) {
        return { ok: false, message: res.message, id: id, labels: labels };
      }
      files = res.files;
      spec = res.spec;
      edits = res.edits;
      labels.push(res.label);
    }
    return { ok: true, files: files, spec: spec, edits: edits, labels: labels };
  }

  function contextApplyOthers() {
    const C = contextModule();
    const slug = contextScope();
    if (!C) return "context is unavailable in this browser";
    const raw = C.get(slug, "edit", "last");
    if (!raw) {
      return "no recent edit in this project's context · apply an edit first";
    }
    let record;
    try { record = JSON.parse(raw); } catch (e) { record = null; }
    const ids = record && Array.isArray(record.ids) ? record.ids : [];
    if (!ids.length) return "the last edit is not replayable";
    const others = Object.keys(projects.items).sort().filter(function (k) {
      return k !== slug;
    });
    if (!others.length) {
      return "no other projects to apply the changes to · build a second project first";
    }
    const done = [], failed = [];
    others.forEach(function (key) {
      const p = projects.items[key];
      const res = applyIdsToProject(p, ids, record.arg || "");
      if (!res.ok) {
        failed.push(key + ": " + res.message);
        return;
      }
      const budget = budgetCheck(res.files);
      if (!budget.ok) {
        failed.push(key + ": " + budget.why);
        return;
      }
      pushProjectHistory(p, "same changes: " + res.labels.join(" + "));
      p.files = res.files;
      p.spec = res.spec;
      p.edits = res.edits;
      p.bundled = bundleProject(p);
      p.updated = Date.now();
      writeProjectFiles(p);
      captureProjectContext(p, true);
      done.push(key + " (" + res.labels.join(" + ") + ")");
    });
    writeProjects();
    const lines = ["applied the last edit to " + done.length + " other project"
      + (done.length === 1 ? "" : "s") + " · " + (record.labels || ids).join(" + ")];
    if (done.length) lines.push("changed: " + done.join(" · "));
    if (failed.length) lines.push("not changed: " + failed.join(" · "));
    return lines.join("\n");
  }


  function buildPage(kind, desc) {
    const t = root.toolrxTemplates;
    if (!t) throw new Error("build templates are not loaded");
    if (t.project) return buildProject(kind, desc);
    const theme = preview.theme === "light" ? "light" : "dark";
    const html = t.build(kind, desc, { theme: theme });
    preview = {
      html: html, kind: String(kind || "playground"), desc: String(desc || ""),
      title: t.title(kind, desc), theme: theme, at: Date.now(),
    };
    files["site/index.html"] = html;
    writeFS(files);
    notifyPreview();
    remember("last_build", {
      title: preview.title, kind: preview.kind, desc: preview.desc,
      slug: "site", theme: theme, at: Date.now(),
    });
    return 'built "' + preview.title + '" → site/index.html\npreview updated · the page runs offline';
  }

  function setTheme(name) {
    const theme = name === "light" ? "light" : "dark";
    const t = root.toolrxTemplates;
    // A real project owns its own files: change the theme class in place so an
    // edited title, added toggle, or footer note survives the switch.
    const project = activeProject();
    if (project && project.files && project.files["index.html"]) {
      return !!setProjectTheme(project.slug, theme);
    }
    if (!t) return false;
    if (!preview.kind) {
      preview.html = t.build("welcome", "", { theme: theme });
      preview.kind = "welcome";
      preview.title = "Preview ready";
      preview.theme = theme;
      preview.at = Date.now();
      notifyPreview();
      return true;
    }
    preview.theme = theme;
    preview.html = t.build(preview.kind, preview.desc, { theme: theme });
    preview.at = Date.now();
    files["site/index.html"] = preview.html;
    writeFS(files);
    notifyPreview();
    return true;
  }

  function defaultPreview() {
    if (preview.html) return preview.html;
    // A reloaded page has no preview state, but the active project is still in
    // localStorage. Resume it instead of showing the welcome page over it.
    const p = activeProject();
    if (p && p.files && p.files["index.html"]) {
      const html = bundleProject(p) || p.bundled;
      if (html) {
        preview = {
          html: html, kind: p.kind, desc: p.desc, title: p.name,
          theme: htmlTheme(p.files["index.html"]), at: Date.now(),
        };
        notifyPreview();
        return preview.html;
      }
    }
    const t = root.toolrxTemplates;
    if (!t) return "";
    preview.html = t.build("welcome", "", { theme: preview.theme });
    preview.kind = "welcome";
    preview.title = "Preview ready";
    preview.at = Date.now();
    notifyPreview();
    return preview.html;
  }

  /* --------------------------------------------------------- web access ---- */
  /* Only CORS-enabled, key-free endpoints: Wikipedia, DuckDuckGo instant
   * answers, dictionaryapi.dev, and Open-Meteo. Failure is reported honestly
   * instead of being papered over. */
  function fetchJSON(url) {
    return fetch(url, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  function sentences(text, n) {
    const parts = String(text || "").replace(/\s+/g, " ").match(/[^.!?]+[.!?]+/g) || [String(text || "")];
    return parts.slice(0, n || 3).join(" ").trim();
  }

  async function webSearch(q) {
    const query = String(q || "").trim();
    if (!query) throw new Error("nothing to search for");
    const u = "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch="
      + encodeURIComponent(query) + "&srlimit=3&format=json&origin=*";
    const d = await fetchJSON(u);
    const hits = (d.query && d.query.search) || [];
    if (!hits.length) throw new Error('no Wikipedia results for "' + query + '"');
    const first = hits[0];
    const sum = await fetchJSON("https://en.wikipedia.org/api/rest_v1/page/summary/"
      + encodeURIComponent(first.title));
    const extract = sum.extract || (first.snippet || "").replace(/<[^>]+>/g, "");
    const lines = [
      sum.title || first.title,
      "",
      sentences(extract, 4),
      "",
      "source: " + (sum.content_urls && sum.content_urls.desktop && sum.content_urls.desktop.page
        || "https://en.wikipedia.org/wiki/" + encodeURIComponent(first.title)),
    ];
    if (hits.length > 1) {
      lines.push("also: " + hits.slice(1).map(function (h) { return h.title; }).join(" · "));
    }
    return { text: lines.join("\n"), source: (sum.content_urls && sum.content_urls.desktop && sum.content_urls.desktop.page) || "", title: sum.title || first.title };
  }

  async function webDefine(word) {
    const w = String(word || "").trim().replace(/[^a-zA-Z' -]/g, "");
    if (!w) throw new Error("which word?");
    const d = await fetchJSON("https://api.dictionaryapi.dev/api/v2/entries/en/" + encodeURIComponent(w));
    const entry = Array.isArray(d) ? d[0] : d;
    if (!entry) throw new Error('no definition for "' + w + '"');
    const lines = [(entry.word || w) + (entry.phonetic ? "  " + entry.phonetic : "")];
    (entry.meanings || []).slice(0, 2).forEach(function (m) {
      lines.push("", m.partOfSpeech + ":");
      (m.definitions || []).slice(0, 2).forEach(function (def) { lines.push("  - " + def.definition); });
    });
    return { text: lines.join("\n"), source: "https://dictionaryapi.dev/", title: entry.word || w };
  }

  async function webWeather(place) {
    const p = String(place || "").trim();
    if (!p) throw new Error("which place?");
    const geo = await fetchJSON("https://geocoding-api.open-meteo.com/v1/search?name="
      + encodeURIComponent(p) + "&count=1&language=en&format=json");
    const hit = geo.results && geo.results[0];
    if (!hit) throw new Error('could not find "' + p + '"');
    const f = await fetchJSON("https://api.open-meteo.com/v1/forecast?latitude=" + hit.latitude
      + "&longitude=" + hit.longitude
      + "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&timezone=auto");
    const c = f.current || {};
    const codes = { 0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers", 95: "thunderstorm" };
    return {
      text: hit.name + (hit.country ? ", " + hit.country : "") + "\n"
        + c.temperature_2m + "°C · " + (codes[c.weather_code] || "weather code " + c.weather_code) + "\n"
        + "humidity " + c.relative_humidity_2m + "% · wind " + c.wind_speed_10m + " km/h\n"
        + "source: Open-Meteo (" + (f.timezone || "local") + ")",
      source: "https://open-meteo.com/", title: hit.name,
    };
  }

  async function webAnswer(q) {
    const u = "https://api.duckduckgo.com/?q=" + encodeURIComponent(q)
      + "&format=json&no_html=1&skip_disambig=1";
    const d = await fetchJSON(u);
    if (d.AbstractText) {
      return { text: d.Heading + "\n\n" + d.AbstractText + "\n\nsource: " + (d.AbstractURL || "DuckDuckGo"), source: d.AbstractURL || "", title: d.Heading };
    }
    // fall back to the top related topic
    const rel = (d.RelatedTopics || []).filter(function (r) { return r.Text; })[0];
    if (rel) return { text: rel.Text + "\n\nsource: " + (rel.FirstURL || "DuckDuckGo"), source: rel.FirstURL || "", title: q };
    throw new Error("no instant answer for \"" + q + "\" — try: wikipedia " + q);
  }

  /* --------------------------------------------------------- project ctx --- */
  function projectContext() {
    return {
      new: function (name) {
        const p = newProject(name);
        return "created project " + p.slug + " · " + p.name + "\ntry: build a todo app (it will land in the active project)";
      },
      list: function () {
        const list = projectList();
        if (!list.length) return "no projects yet — build something or say: new project notes";
        return list.map(function (p) {
          return (p.active ? "* " : "  ") + p.slug + "  ·  " + p.name + "  ·  "
            + p.files.length + " files  ·  " + p.kind;
        }).join("\n") + "\n\n* = active";
      },
      open: function (slug) { return openProject(slug); },
      rename: function (slug, name) { return renameProject(slug, name); },
      remove: function (slug) { return deleteProject(slug); },
      title: function (slug, name) { return editProjectTitle(slug, name); },
      theme: function (slug, name) { return setProjectTheme(slug, name); },
      themeToggle: function (slug) { return addThemeToggle(slug); },
      note: function (slug, text) { return addFooterNote(slug, text); },
      files: function (slug) {
        const p = findProject(slug);
        if (!p) return "no active project — build something first";
        const names = filesForProject(p);
        return p.name + " (" + p.slug + ")\n" + names.map(function (n) {
          return "  " + n + "  ·  " + String(p.files[n] || "").length + " chars";
        }).join("\n");
      },
      exportBundle: function (ref) { return exportProjectBundle(ref); },
      importBundle: function (name) { return importProjectNamed(name); },
      exportWorkspace: function () { return exportWorkspaceBundle(); },
      importWorkspace: function (name) { return importWorkspaceNamed(name); },
      bundles: function () { return bundleList(); },
      active: function () { return activeProject(); },
    };
  }

  function promptContext() {
    const ctx = {
      prev: "",
      fs: {
        exists: function (p) { try { return normPath(p) in files; } catch (e) { return false; } },
        read: function (p) { return readFile(p); },
        write: function (p, content) { return edit(p, content); },
        list: function (p) { return listDir(p); },
      },
      preview: function () { return defaultPreview(); },
      theme: function (name) { return setTheme(name); },
      build: function (kind, desc) { return buildPage(kind, desc); },
      edit: function (patch, arg) { return applyProjectEdit(patch, arg); },
      editMany: function (list) { return applyProjectEdits(list); },
      grow: function (which, name) { return growActiveProject(which, name); },
      growSystems: function (list) { return growActiveSystems(list); },
      contextShow: contextShow,
      contextRaw: contextRaw,
      contextSnapshot: contextSnapshot,
      contextDiff: contextDiff,
      contextClear: contextClear,
      contextContinue: contextContinue,
      contextExpand: contextExpand,
      contextApplyOthers: contextApplyOthers,
      undo: function () { return undoProjectEdit(); },
      llmStatus: llmStatus,
      llmEnable: llmEnable,
      llmCacheClear: llmCacheClear,
      llmPlan: llmPlan,
      llmPatch: llmPatch,
      llmApply: llmApply,
      llmDiscard: llmDiscard,
      webPage: function (info) { return buildWebPage(info); },
      architecture: function (kind, desc) {
        const t = root.toolrxTemplates;
        if (!t || !t.architecture) throw new Error("templates are not loaded");
        const html = t.architecture(kind, desc, { theme: preview.theme });
        const real = t.canonical(kind, desc);
        const slug = "plan-" + slugify(real);
        const p = newProject(slug);
        p.kind = real; p.desc = String(desc || "");
        p.files = { "index.html": html };
        p.bundled = html;
        p.updated = Date.now();
        projects.active = p.slug;
        writeProjects();
        writeProjectFiles(p);
        preview = { html: html, kind: real, desc: String(desc || ""), title: "Architecture · " + p.name, theme: preview.theme, at: Date.now() };
        notifyPreview();
        return 'architecture brief for "' + p.name + '" → projects/' + p.slug + "/index.html\n"
          + "it lists files, state, modules, data flow, build order, and extension points\n"
          + "say \"build it\" to get the working starter";
      },
      blueprint: function (kind, desc) {
        const t = root.toolrxTemplates;
        if (!t || !t.brief) throw new Error("templates are not loaded");
        return t.brief(kind, desc);
      },
      project: projectContext(),
      chat: function (who, text) { return chatAppend(who, text); },
      history: function () { return chatHistory(); },
      memory: {
        get: function (k) { return memory[k]; },
        set: function (k, v) { return remember(k, v); },
        remove: function (k) { return forgetKey(k); },
        clear: function () { return clearMemory(); },
        keys: function () { return Object.keys(memory); },
      },
      web: {
        search: webSearch,
        define: webDefine,
        weather: webWeather,
        answer: webAnswer,
      },
      limits: {
        stepMs: stepTimeout(),
        planMs: planTimeout(),
        chars: planLimits().chars,
        steps: planLimits().steps,
      },
    };
    ctx.fallback = async function (step) {
      const decision = rt.route(step, model, []);
      const res = await execute(decision.tool, decision.args);
      const text = res.ok ? res.text
        : "blocked: " + (res.reason || "not available in the browser");
      // Conversation wins when the router is not confident: a greeting or a
      // reflection should sound like a reply, not a mis-filed tool call.
      if (decision.confidence < 0.46 && root.toolrxSkills && root.toolrxSkills.chat) {
        const reply = root.toolrxSkills.chat(step, ctx);
        if (reply) {
          return { text: reply, via: "chat", confidence: decision.confidence };
        }
      }
      return {
        text: text, error: !res.ok, via: "router." + decision.tool,
        tool: decision.tool, confidence: decision.confidence,
        margin: decision.margin, args: decision.args,
      };
    };
    return ctx;
  }

  function now() {
    return (root.performance && performance.now) ? performance.now() : Date.now();
  }

  function readFS() {
    try {
      const raw = root.localStorage.getItem(FS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.files === "object") return parsed.files;
      }
    } catch (e) { /* private mode / disabled storage */ }
    return Object.assign({}, SEED);
  }

  function writeFS(files) {
    try { root.localStorage.setItem(FS_KEY, JSON.stringify({ files: files })); }
    catch (e) { /* storage full or disabled; workspace stays in memory */ }
  }

  let files = readFS();

  function normPath(p) {
    if (p === null || p === undefined || p === "") return ".";
    let s = String(p).trim().replace(/^["']+|["']+$/g, "").replace(/\\/g, "/");
    const parts = s.split("/").filter(function (x) { return x && x !== "."; });
    const out = [];
    for (const part of parts) {
      if (part === "..") {
        if (!out.length) throw new Error("path escapes the sandbox: " + p);
        out.pop();
      } else {
        out.push(part);
      }
    }
    return out.join("/") || ".";
  }

  function isDir(p) {
    if (p === ".") return true;
    const prefix = p + "/";
    for (const f in files) if (f.indexOf(prefix) === 0) return true;
    return false;
  }

  function sizeOf(text) {
    return new TextEncoder().encode(text).length;
  }

  function humanSize(n) {
    if (n < 1024) return n + " B";
    return (n / 1024).toFixed(1) + " KB";
  }

  function listDir(path) {
    const p = normPath(path);
    if (!isDir(p)) throw new Error("not a directory: " + p);
    const prefix = p === "." ? "" : p + "/";
    const entries = new Set();
    for (const f in files) {
      if (f.indexOf(prefix) !== 0) continue;
      const rest = f.slice(prefix.length);
      const slash = rest.indexOf("/");
      entries.add(slash === -1 ? rest : rest.slice(0, slash) + "/");
    }
    if (!entries.size) return "(empty)";
    return Array.from(entries).sort().join("\n");
  }

  function readFile(path) {
    const p = normPath(path);
    if (!(p in files)) throw new Error("no such file: " + p);
    let text = files[p];
    if (text.length > MAX_FILE) text = text.slice(0, MAX_FILE) + "\n...[truncated]";
    return text;
  }

  function catAll() {
    const names = Object.keys(files).sort();
    let out = "";
    for (const name of names) {
      let text = files[name];
      if (text.length > MAX_FILE) text = text.slice(0, MAX_FILE) + "\n...[truncated]";
      out += "===== " + name + " =====\n" + text + "\n";
      if (out.length > MAX_TOTAL) { out += "...[truncated]\n"; break; }
    }
    return out || "(workspace is empty)";
  }

  function inspect(path) {
    const p = normPath(path);
    if (isDir(p) && p !== "." && !(p in files)) {
      const entries = listDir(p).split("\n");
      return "type: directory\npath: " + p + "\nentries: " + entries.length;
    }
    if (!(p in files)) throw new Error("no such file or directory: " + p);
    const text = files[p];
    return [
      "type: file",
      "path: " + p,
      "bytes: " + sizeOf(text),
      "lines: " + (text.match(/\n/g) || []).length + 1,
      "chars: " + text.length,
    ].join("\n");
  }

  function edit(path, content, mode) {
    const p = normPath(path);
    if (isDir(p) && p !== "." && !(p in files)) throw new Error("is a directory: " + p);
    const before = files[p];
    const text = content === undefined || content === null ? "" : String(content);
    if (mode === "append") files[p] = (before || "") + text;
    else if (mode === "create" && before !== undefined) throw new Error("already exists: " + p);
    else files[p] = text;
    writeFS(files);
    return (mode === "append" ? "appended to " : "wrote ") + p + " (" + sizeOf(files[p]) + " bytes)";
  }

  /* ---- a small line diff for config.diff ---- */
  function diffLines(a, b) {
    const A = a.split("\n"), B = b.split("\n");
    const m = A.length, n = B.length;
    const dp = Array.from({ length: m + 1 }, function () { return new Uint16Array(n + 1); });
    for (let i = m - 1; i >= 0; i--) {
      for (let j = n - 1; j >= 0; j--) {
        dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    const out = [];
    let i = 0, j = 0;
    while (i < m && j < n) {
      if (A[i] === B[j]) { out.push("  " + A[i]); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push("- " + A[i]); i++; }
      else { out.push("+ " + B[j]); j++; }
    }
    while (i < m) { out.push("- " + A[i]); i++; }
    while (j < n) { out.push("+ " + B[j]); j++; }
    const changed = out.filter(function (l) { return l[0] !== " "; }).length;
    return changed ? out.join("\n") : "(identical)";
  }

  function diff(pathA, pathB) {
    const a = readFile(pathA), b = readFile(pathB);
    return "--- " + normPath(pathA) + "\n+++ " + normPath(pathB) + "\n" + diffLines(a, b);
  }

  /* ---- host tools that map onto browser APIs ---- */
  async function memStatus() {
    const lines = [];
    const total = root.navigator && navigator.deviceMemory;
    if (total) lines.push("device memory: ~" + total + " GB (coarse, browser-provided)");
    const perf = root.performance;
    if (perf && perf.memory) {
      const mb = function (x) { return Math.round(x / 1048576) + " MB"; };
      lines.push("JS heap used: " + mb(perf.memory.usedJSHeapSize));
      lines.push("JS heap total: " + mb(perf.memory.totalJSHeapSize));
      lines.push("JS heap limit: " + mb(perf.memory.jsHeapSizeLimit));
    }
    if (!lines.length) lines.push("this browser does not expose memory figures");
    return lines.join("\n");
  }

  async function disk() {
    if (root.navigator && navigator.storage && navigator.storage.estimate) {
      try {
        const est = await navigator.storage.estimate();
        const mb = function (x) { return (x / 1048576).toFixed(1) + " MB"; };
        return [
          "origin: " + (root.location ? location.origin : "unknown"),
          "quota: " + mb(est.quota || 0),
          "usage: " + mb(est.usage || 0),
          "workspace files: " + Object.keys(files).length,
        ].join("\n");
      } catch (e) { /* fall through */ }
    }
    return "storage estimate unavailable in this browser";
  }

  function ifconfig() {
    const lines = ["online: " + (root.navigator ? navigator.onLine : "unknown")];
    const c = root.navigator && (navigator.connection || navigator.mozConnection);
    if (c) {
      if (c.effectiveType) lines.push("effective type: " + c.effectiveType);
      if (c.downlink) lines.push("downlink: ~" + c.downlink + " Mbps");
      if (c.rtt) lines.push("rtt: ~" + c.rtt + " ms");
    }
    lines.push("address: not exposed to web pages");
    return lines.join("\n");
  }

  function uptime() {
    const s = Math.round(now() / 1000);
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    return "page uptime: " + (d ? d + "d " : "") + h + "h " + m + "m " + (s % 60) + "s";
  }

  /* ---- executor ---- */
  const EXEC = {
    "math.sum": function (args) {
      const terms = Array.isArray(args.terms) ? args.terms : [];
      if (!terms.length) throw new Error("no integers found in the query");
      const total = terms.reduce(function (a, b) { return a + b; }, 0);
      return terms.join(" + ") + " = " + total;
    },
    "fs.read_file": function (args) { return readFile(args.path); },
    "fs.list_dir": function (args) { return listDir(args.path); },
    "fs.cat_all": function () { return catAll(); },
    "fs.inspect_dir": function (args) { return inspect(args.file || args.path); },
    "file.edit": function (args) { return edit(args.path, args.content, args.mode); },
    "config.diff": function (args) { return diff(args.path_a, args.path_b); },
    "sys.mem_status": memStatus,
    "sys.disk": disk,
    "sys.uptime": uptime,
    "sys.ifconfig": ifconfig,
    "sys.processes": function () {
      return "a browser tab has no process table. Run `python3 toolrx/server.py` for real process data.";
    },
    "sys.netstat": function () {
      return "a browser tab cannot open sockets. Run the local server for /proc/net/tcp.";
    },
    "net.ping": function (args) {
      throw new Error("ICMP needs a real socket; this tool only runs against the local server (host: "
        + (args.host || "?") + ")");
    },
  };

  const UNAVAILABLE = {
    "module.start": "scheduled modules need the local server",
    "module.run": "scheduled modules need the local server",
    "module.stop": "scheduled modules need the local server",
    "module.clear": "scheduled modules need the local server",
    "net.cfg_gen": "network config generation needs the local server",
    "net.cfg_check": "network config checks need the local server",
    "net.lab_state": "the multi-node lab needs the local server",
    "net.lab_push": "the multi-node lab needs the local server",
    "net.lab_apply": "the multi-node lab needs the local server",
    "net.lab_topo": "the multi-node lab needs the local server",
    "net.lab_topo_apply": "the multi-node lab needs the local server",
    "net.lab_link": "the multi-node lab needs the local server",
    "net.lab_down": "the multi-node lab needs the local server",
  };

  function execute(tool, args) {
    if (UNAVAILABLE[tool]) {
      return Promise.resolve({ ok: false, blocked: true, reason: UNAVAILABLE[tool] });
    }
    const fn = EXEC[tool];
    if (!fn) return Promise.resolve({ ok: false, blocked: true, reason: "no browser executor for " + tool });
    return Promise.resolve().then(function () { return fn(args || {}); })
      .then(function (text) { return { ok: true, text: String(text) }; })
      .catch(function (e) { return { ok: false, blocked: true, reason: String(e.message || e) }; });
  }

  const api = {
    ready: false,
    model: null,
    init: function (url) {
      rt = root.toolrxRouter;
      if (!rt) return Promise.resolve(false);
      return fetch(url, { cache: "force-cache" })
        .then(function (r) { if (!r.ok) throw new Error("model " + r.status); return r.json(); })
        .then(function (raw) {
          model = rt.load(raw);
          loadedAt = Date.now();
          api.ready = true;
          api.model = model;
          return true;
        })
        .catch(function () { api.ready = false; return false; });
    },
    run: async function (query) {
      if (!api.ready) return { blocked: true, reason: "router model not loaded" };
      const decision = rt.route(query, model, []);
      const res = await execute(decision.tool, decision.args);
      return {
        query: query,
        tool: decision.tool,
        confidence: decision.confidence,
        margin: decision.margin,
        scores: decision.scores,
        ranked: decision.ranked,
        args: decision.args,
        ok: !!res.ok,
        blocked: !!res.blocked,
        reason: res.reason || "",
        output: res.text || "",
        ms: decision.ms,
      };
    },
    /* Multi-step prompt: the deterministic command library runs first, and any
     * step it does not know falls back to the core hashed router. */
    prompt: async function (query) {
      const started = now();
      const before = runSnapshot();
      if (!api.ready) {
        return [{ step: String(query), text: "router model not loaded", error: true }];
      }
      const skills = root.toolrxSkills;
      if (!skills || !skills.count()) {
        const r = await api.run(query);
        const results = [{
          step: String(query),
          text: r.blocked ? r.reason : r.output,
          error: !!r.blocked,
          via: "router." + r.tool,
          tool: r.tool,
          confidence: r.confidence,
          margin: r.margin,
          ms: r.ms,
        }];
        recordRun(String(query), results, started, {
          beforeFiles: before.files, beforeBytes: before.bytes,
          contextBytes: contextStoredBytes(),
        });
        return results;
      }
      const results = await skills.runPrompt(String(query), promptContext());
      notePromptContext(String(query), results);
      recordRun(String(query), results, started, {
        beforeFiles: before.files, beforeBytes: before.bytes,
        contextBytes: contextStoredBytes(),
      });
      // Keep a lightweight transcript for the chat side of the harness.
      chatAppend("you", String(query));
      const said = results.map(function (r) { return r.text; }).filter(Boolean).join("\n");
      if (said) chatAppend("toolrx", said);
      return results;
    },
    files: function () { return Object.assign({}, files); },
    /* project management ------------------------------------------------ */
    projects: function () { return projectList(); },
    project: function (slug) {
      const p = slug ? findProject(slug) : activeProject();
      if (!p) return null;
      return {
        slug: p.slug, name: p.name, kind: p.kind, desc: p.desc,
        files: filesForProject(p), html: p.bundled || "",
        updated: p.updated, active: p.slug === projects.active,
      };
    },
    projectFile: function (slug, name) {
      const p = findProject(slug);
      if (!p) throw new Error("no such project: " + slug);
      const n = String(name || "").replace(/^\/+/, "");
      if (!(n in p.files)) throw new Error("no such file in project: " + n);
      return p.files[n];
    },
    writeProjectFile: function (slug, name, content) {
      return writeProjectFile(slug, name, content);
    },
    newProject: function (name) { const p = newProject(name); return p.slug; },
    openProject: function (slug) { return openProject(slug); },
    deleteProject: function (slug) { return deleteProject(slug); },
    exportProject: function (slug) { return exportProject(slug); },
    importProject: function (text) { return importProject(text); },
    exportWorkspace: function () { return exportWorkspace(); },
    importWorkspace: function (text) { return importWorkspace(text); },
    importBundle: function (text) { return importBundle(text); },
    exportProjectBundle: function (slug) { return exportProjectBundle(slug); },
    exportWorkspaceBundle: function () { return exportWorkspaceBundle(); },
    importProjectNamed: function (name) { return importProject(readBundle(name)); },
    importWorkspaceNamed: function (name) { return importWorkspace(readBundle(name)); },
    bundles: function () { return bundleList(); },
    renameProject: function (slug, name) { return renameProject(slug, name); },
    chatHistory: chatHistory,
    memory: function (k, v) { return remember(k, v); },
    context: function () {
      const C = contextModule();
      return C ? C.report(contextScope()) : null;
    },
    contextRaw: contextRaw,
    contextSnapshot: contextSnapshot,
    contextDiff: contextDiff,
    contextClear: contextClear,
    reset: function () {
      files = Object.assign({}, SEED);
      writeFS(files);
      projects = { active: "", items: {} };
      writeProjects();
      chatLog = [];
      writeChat();
      cancelPending = false;
      lastProgress = null;
      lastRun = null;
      try { root.localStorage.removeItem(LASTRUN_KEY); } catch (e) { /* ignore */ }
      try { root.localStorage.removeItem(MEMORY_KEY); } catch (e) { /* ignore */ }
      memory = {};
      const C = contextModule();
      if (C) C.clearAll();
    },
    loadedAt: function () { return loadedAt; },
    preview: snapshotPreview,
    defaultPreview: defaultPreview,
    theme: setTheme,
    onPreview: function (fn) {
      if (typeof fn === "function") previewListeners.push(fn);
      return function () {
        previewListeners = previewListeners.filter(function (x) { return x !== fn; });
      };
    },
    onProgress: function (fn) {
      if (typeof fn === "function") progressListeners.push(fn);
      return function () {
        progressListeners = progressListeners.filter(function (x) { return x !== fn; });
      };
    },
    progress: function () {
      return lastProgress ? Object.assign({}, lastProgress) : null;
    },
    lastRun: function () {
      return lastRun ? Object.assign({}, lastRun) : null;
    },
    cancelBuild: function () {
      cancelPending = true;
      return "build cancel requested — the previous project is kept";
    },
    limits: function () {
      const plan = planLimits();
      return {
        file: MAX_PROJECT_FILE, project: projectBudget(),
        files: MAX_PROJECT_FILES, timeout: buildTimeout(),
        readFile: MAX_FILE, readTotal: MAX_TOTAL,
        stepTimeout: plan.stepMs, planTimeout: plan.planMs,
        planChars: plan.chars, planSteps: plan.steps, block: plan.block,
      };
    },
    planPreview: function (query) {
      const skills = root.toolrxSkills;
      if (!skills || !skills.planPreview) return null;
      const preview = skills.planPreview(String(query), {
        stepMs: stepTimeout(), planMs: planTimeout(),
      });
      if (preview && preview.budget) {
        const p = activeProject();
        const usedFiles = p ? filesForProject(p).length : 0;
        const usedBytes = p ? projectBytes(p) : 0;
        preview.budget.project = {
          files: { used: usedFiles, max: MAX_PROJECT_FILES,
                   remaining: Math.max(0, MAX_PROJECT_FILES - usedFiles) },
          bytes: { used: usedBytes, max: projectBudget(),
                   remaining: Math.max(0, projectBudget() - usedBytes) },
        };
        preview.budget.fits = preview.budget.fits
          && usedFiles <= MAX_PROJECT_FILES && usedBytes <= projectBudget();
      }
      return preview;
    },
    report: function () { return lastRun ? lastRun.budget || null : null; },
    projectBytes: function (slug) {
      const p = slug === undefined ? activeProject() : findProject(slug);
      if (!p) return 0;
      return projectBytes(p);
    },
    budget: function (slug) {
      const p = slug === undefined ? activeProject() : findProject(slug);
      const total = p ? projectBytes(p) : 0;
      const budget = projectBudget();
      return { bytes: total, budget: budget, remaining: Math.max(0, budget - total),
        pct: budget ? Math.round((total / budget) * 100) : 0 };
    },
  };

  root.toolrxWeb = api;
})(typeof self !== "undefined" ? self : this);

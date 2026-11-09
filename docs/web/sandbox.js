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
  const MAX_FILE = 8000;
  const MAX_TOTAL = 24000;

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
    try {
      return Promise.resolve(fn(args || {})).then(function (text) {
        return { ok: true, text: String(text) };
      });
    } catch (e) {
      return Promise.resolve({ ok: false, blocked: true, reason: String(e.message || e) });
    }
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
    files: function () { return Object.assign({}, files); },
    reset: function () { files = Object.assign({}, SEED); writeFS(files); },
    loadedAt: function () { return loadedAt; },
  };

  root.toolrxWeb = api;
})(typeof self !== "undefined" ? self : this);

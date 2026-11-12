/* toolrx optional LLM adapter.
 *
 * Off by default. The deterministic parser and builders always run first; this
 * module is only reached when a prompt has no known genre (`playground`), the
 * user explicitly configured an OpenAI-compatible endpoint, and the user asked
 * for an LLM plan or patch. Nothing here is required for the rest of the app.
 *
 * Guarantees:
 * - no request unless `enabled` is true and an endpoint + model are saved
 * - HTTPS only, with HTTP allowed for localhost so people can use a local server
 * - strict JSON + schema validation; unknown keys are rejected
 * - every response is cached by normalized prompt and a content hash
 * - a session call budget, request timeout, and response-size cap
 * - the API key is stored in this browser only and never written to the cache,
 *   status text, or console
 *
 * Exposes: self.toolrxLlm = { config, configure, enable, status, plan, patch,
 *   applyDiff, pending, setPending, clearPending, clearCache, hash, ... }
 */
(function (root) {
  "use strict";

  var CONFIG_KEY = "toolrx.llm.config";
  var CACHE_KEY = "toolrx.llm.cache";
  var PENDING_KEY = "toolrx.llm.pending";
  var MAX_CACHE = 50;
  var MAX_DIFF = 40000;
  var MAX_SOURCE = 30000;
  var MAX_WHY = 200;

  var DEFAULTS = {
    enabled: false,
    endpoint: "",
    model: "",
    key: "",
    maxCalls: 8,
    timeoutMs: 20000,
    maxResponse: 65536,
  };

  var session = { calls: 0, lastError: "" };

  /* ------------------------------------------------------------ storage -- */
  function store() {
    try { return root.localStorage || null; } catch (e) { return null; }
  }

  function readJSON(key, fallback) {
    var s = store();
    if (!s) return fallback;
    try {
      var raw = s.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch (e) { return fallback; }
  }

  function writeJSON(key, value) {
    var s = store();
    if (!s) return false;
    try { s.setItem(key, JSON.stringify(value)); return true; }
    catch (e) { return false; }
  }

  function clamp(n, lo, hi, fallback) {
    n = Number(n);
    if (!isFinite(n)) return fallback;
    n = Math.round(n);
    return Math.max(lo, Math.min(hi, n));
  }

  /* -------------------------------------------------------------- hash --- */
  /* FNV-1a over a string. Used for cache keys and for proving a patch was
   * generated against the file contents it is being applied to. */
  function hash(text) {
    var s = String(text == null ? "" : text);
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return (h >>> 0).toString(16);
  }

  function normalizePrompt(text) {
    return String(text == null ? "" : text)
      .toLowerCase()
      .replace(/\s+/g, " ")
      .replace(/[\s.!?]+$/, "")
      .trim();
  }

  /* ------------------------------------------------------------- config -- */
  function config() {
    var saved = readJSON(CONFIG_KEY, {}) || {};
    var out = {};
    for (var k in DEFAULTS) out[k] = DEFAULTS[k];
    if (saved && typeof saved === "object") {
      for (var j in DEFAULTS) {
        if (Object.prototype.hasOwnProperty.call(saved, j)) out[j] = saved[j];
      }
    }
    out.enabled = !!out.enabled;
    out.endpoint = typeof out.endpoint === "string" ? out.endpoint : "";
    out.model = typeof out.model === "string" ? out.model : "";
    out.key = typeof out.key === "string" ? out.key : "";
    out.maxCalls = clamp(out.maxCalls, 1, 64, DEFAULTS.maxCalls);
    out.timeoutMs = clamp(out.timeoutMs, 20, 120000, DEFAULTS.timeoutMs);
    out.maxResponse = clamp(out.maxResponse, 1024, 1048576, DEFAULTS.maxResponse);
    return out;
  }

  function safeEndpoint(url) {
    var raw = String(url || "").trim();
    if (!raw) return "";
    var u;
    try { u = new URL(raw); } catch (e) { throw new Error("endpoint must be a full URL, e.g. https://api.example.com/v1/chat/completions"); }
    if (u.username || u.password) throw new Error("endpoint must not contain a username or password");
    if (u.protocol === "https:") return u.href;
    if (u.protocol !== "http:") throw new Error("endpoint must use https (http is only allowed for localhost)");
    if (!/^(localhost|127\.0\.0\.1|\[::1\]|::1)$/i.test(u.hostname)) {
      throw new Error("plain http is only allowed for localhost / 127.0.0.1 / ::1 — use https for remote endpoints");
    }
    return u.href;
  }

  function configure(patch) {
    var p = patch || {};
    var c = config();
    if (Object.prototype.hasOwnProperty.call(p, "endpoint")) {
      c.endpoint = safeEndpoint(p.endpoint);
    }
    if (Object.prototype.hasOwnProperty.call(p, "model")) {
      c.model = String(p.model == null ? "" : p.model).trim().slice(0, 120);
    }
    if (Object.prototype.hasOwnProperty.call(p, "key")) {
      // An empty string clears the saved key; the value never leaves localStorage
      // except in the Authorization header of a request the user asked for.
      c.key = String(p.key == null ? "" : p.key).trim();
    }
    if (Object.prototype.hasOwnProperty.call(p, "enabled")) c.enabled = !!p.enabled;
    if (p.maxCalls != null) c.maxCalls = clamp(p.maxCalls, 1, 64, c.maxCalls);
    if (p.timeoutMs != null) c.timeoutMs = clamp(p.timeoutMs, 20, 120000, c.timeoutMs);
    if (p.maxResponse != null) c.maxResponse = clamp(p.maxResponse, 1024, 1048576, c.maxResponse);
    if (c.enabled && (!c.endpoint || !c.model)) {
      throw new Error("save an endpoint and model before enabling the LLM");
    }
    if (!writeJSON(CONFIG_KEY, c)) throw new Error("could not save the LLM settings in this browser");
    return c;
  }

  function enable(on) {
    var c = config();
    if (on) {
      if (!c.endpoint) throw new Error("no endpoint saved — open Command Center → LLM and set one");
      if (!c.model) throw new Error("no model saved — open Command Center → LLM and set one");
      c.enabled = true;
    } else {
      c.enabled = false;
    }
    writeJSON(CONFIG_KEY, c);
    return statusText();
  }

  function hostOf(url) {
    try { return new URL(url).host; } catch (e) { return url ? "(invalid endpoint)" : ""; }
  }

  function status() {
    var c = config();
    var p = pending();
    return {
      enabled: c.enabled,
      configured: !!(c.endpoint && c.model),
      endpoint: c.endpoint ? hostOf(c.endpoint) : "",
      model: c.model || "",
      hasKey: !!c.key,
      calls: session.calls,
      maxCalls: c.maxCalls,
      cache: cacheSize(),
      maxCache: MAX_CACHE,
      pending: p ? { file: p.file, instruction: p.instruction || "" } : null,
      lastError: session.lastError || "",
    };
  }

  function statusText() {
    var s = status();
    var lines = ["llm · " + (s.enabled ? "on" : "off") + " · optional adapter"];
    if (s.configured) {
      lines.push("endpoint: " + s.endpoint + " · model: " + s.model + (s.hasKey ? " · key saved" : " · no key"));
    } else {
      lines.push("no endpoint/model saved — open Command Center → LLM, or keep using the deterministic parser");
    }
    lines.push("calls " + s.calls + "/" + s.maxCalls + " this session · cache " + s.cache + "/" + s.maxCache);
    if (s.pending) lines.push("pending patch: " + s.pending.file + " — say apply the llm patch or discard the llm patch");
    lines.push("deterministic commands never call the model; only llm plan / llm patch do");
    return lines.join("\n");
  }

  /* -------------------------------------------------------------- cache -- */
  function readCache() {
    var a = readJSON(CACHE_KEY, []);
    return Array.isArray(a) ? a : [];
  }

  function cacheSize() { return readCache().length; }

  function cacheGet(key) {
    var a = readCache();
    for (var i = a.length - 1; i >= 0; i--) {
      if (a[i] && a[i].k === key) return a[i].v || null;
    }
    return null;
  }

  function cachePut(key, value) {
    var a = readCache().filter(function (x) { return x && x.k !== key; });
    a.push({ k: key, v: value, at: Date.now() });
    writeJSON(CACHE_KEY, a.slice(-MAX_CACHE));
  }

  function clearCache() {
    writeJSON(CACHE_KEY, []);
    return "llm cache cleared — the next request starts from an empty cache";
  }

  /* ------------------------------------------------------------ pending -- */
  function pending() {
    var p = readJSON(PENDING_KEY, null);
    if (!p || typeof p !== "object" || !p.file || !p.diff) return null;
    return p;
  }

  function setPending(p) {
    if (!p) { clearPending(); return null; }
    writeJSON(PENDING_KEY, p);
    return p;
  }

  function clearPending() {
    var s = store();
    if (s) { try { s.removeItem(PENDING_KEY); } catch (e) { /* ignore */ } }
  }

  /* ------------------------------------------------------------- budget -- */
  function assertReady() {
    var c = config();
    if (!c.enabled) {
      throw new Error("the LLM is off (the default) — deterministic commands still work; open Command Center → LLM to enable it");
    }
    if (!c.endpoint) throw new Error("no LLM endpoint saved — open Command Center → LLM");
    if (!c.model) throw new Error("no LLM model saved — open Command Center → LLM");
    if (session.calls >= c.maxCalls) {
      throw new Error("LLM budget reached (" + c.maxCalls + " calls this session) — the deterministic parser still works");
    }
    return c;
  }

  /* ----------------------------------------------------------- transport -- */
  async function ask(system, user, c) {
    session.calls += 1;
    var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    var timer = null;
    if (ctrl) timer = setTimeout(function () { try { ctrl.abort(); } catch (e) { /* ignore */ } }, c.timeoutMs);
    var res, text;
    try {
      var headers = { "Content-Type": "application/json" };
      if (c.key) headers.Authorization = "Bearer " + c.key;
      res = await fetch(c.endpoint, {
        method: "POST",
        headers: headers,
        body: JSON.stringify({
          model: c.model,
          messages: [
            { role: "system", content: system },
            { role: "user", content: user },
          ],
          temperature: 0,
          max_tokens: 400,
          stream: false,
          response_format: { type: "json_object" },
        }),
        signal: ctrl ? ctrl.signal : undefined,
      });
      if (res && res.ok === false) {
        throw new Error("endpoint returned HTTP " + res.status);
      }
      var announced = res && res.headers && res.headers.get ? Number(res.headers.get("content-length")) : NaN;
      if (isFinite(announced) && announced > c.maxResponse) {
        throw new Error("endpoint response is too large (" + announced + " bytes; max " + c.maxResponse + ")");
      }
      text = await res.text();
      if (text.length > c.maxResponse) {
        throw new Error("endpoint response is too large (" + text.length + " chars; max " + c.maxResponse + ")");
      }
    } catch (e) {
      if (ctrl && ctrl.signal && ctrl.signal.aborted) {
        session.lastError = "LLM request timed out after " + c.timeoutMs + "ms";
        throw new Error(session.lastError);
      }
      var message = e && e.message ? e.message : String(e);
      if (e && (e.name === "TypeError" || /failed to fetch|load failed|networkerror/i.test(message))) {
        message += " — the endpoint must allow CORS from this page and be reachable from the browser";
      }
      session.lastError = message;
      throw new Error(message);
    } finally {
      if (timer) clearTimeout(timer);
    }

    var envelope;
    try { envelope = JSON.parse(text); }
    catch (e) { throw new Error("endpoint returned an invalid JSON envelope"); }
    if (envelope && envelope.error) {
      var msg = typeof envelope.error === "string" ? envelope.error : (envelope.error.message || "unknown error");
      throw new Error("endpoint error: " + String(msg).slice(0, 160));
    }
    var content = null;
    if (envelope && Array.isArray(envelope.choices) && envelope.choices[0]) {
      var ch = envelope.choices[0];
      content = ch.message && ch.message.content;
      if (Array.isArray(content)) {
        content = content.map(function (part) { return part && part.text ? part.text : ""; }).join("");
      }
      if (content == null) content = ch.text;
    }
    if (typeof content !== "string" || !content.trim()) {
      throw new Error("endpoint returned no message content");
    }
    session.lastError = "";
    return content;
  }

  /* ---------------------------------------------------------- validation -- */
  function extractJson(raw) {
    var text = String(raw == null ? "" : raw).trim();
    if (!text) throw new Error("model returned an empty response");
    var fenced = /^```(?:json)?\s*\r?\n([\s\S]*?)\r?\n```$/i.exec(text);
    if (fenced) text = fenced[1].trim();
    else if (/^```|```$/.test(text)) {
      throw new Error("model returned a partially fenced response; expected one JSON object");
    }
    if (text.charAt(0) !== "{") {
      throw new Error("model did not return a JSON object");
    }
    var obj;
    try { obj = JSON.parse(text); }
    catch (e) { throw new Error("model returned invalid JSON: " + e.message); }
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
      throw new Error("model returned JSON that is not an object");
    }
    return obj;
  }

  function genres() {
    var t = root.toolrxTemplates;
    if (t && typeof t.gameGenres === "function") return t.gameGenres();
    return ["platformer", "rpg", "shooter", "racer", "maze", "roguelike",
      "towerdefense", "farmingsim", "rhythm", "builder"];
  }

  function validatePlan(obj) {
    var allowed = ["genre", "dim", "why"];
    var keys = Object.keys(obj);
    for (var i = 0; i < keys.length; i++) {
      if (allowed.indexOf(keys[i]) < 0) {
        throw new Error("model returned an unexpected key: " + keys[i]);
      }
    }
    if (typeof obj.genre !== "string" || !obj.genre.trim()) {
      throw new Error("plan is missing a genre");
    }
    var genre = obj.genre.trim().toLowerCase();
    if (genres().indexOf(genre) < 0) {
      throw new Error("model chose a genre outside the allow-list: " + genre);
    }
    var dim = "";
    if (obj.dim != null) {
      if (typeof obj.dim !== "string") throw new Error("plan dim must be a string (2D or 3D)");
      dim = obj.dim.trim().toUpperCase();
      if (dim !== "2D" && dim !== "3D") throw new Error("plan dim must be 2D or 3D");
    }
    var why = "";
    if (obj.why != null) {
      if (typeof obj.why !== "string") throw new Error("plan why must be a string");
      why = obj.why.replace(/\s+/g, " ").trim().slice(0, MAX_WHY);
    }
    return { genre: genre, dim: dim, why: why };
  }

  function validatePatch(obj, file) {
    var allowed = ["file", "diff"];
    var keys = Object.keys(obj);
    for (var i = 0; i < keys.length; i++) {
      if (allowed.indexOf(keys[i]) < 0) {
        throw new Error("model returned an unexpected key: " + keys[i]);
      }
    }
    if (obj.file !== file) {
      throw new Error("model tried to patch " + JSON.stringify(obj.file) + " instead of " + file);
    }
    if (typeof obj.diff !== "string" || !obj.diff.trim()) {
      throw new Error("patch is missing a diff");
    }
    if (obj.diff.length > MAX_DIFF) {
      throw new Error("patch diff is too large (" + obj.diff.length + " chars; max " + MAX_DIFF + ")");
    }
    if (obj.diff.indexOf("\u0000") >= 0) throw new Error("patch diff contains a NUL byte");
    if (!/^@@ /m.test(obj.diff)) throw new Error("patch diff has no unified-diff hunk (@@ ... @@)");
    if (/^GIT binary patch/m.test(obj.diff) || /^Binary files /m.test(obj.diff)) {
      throw new Error("binary patches are not supported");
    }
    return { file: file, diff: obj.diff };
  }

  /* ------------------------------------------------------------- naming -- */
  function safeFileName(name) {
    var n = String(name == null ? "" : name).trim();
    if (!n) throw new Error("no file name given");
    if (n.length > 64) throw new Error("file name is too long");
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(n)) {
      throw new Error("file name must be a plain project file, e.g. app.js");
    }
    if (n.indexOf("..") >= 0) throw new Error("file name must not contain ..");
    return n;
  }

  /* -------------------------------------------------------- diff parser -- */
  function splitLines(text) {
    return String(text).replace(/\r\n/g, "\n").split("\n");
  }

  function parseDiff(diff, file) {
    var raw = splitLines(diff);
    var hunks = [];
    var current = null;
    var sawHeader = false;

    for (var i = 0; i < raw.length; i++) {
      var line = raw[i];
      if (i === raw.length - 1 && line === "") break; // trailing newline of the diff
      if (line.indexOf("\\ ") === 0) {
        if (current) current.noNewline = /no newline/i.test(line);
        continue;
      }
      if (line.indexOf("@@") === 0) {
        var m = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/.exec(line);
        if (!m) throw new Error("invalid hunk header in the patch: " + line.slice(0, 60));
        current = {
          oldStart: parseInt(m[1], 10),
          oldCount: m[2] == null ? 1 : parseInt(m[2], 10),
          newStart: parseInt(m[3], 10),
          newCount: m[4] == null ? 1 : parseInt(m[4], 10),
          expect: [],
          replace: [],
          noNewline: false,
        };
        hunks.push(current);
        sawHeader = true;
        continue;
      }
      if (!current) {
        if (line.indexOf("--- ") === 0 || line.indexOf("+++ ") === 0) {
          var named = line.slice(4).trim().split(/\s+/)[0].replace(/^[ab]\//, "");
          if (named !== file) {
            throw new Error("patch header names " + named + " but the target is " + file);
          }
          continue;
        }
        if (line.indexOf("diff --git") === 0 || line.indexOf("index ") === 0
            || line.indexOf("new file mode") === 0 || line.indexOf("deleted file mode") === 0
            || line === "") {
          continue;
        }
        throw new Error("unexpected line before the first hunk: " + line.slice(0, 60));
      }
      var tag = line.charAt(0);
      var rest = line.slice(1);
      if (tag === " " || tag === "") {
        current.expect.push(rest);
        current.replace.push(rest);
      } else if (tag === "-") {
        current.expect.push(rest);
      } else if (tag === "+") {
        current.replace.push(rest);
      } else {
        throw new Error("invalid diff line: " + line.slice(0, 60));
      }
    }
    if (!sawHeader) throw new Error("patch diff has no hunks");
    for (var h = 0; h < hunks.length; h++) {
      var hk = hunks[h];
      if (hk.expect.length !== hk.oldCount) {
        throw new Error("hunk declares " + hk.oldCount + " old lines but carries " + hk.expect.length);
      }
      if (hk.replace.length !== hk.newCount) {
        throw new Error("hunk declares " + hk.newCount + " new lines but carries " + hk.replace.length);
      }
    }
    return hunks;
  }

  function applyDiff(content, diff, file) {
    var name = safeFileName(file);
    if (typeof diff !== "string" || diff.length > MAX_DIFF) {
      throw new Error("diff is missing or too large");
    }
    var src = String(content == null ? "" : content).replace(/\r\n/g, "\n");
    var trailing = /\n$/.test(src);
    var lines = src.length ? src.split("\n") : [];
    if (trailing && lines.length) lines.pop();
    if (!lines.length && src.length === 0) lines = [];

    var hunks = parseDiff(diff, name);
    var out = [];
    var cursor = 0;
    var noNewline = false;

    for (var i = 0; i < hunks.length; i++) {
      var h = hunks[i];
      var pos = h.oldCount === 0 ? h.oldStart : Math.max(0, h.oldStart - 1);
      if (pos < cursor) throw new Error("hunks overlap in " + name);
      if (pos > lines.length) {
        throw new Error("hunk starts past the end of " + name + " (line " + (pos + 1) + ")");
      }
      var actual = lines.slice(pos, pos + h.expect.length);
      if (actual.length !== h.expect.length) {
        throw new Error("hunk runs past the end of " + name + " (line " + (pos + 1) + ")");
      }
      for (var k = 0; k < h.expect.length; k++) {
        if (actual[k] !== h.expect[k]) {
          throw new Error("diff does not apply to " + name + " at line " + (pos + 1)
            + " — the file changed since the patch was generated");
        }
      }
      for (var c = cursor; c < pos; c++) out.push(lines[c]);
      for (var r = 0; r < h.replace.length; r++) out.push(h.replace[r]);
      cursor = pos + h.expect.length;
      if (h.noNewline) noNewline = true;
    }
    for (var t = cursor; t < lines.length; t++) out.push(lines[t]);

    var body = out.join("\n");
    if (noNewline) return body;
    return body + (trailing || !src.length ? "\n" : "");
  }

  /* ---------------------------------------------------------------- plan -- */
  function planKey(prompt) {
    return "plan:" + hash(normalizePrompt(prompt) + "|" + genres().join(","));
  }

  function planSystem() {
    return "You choose one genre for a deterministic offline game builder. "
      + "Reply with a single JSON object and nothing else. "
      + 'Shape: {"genre":"<one of the allow-list>","dim":"2D or 3D","why":"at most 140 characters"}. '
      + "No other keys. The allow-list is: " + genres().join(", ") + ". "
      + "Pick the closest playable genre; never invent a genre.";
  }

  function planText(r, extra) {
    var t = root.toolrxTemplates;
    var spec = t && t.spec ? t.spec(r.genre, r.prompt || r.genre) : null;
    var dim = spec && spec.dim ? spec.dim : (r.dim || "2D");
    var label = spec && spec.label ? spec.label : r.genre;
    var lines = ["llm plan · " + label + " (" + dim + ")"];
    if (r.why) lines.push("why: " + r.why);
    if (r.note) lines.push(r.note);
    lines.push(extra);
    lines.push("try: build a " + label + " game");
    return lines.join("\n");
  }

  async function plan(prompt) {
    var q = String(prompt == null ? "" : prompt).trim();
    if (!q) throw new Error("no prompt for the llm plan");
    var t = root.toolrxTemplates;
    var genre = t && t.canonical ? t.canonical(q, q) : "playground";
    if (genre !== "playground") {
      var base = planText({ genre: genre, prompt: q, why: "" },
        "deterministic parser matched this prompt — no request sent");
      return {
        ok: true, source: "deterministic", genre: genre, dim: "", why: "",
        text: base, calls: session.calls,
      };
    }
    var c = assertReady();
    var key = planKey(q);
    var hit = cacheGet(key);
    if (hit && hit.genre) {
      return {
        ok: true, source: "cache", genre: hit.genre, dim: hit.dim || "",
        why: hit.why || "", calls: session.calls,
        text: planText({ genre: hit.genre, prompt: q, why: hit.why },
          "cache hit · no request sent · calls " + session.calls + "/" + c.maxCalls),
      };
    }
    var raw = await ask(planSystem(),
      "Prompt: " + q + "\nAllowed genres: " + genres().join(", "), c);
    var v = validatePlan(extractJson(raw));
    cachePut(key, v);
    return {
      ok: true, source: "llm", genre: v.genre, dim: v.dim, why: v.why,
      calls: session.calls,
      text: planText({ genre: v.genre, prompt: q, why: v.why },
        "cache miss · call " + session.calls + "/" + c.maxCalls
          + " · deterministic fallback was playground"),
    };
  }

  /* --------------------------------------------------------------- patch -- */
  function patchKey(file, instruction, content) {
    return "patch:" + file + ":" + hash(normalizePrompt(instruction) + "|" + hash(content));
  }

  function patchSystem(file) {
    return "You write one unified diff against the current content of " + file + ". "
      + "Reply with a single JSON object and nothing else. "
      + 'Shape: {"file":"' + file + '","diff":"@@ -start,count +start,count @@\\n context\\n-old\\n+new"}. '
      + "No other keys, no markdown, no commentary. Use exactly the file name given. "
      + "The diff must apply line-for-line to the current content. Keep the change small.";
  }

  async function patch(file, instruction, opts) {
    var name = safeFileName(file);
    var text = String(instruction == null ? "" : instruction).trim();
    if (!text) throw new Error("no instruction for the llm patch");
    var o = opts || {};
    var content = String(o.content == null ? "" : o.content);
    if (!content) throw new Error("there is no content to patch in " + name);
    if (content.length > MAX_SOURCE) {
      throw new Error(name + " is too large for an LLM patch ("
        + content.length + " chars; max " + MAX_SOURCE + ")");
    }
    var c = assertReady();
    var key = patchKey(name, text, content);
    var hit = cacheGet(key);
    if (hit && hit.diff) {
      return {
        ok: true, source: "cache", file: name, diff: hit.diff, calls: session.calls,
        text: "llm patch · " + name + "\ninstruction: " + text
          + "\ncache hit · no request sent · calls " + session.calls + "/" + c.maxCalls
          + "\nsay apply the llm patch to write it, or discard the llm patch",
      };
    }
    var raw = await ask(patchSystem(name),
      "File: " + name + "\nInstruction: " + text + "\n\nCurrent content:\n" + content, c);
    var v = validatePatch(extractJson(raw), name);
    cachePut(key, v);
    return {
      ok: true, source: "llm", file: name, diff: v.diff, calls: session.calls,
      text: "llm patch · " + name + "\ninstruction: " + text
        + "\n" + (v.diff.match(/^@@ /gm) || []).length + " hunk(s) · "
        + v.diff.length + " chars"
        + " · cache miss · call " + session.calls + "/" + c.maxCalls
        + "\nsay apply the llm patch to write it, or discard the llm patch",
    };
  }

  /* --------------------------------------------------------------- misc -- */
  function resetBudget() {
    session.calls = 0;
    session.lastError = "";
  }

  root.toolrxLlm = {
    CONFIG_KEY: CONFIG_KEY,
    CACHE_KEY: CACHE_KEY,
    PENDING_KEY: PENDING_KEY,
    MAX_CACHE: MAX_CACHE,
    DEFAULTS: DEFAULTS,
    config: config,
    configure: configure,
    enable: enable,
    status: status,
    statusText: statusText,
    plan: plan,
    patch: patch,
    applyDiff: applyDiff,
    parseDiff: parseDiff,
    validatePlan: validatePlan,
    validatePatch: validatePatch,
    extractJson: extractJson,
    safeFileName: safeFileName,
    safeEndpoint: safeEndpoint,
    genres: genres,
    hash: hash,
    normalizePrompt: normalizePrompt,
    pending: pending,
    setPending: setPending,
    clearPending: clearPending,
    cacheSize: cacheSize,
    clearCache: clearCache,
    resetBudget: resetBudget,
    calls: function () { return session.calls; },
  };
})(typeof self !== "undefined" ? self : this);

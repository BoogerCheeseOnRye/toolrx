/* toolrx deterministic cross-project workspace index (step 64).
 *
 * The workspace index is derived, never a second copy of the journals. It
 * reads the project list (slug, name, kind, theme, seed, updated) plus each
 * project's own journal, and keeps only the newest build line and the sorted
 * topic names. Full entries stay in their per-project journals, and project
 * context is never read.
 *
 * Five explicit limits bound the work: `workspaceProjects`, `workspaceTopics`,
 * `workspaceRows`, `workspaceIndexBytes`, and `workspaceChars`. Drops at a cap
 * are reported in the index and the rendered answer, never silently.
 *
 * This module is the byte-identical twin of `toolrx/workspace.py`: the same
 * `build`, `render`, `exportDoc`, and `importDoc` over the same caps. No DOM, no
 * network, no clock. The sandbox passes in the live state; this module only
 * validates, bounds, stores, and answers.
 */
(function (root) {
  "use strict";

  var VERSION = 1;
  var KINDS = ["decision", "rejection", "preference"];
  var WORDS = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7,
    eight: 8, nine: 9 };
  var STOP = {
    a: 1, an: 1, and: 1, about: 1, are: 1, be: 1, by: 1, choose: 1,
    chose: 1, decide: 1, decided: 1, decision: 1, did: 1, do: 1, for: 1,
    have: 1, in: 1, is: 1, it: 1, journal: 1, of: 1, on: 1, or: 1, our: 1,
    reject: 1, rejected: 1, said: 1, say: 1, the: 1, to: 1, was: 1, we: 1,
    were: 1, what: 1, why: 1
  };

  function byteLength(text) {
    var s = String(text == null ? "" : text);
    if (typeof TextEncoder !== "undefined") {
      return new TextEncoder().encode(s).length;
    }
    try { return unescape(encodeURIComponent(s)).length; }
    catch (e) { return s.length; }
  }

  function oneLine(text) {
    return String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  }

  function norm(text) {
    return oneLine(text).toLowerCase();
  }

  function tokens(text) {
    return String(text == null ? "" : text).toLowerCase()
      .split(/[^a-z0-9]+/).filter(Boolean);
  }

  function keywords(text) {
    return tokens(text).filter(function (t) {
      return !Object.prototype.hasOwnProperty.call(STOP, t);
    });
  }

  function plural(n, one, many) {
    return n + " " + (n === 1 ? one : many);
  }

  /* Python `int()` accepts a signed integer string (underscores and surrounding
   * whitespace included) and truncates floats toward zero; anything else is the
   * fallback. Mirror that exactly so the two twins agree on imported values. */
  function asInt(value, fallback) {
    if (fallback === undefined) fallback = 0;
    if (typeof value === "boolean") value = value ? 1 : 0;
    if (typeof value === "number") {
      if (!isFinite(value)) return fallback;
      value = value < 0 ? Math.ceil(value) : Math.floor(value);
      return value < 0 ? fallback : value;
    }
    if (typeof value === "string") {
      var text = value.replace(/\s+/g, "").replace(/_/g, "");
      if (!/^[+-]?\d+$/.test(text)) return fallback;
      var n = parseInt(text, 10);
      if (!isFinite(n) || n < 0) return fallback;
      return n;
    }
    return fallback;
  }

  /* Python slices and `len()` count code points, not UTF-16 units. */
  function cut(text, n) {
    var chars = Array.from(String(text == null ? "" : text));
    if (chars.length <= n) return chars.join("");
    return chars.slice(0, n).join("");
  }

  function charsLen(text) {
    return Array.from(String(text == null ? "" : text)).length;
  }

  /* Python sorts strings by code point; JS's default sort uses UTF-16 units. */
  function cmpText(a, b) {
    var x = Array.from(a), y = Array.from(b);
    var n = Math.min(x.length, y.length);
    for (var i = 0; i < n; i++) {
      var cx = x[i].codePointAt(0), cy = y[i].codePointAt(0);
      if (cx !== cy) return cx < cy ? -1 : 1;
    }
    return x.length - y.length;
  }

  function sortedText(list) {
    return list.slice().sort(cmpText);
  }

  function uniqueSorted(list) {
    var seen = Object.create(null), out = [];
    list.forEach(function (item) {
      var key = String(item);
      if (!seen[key]) { seen[key] = 1; out.push(key); }
    });
    return sortedText(out);
  }

  /* ---------------------------------------------------------------- caps --- */
  function caps(limits) {
    var base = root.toolrxLimits;
    if (!base) throw new Error("toolrx/web/limits.js must load before workspace.js");
    var data = {};
    Object.keys(base).forEach(function (k) { data[k] = base[k]; });
    if (limits) Object.keys(limits).forEach(function (k) { data[k] = limits[k]; });
    function get(key, fallback) {
      var n = parseInt(data[key], 10);
      if (!isFinite(n)) n = fallback;
      return Math.max(1, n);
    }
    return {
      projects: get("workspaceProjects", 24),
      topics: get("workspaceTopics", 8),
      rows: get("workspaceRows", 12),
      bytes: get("workspaceIndexBytes", 8192),
      chars: get("workspaceChars", 4000),
      journalText: get("journalText", 240)
    };
  }

  /* --------------------------------------------------------------- index --- */
  function cleanEntry(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
    var kind = String(raw.kind || "");
    if (KINDS.indexOf(kind) < 0) return null;
    var topic = cut(oneLine(raw.topic), 60);
    var text = cut(oneLine(raw.text), 240);
    if (!topic || !text) return null;
    return {
      seq: asInt(raw.seq),
      kind: kind,
      topic: topic,
      text: text,
      source: cut(oneLine(raw.source || "unknown"), 60)
    };
  }

  function cleanProject(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
    var slug = cut(oneLine(raw.slug), 60);
    if (!slug) return null;
    var seed = raw.seed;
    if (typeof seed === "boolean" || typeof seed !== "number"
        || !isFinite(seed) || seed < 0) {
      seed = null;
    } else {
      seed = Math.floor(seed);
    }
    var journal = [];
    if (Array.isArray(raw.journal)) {
      raw.journal.forEach(function (entry) {
        var clean = cleanEntry(entry);
        if (clean) journal.push(clean);
      });
    }
    return {
      slug: slug,
      name: cut(oneLine(raw.name), 60) || slug,
      kind: cut(oneLine(raw.kind), 40) || "unknown",
      theme: oneLine(raw.theme).toLowerCase() === "light" ? "light" : "dark",
      seed: seed,
      updated: asInt(raw.updated),
      journal: journal
    };
  }

  function cleanProjects(raw) {
    var out = [];
    if (Array.isArray(raw)) {
      raw.forEach(function (project) {
        var clean = cleanProject(project);
        if (clean) out.push(clean);
      });
    }
    out.sort(function (a, b) { return cmpText(a.slug, b.slug); });
    return out;
  }

  function exportDoc(index) {
    return JSON.stringify(index);
  }

  function size(index) {
    return byteLength(exportDoc(index));
  }

  function build(state, limits) {
    var cap = caps(limits);
    var rows = [];
    var droppedTopics = 0;
    cleanProjects((state || {}).projects).forEach(function (project) {
      var topics = uniqueSorted(project.journal.map(function (e) { return e.topic; })
        .filter(Boolean));
      var kept = topics.slice(0, cap.topics);
      droppedTopics += topics.length - kept.length;
      var latest = null;
      project.journal.forEach(function (entry) {
        if (entry.source !== "build") return;
        if (latest === null || entry.seq >= latest.seq) latest = entry;
      });
      rows.push({
        slug: project.slug,
        name: project.name,
        kind: project.kind,
        theme: project.theme,
        seed: project.seed,
        build: latest ? cut(oneLine(latest.text), 120) : "",
        topics: kept,
        updated: project.updated
      });
    });
    var droppedProjects = Math.max(0, rows.length - cap.projects);
    rows = rows.slice(0, cap.projects);
    var doc = {
      version: 1,
      projects: rows,
      dropped: { projects: droppedProjects, topics: droppedTopics }
    };
    while (rows.length && size(doc) > cap.bytes) {
      rows.pop();
      doc.dropped.projects += 1;
    }
    doc.bytes = size(doc);
    return doc;
  }

  function importDoc(raw, limits) {
    var cap = caps(limits);
    var doc;
    if (typeof raw === "string") {
      try { doc = JSON.parse(raw); }
      catch (e) { return { ok: false, why: "the workspace index is not valid JSON" }; }
    } else {
      doc = raw;
    }
    if (!doc || typeof doc !== "object" || Array.isArray(doc)) {
      return { ok: false, why: "the workspace index is not an object" };
    }
    if (doc.version !== 1) {
      return { ok: false, why: "unsupported workspace index version " + String(doc.version) };
    }
    if (!Array.isArray(doc.projects)) {
      return { ok: false, why: "the workspace index has no projects list" };
    }
    var rows = [];
    var dropped = (doc.dropped && typeof doc.dropped === "object"
      && !Array.isArray(doc.dropped)) ? doc.dropped : {};
    var droppedTopics = asInt(dropped.topics);
    for (var i = 0; i < doc.projects.length; i++) {
      var rawProject = doc.projects[i];
      if (!rawProject || typeof rawProject !== "object" || Array.isArray(rawProject)) {
        return { ok: false, why: "a workspace index row is not an object" };
      }
      var slug = cut(oneLine(rawProject.slug), 60);
      if (!slug) return { ok: false, why: "a workspace index row has no slug" };
      var seed = rawProject.seed;
      if (typeof seed === "boolean" || typeof seed !== "number"
          || !isFinite(seed) || seed < 0) {
        seed = null;
      } else {
        seed = Math.floor(seed);
      }
      if (!Array.isArray(rawProject.topics)) {
        return { ok: false, why: "workspace index topics must be a list" };
      }
      var topics = [];
      rawProject.topics.forEach(function (topic) {
        var text = cut(oneLine(topic), 60);
        if (text && topics.indexOf(text) < 0) topics.push(text);
      });
      topics = sortedText(topics);
      var kept = topics.slice(0, cap.topics);
      droppedTopics += topics.length - kept.length;
      rows.push({
        slug: slug,
        name: cut(oneLine(rawProject.name), 60) || slug,
        kind: cut(oneLine(rawProject.kind), 40) || "unknown",
        theme: oneLine(rawProject.theme).toLowerCase() === "light" ? "light" : "dark",
        seed: seed,
        build: cut(oneLine(rawProject.build), 120),
        topics: kept,
        updated: asInt(rawProject.updated)
      });
    }
    rows.sort(function (a, b) { return cmpText(a.slug, b.slug); });
    var droppedProjects = asInt(dropped.projects)
      + Math.max(0, rows.length - cap.projects);
    rows = rows.slice(0, cap.projects);
    var out = {
      version: 1,
      projects: rows,
      dropped: { projects: droppedProjects, topics: droppedTopics }
    };
    while (rows.length && size(out) > cap.bytes) {
      rows.pop();
      out.dropped.projects += 1;
    }
    out.bytes = size(out);
    return { ok: true, index: out };
  }

  /* -------------------------------------------------------------- render --- */
  function finish(lines, cap) {
    var text = lines.join("\n");
    if (charsLen(text) <= cap.chars) return text;
    var cutText = cut(text, cap.chars);
    var at = cutText.lastIndexOf("\n");
    if (at > 0) cutText = cutText.slice(0, at);
    return cutText + "\n… trimmed to workspaceChars (" + cap.chars + " chars) · r.trim";
  }

  function seedText(seed) {
    return seed === null || seed === undefined ? "n/a" : String(seed);
  }

  function renderIndex(doc, cap) {
    var projects = doc.projects;
    if (!projects.length) {
      return finish([
        "workspace index · empty",
        "no projects yet — build something first",
        "writes: no file · r.no-write"
      ], cap);
    }
    var topics = 0;
    projects.forEach(function (p) { topics += p.topics.length; });
    var lines = [
      "workspace index · " + plural(projects.length, "project", "projects")
      + " · " + plural(topics, "topic", "topics")
      + " · cap " + cap.projects + " projects · " + cap.bytes + " bytes"
    ];
    projects.forEach(function (project) {
      var listed = project.topics.length ? project.topics.join(", ") : "none";
      lines.push("  " + project.slug + " · " + project.name + " · "
        + project.kind + " · " + project.theme + " · seed "
        + seedText(project.seed) + " · topics " + listed);
      lines.push("    last build: " + (project.build || "none"));
    });
    var notes = [];
    if (doc.dropped.projects) {
      notes.push(plural(doc.dropped.projects, "project", "projects")
        + " dropped at the workspaceProjects cap");
    }
    if (doc.dropped.topics) {
      notes.push(plural(doc.dropped.topics, "topic", "topics")
        + " dropped at the workspaceTopics cap");
    }
    lines.push("notes: " + (notes.length ? notes.join(" · ") : "none"));
    lines.push("source: project files + per-project journals · context is never read · r.index");
    lines.push("writes: no file · r.no-write");
    return finish(lines, cap);
  }

  function renderThemes(doc, cap) {
    var projects = doc.projects;
    if (!projects.length) {
      return finish([
        "workspace themes · empty",
        "no projects yet — build something first",
        "writes: no file · r.no-write"
      ], cap);
    }
    var lines = ["workspace themes · "
      + plural(projects.length, "project", "projects")];
    var shown = projects.slice(0, cap.rows);
    shown.forEach(function (project) {
      lines.push("  " + project.slug + " · " + project.theme + " · "
        + project.kind + " · seed " + seedText(project.seed));
    });
    if (projects.length > shown.length) {
      lines.push("  · … " + (projects.length - shown.length)
        + " more projects at the workspaceRows cap");
    }
    lines.push("cap " + cap.rows + " rows · workspaceRows · r.themes");
    return finish(lines, cap);
  }

  function parseLimit(value) {
    var text = norm(value);
    if (!text) return 3;
    var n = Object.prototype.hasOwnProperty.call(WORDS, text)
      ? WORDS[text] : undefined;
    if (n === undefined) {
      if (!/^[+-]?\d+$/.test(text)) n = 3;
      else n = parseInt(text, 10);
    }
    return Math.max(1, Math.min(9, n));
  }

  function entryMatches(entry, want, phrase) {
    var hay = tokens(entry.topic + " " + entry.text + " " + entry.source);
    var score = 0;
    if (!want.length) score = 1;
    want.forEach(function (token) {
      if (hay.indexOf(token) >= 0) score += 2;
    });
    if (phrase && (norm(entry.topic).indexOf(phrase) >= 0
        || norm(entry.text + " " + entry.source).indexOf(phrase) >= 0)) {
      score += 4;
    }
    return score > 0;
  }

  function renderDecisions(state, args, cap) {
    var projects = cleanProjects((state || {}).projects);
    var topic = oneLine((args || {}).topic);
    var limit = parseLimit((args || {}).limit);
    if (!projects.length) {
      return finish([
        "workspace decisions · empty",
        "no projects yet — build something first",
        "writes: no file · r.no-write"
      ], cap);
    }
    var ordered = projects.slice().sort(function (a, b) {
      if (a.updated !== b.updated) return b.updated - a.updated;
      return cmpText(a.slug, b.slug);
    }).slice(0, limit);
    var want = keywords(topic);
    var phrase = norm(topic);
    var rows = [];
    ordered.forEach(function (project) {
      var matches = project.journal.filter(function (entry) {
        return entryMatches(entry, want, phrase);
      });
      matches.sort(function (a, b) { return b.seq - a.seq; });
      matches.forEach(function (entry) { rows.push([project, entry]); });
    });
    var known = [];
    ordered.forEach(function (p) {
      p.journal.forEach(function (e) { known.push(e.topic); });
    });
    known = uniqueSorted(known).slice(0, cap.topics);
    if (!rows.length) {
      var lines = ["workspace decisions · nothing about \"" + topic + "\" yet · "
        + plural(ordered.length, "project", "projects") + " searched"];
      if (known.length) lines.push("known topics: " + known.join(", "));
      lines.push("cap " + cap.rows + " rows · r.decisions");
      return finish(lines, cap);
    }
    var shown = rows.slice(0, cap.rows);
    var head = ["workspace decisions · \"" + topic + "\" · last " + limit
      + " builds · " + plural(rows.length, "match", "matches")];
    shown.forEach(function (pair) {
      var project = pair[0], entry = pair[1];
      head.push("  " + project.slug + " · #" + entry.seq + " "
        + entry.kind + " · " + entry.topic + " · "
        + entry.text + " · via " + entry.source);
    });
    if (rows.length > shown.length) {
      head.push("  · … " + (rows.length - shown.length)
        + " more matches at the workspaceRows cap");
    }
    head.push("cap " + cap.rows + " rows · searched "
      + plural(ordered.length, "project", "projects") + " · r.decisions");
    return finish(head, cap);
  }

  function render(kind, state, args, limits) {
    var cap = caps(limits);
    if (kind === "index") return renderIndex(build(state, limits), cap);
    if (kind === "themes") return renderThemes(build(state, limits), cap);
    if (kind === "decisions") return renderDecisions(state, args || {}, cap);
    throw new Error("unknown workspace target: " + kind);
  }

  root.toolrxWorkspace = {
    LIMIT: caps(null),
    caps: caps,
    build: build,
    render: render,
    exportDoc: exportDoc,
    importDoc: importDoc,
    size: size
  };
})(typeof globalThis !== "undefined" ? globalThis : this);

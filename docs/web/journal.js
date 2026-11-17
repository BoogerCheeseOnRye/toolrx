/* toolrx deterministic project journal (step 56).
 *
 * One small, inspectable log of decisions, rejected alternatives, and user
 * preferences per project. Entries live in localStorage under one key per
 * project, so two projects can never share a journal, and they are deliberately
 * separate from the short conversation memory.
 *
 * Every entry names the route that made it (`build`, `edit.apply`,
 * `repair.plan`, `plan.variant`, `memory.remember`, …). Three explicit limits
 * bound the log: `journalEntries`, `journalBytes`, and `journalText`. Evictions
 * and trims are recorded in a bounded note ring so the cap is never silent.
 *
 * No DOM, no network, no clock. The sandbox decides when to add; this module
 * only validates, bounds, stores, and answers.
 */
(function (root) {
  "use strict";

  var PREFIX = "toolrx.journal.v1.";
  var INDEX_KEY = PREFIX + "index";
  var VERSION = 1;
  var KINDS = ["decision", "rejection", "preference"];
  var NOTE_KEEP = 8;
  var LIMIT = (function () {
    if (!root.toolrxLimits) {
      throw new Error("toolrx/web/limits.js must load before journal.js");
    }
    return {
      entries: root.toolrxLimits.journalEntries,
      bytes: root.toolrxLimits.journalBytes,
      text: root.toolrxLimits.journalText
    };
  })();

  var STOP = {
    a: 1, an: 1, and: 1, about: 1, are: 1, be: 1, by: 1, choose: 1,
    chose: 1, decide: 1, decided: 1, decision: 1, did: 1, do: 1, for: 1,
    have: 1, in: 1, is: 1, it: 1, journal: 1, of: 1, on: 1, or: 1, our: 1,
    reject: 1, rejected: 1, said: 1, say: 1, the: 1, to: 1, was: 1, we: 1,
    were: 1, what: 1, why: 1
  };

  function keyFor(slug) {
    return PREFIX + (String(slug || "").trim() || "scratch");
  }

  function byteLength(text) {
    var s = String(text == null ? "" : text);
    if (typeof TextEncoder !== "undefined") {
      return new TextEncoder().encode(s).length;
    }
    try { return unescape(encodeURIComponent(s)).length; }
    catch (e) { return s.length; }
  }

  function trimToBytes(text, max) {
    var s = String(text == null ? "" : text);
    if (byteLength(s) <= max) return s;
    var out = "", used = 0;
    for (var i = 0; i < s.length; i++) {
      var code = s.charCodeAt(i);
      var wide = code >= 0xD800 && code <= 0xDBFF && i + 1 < s.length;
      var piece = wide ? s.substr(i, 2) : s.charAt(i);
      var size = byteLength(piece);
      if (used + size > max) break;
      out += piece;
      used += size;
      if (wide) i++;
    }
    return out;
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
    return tokens(text).filter(function (t) { return !STOP[t]; });
  }

  function emptyState(slug) {
    return {
      version: VERSION,
      project: String(slug || "").trim() || "scratch",
      seq: 0,
      entries: [],
      notes: [],
      dropped: 0
    };
  }

  function cleanEntry(raw) {
    if (!raw || typeof raw !== "object") return null;
    var kind = String(raw.kind || "");
    if (KINDS.indexOf(kind) < 0) return null;
    var topic = oneLine(raw.topic).slice(0, 60);
    var text = oneLine(raw.text).slice(0, LIMIT.text);
    if (!topic || !text) return null;
    return {
      seq: Math.max(0, parseInt(raw.seq, 10) || 0),
      kind: kind,
      topic: topic,
      text: text,
      source: oneLine(raw.source || "unknown").slice(0, 60),
      n: Math.max(0, parseInt(raw.n, 10) || 0)
    };
  }

  function cleanNote(raw) {
    if (!raw || typeof raw !== "object") return null;
    return {
      seq: Math.max(0, parseInt(raw.seq, 10) || 0),
      kind: KINDS.indexOf(String(raw.kind || "")) >= 0
        ? String(raw.kind) : "entry",
      topic: oneLine(raw.topic).slice(0, 60),
      why: oneLine(raw.why || "evicted").slice(0, 40)
    };
  }

  function read(slug) {
    var key = keyFor(slug);
    try {
      var raw = root.localStorage && root.localStorage.getItem(key);
      if (!raw) return emptyState(slug);
      var parsed = JSON.parse(raw);
      if (!parsed || parsed.version !== VERSION
          || !Array.isArray(parsed.entries)) {
        return emptyState(slug);
      }
      var state = emptyState(slug);
      state.seq = Math.max(0, parseInt(parsed.seq, 10) || 0);
      state.dropped = Math.max(0, parseInt(parsed.dropped, 10) || 0);
      state.entries = parsed.entries.map(cleanEntry).filter(Boolean);
      state.notes = (Array.isArray(parsed.notes) ? parsed.notes : [])
        .map(cleanNote).filter(Boolean).slice(-NOTE_KEEP);
      return state;
    } catch (e) {
      return emptyState(slug);
    }
  }

  function readIndex() {
    try {
      var raw = root.localStorage && root.localStorage.getItem(INDEX_KEY);
      var list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list.map(String) : [];
    } catch (e) { return []; }
  }

  function rememberScope(slug) {
    var s = String(slug || "").trim() || "scratch";
    var list = readIndex();
    if (list.indexOf(s) >= 0) return;
    list.push(s);
    list.sort();
    try {
      root.localStorage.setItem(INDEX_KEY, JSON.stringify(list));
    } catch (e) { /* ignore */ }
  }

  function forgetScope(slug) {
    var s = String(slug || "").trim() || "scratch";
    var list = readIndex().filter(function (x) { return x !== s; });
    try {
      root.localStorage.setItem(INDEX_KEY, JSON.stringify(list));
    } catch (e) { /* ignore */ }
  }

  function size(state) {
    return byteLength(JSON.stringify(state));
  }

  function addNote(state, entry, why) {
    state.notes.push({
      seq: entry.seq, kind: entry.kind, topic: entry.topic, why: why
    });
    while (state.notes.length > NOTE_KEEP) state.notes.shift();
  }

  /* Keep the newest entries under both caps. The oldest entry goes first; if a
   * single entry is larger than the byte cap, its text is trimmed instead, and
   * only then is it dropped. Every action leaves a named note. */
  function fit(state) {
    while (state.entries.length > LIMIT.entries) {
      var gone = state.entries.shift();
      state.dropped += 1;
      addNote(state, gone, "entry cap");
    }
    var guard = 0;
    while (state.entries.length > 1 && size(state) > LIMIT.bytes
           && guard++ < 1000) {
      var gone2 = state.entries.shift();
      state.dropped += 1;
      addNote(state, gone2, "byte cap");
    }
    if (state.entries.length && size(state) > LIMIT.bytes) {
      var only = state.entries[0];
      var over = size(state) - LIMIT.bytes;
      var room = byteLength(only.text) - over - 40;
      if (room < 24) {
        state.entries.shift();
        state.dropped += 1;
        addNote(state, only, "byte cap");
      } else {
        only.text = trimToBytes(only.text, room) + "…";
        addNote(state, only, "trimmed");
      }
    }
    while (state.notes.length && size(state) > LIMIT.bytes) {
      state.notes.shift();
    }
    return state;
  }

  function write(slug, state) {
    try {
      root.localStorage.setItem(keyFor(slug), JSON.stringify(state));
      rememberScope(slug);
      return true;
    } catch (e) {
      return false;
    }
  }

  function add(slug, input) {
    var raw = input || {};
    var kind = String(raw.kind || "");
    if (KINDS.indexOf(kind) < 0) {
      return { ok: false, why: "journal kind must be decision, rejection, or preference" };
    }
    var topic = oneLine(raw.topic).slice(0, 60);
    var text = oneLine(raw.text).slice(0, LIMIT.text);
    if (!topic || !text) {
      return { ok: false, why: "a journal entry needs a topic and text" };
    }
    var state = read(slug);
    var last = state.entries[state.entries.length - 1];
    var source = oneLine(raw.source || "unknown").slice(0, 60);
    if (last && last.kind === kind && last.topic === topic
        && last.text === text && last.source === source) {
      return { ok: true, duplicate: true, entry: last, state: state };
    }
    state.seq += 1;
    var entry = {
      seq: state.seq, kind: kind, topic: topic, text: text,
      source: source, n: Math.max(0, parseInt(raw.n, 10) || 0)
    };
    state.entries.push(entry);
    fit(state);
    if (state.entries.indexOf(entry) < 0) {
      return { ok: false, why: "the journal is full and could not keep that entry" };
    }
    if (!write(slug, state)) {
      return { ok: false, why: "this browser refused to store the journal" };
    }
    return { ok: true, duplicate: false, entry: entry, state: state };
  }

  function query(slug, topic) {
    var state = read(slug);
    var phrase = norm(topic);
    var want = keywords(topic);
    var rows = state.entries.map(function (entry) {
      var hay = tokens(entry.topic + " " + entry.text + " " + entry.source);
      var score = 0;
      if (!want.length) score = 1;
      want.forEach(function (t) {
        if (hay.indexOf(t) >= 0) score += 2;
      });
      if (phrase && (norm(entry.topic).indexOf(phrase) >= 0
                     || norm(entry.text + " " + entry.source).indexOf(phrase) >= 0)) {
        score += 4;
      }
      return { entry: entry, score: score };
    }).filter(function (row) { return row.score > 0; });
    rows.sort(function (a, b) {
      return b.score - a.score || b.entry.seq - a.entry.seq;
    });
    return {
      topic: oneLine(topic),
      matches: rows.map(function (row) { return row.entry; }),
      total: state.entries.length,
      state: state
    };
  }

  function entryLine(entry) {
    return "#" + entry.seq + " " + entry.kind + " · " + entry.topic + " · "
      + entry.text + " · via " + entry.source;
  }

  function answer(slug, topic) {
    var res = query(slug, topic);
    var t = oneLine(topic);
    if (!res.total) {
      return ["journal · empty",
        "nothing has been decided in this project yet",
        'try: build a platformer game, then ask "what did we decide about the art style?"'
      ].join("\n");
    }
    if (!res.matches.length) {
      var known = topics(slug);
      var lines = ['journal · nothing about "' + t + '" yet · '
        + res.total + " entr" + (res.total === 1 ? "y" : "ies") + " stored"];
      if (known.length) lines.push("known topics: " + known.join(", "));
      return lines.join("\n");
    }
    var out = ['journal · ' + res.matches.length + " match"
      + (res.matches.length === 1 ? "" : "es") + ' for "' + t + '" · '
      + res.total + " entr" + (res.total === 1 ? "y" : "ies") + " stored"];
    res.matches.slice(0, 12).forEach(function (entry) {
      out.push("  " + entryLine(entry));
    });
    if (res.matches.length > 12) {
      out.push("  · … " + (res.matches.length - 12) + " more");
    }
    return out.join("\n");
  }

  function summary(slug) {
    var state = read(slug);
    var out = {
      entries: state.entries.length,
      decisions: 0,
      rejections: 0,
      preferences: 0,
      dropped: state.dropped,
      bytes: size(state),
      cap: LIMIT.entries,
      byteCap: LIMIT.bytes
    };
    state.entries.forEach(function (entry) {
      out[entry.kind + "s"] += 1;
    });
    return out;
  }

  function text(slug) {
    var state = read(slug);
    if (!state.entries.length) {
      return ["journal · empty",
        "cap " + LIMIT.entries + " entries · " + LIMIT.bytes + " bytes",
        "nothing has been decided in this project yet"].join("\n");
    }
    var counts = summary(slug);
    var lines = [
      "journal · " + counts.entries + " entr"
        + (counts.entries === 1 ? "y" : "ies")
        + " · " + counts.decisions + " decision"
        + (counts.decisions === 1 ? "" : "s")
        + " · " + counts.rejections + " rejection"
        + (counts.rejections === 1 ? "" : "s")
        + " · " + counts.preferences + " preference"
        + (counts.preferences === 1 ? "" : "s"),
      "cap " + LIMIT.entries + " entries · " + LIMIT.bytes + " bytes · stored "
        + counts.bytes + " bytes · dropped " + counts.dropped,
      "(newest first)"
    ];
    state.entries.slice().reverse().forEach(function (entry) {
      lines.push("  " + entryLine(entry));
    });
    if (state.notes.length) {
      lines.push("notes (oldest first):");
      state.notes.forEach(function (note) {
        lines.push("  · #" + note.seq + " " + note.kind + " " + note.topic
          + " · " + note.why);
      });
    } else {
      lines.push("notes: none");
    }
    return lines.join("\n");
  }

  function topics(slug) {
    var seen = {};
    read(slug).entries.forEach(function (entry) { seen[entry.topic] = true; });
    return Object.keys(seen).sort();
  }

  function clear(slug) {
    try {
      root.localStorage.removeItem(keyFor(slug));
      forgetScope(slug);
      return true;
    } catch (e) {
      return false;
    }
  }

  function clearAll() {
    var list = readIndex();
    list.forEach(function (slug) {
      try { root.localStorage.removeItem(keyFor(slug)); } catch (e) { /* ignore */ }
    });
    try { root.localStorage.removeItem(INDEX_KEY); } catch (e) { /* ignore */ }
    return list.length;
  }

  function exportFor(slug) {
    return read(slug).entries.map(function (entry) {
      return {
        seq: entry.seq, kind: entry.kind, topic: entry.topic,
        text: entry.text, source: entry.source, n: entry.n
      };
    });
  }

  function importFor(slug, entries) {
    var state = emptyState(slug);
    if (Array.isArray(entries)) {
      entries.forEach(function (raw) {
        var entry = cleanEntry(raw);
        if (!entry) return;
        state.seq = Math.max(state.seq, entry.seq);
        state.entries.push(entry);
      });
      if (state.entries.length) state.seq += 1;
    }
    fit(state);
    if (!write(slug, state)) return null;
    return state;
  }

  root.toolrxJournal = {
    PREFIX: PREFIX,
    VERSION: VERSION,
    KINDS: KINDS,
    LIMIT: LIMIT,
    byteLength: byteLength,
    read: read,
    add: add,
    query: query,
    answer: answer,
    text: text,
    summary: summary,
    topics: topics,
    clear: clear,
    clearAll: clearAll,
    exportFor: exportFor,
    importFor: importFor,
    entryLine: entryLine
  };
})(typeof self !== "undefined" ? self : this);

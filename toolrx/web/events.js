/* toolrx deterministic operator event log (step 65).
 *
 * One small, inspectable stream of the decisions the stored records already
 * made: context compaction, plan rewriting, repair, resume, and refusal. Each
 * event names the route that produced it and carries the timestamp the caller
 * supplied; this module never reads the clock, the DOM, or the network.
 *
 * Three explicit limits bound the log: `eventEntries`, `eventBytes`, and
 * `eventText`. The oldest events are dropped at a cap and the count is kept in
 * the record, so the stream never pretends it kept more than it did.
 *
 * The sandbox derives events from stored records (the compaction report, the
 * stored plan variant, the repair/resume record, and the last run) and calls
 * `add`; the dashboard only renders what is stored here.
 */
(function (root) {
  "use strict";

  var PREFIX = "toolrx.events.v1.";
  var INDEX_KEY = PREFIX + "index";
  var VERSION = 1;
  var KINDS = ["compact", "rewrite", "repair", "resume", "refusal"];
  var LIMIT = (function () {
    if (!root.toolrxLimits) {
      throw new Error("toolrx/web/limits.js must load before events.js");
    }
    return {
      entries: root.toolrxLimits.eventEntries,
      bytes: root.toolrxLimits.eventBytes,
      text: root.toolrxLimits.eventText
    };
  })();

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

  function number(value, fallback) {
    var n = parseInt(value, 10);
    return isFinite(n) && n >= 0 ? n : fallback;
  }

  function cleanEvent(raw) {
    if (!raw || typeof raw !== "object") return null;
    var kind = String(raw.kind || "");
    if (KINDS.indexOf(kind) < 0) return null;
    var route = oneLine(raw.route).slice(0, 80);
    var text = trimToBytes(oneLine(raw.text), LIMIT.text);
    if (!route || !text) return null;
    return {
      seq: number(raw.seq, 0),
      at: number(raw.at, 0),
      kind: kind,
      route: route,
      text: text
    };
  }

  function emptyState(slug) {
    return {
      version: VERSION,
      project: String(slug || "").trim() || "scratch",
      seq: 0,
      entries: [],
      dropped: 0
    };
  }

  function read(slug) {
    var state = emptyState(slug);
    try {
      var raw = root.localStorage && root.localStorage.getItem(keyFor(slug));
      var parsed = raw ? JSON.parse(raw) : null;
      if (!parsed || parsed.version !== VERSION || !Array.isArray(parsed.entries)) {
        return state;
      }
      state.seq = number(parsed.seq, 0);
      state.dropped = number(parsed.dropped, 0);
      parsed.entries.forEach(function (entry) {
        var clean = cleanEvent(entry);
        if (!clean) return;
        state.entries.push(clean);
        if (clean.seq > state.seq) state.seq = clean.seq;
      });
      state.entries.sort(function (a, b) { return a.seq - b.seq; });
      return state;
    } catch (e) {
      return state;
    }
  }

  /* Drop the oldest events until both the entry count and the serialized
   * bytes fit. The count of dropped events is kept, never hidden. */
  function fit(state) {
    var dropped = 0;
    var drop = function () {
      state.entries.shift();
      state.dropped += 1;
      dropped += 1;
    };
    while (state.entries.length > LIMIT.entries) drop();
    while (state.entries.length
           && byteLength(JSON.stringify(state)) > LIMIT.bytes) drop();
    return dropped;
  }

  function write(slug, state) {
    try {
      root.localStorage.setItem(keyFor(slug), JSON.stringify(state));
      return true;
    } catch (e) {
      return false;
    }
  }

  function add(slug, event) {
    var clean = cleanEvent(event);
    if (!clean) {
      return { ok: false, why: "an event needs a known kind, a route, and text" };
    }
    var state = read(slug);
    var last = state.entries[state.entries.length - 1];
    if (last && last.kind === clean.kind && last.route === clean.route
        && last.text === clean.text) {
      return { ok: true, duplicate: true, event: last, count: state.entries.length };
    }
    state.seq += 1;
    clean.seq = state.seq;
    state.entries.push(clean);
    var dropped = fit(state);
    var ok = write(slug, state);
    return {
      ok: ok,
      event: clean,
      count: state.entries.length,
      dropped: dropped,
      totalDropped: state.dropped
    };
  }

  function list(slug) {
    return read(slug).entries.map(function (entry) {
      return {
        seq: entry.seq, at: entry.at, kind: entry.kind,
        route: entry.route, text: entry.text
      };
    });
  }

  function stamp(at) {
    if (!at) return "no timestamp";
    try { return new Date(at).toISOString(); }
    catch (e) { return "no timestamp"; }
  }

  function text(slug) {
    var state = read(slug);
    var lines = [
      "event stream · project: " + state.project,
      "cap " + LIMIT.entries + " entries · " + LIMIT.bytes + " bytes · "
        + LIMIT.text + " chars per event"
    ];
    if (!state.entries.length) {
      lines.push("no operator events yet · compaction, rewrite, repair, "
        + "resume, and refusal appear here");
    } else {
      state.entries.forEach(function (entry) {
        lines.push("#" + entry.seq + " · " + stamp(entry.at) + " · "
          + entry.kind + " · " + entry.route + " · " + entry.text);
      });
    }
    if (state.dropped) {
      lines.push("dropped " + state.dropped + " older event(s) at the "
        + "eventEntries/eventBytes cap");
    }
    return lines.join("\n");
  }

  function summary(slug) {
    var state = read(slug);
    return {
      version: VERSION,
      project: state.project,
      count: state.entries.length,
      dropped: state.dropped,
      cap: { entries: LIMIT.entries, bytes: LIMIT.bytes, text: LIMIT.text },
      entries: list(slug)
    };
  }

  function exportFor(slug) {
    return list(slug);
  }

  function importFor(slug, entries) {
    var state = emptyState(slug);
    var listIn = Array.isArray(entries) ? entries : [];
    listIn.forEach(function (raw) {
      var clean = cleanEvent(raw);
      if (!clean) return;
      state.entries.push(clean);
      if (clean.seq > state.seq) state.seq = clean.seq;
    });
    state.entries.sort(function (a, b) { return a.seq - b.seq; });
    if (state.entries.length > state.seq) state.seq = state.entries.length;
    var dropped = fit(state);
    var ok = write(slug, state);
    return {
      ok: ok,
      count: state.entries.length,
      dropped: dropped,
      totalDropped: state.dropped
    };
  }

  function clear(slug) {
    try { root.localStorage.removeItem(keyFor(slug)); } catch (e) { /* ignore */ }
  }

  function index() {
    try {
      var raw = root.localStorage && root.localStorage.getItem(INDEX_KEY);
      var parsed = raw ? JSON.parse(raw) : null;
      return parsed && Array.isArray(parsed) ? parsed.slice() : [];
    } catch (e) {
      return [];
    }
  }

  root.toolrxEvents = {
    VERSION: VERSION,
    KINDS: KINDS,
    LIMIT: LIMIT,
    keyFor: keyFor,
    byteLength: byteLength,
    add: add,
    list: list,
    text: text,
    summary: summary,
    exportFor: exportFor,
    importFor: importFor,
    clear: clear,
    index: index
  };
})(typeof self !== "undefined" ? self : this);

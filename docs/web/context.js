/* toolrx deterministic context store.
 *
 * Step 31 keeps a small, inspectable working memory per project: the last
 * result, the last plan, the active build spec, a summary + hash for every
 * project file, and a rolling list of recent steps. It is deliberately plain:
 * entries live in localStorage under one key per project, serialize with
 * sorted keys, and carry a monotonic sequence number instead of wall-clock
 * timestamps so the stored bytes are reproducible.
 *
 * Nothing here performs I/O beyond localStorage. Context is never passed to
 * fetch, the router, or the optional LLM adapter.
 *
 * Exposes: self.toolrxContext = {
 *   LIMIT, PREFIX, byteLength, stable, fingerprint,
 *   read, raw, set, setMany, get, remove, clear, clearAll, scopes,
 *   show, report, empty, snapshot, diff, notes
 * }
 */
(function (root) {
  "use strict";

  var PREFIX = "toolrx.context.v1.";
  var INDEX_KEY = PREFIX + "index";
  var VERSION = 1;
  var LIMIT = (function () {
    if (!root.toolrxLimits) {
      throw new Error("toolrx/web/limits.js must load before context.js");
    }
    return root.toolrxLimits.contextBytes;
  })();
  var NOTE_MAX = 3;
  var OVERHEAD = 300;

  function cap() {
    var n = LIMIT;
    try {
      var raw = root.localStorage && root.localStorage.getItem("toolrx.context.cap");
      var parsed = parseInt(raw, 10);
      if (!isNaN(parsed)) n = parsed;
    } catch (e) { /* private mode */ }
    return Math.max(256, Math.min(65536, n));
  }

  function byteLength(text) {
    var s = String(text == null ? "" : text);
    if (typeof TextEncoder !== "undefined") {
      return new TextEncoder().encode(s).length;
    }
    var n = 0;
    for (var i = 0; i < s.length; i++) {
      var code = s.charCodeAt(i);
      if (code < 0x80) n += 1;
      else if (code < 0x800) n += 2;
      else if (code >= 0xD800 && code <= 0xDBFF
               && i + 1 < s.length
               && s.charCodeAt(i + 1) >= 0xDC00 && s.charCodeAt(i + 1) <= 0xDFFF) {
        n += 4;
        i++;
      } else n += 3;
    }
    return n;
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

  /* JSON with object keys sorted at every level. Arrays keep their order so
   * entries and eviction notes remain chronologically meaningful. */
  function stable(value) {
    if (value === null || value === undefined) return "null";
    if (Array.isArray(value)) {
      return "[" + value.map(stable).join(",") + "]";
    }
    if (typeof value === "object") {
      return "{" + Object.keys(value).sort().map(function (key) {
        return JSON.stringify(key) + ":" + stable(value[key]);
      }).join(",") + "}";
    }
    return JSON.stringify(value);
  }

  function fingerprint(text) {
    var s = String(text == null ? "" : text);
    if (root.blake2bHex) {
      try { return root.blake2bHex(s, null, 8); } catch (e) { /* fall through */ }
    }
    // Small deterministic fallback for environments without blake2b.
    var h1 = 0x811c9dc5, h2 = 0x1000193;
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0;
      h2 = Math.imul(h2 + c, 0x85ebca6b) >>> 0;
    }
    return ("00000000" + h1.toString(16)).slice(-8)
      + ("00000000" + h2.toString(16)).slice(-8);
  }

  function empty(slug) {
    return {
      version: VERSION,
      project: String(slug || "scratch"),
      seq: 0,
      entries: []
    };
  }

  function cleanEntry(entry) {
    if (!entry || typeof entry !== "object") return null;
    if (typeof entry.kind !== "string" || typeof entry.key !== "string") return null;
    var seq = parseInt(entry.seq, 10);
    return {
      kind: entry.kind.slice(0, 40),
      key: entry.key.slice(0, 80),
      text: String(entry.text == null ? "" : entry.text),
      seq: isNaN(seq) ? 0 : seq
    };
  }

  function sanitize(parsed, slug) {
    if (!parsed || parsed.version !== VERSION) return empty(slug);
    var state = empty(slug);
    state.seq = Math.max(0, parseInt(parsed.seq, 10) || 0);
    var seen = {};
    (Array.isArray(parsed.entries) ? parsed.entries : []).forEach(function (raw) {
      var entry = cleanEntry(raw);
      if (!entry) return;
      var id = entry.kind + "\u0000" + entry.key;
      if (seen[id]) return;
      seen[id] = true;
      state.entries.push(entry);
      if (entry.seq > state.seq) state.seq = entry.seq;
    });
    return state;
  }

  function keyFor(slug) {
    return PREFIX + String(slug || "scratch");
  }

  function read(slug) {
    try {
      var raw = root.localStorage && root.localStorage.getItem(keyFor(slug));
      if (!raw) return empty(slug);
      return sanitize(JSON.parse(raw), slug);
    } catch (e) {
      return empty(slug);
    }
  }

  function raw(slug) {
    try {
      return root.localStorage ? root.localStorage.getItem(keyFor(slug)) || "" : "";
    } catch (e) {
      return "";
    }
  }

  function readIndex() {
    try {
      var raw = root.localStorage && root.localStorage.getItem(INDEX_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(parsed)) return [];
      return parsed.map(function (s) { return String(s); })
        .filter(function (s, i, all) { return s && all.indexOf(s) === i; })
        .sort();
    } catch (e) {
      return [];
    }
  }

  function writeIndex(list) {
    try {
      root.localStorage.setItem(INDEX_KEY, stable(list.slice().sort()));
    } catch (e) { /* ignore */ }
  }

  function addScope(slug) {
    var list = readIndex();
    if (list.indexOf(slug) < 0) {
      list.push(slug);
      writeIndex(list);
    }
  }

  function dropScope(slug) {
    writeIndex(readIndex().filter(function (s) { return s !== slug; }));
  }

  function write(slug, state) {
    try {
      root.localStorage.setItem(keyFor(slug), stable(state));
      addScope(slug);
      return true;
    } catch (e) {
      return false;
    }
  }

  function entryBytes(entries) {
    return entries.reduce(function (total, entry) {
      return total + byteLength(entry.text);
    }, 0);
  }

  function notesKey(slug) { return keyFor(slug) + ".notes"; }

  function readNotes(slug) {
    try {
      var raw = root.localStorage && root.localStorage.getItem(notesKey(slug));
      var parsed = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(parsed)) return [];
      return parsed.filter(function (note) {
        return note && typeof note.kind === "string" && typeof note.key === "string";
      }).slice(-NOTE_MAX).map(function (note) {
        return {
          kind: String(note.kind).slice(0, 40),
          key: String(note.key).slice(0, 80),
          bytes: Math.max(0, parseInt(note.bytes, 10) || 0),
          why: note.why === "trimmed" ? "trimmed" : "evicted"
        };
      });
    } catch (e) {
      return [];
    }
  }

  function writeNotes(slug, notes) {
    try {
      if (!notes.length) root.localStorage.removeItem(notesKey(slug));
      else root.localStorage.setItem(notesKey(slug), stable(notes.slice(-NOTE_MAX)));
    } catch (e) { /* ignore */ }
  }

  function addNotes(slug, list) {
    if (!list.length) return;
    var notes = readNotes(slug).concat(list.map(function (entry) {
      return {
        kind: entry.kind,
        key: entry.key,
        bytes: entry.bytes != null ? entry.bytes : byteLength(entry.text),
        why: entry.why || "evicted"
      };
    }));
    writeNotes(slug, notes);
  }

  function serializedBytes(state) {
    return byteLength(stable(state));
  }

  function fit(state, limit) {
    var evicted = [];
    while (serializedBytes(state) > limit && state.entries.length) {
      var oldest = 0;
      for (var i = 1; i < state.entries.length; i++) {
        if (state.entries[i].seq < state.entries[oldest].seq) oldest = i;
      }
      evicted.push(state.entries.splice(oldest, 1)[0]);
    }
    return evicted;
  }

  /* setMany accepts [{kind,key,text}] and applies them in order. When
   * opts.kind is set, entries of that kind that are not present are removed;
   * unchanged entries keep their old sequence number, so repeated captures do
   * not rewrite stable bytes. Eviction and trim notes live beside the capped
   * state so the stored context itself stays within the byte cap. */
  function setMany(slug, items, opts) {
    opts = opts || {};
    var state = read(slug);
    var limit = cap();
    var evicted = [];
    var notes = [];
    var trimmed = [];
    var wanted = {};

    items.forEach(function (item) {
      if (!item) return;
      wanted[String(item.kind) + "\u0000" + String(item.key)] = true;
    });

    if (opts.kind) {
      state.entries = state.entries.filter(function (entry) {
        if (entry.kind !== opts.kind) return true;
        return !!wanted[entry.kind + "\u0000" + entry.key];
      });
    }

    items.forEach(function (item) {
      if (!item) return;
      var kind = String(item.kind || "").slice(0, 40);
      var key = String(item.key || "").slice(0, 80);
      if (!kind || !key) return;
      var text = String(item.text == null ? "" : item.text);
      var existing = null;
      for (var i = 0; i < state.entries.length; i++) {
        if (state.entries[i].kind === kind && state.entries[i].key === key) {
          existing = i;
          break;
        }
      }
      if (existing !== null && state.entries[existing].text === text) return;
      if (existing !== null) state.entries.splice(existing, 1);
      var max = Math.max(32, limit - OVERHEAD);
      if (byteLength(text) > max) {
        var original = byteLength(text);
        text = trimToBytes(text, max) + "\n… [trimmed for context]";
        notes.push({ kind: kind, key: key, bytes: original, why: "trimmed" });
        trimmed.push({ kind: kind, key: key, bytes: original });
      }
      state.seq += 1;
      state.entries.push({ kind: kind, key: key, text: text, seq: state.seq });
    });

    evicted = fit(state, limit);
    var ok = (items.length === 0 && state.entries.length === 0)
      ? (function () {
          try { root.localStorage.removeItem(keyFor(slug)); } catch (e) { /* ignore */ }
          writeNotes(slug, []);
          removeSnapshot(slug);
          removePlanNote(slug);
          dropScope(slug);
          return true;
        })()
      : write(slug, state);
    notes = notes.concat(evicted.map(function (entry) {
      return { kind: entry.kind, key: entry.key, bytes: byteLength(entry.text), why: "evicted" };
    }));
    addNotes(slug, notes);
    var planNote = null;
    notes.forEach(function (note) {
      if (note.kind === "plan" && note.key === "last") planNote = note;
    });
    var wrotePlan = items.some(function (item) {
      return item && item.kind === "plan" && item.key === "last";
    });
    var removedPlan = opts.kind === "plan"
      && !wanted["plan\u0000last"];
    if (planNote) writePlanNote(slug, planNote);
    else if (wrotePlan || removedPlan) removePlanNote(slug);
    return {
      ok: ok,
      bytes: entryBytes(state.entries),
      stored: serializedBytes(state),
      entries: state.entries.length,
      evicted: evicted,
      trimmed: trimmed,
      limit: limit
    };
  }

  function set(slug, kind, key, text) {
    return setMany(slug, [{ kind: kind, key: key, text: text }]);
  }

  function get(slug, kind, key) {
    var state = read(slug);
    for (var i = 0; i < state.entries.length; i++) {
      if (state.entries[i].kind === kind && state.entries[i].key === key) {
        return state.entries[i].text;
      }
    }
    return "";
  }

  function remove(slug, kind, key) {
    var state = read(slug);
    var before = state.entries.length;
    state.entries = state.entries.filter(function (entry) {
      return !(entry.kind === kind && entry.key === key);
    });
    if (state.entries.length === before) return false;
    if (!state.entries.length) {
      clear(slug);
      return true;
    }
    write(slug, state);
    return true;
  }

  function clear(slug) {
    try { root.localStorage.removeItem(keyFor(slug)); } catch (e) { /* ignore */ }
    try { root.localStorage.removeItem(notesKey(slug)); } catch (e) { /* ignore */ }
    removeSnapshot(slug);
    removePlanNote(slug);
    dropScope(slug);
    return true;
  }

  function clearAll() {
    var scopes = readIndex();
    var count = 0;
    scopes.forEach(function (slug) {
      try {
        root.localStorage.removeItem(keyFor(slug));
        root.localStorage.removeItem(notesKey(slug));
        removeSnapshot(slug);
        removePlanNote(slug);
        count++;
      } catch (e) { /* ignore */ }
    });
    try { root.localStorage.removeItem(INDEX_KEY); } catch (e) { /* ignore */ }
    return count;
  }

  /* Step 39: deterministic snapshots and diffs. A snapshot stores only the
   * entry shapes, byte counts, hashes, eviction notes, and pending plan steps;
   * the context text itself is not duplicated. Snapshots live beside the
   * context under one key per project, so they never enter a network request
   * and never leak across projects. */
  function snapshotKey(slug) { return keyFor(slug) + ".snapshot"; }
  function planNoteKey(slug) { return keyFor(slug) + ".plan-note"; }

  /* The general eviction ring keeps only the newest few notes. A plan is
   * special: losing it makes continuation impossible, so its last trim or
   * eviction is kept in a dedicated marker until a new plan replaces it. */
  function readPlanNote(slug) {
    try {
      var raw = root.localStorage && root.localStorage.getItem(planNoteKey(slug));
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed || parsed.kind !== "plan" || parsed.key !== "last") return null;
      return {
        kind: "plan", key: "last",
        bytes: Math.max(0, parseInt(parsed.bytes, 10) || 0),
        why: parsed.why === "trimmed" ? "trimmed" : "evicted"
      };
    } catch (e) {
      return null;
    }
  }

  function writePlanNote(slug, note) {
    try {
      root.localStorage.setItem(planNoteKey(slug), stable({
        kind: "plan", key: "last", bytes: note.bytes,
        why: note.why === "trimmed" ? "trimmed" : "evicted"
      }));
    } catch (e) { /* ignore */ }
  }

  function removePlanNote(slug) {
    try { root.localStorage.removeItem(planNoteKey(slug)); } catch (e) { /* ignore */ }
  }

  function sortedEntries(state) {
    return state.entries.slice().sort(function (a, b) {
      if (a.kind !== b.kind) return a.kind < b.kind ? -1 : 1;
      if (a.key !== b.key) return a.key < b.key ? -1 : 1;
      return a.seq - b.seq;
    });
  }

  function planPending(state) {
    for (var i = 0; i < state.entries.length; i++) {
      var entry = state.entries[i];
      if (entry.kind !== "plan" || entry.key !== "last") continue;
      try {
        var plan = JSON.parse(entry.text);
        var steps = Array.isArray(plan.steps) ? plan.steps : [];
        var status = Array.isArray(plan.status) ? plan.status : [];
        var pending = [];
        for (var j = 0; j < steps.length; j++) {
          if (status[j] === "pending") pending.push(String(steps[j]));
        }
        return { steps: pending, total: steps.length, status: status };
      } catch (e) {
        return { steps: [], total: 0, status: [], broken: true };
      }
    }
    return { steps: [], total: 0, status: [] };
  }

  function shape(state, stored) {
    var entries = sortedEntries(state).map(function (entry) {
      return {
        kind: entry.kind,
        key: entry.key,
        seq: entry.seq,
        bytes: byteLength(entry.text),
        sha: fingerprint(entry.text)
      };
    });
    var plan = planPending(state);
    return {
      version: VERSION,
      project: state.project,
      seq: state.seq,
      entries: entries,
      bytes: entryBytes(state.entries),
      stored: byteLength(stored),
      sha: fingerprint(stored),
      pending: plan.steps,
      pendingTotal: plan.total,
      planBroken: !!plan.broken,
      notes: notes(state.project)
    };
  }

  function readSnapshot(slug) {
    try {
      var raw = root.localStorage && root.localStorage.getItem(snapshotKey(slug));
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed || parsed.version !== VERSION || !Array.isArray(parsed.entries)) {
        return null;
      }
      return parsed;
    } catch (e) {
      return null;
    }
  }

  function removeSnapshot(slug) {
    try { root.localStorage.removeItem(snapshotKey(slug)); } catch (e) { /* ignore */ }
  }

  function delta(before, after) {
    var n = after - before;
    return n > 0 ? "+" + n : String(n);
  }

  function pendingDiff(before, after) {
    var removed = [], added = [], counts = {}, i;
    for (i = 0; i < before.length; i++) {
      counts["-" + before[i]] = (counts["-" + before[i]] || 0) + 1;
    }
    for (i = 0; i < after.length; i++) {
      var key = "-" + after[i];
      if (counts[key]) counts[key]--;
      else added.push(after[i]);
    }
    counts = {};
    for (i = 0; i < after.length; i++) {
      counts["+" + after[i]] = (counts["+" + after[i]] || 0) + 1;
    }
    for (i = 0; i < before.length; i++) {
      var pkey = "+" + before[i];
      if (counts[pkey]) counts[pkey]--;
      else removed.push(before[i]);
    }
    return { removed: removed, added: added };
  }

  function notesDiff(before, after) {
    var b = {}, a = {}, i;
    for (i = 0; i < before.length; i++) {
      b[before[i].kind + "\u0000" + before[i].key] = before[i];
    }
    for (i = 0; i < after.length; i++) {
      a[after[i].kind + "\u0000" + after[i].key] = after[i];
    }
    var added = [], removed = [];
    for (i = 0; i < after.length; i++) {
      var n = after[i];
      if (!b[n.kind + "\u0000" + n.key]) added.push(n);
    }
    for (i = 0; i < before.length; i++) {
      var o = before[i];
      if (!a[o.kind + "\u0000" + o.key]) removed.push(o);
    }
    return { added: added, removed: removed };
  }

  function snapshotText(snap, saved) {
    var lines = [
      "context snapshot · project: " + snap.project,
      snap.entries.length + " entries · " + snap.bytes + " entry bytes · stored "
        + snap.stored + " bytes · sha " + snap.sha
    ];
    if (snap.planBroken) {
      lines.push("pending plan: unreadable (the stored plan was trimmed or evicted)");
    } else {
      lines.push("pending plan: " + snap.pending.length + " step"
        + (snap.pending.length === 1 ? "" : "s"));
      snap.pending.forEach(function (step) { lines.push("  · " + step); });
    }
    if (snap.notes.length) {
      lines.push("evicted or trimmed (oldest first):");
      snap.notes.forEach(function (note) {
        lines.push("  " + note.kind + "/" + note.key + " · " + note.bytes
          + " bytes · " + note.why);
      });
    }
    if (saved) lines.push("saved as the previous context snapshot");
    return lines.join("\n");
  }

  function snapshot(slug) {
    var state = read(slug);
    var snap = shape(state, raw(slug));
    try {
      root.localStorage.setItem(snapshotKey(slug), stable(snap));
      addScope(state.project);
    } catch (e) {
      return { ok: false, snapshot: snap,
               text: "could not save the context snapshot (storage is unavailable)" };
    }
    return { ok: true, snapshot: snap, text: snapshotText(snap, true) };
  }

  function diff(slug) {
    var prior = readSnapshot(slug);
    if (!prior) {
      return { ok: false, snapshot: null,
               text: "no previous context snapshot · say context snapshot first" };
    }
    var state = read(slug);
    var current = shape(state, raw(slug));
    var before = {}, after = {}, i;
    for (i = 0; i < prior.entries.length; i++) {
      var pe = prior.entries[i];
      before[pe.kind + "\u0000" + pe.key] = pe;
    }
    for (i = 0; i < current.entries.length; i++) {
      var ce = current.entries[i];
      after[ce.kind + "\u0000" + ce.key] = ce;
    }
    var added = [], removed = [], changed = [];
    for (i = 0; i < current.entries.length; i++) {
      var now = current.entries[i];
      var old = before[now.kind + "\u0000" + now.key];
      if (!old) added.push(now);
      else if (old.sha !== now.sha || old.bytes !== now.bytes) {
        changed.push({ before: old, after: now });
      }
    }
    for (i = 0; i < prior.entries.length; i++) {
      var gone = prior.entries[i];
      if (!after[gone.kind + "\u0000" + gone.key]) removed.push(gone);
    }

    var lines = [
      "context diff · project: " + current.project,
      "snapshot: " + prior.entries.length + " entries · " + prior.bytes
        + " bytes · stored " + prior.stored + " bytes · sha " + prior.sha,
      "current:  " + current.entries.length + " entries · " + current.bytes
        + " bytes · stored " + current.stored + " bytes · sha " + current.sha
    ];
    if (!added.length && !removed.length && !changed.length) {
      lines.push("entries: no changes");
    } else {
      lines.push("entries: " + added.length + " added · " + removed.length
        + " removed · " + changed.length + " changed");
      added.forEach(function (entry) {
        lines.push("  + " + entry.kind + "/" + entry.key + " · " + entry.bytes
          + " bytes · sha " + entry.sha);
      });
      removed.forEach(function (entry) {
        lines.push("  - " + entry.kind + "/" + entry.key + " · " + entry.bytes
          + " bytes · sha " + entry.sha);
      });
      changed.forEach(function (pair) {
        lines.push("  ~ " + pair.after.kind + "/" + pair.after.key + " · "
          + pair.before.bytes + " -> " + pair.after.bytes + " bytes · sha "
          + pair.before.sha + " -> " + pair.after.sha);
      });
    }
    lines.push("bytes: " + delta(prior.bytes, current.bytes) + " entry · "
      + delta(prior.stored, current.stored) + " stored");

    var pending = pendingDiff(prior.pending || [], current.pending || []);
    lines.push("pending plan: " + (prior.pending || []).length + " -> "
      + (current.pending || []).length);
    pending.removed.forEach(function (step) { lines.push("  - " + step); });
    pending.added.forEach(function (step) { lines.push("  + " + step); });
    if (current.planBroken) {
      lines.push("  ! the current stored plan is unreadable (trimmed or evicted)");
    }

    var notes = notesDiff(prior.notes || [], current.notes || []);
    if (notes.added.length || notes.removed.length) {
      lines.push("evicted or trimmed: " + notes.added.length + " added · "
        + notes.removed.length + " removed");
      notes.added.forEach(function (note) {
        lines.push("  + " + note.kind + "/" + note.key + " · " + note.bytes
          + " bytes · " + note.why);
      });
      notes.removed.forEach(function (note) {
        lines.push("  - " + note.kind + "/" + note.key + " · " + note.bytes
          + " bytes · " + note.why);
      });
    }
    return { ok: true, snapshot: prior, current: current, text: lines.join("\n") };
  }

  function notes(slug) {
    var list = readNotes(slug).slice();
    var marker = readPlanNote(slug);
    if (marker && !list.some(function (note) {
      return note.kind === "plan" && note.key === "last";
    })) {
      list.push(marker);
    }
    return list;
  }

  function label(entry) {
    if (entry.kind === "result") return "last result";
    if (entry.kind === "plan") return "last plan";
    if (entry.kind === "session") return "session plan";
    if (entry.kind === "spec") return "build spec";
    if (entry.kind === "edit") return "last edit";
    if (entry.kind === "file") return "file " + entry.key;
    return entry.kind + "/" + entry.key;
  }

  function firstLine(text) {
    var lines = String(text == null ? "" : text).split(/\n/);
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (line) return line.length > 110 ? line.slice(0, 107) + "…" : line;
    }
    return "(empty)";
  }

  function describe(entry) {
    if (entry.kind === "plan") {
      try {
        var plan = JSON.parse(entry.text);
        var steps = plan.steps || [];
        var done = (plan.status || []).filter(function (s) { return s === "done"; }).length;
        var errors = (plan.status || []).filter(function (s) { return s === "error"; }).length;
        var pending = (plan.status || []).filter(function (s) { return s === "pending"; }).length;
        return plan.steps.length + " steps · " + done + " done · " + errors
          + " error · " + pending + " pending";
      } catch (e) { /* fall through */ }
    }
    if (entry.kind === "session") {
      var rows = entry.text.split("\n").filter(Boolean);
      return rows.length + " recent step" + (rows.length === 1 ? "" : "s")
        + (rows.length ? " · last: " + firstLine(rows[rows.length - 1]) : "");
    }
    if (entry.kind === "edit") {
      try {
        var record = JSON.parse(entry.text);
        var labels = record.labels || record.ids || [];
        if (labels.length) return labels.join(" + ");
      } catch (e) { /* fall through */ }
    }
    return firstLine(entry.text);
  }

  function show(slug) {
    var state = read(slug);
    var stored = raw(slug);
    var notes = readNotes(slug);
    var entries = state.entries.slice().sort(function (a, b) { return a.seq - b.seq; });
    var bytes = entryBytes(entries);
    var lines = [];
    lines.push("context · project: " + state.project);
    lines.push("cap " + cap() + " bytes · " + entries.length + " entries · "
      + bytes + " entry bytes");
    lines.push("stored: " + byteLength(stored) + " bytes · sha " + fingerprint(stored));
    if (!entries.length) {
      lines.push("(empty — build something or run a command to fill it)");
    }
    entries.forEach(function (entry) {
      lines.push(label(entry) + " · " + byteLength(entry.text) + " bytes · seq "
        + entry.seq);
      lines.push("  " + describe(entry));
    });
    if (notes.length) {
      lines.push("evicted (oldest first): " + notes.map(function (note) {
        return note.kind + "/" + note.key + " · " + note.bytes + " bytes · " + note.why;
      }).join(" · "));
    }
    return {
      text: lines.join("\n"),
      project: state.project,
      entries: entries.length,
      bytes: bytes,
      stored: byteLength(stored),
      sha: fingerprint(stored),
      evicted: notes.length
    };
  }

  root.toolrxContext = {
    LIMIT: LIMIT,
    PREFIX: PREFIX,
    INDEX_KEY: INDEX_KEY,
    cap: cap,
    byteLength: byteLength,
    stable: stable,
    fingerprint: fingerprint,
    read: read,
    raw: raw,
    set: set,
    setMany: setMany,
    get: get,
    remove: remove,
    clear: clear,
    clearAll: clearAll,
    scopes: readIndex,
    show: function (slug) { return show(slug).text; },
    report: show,
    snapshot: snapshot,
    diff: diff,
    notes: notes,
    empty: empty
  };
})(typeof self !== "undefined" ? self : this);

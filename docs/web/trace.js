/* toolrx deterministic reasoning traces (step 55).
 *
 * One small, inspectable record of the thinking or repair pass that chose or
 * rejected a path. A trace names its route, decision, rule, source, and the
 * plan it examined; it never restates a whole answer and never reads the
 * clock. `traceBytes` is the only cap, and trimming is named in the record.
 *
 * No DOM, no network. The context store persists the record; this module only
 * shapes it.
 */
(function (root) {
  "use strict";

  var RULES = {
    "r.trace-cap": "a stored trace is bounded by traceBytes",
    "r.trace-trim": "an oversized trace is trimmed, not silently dropped",
    "r.trace-plan": "the trace is tied to the plan it examined",
    "r.trace-no-plan": "the trace examined no stored plan",
    "r.trace-none": "there is no stored trace",
    "r.trace-decision": "the decision is read from the output rule"
  };

  function rule(id) { return "· " + id; }

  function number(value, fallback) {
    var n = Number(value);
    return isFinite(n) && n >= 0 ? n : fallback;
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

  function ruleOf(text) {
    var found = String(text == null ? "" : text).match(/\br\.[a-z0-9-]+\b/g);
    return found && found.length ? found[found.length - 1] : "";
  }

  function lineAfter(text, pattern) {
    var lines = String(text == null ? "" : text).split("\n");
    for (var i = 0; i < lines.length; i++) {
      if (pattern.test(lines[i])) {
        return oneLine(lines[i].replace(pattern, ""));
      }
    }
    return "";
  }

  /* The decision is read from the same output the user saw: the repair line
   * for a critique, the recommendation for a trade-off, the goal or step
   * count for a decomposition. Nothing is invented. */
  function decisionOf(via, text) {
    var v = String(via == null ? "" : via);
    if (v === "think.critique") {
      var repair = lineAfter(text, /^repair:\s*/);
      if (repair) {
        return oneLine(repair.replace(/\s*·\s*r\.[a-z0-9-]+.*$/, ""))
          || "critique";
      }
      return "critique";
    }
    if (v === "think.tradeoff") {
      var rec = lineAfter(text, /^recommendation:\s*/)
        || lineAfter(text, /^verdict:\s*/);
      return rec
        ? oneLine(rec.replace(/\s*·\s*r\.[a-z0-9-]+.*$/, "")) || "trade-off"
        : "trade-off";
    }
    if (v === "think.decompose") {
      var goals = String(text == null ? "" : text)
        .match(/goals \((\d+) shown of (\d+)\)/);
      return goals ? "decompose " + goals[2] + " goal(s)" : "decompose";
    }
    if (v === "think.reason") {
      var steps = String(text == null ? "" : text)
        .match(/steps \((\d+) shown of (\d+)\)/);
      return steps ? "reason " + steps[2] + " step(s)" : "reason";
    }
    if (/^repair\./.test(v)) {
      return /(^|\n)repair: none\b/.test(String(text == null ? "" : text))
        ? "refuse" : "repair";
    }
    return v || "trace";
  }

  function decisionRuleOf(via, text) {
    var v = String(via == null ? "" : via);
    var prefixes = v === "think.critique" ? [/^repair:/]
      : v === "think.tradeoff" ? [/^recommendation:/, /^verdict:/]
      : [];
    var lines = String(text == null ? "" : text).split("\n");
    for (var i = 0; i < lines.length; i++) {
      for (var j = 0; j < prefixes.length; j++) {
        if (prefixes[j].test(lines[i])) {
          var found = ruleOf(lines[i]);
          if (found) return found;
        }
      }
    }
    return ruleOf(text);
  }

  /* record() shapes one trace. `text` is the visible output, trimmed to
   * `maxText`; the whole record is then checked against `maxBytes`. A record
   * that cannot fit even the minimum returns null, and the caller says so. */
  function record(input, opts) {
    var safe = input || {};
    var o = opts || {};
    var maxText = number(o.maxText, 2000) || 2000;
    var maxBytes = number(o.maxBytes, 2048) || 2048;
    var text = String(safe.text == null ? "" : safe.text);
    var trimmed = false;
    if (byteLength(text) > maxText) {
      text = trimToBytes(text, maxText) + "\n… [trimmed]";
      trimmed = true;
    }
    var doc = {
      version: 1,
      kind: "trace",
      key: "last",
      via: String(safe.via == null ? "" : safe.via).slice(0, 80),
      rule: String(safe.rule || ruleOf(text)).slice(0, 60),
      decision: oneLine(safe.decision || decisionOf(safe.via, text))
        .slice(0, 200),
      source: oneLine(safe.source).slice(0, 120),
      planSteps: (Array.isArray(safe.planSteps) ? safe.planSteps : [])
        .slice(0, 40).map(function (step) {
          return String(step == null ? "" : step).replace(/\s+/g, " ")
            .slice(0, 240);
        }),
      planSha: "",
      text: text,
      trimmed: trimmed,
      bytes: byteLength(text)
    };
    if (byteLength(JSON.stringify(doc)) > maxBytes) {
      var over = byteLength(JSON.stringify(doc)) - maxBytes;
      var room = byteLength(doc.text) - over - 32;
      if (room < 32) return null;
      doc.text = trimToBytes(doc.text, room) + "\n… [trimmed]";
      doc.trimmed = true;
      doc.bytes = byteLength(doc.text);
      if (byteLength(JSON.stringify(doc)) > maxBytes) return null;
    }
    return doc;
  }

  /* The plan hash is stamped by the context store, which is the only place
   * that knows the exact bytes of the stored plan entry. */
  function withPlan(doc, planSha) {
    if (!doc) return null;
    var out = {};
    Object.keys(doc).forEach(function (key) { out[key] = doc[key]; });
    out.planSha = String(planSha == null ? "" : planSha);
    return out;
  }

  function matches(doc, planSha) {
    if (!doc) return false;
    if (!doc.planSha) return true; // a trace of a literal, not of a plan
    return doc.planSha === String(planSha == null ? "" : planSha);
  }

  function text(doc) {
    if (!doc) return "trace · none " + rule("r.trace-none");
    var lines = [
      "trace · " + (doc.via || "?") + " · " + (doc.decision || "?")
        + " · " + (doc.rule || "no rule") + " " + rule("r.trace-decision")
    ];
    if (doc.source) lines.push("source: " + doc.source);
    if (doc.planSha) {
      lines.push("plan: " + doc.planSha.slice(0, 12) + " " + rule("r.trace-plan"));
    } else if (doc.planSteps && doc.planSteps.length) {
      lines.push("plan: not stored " + rule("r.trace-no-plan"));
    }
    lines.push("cap: " + (doc.bytes || 0) + " bytes stored"
      + (doc.trimmed ? " · trimmed " + rule("r.trace-trim")
        : " " + rule("r.trace-cap")));
    return lines.join("\n");
  }

  function summary(doc) {
    if (!doc) return null;
    return {
      via: doc.via,
      rule: doc.rule,
      decision: doc.decision,
      source: doc.source,
      planSha: doc.planSha,
      bytes: doc.bytes,
      trimmed: !!doc.trimmed
    };
  }

  root.toolrxTrace = {
    RULES: RULES,
    record: record,
    withPlan: withPlan,
    matches: matches,
    decisionOf: decisionOf,
    decisionRuleOf: decisionRuleOf,
    ruleOf: ruleOf,
    text: text,
    summary: summary,
    byteLength: byteLength
  };
})(typeof self !== "undefined" ? self : this);

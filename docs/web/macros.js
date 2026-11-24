/* toolrx named plan macros (step 67).
 *
 * One checked-in table, `toolrx/macros.json`, is the only source of the
 * `macro.*` routes and the expansion data. This module is the pure browser
 * twin of `toolrx/macros.py`: it expands a macro literally, never recursively,
 * and refuses with a named reason before anything runs.
 *
 * The existing plan limits do the work: `planSteps` caps the expanded step
 * count and `planChars` caps the joined text. No new cap and no new tool.
 */
(function (root) {
  "use strict";

  var DEFAULT_LIMITS = { steps: 40, chars: 8000, single: 2000 };

  var MACRO_INVOKE = new RegExp(
    "^\\s*(?:(?:run|use|invoke|apply|preview|show|expand)\\s+"
    + "(?:the\\s+)?macro\\b"
    + "|(?:run|use|invoke|apply|preview|show|expand)\\s+the\\s+.+?\\s+macro\\s*$"
    + "|macro\\b)", "i");
  var SPLIT = /\s*(?:\||;|\bthen\b|\n)\s*/i;

  function cp(text) {
    return Array.from(String(text == null ? "" : text)).length;
  }

  function cpSlice(text, max) {
    return Array.from(String(text == null ? "" : text)).slice(0, max).join("");
  }

  function one(text) {
    return String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  }

  function norm(text) {
    return one(text).toLowerCase();
  }

  function number(value, fallback) {
    var n = Number(value);
    if (!isFinite(n)) return fallback;
    n = Math.trunc(n);
    return n >= 1 ? n : 1;
  }

  function limits(input) {
    var raw = input || {};
    return {
      steps: number(raw.steps, DEFAULT_LIMITS.steps),
      chars: number(raw.chars, DEFAULT_LIMITS.chars),
      single: number(raw.single, DEFAULT_LIMITS.single)
    };
  }

  function macrosOf(table) {
    return (table && Array.isArray(table.macros)) ? table.macros : [];
  }

  function result(ok, name, steps, reason, detail, summary) {
    var clean = (steps || []).map(function (step) { return String(step); });
    return {
      ok: !!ok,
      name: String(name),
      summary: String(summary || ""),
      steps: clean,
      total: clean.length,
      chars: cp(clean.join("\n")),
      reason: reason || null,
      detail: String(detail || "")
    };
  }

  function parseSteps(text) {
    var raw = String(text == null ? "" : text).replace(/\r/g, "");
    return raw.split(SPLIT).map(function (part) {
      return part.trim();
    }).filter(Boolean);
  }

  function check(name, steps, limit) {
    var lim = limits(limit);
    var clean = (steps || []).map(function (step) { return String(step); });
    var total = clean.length;
    var joined = clean.join("\n");
    if (!total) {
      return result(false, name, clean, "r.macro-empty",
                    "a macro needs at least one step");
    }
    if (total > lim.steps) {
      return result(false, name, clean, "r.macro-steps",
                    total + " steps > planSteps " + lim.steps);
    }
    if (cp(joined) > lim.chars) {
      return result(false, name, clean, "r.macro-chars",
                    cp(joined) + " chars > planChars " + lim.chars);
    }
    for (var i = 0; i < clean.length; i++) {
      var step = clean[i];
      var n = i + 1;
      if (!step.trim()) {
        return result(false, name, clean, "r.macro-empty-step",
                      "step " + n + " is empty");
      }
      if (cp(step) > lim.single) {
        return result(false, name, clean, "r.macro-step-chars",
                      "step " + n + " is " + cp(step)
                      + " chars > singleChars " + lim.single);
      }
      if (MACRO_INVOKE.test(step)) {
        return result(false, name, clean, "r.macro-recursive",
                      "step " + n + " invokes another macro: "
                      + cpSlice(one(step), 120));
      }
    }
    return result(true, name, clean);
  }

  function find(table, name) {
    var key = norm(name);
    var macros = macrosOf(table);
    for (var i = 0; i < macros.length; i++) {
      var macro = macros[i];
      var phrases = [macro.name].concat(macro.aliases || []);
      for (var j = 0; j < phrases.length; j++) {
        if (norm(phrases[j]) === key) return macro;
      }
    }
    return null;
  }

  function expand(table, name, limit) {
    var macro = find(table, name);
    if (!macro) {
      return result(false, one(name), [], "r.macro-missing",
                    'no macro named "' + cpSlice(one(name), 120) + '"');
    }
    var out = check(macro.name, macro.steps, limit);
    out.summary = macro.summary;
    return out;
  }

  function refusalText(out) {
    var name = one(out && out.name || "macro");
    var reason = (out && out.reason) || "r.macro-refused";
    var detail = one(out && out.detail || "the macro could not be expanded");
    return [
      "macro · " + name + " · refused · " + reason,
      detail + " · " + reason,
      "nothing was run · r.macro-none"
    ].join("\n");
  }

  function previewText(out, limit) {
    if (!out || !out.ok) return refusalText(out);
    var lim = limits(limit);
    var lines = [
      "macro · " + one(out.name) + " · " + out.total + " steps · planSteps "
      + lim.steps + " · r.macro"
    ];
    if (out.summary) lines.push("summary: " + one(out.summary));
    out.steps.forEach(function (step, i) {
      lines.push("  " + (i + 1) + ". " + step);
    });
    lines.push("say yes to run exactly these steps, no to cancel, or edit "
               + "the macro plan to change the list · r.macro-preview");
    return lines.join("\n");
  }

  function editText(out, limit) {
    if (!out || !out.ok) return refusalText(out);
    var lines = [
      "macro plan · " + one(out.name) + " · edited · " + out.total
      + " steps · r.macro-edit"
    ];
    out.steps.forEach(function (step, i) {
      lines.push("  " + (i + 1) + ". " + step);
    });
    lines.push('the macro "' + one(out.name)
               + '" is unchanged · r.macro-immutable');
    lines.push("say yes to run exactly these steps, no to cancel · "
               + "r.macro-preview");
    return lines.join("\n");
  }

  function listText(table) {
    var macros = macrosOf(table);
    var lines = [
      "macros · " + macros.length
      + " named · literal, non-recursive expansion · r.macro-list"
    ];
    macros.forEach(function (macro) {
      lines.push("  " + macro.name + " · " + (macro.steps || []).length
                 + " steps · " + one(macro.summary));
    });
    lines.push("preview macro <name> · run macro <name> · edit the macro "
               + "plan to change a staged list");
    return lines.join("\n");
  }

  root.toolrxMacros = {
    DEFAULT_LIMITS: DEFAULT_LIMITS,
    parseSteps: parseSteps,
    check: check,
    expand: expand,
    previewText: previewText,
    editText: editText,
    listText: listText,
    refusalText: refusalText
  };
})(typeof self !== "undefined" ? self : this);

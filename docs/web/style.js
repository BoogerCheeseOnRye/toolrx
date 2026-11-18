/* Step 58: adaptive response style.
 *
 * One pure module. It adds wrapper text around an already-executed exact
 * result; it never chooses a tool, changes an argument, touches a file, or
 * rewrites an error. `sandbox.prompt` applies it only after the whole plan has
 * run, so a style can never affect a chained step.
 */
(function (root) {
  "use strict";

  var STYLES = ["concise", "explanatory", "tutorial"];
  var RULES = {
    "r.style-concise": "concise adds no wrapper",
    "r.style-explanatory": "the wrapper names the exact route and explains it",
    "r.style-tutorial": "the wrapper adds one deterministic next step",
    "r.style-skip": "errors, chat, and non-exact results are never wrapped",
    "r.style-trim": "the wrapper is truncated at styleChars"
  };

  function number(value, fallback) {
    var n = Number(value);
    return isFinite(n) && n >= 0 ? n : fallback;
  }

  function oneLine(text) {
    return String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  }

  function normalize(value) {
    var name = oneLine(value).toLowerCase();
    return STYLES.indexOf(name) >= 0 ? name : null;
  }

  function wrappable(result) {
    if (!result || result.error) return false;
    if (result.exact !== true) return false;
    var via = String(result.via || "");
    if (/^(?:chat|conversation|think|repair|plan|budget|style)(?:\.|$)/.test(via)) {
      return false;
    }
    return true;
  }

  function describe(result) {
    var via = String(result.via || "step");
    var desc = oneLine(result.desc);
    // Catalog `d` is sometimes a display pattern ("{a} plus {b}"), which is
    // not a description; name the route alone rather than show placeholders.
    if (desc.indexOf("{") !== -1) desc = "";
    return desc ? via + " · " + desc : via;
  }

  function suggestion(result) {
    var via = String(result.via || "");
    if (/^(?:build|blueprint|system|module)(?:\.|$)/.test(via)) {
      return 'add a system ("add inventory and save systems"), patch it, or export the project';
    }
    if (/^(?:math|unit|color|csv|date|encode|json|regex|hash|gen|echo)(?:\.|$)/.test(via)) {
      return 'change the input, or chain another step with "then"';
    }
    if (/^text(?:\.|$)/.test(via)) {
      return "write the result to a file, or chain an extractor";
    }
    if (/^(?:edit|project|preview|workspace)(?:\.|$)/.test(via)) {
      return "read the file back, undo the edit, or show the project files";
    }
    if (/^(?:context|journal|memory|library|lang)(?:\.|$)/.test(via)) {
      return 'ask a follow-up, or say "show context" / "show journal"';
    }
    return 'chain another step with "then", or say "show limits" to see the caps';
  }

  function headFor(style, result) {
    if (style === "concise") return "";
    return "style · " + style + " · " + describe(result) + "\n\n";
  }

  function tailFor(style, result) {
    if (style === "explanatory") {
      return "\n\nwhy: the exact " + String(result.via || "step")
        + " command ran locally with no model and no network; the arguments "
        + "came from your request, and the result above is unchanged.";
    }
    if (style === "tutorial") {
      return "\n\ntry next: " + suggestion(result)
        + '\nlearn: say "show limits" for the caps or "show commands" to '
        + "browse the catalog.";
    }
    return "";
  }

  function fit(head, tail, max) {
    var note = " · r.style-trim";
    if (head.length + tail.length <= max) {
      return { head: head, tail: tail, trimmed: false };
    }
    if (max <= note.length) {
      return { head: "", tail: note.slice(0, max), trimmed: true };
    }
    var room = max - note.length;
    var h = head.slice(0, Math.min(head.length, room));
    var t = tail.slice(0, Math.max(0, room - h.length));
    return { head: h, tail: t + note, trimmed: true };
  }

  /* Wrap only after execution. The inner text is copied verbatim; `via`,
   * `exact`, `desc`, and every other field stay as they were. */
  function apply(results, name, opts) {
    var style = normalize(name) || "concise";
    var o = opts || {};
    var max = number(o.maxChars, 600) || 600;
    var list = Array.isArray(results) ? results : [];
    var out = list.slice();
    Object.keys(list).forEach(function (key) {
      if (!/^\d+$/.test(key)) out[key] = list[key];
    });
    for (var i = 0; i < list.length; i += 1) {
      var result = list[i];
      if (!wrappable(result)) {
        out[i] = result;
        continue;
      }
      var copy = Object.assign({}, result);
      if (style === "concise") {
        copy.style = {
          name: style, rule: "r.style-concise", added: 0, trimmed: false
        };
        out[i] = copy;
        continue;
      }
      var fitted = fit(headFor(style, result), tailFor(style, result), max);
      copy.text = fitted.head + String(result.text == null ? "" : result.text)
        + fitted.tail;
      copy.style = {
        name: style,
        rule: fitted.trimmed ? "r.style-trim" : "r.style-" + style,
        added: fitted.head.length + fitted.tail.length,
        trimmed: fitted.trimmed
      };
      out[i] = copy;
    }
    return out;
  }

  function showText(name, opts) {
    var style = normalize(name) || "concise";
    var max = number(opts && opts.maxChars, 600) || 600;
    var on = style === "concise" ? "wrapper off" : "wrapper on";
    return "style · " + style + " · " + on + "\n"
      + (style === "concise"
        ? "exact command output is shown unchanged."
        : "exact command output keeps its text; only the wrapper changes.")
      + "\navailable: " + STYLES.join(", ") + " · wrapper cap " + max + " chars\n"
      + 'say "style explanatory" to change it; tool choice, arguments, files, '
      + "limits, and refusals never depend on style.";
  }

  function setText(name, opts) {
    var style = normalize(name) || "concise";
    var max = number(opts && opts.maxChars, 600) || 600;
    var what = style === "concise"
      ? "exact command output is shown unchanged"
      : style === "explanatory"
        ? "the wrapper names the exact route and explains what ran"
        : "the wrapper names the exact route and suggests one next step";
    return "style · " + style + " · on\n" + what
      + "; tool choice, arguments, files, limits, and refusals do not change.\n"
      + "wrapper cap " + max + " chars · say \"show style\" to inspect it.";
  }

  root.toolrxStyle = {
    STYLES: STYLES.slice(),
    RULES: RULES,
    normalize: normalize,
    wrappable: wrappable,
    apply: apply,
    showText: showText,
    setText: setText
  };
})(typeof self !== "undefined" ? self : this);

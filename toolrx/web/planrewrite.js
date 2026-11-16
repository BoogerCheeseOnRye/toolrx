/* toolrx plan rewriting (step 52).
 *
 * A deterministic compacted-plan variant. Given the parsed steps and the five
 * budgets, it keeps the highest-value steps that still fit and reports every
 * dropped step with the budget that forced it out. No model, no DOM, no fetch,
 * and no caps of its own: the caller supplies every maximum from
 * `toolrx/limits.json`.
 *
 * The two project numbers are estimates, not measurements: a build/growth step
 * reserves `planBuildBytes` and an edit reserves `planEditBytes`. The context
 * number is an upper bound built from the same plan entry and 12-row session
 * slice the browser stores.
 */
(function (root) {
  "use strict";

  var ORDER = ["chars", "steps", "time", "context", "project"];

  var WRITE_OPS = {
    "build": 1, "build.web": 1, "project.grow": 1,
    "edit.apply": 1, "edit.apply.many": 1,
    "system.add": 1, "system.add.many": 1,
    "project.title": 1, "project.theme": 1, "project.themeToggle": 1,
    "project.note": 1, "project.rename": 1, "llm.apply": 1
  };

  var EDIT_OPS = {
    "edit.apply": 1, "edit.apply.many": 1, "project.title": 1,
    "project.theme": 1, "project.themeToggle": 1, "project.note": 1,
    "project.rename": 1
  };

  var SESSION_ROWS = 12;
  var SESSION_ROW_BYTES = 170;
  var PLAN_OVERHEAD = 64;

  function byteLength(text) {
    var s = String(text == null ? "" : text);
    if (typeof TextEncoder !== "undefined") {
      return new TextEncoder().encode(s).length;
    }
    try { return unescape(encodeURIComponent(s)).length; }
    catch (e) { return s.length; }
  }

  function number(value, fallback) {
    var n = Number(value);
    return isFinite(n) && n >= 0 ? n : fallback;
  }

  function estimateContext(steps) {
    var plan = JSON.stringify({
      version: 1,
      steps: steps.map(function (step) { return String(step.text || ""); }),
      status: steps.map(function () { return "pending"; })
    });
    var rows = Math.min(steps.length, SESSION_ROWS) * SESSION_ROW_BYTES;
    return byteLength(plan) + rows + PLAN_OVERHEAD;
  }

  function estimateProject(steps, buildBytes, editBytes) {
    var total = 0;
    steps.forEach(function (step) {
      var op = String(step.via || "");
      if (op === "build" || op === "build.web" || op === "project.grow"
          || op === "system.add" || op === "system.add.many") {
        total += buildBytes;
      } else if (EDIT_OPS[op]) {
        total += editBytes;
      }
    });
    return total;
  }

  function score(step) {
    var op = String(step.via || "");
    if (WRITE_OPS[op]) return 3;
    return step.exact ? 2 : 1;
  }

  function measures(steps, input) {
    var text = steps.map(function (step) { return String(step.text || ""); })
      .join("\n");
    var chars = byteLength(text);
    var count = steps.length;
    return {
      chars: chars,
      steps: count,
      time: count * input.stepMs,
      context: input.contextBytes + estimateContext(steps),
      project: input.projectBytes
        + estimateProject(steps, input.buildBytes, input.editBytes)
    };
  }

  function limits(input) {
    return {
      chars: input.maxChars,
      steps: input.maxSteps,
      time: input.planMs,
      context: input.contextMax,
      project: input.projectMax
    };
  }

  function overKeys(m, max) {
    return ORDER.filter(function (key) { return m[key] > max[key]; });
  }

  function fits(steps, input) {
    var m = measures(steps, input);
    return overKeys(m, limits(input)).length === 0;
  }

  function bars(m, max, estimated) {
    var B = root.toolrxBudget;
    var spec = {
      chars: { used: m.chars, max: max.chars },
      steps: { used: m.steps, max: max.steps },
      context: { used: m.context, max: max.context },
      project: { used: m.project, max: max.project },
      time: { used: m.time, max: max.time }
    };
    var list = B ? B.bars(spec) : ORDER.map(function (key) {
      return { key: key, used: m[key], max: max[key],
               over: m[key] > max[key] };
    });
    (estimated || []).forEach(function (key) {
      list.forEach(function (bar) {
        if (bar.key === key) bar.estimated = true;
      });
    });
    return list;
  }

  function whyDropped(step, chosen, input, over) {
    var test = chosen.concat([step]).sort(function (a, b) { return a.i - b.i; });
    var keys = overKeys(measures(test, input), limits(input));
    if (keys.length) return keys[0];
    return over[0] || "steps";
  }

  /* `input`:
   *   text, steps [{text, via, exact}], stepMs, planMs,
   *   maxChars, maxSteps, contextBytes, contextMax,
   *   projectBytes, projectMax, buildBytes, editBytes
   *
   * Returns { needed, fits, name, steps, dropped, before, after, over,
   *           reason, estimated }.
   */
  function rewrite(input) {
    var all = (input.steps || []).map(function (step, i) {
      return { text: String(step.text || ""), via: String(step.via || ""),
               exact: !!step.exact, i: i };
    });
    var max = limits(input);
    var before = measures(all, input);
    var over = overKeys(before, max);
    var estimated = ["context", "project"];
    if (!over.length) {
      return { needed: false, fits: true, name: null, steps: all,
               dropped: [], before: before, after: before, over: [],
               reason: null, estimated: estimated,
               beforeBars: bars(before, max, estimated),
               afterBars: bars(before, max, estimated) };
    }
    // The current project or context may already be over its cap. No subset of
    // steps can fix that, so refuse and name the budget instead of pretending.
    var base = measures([], input);
    var stuck = overKeys(base, max);
    if (stuck.length) {
      return { needed: true, fits: false, name: null, steps: [],
               dropped: all.map(function (step) {
                 return { text: step.text, via: step.via,
                          why: stuck[0] };
               }),
               before: before, after: base, over: over,
               reason: stuck[0] + " is already over its cap ("
                 + base[stuck[0]] + " > " + max[stuck[0]] + "); compact or "
                 + "reduce it first",
               estimated: estimated,
               beforeBars: bars(before, max, estimated),
               afterBars: bars(base, max, estimated) };
    }
    var ranked = all.slice().sort(function (a, b) {
      return score(b) - score(a) || a.i - b.i;
    });
    var chosen = [];
    ranked.forEach(function (step) {
      var candidate = chosen.concat([step])
        .sort(function (a, b) { return a.i - b.i; });
      if (fits(candidate, input)) chosen = candidate;
    });
    if (!chosen.length) {
      return { needed: true, fits: false, name: null, steps: [],
               dropped: all.map(function (step) {
                 return { text: step.text, via: step.via, why: over[0] };
               }),
               before: before, after: base, over: over,
               reason: "no step fits the " + over.join(" and ") + " budget",
               estimated: estimated,
               beforeBars: bars(before, max, estimated),
               afterBars: bars(base, max, estimated) };
    }
    var kept = {};
    chosen.forEach(function (step) { kept[step.i] = true; });
    var dropped = all.filter(function (step) { return !kept[step.i]; })
      .map(function (step) {
        return { text: step.text, via: step.via,
                 why: whyDropped(step, chosen, input, over) };
      });
    var after = measures(chosen, input);
    return {
      needed: true,
      fits: true,
      name: "compact-" + over.join("-"),
      steps: chosen,
      dropped: dropped,
      before: before,
      after: after,
      over: over,
      reason: null,
      estimated: estimated,
      beforeBars: bars(before, max, estimated),
      afterBars: bars(after, max, estimated)
    };
  }

  /* The stored variant lives beside conversation memory. `planVariantBytes`
   * bounds it; a plan too large to stage is refused rather than silently
   * trimmed, so the caller can tell the user which limit stopped it. */
  function variantRecord(variant, original, opts) {
    var o = opts || {};
    var maxText = number(o.maxText, 2000) || 2000;
    var maxBytes = number(o.maxBytes, 9216);
    var record = {
      version: 1,
      name: String(variant.name || "compact"),
      original: String(original || "").slice(0, 240),
      over: (variant.over || []).slice(),
      steps: (variant.steps || []).map(function (step) {
        return { text: String(step.text || "").slice(0, maxText),
                 via: String(step.via || "") };
      }),
      dropped: (variant.dropped || []).slice(0, 40).map(function (drop) {
        return { text: String(drop.text || "").slice(0, 240),
                 via: String(drop.via || ""), why: String(drop.why || "") };
      }),
    };
    if (byteLength(JSON.stringify(record)) > maxBytes) return null;
    return record;
  }

  root.toolrxPlanRewrite = {
    ORDER: ORDER,
    byteLength: byteLength,
    estimateContext: estimateContext,
    estimateProject: estimateProject,
    score: score,
    variantRecord: variantRecord,
    rewrite: rewrite
  };
})(typeof self !== "undefined" ? self : this);

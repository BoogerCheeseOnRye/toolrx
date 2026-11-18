/* toolrx deterministic plan repair (step 54).
 *
 * One small, inspectable program behind the `repair.plan` route. It reads the
 * plan that actually ran, the failed step, and the error text, then returns
 * exactly one of:
 *
 *   retry  - rerun the failed step and the pending suffix
 *   revise - drop the failed step and run only the pending suffix
 *   refuse - name the exact reason it cannot proceed
 *   none   - there is no failed step to repair
 *
 * Every line names the checked-in rule that produced it. Completed steps are
 * never rerun, and a failed or skipped step is never relabelled done. No DOM,
 * no network, no caps of its own: every maximum comes from `limits.json`.
 */
(function (root) {
  "use strict";

  var RULES = {
    "r.no-failure": "the last run has no failed step",
    "r.repair-cap": "accepted repair passes are capped by repairPasses",
    "r.repair-route": "the failed step has no exact route to retry",
    "r.repair-kind": "a kind-gated patch cannot be fixed by rerunning it",
    "r.repair-missing": "a missing input is dropped from the revised plan",
    "r.repair-math": "an impossible calculation is dropped from the revised plan",
    "r.repair-timeout": "a transient timeout is retried once",
    "r.repair-retry": "the smallest repair retries the failed step",
    "r.repair-drop": "the failed step is dropped",
    "r.repair-dependency": "a pending step depends on the failed result",
    "r.repair-empty": "nothing remains to run after the repair",
    "r.repair-steps": "the revised plan fits planSteps",
    "r.repair-chars": "the revised plan fits planChars",
    "r.repair-suffix": "only the failed step and later steps are in the revised plan",
    "r.repair-record": "the stored repair record fits planVariantBytes",
    "r.repair-none": "no repair is staged",
    /* Step 57: one-command partial-result continuation. */
    "r.resume-none": "there is no last-run plan to resume",
    "r.resume-nofail": "the last run has no failed step to skip",
    "r.resume-last": "the failed step is the last step, so nothing is pending",
    "r.resume-cap": "resume and repair share the repairPasses cap",
    "r.resume-build": "a failed build is retried, not skipped",
    "r.resume-noproject": "a pending step needs a project and none is open",
    "r.resume-dependency": "a pending step depends on the failed result",
    "r.resume-steps": "the pending suffix fits planSteps",
    "r.resume-chars": "the pending suffix fits planChars",
    "r.resume-pending": "only the pending suffix is resumed",
    "r.resume-suffix": "only the pending steps are resumed",
    "r.resume-skip": "the failed step is skipped, not relabelled done",
    "r.resume-record": "the resume record fits planVariantBytes"
  };

  function rule(id) { return "· " + id; }

  function number(value, fallback) {
    var n = Number(value);
    return isFinite(n) && n >= 0 ? n : fallback;
  }

  function oneLine(text) {
    return String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  }

  function quote(text, n) {
    return '"' + oneLine(text).slice(0, n || 120) + '"';
  }

  function byteLength(text) {
    var s = String(text == null ? "" : text);
    if (typeof TextEncoder !== "undefined") {
      return new TextEncoder().encode(s).length;
    }
    try { return unescape(encodeURIComponent(s)).length; }
    catch (e) { return s.length; }
  }

  function normalizeStep(step) {
    if (step && typeof step === "object") {
      return {
        text: oneLine(step.text),
        op: String(step.op || ""),
        exact: !!step.exact
      };
    }
    return { text: oneLine(step), op: "", exact: false };
  }

  function limitsOf(input) {
    var l = input.limits || {};
    return {
      steps: number(l.planSteps, 40),
      chars: number(l.planChars, 8000),
      variantBytes: number(l.planVariantBytes, 9216)
    };
  }

  function routeLabel(step) {
    return step.exact ? "exact " + (step.op || "command")
      : "router (no exact route)";
  }

  function overLimits(steps, lim, prefix) {
    var head = prefix || "r.repair-";
    if (steps.length > lim.steps) {
      return { rule: head + "steps", why: steps.length + " steps > "
        + lim.steps + " planSteps" };
    }
    var chars = byteLength(steps.map(function (s) { return s.text; })
      .join("\n"));
    if (chars > lim.chars) {
      return { rule: head + "chars", why: chars + " characters > "
        + lim.chars + " planChars" };
    }
    return null;
  }

  function dependsOnFailed(text) {
    return /\b(?:it|that|those|them|the result|the previous|previous step)\b/i
      .test(String(text || ""));
  }

  function shortError(error) {
    return oneLine(error).replace(/\s+try:\s.*$/i, "").slice(0, 160);
  }

  function kindReason(error) {
    var text = oneLine(error);
    var wired = text.match(/wired for ([^.;]+?)(?:\s+try:|$)/i);
    var compatible = wired ? oneLine(wired[1]) : "";
    return compatible
      ? "this patch is not available for the active project kind; it is wired "
        + "for " + compatible + "; build a compatible starter first"
      : "this patch is not available for the active project kind; build a "
        + "compatible starter first";
  }

  function result(kind, ruleId, reason, extra) {
    var out = {
      kind: kind,
      rule: ruleId,
      reason: reason,
      steps: [],
      dropped: [],
      failedStep: "",
      errorText: "",
      failedAt: -1,
      passes: 0,
      maxPasses: 2,
      pending: 0
    };
    if (extra) Object.keys(extra).forEach(function (k) { out[k] = extra[k]; });
    return out;
  }

  function plan(input) {
    var safe = input || {};
    var raw = Array.isArray(safe.steps) ? safe.steps : [];
    var steps = raw.map(normalizeStep);
    var failedAt = Number.isInteger(safe.failedAt) ? safe.failedAt : -1;
    var passes = number(safe.passes, 0);
    var maxPasses = number(safe.maxPasses, 2) || 2;
    var lim = limitsOf(safe);
    var error = oneLine(safe.errorText);
    var original = number(safe.originalSteps, steps.length);

    if (failedAt < 0 || failedAt >= steps.length) {
      return result("none", "r.no-failure",
        "the last run has no failed step", {
          passes: passes, maxPasses: maxPasses, originalSteps: original
        });
    }
    var failed = steps[failedAt];
    var pending = steps.slice(failedAt + 1);
    var base = {
      failedStep: failed.text,
      errorText: error,
      failedAt: failedAt,
      passes: passes,
      maxPasses: maxPasses,
      pending: pending.length,
      originalSteps: original
    };

    if (passes >= maxPasses) {
      return result("refuse", "r.repair-cap",
        "the repair pass cap (" + maxPasses + ") is reached; send a new "
        + "request or say undo", base);
    }
    if (!failed.exact) {
      return result("refuse", "r.repair-route",
        "the failed step has no exact route, and the router already tried; "
        + "I will not guess a different command", base);
    }
    if (/not edited\s*·|wired for|compatible starter/i.test(error)) {
      return result("refuse", "r.repair-kind", kindReason(error), base);
    }

    var revise = /no such file|not found|does not exist|cannot read/i
      .test(error);
    var math = /division by zero|cannot divide|divide by zero/i.test(error);
    var transient = /timed out|timeout|budget .*exhausted|temporar/i
      .test(error);

    if (revise || math) {
      if (!pending.length) {
        return result("refuse", "r.repair-empty",
          "the failed step is the last step, so dropping it leaves nothing "
          + "to run", base);
      }
      var dependency = pending.filter(function (step) {
        return dependsOnFailed(step.text);
      })[0];
      if (dependency) {
        return result("refuse", "r.repair-dependency",
          "the pending step " + quote(dependency.text)
          + " depends on the failed result, so dropping the failure would "
          + "produce a wrong answer", base);
      }
      var over = overLimits(pending, lim);
      if (over) {
        return result("refuse", over.rule,
          "the revised plan does not fit: " + over.why, base);
      }
      return result("revise", revise ? "r.repair-missing" : "r.repair-math",
        (revise ? "the input is missing, so drop the failed step"
          : "the calculation is impossible, so drop the failed step")
        + " and run the " + pending.length + " pending step(s)", {
          steps: pending,
          dropped: [failed.text],
          failedStep: failed.text,
          errorText: error,
          failedAt: failedAt,
          passes: passes,
          maxPasses: maxPasses,
          pending: pending.length,
          originalSteps: original
        });
    }

    if (transient) {
      var retry = [failed].concat(pending);
      var overRetry = overLimits(retry, lim);
      if (overRetry) {
        return result("refuse", overRetry.rule,
          "the revised plan does not fit: " + overRetry.why, base);
      }
      return result("retry", "r.repair-timeout",
        "the failure is transient, so retry the failed step and the "
        + pending.length + " pending step(s)", {
          steps: retry,
          failedStep: failed.text,
          errorText: error,
          failedAt: failedAt,
          passes: passes,
          maxPasses: maxPasses,
          pending: pending.length,
          originalSteps: original
        });
    }

    var retryAll = [failed].concat(pending);
    var overAll = overLimits(retryAll, lim);
    if (overAll) {
      return result("refuse", overAll.rule,
        "the revised plan does not fit: " + overAll.why, base);
    }
    return result("retry", "r.repair-retry",
      "the smallest repair retries the failed step and the "
      + pending.length + " pending step(s)", {
        steps: retryAll,
        failedStep: failed.text,
        errorText: error,
        failedAt: failedAt,
        passes: passes,
        maxPasses: maxPasses,
        pending: pending.length,
        originalSteps: original
      });
  }

  function text(out) {
    var shownPass = Math.min(out.passes + 1, out.maxPasses);
    var head = "repair · pass " + shownPass + " of " + out.maxPasses
      + (out.rule === "r.repair-cap" ? " · cap reached" : "")
      + " · source last run";
    if (out.kind === "none") {
      return [head,
        "the last run has no failed step " + rule(out.rule),
        'say "critique this plan" to inspect the plan instead'].join("\n");
    }
    var lines = [head];
    lines.push("failed: step " + (out.failedAt + 1) + " · "
      + quote(out.failedStep) + " · " + shortError(out.errorText)
      + " " + rule(out.rule));
    lines.push("reason: " + out.reason + " " + rule(out.rule));
    if (out.kind === "refuse") {
      lines.push("repair: none · nothing was staged " + rule("r.repair-none"));
    } else {
      lines.push("revised plan (" + out.steps.length + " step"
        + (out.steps.length === 1 ? "" : "s") + "): "
        + rule("r.repair-suffix"));
      out.steps.forEach(function (step, i) {
        lines.push("  " + (i + 1) + ". " + step.text + " · "
          + routeLabel(step) + " " + rule(step.exact
            ? "r.repair-suffix" : "r.repair-route"));
      });
      if (out.dropped.length) {
        lines.push("dropped: " + out.dropped.map(function (s) {
          return quote(s);
        }).join(", ") + " " + rule("r.repair-drop"));
      }
      lines.push("completed: the " + out.failedAt + " step(s) before the "
        + "failure are not rerun " + rule("r.repair-suffix"));
    }
    lines.push("original: " + out.originalSteps + " step(s) kept · say undo "
      + "to revert files " + rule("r.repair-record"));
    if (out.kind === "refuse") {
      lines.push("say a new request to move on");
    } else {
      lines.push("say yes to run exactly these steps, no to keep the project "
        + "untouched, or send an edited request");
    }
    return lines.join("\n");
  }

  /* Step 57: partial-result continuation. `resume` is deliberately narrower
   * than `repair`: it never retries and never guesses. It skips the failed
   * step and returns only the pending suffix, after the same safety checks a
   * human would apply before continuing a half-finished plan. */
  function resume(input) {
    var safe = input || {};
    var raw = Array.isArray(safe.steps) ? safe.steps : [];
    var steps = raw.map(normalizeStep);
    var failedAt = Number.isInteger(safe.failedAt) ? safe.failedAt : -1;
    var passes = number(safe.passes, 0);
    var maxPasses = number(safe.maxPasses, 2) || 2;
    var lim = limitsOf(safe);
    var error = oneLine(safe.errorText);
    var original = number(safe.originalSteps, steps.length);
    var hasProject = !!safe.hasProject;
    var pendingNeedsProject = !!safe.pendingNeedsProject;

    if (!steps.length) {
      return result("refuse", "r.resume-none",
        "the last run has no plan; run a plan first", {
          passes: passes, maxPasses: maxPasses, originalSteps: original
        });
    }
    if (failedAt < 0 || failedAt >= steps.length) {
      return result("refuse", "r.resume-nofail",
        "the last run did not fail; there is nothing to resume", {
          passes: passes, maxPasses: maxPasses, originalSteps: original
        });
    }
    var failed = steps[failedAt];
    var pending = steps.slice(failedAt + 1);
    var base = {
      failedStep: failed.text,
      errorText: error,
      failedAt: failedAt,
      passes: passes,
      maxPasses: maxPasses,
      pending: pending.length,
      originalSteps: original
    };
    if (!pending.length) {
      return result("refuse", "r.resume-last",
        "the failed step is the last step, so there is no pending suffix "
        + "to resume", base);
    }
    if (passes >= maxPasses) {
      return result("refuse", "r.resume-cap",
        "the resume/repair pass cap (" + maxPasses + ") is reached; send a "
        + "new request or say undo", base);
    }
    if (failed.op === "build" || /^build\b/i.test(failed.text)) {
      return result("refuse", "r.resume-build",
        "the build step failed; the previous project is still open, but the "
        + "pending steps were meant for the new build — say repair this plan "
        + "to retry the build, or send the build request again", base);
    }
    if (pendingNeedsProject && !hasProject) {
      return result("refuse", "r.resume-noproject",
        "a pending step needs a project and none is open; build a starter "
        + "first", base);
    }
    var dependency = pending.filter(function (step) {
      return dependsOnFailed(step.text);
    })[0];
    if (dependency) {
      return result("refuse", "r.resume-dependency",
        "the pending step " + quote(dependency.text)
        + " depends on the failed result, so skipping the failure would "
        + "produce a wrong answer", base);
    }
    var over = overLimits(pending, lim, "r.resume-");
    if (over) {
      return result("refuse", over.rule,
        "the pending suffix does not fit: " + over.why, base);
    }
    return result("resume", "r.resume-pending",
      "skip the failed step and run the " + pending.length
      + " pending step(s)", {
        steps: pending,
        skipped: [failed.text],
        failedStep: failed.text,
        errorText: error,
        failedAt: failedAt,
        passes: passes,
        maxPasses: maxPasses,
        pending: pending.length,
        originalSteps: original
      });
  }

  function resumeText(out) {
    var shownPass = Math.min(out.passes + 1, out.maxPasses);
    var head = "resume · pass " + shownPass + " of " + out.maxPasses
      + (out.rule === "r.resume-cap" ? " · cap reached" : "")
      + " · " + (out.kind === "resume"
        ? "run the pending suffix" : "nothing resumed")
      + " · source last run";
    if (out.kind === "refuse") {
      var lines = [head];
      if (out.failedStep) {
        lines.push("failed: step " + (out.failedAt + 1) + " · "
          + quote(out.failedStep)
          + (out.errorText ? " · " + shortError(out.errorText) : "")
          + " " + rule(out.rule));
      }
      lines.push("reason: " + out.reason + " " + rule(out.rule));
      lines.push("resume: none · nothing was run " + rule("r.resume-none"));
      if (out.rule === "r.resume-build") {
        lines.push("the previous project is still open · say repair this plan "
          + "to retry the build");
      } else if (out.rule === "r.resume-cap") {
        lines.push("send a new request or say undo to move on");
      } else {
        lines.push("send a new request to move on");
      }
      return lines.join("\n");
    }
    var lines2 = [head];
    lines2.push("skipped: step " + (out.failedAt + 1) + " · "
      + quote(out.failedStep)
      + (out.errorText ? " · " + shortError(out.errorText) : "")
      + " " + rule("r.resume-skip"));
    lines2.push("pending plan (" + out.steps.length + " step"
      + (out.steps.length === 1 ? "" : "s") + "): "
      + rule("r.resume-suffix"));
    out.steps.forEach(function (step, i) {
      lines2.push("  " + (i + 1) + ". " + step.text + " · "
        + routeLabel(step) + " " + rule("r.resume-suffix"));
    });
    lines2.push("completed: the " + out.failedAt + " step(s) before the "
      + "failure are not rerun " + rule("r.resume-suffix"));
    lines2.push("original: " + out.originalSteps + " step(s) kept · completed "
      + "files stay written " + rule("r.resume-record"));
    lines2.push("running now · say undo to revert files");
    return lines2.join("\n");
  }

  function record(out, input, opts) {
    var o = opts || {};
    var kind = o.kind === "resume" ? "resume" : "repair";
    var maxText = number(o.maxText, 2000) || 2000;
    var maxBytes = number(o.maxBytes, 9216);
    var safe = input || {};
    var original = (Array.isArray(safe.originalSteps)
      ? safe.originalSteps : (safe.steps || [])).map(function (step) {
        return normalizeStep(step);
      });
    var doc = {
      version: 1,
      kind: kind,
      name: kind + "-" + (out.passes + 1),
      rule: out.rule,
      reason: oneLine(out.reason).slice(0, 240),
      failedAt: out.failedAt,
      failedStep: oneLine(out.failedStep).slice(0, maxText),
      errorText: oneLine(safe.errorText).slice(0, 400),
      passes: out.passes + 1,
      maxPasses: out.maxPasses,
      original: original.slice(0, 40).map(function (step) {
        return { text: step.text.slice(0, 240), op: step.op, exact: step.exact };
      }),
      steps: out.steps.map(function (step) {
        return { text: step.text.slice(0, maxText), op: step.op,
                 exact: step.exact };
      }),
      dropped: (out.dropped || []).slice(0, 40).map(function (s) {
        return String(s).slice(0, 240);
      })
    };
    if (kind === "resume") {
      doc.skipped = (out.skipped || []).slice(0, 40).map(function (s) {
        return String(s).slice(0, 240);
      });
    }
    if (byteLength(JSON.stringify(doc)) > maxBytes) return null;
    return doc;
  }

  root.toolrxRepair = {
    RULES: RULES,
    plan: plan,
    text: text,
    resume: resume,
    resumeText: resumeText,
    record: record
  };
})(typeof self !== "undefined" ? self : this);

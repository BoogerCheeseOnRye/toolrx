/* toolrx deterministic thinking (step 53).
 *
 * Four small, inspectable programs behind the `think.*` routes: decompose,
 * reason, tradeoff, and critique. Every line that makes a claim names the
 * checked-in rule that produced it, or quotes the input it came from. The
 * same input always produces byte-identical text.
 *
 * No DOM, no network, no caps of its own: the caller passes every maximum from
 * `toolrx/limits.json`, and the goals are already split and routed by the real
 * planner so the output describes the plan that would actually run.
 */
(function (root) {
  "use strict";

  var MODES = ["decompose", "reason", "tradeoff", "critique"];

  /* One checked-in rule table. Ids are stable and appear in the output, so a
   * reader can trace every claim back to the rule that made it. */
  var RULES = {
    "r.input-cap": "input is analyzed up to thinkChars",
    "r.goal-cap": "goals are listed up to thinkGoals",
    "r.split": "goals come from the planner's own split",
    "r.order": "goals keep request order",
    "r.next-first": "the next action is the first goal",
    "r.route-exact": "the step has an exact catalog route",
    "r.route-router": "the step has no exact route and uses the router",
    "r.build-cost": "a build writes about planBuildBytes",
    "r.edit-cost": "an edit writes about planEditBytes",
    "r.read-cost": "a read is bounded by readFileBytes and readTotalBytes",
    "r.math-cost": "arithmetic writes nothing",
    "r.context-cost": "a context step is bounded by contextBytes",
    "r.default-cost": "the step writes nothing",
    "r.steps-cap": "step count is within planSteps",
    "r.chars-cap": "characters are within planChars",
    "r.time-cap": "worst-case time is within planMs",
    "r.duplicate": "no step is repeated",
    "r.failed-step": "no step is marked failed",
    "r.pending-step": "pending steps are counted, not assumed done",
    "r.project-cap": "project bytes plus estimates fit projectBytes",
    "r.context-cap": "context bytes fit contextBytes",
    "r.files-cap": "project files fit projectFiles",
    "r.plan-exists": "a plan is available to check",
    "r.repair-failed": "smallest repair for a failed step",
    "r.repair-duplicate": "smallest repair for a duplicate step",
    "r.repair-steps": "smallest repair for too many steps",
    "r.repair-chars": "smallest repair for too many characters",
    "r.repair-time": "smallest repair for too little time",
    "r.repair-project": "smallest repair for a full project",
    "r.repair-context": "smallest repair for a full context",
    "r.repair-files": "smallest repair for too many files",
    "r.repair-none": "every checked rule passes",
    "r.offline": "offline and network keywords",
    "r.speed": "speed keywords",
    "r.size": "size keywords",
    "r.risk": "risk keywords",
    "r.first-listed": "tiebreak by the first listed option",
    "r.no-match": "no checked rule matches the options",
    "r.single-option": "one option is not a trade-off",
    "r.limits": "numbers come from limits.json"
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

  function fmt(n) {
    var s = String(Math.round(Number(n) || 0));
    return s.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function fmtScore(n) {
    return Number.isInteger(n) ? String(n) : n.toFixed(1);
  }

  function words(text) {
    return String(text == null ? "" : text).match(/[A-Za-z0-9']+/g) || [];
  }

  function oneLine(text) {
    return String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  }

  function quote(text) {
    return '"' + oneLine(text).slice(0, 120) + '"';
  }

  function routeLabel(step) {
    return step.exact ? "exact " + (step.op || "command")
      : "router (no exact route)";
  }

  function routeRule(step) {
    return step.exact ? "r.route-exact" : "r.route-router";
  }

  function limitsOf(input) {
    var l = input.limits || {};
    return {
      chars: number(l.planChars, 8000),
      steps: number(l.planSteps, 40),
      stepMs: number(l.stepMs, 4000),
      planMs: number(l.planMs, 160000),
      context: number(l.contextMax, 8192),
      project: number(l.projectMax, 524288),
      files: number(l.projectFiles, 32),
      buildBytes: number(l.buildBytes, 65536),
      editBytes: number(l.editBytes, 4096),
      readFileBytes: number(l.readFileBytes, 8000),
      readTotalBytes: number(l.readTotalBytes, 24000),
      thinkChars: number(l.thinkChars, 4000),
      thinkGoals: number(l.thinkGoals, 8),
      thinkRules: number(l.thinkRules, 12)
    };
  }

  function projectEstimate(steps, lim) {
    var R = root.toolrxPlanRewrite;
    if (R && typeof R.estimateProject === "function") {
      /* The plan rewriter reads `via`; thinking steps carry `op`. Normalise so
       * both modules measure the same plan the same way. */
      return R.estimateProject(steps.map(function (step) {
        return { via: step.op, exact: step.exact };
      }), lim.buildBytes, lim.editBytes);
    }
    var total = 0;
    steps.forEach(function (step) {
      var op = String(step.op || "");
      if (op === "build" || op === "build.web" || op === "project.grow"
          || op === "system.add" || op === "system.add.many") {
        total += lim.buildBytes;
      } else if (/^edit\.|^project\.(?:title|theme|themeToggle|note|rename)$/.test(op)) {
        total += lim.editBytes;
      }
    });
    return total;
  }

  function baseProject(input) {
    var p = input.project;
    return p ? number(p.bytes, 0) : 0;
  }

  function checksLine(steps, input, lim) {
    var chars = byteLength(input.text || "");
    var time = steps.length * lim.stepMs;
    var project = baseProject(input) + projectEstimate(steps, lim);
    return "steps " + steps.length + "/" + lim.steps
      + " · chars " + fmt(chars) + "/" + fmt(lim.chars)
      + " · time " + fmt(time / 1000) + " s/" + fmt(lim.planMs / 1000) + " s"
      + " · project est. " + fmt(project) + "/" + fmt(lim.project) + " bytes";
  }

  function overLimits(steps, input, lim) {
    var over = [];
    var chars = byteLength(input.text || "");
    if (steps.length > lim.steps) over.push("steps");
    if (chars > lim.chars) over.push("chars");
    if (steps.length * lim.stepMs > lim.planMs) over.push("time");
    if (baseProject(input) + projectEstimate(steps, lim) > lim.project) {
      over.push("project");
    }
    return over;
  }

  function header(mode, input, body) {
    var lines = ["think · " + mode + " · source " + (input.source || "literal")
      + " · " + words(body).length + " words"];
    return lines;
  }

  function inputLines(lines, input, lim) {
    var text = String(input.text || "");
    if (text.length > lim.thinkChars) {
      lines.push("input truncated to " + fmt(lim.thinkChars) + " characters "
        + "of " + fmt(text.length) + " " + rule("r.input-cap"));
    }
    return lines;
  }

  function rulesLine(lines) {
    var seen = [];
    var re = /r\.[a-z][a-z-]*/g;
    var text = lines.join("\n");
    var match;
    while ((match = re.exec(text))) {
      if (seen.indexOf(match[0]) < 0) seen.push(match[0]);
    }
    return "rules: " + seen.join(", ");
  }

  function emptyText(mode) {
    return ["think · " + mode + " · nothing to work on",
      "give me a topic, a file, the previous result, the active plan, "
        + "or the context"].join("\n");
  }

  /* ------------------------------------------------------------ decompose -- */
  function decompose(input) {
    var lim = limitsOf(input);
    var goals = (input.goals || []).slice();
    if (!goals.length) return emptyText("decompose");
    var lines = header("decompose", input, input.text || "");
    inputLines(lines, input, lim);
    var shown = goals.slice(0, lim.thinkGoals);
    lines.push("goals (" + shown.length + " shown of " + goals.length + "): "
      + rule("r.split"));
    shown.forEach(function (goal, i) {
      lines.push("  " + (i + 1) + ". " + oneLine(goal.text) + " · "
        + routeLabel(goal) + " " + rule(routeRule(goal)));
    });
    if (goals.length > shown.length) {
      lines.push("… " + (goals.length - shown.length) + " more goal(s) counted "
        + "but not listed " + rule("r.goal-cap"));
    }
    var order = shown.map(function (_, i) { return i + 1; }).join(" → ");
    lines.push("order: " + order + " · "
      + (input.sequenced ? "explicit sequence words in the request"
        : "request order") + " " + rule("r.order"));
    lines.push("checks: " + checksLine(goals, input, lim) + " " + rule("r.limits"));
    var over = overLimits(goals, input, lim);
    var firstExact = goals.filter(function (goal) { return goal.exact; })[0];
    if (over.length) {
      lines.push("next: split the request; " + over.join(" + ")
        + " over budget " + rule("r.next-first"));
    } else if (firstExact) {
      lines.push("next: " + oneLine(firstExact.text) + " "
        + rule("r.next-first"));
    } else if (input.literal !== false) {
      lines.push("next: " + oneLine(goals[0].text) + " (router; no exact "
        + "route) " + rule("r.route-router"));
    } else {
      lines.push("next: none of the " + goals.length + " line(s) has an "
        + "exact route · this source is a listing, not a request "
        + rule("r.route-router"));
    }
    lines.push(rulesLine(lines));
    return lines.join("\n");
  }

  /* --------------------------------------------------------------- reason -- */
  function opCheck(step, input, lim) {
    var op = String(step.op || "");
    if (op === "build" || op === "build.web" || op === "project.grow"
        || op === "system.add" || op === "system.add.many") {
      return {
        text: "writes about " + fmt(lim.buildBytes) + " bytes · project "
          + fmt(baseProject(input)) + "/" + fmt(lim.project) + " bytes",
        rule: "r.build-cost"
      };
    }
    if (/^edit\.|^project\.(?:title|theme|themeToggle|note|rename)$/.test(op)) {
      return {
        text: "writes about " + fmt(lim.editBytes) + " bytes · project "
          + fmt(baseProject(input)) + "/" + fmt(lim.project) + " bytes",
        rule: "r.edit-cost"
      };
    }
    if (op === "fs.read_file" || op === "fs.cat_all" || op === "file.read") {
      return {
        text: "reads up to " + fmt(lim.readFileBytes) + " bytes · all reads "
          + fmt(lim.readTotalBytes) + " bytes",
        rule: "r.read-cost"
      };
    }
    if (/^math\./.test(op)) {
      return { text: "exact arithmetic · no project write", rule: "r.math-cost" };
    }
    if (/^context\./.test(op)) {
      return {
        text: "context " + fmt(number(input.contextBytes, 0)) + "/"
          + fmt(lim.context) + " bytes",
        rule: "r.context-cost"
      };
    }
    return { text: "no project write", rule: "r.default-cost" };
  }

  function reason(input) {
    var lim = limitsOf(input);
    var goals = (input.goals || []).slice();
    if (!goals.length) return emptyText("reason");
    var lines = header("reason", input, input.text || "");
    inputLines(lines, input, lim);
    var shown = goals.slice(0, lim.thinkGoals);
    shown.forEach(function (goal, i) {
      var check = opCheck(goal, input, lim);
      lines.push("step " + (i + 1) + " · " + quote(goal.text));
      lines.push("  route: " + routeLabel(goal) + " " + rule(routeRule(goal)));
      lines.push("  check: " + check.text + " " + rule(check.rule));
      lines.push("  then: " + (i + 1 < shown.length
        ? "step " + (i + 2) : "report the result"));
    });
    if (goals.length > shown.length) {
      lines.push("… " + (goals.length - shown.length) + " more step(s) counted "
        + "but not walked " + rule("r.goal-cap"));
    }
    var over = overLimits(goals, input, lim);
    var firstExact = goals.filter(function (goal) { return goal.exact; })[0];
    if (over.length) {
      lines.push("conclusion: " + over.join(" + ") + " over budget · split the "
        + "request before running it " + rule("r.steps-cap"));
    } else if (firstExact) {
      lines.push("conclusion: " + goals.length + " step(s) fit every checked "
        + "limit · start with " + quote(firstExact.text) + " "
        + rule("r.next-first"));
    } else if (input.literal === false) {
      lines.push("conclusion: " + goals.length + " line(s), none with an exact "
        + "route · this source is a listing, not a request "
        + rule("r.route-router"));
    } else {
      lines.push("conclusion: " + goals.length + " step(s) fit every checked "
        + "limit · start with " + quote(goals[0].text) + " (router) "
        + rule("r.next-first"));
    }
    lines.push("checks: " + checksLine(goals, input, lim) + " " + rule("r.limits"));
    lines.push(rulesLine(lines));
    return lines.join("\n");
  }

  /* ------------------------------------------------------------- tradeoff -- */
  var CRITERIA = [
    {
      id: "offline",
      better: /\b(offline|local|deterministic|self-hosted)\b/i,
      worse: /\b(network|online|cloud|api|remote)\b/i,
      rule: "r.offline"
    },
    {
      id: "speed",
      better: /\b(fast|quick|instant|native|compiled|precomputed)\b/i,
      worse: /\b(slow|async|round trip|remote)\b/i,
      rule: "r.speed"
    },
    {
      id: "size",
      better: /\b(small|tiny|minimal|light|lean)\b/i,
      worse: /\b(large|heavy|big|bloated)\b/i,
      rule: "r.size"
    },
    {
      id: "risk",
      better: /\b(simple|stable|tested|boring)\b/i,
      worse: /\b(complex|experimental|fragile|risky|clever)\b/i,
      rule: "r.risk"
    }
  ];

  function splitOptions(text) {
    var parts = String(text || "").split(/\s+(?:vs\.?|versus|compared to|or)\s+/i);
    var out = [];
    parts.forEach(function (part) {
      var clean = oneLine(part).replace(/^["']|["']$/g, "");
      if (clean) out.push(clean);
    });
    return out;
  }

  function verdictFor(option, criterion) {
    var better = criterion.better.test(option);
    var worse = criterion.worse.test(option);
    if (better && worse) return "mixed";
    if (better) return "better";
    if (worse) return "worse";
    return "unknown";
  }

  function scoreOf(verdict) {
    if (verdict === "better") return 1;
    if (verdict === "mixed") return 0.5;
    if (verdict === "worse") return -1;
    return 0;
  }

  function tradeoff(input) {
    var lim = limitsOf(input);
    var text = String(input.text || "");
    if (!oneLine(text)) return emptyText("trade-off");
    var lines = header("trade-off", input, text);
    inputLines(lines, input, lim);
    var options = splitOptions(text);
    if (options.length > 2) {
      lines.push("options: using the first two of " + options.length
        + " · " + options.slice(0, 2).map(quote).join(" · "));
      options = options.slice(0, 2);
    } else {
      lines.push("options: " + options.map(quote).join(" · "));
    }
    if (options.length < 2) {
      var matches = [];
      CRITERIA.forEach(function (criterion) {
        var v = verdictFor(options[0] || "", criterion);
        if (v !== "unknown") {
          matches.push(criterion.id + " (" + v + ") " + rule(criterion.rule));
        }
      });
      if (matches.length) lines.push("matches: " + matches.join(" · "));
      lines.push("recommendation: none · one option is not a trade-off; say "
        + "\"A vs B\" " + rule("r.single-option"));
      lines.push(rulesLine(lines));
      return lines.join("\n");
    }
    var rows = [];
    var matched = 0;
    CRITERIA.forEach(function (criterion) {
      var a = verdictFor(options[0], criterion);
      var b = verdictFor(options[1], criterion);
      if (a === "unknown" && b === "unknown") return;
      matched += 1;
      rows.push("  " + criterion.id + " · A " + a + " · B " + b + " "
        + rule(criterion.rule));
    });
    lines.push("criteria (" + matched + " matched of " + CRITERIA.length + "):");
    if (rows.length) rows.forEach(function (row) { lines.push(row); });
    else lines.push("  none — no checked keyword rule matches either option");
    var routes = input.optionRoutes || null;
    if (routes) {
      lines.push("routes: A " + (routes[0] ? "exact" : "router") + " · B "
        + (routes[1] ? "exact" : "router") + " "
        + rule(routes[0] && routes[1] ? "r.route-exact" : "r.route-router"));
    }
    if (!matched) {
      lines.push("recommendation: none · no checked rule matches either option, "
        + "so I will not invent one " + rule("r.no-match"));
    } else {
      var scores = [0, 0];
      CRITERIA.forEach(function (criterion) {
        var a = verdictFor(options[0], criterion);
        var b = verdictFor(options[1], criterion);
        if (a === "unknown" && b === "unknown") return;
        scores[0] += scoreOf(a);
        scores[1] += scoreOf(b);
      });
      var pick = scores[0] === scores[1] ? 0 : (scores[0] > scores[1] ? 0 : 1);
      var why = scores[0] === scores[1]
        ? "tie on " + fmtScore(scores[0]) + " of " + matched
          + " matched criteria · tiebreak " + rule("r.first-listed")
        : "scores " + fmtScore(scores[pick]) + " vs " + fmtScore(scores[1 - pick])
          + " on " + matched + " matched criteria";
      lines.push("recommendation: " + quote(options[pick]) + " · " + why);
    }
    lines.push(rulesLine(lines));
    return lines.join("\n");
  }

  /* ------------------------------------------------------------- critique -- */
  function checkList(input, lim) {
    var steps = (input.plan && input.plan.steps) || [];
    var chars = byteLength(input.text || steps.map(function (s) {
      return s.text;
    }).join("\n"));
    var time = steps.length * lim.stepMs;
    var project = baseProject(input) + projectEstimate(steps, lim);
    var seen = Object.create(null);
    var duplicates = [];
    var unknown = [];
    var failed = [];
    var pending = 0;
    steps.forEach(function (step) {
      var key = oneLine(step.text).toLowerCase();
      if (seen[key]) duplicates.push(step.text);
      seen[key] = true;
      if (!step.exact) unknown.push(step.text);
      if (step.status === "error") failed.push(step.text);
      if (step.status === "pending") pending += 1;
    });
    var files = input.project ? (input.project.files || []).length : 0;
    return [
      { id: "r.plan-exists", ok: steps.length > 0, label: "plan exists",
        detail: steps.length + " step(s)" },
      { id: "r.steps-cap", ok: steps.length <= lim.steps, label: "step count",
        detail: steps.length + "/" + lim.steps },
      { id: "r.chars-cap", ok: chars <= lim.chars, label: "characters",
        detail: fmt(chars) + "/" + fmt(lim.chars) },
      { id: "r.time-cap", ok: time <= lim.planMs, label: "worst-case time",
        detail: fmt(time / 1000) + " s/" + fmt(lim.planMs / 1000) + " s" },
      { id: "r.duplicate", ok: !duplicates.length, label: "repeated steps",
        detail: duplicates.length ? quote(duplicates[0]) : "none" },
      { id: "r.failed-step", ok: !failed.length, label: "failed steps",
        detail: failed.length ? quote(failed[0]) : "none" },
      { id: "r.route-router", ok: !unknown.length, label: "exact routes",
        detail: unknown.length ? quote(unknown[0]) : "all exact" },
      { id: "r.project-cap", ok: project <= lim.project, label: "project bytes",
        detail: fmt(project) + "/" + fmt(lim.project) },
      { id: "r.context-cap", ok: number(input.contextBytes, 0) <= lim.context,
        label: "context bytes",
        detail: fmt(number(input.contextBytes, 0)) + "/" + fmt(lim.context) },
      { id: "r.files-cap", ok: files <= lim.files, label: "project files",
        detail: files + "/" + lim.files },
      { id: "r.pending-step", ok: true, label: "pending steps",
        detail: String(pending), info: pending > 0 }
    ];
  }

  function repairFor(found, input, lim) {
    var byId = {};
    found.forEach(function (check) { byId[check.id] = check; });
    if (byId["r.failed-step"]) {
      var failed = (input.plan.steps || []).filter(function (step) {
        return step.status === "error";
      })[0];
      return {
        text: "rerun only " + quote(failed ? failed.text : "the failed step")
          + "; the failed step stays failed and completed files stay written",
        rule: "r.repair-failed"
      };
    }
    if (byId["r.duplicate"]) {
      return { text: "remove the repeated step", rule: "r.repair-duplicate" };
    }
    if (byId["r.steps-cap"]) {
      var over = (input.plan.steps || []).length - lim.steps;
      return {
        text: "drop " + over + " step(s) or accept the compacted plan variant",
        rule: "r.repair-steps"
      };
    }
    if (byId["r.chars-cap"]) {
      return { text: "split the request into smaller plans",
        rule: "r.repair-chars" };
    }
    if (byId["r.time-cap"]) {
      return {
        text: "raise toolrx.plan.timeout or split the plan",
        rule: "r.repair-time"
      };
    }
    if (byId["r.project-cap"]) {
      return { text: "compact the project or reduce the writes",
        rule: "r.repair-project" };
    }
    if (byId["r.context-cap"]) {
      return { text: "compact context first", rule: "r.repair-context" };
    }
    if (byId["r.files-cap"]) {
      return { text: "remove a file before adding more",
        rule: "r.repair-files" };
    }
    return { text: "none", rule: "r.repair-none" };
  }

  function critique(input) {
    var lim = limitsOf(input);
    var plan = input.plan || { steps: [] };
    var steps = plan.steps || [];
    if (!steps.length) {
      return ["think · critique · nothing to critique",
        "build something first, or say critique <text> "
          + rule("r.plan-exists")].join("\n");
    }
    var lines = header("critique", input, input.text || "");
    inputLines(lines, input, lim);
    var done = steps.filter(function (s) { return s.status === "done"; }).length;
    var failed = steps.filter(function (s) { return s.status === "error"; }).length;
    var pending = steps.filter(function (s) { return s.status === "pending"; }).length;
    lines.push("plan: " + steps.length + " step(s) · " + done + " done · "
      + failed + " error · " + pending + " pending"
      + (input.plan.dry ? " · not run yet" : ""));
    var checks = checkList(input, lim);
    var evaluated = checks.slice(0, lim.thinkRules);
    var skipped = checks.length - evaluated.length;
    var findings = evaluated.filter(function (check) { return !check.ok; });
    var passed = evaluated.filter(function (check) { return check.ok; });
    lines.push("findings (" + findings.length + "):");
    if (!findings.length) lines.push("  none");
    findings.forEach(function (check) {
      lines.push("  · fail " + check.label + " · " + check.detail + " "
        + rule(check.id));
    });
    lines.push("passed: " + passed.length + " of " + evaluated.length
      + " checks · " + passed.map(function (check) {
        return check.id;
      }).join(", "));
    if (skipped > 0) {
      lines.push("skipped: " + skipped + " check(s) beyond thinkRules "
        + rule("r.input-cap"));
    }
    var repair = repairFor(findings, input, lim);
    lines.push("repair: " + repair.text + " " + rule(repair.rule));
    lines.push("verdict: " + findings.length + " finding(s) · "
      + passed.length + " check(s) passed"
      + (pending ? " · " + pending + " pending " + rule("r.pending-step") : ""));
    lines.push(rulesLine(lines));
    return lines.join("\n");
  }

  function run(mode, input) {
    var safe = input || {};
    if (mode === "decompose") return decompose(safe);
    if (mode === "reason") return reason(safe);
    if (mode === "tradeoff") return tradeoff(safe);
    if (mode === "critique") return critique(safe);
    throw new Error("unknown thinking mode: " + mode);
  }

  root.toolrxThinking = {
    MODES: MODES,
    RULES: RULES,
    splitOptions: splitOptions,
    run: run
  };
})(typeof self !== "undefined" ? self : this);

/* toolrx deterministic explain (step 61).
 *
 * One pure program behind the `explain.*` routes. It reads the state the
 * workspace already stores and prints a structured explanation of the active
 * project, the last plan, or the build theme. Every line that makes a claim
 * names the checked-in rule that produced it, and every file or system it
 * names is one of the project's real files.
 *
 * No DOM, no network, no clock, no writes. The caller passes every maximum
 * from `toolrx/limits.json`; the same input always produces byte-identical
 * text, and an explanation over `explainChars` is trimmed with a named note.
 */
(function (root) {
  "use strict";

  var TARGETS = ["project", "plan", "theme"];

  /* Stable rule ids. They appear in the output, so a reader can trace every
   * claim back to the rule that made it. */
  var RULES = {
    "r.project-exists": "the active project is read from the workspace",
    "r.plan-exists": "a plan is available to explain",
    "r.files-listed": "files listed are the project's real files",
    "r.files-cap": "files listed are bounded by explainFiles",
    "r.roles": "file roles come from the file name",
    "r.systems": "systems are the project files under systems/",
    "r.edits": "recent edits are the project's applied edits",
    "r.edits-cap": "recent edits listed are bounded by explainEdits",
    "r.seed": "the seed is the one stored in the build spec",
    "r.seed-missing": "no build spec seed is stored",
    "r.theme": "the page theme is the html class",
    "r.theme-spec": "the named theme is stored in the build spec",
    "r.theme-seed": "the theme pack was chosen from the seed",
    "r.theme-prompt": "the prompt named the theme",
    "r.theme-default": "dark is the default when no theme was requested",
    "r.budget-project": "project bytes are within projectBytes",
    "r.budget-files": "file count is within projectFiles",
    "r.budget-context": "context bytes are within contextBytes",
    "r.journal": "journal counts come from the project journal",
    "r.journal-empty": "no decisions are recorded yet",
    "r.plan-steps": "steps are listed in run order",
    "r.plan-status": "status is the recorded done, error, or pending",
    "r.plan-failure": "the failed step and its error are recorded",
    "r.plan-router": "a step has no exact catalog route",
    "r.risk-budget": "project is at or above 80% of projectBytes",
    "r.risk-files": "project is at or above 80% of projectFiles",
    "r.risk-context": "context is at or above 80% of contextBytes",
    "r.risk-seed": "the project has no stored seed",
    "r.risk-architecture": "the project has no ARCHITECTURE.md",
    "r.risk-journal": "the journal is empty",
    "r.risk-plan": "the last plan has an error",
    "r.risk-empty": "the project has no files",
    "r.risk-none": "no open risk was found",
    "r.trim": "the output was trimmed to explainChars",
    "r.limits": "numbers come from limits.json",
    "r.no-write": "explaining reads state and writes no file"
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

  function fmt(n) {
    var s = String(Math.round(Number(n) || 0));
    return s.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function oneLine(text) {
    return String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  }

  function quote(text) {
    return '"' + oneLine(text).slice(0, 120) + '"';
  }

  function plural(n, one, many) {
    return String(n) + " " + (n === 1 ? one : many);
  }

  function limitsOf(input) {
    var l = input.limits || {};
    return {
      chars: number(l.explainChars, 8000),
      files: number(l.explainFiles, 24),
      edits: number(l.explainEdits, 8),
      project: number(l.projectBytes, 524288),
      projectFiles: number(l.projectFiles, 32),
      context: number(l.contextBytes, 8192),
      planChars: number(l.planChars, 8000),
      planSteps: number(l.planSteps, 40),
      stepMs: number(l.stepMs, 4000),
      planMs: number(l.planMs, 160000),
      journalEntries: number(l.journalEntries, 24),
      journalBytes: number(l.journalBytes, 4096),
      journalText: number(l.journalText, 240)
    };
  }

  function finish(lines, lim) {
    var text = lines.join("\n");
    if (byteLength(text) <= lim.chars) return text;
    var note = "\n… trimmed to " + fmt(lim.chars)
      + " chars (explainChars) " + rule("r.trim");
    var room = lim.chars - byteLength(note);
    if (room < 0) room = 0;
    var cut = trimToBytes(text, room);
    var newline = cut.lastIndexOf("\n");
    if (newline > 0) cut = cut.slice(0, newline);
    return cut + note;
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

  function fileRole(name) {
    var n = String(name || "");
    if (n === "index.html") return "entry page";
    if (n === "styles.css") return "styles";
    if (n === "app.js") return "behavior";
    if (n === "README.md") return "readme";
    if (n === "ARCHITECTURE.md") return "architecture";
    if (n.indexOf("systems/") === 0) return "system";
    if (n.indexOf("core/") === 0) return "state module";
    if (n.indexOf("ui/") === 0) return "render module";
    if (n.indexOf("data/") === 0) return "data module";
    if (n.indexOf("content/") === 0) return "content module";
    if (/\.css$/.test(n)) return "styles";
    if (/\.js$/.test(n)) return "script";
    if (/\.html?$/.test(n)) return "page";
    if (/\.json$/.test(n)) return "data";
    if (/\.md$/.test(n)) return "notes";
    return "file";
  }

  function seedText(project) {
    return project && project.seed != null ? String(project.seed) : "none";
  }

  function seedRule(project) {
    return project && project.seed != null ? "r.seed" : "r.seed-missing";
  }

  function themeWord(source) {
    if (source === "prompt") return "prompt";
    if (source === "seed") return "seed";
    if (source === "spec") return "build spec";
    return "default";
  }

  function themeRule(source) {
    if (source === "prompt") return "r.theme-prompt";
    if (source === "seed") return "r.theme-seed";
    if (source === "spec") return "r.theme-spec";
    return "r.theme-default";
  }

  function themeLine(project) {
    var page = project.theme === "light" ? "light" : "dark";
    var name = oneLine(project.themeName || "");
    if (!name) {
      return "theme: " + page + " · no named theme · default page class "
        + rule("r.theme-default");
    }
    return "theme: " + page + " · named " + quote(name) + " · from the "
      + themeWord(project.themeSource) + " " + rule(themeRule(project.themeSource));
  }

  function fileLines(lines, files, lim) {
    var shown = files.slice(0, lim.files);
    lines.push("files (" + shown.length + " shown of " + files.length + "): "
      + rule("r.files-listed"));
    shown.forEach(function (file) {
      lines.push("  " + file.name + " · " + fmt(file.bytes) + " bytes · "
        + fmt(file.lines) + " lines · sha " + String(file.sha || "")
        + " · " + fileRole(file.name) + " " + rule("r.roles"));
    });
    if (files.length > shown.length) {
      lines.push("… " + (files.length - shown.length)
        + " more file(s) not listed " + rule("r.files-cap"));
    }
  }

  function editLine(lines, project, lim) {
    var edits = project.edits || [];
    var shown = edits.slice(Math.max(0, edits.length - lim.edits));
    var labels = shown.map(function (edit) {
      return oneLine(edit.label || edit.id || "edit");
    });
    lines.push("edits (" + edits.length + "): "
      + (labels.length ? labels.join(" · ") : "none") + " "
      + rule("r.edits"));
    if (edits.length > shown.length) {
      lines.push("… " + (edits.length - shown.length)
        + " older edit(s) not listed " + rule("r.edits-cap"));
    }
  }

  function journalLine(input) {
    var j = input.journal || {};
    var entries = j.entries || [];
    var summary = j.summary || {};
    var limit = j.limit || {};
    if (!entries.length) {
      return "journal: empty · 0/" + fmt(number(limit.entries, 24))
        + " entries " + rule("r.journal-empty");
    }
    var latest = entries[entries.length - 1];
    return "journal: " + entries.length + "/" + fmt(number(limit.entries, 24))
      + " entries · " + number(summary.decisions, 0) + " decision"
      + (number(summary.decisions, 0) === 1 ? "" : "s")
      + " · " + number(summary.rejections, 0) + " rejection"
      + (number(summary.rejections, 0) === 1 ? "" : "s")
      + " · " + number(summary.preferences, 0) + " preference"
      + (number(summary.preferences, 0) === 1 ? "" : "s")
      + " · latest #" + number(latest.seq, 0) + " " + latest.kind
      + " · " + oneLine(latest.topic) + " " + rule("r.journal");
  }

  function projectRisks(input, project, files, lim) {
    var risks = [];
    var context = input.context || {};
    var bytes = number(project.bytes, 0);
    if (!files.length) {
      risks.push({ text: "the project has no files", rule: "r.risk-empty" });
    }
    if (lim.project > 0 && bytes * 100 >= lim.project * 80) {
      risks.push({
        text: "project is at " + Math.round((bytes / lim.project) * 100)
          + "% of projectBytes",
        rule: "r.risk-budget"
      });
    }
    if (lim.projectFiles > 0 && files.length * 100 >= lim.projectFiles * 80) {
      risks.push({
        text: "files are at " + Math.round((files.length / lim.projectFiles) * 100)
          + "% of projectFiles",
        rule: "r.risk-files"
      });
    }
    if (lim.context > 0 && number(context.bytes, 0) * 100 >= lim.context * 80) {
      risks.push({
        text: "context is at " + Math.round((number(context.bytes, 0) / lim.context) * 100)
          + "% of contextBytes",
        rule: "r.risk-context"
      });
    }
    if (project.seed == null) {
      risks.push({ text: "no seed is stored in the build spec",
                   rule: "r.risk-seed" });
    }
    var hasArchitecture = files.some(function (file) {
      return file.name === "ARCHITECTURE.md";
    });
    if (!hasArchitecture) {
      risks.push({ text: "the project has no ARCHITECTURE.md",
                   rule: "r.risk-architecture" });
    }
    if (!((input.journal && input.journal.entries) || []).length) {
      risks.push({ text: "the journal is empty", rule: "r.risk-journal" });
    }
    if (input.plan && number(input.plan.failedAt, -1) >= 0) {
      risks.push({
        text: "the last plan has an error at step "
          + (number(input.plan.failedAt, 0) + 1),
        rule: "r.risk-plan"
      });
    }
    return risks;
  }

  function projectExplain(input) {
    var lim = limitsOf(input);
    var project = input.project;
    if (!project) {
      return finish([
        "explain · project · no active project",
        "build something first, then ask again " + rule("r.project-exists"),
        "writes: no file " + rule("r.no-write")
      ], lim);
    }
    var files = (project.files || []).slice().sort(function (a, b) {
      return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0);
    });
    var systems = files.filter(function (file) {
      return String(file.name).indexOf("systems/") === 0;
    }).map(function (file) { return file.name; });
    var context = input.context || {};
    var lines = [
      "explain · project · " + oneLine(project.name) + " · "
        + plural(files.length, "file", "files") + " · seed " + seedText(project)
        + " " + rule("r.project-exists"),
      "project: " + oneLine(project.name) + " (" + oneLine(project.slug)
        + ") · kind " + oneLine(project.kind || "unknown") + " · "
        + fmt(number(project.bytes, 0)) + "/" + fmt(lim.project) + " bytes "
        + rule("r.budget-project"),
      themeLine(project)
    ];
    fileLines(lines, files, lim);
    lines.push("systems (" + systems.length + "): "
      + (systems.length ? systems.join(" · ") : "none") + " "
      + rule("r.systems"));
    editLine(lines, project, lim);
    lines.push("seed: " + seedText(project) + " · "
      + (project.seed != null ? "from the build spec" : "no build spec seed is stored")
      + " " + rule(seedRule(project)));
    lines.push("budgets: files " + files.length + "/" + lim.projectFiles
      + " · project " + fmt(number(project.bytes, 0)) + "/" + fmt(lim.project)
      + " bytes · context " + fmt(number(context.bytes, 0)) + "/"
      + fmt(lim.context) + " bytes · explain cap " + fmt(lim.chars) + " chars "
      + rule("r.limits"));
    lines.push(journalLine(input));
    var risks = projectRisks(input, project, files, lim);
    lines.push("risks (" + risks.length + "):");
    if (!risks.length) {
      lines.push("  none " + rule("r.risk-none"));
    } else {
      risks.forEach(function (risk) {
        lines.push("  · " + risk.text + " " + rule(risk.rule));
      });
    }
    lines.push("writes: no file " + rule("r.no-write"));
    lines.push(rulesLine(lines));
    return finish(lines, lim);
  }

  function planChars(steps) {
    return byteLength(steps.map(function (step) {
      return String(step.text == null ? "" : step.text);
    }).join("\n"));
  }

  function planRisks(input, plan, steps, lim) {
    var risks = [];
    var failed = steps.filter(function (step) { return step.status === "error"; });
    var pending = steps.filter(function (step) { return step.status === "pending"; });
    var router = steps.filter(function (step) { return !step.exact; });
    var seen = {};
    var duplicates = [];
    steps.forEach(function (step) {
      var key = oneLine(step.text).toLowerCase();
      if (seen[key]) duplicates.push(step.text);
      seen[key] = true;
    });
    if (failed.length) {
      risks.push({ text: "step " + (steps.indexOf(failed[0]) + 1)
        + " failed", rule: "r.risk-plan" });
    }
    if (pending.length) {
      risks.push({ text: plural(pending.length, "pending step", "pending steps")
        + " not run", rule: "r.plan-status" });
    }
    if (router.length) {
      risks.push({ text: plural(router.length, "step has", "steps have")
        + " no exact route", rule: "r.plan-router" });
    }
    if (duplicates.length) {
      risks.push({ text: "repeated step " + quote(duplicates[0]),
                   rule: "r.plan-steps" });
    }
    if (steps.length > lim.planSteps) {
      risks.push({ text: "steps " + steps.length + "/" + lim.planSteps,
                   rule: "r.risk-plan" });
    }
    var chars = planChars(steps);
    if (chars > lim.planChars) {
      risks.push({ text: "chars " + fmt(chars) + "/" + fmt(lim.planChars),
                   rule: "r.risk-plan" });
    }
    if (steps.length * lim.stepMs > lim.planMs) {
      risks.push({ text: "worst-case time "
        + fmt((steps.length * lim.stepMs) / 1000) + " s/"
        + fmt(lim.planMs / 1000) + " s", rule: "r.risk-plan" });
    }
    return risks;
  }

  function planExplain(input) {
    var lim = limitsOf(input);
    var plan = input.plan;
    if (!plan || !Array.isArray(plan.steps) || !plan.steps.length) {
      return finish([
        "explain · plan · no plan to explain",
        "run a plan first, then ask again " + rule("r.plan-exists"),
        "writes: no file " + rule("r.no-write")
      ], lim);
    }
    var steps = plan.steps;
    var done = steps.filter(function (step) { return step.status === "done"; }).length;
    var failed = steps.filter(function (step) { return step.status === "error"; }).length;
    var pending = steps.filter(function (step) { return step.status === "pending"; }).length;
    var chars = planChars(steps);
    var time = steps.length * lim.stepMs;
    var lines = [
      "explain · plan · " + oneLine(plan.from || "plan") + " · "
        + plural(steps.length, "step", "steps") + " · " + done + " done · "
        + failed + " error · " + pending + " pending " + rule("r.plan-exists"),
      "plan: " + steps.length + "/" + lim.planSteps + " steps · chars "
        + fmt(chars) + "/" + fmt(lim.planChars) + " · time "
        + fmt(time / 1000) + " s/" + fmt(lim.planMs / 1000) + " s "
        + rule("r.plan-steps")
    ];
    steps.forEach(function (step, i) {
      lines.push("  " + (i + 1) + ". " + oneLine(step.text) + " · "
        + (step.exact ? "exact " + oneLine(step.op || "command") : "router")
        + " · " + oneLine(step.status || "pending") + " "
        + rule(step.exact ? "r.plan-status" : "r.plan-router"));
    });
    var failedAt = number(plan.failedAt, -1);
    if (failedAt >= 0 && failedAt < steps.length) {
      lines.push("failure: step " + (failedAt + 1) + " · "
        + oneLine(plan.errorText || "no error text recorded") + " "
        + rule("r.plan-failure"));
    } else {
      lines.push("failure: none recorded " + rule("r.plan-status"));
    }
    lines.push("budgets: steps " + steps.length + "/" + lim.planSteps
      + " · chars " + fmt(chars) + "/" + fmt(lim.planChars)
      + " · time " + fmt(time / 1000) + " s/" + fmt(lim.planMs / 1000)
      + " s · explain cap " + fmt(lim.chars) + " chars " + rule("r.limits"));
    var risks = planRisks(input, plan, steps, lim);
    lines.push("risks (" + risks.length + "):");
    if (!risks.length) {
      lines.push("  none " + rule("r.risk-none"));
    } else {
      risks.forEach(function (risk) {
        lines.push("  · " + risk.text + " " + rule(risk.rule));
      });
    }
    lines.push("writes: no file " + rule("r.no-write"));
    lines.push(rulesLine(lines));
    return finish(lines, lim);
  }

  function themeExplain(input) {
    var lim = limitsOf(input);
    var project = input.project;
    if (!project) {
      return finish([
        "explain · theme · no active project",
        "build something first, then ask again " + rule("r.project-exists"),
        "writes: no file " + rule("r.no-write")
      ], lim);
    }
    var context = input.context || {};
    var name = oneLine(project.themeName || "");
    var source = project.themeSource || "default";
    var page = project.theme === "light" ? "light" : "dark";
    var lines = [
      "explain · theme · " + oneLine(project.name) + " · seed "
        + seedText(project) + " " + rule("r.project-exists"),
      "page: " + page + " · the html class sets the light/dark page theme "
        + rule("r.theme")
    ];
    if (name) {
      lines.push("named: " + quote(name) + " · from the " + themeWord(source)
        + " " + rule(themeRule(source)));
    } else {
      lines.push("named: none · no theme word was stored in the build spec "
        + rule("r.theme-default"));
    }
    if (source === "prompt") {
      lines.push("why: the prompt named " + quote(name)
        + ", so the build spec stored that theme " + rule("r.theme-prompt"));
    } else if (source === "seed") {
      lines.push("why: the prompt did not name a theme, so the build used the "
        + "pack chosen by seed " + seedText(project) + " " + rule("r.theme-seed"));
    } else if (source === "spec") {
      lines.push("why: the build spec stores the theme, but neither the prompt "
        + "nor the seed explains it " + rule("r.theme-spec"));
    } else {
      lines.push("why: no theme word was stored, so the page uses the default "
        + page + " class " + rule("r.theme-default"));
    }
    lines.push("seed: " + seedText(project) + " · "
      + (project.seed != null
        ? "the build spec seed chooses seeded content and can choose the theme pack"
        : "no seed stored in the build spec") + " " + rule(seedRule(project)));
    if (project.art || project.subtheme) {
      lines.push("style: " + [oneLine(project.art || ""),
        oneLine(project.subtheme || "")].filter(Boolean).join(" · ") + " "
        + rule("r.theme-spec"));
    }
    if (project.specLine) {
      lines.push("spec: " + oneLine(project.specLine));
    }
    lines.push("budgets: project " + fmt(number(project.bytes, 0)) + "/"
      + fmt(lim.project) + " bytes · context " + fmt(number(context.bytes, 0))
      + "/" + fmt(lim.context) + " bytes · explain cap " + fmt(lim.chars)
      + " chars " + rule("r.limits"));
    lines.push("writes: no file " + rule("r.no-write"));
    lines.push(rulesLine(lines));
    return finish(lines, lim);
  }

  function run(target, input) {
    var safe = input || {};
    if (target === "project") return projectExplain(safe);
    if (target === "plan") return planExplain(safe);
    if (target === "theme") return themeExplain(safe);
    throw new Error("unknown explain target: " + target);
  }

  root.toolrxExplain = {
    TARGETS: TARGETS,
    RULES: RULES,
    fileRole: fileRole,
    run: run
  };
})(typeof self !== "undefined" ? self : this);

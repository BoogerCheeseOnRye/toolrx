/* toolrx deterministic verification (step 66).
 *
 * One pure program behind the `verify.*` routes. It answers three questions
 * about the active project without a test runner, a shell, or the network:
 *
 *   files   which files the build spec promised, which files exist, and the
 *           exact names that are missing or extra
 *   smoke   eight pure predicates over the project's own file text
 *   report  both, plus one bounded verdict
 *
 * Expected files derive from the stored build spec; actual files are the
 * project's real file names. Every claim names the checked-in rule that made
 * it. Nothing is executed, read from disk, fetched, or written.
 */
(function (root) {
  "use strict";

  var TARGETS = ["files", "smoke", "report"];

  var BASE_FILES = ["ARCHITECTURE.md", "README.md", "app.js", "index.html",
    "styles.css"];
  var RPG_SHARED = ["engine2d.js", "rpg2.js", "worldgen.js"];
  var THREE_D_ROUTE = { platformer: 1, maze: 1, racer: 1, explore: 1,
    waveshooter: 1, builder: 1 };
  var ENGINE_GENRES = { platformer: 1, snake: 1, breakout: 1, shooter: 1,
    racer: 1, rpg: 1, twinstick: 1, roguelike: 1, towerdefense: 1, merges: 1,
    farmingsim: 1, rhythm: 1, waveshooter: 1 };
  var STARTER_KINDS = { authapp: 1, datadash: 1, notebook: 1, multipage: 1,
    apimock: 1 };
  var STARTER_FILES = {
    authapp: ["auth.js"],
    datadash: ["data.js"],
    notebook: ["seed-notes.js"],
    multipage: ["about.html", "contact.html", "docs.html", "site.js"],
    apimock: ["api.js", "openapi.json"]
  };

  var RULES = {
    "r.project-exists": "the active project is read from the workspace",
    "r.files": "expected files come from the build spec, actual files from the project",
    "r.spec": "the expected list is derived from the stored build spec",
    "r.actual": "the actual list is the project's real file names",
    "r.missing": "missing names are expected files the project does not have",
    "r.extra": "extra names are project files the spec did not promise",
    "r.files-cap": "listed file names are bounded by verifyFiles",
    "r.smoke": "every smoke check is a pure predicate over project file text",
    "r.check-index": "index.html exists and has content",
    "r.check-title": "the index title matches the project name",
    "r.check-styles": "styles.css exists and has content",
    "r.check-entry": "app.js defines a function or an event listener",
    "r.check-order": "local scripts load before app.js",
    "r.check-links": "every local link and script src names a real file",
    "r.check-docs": "README.md and ARCHITECTURE.md have content",
    "r.check-budget": "file count and bytes are within the project budget",
    "r.checks-cap": "checks run are bounded by verifyChecks",
    "r.report": "the report combines the file diff and the smoke checks",
    "r.verdict": "the verdict is ok only when files and checks all pass",
    "r.read-only": "checks read project text only and execute nothing",
    "r.limits": "the report is bounded by verifyReportChars",
    "r.no-write": "verification writes no project file",
    "r.trim": "an over-cap report is trimmed at a line boundary"
  };

  var RULE = /r\.[a-z][a-z-]*/;

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

  function number(value, fallback) {
    var n = Number(value);
    if (!isFinite(n) || n < 0) return fallback;
    return Math.floor(n);
  }

  function oneLine(text) {
    return String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  }

  function rule(id) {
    return "· " + id;
  }

  function limits(input) {
    var l = (input && input.limits) || {};
    return {
      files: number(l.verifyFiles, 32),
      checks: number(l.verifyChecks, 8),
      chars: number(l.verifyReportChars, 4000),
      project: number(l.projectBytes, 524288),
      projectFiles: number(l.projectFiles, 32)
    };
  }

  function finish(lines, lim) {
    var text = lines.join("\n");
    if (byteLength(text) <= lim.chars) return text;
    var note = "\n… trimmed to " + fmt(lim.chars)
      + " chars (verifyReportChars) " + rule("r.trim");
    var room = lim.chars - byteLength(note);
    if (room < 0) room = 0;
    var cut = trimToBytes(text, room);
    var newline = cut.lastIndexOf("\n");
    if (newline > 0) cut = cut.slice(0, newline);
    return cut + note;
  }

  function rulesLine(lines) {
    var seen = [];
    var re = new RegExp(RULE.source, "g");
    var text = lines.join("\n");
    var match;
    while ((match = re.exec(text))) {
      if (seen.indexOf(match[0]) < 0) seen.push(match[0]);
    }
    return "rules: " + seen.join(", ");
  }

  function projectOf(input) {
    var p = input && input.project;
    if (!p || typeof p !== "object") return null;
    return p;
  }

  function filesOf(project) {
    var raw = (project && project.files) || {};
    var out = {};
    Object.keys(raw).forEach(function (name) {
      out[String(name)] = String(raw[name] == null ? "" : raw[name]);
    });
    return out;
  }

  function wantsContent(spec) {
    var genre = String(spec.genre || spec.kind || "");
    if (STARTER_KINDS[genre]) return false;
    var counts = spec.counts || {};
    return !!((spec.features && spec.features.length)
      || Object.keys(counts).length
      || spec.levels
      || spec.size
      || spec.subtheme);
  }

  function expectedFiles(spec) {
    spec = spec || {};
    var genre = String(spec.genre || spec.kind || "");
    var names = BASE_FILES.slice();
    if (genre === "rpg") {
      names = names.concat(RPG_SHARED);
    } else if (spec.dim === "3D" && THREE_D_ROUTE[genre]) {
      names.push("engine3d.js");
    } else if (ENGINE_GENRES[genre]) {
      names.push("engine2d.js");
    }
    if (wantsContent(spec)) names.push("content.js");
    (STARTER_FILES[genre] || []).forEach(function (name) { names.push(name); });
    (spec.modules || []).forEach(function (name) {
      if (name) names.push(String(name));
    });
    (spec.systems || []).forEach(function (id) {
      if (id) names.push("systems/" + String(id) + ".js");
    });
    var seen = {};
    var out = [];
    names.forEach(function (name) {
      if (!seen[name]) { seen[name] = true; out.push(name); }
    });
    out.sort();
    return out;
  }

  function decodeEntities(text) {
    return String(text == null ? "" : text)
      .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
      .replace(/&amp;/g, "&");
  }

  function titleOf(html) {
    var match = /<title[^>]*>([\s\S]*?)<\/title>/i.exec(String(html || ""));
    return match ? oneLine(decodeEntities(match[1])) : "";
  }

  function scriptTags(html) {
    var out = [];
    var re = /<script\b[^>]*\bsrc\s*=\s*["']([^"']+)["'][^>]*>/gi;
    var match;
    var text = String(html || "");
    while ((match = re.exec(text))) {
      out.push({ src: match[1], at: match.index });
    }
    return out;
  }

  function localPath(value) {
    var name = String(value == null ? "" : value).trim();
    if (!name) return "";
    if (name.charAt(0) === "#") return "";
    if (name.indexOf("//") === 0) return "";
    if (/^[a-z][a-z0-9+.-]*:/i.test(name)) return "";
    name = name.replace(/[?#].*$/, "");
    while (name.indexOf("./") === 0) name = name.slice(2);
    if (name.charAt(0) === "/") name = name.slice(1);
    if (!name || name === "." || name.slice(-1) === "/") return "";
    return name;
  }

  function linkNames(html) {
    var out = [];
    var text = String(html || "");
    var re = /\b(?:href|src)\s*=\s*["']([^"']+)["']/gi;
    var match;
    while ((match = re.exec(text))) {
      var name = localPath(match[1]);
      if (name) out.push(name);
    }
    return out;
  }

  function byteSize(files) {
    var total = 0;
    Object.keys(files).forEach(function (name) {
      total += byteLength(files[name]);
    });
    return total;
  }

  function check(id, pass, label, detail) {
    return { id: id, pass: !!pass, label: label, detail: detail || "" };
  }

  function smokeChecks(project, files, lim) {
    var names = Object.keys(files).sort();
    var has = function (name) {
      return Object.prototype.hasOwnProperty.call(files, name);
    };
    var text = function (name) { return has(name) ? files[name] : ""; };
    var html = text("index.html");
    var checks = [];

    checks.push(check("r.check-index", has("index.html") && oneLine(html) !== "",
      "index.html exists and has content",
      !has("index.html") ? "index.html is missing"
        : (oneLine(html) === "" ? "index.html is empty" : "")));

    var title = titleOf(html);
    var wantTitle = oneLine(project.name) + " · toolrx";
    checks.push(check("r.check-title", title === wantTitle,
      "title matches the project name",
      !title ? "no title tag"
        : (title === wantTitle ? "" : 'found "' + title + '"')));

    checks.push(check("r.check-styles",
      has("styles.css") && oneLine(text("styles.css")) !== "",
      "styles.css has content",
      !has("styles.css") ? "styles.css is missing"
        : (oneLine(text("styles.css")) === "" ? "styles.css is empty" : "")));

    var js = text("app.js");
    checks.push(check("r.check-entry",
      has("app.js")
        && /function\s+[A-Za-z_$][A-Za-z0-9_$]*|=>|addEventListener\s*\(/
          .test(js),
      "app.js defines a function or event listener",
      !has("app.js") ? "app.js is missing"
        : (/function\s+[A-Za-z_$][A-Za-z0-9_$]*|=>|addEventListener\s*\(/
            .test(js) ? "" : "no function or event listener")));

    var tags = scriptTags(html);
    var appAt = -1;
    for (var i = 0; i < tags.length; i++) {
      if (localPath(tags[i].src) === "app.js") { appAt = tags[i].at; break; }
    }
    var after = [];
    if (appAt >= 0) {
      tags.forEach(function (tag) {
        if (tag.at > appAt && localPath(tag.src) !== "app.js") {
          after.push(localPath(tag.src));
        }
      });
    }
    checks.push(check("r.check-order", appAt >= 0 && after.length === 0,
      "scripts load before app.js",
      appAt < 0 ? "app.js is not referenced"
        : (after.length ? after.length + " script(s) load after app.js: "
            + after.join(", ") : "")));

    var links = linkNames(html);
    var missingLinks = [];
    links.forEach(function (name) {
      if (!has(name) && missingLinks.indexOf(name) < 0) missingLinks.push(name);
    });
    checks.push(check("r.check-links",
      has("index.html") && missingLinks.length === 0,
      "local links resolve to real files",
      !has("index.html") ? "index.html is missing"
        : (missingLinks.length ? missingLinks.length + " missing: "
            + missingLinks.slice(0, 4).join(", ") : "")));

    var docs = ["README.md", "ARCHITECTURE.md"].filter(function (name) {
      return !has(name) || oneLine(files[name]) === "";
    });
    checks.push(check("r.check-docs", docs.length === 0,
      "README.md and ARCHITECTURE.md have content",
      docs.length ? "missing or empty: " + docs.join(", ") : ""));

    var bytes = byteSize(files);
    var overFiles = lim.projectFiles > 0 && names.length > lim.projectFiles;
    var overBytes = lim.project > 0 && bytes > lim.project;
    checks.push(check("r.check-budget", !overFiles && !overBytes,
      "files and bytes are within budget",
      overFiles || overBytes
        ? "files " + names.length + "/" + fmt(lim.projectFiles)
          + " · bytes " + fmt(bytes) + "/" + fmt(lim.project)
        : ""));

    return checks;
  }

  function fileDiff(project) {
    var spec = project.spec || {};
    var expected = expectedFiles(spec);
    var files = filesOf(project);
    var actual = Object.keys(files).sort();
    var missing = expected.filter(function (name) {
      return actual.indexOf(name) < 0;
    });
    var extra = actual.filter(function (name) {
      return expected.indexOf(name) < 0;
    });
    return { expected: expected, actual: actual, missing: missing,
             extra: extra, files: files };
  }

  function listLine(label, names, id, lim) {
    var shown = names.slice(0, lim.files);
    var lines = [label + " (" + names.length + "): "
      + (shown.length ? shown.join(" · ") : "none") + " " + rule(id)];
    if (names.length > shown.length) {
      lines.push("… " + (names.length - shown.length) + " more " + label
        + " not listed " + rule("r.files-cap"));
    }
    return lines;
  }

  function budgetLine(project, files, lim) {
    return "budgets: files " + Object.keys(files).length + "/"
      + fmt(lim.projectFiles) + " · bytes " + fmt(byteSize(files)) + "/"
      + fmt(lim.project) + " · verify cap " + fmt(lim.chars)
      + " chars " + rule("r.limits");
  }

  function filesText(input, project, lim) {
    var diff = fileDiff(project);
    var ok = diff.missing.length === 0 && diff.extra.length === 0;
    var lines = [
      "verify · files · " + oneLine(project.name) + " · "
        + diff.expected.length + " expected · " + diff.actual.length
        + " actual · " + (ok ? "ok" : "fail") + " " + rule("r.files")
    ];
    lines = lines.concat(listLine("expected", diff.expected, "r.spec", lim));
    lines = lines.concat(listLine("actual", diff.actual, "r.actual", lim));
    lines = lines.concat(listLine("missing", diff.missing, "r.missing", lim));
    lines = lines.concat(listLine("extra", diff.extra, "r.extra", lim));
    lines.push(budgetLine(project, diff.files, lim));
    lines.push("writes: no file " + rule("r.no-write"));
    lines.push(rulesLine(lines));
    return finish(lines, lim);
  }

  function checkLines(checks) {
    return checks.map(function (c) {
      return "  " + (c.pass ? "pass" : "fail") + " · " + c.label
        + (c.detail ? " · " + c.detail : "") + " " + rule(c.id);
    });
  }

  function capChecks(all, lim) {
    var checks = all.slice(0, lim.checks);
    return { checks: checks, skipped: all.length - checks.length };
  }

  function smokeText(input, project, lim) {
    var files = filesOf(project);
    var capped = capChecks(smokeChecks(project, files, lim), lim);
    var checks = capped.checks;
    var passed = checks.filter(function (c) { return c.pass; }).length;
    var failed = checks.length - passed;
    var lines = [
      "verify · smoke · " + oneLine(project.name) + " · " + checks.length
        + " checks · " + passed + " pass · " + failed + " fail · "
        + (failed ? "fail" : "ok") + " " + rule("r.smoke")
    ];
    lines = lines.concat(checkLines(checks));
    if (capped.skipped > 0) {
      lines.push("… " + capped.skipped + " more check(s) not run "
        + rule("r.checks-cap"));
    }
    lines.push("reads: project files only · nothing is executed "
      + rule("r.read-only"));
    lines.push(budgetLine(project, files, lim));
    lines.push("writes: no file " + rule("r.no-write"));
    lines.push(rulesLine(lines));
    return finish(lines, lim);
  }

  function reportText(input, project, lim) {
    var diff = fileDiff(project);
    var capped = capChecks(smokeChecks(project, diff.files, lim), lim);
    var checks = capped.checks;
    var passed = checks.filter(function (c) { return c.pass; }).length;
    var failed = checks.length - passed;
    var ok = diff.missing.length === 0 && diff.extra.length === 0 && failed === 0;
    var lines = [
      "verify · report · " + oneLine(project.name) + " · "
        + diff.expected.length + "/" + diff.actual.length + " files · "
        + passed + "/" + checks.length + " checks · "
        + (ok ? "ok" : "fail") + " " + rule("r.report"),
      "files: " + diff.expected.length + " expected · " + diff.actual.length
        + " actual · " + diff.missing.length + " missing · "
        + diff.extra.length + " extra " + rule("r.files")
    ];
    var verdict = ok
      ? "verdict: ok · every expected file is present and every smoke check passed"
      : "verdict: fail · " + diff.missing.length + " missing · "
        + diff.extra.length + " extra · " + failed + " failed checks";
    lines.push(verdict + " " + rule("r.verdict"));
    lines = lines.concat(listLine("missing", diff.missing, "r.missing", lim));
    lines = lines.concat(listLine("extra", diff.extra, "r.extra", lim));
    lines = lines.concat(checkLines(checks));
    if (capped.skipped > 0) {
      lines.push("… " + capped.skipped + " more check(s) not run "
        + rule("r.checks-cap"));
    }
    lines.push("reads: project files only · nothing is executed "
      + rule("r.read-only"));
    lines.push(budgetLine(project, diff.files, lim));
    lines.push("writes: no file " + rule("r.no-write"));
    lines.push(rulesLine(lines));
    return finish(lines, lim);
  }

  function missingText(target, lim) {
    return finish([
      "verify · " + target + " · no active project",
      "build something first, then ask again " + rule("r.project-exists"),
      "writes: no file " + rule("r.no-write"),
    ], lim);
  }

  function run(target, input) {
    var safe = input || {};
    var lim = limits(safe);
    var project = projectOf(safe);
    if (!project) return missingText(target, lim);
    if (target === "files") return filesText(safe, project, lim);
    if (target === "smoke") return smokeText(safe, project, lim);
    if (target === "report") return reportText(safe, project, lim);
    throw new Error("unknown verify target: " + target);
  }

  root.toolrxVerify = {
    TARGETS: TARGETS,
    RULES: RULES,
    expectedFiles: expectedFiles,
    wantsContent: wantsContent,
    smokeChecks: function (project, limits) {
      var lim = limits || {};
      return smokeChecks(project || { name: "" }, filesOf(project), {
        files: number(lim.verifyFiles, 32),
        checks: number(lim.verifyChecks, 8),
        chars: number(lim.verifyReportChars, 4000),
        project: number(lim.projectBytes, 524288),
        projectFiles: number(lim.projectFiles, 32)
      });
    },
    run: run
  };
})(typeof self !== "undefined" ? self : this);

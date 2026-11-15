/* toolrx budget bars.
 *
 * One pure model for the five budgets the roadmap promises: characters,
 * steps, context bytes, project bytes, and time. The same descriptor drives
 * the plan preview, the live plan bar, and the last-run detail, so the DOM
 * cannot invent a friendlier number than the report.
 *
 * No DOM, no fetch, no limits of its own: every maximum comes from
 * toolrxLimits, which is generated from toolrx/limits.json.
 */
(function (root) {
  "use strict";

  var ORDER = ["chars", "steps", "context", "project", "time"];
  var LABELS = {
    chars: "characters",
    steps: "steps",
    context: "context",
    project: "project",
    time: "time"
  };
  var UNITS = {
    chars: "chars",
    steps: "steps",
    context: "bytes",
    project: "bytes",
    time: "ms"
  };
  var WARN_AT = 0.8;

  function number(value, fallback) {
    var n = Number(value);
    return isFinite(n) && n >= 0 ? n : fallback;
  }

  function group(value) {
    var n = Math.round(number(value, 0));
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function format(value, unit) {
    var n = number(value, 0);
    if (unit === "bytes") {
      if (n < 1024) return group(n) + " B";
      if (n < 1024 * 1024) {
        return (n / 1024).toFixed(n < 10240 ? 1 : 0) + " KB";
      }
      return (n / (1024 * 1024)).toFixed(1) + " MB";
    }
    if (unit === "ms") {
      if (n < 1000) return group(n) + " ms";
      return (n / 1000).toFixed(n < 10000 ? 1 : 0) + " s";
    }
    return group(n) + " " + unit;
  }

  function one(key, used, max) {
    var u = number(used, 0);
    var m = number(max, 0);
    var ratio = m > 0 ? u / m : 0;
    var over = m > 0 && u > m;
    var level = over ? "over" : (m > 0 && ratio >= WARN_AT ? "warn" : "ok");
    var unit = UNITS[key];
    return {
      key: key,
      label: LABELS[key],
      unit: unit,
      used: u,
      max: m,
      remaining: Math.max(0, m - u),
      ratio: Math.round(ratio * 10000) / 10000,
      level: level,
      over: over,
      readout: format(u, unit) + " / " + format(m, unit),
      room: format(Math.max(0, m - u), unit)
    };
  }

  function bars(spec) {
    spec = spec || {};
    return ORDER.map(function (key) {
      var item = spec[key] || {};
      return one(key, item.used, item.max);
    });
  }

  function over(list) {
    return (list || []).filter(function (bar) { return bar.over; });
  }

  root.toolrxBudget = {
    ORDER: ORDER,
    LABELS: LABELS,
    UNITS: UNITS,
    WARN_AT: WARN_AT,
    bars: bars,
    over: over,
    format: format
  };
})(typeof self !== "undefined" ? self : this);

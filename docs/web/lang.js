/* toolrx language recognition.
 *
 * Offline, deterministic detection for programming languages and natural
 * languages, plus a small phrase table for known localized intents. The data
 * lives in `i18n.json`; call `configure(data)` before using the detectors.
 *
 * This is recognition, not translation. Unknown or low-confidence input is
 * reported as unknown/ambiguous instead of being guessed.
 */
(function (root) {
  "use strict";

  let DATA = null;
  let PROG = [];
  let NAT = [];
  let SCRIPTS = [];
  let PHRASES = [];
  let ALIAS = Object.create(null);

  const SCRIPT_NAMES = {
    ja: "kana", ko: "hangul", hi: "devanagari", ar: "arabic",
    ru: "cyrillic", uk: "ukrainian", el: "greek", he: "hebrew",
    th: "thai", zh: "han characters"
  };
  const NATURAL_NAMES = {
    hi: "Hindi", ja: "Japanese", zh: "Chinese", ko: "Korean", ar: "Arabic",
    ru: "Russian", uk: "Ukrainian", el: "Greek", he: "Hebrew", th: "Thai",
    bg: "Bulgarian", fa: "Persian", ur: "Urdu", mr: "Marathi", ne: "Nepali"
  };

  function fold(s) {
    return String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function clean(s) {
    return String(s || "").trim()
      .replace(/[¿¡]/g, "")
      .replace(/[?!.,;:\s]+$/, "")
      .replace(/\s+/g, " ");
  }

  function round(n) {
    return Math.round(n * 100) / 100;
  }

  function compileSignal(sig) {
    return { rx: new RegExp(sig.re, "im"), w: sig.w, label: sig.label };
  }

  function configure(data) {
    DATA = data || {};
    ALIAS = Object.create(null);
    PROG = Object.keys(DATA.programming || {}).map(function (id) {
      const p = DATA.programming[id];
      const out = {
        id: id,
        name: p.name || id,
        aliases: (p.aliases || []).map(fold),
        extensions: (p.extensions || []).map(function (e) { return String(e).toLowerCase(); }),
        signals: (p.signals || []).map(compileSignal)
      };
      [id].concat(out.aliases).forEach(function (a) { ALIAS[fold(a)] = id; });
      return out;
    });
    NAT = Object.keys(DATA.natural || {}).map(function (id) {
      const n = DATA.natural[id];
      return {
        id: id,
        name: n.name || id,
        stop: new Set((n.stopwords || []).map(fold)),
        marksRx: n.marks ? new RegExp(n.marks, "i") : null
      };
    });
    SCRIPTS = (DATA.scripts || []).map(function (s) {
      return Object.assign({}, s, {
        rx: new RegExp(s.re),
        zhRx: s.zh_markers ? new RegExp(s.zh_markers) : null,
        label: SCRIPT_NAMES[s.lang] || "script"
      });
    });
    PHRASES = (DATA.phrases || []).map(function (p) {
      return Object.assign({}, p, { rx: new RegExp(p.re, "i") });
    });
    return true;
  }

  function ready() {
    return !!(DATA && PROG.length);
  }

  function nameOf(mode, id) {
    if (!id) return "unknown";
    if (mode === "programming" && DATA && DATA.programming[id]) {
      return DATA.programming[id].name;
    }
    if (mode === "natural" && DATA && DATA.natural[id]) {
      return DATA.natural[id].name;
    }
    if (mode === "natural" && NATURAL_NAMES[id]) return NATURAL_NAMES[id];
    return String(id).toUpperCase();
  }

  function unknown(mode) {
    return { lang: null, confidence: 0, alternatives: [], signals: [], unknown: true, mode: mode };
  }

  function detectProgramming(text) {
    const raw = String(text || "");
    if (!raw.trim() || !ready()) return unknown("programming");
    // A sample is enough to identify a language; cap the scan so huge files
    // stay inside the interactive budget.
    const sample = raw.length > 8192 ? raw.slice(0, 8192) : raw;

    const scores = Object.create(null);
    const why = Object.create(null);
    function bump(id, w, label) {
      if (!DATA.programming[id]) return;
      scores[id] = (scores[id] || 0) + w;
      if (label) {
        why[id] = why[id] || [];
        if (why[id].indexOf(label) < 0) why[id].push(label);
      }
    }

    const fence = /(?:```|~~~)\s*([A-Za-z0-9+#.-]+)/.exec(sample);
    if (fence) {
      const hinted = ALIAS[fold(fence[1])];
      if (hinted) bump(hinted, 10, "fence: " + fence[1]);
    }

    const extRe = /\b[\w-]+\.([A-Za-z0-9]+)\b/g;
    let extMatch;
    while ((extMatch = extRe.exec(sample))) {
      const ext = extMatch[1].toLowerCase();
      PROG.forEach(function (p) {
        if (p.extensions.indexOf(ext) >= 0) bump(p.id, 6, ext + " file");
      });
    }

    PROG.forEach(function (p) {
      p.signals.forEach(function (s) {
        if (s.rx.test(sample)) bump(p.id, s.w, s.label);
      });
    });

    if (scores.html && /<script\b/i.test(sample)) bump("javascript", 3, "inline <script>");
    if (scores.html && /<style\b/i.test(sample)) bump("css", 3, "inline <style>");

    const ranked = Object.keys(scores)
      .filter(function (id) { return scores[id] > 0; })
      .map(function (id) { return { id: id, score: scores[id] }; })
      .sort(function (a, b) { return b.score - a.score || (a.id < b.id ? -1 : 1); });

    if (!ranked.length || ranked[0].score < 2) {
      const low = ranked.length ? ranked[0] : null;
      if (low && low.score >= 1) {
        return {
          lang: low.id, name: nameOf("programming", low.id),
          confidence: 0.4, alternatives: [], signals: why[low.id] || [],
          uncertain: true, mode: "programming"
        };
      }
      return unknown("programming");
    }

    const top = ranked[0];
    const second = ranked[1] || null;
    const share = top.score / (top.score + (second ? second.score : 0));
    const evidence = Math.min(1, top.score / 8);
    let confidence = 0.55 + 0.35 * share + 0.10 * evidence;
    if (top.score < 3) confidence = Math.min(confidence, 0.62);
    confidence = Math.min(0.99, round(confidence));

    const alternatives = ranked.slice(1)
      .filter(function (r) { return r.score >= Math.max(1, top.score * 0.45); })
      .slice(0, 3)
      .map(function (r) { return r.id; });

    return {
      lang: top.id,
      name: nameOf("programming", top.id),
      confidence: confidence,
      alternatives: alternatives,
      signals: (why[top.id] || []).slice(0, 4),
      mode: "programming"
    };
  }

  function detectNatural(text) {
    const raw = String(text || "").trim();
    if (!raw || !ready()) return unknown("natural");
    const sample = raw.length > 8192 ? raw.slice(0, 8192) : raw;

    for (let i = 0; i < SCRIPTS.length; i++) {
      const s = SCRIPTS[i];
      if (!s.rx.test(sample)) continue;
      if (s.ambiguous) {
        // Han characters alone cannot separate Chinese from Japanese. Common
        // simplified forms are a strong Chinese signal, so use them when
        // present and stay honestly ambiguous otherwise.
        if (s.zhRx && s.zhRx.test(sample)) {
          return {
            lang: "zh", name: nameOf("natural", "zh"), confidence: 0.82,
            alternatives: ["ja"], signals: [s.label, "simplified forms"],
            mode: "natural"
          };
        }
        return {
          lang: null, name: null, confidence: s.confidence,
          alternatives: s.alternatives || [], ambiguous: s.alternatives || [],
          signals: [s.label], mode: "natural"
        };
      }
      return {
        lang: s.lang, name: nameOf("natural", s.lang), confidence: s.confidence,
        alternatives: s.alternatives || [], signals: [s.label], mode: "natural"
      };
    }

    const words = fold(sample).match(/[a-z\u00c0-\u024f]+/g) || [];
    if (!words.length) return unknown("natural");
    if (words.length < 2) return unknown("natural");

    const scores = Object.create(null);
    const matched = Object.create(null);
    NAT.forEach(function (p) {
      let hits = 0;
      const hitWords = [];
      words.forEach(function (w) {
        if (p.stop.has(w)) {
          hits++;
          if (hitWords.length < 4 && hitWords.indexOf(w) < 0) hitWords.push(w);
        }
      });
      if (hits > 0 && p.marksRx && p.marksRx.test(sample)) hits += 1;
      if (hits) {
        scores[p.id] = hits;
        matched[p.id] = hitWords;
      }
    });

    const ranked = Object.keys(scores)
      .map(function (id) { return { id: id, score: scores[id] }; })
      .sort(function (a, b) { return b.score - a.score || (a.id < b.id ? -1 : 1); });
    if (!ranked.length) return unknown("natural");

    const top = ranked[0];
    const second = ranked[1] || null;
    const density = Math.min(1, top.score / Math.max(2, words.length * 0.3));
    const share = top.score / (top.score + (second ? second.score : 0));
    let confidence = 0.30 + 0.45 * density + 0.10 * share
      + 0.10 * Math.min(1, words.length / 4);
    if (words.length < 3) confidence = Math.min(confidence, 0.55);
    confidence = Math.min(0.97, round(confidence));

    const alternatives = ranked.slice(1)
      .filter(function (r) { return r.score >= Math.max(1, top.score * 0.5); })
      .slice(0, 3)
      .map(function (r) { return r.id; });

    return {
      lang: top.id,
      name: nameOf("natural", top.id),
      confidence: confidence,
      alternatives: alternatives,
      signals: (matched[top.id] || []).slice(0, 4),
      mode: "natural"
    };
  }

  function detect(text) {
    return { programming: detectProgramming(text), natural: detectNatural(text) };
  }

  function normalize(text) {
    const raw = String(text || "");
    const cleaned = clean(raw);
    const folded = fold(cleaned);
    for (let i = 0; i < PHRASES.length; i++) {
      const p = PHRASES[i];
      const m = p.rx.exec(folded) || p.rx.exec(cleaned);
      if (!m) continue;
      const to = String(p.to).replace(/\{(\d+)\}/g, function (_, n) {
        return m[Number(n)] == null ? "" : m[Number(n)];
      });
      return {
        text: to.replace(/\s+/g, " ").trim(),
        lang: p.lang,
        interpreted: true,
        changed: to !== raw,
        original: raw
      };
    }
    return { text: raw, lang: null, interpreted: false, changed: false, original: raw };
  }

  root.toolrxLang = {
    configure: configure,
    ready: ready,
    nameOf: nameOf,
    detect: detect,
    detectProgramming: detectProgramming,
    detectNatural: detectNatural,
    normalize: normalize
  };
})(typeof self !== "undefined" ? self : this);

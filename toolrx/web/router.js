/* toolrx client-side router.
 *
 * A line-for-line port of toolrx/tokhash.py + toolrx/router.py, so the
 * deterministic router can run in a browser tab with the same model file the
 * Python server uses. No transformer, no API key, no network.
 *
 * Exposes: self.toolrxRouter = { load, features, embed, route }
 */
(function (root) {
  "use strict";

  const DEFAULT_DIM = 4096;
  const WORD_RE = /[a-z0-9]+/gi;
  const WORDISH_RE = /[A-Za-z0-9./_\-~]+/g;
  const NUM_WORDS = {
    zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7,
    eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12, thirteen: 13,
    fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18,
    nineteen: 19, twenty: 20,
  };

  /* blake2b(key, digest_size=8) % dim, exactly like _ngrams()+features(). */
  function hashIndex(key, dim) {
    const hex = root.blake2bHex(key, null, 8);
    return Number(BigInt("0x" + hex) % BigInt(dim));
  }

  function features(text, dim) {
    text = (text || "").toLowerCase();
    const counts = Object.create(null);
    const add = function (key) {
      const i = hashIndex(key, dim);
      counts[i] = (counts[i] || 0) + 1;
    };
    const words = text.match(WORD_RE);
    if (words) for (let i = 0; i < words.length; i++) add(words[i]);
    for (let n = 3; n <= 4; n++) {
      for (let i = 0; i + n <= text.length; i++) add(text.slice(i, i + n));
    }
    return counts;
  }

  function l2(vec) {
    let sum = 0;
    for (const k in vec) sum += vec[k] * vec[k];
    const norm = Math.sqrt(sum) || 1;
    for (const k in vec) vec[k] /= norm;
    return vec;
  }

  function embed(text, dim, idf) {
    const vec = features(text, dim);
    if (idf) {
      for (const k in vec) {
        const w = idf[k];
        if (w !== undefined) vec[k] *= w;
      }
    }
    return l2(vec);
  }

  function dot(a, b) {
    let small = a, big = b, n = 0;
    for (const k in a) n++;
    let m = 0;
    for (const k in b) m++;
    if (m < n) { small = b; big = a; }
    let sum = 0;
    for (const k in small) {
      const v = big[k];
      if (v !== undefined) sum += small[k] * v;
    }
    return sum;
  }

  function load(raw) {
    const dim = raw.dim || DEFAULT_DIM;
    const idf = Object.create(null);
    for (const k in raw.idf) idf[k] = +raw.idf[k];
    const centroids = Object.create(null);
    for (const name in raw.centroids) {
      const c = Object.create(null);
      for (const k in raw.centroids[name]) c[k] = +raw.centroids[name][k];
      centroids[name] = c;
    }
    const byName = Object.create(null);
    for (const t of raw.tools || []) byName[t.name] = t;
    return { dim: dim, idf: idf, centroids: centroids, tools: raw.tools || [], byName: byName };
  }

  /* ---- argument extraction (mirrors router.extract_args) ---- */

  function intsIn(query) {
    const out = [];
    const re = /-?\d+/g;
    let m;
    while ((m = re.exec(query)) !== null) out.push(parseInt(m[0], 10));
    const words = query.toLowerCase().match(WORDISH_RE) || [];
    for (const tok of words) {
      if (tok in NUM_WORDS) out.push(NUM_WORDS[tok]);
    }
    return out;
  }

  function pathCandidates(query) {
    return (query.match(WORDISH_RE) || []).filter(function (m) {
      return m.indexOf("/") !== -1 || m.indexOf(".") !== -1 || m === "." || m === "..";
    });
  }

  function extractInterval(query) {
    let m = query.match(/(?:every|each|per)\s+(\d+)/i);
    if (!m) m = query.match(/(\d+)\s*(?:seconds?|secs?|\bs\b)/i);
    return m ? parseInt(m[1], 10) : null;
  }

  function extractDuration(query) {
    let m = query.match(/(?:for|during|over)\s+(\d+)\s*(minutes?|mins?|seconds?|secs?)/i);
    if (!m) m = query.match(/(\d+)\s*(minutes?|mins?)/i);
    if (!m) return null;
    const n = parseInt(m[1], 10);
    return /^min/i.test(m[2]) ? n * 60 : n;
  }

  function extractModuleName(query) {
    const low = query.toLowerCase();
    for (const name of ["memory", "disk", "uptime"]) {
      if (low.indexOf(name) !== -1) return name;
    }
    return null;
  }

  function extractModuleTool(query) {
    const low = query.toLowerCase();
    if (low.indexOf("ping") !== -1) return "net.ping";
    if (low.indexOf("disk") !== -1) return "sys.disk";
    if (low.indexOf("memory") !== -1 || low.indexOf("ram") !== -1) return "sys.mem_status";
    if (low.indexOf("process") !== -1) return "sys.processes";
    if (low.indexOf("uptime") !== -1 || low.indexOf("up time") !== -1) return "sys.uptime";
    if (low.indexOf("interface") !== -1 || low.indexOf("netw") !== -1) return "sys.ifconfig";
    if (low.indexOf("port") !== -1 || low.indexOf("listen") !== -1) return "sys.netstat";
    return null;
  }

  function extractHost(query, allowlist) {
    allowlist = allowlist || [];
    const toks = (query.match(WORDISH_RE) || []).filter(function (t) {
      return t.indexOf(".") !== -1 || /^[A-Za-z]+$/.test(t);
    });
    for (const t of toks) if (allowlist.indexOf(t) !== -1) return t;
    if ((toks.indexOf("local") !== -1 || toks.indexOf("localhost") !== -1)
        && allowlist.indexOf("localhost") !== -1) return "localhost";
    return toks.length ? toks[toks.length - 1] : null;
  }

  function extractContent(query, specs, args) {
    if (!specs.some(function (p) { return p.name === "content"; })) return;
    if (args.content) return;
    if (query.indexOf(":") !== -1) {
      args.content = query.split(":").slice(1).join(":").trim();
      return;
    }
    let q = query;
    if (args.path) q = q.replace(args.path, "");
    q = q.replace(/^(write|create|edit|save|append|update|set|make|add|change|put|insert|with|to|in|the|a|an|for|contents?|as)\b\s*/gi, "");
    args.content = q.replace(/^[ :]+|[ :]+$/g, "");
  }

  function extractArgs(query, specs, hostAllowlist) {
    specs = specs || [];
    const args = {};
    const hasHost = specs.some(function (p) { return p.type === "string" && p.name === "host"; });
    if (hasHost) {
      const cand = extractHost(query, hostAllowlist);
      if (cand) args.host = cand;
    }
    const pathNames = ["path", "path_a", "path_b", "file", "dir", "target"];
    const stringParams = specs.filter(function (p) {
      return p.type === "string" && p.name !== "host" && pathNames.indexOf(p.name) !== -1;
    });
    for (const p of specs) {
      if (p.name === "name" && p.type === "string") {
        const v = extractModuleName(query);
        if (v !== null) args.name = v;
      }
      if (p.name === "tool" && p.type === "string") {
        const v = extractModuleTool(query);
        if (v !== null) args.tool = v;
      }
    }
    const cands = pathCandidates(query).reverse();
    for (let i = stringParams.length - 1; i >= 0; i--) {
      const name = stringParams[i].name;
      if (name in args) continue;
      if (cands.length) args[name] = cands.pop();
      else if ("default" in stringParams[i]) args[name] = stringParams[i].default;
    }
    for (const p of specs) {
      if (p.type === "string" && !(p.name in args) && p.name !== "host" && "default" in p) {
        if (!(p.name in args)) args[p.name] = p.default;
      }
    }
    for (const p of specs) {
      const name = p.name;
      if (name === "interval" && p.type === "int") {
        const iv = extractInterval(query);
        if (iv !== null) args[name] = iv;
        else if (!(name in args) && "default" in p) args[name] = p.default;
      } else if (name === "duration" && p.type === "int") {
        const du = extractDuration(query);
        if (du !== null) args[name] = du;
      } else if (p.type === "int_list") {
        const nums = intsIn(query);
        if (nums.length) args[name] = nums;
      }
      if (!(name in args) && "default" in p) args[name] = p.default;
    }
    extractContent(query, specs, args);
    return args;
  }

  function route(query, model, hostAllowlist) {
    const t0 = (root.performance && performance.now) ? performance.now() : Date.now();
    const qv = embed(query, model.dim, model.idf);
    const ranked = [];
    for (const name in model.centroids) {
      ranked.push([name, dot(qv, model.centroids[name])]);
    }
    ranked.sort(function (a, b) { return b[1] - a[1]; });
    const round = function (x) { return Math.round(x * 10000) / 10000; };
    const best = ranked[0] || ["", 0];
    const runner = ranked.length > 1 ? ranked[1][1] : 0;
    const tool = model.byName[best[0]] || null;
    const scores = {};
    ranked.forEach(function (kv) { scores[kv[0]] = round(kv[1]); });
    return {
      query: query,
      tool: best[0],
      confidence: round(best[1]),
      margin: round(best[1] - runner),
      scores: scores,
      ranked: ranked.map(function (kv) { return [kv[0], round(kv[1])]; }),
      args: extractArgs(query, tool ? tool.params : [], hostAllowlist),
      ms: ((root.performance && performance.now) ? performance.now() : Date.now()) - t0,
    };
  }

  root.toolrxRouter = {
    load: load,
    features: features,
    embed: embed,
    route: route,
    extractArgs: extractArgs,
  };
})(typeof self !== "undefined" ? self : this);

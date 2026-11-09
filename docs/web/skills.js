/* toolrx deterministic skills.
 *
 * A data-driven command library (toolrx/web/commands.json) plus a planner that
 * runs several steps in order. Everything here is pattern matching + explicit
 * handlers: no model decides arguments, so the same prompt always produces the
 * same plan and the same output.
 *
 * Exposes: self.toolrxSkills = { init, count, categories, match, splitPrompt,
 *                               exec, runPrompt, search }
 */
(function (root) {
  "use strict";

  const MAX_OUT = 12000;
  const PRONOUN = /^(?:it|that|this|the text|the result|the output|previous|above|same)$/i;

  let COMMANDS = [];
  let BY_OP = Object.create(null);
  let meta = { count: 0, categories: {} };

  /* ---------------------------------------------------------- numbers --- */
  const WORDS = {
    zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7,
    eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12, thirteen: 13,
    fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18,
    nineteen: 19, twenty: 20,
  };

  function num(v) {
    if (typeof v === "number") return v;
    if (v === null || v === undefined) return NaN;
    let s = String(v).trim().toLowerCase().replace(/,/g, "");
    if (s in WORDS) return WORDS[s];
    if (/^-?\d*\.?\d+$/.test(s)) return parseFloat(s);
    return NaN;
  }

  function numOrThrow(v) {
    const n = num(v);
    if (!isFinite(n)) throw new Error(`not a number: ${v}`);
    return n;
  }

  /* The last number in a previous step's output, so "square the result" works
   * even when the previous line was "5 km = 3.106856 mi". */
  function prevNumber(text) {
    const found = String(text === undefined || text === null ? "" : text)
      .match(/-?\d[\d,]*(?:\.\d+)?/g);
    if (!found || !found.length) return NaN;
    return num(found[found.length - 1]);
  }

  function fmt(n) {
    if (typeof n !== "number" || !isFinite(n)) return String(n);
    if (Number.isInteger(n) && Math.abs(n) < 1e21) return String(n);
    const r = Math.round(n * 1e10) / 1e10;
    return String(r);
  }

  function int(n) {
    return Math.trunc(n);
  }

  /* ------------------------------------------------------- expressions --- */
  function evalExpr(src) {
    const tokens = String(src).replace(/\s+/g, "").toLowerCase();
    let i = 0;

    function peek() { return tokens[i]; }
    function eat(c) { if (tokens[i] === c) { i++; return true; } return false; }

    function primary() {
      if (eat("(")) { const v = expr(); eat(")"); return v; }
      if (eat("-")) return -primary();
      if (eat("+")) return primary();
      if (tokens.startsWith("pi", i)) { i += 2; return Math.PI; }
      if (tokens.startsWith("e", i) && !/[a-z]/.test(tokens[i + 1] || "")) { i += 1; return Math.E; }
      const m = /^\d*\.?\d+/.exec(tokens.slice(i));
      if (m) { i += m[0].length; return parseFloat(m[0]); }
      const fn = /^[a-z]+/.exec(tokens.slice(i));
      if (fn) {
        const name = fn[0];
        if (name === "sqrt" || name === "cbrt" || name === "abs" || name === "round" ||
            name === "floor" || name === "ceil" || name === "sin" || name === "cos" ||
            name === "tan" || name === "log" || name === "ln" || name === "exp") {
          i += name.length;
          eat("(");
          const v = expr();
          eat(")");
          switch (name) {
            case "sqrt": return Math.sqrt(v);
            case "cbrt": return Math.cbrt(v);
            case "abs": return Math.abs(v);
            case "round": return Math.round(v);
            case "floor": return Math.floor(v);
            case "ceil": return Math.ceil(v);
            case "sin": return Math.sin(v);
            case "cos": return Math.cos(v);
            case "tan": return Math.tan(v);
            case "log": return Math.log10(v);
            case "ln": return Math.log(v);
            case "exp": return Math.exp(v);
          }
        }
      }
      throw new Error(`cannot parse expression near "${tokens.slice(i) || "end"}"`);
    }

    function power() {
      let base = primary();
      if (eat("^")) base = Math.pow(base, power());
      return base;
    }

    function unary() {
      if (eat("-")) return -unary();
      if (eat("+")) return +unary();
      return power();
    }

    function term() {
      let v = unary();
      while (i < tokens.length) {
        if (eat("*")) v *= unary();
        else if (eat("/")) v /= unary();
        else if (eat("%")) v %= unary();
        else break;
      }
      return v;
    }

    function expr() {
      let v = term();
      while (i < tokens.length) {
        if (eat("+")) v += term();
        else if (eat("-")) v -= term();
        else break;
      }
      return v;
    }

    const out = expr();
    if (i !== tokens.length) throw new Error(`unexpected "${tokens.slice(i)}"`);
    return out;
  }

  /* ------------------------------------------------------------ utils --- */
  function decodeEntities(s) {
    return String(s).replace(/&amp;/g, "&").replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'");
  }

  function resolveText(v, ctx) {
    if (v === undefined || v === null) return ctx.prev || "";
    let s = String(v).trim().replace(/^["']|["']$/g, "");
    if (!s || PRONOUN.test(s)) return ctx.prev || "";
    if (ctx.fs && /^[\w./-]+$/.test(s) && ctx.fs.exists(s)) return ctx.fs.read(s);
    return decodeEntities(s);
  }

  function cap(s) {
    s = String(s);
    return s.length > MAX_OUT ? s.slice(0, MAX_OUT) + "\n...[truncated]" : s;
  }

  function words(s) {
    return String(s).match(/[A-Za-z0-9']+/g) || [];
  }

  function b64encode(s) {
    const bytes = new TextEncoder().encode(s);
    let bin = "";
    for (const b of bytes) bin += String.fromCharCode(b);
    return btoa(bin);
  }

  function b64decode(s) {
    const bin = atob(String(s).replace(/\s+/g, ""));
    const bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  }

  function hexEncode(s) {
    return Array.from(new TextEncoder().encode(s))
      .map(b => b.toString(16).padStart(2, "0")).join("");
  }

  function hexDecode(s) {
    const h = String(s).replace(/[^0-9a-f]/gi, "");
    const bytes = new Uint8Array(h.length / 2);
    for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(h.substr(i * 2, 2), 16);
    return new TextDecoder().decode(bytes);
  }

  const MORSE = {
    a: ".-", b: "-...", c: "-.-.", d: "-..", e: ".", f: "..-.", g: "--.", h: "....",
    i: "..", j: ".---", k: "-.-", l: ".-..", m: "--", n: "-.", o: "---", p: ".--.",
    q: "--.-", r: ".-.", s: "...", t: "-", u: "..-", v: "...-", w: ".--", x: "-..-",
    y: "-.--", z: "--..", 0: "-----", 1: ".----", 2: "..---", 3: "...--", 4: "....-",
    5: ".....", 6: "-....", 7: "--...", 8: "---..", 9: "----.",
  };
  const UNMORSE = Object.fromEntries(Object.entries(MORSE).map(([k, v]) => [v, k]));

  function fromRoman(s) {
    const vals = { i: 1, v: 5, x: 10, l: 50, c: 100, d: 500, m: 1000 };
    let total = 0;
    const t = String(s).toLowerCase();
    for (let i = 0; i < t.length; i++) {
      const v = vals[t[i]], next = vals[t[i + 1]] || 0;
      total += v < next ? -v : v;
    }
    return total;
  }

  function toRoman(n) {
    n = Math.trunc(n);
    if (n < 1 || n > 3999) throw new Error("roman numerals cover 1..3999");
    const map = [[1000, "M"], [900, "CM"], [500, "D"], [400, "CD"], [100, "C"],
      [90, "XC"], [50, "L"], [40, "XL"], [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]];
    let out = "";
    for (const [v, s] of map) while (n >= v) { out += s; n -= v; }
    return out;
  }

  const ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen"];
  const TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];

  function numberToWords(n) {
    n = Math.trunc(n);
    if (n < 0) return "minus " + numberToWords(-n);
    if (n < 20) return ONES[n];
    if (n < 100) return TENS[Math.floor(n / 10)] + (n % 10 ? "-" + ONES[n % 10] : "");
    if (n < 1000) return ONES[Math.floor(n / 100)] + " hundred" + (n % 100 ? " " + numberToWords(n % 100) : "");
    const scales = [[1e12, "trillion"], [1e9, "billion"], [1e6, "million"], [1e3, "thousand"]];
    for (const [v, name] of scales) {
      if (n >= v) {
        return numberToWords(Math.floor(n / v)) + " " + name +
          (n % v ? " " + numberToWords(n % v) : "");
      }
    }
    return String(n);
  }

  function ordinal(n) {
    n = Math.trunc(n);
    const s = ["th", "st", "nd", "rd"], v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
  }

  function hashText(algo, text) {
    const name = String(algo).toLowerCase();
    if (name === "blake2b" || name === "blake2b-256") return root.blake2bHex(text, null, 32);
    if (name === "blake2b-512") return root.blake2bHex(text, null, 64);
    if (name === "sha256" && root.crypto && crypto.subtle) {
      return crypto.subtle.digest("SHA-256", new TextEncoder().encode(text))
        .then(buf => Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join(""));
    }
    throw new Error(`unsupported hash: ${algo}`);
  }

  function parseFlags(p) {
    const m = /^\/(.*)\/([a-z]*)$/.exec(String(p).trim());
    if (m) return { re: new RegExp(m[1], m[2]), src: m[1] };
    return { re: new RegExp(String(p)), src: String(p) };
  }

  /* --------------------------------------------------------- unit math --- */
  const FACTORS = {
    length: { mm: .001, cm: .01, m: 1, km: 1000, in: .0254, ft: .3048, yd: .9144, mi: 1609.344, nmi: 1852 },
    mass: { mg: .001, g: 1, kg: 1000, t: 1e6, oz: 28.349523125, lb: 453.59237, st: 6350.29318 },
    volume: { ml: .001, l: 1, tsp: .00492892159375, tbsp: .01478676478125, floz: .0295735295625,
      cup: .2365882365, pt: .473176473, qt: .946352946, gal: 3.785411784 },
    data: { kb: 1e3, mb: 1e6, gb: 1e9, tb: 1e12, kib: 1024, mib: 1048576, gib: 1073741824 },
    time: { ms: .001, s: 1, min: 60, h: 3600, day: 86400, week: 604800 },
    speed: { mps: 1, kph: 1 / 3.6, mph: 0.44704, knot: 1852 / 3600 },
    area: { mm2: 1e-6, cm2: 1e-4, m2: 1, km2: 1e6, ha: 1e4, acre: 4046.8564224,
      ft2: .09290304, in2: .00064516 },
    energy: { j: 1, kj: 1000, cal: 4.184, kcal: 4184, wh: 3600, kwh: 3.6e6 },
    pressure: { pa: 1, kpa: 1000, bar: 1e5, atm: 101325, psi: 6894.757293, mmhg: 133.322387 },
    angle: { deg: 1, rad: 57.29577951308232, grad: .9 },
  };

  const UNIT_LABEL = {
    mm: "mm", cm: "cm", m: "m", km: "km", in: "in", ft: "ft", yd: "yd", mi: "mi",
    nmi: "nmi", mg: "mg", g: "g", kg: "kg", t: "t", oz: "oz", lb: "lb", st: "st",
    ml: "mL", l: "L", tsp: "tsp", tbsp: "tbsp", floz: "fl oz", cup: "cups", pt: "pt",
    qt: "qt", gal: "gal", kb: "KB", mb: "MB", gb: "GB", tb: "TB", kib: "KiB",
    mib: "MiB", gib: "GiB", ms: "ms", s: "s", min: "min", h: "h", day: "days",
    week: "weeks", mps: "m/s", kph: "km/h", mph: "mph", knot: "kn", mm2: "mm²",
    cm2: "cm²", m2: "m²", km2: "km²", ha: "ha", acre: "ac", ft2: "ft²", in2: "in²",
    j: "J", kj: "kJ", cal: "cal", kcal: "kcal", wh: "Wh", kwh: "kWh", pa: "Pa",
    kpa: "kPa", bar: "bar", atm: "atm", psi: "psi", mmhg: "mmHg", deg: "°", rad: "rad",
    grad: "grad", c: "°C", f: "°F", k: "K",
  };

  function convertUnit(n, from, to) {
    if (from === to) return n;
    const temp = { c: v => v, f: v => (v - 32) * 5 / 9, k: v => v - 273.15 };
    const untemp = { c: v => v, f: v => v * 9 / 5 + 32, k: v => v + 273.15 };
    if (from in temp && to in untemp) return untemp[to](temp[from](n));
    for (const cat in FACTORS) {
      const f = FACTORS[cat];
      if (from in f && to in f) return n * f[from] / f[to];
    }
    throw new Error(`no conversion from ${from} to ${to}`);
  }

  /* -------------------------------------------------------------- color --- */
  function parseColor(c) {
    const s = String(c).trim();
    let m = /^#?([0-9a-f]{3})$/i.exec(s);
    if (m) return [parseInt(m[1][0] + m[1][0], 16), parseInt(m[1][1] + m[1][1], 16), parseInt(m[1][2] + m[1][2], 16)];
    m = /^#?([0-9a-f]{6})$/i.exec(s);
    if (m) return [0, 2, 4].map(i => parseInt(m[1].substr(i, 2), 16));
    m = /^rgba?\(?\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/i.exec(s);
    if (m) return [m[1], m[2], m[3]].map(Number);
    throw new Error(`not a color: ${c}`);
  }

  function toHex(rgb) {
    return "#" + rgb.map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
  }

  function luminance(rgb) {
    const [r, g, b] = rgb.map(v => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  function contrast(a, b) {
    const la = luminance(parseColor(a)), lb = luminance(parseColor(b));
    const hi = Math.max(la, lb), lo = Math.min(la, lb);
    return (hi + 0.05) / (lo + 0.05);
  }

  /* --------------------------------------------------------------- CSV --- */
  function parseCSV(text) {
    const rows = [];
    let row = [], field = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
        else if (c === '"') quoted = false;
        else field += c;
      } else if (c === '"') quoted = true;
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
      else if (c !== "\r") field += c;
    }
    if (field || row.length) { row.push(field); rows.push(row); }
    return rows.filter(r => r.some(x => x.trim() !== ""));
  }

  function csvToJson(text) {
    const rows = parseCSV(String(text).trim());
    if (!rows.length) return "[]";
    const head = rows[0];
    const objects = rows.slice(1).map(r => {
      const o = {};
      head.forEach((h, i) => { o[h.trim()] = r[i] === undefined ? "" : r[i]; });
      return o;
    });
    return JSON.stringify(objects, null, 2);
  }

  function jsonToCsv(value) {
    const list = Array.isArray(value) ? value : [value];
    const keys = Array.from(new Set(list.flatMap(o => Object.keys(o))));
    const esc = v => {
      const s = v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v);
      return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    return [keys.join(",")].concat(list.map(o => keys.map(k => esc(o[k])).join(","))).join("\n");
  }

  function getPath(obj, path) {
    return String(path).split(".").reduce((o, k) => {
      if (o === null || o === undefined) return undefined;
      return o[k.replace(/^\[(\d+)\]$/, "$1")];
    }, obj);
  }

  /* ------------------------------------------------------------ seeding --- */
  function seeded(seed) {
    let h = 2166136261;
    for (const ch of String(seed)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); }
    return function () {
      h += 0x6D2B79F5;
      let t = h;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* ------------------------------------------------------------ facts ----- */
  const CAPITALS = {
    afghanistan: "Kabul", albania: "Tirana", algeria: "Algiers", argentina: "Buenos Aires",
    armenia: "Yerevan", australia: "Canberra", austria: "Vienna", bangladesh: "Dhaka",
    belgium: "Brussels", bolivia: "Sucre (seat of government: La Paz)", brazil: "Brasília",
    bulgaria: "Sofia", cambodia: "Phnom Penh", cameroon: "Yaoundé", canada: "Ottawa",
    chile: "Santiago", china: "Beijing", colombia: "Bogotá", croatia: "Zagreb",
    cuba: "Havana", cyprus: "Nicosia", czechia: "Prague", "czech republic": "Prague",
    denmark: "Copenhagen", ecuador: "Quito", egypt: "Cairo", estonia: "Tallinn",
    ethiopia: "Addis Ababa", finland: "Helsinki", france: "Paris", georgia: "Tbilisi",
    germany: "Berlin", ghana: "Accra", greece: "Athens", hungary: "Budapest",
    iceland: "Reykjavík", india: "New Delhi", indonesia: "Jakarta", iran: "Tehran",
    iraq: "Baghdad", ireland: "Dublin", israel: "Jerusalem", italy: "Rome",
    jamaica: "Kingston", japan: "Tokyo", jordan: "Amman", kazakhstan: "Astana",
    kenya: "Nairobi", "south korea": "Seoul", "north korea": "Pyongyang",
    latvia: "Riga", lebanon: "Beirut", lithuania: "Vilnius", luxembourg: "Luxembourg",
    madagascar: "Antananarivo", malaysia: "Kuala Lumpur", mexico: "Mexico City",
    mongolia: "Ulaanbaatar", morocco: "Rabat", nepal: "Kathmandu", netherlands: "Amsterdam",
    "new zealand": "Wellington", nigeria: "Abuja", norway: "Oslo", pakistan: "Islamabad",
    panama: "Panama City", paraguay: "Asunción", peru: "Lima", philippines: "Manila",
    poland: "Warsaw", portugal: "Lisbon", qatar: "Doha", romania: "Bucharest",
    russia: "Moscow", "saudi arabia": "Riyadh", senegal: "Dakar", serbia: "Belgrade",
    singapore: "Singapore", slovakia: "Bratislava", slovenia: "Ljubljana",
    "south africa": "Pretoria (executive), Cape Town (legislative), Bloemfontein (judicial)",
    spain: "Madrid", "sri lanka": "Sri Jayawardenepura Kotte", sweden: "Stockholm",
    switzerland: "Bern", syria: "Damascus", taiwan: "Taipei", tanzania: "Dodoma",
    thailand: "Bangkok", tunisia: "Tunis", turkey: "Ankara", uganda: "Kampala",
    ukraine: "Kyiv", "united arab emirates": "Abu Dhabi", uae: "Abu Dhabi",
    "united kingdom": "London", uk: "London", england: "London",
    "united states": "Washington, D.C.", usa: "Washington, D.C.",
    "united states of america": "Washington, D.C.", uruguay: "Montevideo",
    uzbekistan: "Tashkent", venezuela: "Caracas", vietnam: "Hanoi", yemen: "Sanaa",
    zambia: "Lusaka", zimbabwe: "Harare",
  };

  const SYMBOLS = {
    hydrogen: "H", helium: "He", lithium: "Li", beryllium: "Be", boron: "B",
    carbon: "C", nitrogen: "N", oxygen: "O", fluorine: "F", neon: "Ne",
    sodium: "Na", magnesium: "Mg", aluminium: "Al", aluminum: "Al", silicon: "Si",
    phosphorus: "P", sulfur: "S", sulphur: "S", chlorine: "Cl", argon: "Ar",
    potassium: "K", calcium: "Ca", scandium: "Sc", titanium: "Ti", vanadium: "V",
    chromium: "Cr", manganese: "Mn", iron: "Fe", cobalt: "Co", nickel: "Ni",
    copper: "Cu", zinc: "Zn", silver: "Ag", tin: "Sn", gold: "Au", mercury: "Hg",
    lead: "Pb", uranium: "U",
  };

  function factKey(s) {
    return String(s).toLowerCase().replace(/[?.!,]/g, "").replace(/^the\s+/, "").trim();
  }

  /* ------------------------------------------------------------- chat ----- */
  /* Deterministic conversation. No model: a small set of intents, a stable
   * hash to choose among hand-written responses, and a reflection pattern
   * inspired by the voidscream therapist. It listens, names the feeling, and
   * asks one gentle question. It never claims to be a clinician. */
  function seedOf(s) {
    let h = 2166136261;
    const t = String(s || "");
    for (let i = 0; i < t.length; i++) { h ^= t.charCodeAt(i); h = Math.imul(h, 16777619); }
    return (h >>> 0);
  }

  function pick(list, seed) {
    return list[seed % list.length];
  }

  const FEELINGS = [
    [/\b(anxious|anxiety|panic|nervous|worried|worry)\b/i, "anxious", "the worry is loud right now"],
    [/\b(sad|down|depressed|low|blue|empty)\b/i, "sad", "something feels heavy"],
    [/\b(angry|mad|furious|irritated|annoyed)\b/i, "angry", "something crossed a line"],
    [/\b(stressed|overwhelmed|overloaded|buried|swamped)\b/i, "overwhelmed", "there is more than fits"],
    [/\b(tired|exhausted|drained|burnt out|burned out)\b/i, "tired", "the tank is low"],
    [/\b(lonely|alone|isolated)\b/i, "lonely", "the quiet is doing the talking"],
    [/\b(scared|afraid|fear)\b/i, "afraid", "the future is showing its teeth"],
    [/\b(confused|lost|stuck|uncertain)\b/i, "stuck", "the next step is not visible"],
  ];

  function chatReply(step, ctx) {
    const raw = String(step || "").trim();
    const q = raw.toLowerCase().replace(/\s+/g, " ");
    if (!q) return "";
    // Command-shaped text should fail as a command, not get a reflection.
    if (/^(?:read|list|write|delete|remove|open|show|run|convert|calculate|calc|count|find|search|define|summarize|build|make|create|plan|blueprint|new|rename|multiply|divide|add|subtract|square|uppercase|lowercase|reverse|hash|encode|decode)\b/.test(q)) {
      return "";
    }
    const seed = seedOf(q);
    const mem = (ctx && ctx.memory) || { get: function () {}, set: function () {} };
    const name = mem.get("name");

    let m = /(?:my name is|call me|remember my name is)\s+([a-z][a-z'\-]{1,24})/i.exec(raw);
    if (m) {
      const who = m[1].replace(/^./, function (c) { return c.toUpperCase(); });
      mem.set("name", who);
      return "Noted — " + who + ". I'll use that.\n\nWhat are you working on today?";
    }
    if (/^(?:what(?:'s| is) my name|who am i|do you remember my name)\??$/i.test(q)) {
      return name ? "You told me your name is " + name + "." : "You haven't told me a name yet. Say: remember my name is …";
    }

    if (/^(?:hi|hello|hey|yo|hiya|good (?:morning|afternoon|evening))\b/.test(q)) {
      return pick([
        "Hey" + (name ? ", " + name : "") + ". What are we making?",
        "Hi. I'm here — deterministic, but listening. What's on your mind?",
        "Hello. We can build something, look something up, or just talk. Which?",
      ], seed);
    }
    if (/\b(thanks|thank you|thx|appreciate it)\b/.test(q)) {
      return pick(["You're welcome. Want to keep going?", "Any time. What's next?", "Glad it helped."], seed);
    }
    if (/^(?:bye|goodbye|see you|later|good night)\b/.test(q)) {
      return pick(["See you. Your workspace stays here.", "Later. The project is saved in this browser.", "Good night. Pick it up whenever."], seed);
    }
    if (/\bhow are you\b/.test(q)) {
      return "I don't have moods, but I do have state — and right now it's steady. How are you, honestly?";
    }
    if (/\b(tell me a joke|make me laugh|something funny)\b/.test(q)) {
      return pick([
        "A router walks into a bar. The bartender asks what it wants. It says: \"I already knew.\"",
        "Why did the function stop calling? It lost its reference.",
        "There are two hard things in computing: naming things, cache invalidation, and off-by-one errors.",
        "I tried to write a joke about recursion. I'll tell you the rest when I get there.",
      ], seed);
    }
    if (/\b(motivate me|i need motivation|encourage me|pep talk)\b/.test(q)) {
      return pick([
        "You don't need a whole plan. You need the next small true step. Pick one and do it badly on purpose.",
        "Start with something you can finish in ten minutes. Momentum is a real technology.",
        "The work is allowed to be small. Small things, repeated, become the thing.",
      ], seed) + "\n\nWhat's the smallest version of what you're avoiding?";
    }
    if (/\b(who are you|what are you|tell me about yourself)\b/.test(q)) {
      return "I'm toolrx — a deterministic router and a small builder. I match patterns, run real tools, write project files, and I can look things up on the web.\n\nI'm not an LLM. That means I won't invent an answer: if I don't know, I'll say so.";
    }
    if (/\b(what should i (?:build|make)|give me an idea|project idea)\b/.test(q)) {
      return pick([
        "Build a tiny tool you would actually use twice: a unit converter, a shift timer, a packing list.",
        "Build the smallest game you can lose: snake, pong, or a one-screen maze.",
        "Build a page that explains one idea well. Architecture first, decoration second.",
      ], seed) + "\n\nSay \"plan it\" and I'll lay out the files, state, modules, and build order.";
    }
    if (/\b(are you (?:real|alive|sentient|conscious)|do you have feelings)\b/.test(q)) {
      return "No. I'm a pattern matcher with a workspace. The care in the words is real in the sense that it's written carefully — but there's nobody home behind them.";
    }
    if (/\b(suicide|kill myself|self[- ]harm|hurt myself|end my life|want to die)\b/i.test(q)) {
      return "I'm really sorry you're carrying that. I'm not a crisis service and I can't keep you safe from here.\n\nPlease reach out to a local emergency number or a crisis line right now, and if you can, tell one person nearby that you're not okay. If you're in the US, call or text 988. In the UK, 116 123. Elsewhere: findahelpline.com.\n\nI'm still here if you want to keep talking, but please put a human in the loop first.";
    }

    for (let i = 0; i < FEELINGS.length; i++) {
      if (FEELINGS[i][0].test(q)) {
        const label = FEELINGS[i][1];
        const image = FEELINGS[i][2];
        const openers = [
          "That sounds " + label + " — " + image + ".",
          "I hear " + label + ". " + image.charAt(0).toUpperCase() + image.slice(1) + ".",
          "So there's " + label + " in the room. " + image.charAt(0).toUpperCase() + image.slice(1) + ".",
        ];
        const follows = [
          "What part of it is loudest right now?",
          "If it had a shape, what would it look like?",
          "What would 'a little better' look like today — not fixed, just a little better?",
          "Is there one thing you can put down for an hour?",
        ];
        return pick(openers, seed) + "\n\n" + pick(follows, seed >> 3);
      }
    }

    m = /^(?:i (?:feel|am|'m)\s+)(.{2,80})$/i.exec(raw);
    if (m && !/^(?:going|trying|working|building|making|okay|ok|fine|good|great)\b/i.test(m[1])) {
      return "You said you feel " + m[1].replace(/[.!?]+$/, "") + ".\n\n"
        + pick(["Where do you notice it in your body?", "How long has it been there?", "What would you want someone to say right now?"], seed);
    }
    if (/\b(i (?:can'?t|cannot)|i'?m stuck|i don'?t know (?:what|how))\b/i.test(q)) {
      return "Stuck is information, not a verdict.\n\nName the smallest piece you *can* do — even if it's opening the file. We'll start there.";
    }
    if (/\b(i (?:want|need) to|i should|i have to)\b/i.test(q)) {
      return "There's a should in that sentence. Which part of it is yours, and which part is borrowed?\n\nIf you strip it to one action for today, what remains?";
    }
    if (/^(?:why|really|and|so)\??$/.test(q) && ctx && ctx.history) {
      const hist = ctx.history().filter(function (x) { return x.who === "toolrx"; });
      if (hist.length) return "Because that's what I have: the last thing you said, reflected back honestly. Tell me more and I'll stay with it.";
    }
    if (/\b(i'?m (?:okay|ok|fine|good|great|alright))\b/i.test(q)) {
      return "Good. And if 'fine' is doing a lot of work in that sentence, you can say that too.";
    }
    if (/\b(help|support|listen)\b/.test(q) && q.split(" ").length <= 4) {
      return "I can listen, or I can switch to building.\n\nTry: \"i feel overwhelmed\" · \"plan a todo app\" · \"wikipedia ursula k le guin\" · \"list projects\".";
    }

    // Deterministic reflection for anything else conversational.
    const reflect = raw.replace(/[.!?]+$/, "").replace(/^i\s+/i, "you ");
    return "I heard: \"" + raw.slice(0, 180) + "\".\n\n"
      + pick([
        "What's underneath that for you?",
        "Say more — what part matters most?",
        "If we changed one thing about it, what would you change first?",
      ], seed)
      + (reflect !== raw ? "\n\n(" + reflect.charAt(0).toUpperCase() + reflect.slice(1) + "…)" : "");
  }

  function summarizeText(text, n) {
    const src = String(text || "").replace(/\s+/g, " ").trim();
    if (!src) return "nothing to summarize";
    const parts = src.match(/[^.!?]+[.!?]+/g) || [src];
    const take = parts.slice(0, n || 3).join(" ").trim();
    const words = src.split(/\s+/).filter(Boolean).length;
    return take + "\n\n(" + words + " words, " + parts.length + " sentences)";
  }

  /* -------------------------------------------------------------- ops ---- */
  const OPS = {
    "math.binary": function (a) {
      const x = numOrThrow(a.a), y = numOrThrow(a.b);
      switch (a.op) {
        case "add": return fmt(x + y);
        case "sub": return fmt(x - y);
        case "mul": return fmt(x * y);
        case "div": if (y === 0) throw new Error("division by zero"); return fmt(x / y);
        case "mod": if (y === 0) throw new Error("division by zero"); return fmt(x % y);
        case "pow": return fmt(Math.pow(x, y));
        case "gcd": {
          let p = Math.abs(int(x)), q = Math.abs(int(y));
          while (q) { [p, q] = [q, p % q]; }
          return fmt(p);
        }
        case "lcm": {
          let p = Math.abs(int(x)), q = Math.abs(int(y)), g = p;
          while (q) { [g, q] = [q, g % q]; }
          return fmt(g ? p / g * Math.abs(int(y)) : 0);
        }
        case "min": return fmt(Math.min(x, y));
        case "max": return fmt(Math.max(x, y));
        case "pct_of": return fmt(x / 100 * y);
        case "pct_change": return fmt((y - x) / Math.abs(x) * 100) + "%";
        case "log": return fmt(Math.log(x) / Math.log(y));
        case "divisible": return y === 0 ? "no (division by zero)" : (x % y === 0 ? "yes" : "no");
        default: throw new Error("unknown binary op " + a.op);
      }
    },
    "math.unary": function (a, ctx) {
      const raw = a.a === undefined || a.a === null || a.a === "" || PRONOUN.test(String(a.a).trim())
        ? prevNumber(ctx && ctx.prev) : a.a;
      const x = numOrThrow(raw);
      switch (a.op) {
        case "square": return fmt(x * x);
        case "cube": return fmt(x * x * x);
        case "sqrt": if (x < 0) throw new Error("square root of a negative number"); return fmt(Math.sqrt(x));
        case "cbrt": return fmt(Math.cbrt(x));
        case "abs": return fmt(Math.abs(x));
        case "neg": return fmt(-x);
        case "round": return fmt(Math.round(x));
        case "floor": return fmt(Math.floor(x));
        case "ceil": return fmt(Math.ceil(x));
        case "fact": {
          const n = int(x);
          if (n < 0 || n > 170) throw new Error("factorial needs 0..170");
          let r = 1;
          for (let i = 2; i <= n; i++) r *= i;
          return fmt(r);
        }
        case "recip": if (x === 0) throw new Error("division by zero"); return fmt(1 / x);
        case "isprime": {
          const n = int(x);
          if (n < 2) return "no";
          for (let i = 2; i * i <= n; i++) if (n % i === 0) return "no";
          return "yes";
        }
        case "iseven": return int(x) % 2 === 0 ? "yes" : "no";
        case "isodd": return Math.abs(int(x) % 2) === 1 ? "yes" : "no";
        case "sign": return String(Math.sign(x));
        case "double": return fmt(x * 2);
        case "half": return fmt(x / 2);
        case "triple": return fmt(x * 3);
        case "factors": {
          const n = Math.abs(int(x));
          if (!n) return "0";
          const out = [];
          for (let i = 1; i * i <= n; i++) {
            if (n % i) continue;
            out.push(i);
            if (i !== n / i) out.push(n / i);
          }
          return out.sort((p, q) => p - q).join(", ");
        }
        case "primefactors": {
          let n = Math.abs(int(x));
          if (n < 2) return String(n);
          const out = [];
          for (let p = 2; p * p <= n; p++) {
            while (n % p === 0) { out.push(p); n /= p; }
          }
          if (n > 1) out.push(n);
          return out.join(" × ");
        }
        case "divcount": {
          const n = Math.abs(int(x));
          if (!n) return "0";
          let count = 0;
          for (let i = 1; i * i <= n; i++) {
            if (n % i) continue;
            count += i === n / i ? 1 : 2;
          }
          return fmt(count);
        }
        case "deg2rad": return fmt(x * Math.PI / 180);
        case "rad2deg": return fmt(x * 180 / Math.PI);
        default: throw new Error("unknown unary op " + a.op);
      }
    },
    "math.list": function (a) {
      const xs = String(a.list).split(/\s*(?:,|;|\band\b|\s)\s*/).map(num)
        .filter(v => isFinite(v));
      if (!xs.length) throw new Error("no numbers found");
      const sorted = xs.slice().sort((p, q) => p - q);
      const sum = xs.reduce((p, q) => p + q, 0);
      switch (a.op) {
        case "sum": return fmt(sum);
        case "mean": return fmt(sum / xs.length);
        case "median": {
          const mid = Math.floor(sorted.length / 2);
          return fmt(sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2);
        }
        case "mode": {
          const counts = {};
          xs.forEach(v => counts[v] = (counts[v] || 0) + 1);
          const best = Math.max(...Object.values(counts));
          return Object.keys(counts).filter(k => counts[k] === best).join(", ");
        }
        case "range": return fmt(sorted[sorted.length - 1] - sorted[0]);
        case "stdev": {
          const m = sum / xs.length;
          return fmt(Math.sqrt(xs.reduce((p, q) => p + (q - m) * (q - m), 0) / xs.length));
        }
        case "minlist": return fmt(sorted[0]);
        case "maxlist": return fmt(sorted[sorted.length - 1]);
        case "product": return fmt(xs.reduce((p, q) => p * q, 1));
        default: throw new Error("unknown list op " + a.op);
      }
    },
    "math.expr": function (a) {
      return fmt(evalExpr(a.expr));
    },
    "math.format": function (a) {
      const x = numOrThrow(a.a);
      switch (a.op) {
        case "words": return numberToWords(x);
        case "roman": return toRoman(x);
        case "ordinal": return ordinal(x);
        case "base2": return int(x).toString(2);
        case "base8": return int(x).toString(8);
        case "base16": return int(x).toString(16).toUpperCase();
        case "sci": return x.toExponential();
        default: throw new Error("unknown format " + a.op);
      }
    },
    "unit.convert": function (a) {
      const n = numOrThrow(a.n);
      const v = convertUnit(n, a.from, a.to);
      const label = u => UNIT_LABEL[u] || u;
      return `${fmt(n)} ${label(a.from)} = ${fmt(v)} ${label(a.to)}`;
    },
    "text.transform": function (a, ctx) {
      const t = resolveText(a.text, ctx);
      const op = a.op;
      switch (op) {
        case "reverse": return Array.from(t).reverse().join("");
        case "upper": return t.toUpperCase();
        case "lower": return t.toLowerCase();
        case "title": return t.replace(/\w\S*/g, w => w[0].toUpperCase() + w.slice(1).toLowerCase());
        case "sentence": return t.toLowerCase().replace(/(^\s*\w|[.!?]\s+\w)/g, c => c.toUpperCase());
        case "capitalize": return t.charAt(0).toUpperCase() + t.slice(1);
        case "trim": return t.trim();
        case "collapse": return t.replace(/\s+/g, " ").trim();
        case "slug": return t.toLowerCase().trim().replace(/[^\w\s-]/g, "").replace(/[\s_]+/g, "-").replace(/-+/g, "-");
        case "snake": return t.trim().replace(/[^\w\s-]/g, "").replace(/[\s-]+/g, "_").toLowerCase();
        case "kebab": return t.trim().replace(/[^\w\s-]/g, "").replace(/[\s_]+/g, "-").toLowerCase();
        case "camel": {
          const p = t.trim().split(/[^\w]+/).filter(Boolean);
          return p.map((w, i) => i ? w[0].toUpperCase() + w.slice(1).toLowerCase() : w.toLowerCase()).join("");
        }
        case "pascal":
          return t.trim().split(/[^\w]+/).filter(Boolean)
            .map(w => w[0].toUpperCase() + w.slice(1).toLowerCase()).join("");
        case "sortlines": return t.split("\n").sort().join("\n");
        case "sortwords": return words(t).sort((x, y) => x.localeCompare(y)).join(" ");
        case "uniqlines": return Array.from(new Set(t.split("\n"))).join("\n");
        case "reverselines": return t.split("\n").reverse().join("\n");
        case "reversewords": return words(t).reverse().join(" ");
        case "striptags": return t.replace(/<[^>]*>/g, "");
        case "leet": return t.replace(/[aeiost]/gi, c => ({ a: "4", e: "3", i: "1", o: "0", s: "5", t: "7" })[c.toLowerCase()] || c);
        case "initials": return words(t).map(w => w[0].toUpperCase()).join("");
        case "acronym": return words(t).filter(w => w.length > 2).map(w => w[0].toUpperCase()).join("");
        case "longest": return words(t).reduce((b, w) => w.length > b.length ? w : b, "");
        case "freq": {
          const counts = {};
          words(t.toLowerCase()).forEach(w => counts[w] = (counts[w] || 0) + 1);
          return Object.entries(counts).sort((p, q) => q[1] - p[1]).slice(0, 20)
            .map(([w, c]) => `${w}: ${c}`).join("\n");
        }
        case "charfreq": {
          const counts = {};
          for (const c of t.replace(/\s/g, "").toLowerCase()) counts[c] = (counts[c] || 0) + 1;
          return Object.entries(counts).sort((p, q) => q[1] - p[1])
            .map(([c, n]) => `${c}: ${n}`).join("\n");
        }
        case "indent": return t.split("\n").map(l => "  " + l).join("\n");
        case "dedupe": {
          const seen = new Set();
          return words(t).filter(w => { const k = w.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; }).join(" ");
        }
        default: throw new Error("unknown text op " + op);
      }
    },
    "text.count": function (a, ctx) {
      const t = resolveText(a.text, ctx);
      const what = a.what;
      const counts = {
        words: words(t).length,
        chars: t.length,
        lines: t ? t.split("\n").length : 0,
        sentences: (t.match(/[^.!?]+[.!?]+/g) || []).length || (t.trim() ? 1 : 0),
        vowels: (t.match(/[aeiou]/gi) || []).length,
        consonants: (t.match(/[bcdfghjklmnpqrstvwxyz]/gi) || []).length,
      };
      return `${counts[what]} ${what}`;
    },
    "text.check": function (a, ctx) {
      const t = resolveText(a.text, ctx);
      const clean = s => words(String(s).toLowerCase()).join("");
      if (a.op === "palindrome") {
        const c = clean(t);
        return c && c === Array.from(c).reverse().join("") ? "yes" : "no";
      }
      if (a.op === "anagram") {
        const t2 = resolveText(a.text2, ctx);
        const s1 = clean(t).split("").sort().join(""), s2 = clean(t2).split("").sort().join("");
        return s1 && s1 === s2 ? "yes" : "no";
      }
      throw new Error("unknown check " + a.op);
    },
    "text.extract": function (a, ctx) {
      const t = resolveText(a.text, ctx);
      const patterns = {
        emails: /[\w.+-]+@[\w-]+\.[\w.-]+/g,
        urls: /https?:\/\/[^\s<>"')]+/g,
        numbers: /-?\d[\d,]*(?:\.\d+)?/g,
      };
      const out = t.match(patterns[a.what]) || [];
      return out.length ? Array.from(new Set(out)).join("\n") : "(none found)";
    },
    "text.replace": function (a, ctx) {
      const t = resolveText(a.text, ctx);
      return t.split(String(a.find)).join(String(a.repl));
    },
    "encode": function (a, ctx) {
      const t = resolveText(a.text, ctx);
      switch (a.op) {
        case "b64e": return b64encode(t);
        case "b64d": return b64decode(t);
        case "urle": return encodeURIComponent(t);
        case "urld": return decodeURIComponent(t);
        case "hexe": return hexEncode(t);
        case "hexd": return hexDecode(t);
        case "bine": return Array.from(new TextEncoder().encode(t)).map(b => b.toString(2).padStart(8, "0")).join(" ");
        case "bind": return new TextDecoder().decode(new Uint8Array(t.trim().split(/\s+/).map(b => parseInt(b, 2))));
        case "rot13": return t.replace(/[a-z]/gi, c => {
          const base = c <= "Z" ? 65 : 97;
          return String.fromCharCode((c.charCodeAt(0) - base + 13) % 26 + base);
        });
        case "morse": return words(t.toLowerCase()).map(w => w.split("").map(c => MORSE[c] || "?").join(" ")).join(" / ");
        case "unmorse": return t.trim().split(/\s*\/\s*/).map(w => w.split(/\s+/).map(c => UNMORSE[c] || "?").join("")).join(" ");
        default: throw new Error("unknown encoding " + a.op);
      }
    },
    "hash": function (a, ctx) {
      return hashText(a.algo, resolveText(a.text, ctx));
    },
    "json.op": function (a, ctx) {
      const t = resolveText(a.text, ctx);
      let obj;
      if (a.op === "validate") {
        try { JSON.parse(t); return "valid JSON"; }
        catch (e) { return "invalid JSON: " + e.message; }
      }
      try { obj = JSON.parse(t); }
      catch (e) { throw new Error("invalid JSON: " + e.message); }
      switch (a.op) {
        case "pretty": return JSON.stringify(obj, null, 2);
        case "minify": return JSON.stringify(obj);
        case "keys": return Array.isArray(obj) ? obj.map((_, i) => i).join("\n") : Object.keys(obj).join("\n");
        case "values": return (Array.isArray(obj) ? obj : Object.values(obj)).map(v => typeof v === "object" ? JSON.stringify(v) : String(v)).join("\n");
        case "tocsv": return jsonToCsv(obj);
        default: throw new Error("unknown json op " + a.op);
      }
    },
    "csv.op": function (a, ctx) {
      return csvToJson(resolveText(a.text, ctx));
    },
    "date.op": function (a, ctx) {
      const now = new Date();
      const dateOf = v => {
        if (v === undefined || v === null || v === "") return now;
        const n = num(v);
        if (isFinite(n) && String(v).trim().match(/^\d+$/)) return new Date(n > 1e11 ? n : n * 1000);
        const d = new Date(v);
        if (isNaN(d)) throw new Error("not a date: " + v);
        return d;
      };
      const iso = d => d.toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC");
      switch (a.op) {
        case "time": return iso(now);
        case "now": return iso(now);
        case "today": return now.toISOString().slice(0, 10);
        case "unix": return String(Math.floor(now.getTime() / 1000));
        case "add": return iso(new Date(now.getTime() + numOrThrow(a.n) * 86400000));
        case "sub": return iso(new Date(now.getTime() - numOrThrow(a.n) * 86400000));
        case "diff": {
          const d1 = dateOf(a.a), d2 = dateOf(a.b);
          return fmt(Math.round((d2 - d1) / 86400000)) + " days";
        }
        case "weekday": return dateOf(a.text).toLocaleDateString(undefined, { weekday: "long" });
        case "leap": {
          const y = int(numOrThrow(a.n));
          return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0 ? "yes" : "no";
        }
        case "parse": {
          const d = dateOf(a.text);
          return `${iso(d)}\nunix: ${Math.floor(d.getTime() / 1000)}\nweekday: ${d.toLocaleDateString(undefined, { weekday: "long" })}`;
        }
        case "dayname": return now.toLocaleDateString(undefined, { weekday: "long" });
        case "year": return String(now.getFullYear());
        case "daysin": {
          const t = String(a.text).toLowerCase().replace(/[?.!]/g, "").trim();
          const leap = n => (n % 4 === 0 && n % 100 !== 0) || n % 400 === 0;
          const months = {
            january: 31, february: leap(now.getFullYear()) ? 29 : 28, march: 31,
            april: 30, may: 31, june: 30, july: 31, august: 31, september: 30,
            october: 31, november: 30, december: 31,
          };
          const names = Object.keys(months).filter(m => m.startsWith(t) || t.startsWith(m));
          if (names.length) return String(months[names[0]]);
          if (t === "this month" || t === "the month") {
            return String(new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate());
          }
          throw new Error("unknown month: " + a.text);
        }
        default: throw new Error("unknown date op " + a.op);
      }
    },
    "color.op": function (a) {
      switch (a.op) {
        case "toRgb": {
          const [r, g, b] = parseColor(a.text);
          return `rgb(${r}, ${g}, ${b})`;
        }
        case "toHex": return toHex([numOrThrow(a.a), numOrThrow(a.b), numOrThrow(a.c)]);
        case "lighten":
        case "darken": {
          const rgb = parseColor(a.text);
          const p = numOrThrow(a.n) / 100 * (a.op === "lighten" ? 1 : -1);
          return toHex(rgb.map(v => v + (p > 0 ? (255 - v) * p : v * p)));
        }
        case "mix": {
          const x = parseColor(a.a), y = parseColor(a.b);
          return toHex(x.map((v, i) => (v + y[i]) / 2));
        }
        case "contrast": return fmt(contrast(a.a, a.b)) + ":1";
        case "luminance": return fmt(luminance(parseColor(a.text)));
        default: throw new Error("unknown color op " + a.op);
      }
    },
    "gen.op": function (a, ctx) {
      const rnd = crypto.getRandomValues(new Uint32Array(1))[0] / 4294967296;
      const rint = (lo, hi) => lo + Math.floor(rnd * (hi - lo + 1));
      switch (a.op) {
        case "coin": return rnd < 0.5 ? "heads" : "tails";
        case "die": return String(rint(1, 6));
        case "dice": {
          const count = Math.min(100, int(numOrThrow(a.a)));
          return Array.from({ length: count }, () => rint(1, 6)).join(" ");
        }
        case "dice2": return Array.from({ length: Math.min(100, int(numOrThrow(a.a))) }, () => rint(1, int(numOrThrow(a.b)))).join(" ");
        case "rand": {
          const lo = Math.min(numOrThrow(a.a), numOrThrow(a.b));
          const hi = Math.max(numOrThrow(a.a), numOrThrow(a.b));
          return fmt(rint(Math.ceil(lo), Math.floor(hi)));
        }
        case "pick": {
          const opts = String(a.text).split(/\s*(?:,|\bor\b|\|)\s*/).filter(Boolean);
          if (!opts.length) throw new Error("nothing to pick from");
          return opts[rint(0, opts.length - 1)];
        }
        case "shuffle": {
          const opts = String(a.text).split(/\s*(?:,|\band\b)\s*/).filter(Boolean);
          for (let i = opts.length - 1; i > 0; i--) {
            const j = rint(0, i);
            [opts[i], opts[j]] = [opts[j], opts[i]];
          }
          return opts.join(", ");
        }
        case "lorem": {
          const pool = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna aliqua enim ad minim veniam quis nostrud exercitation ullamco laboris nisi aliquip ex ea commodo consequat".split(" ");
          const n = Math.min(500, int(numOrThrow(a.a)));
          return Array.from({ length: n }, () => pool[rint(0, pool.length - 1)]).join(" ");
        }
        case "uuid":
          return (root.crypto && crypto.randomUUID) ? crypto.randomUUID() :
            "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
              const r = rint(0, 15), v = c === "x" ? r : (r & 3 | 8);
              return v.toString(16);
            });
        case "pw":
        case "pwlen": {
          const len = a.op === "pwlen" ? Math.min(128, int(numOrThrow(a.a))) : 20;
          const chars = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%^&*-_=+";
          const bytes = crypto.getRandomValues(new Uint32Array(len));
          return Array.from(bytes, b => chars[b % chars.length]).join("");
        }
        default: throw new Error("unknown generator " + a.op);
      }
    },
    "regex.op": function (a, ctx) {
      const t = resolveText(a.text, ctx);
      if (a.op === "test") {
        const r = parseFlags(a.pat);
        return r.re.test(t) ? "match" : "no match";
      }
      if (a.op === "match") {
        const r = parseFlags(a.pat);
        const flags = r.re.flags.includes("g") ? r.re.flags : r.re.flags + "g";
        const re = new RegExp(r.re.source, flags);
        const found = Array.from(t.matchAll(re));
        return found.length ? found.map(m => m[0]).join("\n") : "(no matches)";
      }
      if (a.op === "replace") {
        const r = parseFlags(a.pat);
        const flags = r.re.flags.includes("g") ? r.re.flags : r.re.flags + "g";
        return t.replace(new RegExp(r.re.source, flags), String(a.repl));
      }
      throw new Error("unknown regex op " + a.op);
    },
    "echo": function (a, ctx) { return resolveText(a.text, ctx); },
    "fact.capital": function (a) {
      const key = factKey(a.subject);
      if (!key) return "name a country — e.g. \"capital of france\"";
      const hit = CAPITALS[key];
      return hit || `I don't have "${key}" in the local capitals table (it is a small, fixed list).`;
    },
    "fact.symbol": function (a) {
      const key = factKey(a.subject);
      const hit = SYMBOLS[key];
      return hit ? hit : `I don't have "${key}" in the local element table.`;
    },
    "preview": function (a, ctx) {
      const html = ctx.preview();
      return html ? "preview updated" : "nothing to preview yet — try: build a calculator app";
    },
    "preview.theme": function (a, ctx) {
      const ok = ctx.theme(a.theme);
      return ok ? `preview switched to ${a.theme}` : "no preview yet — build something first";
    },
    "system": function (a, ctx) {
      if (a.op === "who") {
        return "toolrx — a deterministic micro tool router. In this tab it runs a hashed n-gram model plus a "
          + meta.count + "-command pattern library. No LLM, no API key, no signal leaving the page.";
      }
      const topic = (a.topic || "").toLowerCase();
      if (a.op === "help" || a.op === "help") {
        return helpText(topic, ctx);
      }
      return helpText(topic, ctx);
    },
    "build": function (a, ctx) {
      return ctx.build(a.kind, a.desc);
    },
    "plan": function (a, ctx) {
      if (!ctx.architecture) throw new Error("architecture briefs need the browser workspace");
      return ctx.architecture(a.kind || a.desc || "app", a.desc || a.kind || "");
    },
    "blueprint": function (a, ctx) {
      if (!ctx.blueprint) throw new Error("blueprints need the browser workspace");
      return ctx.blueprint(a.kind || a.desc || "app", a.desc || a.kind || "");
    },
    "project.new": function (a, ctx) {
      if (!ctx.project) throw new Error("projects need the browser workspace");
      return ctx.project.new(a.name);
    },
    "project.list": function (a, ctx) {
      if (!ctx.project) throw new Error("projects need the browser workspace");
      return ctx.project.list();
    },
    "project.open": function (a, ctx) {
      if (!ctx.project) throw new Error("projects need the browser workspace");
      return ctx.project.open(a.slug);
    },
    "project.delete": function (a, ctx) {
      if (!ctx.project) throw new Error("projects need the browser workspace");
      return ctx.project.remove(a.slug);
    },
    "project.rename": function (a, ctx) {
      if (!ctx.project) throw new Error("projects need the browser workspace");
      return ctx.project.rename(a.slug, a.name);
    },
    "project.files": function (a, ctx) {
      if (!ctx.project) throw new Error("projects need the browser workspace");
      return ctx.project.files(a.slug);
    },
    "chat": function (a, ctx) {
      const text = chatReply((a && a.text) || (ctx && ctx.step) || "", ctx);
      return { text: text || "I'm here. Say a little more.", chat: true };
    },
    "web.search": async function (a, ctx) {
      if (!ctx.web) throw new Error("web access needs the browser workspace");
      return ctx.web.search(a.q);
    },
    "web.answer": async function (a, ctx) {
      if (!ctx.web) throw new Error("web access needs the browser workspace");
      return ctx.web.answer(a.q);
    },
    "web.define": async function (a, ctx) {
      if (!ctx.web) throw new Error("web access needs the browser workspace");
      return ctx.web.define(a.word);
    },
    "web.weather": async function (a, ctx) {
      if (!ctx.web) throw new Error("web access needs the browser workspace");
      return ctx.web.weather(a.place);
    },
    "text.summarize": function (a, ctx) {
      return summarizeText(resolveText(a.text, ctx), a.n ? Number(a.n) : 3);
    },
  };

  function helpText(topic, ctx) {
    const cats = meta.categories || {};
    if (topic) {
      const hits = search(topic, 40);
      if (hits.length) {
        return `commands matching "${topic}" (${hits.length} shown):\n\n` +
          hits.map(c => "  " + c.d).join("\n");
      }
      return `no commands matched "${topic}". Categories: ` + Object.keys(cats).join(", ");
    }
    const lines = ["deterministic command library: " + meta.count + " commands"];
    for (const [k, v] of Object.entries(cats)) lines.push(`  ${k.padEnd(10)} ${v}`);
    lines.push("");
    lines.push("examples:");
    lines.push("  multiply 67 and 420");
    lines.push("  square 67");
    lines.push("  convert 5 km to miles");
    lines.push("  count the words in notes.txt");
    lines.push("  build a calculator app");
    lines.push("  build an rpg");
    lines.push("  plan a todo app");
    lines.push("  new project notes / list projects / show project files");
    lines.push("  wikipedia ursula k le guin / define serendipity / weather in reykjavik");
    lines.push("  i feel overwhelmed · tell me a joke · remember my name is ada");
    lines.push("  read notes.txt then count the words");
    lines.push("");
    lines.push('say "help math" or "help text" for a category');
    return lines.join("\n");
  }

  /* ------------------------------------------------------------ matching -- */
  function compile(data) {
    meta = { count: data.count || data.commands.length, categories: data.categories || {} };
    COMMANDS = data.commands.map(c => Object.assign({}, c, { rx: new RegExp(c.re, "i") }));
    BY_OP = Object.create(null);
    for (const c of COMMANDS) (BY_OP[c.op] = BY_OP[c.op] || []).push(c);
  }

  function applyArgs(spec, m) {
    const out = {};
    for (const k in spec) {
      const v = spec[k];
      if (typeof v === "string" && v[0] === "$" && /^\$\d+$/.test(v)) {
        out[k] = m[Number(v.slice(1))];
      } else out[k] = v;
    }
    return out;
  }

  function match(q) {
    const query = String(q).replace(/\s+/g, " ").trim()
      .replace(/[?!]+$/, "").replace(/\.$/, "");
    if (!query) return null;
    for (const c of COMMANDS) {
      const m = c.rx.exec(query);
      if (m) return { id: c.id, op: c.op, args: applyArgs(c.args, m), desc: c.d, cat: c.c };
    }
    return null;
  }

  function search(term, limit) {
    const t = String(term).toLowerCase();
    const out = [];
    for (const c of COMMANDS) {
      if (c.d && c.d.toLowerCase().includes(t)) out.push(c);
      if (out.length >= (limit || 50)) break;
    }
    return out;
  }

  /* ------------------------------------------------------------- planner -- */
  function splitPrompt(q) {
    let text = String(q).replace(/\r/g, "").trim();
    if (!text) return [];
    const lines = text.split(/\n+/).map(s => s.replace(/^\s*(?:\d+[.)]|[-*])\s*/, "").trim()).filter(Boolean);
    let parts;
    if (lines.length > 1) parts = lines;
    else {
      parts = text.split(/\s*(?:;|->|→|\bthen\b|\bafter that\b|\band then\b|\bfollowed by\b)\s*/i)
        .map(s => s.trim()).filter(Boolean);
    }
    return parts.slice(0, 10);
  }

  async function exec(skill, ctx) {
    const fn = OPS[skill.op];
    if (!fn) throw new Error("no handler for " + skill.op);
    const out = await fn(skill.args, ctx);
    if (out && typeof out === "object") return out;
    return { text: cap(out === undefined ? "" : out) };
  }

  async function runPrompt(query, ctx) {
    const steps = splitPrompt(query);
    const results = [];
    let prev = "";
    for (const step of steps) {
      const local = Object.assign({}, ctx, { prev, step });
      let result;
      const skill = match(step);
      if (skill) {
        try {
          result = await exec(skill, local);
          result.via = skill.op;
          result.desc = skill.desc;
        } catch (e) {
          result = { text: String(e.message || e), error: true, via: skill.op, desc: skill.desc };
        }
      } else if (ctx.fallback) {
        result = await ctx.fallback(step, local);
      } else {
        result = { text: "no command matched that step", error: true };
      }
      result.step = step;
      if (result && result.text) prev = result.text;
      results.push(result);
    }
    return results;
  }

  root.toolrxSkills = {
    init: function (url) {
      return fetch(url, { cache: "force-cache" })
        .then(r => { if (!r.ok) throw new Error("commands " + r.status); return r.json(); })
        .then(data => { compile(data); return true; })
        .catch(() => false);
    },
    count: function () { return meta.count; },
    categories: function () { return meta.categories; },
    match: match,
    search: search,
    splitPrompt: splitPrompt,
    exec: exec,
    runPrompt: runPrompt,
    chat: chatReply,
    summarize: summarizeText,
    help: function () { return helpText("", null); },
  };
})(typeof self !== "undefined" ? self : this);

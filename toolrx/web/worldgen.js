/* toolrx world generator.
 *
 * Builds a deterministic, explorable RPG overworld from a seed: biomes, coast,
 * rivers, roads, three-to-five towns, a dungeon, NPCs, enemies, pickups, and a
 * quest chain. Everything is plain JSON so it can be saved, replayed, and
 * generated again identically from the same seed.
 *
 * Exposes: self.toolrxWorldgen = { generate, TILE, hash, rng, defaultTheme }
 */
(function (root) {
  "use strict";

  var TILE = {
    DEEP: 0, SHALLOW: 1, SAND: 2, GRASS: 3, FOREST: 4, HILL: 5,
    MOUNTAIN: 6, SNOW: 7, ROAD: 8, TOWN: 9, BRIDGE: 10,
    FLOOR: 11, WALL: 12
  };

  var WALKABLE = {
    0: false, 1: false, 2: true, 3: true, 4: true, 5: true, 6: false,
    7: true, 8: true, 9: true, 10: true, 11: true, 12: false
  };

  var DEFAULT_THEME = {
    title: "Verdant RPG",
    sub: "a seed-grown world",
    boss: "the Warden",
    enemy: "slime",
    elder: "the Elder",
    shrine: "the shrine",
    groundA: "#2c4a33", groundB: "#35563b", tree: "#3f6b4a",
    wall: "#3b4658", wall2: "#2a3244",
    places: ["Verdant Hollow", "Mossford", "Greenreach", "Thornvale", "Emberfield"],
    npcs: ["Mira", "Bram", "Sable", "Oren", "Pella", "Rook", "Wren", "Ivo"],
    enemies: ["slime", "thornling", "bog bat"],
    items: ["moon herb", "river stone", "old key"],
    dungeonName: "the Sunken Barrow"
  };

  function hash(s) {
    var h = 2166136261;
    s = String(s == null ? "" : s);
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function rng(seed) {
    var h = (typeof seed === "number" ? seed : hash(seed)) >>> 0;
    return function () {
      h += 0x6D2B79F5;
      var t = h;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function smooth(t) { return t * t * (3 - 2 * t); }

  function rand2(x, y, seed) {
    var h = (seed >>> 0) ^ Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263);
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  }

  function noise2(x, y, seed) {
    var x0 = Math.floor(x), y0 = Math.floor(y);
    var fx = smooth(x - x0), fy = smooth(y - y0);
    var a = rand2(x0, y0, seed), b = rand2(x0 + 1, y0, seed);
    var c = rand2(x0, y0 + 1, seed), d = rand2(x0 + 1, y0 + 1, seed);
    return lerp(lerp(a, b, fx), lerp(c, d, fx), fy);
  }

  function field(x, y, seed) {
    return 0.5 * noise2(x / 26, y / 26, seed)
      + 0.3 * noise2(x / 13, y / 13, seed ^ 0x9e3779b9)
      + 0.2 * noise2(x / 6, y / 6, seed ^ 0x85ebca6b);
  }

  function hex(c) {
    var s = String(c || "").replace("#", "");
    if (s.length === 3) s = s[0] + s[0] + s[1] + s[1] + s[2] + s[2];
    var n = parseInt(s.slice(0, 6), 16);
    return isFinite(n) ? n : 0x445566;
  }

  function mix(a, b, t) {
    var x = hex(a), y = hex(b);
    var r = Math.round(lerp(x >> 16 & 255, y >> 16 & 255, t));
    var g = Math.round(lerp(x >> 8 & 255, y >> 8 & 255, t));
    var bl = Math.round(lerp(x & 255, y & 255, t));
    return "#" + ((1 << 24) | (r << 16) | (g << 8) | bl).toString(16).slice(1);
  }

  function palette(theme) {
    var g = theme.groundA || "#2c4a33";
    var g2 = theme.groundB || mix(g, "#ffffff", 0.08);
    var tree = theme.tree || "#3f6b4a";
    return {
      deep: mix("#0d2233", g, 0.18),
      shallow: "#2f6b8c",
      water: "#2a5f7f",
      sand: "#c2a86b",
      grass: g,
      grass2: g2,
      forest: tree,
      hill: mix(tree, "#8a7b62", 0.4),
      mountain: theme.wall2 || "#5a6273",
      snow: "#dfe8ef",
      road: "#8a7550",
      town: mix(g, "#a8926a", 0.55),
      bridge: "#8a6b45",
      rock: theme.wall2 || "#2a3244",
      floor: "#3b4252",
      wall: theme.wall || "#2b3346",
      roof: "#7a3b3b",
      accent: "#fbbf24",
      gold: "#fbbf24",
      hp: "#ef4444",
      xp: "#34d399",
      ink: "#0b1020"
    };
  }

  function themeOf(theme) {
    var out = {};
    theme = theme || {};
    Object.keys(DEFAULT_THEME).forEach(function (k) {
      out[k] = theme[k] === undefined ? DEFAULT_THEME[k] : theme[k];
    });
    return out;
  }

  function pick(r, arr) { return arr[Math.floor(r() * arr.length) % arr.length]; }

  function generate(opts) {
    opts = opts || {};
    var seed = (opts.seed === undefined ? hash(opts.title || "world") : opts.seed) >>> 0;
    var theme = themeOf(opts.theme);
    var pal = palette(theme);
    var size = clamp(Math.round(opts.size || (opts.large ? 96 : 64)), 48, 128);
    var r = rng(seed);
    var x, y, i, j;

    var heights = [], moist = [], grid = [];
    for (y = 0; y < size; y++) {
      heights[y] = []; moist[y] = []; grid[y] = [];
      for (x = 0; x < size; x++) {
        var nx = x / size * 2 - 1, ny = y / size * 2 - 1;
        var edge = Math.pow(Math.max(Math.abs(nx), Math.abs(ny)), 3);
        var e = field(x, y, seed) * 1.08 - edge * 0.42;
        var m = field(x + 91, y + 37, seed ^ 0x27d4eb2f);
        heights[y][x] = e;
        moist[y][x] = m;
      }
    }

    function biomeAt(e, m) {
      if (e < 0.235) return TILE.DEEP;
      if (e < 0.30) return TILE.SHALLOW;
      if (e < 0.345) return TILE.SAND;
      if (e > 0.79) return TILE.SNOW;
      if (e > 0.70) return TILE.MOUNTAIN;
      if (e > 0.60) return TILE.HILL;
      return m > 0.55 ? TILE.FOREST : TILE.GRASS;
    }

    for (y = 0; y < size; y++) {
      for (x = 0; x < size; x++) grid[y][x] = biomeAt(heights[y][x], moist[y][x]);
    }

    function inside(x, y) { return x >= 0 && y >= 0 && x < size && y < size; }
    function at(x, y) { return inside(x, y) ? grid[y][x] : TILE.DEEP; }
    function set(x, y, t) { if (inside(x, y)) grid[y][x] = t; }
    function land(x, y) {
      var t = at(x, y);
      return t === TILE.SAND || t === TILE.GRASS || t === TILE.FOREST
        || t === TILE.HILL || t === TILE.SNOW || t === TILE.ROAD || t === TILE.TOWN;
    }

    /* Two rivers run downhill from high ground to the sea. */
    function river() {
      var best = null, bs = -1;
      for (var k = 0; k < 120; k++) {
        var sx = 2 + Math.floor(r() * (size - 4));
        var sy = 2 + Math.floor(r() * (size - 4));
        var hv = heights[sy][sx];
        if (hv > bs && at(sx, sy) !== TILE.DEEP) { bs = hv; best = [sx, sy]; }
      }
      if (!best) return;
      var cx = best[0], cy = best[1];
      for (var step = 0; step < size * 2; step++) {
        var here = heights[cy][cx];
        set(cx, cy, TILE.SHALLOW);
        if (r() < 0.45) set(cx + (r() < 0.5 ? 1 : -1), cy, TILE.SAND);
        var low = null, lv = here;
        for (var d = 0; d < 4; d++) {
          var dx = [1, -1, 0, 0][d], dy = [0, 0, 1, -1][d];
          if (!inside(cx + dx, cy + dy)) continue;
          var nh = heights[cy + dy][cx + dx] + (r() - 0.5) * 0.03;
          if (nh < lv) { lv = nh; low = [cx + dx, cy + dy]; }
        }
        if (!low) {
          var open = [];
          for (var d2 = 0; d2 < 4; d2++) {
            var ox = [1, -1, 0, 0][d2], oy = [0, 0, 1, -1][d2];
            if (inside(cx + ox, cy + oy)) open.push([cx + ox, cy + oy]);
          }
          if (!open.length) break;
          low = open[Math.floor(r() * open.length)];
        }
        cx = low[0]; cy = low[1];
        if (at(cx, cy) === TILE.DEEP) break;
      }
    }
    river();
    river();

    /* Towns: spaced-out land sites, flattened into a plaza with houses. */
    var towns = [];
    var townCount = size >= 88 ? 5 : (size >= 72 ? 4 : 3);
    var tries = 0;
    while (towns.length < townCount && tries++ < 900) {
      var tx = 6 + Math.floor(r() * (size - 12));
      var ty = 6 + Math.floor(r() * (size - 12));
      if (!land(tx, ty) || at(tx, ty) === TILE.SNOW) continue;
      var ok = true;
      for (var t = 0; t < towns.length; t++) {
        var td = Math.hypot(towns[t].x - tx, towns[t].y - ty);
        if (td < size * 0.27) { ok = false; break; }
      }
      if (!ok) continue;
      var clear = 0;
      for (var oy = -3; oy <= 3; oy++) for (var ox = -3; ox <= 3; ox++) {
        if (land(tx + ox, ty + oy)) clear++;
      }
      if (clear < 30) continue;
      towns.push({
        id: "town" + towns.length,
        name: theme.places[towns.length % theme.places.length],
        x: tx, y: ty, buildings: [], npcs: []
      });
    }

    towns.forEach(function (town, ti) {
      for (var oy2 = -4; oy2 <= 4; oy2++) {
        for (var ox2 = -4; ox2 <= 4; ox2++) {
          var d = Math.max(Math.abs(ox2), Math.abs(oy2));
          if (d > 4) continue;
          var px = town.x + ox2, py = town.y + oy2;
          if (!inside(px, py)) continue;
          if (d <= 2) set(px, py, TILE.TOWN);
          else if (at(px, py) !== TILE.DEEP && at(px, py) !== TILE.SHALLOW) {
            set(px, py, TILE.GRASS);
          }
        }
      }
      for (x = -2; x <= 2; x++) { set(town.x + x, town.y, TILE.ROAD); set(town.x, town.y + x, TILE.ROAD); }
      var houses = 3 + Math.floor(r() * 4);
      for (var h = 0; h < houses; h++) {
        var ang = (h / houses) * Math.PI * 2 + r() * 0.5;
        var hx = town.x + Math.round(Math.cos(ang) * 3);
        var hy = town.y + Math.round(Math.sin(ang) * 3);
        var w = 2, dd = 2;
        if (hx < 2 || hy < 2 || hx + w >= size - 2 || hy + dd >= size - 2) continue;
        town.buildings.push({ x: hx, y: hy, w: w, d: dd, door: [hx + 1, hy + dd - 1] });
        for (var by = 0; by < dd; by++) for (var bx = 0; bx < w; bx++) {
          set(hx + bx, hy + by, TILE.TOWN);
        }
      }
    });

    /* Roads connect each new town to the closest earlier one. */
    function carveRoad(a, b) {
      var ax = a.x, ay = a.y, bx = b.x, by = b.y;
      var steps = Math.max(Math.abs(bx - ax), Math.abs(by - ay)) * 2;
      for (var k = 0; k <= steps; k++) {
        var t = k / steps;
        var wob = Math.sin(t * Math.PI * (2 + (a.id.length % 2))) * 1.4;
        var cx2 = Math.round(lerp(ax, bx, t) + wob);
        var cy2 = Math.round(lerp(ay, by, t) - wob);
        if (!inside(cx2, cy2)) continue;
        var cur = at(cx2, cy2);
        if (cur === TILE.DEEP || cur === TILE.SHALLOW) set(cx2, cy2, TILE.BRIDGE);
        else if (cur !== TILE.TOWN) {
          set(cx2, cy2, TILE.ROAD);
          if (r() < 0.35) set(cx2 + (r() < 0.5 ? 1 : -1), cy2, TILE.ROAD);
        }
      }
    }
    for (i = 1; i < towns.length; i++) {
      var near = 0, nd = Infinity;
      for (j = 0; j < i; j++) {
        var dist = Math.hypot(towns[j].x - towns[i].x, towns[j].y - towns[i].y);
        if (dist < nd) { nd = dist; near = j; }
      }
      carveRoad(towns[i], towns[near]);
    }

    /* Dungeon site: far from the start town, preferably in hills or mountains. */
    var startTown = towns[0];
    var dungeon = null, dscore = -1;
    for (y = 3; y < size - 3; y++) {
      for (x = 3; x < size - 3; x++) {
        var tl = at(x, y);
        if (tl !== TILE.HILL && tl !== TILE.MOUNTAIN && tl !== TILE.FOREST) continue;
        var ds = Math.hypot(x - (startTown ? startTown.x : size / 2),
                            y - (startTown ? startTown.y : size / 2));
        if (ds > size * 0.3 && ds > dscore) { dscore = ds; dungeon = { x: x, y: y }; }
      }
    }
    if (!dungeon) {
      dungeon = { x: Math.min(size - 6, Math.floor(size * 0.75)),
                  y: Math.min(size - 6, Math.floor(size * 0.68)) };
    }
    dungeon.name = theme.dungeonName || "the Sunken Barrow";
    dungeon.id = "dungeon";
    set(dungeon.x, dungeon.y, TILE.FLOOR);
    for (var dy = -1; dy <= 1; dy++) for (var dx = -1; dx <= 1; dx++) {
      if (dx || dy) set(dungeon.x + dx, dungeon.y + dy, TILE.TOWN);
    }

    /* Pickups: herbs for the healer, chests with gold and potions. */
    var pickups = [];
    function freeSpot(allow) {
      for (var k2 = 0; k2 < 400; k2++) {
        var px2 = 2 + Math.floor(r() * (size - 4));
        var py2 = 2 + Math.floor(r() * (size - 4));
        if (allow.indexOf(at(px2, py2)) >= 0) return { x: px2, y: py2 };
      }
      return null;
    }
    for (i = 0; i < 6; i++) {
      var herb = freeSpot([TILE.GRASS, TILE.FOREST, TILE.HILL]);
      if (herb) pickups.push({ id: "herb" + i, x: herb.x, y: herb.y, kind: "herb", taken: false });
    }
    for (i = 0; i < 6; i++) {
      var chest = freeSpot([TILE.GRASS, TILE.FOREST, TILE.HILL, TILE.SAND]);
      if (chest) pickups.push({
        id: "chest" + i, x: chest.x, y: chest.y, kind: i % 3 === 0 ? "potion" : "gold",
        amount: i % 3 === 0 ? 1 : 8 + Math.floor(r() * 18), taken: false
      });
    }

    /* Enemies: seeded spawns, mostly away from town centres. */
    var enemies = [];
    var types = (theme.enemies || DEFAULT_THEME.enemies).slice(0, 3);
    var ecount = Math.max(18, Math.round(size * 0.42));
    for (i = 0; i < ecount; i++) {
      var spot = freeSpot([TILE.GRASS, TILE.FOREST, TILE.HILL, TILE.SAND, TILE.SNOW]);
      if (!spot) continue;
      var away = true;
      for (var ti2 = 0; ti2 < towns.length; ti2++) {
        if (Math.hypot(spot.x - towns[ti2].x, spot.y - towns[ti2].y) < 6) { away = false; break; }
      }
      if (!away) continue;
      var typeIdx = i % types.length;
      var emax = 6 + typeIdx * 3 + Math.floor(r() * 4);
      enemies.push({
        id: "e" + i, x: spot.x, y: spot.y, homeX: spot.x, homeY: spot.y,
        type: types[typeIdx], kindIdx: typeIdx,
        hp: emax, maxHp: emax, damage: 1 + typeIdx,
        speed: 0.8 + typeIdx * 0.25 + r() * 0.3,
        color: ["#a855f7", "#f97316", "#38bdf8"][typeIdx % 3],
        alive: true
      });
    }

    /* NPCs: two per town, with names, lines, and one merchant per town pair. */
    var roles = ["elder", "merchant", "healer", "smith", "guard", "scholar", "farmer", "bard"];
    var npcs = [];
    var npcIndex = 0;
    towns.forEach(function (town, ti) {
      var wanted = ["elder", "merchant"];
      if (ti === 1) wanted = ["healer", "guard"];
      if (ti === 2) wanted = ["scholar", "smith"];
      if (ti >= 3) wanted = [roles[(ti * 2 + 3) % roles.length], "merchant"];
      wanted.forEach(function (role) {
        var name = theme.npcs[(npcIndex + ti) % theme.npcs.length];
        npcIndex++;
        var spot = null;
        for (var k3 = 0; k3 < towns.length * 30 && !spot; k3++) {
          var nx2 = town.x + Math.floor(r() * 7) - 3;
          var ny2 = town.y + Math.floor(r() * 7) - 3;
          if (at(nx2, ny2) === TILE.TOWN || at(nx2, ny2) === TILE.ROAD) {
            if (!npcs.some(function (n) { return n.x === nx2 && n.y === ny2; })) {
              spot = { x: nx2, y: ny2 };
            }
          }
        }
        if (!spot) spot = { x: town.x, y: town.y + 1 };
        var npc = {
          id: "n" + npcs.length,
          name: name,
          role: role,
          town: town.id,
          x: spot.x, y: spot.y,
          color: role === "merchant" ? "#f59e0b"
            : role === "healer" ? "#34d399"
              : role === "elder" ? "#e2e8f0" : "#93c5fd",
          lines: [],
          quest: null
        };
        if (role === "elder") {
          npc.lines = ["The " + theme.boss.replace(/^the /, "") + " stirs in " + dungeon.name + ".",
            "Take the road, gather your strength, and end it."];
        } else if (role === "merchant") {
          npc.lines = ["Weapons, potions, and rumours. Which will it be?"];
          npc.shop = true;
        } else if (role === "healer") {
          npc.lines = ["The marsh herbs mend what steel cannot.",
            "Bring me three and I will make it worth your while."];
        } else if (role === "smith") {
          npc.lines = ["A blade is only as good as the arm that holds it."];
        } else if (role === "guard") {
          npc.lines = ["Something has been raiding the roads at night.",
            "Thin their numbers and I will pay."];
        } else if (role === "scholar") {
          npc.lines = ["The barrow predates the town. Its door is older than the stones."];
        } else {
          npc.lines = ["The land remembers more than we do."];
        }
        npcs.push(npc);
        town.npcs.push(npc.id);
      });
    });

    /* Quest chain. Every quest is deterministic and tied to real people/places. */
    var quests = [];
    function npcByRole(role, offset) {
      var list = npcs.filter(function (n) { return n.role === role; });
      return list[(offset || 0) % list.length] || npcs[0];
    }
    var elder = npcByRole("elder", 0);
    var guard = npcByRole("guard", 0);
    var healer = npcByRole("healer", 0);
    var scholar = npcByRole("scholar", 0);
    var courier = npcs[Math.min(npcs.length - 1, 3)];

    quests.push({
      id: "q-boss", kind: "boss", title: "The " + theme.boss.replace(/^the /, ""),
      desc: "Defeat " + theme.boss + " in " + dungeon.name + ".",
      giver: elder ? elder.id : null, target: "boss", need: 1, progress: 0,
      state: "offered", reward: { gold: 120, xp: 60 }
    });
    quests.push({
      id: "q-kill", kind: "kill", title: "Thin the " + (types[0] || "herd"),
      desc: "Defeat six " + (types[0] || "creatures") + " on the roads.",
      giver: guard ? guard.id : (elder ? elder.id : null), target: types[0] || "creature",
      need: 6, progress: 0, state: "offered", reward: { gold: 45, xp: 25 }
    });
    quests.push({
      id: "q-herbs", kind: "collect", title: "Marsh medicine",
      desc: "Gather three herbs for the healer.",
      giver: healer ? healer.id : (elder ? elder.id : null), target: "herb",
      need: 3, progress: 0, state: "offered", reward: { gold: 35, xp: 20 }
    });
    var farNpc = npcs.filter(function (n) { return n.id !== courier.id; })[0] || npcs[0];
    quests.push({
      id: "q-letter", kind: "deliver", title: "A sealed letter",
      desc: "Deliver a letter to " + farNpc.name + " in " + (towns[1] ? towns[1].name : "the next town") + ".",
      giver: courier.id, target: farNpc.id,
      need: 1, progress: 0, state: "offered", reward: { gold: 30, xp: 15 }
    });
    if (scholar) {
      quests.push({
        id: "q-explore", kind: "explore", title: "The old barrow",
        desc: "Find and enter " + dungeon.name + ".",
        giver: scholar.id, target: "dungeon", need: 1, progress: 0,
        state: "offered", reward: { gold: 25, xp: 15 }
      });
    }
    quests.forEach(function (q) {
      npcs.forEach(function (n) { if (n.id === q.giver) n.quest = q.id; });
    });

    /* Dungeon interior: rooms joined by corridors, a boss in the far room. */
    var DW = 31, DH = 21;
    var dmap = [];
    for (y = 0; y < DH; y++) {
      dmap[y] = [];
      for (x = 0; x < DW; x++) dmap[y][x] = TILE.WALL;
    }
    var rooms = [];
    var roomTries = 0;
    while (rooms.length < 6 && roomTries++ < 120) {
      var rw = 4 + Math.floor(r() * 4), rh = 3 + Math.floor(r() * 3);
      var rx = 2 + Math.floor(r() * (DW - rw - 4));
      var ry = 2 + Math.floor(r() * (DH - rh - 4));
      var clash = rooms.some(function (rm) {
        return rx < rm.x + rm.w + 1 && rx + rw + 1 > rm.x
          && ry < rm.y + rm.h + 1 && ry + rh + 1 > rm.y;
      });
      if (clash) continue;
      rooms.push({ x: rx, y: ry, w: rw, h: rh });
      for (var yy = ry; yy < ry + rh; yy++) for (var xx = rx; xx < rx + rw; xx++) {
        dmap[yy][xx] = TILE.FLOOR;
      }
    }
    for (i = 1; i < rooms.length; i++) {
      var a = rooms[i - 1], b = rooms[i];
      var corrX = Math.floor(a.x + a.w / 2), corrY = Math.floor(a.y + a.h / 2);
      var endX = Math.floor(b.x + b.w / 2), endY = Math.floor(b.y + b.h / 2);
      for (x = Math.min(corrX, endX); x <= Math.max(corrX, endX); x++) {
        if (dmap[corrY][x] === TILE.WALL) dmap[corrY][x] = TILE.FLOOR;
      }
      for (y = Math.min(corrY, endY); y <= Math.max(corrY, endY); y++) {
        if (dmap[y][endX] === TILE.WALL) dmap[y][endX] = TILE.FLOOR;
      }
    }
    var bossRoom = rooms[rooms.length - 1];
    var entryRoom = rooms[0];
    var dungeonState = {
      w: DW, h: DH, tiles: dmap, rooms: rooms,
      entry: { x: Math.floor(entryRoom.x + entryRoom.w / 2), y: Math.floor(entryRoom.y + entryRoom.h / 2) },
      boss: {
        id: "boss", x: Math.floor(bossRoom.x + bossRoom.w / 2),
        y: Math.floor(bossRoom.y + bossRoom.h / 2),
        type: theme.boss, hp: 44, maxHp: 44, damage: 4, speed: 1.35,
        color: "#ef4444", alive: true, boss: true
      },
      minions: []
    };
    for (i = 1; i < rooms.length - 1; i++) {
      dungeonState.minions.push({
        id: "dm" + i,
        x: Math.floor(rooms[i].x + rooms[i].w / 2),
        y: Math.floor(rooms[i].y + rooms[i].h / 2),
        type: (types[1] || types[0] || "shade"),
        kindIdx: 1, hp: 12, maxHp: 12, damage: 2, speed: 0.95,
        color: "#a855f7", alive: true
      });
    }

    var start = { x: startTown ? startTown.x : size / 2, y: (startTown ? startTown.y : size / 2) + 1 };
    if (!land(start.x, start.y)) {
      start = { x: Math.floor(size / 2), y: Math.floor(size / 2) };
      for (var sy2 = 0; sy2 < size && !land(start.x, start.y); sy2++) {
        for (var sx2 = 0; sx2 < size; sx2++) {
          if (land(sx2, sy2)) { start = { x: sx2, y: sy2 }; break; }
        }
      }
    }

    return {
      version: 1,
      seed: seed,
      size: size,
      theme: theme,
      palette: pal,
      tiles: grid,
      heights: heights,
      towns: towns,
      dungeon: dungeon,
      dungeonMap: dungeonState,
      npcs: npcs,
      quests: quests,
      enemies: enemies,
      pickups: pickups,
      start: start,
      walkable: function (x, y) {
        if (x < 0 || y < 0 || x >= size || y >= size) return false;
        return !!WALKABLE[grid[Math.floor(y)][Math.floor(x)]];
      },
      tileAt: function (x, y) {
        if (x < 0 || y < 0 || x >= size || y >= size) return TILE.DEEP;
        return grid[Math.floor(y)][Math.floor(x)];
      },
      isWater: function (x, y) {
        var t = this.tileAt(x, y);
        return t === TILE.DEEP || t === TILE.SHALLOW;
      }
    };
  }

  root.toolrxWorldgen = {
    generate: generate,
    TILE: TILE,
    WALKABLE: WALKABLE,
    hash: hash,
    rng: rng,
    defaultTheme: DEFAULT_THEME
  };
})(typeof self !== "undefined" ? self : this);

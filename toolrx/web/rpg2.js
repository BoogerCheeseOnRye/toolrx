/* toolrx RPG runtime.
 *
 * An isometric, explorable RPG built on engine2d + worldgen. Handles the
 * camera, dialogue, shops, quests, action battles, inventory, a dungeon,
 * minimap, touch controls, and three local save slots.
 *
 * Exposes: self.toolrxRpg2 = { create }
 */
(function (root) {
  "use strict";

  var T = (root.toolrxWorldgen && root.toolrxWorldgen.TILE) || {
    DEEP: 0, SHALLOW: 1, SAND: 2, GRASS: 3, FOREST: 4, HILL: 5,
    MOUNTAIN: 6, SNOW: 7, ROAD: 8, TOWN: 9, BRIDGE: 10, FLOOR: 11, WALL: 12
  };

  var VIEW_W = 960, VIEW_H = 540;
  var TW = 32, TH = 16;

  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function now() {
    return typeof performance !== "undefined" && performance.now
      ? performance.now() : Date.now();
  }

  function create(opts) {
    opts = opts || {};
    var E = opts.engine;
    if (!E) throw new Error("rpg2 needs an engine (engine2d)");
    var canvas = opts.canvas || E.canvas;
    var ctx = opts.ctx || E.ctx || (canvas && canvas.getContext("2d"));
    if (!ctx) throw new Error("rpg2 needs a 2d context");
    var W = opts.world;
    if (!W || !W.tiles) throw new Error("rpg2 needs a generated world");
    var theme = opts.theme || W.theme || {};
    var pal = W.palette || {};

    var viewW = opts.width || VIEW_W;
    var viewH = opts.height || VIEW_H;
    var state = {
      mode: "play",
      map: "overworld",
      time: 0,
      cam: { x: W.start.x, y: W.start.y },
      player: {
        x: W.start.x, y: W.start.y, fx: 1, fy: 1,
        hp: 30, maxHp: 30, level: 1, xp: 0, xpNext: 25,
        gold: 10, potions: 2, attackT: 0, attackCd: 0, hurtT: 0, walk: 0
      },
      quests: W.quests.map(function (q) {
        return { id: q.id, state: q.state, progress: q.progress };
      }),
      defeated: {},
      taken: {},
      explored: {},
      toast: "",
      toastT: 0,
      dialogue: null,
      shop: null,
      menu: 0,
      help: false,
      touch: !!(root.matchMedia && root.matchMedia("(pointer:coarse)").matches),
      dungeonReturn: null,
      over: false,
      play: 0,
      kills: 0,
      lastSave: "",
      nearD: false,
      pointer: null
    };
    var pressed = {};
    var touchActions = [];

    function tap(a) { return !!(E.tap && E.tap(a)); }
    function held(a) { return !!(E.held && E.held(a)); }

    function player() { return state.player; }
    function liveEnemies() {
      return state.map === "dungeon" ? W.dungeonMap.minions.concat([W.dungeonMap.boss])
        : W.enemies;
    }
    function entityAlive(e) {
      return e && e.alive && !state.defeated[e.id];
    }
    function onMap() {
      if (state.map === "dungeon") {
        return {
          w: W.dungeonMap.w, h: W.dungeonMap.h, tiles: W.dungeonMap.tiles,
          walkable: function (x, y) {
            var ix = Math.floor(x), iy = Math.floor(y);
            if (ix < 0 || iy < 0 || ix >= W.dungeonMap.w || iy >= W.dungeonMap.h) return false;
            return W.dungeonMap.tiles[iy][ix] === T.FLOOR;
          }
        };
      }
      return {
        w: W.size, h: W.size, tiles: W.tiles,
        walkable: function (x, y) { return W.walkable(x, y); }
      };
    }

    function buildingAt(x, y) {
      if (state.map !== "overworld") return false;
      for (var t = 0; t < W.towns.length; t++) {
        var bs = W.towns[t].buildings;
        for (var b = 0; b < bs.length; b++) {
          var r = bs[b];
          if (x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.d) {
            if (r.door && Math.floor(x) === r.door[0] && Math.floor(y) === r.door[1]) return false;
            return true;
          }
        }
      }
      return false;
    }

    function blocked(x, y) {
      if (state.map === "overworld" && W.isWater(x, y)) return true;
      if (!onMap().walkable(x, y)) return true;
      return buildingAt(x, y);
    }

    function move(ent, dx, dy, dist) {
      var steps = Math.max(1, Math.ceil(dist / 0.35));
      var sx = dx / steps, sy = dy / steps;
      for (var i = 0; i < steps; i++) {
        if (!blocked(ent.x + sx, ent.y)) ent.x += sx;
        if (!blocked(ent.x, ent.y + sy)) ent.y += sy;
      }
    }

    function quest(id) {
      for (var i = 0; i < W.quests.length; i++) if (W.quests[i].id === id) return W.quests[i];
      return null;
    }
    function qstate(q) {
      for (var i = 0; i < state.quests.length; i++) if (state.quests[i].id === q.id) return state.quests[i];
      return null;
    }
    function questEvent(kind, target, n) {
      n = n == null ? 1 : n;
      W.quests.forEach(function (q) {
        var s = qstate(q);
        if (!s || s.state !== "active" || q.kind !== kind) return;
        if (q.target !== target) return;
        s.progress = Math.min(q.need, s.progress + n);
        if (s.progress >= q.need) {
          s.state = "ready";
          toast("Quest ready · return to " + npcName(q.giver));
          E.beep && E.beep(920, 0.09, "triangle");
        }
      });
    }
    function npcName(id) {
      for (var i = 0; i < W.npcs.length; i++) if (W.npcs[i].id === id) return W.npcs[i].name;
      return "the quest giver";
    }
    function npcById(id) {
      for (var i = 0; i < W.npcs.length; i++) if (W.npcs[i].id === id) return W.npcs[i];
      return null;
    }
    function toast(text, secs) {
      state.toast = String(text || "");
      state.toastT = secs || 2.6;
    }

    function addXp(n) {
      var p = player();
      p.xp += n;
      while (p.xp >= p.xpNext) {
        p.xp -= p.xpNext;
        p.level++;
        p.xpNext = 20 + p.level * 18;
        p.maxHp += 5;
        p.hp = p.maxHp;
        toast("Level " + p.level + " · max HP " + p.maxHp);
        E.beep && E.beep(760, 0.12, "triangle");
      }
    }

    function reveal() {
      var r = state.map === "dungeon" ? 3 : 5;
      var p = player();
      var cx = Math.floor(p.x), cy = Math.floor(p.y);
      var m = onMap();
      for (var y = cy - r; y <= cy + r; y++) {
        for (var x = cx - r; x <= cx + r; x++) {
          if (Math.hypot(x - cx, y - cy) > r + 0.3) continue;
          if (x < 0 || y < 0 || x >= m.w || y >= m.h) continue;
          var key = (state.map === "dungeon" ? "d" : "o") + x + "," + y;
          if (!state.explored[key]) {
            state.explored[key] = 1;
            if (mini) mini.dirty = true;
          }
        }
      }
    }

    function pickupNear() {
      if (state.map !== "overworld") return;
      var p = player();
      W.pickups.forEach(function (it) {
        if (state.taken[it.id]) return;
        if (Math.hypot(it.x - p.x, it.y - p.y) > 0.75) return;
        state.taken[it.id] = 1;
        if (it.kind === "herb") {
          p.potions += 0;
          p.herbs = (p.herbs || 0) + 1;
          toast("Picked a herb (" + (p.herbs || 0) + ")");
          questEvent("collect", "herb", 1);
        } else if (it.kind === "potion") {
          p.potions++;
          toast("Found a potion");
        } else {
          p.gold += it.amount || 10;
          toast("Found " + (it.amount || 10) + " gold");
        }
        E.beep && E.beep(it.kind === "herb" ? 660 : 880, 0.06, "triangle");
      });
    }

    function nearestNpc() {
      if (state.map !== "overworld") return null;
      var p = player(), best = null, bd = 2.0;
      W.npcs.forEach(function (n) {
        var d = Math.hypot(n.x - p.x, n.y - p.y);
        if (d < bd) { bd = d; best = n; }
      });
      return best;
    }

    function nearDungeon() {
      if (state.map !== "overworld") return false;
      var p = player();
      return Math.hypot(W.dungeon.x - p.x, W.dungeon.y - p.y) < 1.8;
    }

    function enterDungeon() {
      if (state.map === "dungeon") return;
      state.dungeonReturn = { x: player().x, y: player().y };
      state.map = "dungeon";
      var entry = W.dungeonMap.entry;
      player().x = entry.x;
      player().y = entry.y;
      state.cam.x = entry.x;
      state.cam.y = entry.y;
      state.mode = "play";
      reveal();
      questEvent("explore", "dungeon", 1);
      toast("Entered " + (W.dungeon.name || "the dungeon"), 3);
      E.beep && E.beep(220, 0.16, "sawtooth");
    }

    function leaveDungeon() {
      if (state.map !== "dungeon") return;
      state.map = "overworld";
      var back = state.dungeonReturn || W.start;
      player().x = back.x;
      player().y = back.y + 1;
      state.cam.x = player().x;
      state.cam.y = player().y;
      state.mode = "play";
      toast("Back under the open sky");
    }

    function startDialogue(speaker, lines, after) {
      state.dialogue = { speaker: speaker, lines: lines.slice(), i: 0, after: after || null };
      state.mode = "dialogue";
    }

    function advanceDialogue() {
      var d = state.dialogue;
      if (!d) { state.mode = "play"; return; }
      d.i++;
      if (d.i >= d.lines.length) {
        var after = d.after;
        state.dialogue = null;
        state.mode = "play";
        if (after) after();
      }
    }

    function completeQuest(q) {
      var s = qstate(q);
      if (!s) return;
      s.state = "done";
      var p = player();
      p.gold += q.reward.gold;
      addXp(q.reward.xp);
      toast("Quest complete · +" + q.reward.gold + " gold · +" + q.reward.xp + " XP", 3.4);
      E.beep && E.beep(1040, 0.18, "triangle");
    }

    function interact() {
      if (state.mode === "dialogue") { advanceDialogue(); return; }
      if (state.mode === "shop") { state.mode = "play"; state.shop = null; return; }
      if (state.mode === "dead") { respawn(); return; }
      if (state.mode !== "play") return;

      if (state.map === "dungeon") {
        var entry = W.dungeonMap.entry;
        if (Math.hypot(player().x - entry.x, player().y - entry.y) < 1.4) {
          leaveDungeon();
        } else {
          toast("Find the stairs at the entrance to leave");
        }
        return;
      }

      var npc = nearestNpc();
      if (npc) {
        // Delivering a letter to this NPC advances that quest, even though the
        // quest belongs to someone else.
        var delivered = false;
        W.quests.forEach(function (dq) {
          if (delivered || dq.kind !== "deliver" || dq.target !== npc.id) return;
          var ds = qstate(dq);
          if (ds && ds.state === "active") {
            questEvent("deliver", npc.id, 1);
            startDialogue(npc.name, ["A letter, sealed with wax.", "I will read it tonight. Thank you."]);
            delivered = true;
          }
        });
        if (delivered) return;
        var q = npc.quest ? quest(npc.quest) : null;
        if (q) {
          var s = qstate(q);
          if (s && s.state === "ready") {
            completeQuest(q);
            startDialogue(npc.name, ["You did what the rest of us could not.",
              "Take this. The road is safer for it."]);
            return;
          }
          if (s && s.state === "offered") {
            startDialogue(npc.name, [q.title + ".", q.desc, "Will you take it?"], function () {
              var st = qstate(q);
              if (st && st.state === "offered") {
                st.state = "active";
                toast("Quest accepted · " + q.title);
                E.beep && E.beep(680, 0.08, "triangle");
              }
            });
            return;
          }
          if (q.kind === "deliver" && s && s.state === "active" && npc.id === q.target) {
            questEvent("deliver", npc.id, 1);
          }
          if (q.kind === "boss" && qstate(q).state === "active" && npc.id === q.giver) {
            startDialogue(npc.name, ["The " + theme.boss.replace(/^the /, "") + " waits in " + W.dungeon.name + ".",
              "Do not go alone. Or do — the choice is yours."]);
            return;
          }
        }
        var lines = npc.lines.length ? npc.lines : ["Well met, traveller."];
        if (npc.shop) {
          startDialogue(npc.name, lines, function () { openShop(npc); });
        } else {
          startDialogue(npc.name, lines);
        }
        return;
      }

      if (nearDungeon()) { enterDungeon(); return; }
      toast("Nothing here · E talks, F attacks");
    }

    function openShop(npc) {
      state.shop = {
        npc: npc, index: 0,
        items: [
          { name: "potion", price: 12, kind: "potion", note: "heal 12 HP" },
          { name: "tonic", price: 28, kind: "tonic", note: "full heal" },
          { name: "charm", price: 45, kind: "charm", note: "+5 max HP" }
        ]
      };
      state.mode = "shop";
    }

    function buy() {
      var s = state.shop;
      if (!s) return;
      var item = s.items[s.index], p = player();
      if (p.gold < item.price) { toast("Not enough gold"); E.beep && E.beep(140, 0.1, "square"); return; }
      p.gold -= item.price;
      if (item.kind === "potion") p.potions++;
      else if (item.kind === "tonic") p.hp = p.maxHp;
      else if (item.kind === "charm") { p.maxHp += 5; p.hp = p.maxHp; }
      toast("Bought " + item.name);
      E.beep && E.beep(880, 0.06, "triangle");
    }

    function usePotion() {
      var p = player();
      if (p.potions <= 0) { toast("No potions"); return; }
      if (p.hp >= p.maxHp) { toast("Already at full HP"); return; }
      p.potions--;
      p.hp = Math.min(p.maxHp, p.hp + 14);
      toast("Potion · HP " + p.hp + "/" + p.maxHp);
      E.beep && E.beep(720, 0.08, "sine");
    }

    function hurt(n) {
      var p = player();
      if (p.hurtT > 0) return;
      p.hp -= n;
      p.hurtT = 0.7;
      E.beep && E.beep(150, 0.1, "sawtooth");
      if (p.hp <= 0) {
        p.hp = 0;
        state.mode = "dead";
      }
    }

    function respawn() {
      var p = player();
      p.hp = p.maxHp;
      p.gold = Math.floor(p.gold * 0.8);
      state.map = "overworld";
      p.x = W.start.x; p.y = W.start.y;
      state.cam.x = p.x; state.cam.y = p.y;
      state.mode = "play";
      toast("You wake in " + (W.towns[0] ? W.towns[0].name : "town"));
    }

    function attack() {
      var p = player();
      if (p.attackCd > 0) return;
      p.attackCd = 0.34;
      p.attackT = 0.22;
      E.beep && E.beep(320, 0.05, "square");
      liveEnemies().forEach(function (e) {
        if (!entityAlive(e)) return;
        var dx = e.x - p.x, dy = e.y - p.y;
        if (Math.hypot(dx, dy) > 1.75) return;
        var dmg = 3 + p.level * 2 + Math.floor(Math.random() * 2);
        e.hp -= dmg;
        if (e.hp <= 0) {
          e.alive = false;
          state.defeated[e.id] = 1;
          state.kills++;
          addXp(e.boss ? 60 : 8);
          p.gold += e.boss ? 60 : 4;
          toast((e.boss ? theme.boss : e.type) + " defeated", e.boss ? 4 : 2);
          questEvent("kill", e.type, 1);
          if (e.boss) {
            questEvent("boss", "boss", 1);
            toast("The " + theme.boss.replace(/^the /, "") + " falls · the dungeon is quiet", 4.5);
          }
          E.beep && E.beep(e.boss ? 1200 : 520, 0.1, "triangle");
        } else {
          e.x += dx * 0.25; e.y += dy * 0.25;
          E.beep && E.beep(240, 0.04, "square");
        }
      });
    }

    function updateEnemies(dt) {
      var p = player();
      liveEnemies().forEach(function (e) {
        if (!entityAlive(e)) return;
        e.hurtT = Math.max(0, (e.hurtT || 0) - dt);
        var dx = p.x - e.x, dy = p.y - e.y;
        var d = Math.hypot(dx, dy);
        var aggro = e.boss ? 9 : 6.5;
        if (d < aggro && d > 0.01) {
          var sp = e.speed * dt;
          var nx = dx / d, ny = dy / d;
          move(e, nx, ny, sp);
          if (d < 0.85 && p.hurtT <= 0) hurt(e.damage);
        } else {
          e.wander = (e.wander || 0) - dt;
          if (e.wander <= 0) {
            e.wander = 1.4 + (e.id.length % 5) * 0.3;
            e.wx = (e.x + ((e.id.charCodeAt(1) % 3) - 1) * 1.5);
            e.wy = (e.y + ((e.id.charCodeAt(e.id.length - 1) % 3) - 1) * 1.5);
          }
          if (e.wx != null) {
            var wd = Math.hypot(e.wx - e.x, e.wy - e.y);
            if (wd > 0.2) move(e, (e.wx - e.x) / wd, (e.wy - e.y) / wd, e.speed * 0.3 * dt);
          }
        }
      });
    }

    function save(slot) {
      try {
        var p = player();
        var data = {
          version: 2, seed: W.seed, size: W.size, themeTitle: theme.title || "",
          map: state.map, play: state.play, time: state.time, kills: state.kills,
          player: {
            x: p.x, y: p.y, fx: p.fx, fy: p.fy, hp: p.hp, maxHp: p.maxHp,
            level: p.level, xp: p.xp, xpNext: p.xpNext, gold: p.gold,
            potions: p.potions, herbs: p.herbs || 0
          },
          quests: state.quests.map(function (s) { return { id: s.id, state: s.state, progress: s.progress }; }),
          defeated: state.defeated, taken: state.taken, explored: state.explored,
          dungeonReturn: state.dungeonReturn,
          bossAlive: !state.defeated.boss,
          at: now()
        };
        root.localStorage.setItem("toolrx.rpg2.save." + slot, JSON.stringify(data));
        state.lastSave = slot + " · " + new Date().toLocaleTimeString();
        toast("Saved to slot " + slot);
        return true;
      } catch (e) { toast("Could not save here"); return false; }
    }

    function slotInfo(slot) {
      try {
        var raw = root.localStorage.getItem("toolrx.rpg2.save." + slot);
        if (!raw) return null;
        var d = JSON.parse(raw);
        return {
          slot: slot, level: d.player ? d.player.level : 1,
          title: d.themeTitle || "RPG", gold: d.player ? d.player.gold : 0,
          play: Math.round(d.play || 0), at: d.at
        };
      } catch (e) { return null; }
    }

    function load(slot) {
      try {
        var raw = root.localStorage.getItem("toolrx.rpg2.save." + slot);
        if (!raw) { toast("Slot " + slot + " is empty"); return false; }
        var d = JSON.parse(raw);
        if (!d || !d.player) { toast("That save is unreadable"); return false; }
        if (d.seed !== W.seed) {
          W = root.toolrxWorldgen.generate({
            seed: d.seed, size: d.size || W.size, theme: W.theme
          });
          pal = W.palette || pal;
        }
        state.quests = d.quests || state.quests;
        state.defeated = d.defeated || {};
        state.taken = d.taken || {};
        state.explored = d.explored || {};
        if (mini) mini.dirty = true;
        state.dungeonReturn = d.dungeonReturn || null;
        state.map = d.map === "dungeon" ? "dungeon" : "overworld";
        state.play = d.play || 0;
        state.time = d.time || 0;
        state.kills = d.kills || 0;
        var p = player();
        for (var k in d.player) if (Object.prototype.hasOwnProperty.call(d.player, k)) p[k] = d.player[k];
        state.cam.x = p.x; state.cam.y = p.y;
        state.mode = "play";
        state.over = false;
        reveal();
        toast("Loaded slot " + slot + " · level " + p.level);
        return true;
      } catch (e) { toast("Could not load that save"); return false; }
    }

    function newWorld() {
      var seed = ((W.seed || 1) + 1) >>> 0;
      W = root.toolrxWorldgen.generate({ seed: seed, size: W.size, theme: W.theme });
      pal = W.palette || pal;
      state.map = "overworld";
      state.player.x = W.start.x;
      state.player.y = W.start.y;
      state.player.hp = state.player.maxHp;
      state.cam.x = state.player.x;
      state.cam.y = state.player.y;
      state.explored = {};
      if (mini) mini.dirty = true;
      state.defeated = {};
      state.taken = {};
      state.quests = W.quests.map(function (q) {
        return { id: q.id, state: q.state, progress: q.progress };
      });
      state.mode = "play";
      toast("New world · seed " + seed);
    }

    /* --------------------------------------------------------------- input */
    if (E.bind) {
      E.bind({
        up: ["ArrowUp", "w"], down: ["ArrowDown", "s"],
        left: ["ArrowLeft", "a"], right: ["ArrowRight", "d"],
        interact: [" ", "e", "Enter"], attack: ["f", "j"],
        inventory: ["i"], quests: ["q"], map: ["m"], pause: ["Escape"],
        slot1: ["1"], slot2: ["2"], slot3: ["3"]
      });
    }

    function menuItems() {
      return [
        "Resume", "Inventory", "Quest log", "World map",
        "Save slot 1", "Save slot 2", "Save slot 3",
        "Load slot 1", "Load slot 2", "Load slot 3", "New world", "Controls"
      ];
    }
    var MENU = menuItems();

    function menuChoose() {
      var pick = MENU[state.menu];
      if (pick === "Resume") state.mode = "play";
      else if (pick === "Inventory") state.mode = "inventory";
      else if (pick === "Quest log") state.mode = "quests";
      else if (pick === "World map") state.mode = "map";
      else if (/^Save slot/.test(pick)) save(parseInt(pick.slice(-1), 10));
      else if (/^Load slot/.test(pick)) load(parseInt(pick.slice(-1), 10));
      else if (pick === "New world") newWorld();
      else if (pick === "Controls") { state.mode = "help"; }
      else state.mode = "play";
    }

    function handleInput(dt) {
      if (tap("pause")) {
        if (state.mode === "play") { state.mode = "pause"; state.menu = 0; }
        else if (state.mode === "pause") state.mode = "play";
        else if (state.mode === "help") state.mode = "pause";
        else if (state.mode === "inventory") state.mode = "play";
        else if (state.mode === "quests") state.mode = "play";
        else if (state.mode === "map") state.mode = "play";
      }

      if (state.mode === "pause") {
        if (tap("up")) { state.menu = (state.menu + MENU.length - 1) % MENU.length; }
        if (tap("down")) { state.menu = (state.menu + 1) % MENU.length; }
        if (tap("interact")) menuChoose();
        return;
      }
      if (state.mode === "help") {
        if (tap("interact") || tap("pause")) state.mode = "pause";
        return;
      }
      if (state.mode === "dialogue") {
        if (tap("interact") || tap("attack")) advanceDialogue();
        return;
      }
      if (state.mode === "shop") {
        if (tap("up")) state.shop.index = (state.shop.index + state.shop.items.length - 1) % state.shop.items.length;
        if (tap("down")) state.shop.index = (state.shop.index + 1) % state.shop.items.length;
        if (tap("interact")) buy();
        if (tap("attack")) { state.mode = "play"; state.shop = null; }
        return;
      }
      if (state.mode === "inventory") {
        if (tap("interact")) usePotion();
        if (tap("inventory")) state.mode = "play";
        return;
      }
      if (state.mode === "quests") {
        if (tap("quests")) state.mode = "play";
        return;
      }
      if (state.mode === "map") {
        if (tap("map")) state.mode = "play";
        return;
      }
      if (state.mode === "dead") {
        if (tap("interact") || tap("attack")) respawn();
        return;
      }
      if (state.mode !== "play") return;

      if (tap("interact")) interact();
      if (tap("attack")) attack();
      if (tap("inventory")) state.mode = "inventory";
      if (tap("quests")) state.mode = "quests";
      if (tap("map")) state.mode = "map";

      var p = player();
      var dx = (held("right") ? 1 : 0) - (held("left") ? 1 : 0);
      var dy = (held("down") ? 1 : 0) - (held("up") ? 1 : 0);
      if (dx || dy) {
        // Screen-space to iso-space: right = +x,-y; down = +x,+y.
        var mx = dx - dy, my = dx + dy;
        var len = Math.hypot(mx, my) || 1;
        mx /= len; my /= len;
        move(p, mx, my, 3.4 * dt);
        p.fx = mx; p.fy = my;
        p.walk += dt * 9;
        reveal();
        pickupNear();
        var nd = nearDungeon();
        if (nd && !state.nearD) toast("E enter " + (W.dungeon.name || "the dungeon"), 2.2);
        state.nearD = nd;
      } else {
        p.walk += dt * 2;
        state.nearD = false;
      }
    }

    function update(dt) {
      if (!dt) dt = 1 / 60;
      if (dt > 0.05) dt = 0.05;
      state.time += dt;
      if (state.mode === "play") state.play += dt;
      state.player.attackT = Math.max(0, state.player.attackT - dt);
      state.player.attackCd = Math.max(0, state.player.attackCd - dt);
      state.player.hurtT = Math.max(0, state.player.hurtT - dt);
      state.toastT = Math.max(0, state.toastT - dt);

      handleInput(dt);

      if (state.mode === "play") {
        updateEnemies(dt);
        var p = state.player;
        var k = Math.min(1, dt * 7);
        state.cam.x += (p.x - state.cam.x) * k;
        state.cam.y += (p.y - state.cam.y) * k;
      }
      if (state.toastT === 0) state.toast = "";
    }

    /* --------------------------------------------------------------- draw */
    /* Static terrain is baked once per map into an offscreen canvas. Drawing
     * thousands of diamonds every frame costs more than the rest of the game
     * combined; one blit keeps the RPG at frame rate. */
    var bake = null, terrain = null;

    function iso(x, y) {
      if (bake) {
        return { x: (x - y) * (TW / 2) + bake.cx, y: (x + y) * (TH / 2) + bake.cy };
      }
      return {
        x: (x - y - (state.cam.x - state.cam.y)) * (TW / 2) + viewW / 2,
        y: (x + y - (state.cam.x + state.cam.y)) * (TH / 2) + viewH / 2
      };
    }

    function diamond(g, p, fill, stroke) {
      g.beginPath();
      g.moveTo(p.x, p.y - TH / 2);
      g.lineTo(p.x + TW / 2, p.y);
      g.lineTo(p.x, p.y + TH / 2);
      g.lineTo(p.x - TW / 2, p.y);
      g.closePath();
      g.fillStyle = fill;
      g.fill();
      if (stroke) { g.strokeStyle = stroke; g.lineWidth = 1; g.stroke(); }
    }

    function tileColor(tile) {
      switch (tile) {
        case T.DEEP: return pal.deep;
        case T.SHALLOW: return pal.shallow;
        case T.SAND: return pal.sand;
        case T.GRASS: return pal.grass;
        case T.FOREST: return pal.forest;
        case T.HILL: return pal.hill;
        case T.MOUNTAIN: return pal.mountain;
        case T.SNOW: return pal.snow;
        case T.ROAD: return pal.road;
        case T.TOWN: return pal.town;
        case T.BRIDGE: return pal.bridge;
        case T.FLOOR: return pal.floor;
        case T.WALL: return pal.wall;
        default: return pal.grass;
      }
    }

    function elevation(tile) {
      if (tile === T.HILL) return 5;
      if (tile === T.MOUNTAIN) return 15;
      if (tile === T.FOREST) return 2;
      if (tile === T.WALL) return 12;
      return 0;
    }

    function prism(g, x, y, h, color, topColor) {
      var p = iso(x, y);
      if (h <= 0) { diamond(g, p, color); return; }
      var top = { x: p.x, y: p.y - h };
      // south-west and south-east faces
      g.beginPath();
      g.moveTo(p.x - TW / 2, p.y);
      g.lineTo(p.x, p.y + TH / 2);
      g.lineTo(p.x, p.y + TH / 2 - h);
      g.lineTo(p.x - TW / 2, p.y - h);
      g.closePath();
      g.fillStyle = shade(color, 0.72);
      g.fill();
      g.beginPath();
      g.moveTo(p.x + TW / 2, p.y);
      g.lineTo(p.x, p.y + TH / 2);
      g.lineTo(p.x, p.y + TH / 2 - h);
      g.lineTo(p.x + TW / 2, p.y - h);
      g.closePath();
      g.fillStyle = shade(color, 0.86);
      g.fill();
      diamond(g, top, topColor || shade(color, 1.12));
    }

    function shade(c, mul) {
      var s = String(c || "#445566");
      if (s[0] === "#") s = s.slice(1);
      if (s.length === 3) s = s[0] + s[0] + s[1] + s[1] + s[2] + s[2];
      var n = parseInt(s, 16);
      if (!isFinite(n)) return c;
      var r = clamp(Math.round((n >> 16 & 255) * mul), 0, 255);
      var gg = clamp(Math.round((n >> 8 & 255) * mul), 0, 255);
      var b = clamp(Math.round((n & 255) * mul), 0, 255);
      return "rgb(" + r + "," + gg + "," + b + ")";
    }

    /* Visible tile window around the camera. The isometric footprint of a
     * 960x540 view is about 30 tiles in each axis, so draw that box and skip
     * anything whose diamond lands outside the screen. */
    var VIEW_R = 30;
    function bounds(m) {
      if (bake) return { minX: 0, minY: 0, maxX: m.w - 1, maxY: m.h - 1 };
      return {
        minX: Math.max(0, Math.floor(state.cam.x) - VIEW_R),
        maxX: Math.min(m.w - 1, Math.floor(state.cam.x) + VIEW_R),
        minY: Math.max(0, Math.floor(state.cam.y) - VIEW_R),
        maxY: Math.min(m.h - 1, Math.floor(state.cam.y) + VIEW_R)
      };
    }
    function onScreen(p) {
      if (bake) return true;
      return p.x > -TW * 2 && p.x < viewW + TW * 2
        && p.y > -TH * 5 && p.y < viewH + TH * 8;
    }

    function terrainKey() {
      var m = onMap();
      return state.map + "|" + (W.seed >>> 0) + "|" + m.w + "x" + m.h;
    }

    function ensureTerrain(doc) {
      var key = terrainKey();
      if (terrain && terrain.key === key) return terrain;
      terrain = null;
      if (!doc || !doc.createElement) return null;
      var m = onMap();
      var cw = Math.ceil((m.w + m.h) * TW / 2) + TW * 2;
      var ch = Math.ceil((m.w + m.h) * TH / 2) + 200;
      var cv = doc.createElement("canvas");
      cv.width = cw;
      cv.height = ch;
      var c = cv.getContext("2d");
      if (!c) return null;
      bake = { cx: cw / 2, cy: 100 };
      drawGround(c);
      drawDecor(c);
      bake = null;
      terrain = { key: key, canvas: cv, cx: cw / 2, cy: 100 };
      return terrain;
    }

    /* The sky and vignette never change, but evaluating a full-screen
     * gradient every frame is by far the most expensive thing in the game on
     * software rasterisers. Paint them once into two canvases and blit. */
    var backdrops = null;
    function backdropKey() {
      return ((canvas && canvas.width) || viewW) + "x"
        + ((canvas && canvas.height) || viewH) + "|"
        + viewW + "x" + viewH + "|" + (pal.ink || "");
    }
    function ensureBackdrops(doc) {
      var key = backdropKey();
      if (backdrops && backdrops.key === key) return backdrops;
      backdrops = null;
      if (!doc || !doc.createElement) return null;
      var pw = (canvas && canvas.width) || viewW;
      var ph = (canvas && canvas.height) || viewH;
      function make(paint) {
        var c = doc.createElement("canvas");
        c.width = pw;
        c.height = ph;
        var x = c.getContext("2d");
        if (!x) return null;
        paint(x);
        return c;
      }
      var sky = make(function (x) {
        // Deep water, not sky: the island sits in an ocean.
        var grad = x.createLinearGradient(0, 0, 0, ph);
        grad.addColorStop(0, shade(pal.deep || "#0d2233", 1.18));
        grad.addColorStop(1, shade(pal.deep || "#0d2233", 0.82));
        x.fillStyle = grad;
        x.fillRect(0, 0, pw, ph);
      });
      var vig = make(function (x) {
        var grad = x.createRadialGradient(pw / 2, ph / 2, ph * 0.3,
          pw / 2, ph / 2, ph * 0.8);
        grad.addColorStop(0, "rgba(0,0,0,0)");
        grad.addColorStop(1, "rgba(0,0,0,.42)");
        x.fillStyle = grad;
        x.fillRect(0, 0, pw, ph);
      });
      if (!sky || !vig) return null;
      backdrops = { key: key, sky: sky, vig: vig };
      return backdrops;
    }

    function drawGround(g) {
      var m = onMap();
      var b = bounds(m), x, y, t, p;
      for (y = b.minY; y <= b.maxY; y++) {
        for (x = b.minX; x <= b.maxX; x++) {
          t = m.tiles[y][x];
          if (t === T.WALL) continue;
          p = iso(x, y);
          if (!onScreen(p)) continue;
          prism(g, x, y, elevation(t), tileColor(t));
        }
      }
      // walls after floors so they sit above their neighbours
      for (y = b.minY; y <= b.maxY; y++) {
        for (x = b.minX; x <= b.maxX; x++) {
          if (m.tiles[y][x] !== T.WALL) continue;
          p = iso(x, y);
          if (!onScreen(p)) continue;
          prism(g, x, y, 16, pal.wall, shade(pal.wall, 1.15));
        }
      }
    }

    function drawDecor(g) {
      var m = onMap();
      var b = bounds(m);
      var trees = [];
      for (var y = b.minY; y <= b.maxY; y++) {
        for (var x = b.minX; x <= b.maxX; x++) {
          if (m.tiles[y][x] !== T.FOREST) continue;
          if ((x * 7 + y * 13) % 3 !== 0) continue;
          if (!onScreen(iso(x, y))) continue;
          trees.push([x, y]);
        }
      }
      trees.forEach(function (xy) {
        var p = iso(xy[0], xy[1]);
        var top = p.y - 2;
        g.fillStyle = shade(pal.tree, 0.55);
        g.fillRect(p.x - 1.5, top - 5, 3, 7);
        g.beginPath();
        g.arc(p.x, top - 12, 8, 0, Math.PI * 2);
        g.fillStyle = pal.tree;
        g.fill();
        g.beginPath();
        g.arc(p.x - 4, top - 9, 5, 0, Math.PI * 2);
        g.fillStyle = shade(pal.tree, 1.18);
        g.fill();
      });

      if (state.map !== "overworld") return;
      W.towns.forEach(function (town) {
        town.buildings.forEach(function (b) {
          var p = iso(b.x + b.w / 2 - 0.5, b.y + b.d / 2 - 0.5);
          if (!onScreen(p)) return;
          var h = 16;
          var base = { x: p.x, y: p.y };
          g.beginPath();
          g.moveTo(base.x - TW / 2 * b.w, base.y);
          g.lineTo(base.x, base.y + TH / 2 * b.d);
          g.lineTo(base.x, base.y + TH / 2 * b.d - h * b.d);
          g.lineTo(base.x - TW / 2 * b.w, base.y - h * b.d);
          g.closePath();
          g.fillStyle = shade(pal.town, 0.7);
          g.fill();
          g.beginPath();
          g.moveTo(base.x + TW / 2 * b.w, base.y);
          g.lineTo(base.x, base.y + TH / 2 * b.d);
          g.lineTo(base.x, base.y + TH / 2 * b.d - h * b.d);
          g.lineTo(base.x + TW / 2 * b.w, base.y - h * b.d);
          g.closePath();
          g.fillStyle = shade(pal.town, 0.84);
          g.fill();
          var top = { x: base.x, y: base.y - h * b.d };
          diamond(g, { x: top.x, y: top.y - 2 }, pal.roof);
          g.fillStyle = shade(pal.roof, 1.18);
          g.fillRect(top.x - 5, top.y - 10, 10, 8);
          g.fillStyle = "#2b1c14";
          g.fillRect(base.x - 3, base.y + TH / 2 * b.d - 8, 6, 8);
        });
        var tp = iso(town.x, town.y);
        if (bake || (tp.x > -100 && tp.x < viewW + 100 && tp.y > -40 && tp.y < viewH + 60)) {
          g.globalAlpha = 0.72;
          g.font = "600 12px ui-sans-serif, system-ui, sans-serif";
          g.textAlign = "center";
          g.fillStyle = "#f8fafc";
          g.fillText(town.name, tp.x, tp.y - 34);
          g.globalAlpha = 1;
        }
      });

      // dungeon entrance
      var dp = iso(W.dungeon.x, W.dungeon.y);
      if (bake || (dp.x > -60 && dp.x < viewW + 60 && dp.y > -60 && dp.y < viewH + 60)) {
        g.beginPath();
        g.ellipse(dp.x, dp.y, 18, 9, 0, 0, Math.PI * 2);
        g.fillStyle = "#0a0f18";
        g.fill();
        g.beginPath();
        g.arc(dp.x, dp.y - 7, 12, Math.PI, 0);
        g.fillStyle = pal.wall;
        g.fill();
        g.font = "600 11px ui-sans-serif, system-ui, sans-serif";
        g.textAlign = "center";
        g.fillStyle = "#fbbf24";
        g.fillText("E enter", dp.x, dp.y - 24);
      }
    }

    function drawActor(g, a, kind) {
      var p = iso(a.x, a.y);
      if (p.x < -40 || p.x > viewW + 40 || p.y < -40 || p.y > viewH + 40) return;
      var lift = kind === "player" ? Math.sin(a.walk || 0) * 1.4 : 0;
      g.beginPath();
      g.ellipse(p.x, p.y + 3, 9, 4, 0, 0, Math.PI * 2);
      g.fillStyle = "rgba(2,6,20,.42)";
      g.fill();
      var body = a.color || "#22d3ee";
      if (kind === "npc") body = a.color || "#93c5fd";
      if (kind === "enemy") body = (a.hurtT && a.hurtT > 0) ? "#f8fafc" : (a.color || "#a855f7");
      var size = a.boss ? 1.5 : 1;
      g.fillStyle = body;
      g.beginPath();
      g.roundRect
        ? g.roundRect(p.x - 7 * size, p.y - 20 * size - lift, 14 * size, 20 * size, 5)
        : g.rect(p.x - 7 * size, p.y - 20 * size - lift, 14 * size, 20 * size);
      g.fill();
      g.beginPath();
      g.arc(p.x, p.y - 22 * size - lift, 6 * size, 0, Math.PI * 2);
      g.fillStyle = shade(body, 1.14);
      g.fill();
      if (kind === "player") {
        g.fillStyle = "#0b1020";
        g.fillRect(p.x + (a.fx > 0 ? 1 : -4), p.y - 25 - lift, 3, 2);
        if (state.player.attackT > 0) {
          g.beginPath();
          g.moveTo(p.x + a.fx * 8, p.y - 14);
          g.lineTo(p.x + a.fx * 22, p.y - 22);
          g.strokeStyle = "#f8fafc";
          g.lineWidth = 3;
          g.stroke();
        }
      }
      if (kind === "npc") {
        var q = a.quest ? quest(a.quest) : null;
        var s = q ? qstate(q) : null;
        var mark = s && s.state === "ready" ? "?"
          : s && s.state === "offered" ? "!" : "";
        if (mark) {
          g.fillStyle = mark === "?" ? "#34d399" : "#fbbf24";
          g.font = "800 12px ui-sans-serif, system-ui, sans-serif";
          g.textAlign = "center";
          g.fillText(mark, p.x, p.y - 32 * size - lift);
        }
      }
      if (kind === "enemy" && a.hp < a.maxHp) {
        g.fillStyle = "#0b1020";
        g.fillRect(p.x - 12, p.y - 34 * size, 24, 3);
        g.fillStyle = a.boss ? "#ef4444" : "#f97316";
        g.fillRect(p.x - 12, p.y - 34 * size, 24 * Math.max(0, a.hp / a.maxHp), 3);
      }
    }

    function drawActors(g) {
      var list = [];
      if (state.map === "overworld") {
        W.npcs.forEach(function (n) { list.push({ a: n, kind: "npc" }); });
        W.pickups.forEach(function (it) {
          if (!state.taken[it.id]) list.push({ a: it, kind: "pickup" });
        });
        W.enemies.forEach(function (e) {
          if (entityAlive(e)) list.push({ a: e, kind: "enemy" });
        });
      } else {
        var dm = W.dungeonMap;
        if (entityAlive(dm.boss)) list.push({ a: dm.boss, kind: "enemy" });
        dm.minions.forEach(function (e) { if (entityAlive(e)) list.push({ a: e, kind: "enemy" }); });
      }
      list.push({ a: player(), kind: "player" });
      list.sort(function (x, y) { return (x.a.x + x.a.y) - (y.a.x + y.a.y); });
      list.forEach(function (it) {
        if (it.kind === "pickup") {
          var p = iso(it.a.x, it.a.y);
          var bob = Math.sin(state.time * 3 + it.a.x) * 2;
          g.fillStyle = it.a.kind === "herb" ? "#34d399" : "#fbbf24";
          g.beginPath();
          g.arc(p.x, p.y - 8 + bob, it.a.kind === "herb" ? 4 : 5, 0, Math.PI * 2);
          g.fill();
          g.fillStyle = "rgba(255,255,255,.6)";
          g.fillRect(p.x - 1, p.y - 9 + bob, 2, 2);
        } else {
          drawActor(g, it.a, it.kind);
        }
      });
    }

    function panel(g, x, y, w, h) {
      g.fillStyle = "rgba(8,13,26,.92)";
      g.strokeStyle = "rgba(148,163,184,.4)";
      g.lineWidth = 1.5;
      if (g.roundRect) {
        g.beginPath();
        g.roundRect(x, y, w, h, 14);
        g.fill();
        g.stroke();
      } else {
        g.fillRect(x, y, w, h);
        g.strokeRect(x, y, w, h);
      }
    }

    function wrap(g, text, x, y, maxW, lh) {
      var words = String(text || "").split(/\s+/);
      var line = "", cy = y;
      for (var i = 0; i < words.length; i++) {
        var test = line ? line + " " + words[i] : words[i];
        if (g.measureText(test).width > maxW && line) {
          g.fillText(line, x, cy);
          line = words[i];
          cy += lh;
        } else line = test;
      }
      if (line) g.fillText(line, x, cy);
    }

    function bar(g, x, y, w, h, frac, color, bg) {
      g.fillStyle = bg || "rgba(15,23,42,.85)";
      g.fillRect(x, y, w, h);
      g.fillStyle = color;
      g.fillRect(x, y, Math.max(0, Math.min(1, frac)) * w, h);
    }

    function drawHud(g) {
      var p = player();
      var m = onMap();
      g.fillStyle = "rgba(6,10,22,.55)";
      g.fillRect(0, 0, viewW, 58);

      g.font = "700 13px ui-sans-serif, system-ui, sans-serif";
      g.textAlign = "left";
      g.fillStyle = "#e2e8f0";
      g.fillText("LV " + p.level, 16, 22);
      bar(g, 62, 12, 150, 8, p.hp / p.maxHp, "#ef4444");
      g.fillStyle = "#f8fafc";
      g.font = "600 11px ui-monospace, monospace";
      g.fillText(Math.max(0, Math.ceil(p.hp)) + "/" + p.maxHp, 62, 34);
      bar(g, 160, 25, 88, 5, p.xp / p.xpNext, "#34d399");
      g.fillStyle = "#fbbf24";
      g.font = "700 12px ui-sans-serif, system-ui, sans-serif";
      g.fillText("◆ " + p.gold, 264, 22);
      g.fillStyle = "#a78bfa";
      g.fillText("⚗ " + p.potions, 264, 40);

      // quest tracker
      var active = W.quests.filter(function (q) {
        var s = qstate(q);
        return s && (s.state === "active" || s.state === "ready");
      }).slice(0, 3);
      if (active.length) {
        g.font = "600 11px ui-sans-serif, system-ui, sans-serif";
        active.forEach(function (q, i) {
          var s = qstate(q);
          var txt = q.title + (s.state === "ready" ? " · return" : " · " + s.progress + "/" + q.need);
          g.fillStyle = s.state === "ready" ? "#fbbf24" : "#94a3b8";
          g.fillText(txt, 16, 76 + i * 17);
        });
      }

      drawMinimap(g, viewW - 166, 12, 154);

      g.font = "600 11px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "rgba(226,232,240,.62)";
      g.textAlign = "center";
      g.fillText("E talk · F attack · I bag · Q quests · M map · Esc menu",
        viewW / 2, viewH - 12);
    }

    function minimapColor(t) {
      switch (t) {
        case T.DEEP: return "#163247";
        case T.SHALLOW: return "#25506b";
        case T.SAND: return "#b9a069";
        case T.GRASS: return "#3c6446";
        case T.FOREST: return "#2c513a";
        case T.HILL: return "#6b6350";
        case T.MOUNTAIN: return "#626b7d";
        case T.SNOW: return "#dbe6ef";
        case T.ROAD: return "#a08a5b";
        case T.TOWN: return "#c9a86a";
        case T.BRIDGE: return "#8a6b45";
        case T.FLOOR: return "#3b4252";
        case T.WALL: return "#1e2433";
        default: return "#3c6446";
      }
    }

    var mini = { key: "", canvas: null, dirty: true };

    function miniKey() {
      var m = onMap();
      return state.map + "|" + (W.seed >>> 0) + "|" + m.w + "x" + m.h;
    }

    function buildMini(inner) {
      var doc = canvas && canvas.ownerDocument
        || (typeof document !== "undefined" ? document : null);
      if (!doc || !doc.createElement) return null;
      if (!mini.canvas || mini.canvas.width !== inner || mini.canvas.height !== inner) {
        mini.canvas = doc.createElement("canvas");
        mini.canvas.width = inner;
        mini.canvas.height = inner;
      }
      var c = mini.canvas.getContext("2d");
      if (!c) return null;
      c.clearRect(0, 0, inner, inner);
      c.imageSmoothingEnabled = false;
      var m = onMap();
      var prefix = state.map === "dungeon" ? "d" : "o";
      for (var ty = 0; ty < m.h; ty++) {
        var y0 = Math.floor(ty * inner / m.h);
        var y1 = Math.floor((ty + 1) * inner / m.h);
        for (var tx = 0; tx < m.w; tx++) {
          if (!state.explored[prefix + tx + "," + ty]) continue;
          var x0 = Math.floor(tx * inner / m.w);
          var x1 = Math.floor((tx + 1) * inner / m.w);
          c.fillStyle = minimapColor(m.tiles[ty][tx]);
          c.fillRect(x0, y0, Math.max(1, x1 - x0), Math.max(1, y1 - y0));
        }
      }
      mini.dirty = false;
      return mini.canvas;
    }

    function drawMinimap(g, x, y, size) {
      var m = onMap();
      panel(g, x, y, size, size);
      var inner = size - 12;
      var scale = inner / m.w;
      var ox = x + 6, oy = y + 6;
      g.save();
      g.beginPath();
      g.rect(ox, oy, inner, inner);
      g.clip();
      var key = miniKey();
      if (mini.key !== key) { mini.key = key; mini.dirty = true; }
      var img = mini.dirty ? buildMini(inner) : mini.canvas;
      if (img) {
        g.drawImage(img, ox, oy, inner, inner);
      } else {
        var prefix = state.map === "dungeon" ? "d" : "o";
        for (var ty = 0; ty < m.h; ty++) {
          for (var tx = 0; tx < m.w; tx++) {
            if (!state.explored[prefix + tx + "," + ty]) continue;
            g.fillStyle = minimapColor(m.tiles[ty][tx]);
            g.fillRect(ox + tx * scale, oy + ty * scale, Math.ceil(scale), Math.ceil(scale));
          }
        }
      }
      if (state.map === "overworld") {
        W.towns.forEach(function (t) {
          g.fillStyle = "#fbbf24";
          g.fillRect(ox + t.x * scale - 1, oy + t.y * scale - 1, 3, 3);
        });
        if (state.explored["o" + W.dungeon.x + "," + W.dungeon.y]) {
          g.fillStyle = "#ef4444";
          g.fillRect(ox + W.dungeon.x * scale - 1.5, oy + W.dungeon.y * scale - 1.5, 3, 3);
        }
      }
      var p = player();
      g.fillStyle = "#f8fafc";
      g.fillRect(ox + p.x * scale - 1.5, oy + p.y * scale - 1.5, 3.5, 3.5);
      g.restore();
      g.font = "700 9px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "rgba(226,232,240,.7)";
      g.textAlign = "center";
      g.fillText(state.map === "dungeon" ? "BARROW" : "WORLD", x + size / 2, y + size - 1);
    }

    function drawDialogue(g) {
      var d = state.dialogue;
      if (!d) return;
      var w = viewW - 120, h = 116, x = 60, y = viewH - h - 26;
      panel(g, x, y, w, h);
      g.textAlign = "left";
      g.font = "700 14px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#fbbf24";
      g.fillText(d.speaker, x + 18, y + 26);
      g.font = "500 14px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#e2e8f0";
      wrap(g, d.lines[d.i] || "…", x + 18, y + 52, w - 36, 20);
      g.font = "600 11px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "rgba(148,163,184,.9)";
      g.textAlign = "right";
      g.fillText(d.i < d.lines.length - 1 ? "space ▸" : "space ▸ close", x + w - 16, y + h - 12);
    }

    function drawShop(g) {
      var s = state.shop;
      if (!s) return;
      var w = 420, h = 240, x = (viewW - w) / 2, y = (viewH - h) / 2;
      panel(g, x, y, w, h);
      g.textAlign = "left";
      g.font = "700 15px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#fbbf24";
      g.fillText(s.npc.name + " · wares", x + 18, y + 28);
      g.font = "600 12px ui-monospace, monospace";
      g.fillStyle = "#e2e8f0";
      g.fillText("gold " + player().gold, x + w - 100, y + 28);
      s.items.forEach(function (it, i) {
        var ly = y + 58 + i * 38;
        if (i === s.index) {
          g.fillStyle = "rgba(251,191,36,.14)";
          g.fillRect(x + 12, ly - 20, w - 24, 30);
        }
        g.font = "600 13px ui-sans-serif, system-ui, sans-serif";
        g.fillStyle = "#f8fafc";
        g.fillText(it.name, x + 24, ly);
        g.font = "500 11px ui-sans-serif, system-ui, sans-serif";
        g.fillStyle = "#94a3b8";
        g.fillText(it.note, x + 100, ly);
        g.fillStyle = "#fbbf24";
        g.textAlign = "right";
        g.fillText(it.price + "g", x + w - 24, ly);
        g.textAlign = "left";
      });
      g.font = "600 11px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "rgba(148,163,184,.9)";
      g.fillText("↑↓ choose · space buy · F close", x + 18, y + h - 14);
    }

    function drawInventory(g) {
      var w = 380, h = 220, x = (viewW - w) / 2, y = (viewH - h) / 2;
      panel(g, x, y, w, h);
      g.textAlign = "left";
      g.font = "700 15px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#fbbf24";
      g.fillText("Satchel", x + 18, y + 28);
      g.font = "500 13px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#e2e8f0";
      var p = player();
      g.fillText("potions × " + p.potions, x + 24, y + 62);
      g.fillText("herbs × " + (p.herbs || 0), x + 24, y + 88);
      g.fillText("gold × " + p.gold, x + 24, y + 114);
      g.fillText("kills × " + state.kills, x + 24, y + 140);
      g.font = "600 11px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "rgba(148,163,184,.9)";
      g.fillText("space drink a potion · I close", x + 18, y + h - 14);
    }

    function drawQuests(g) {
      var w = 560, h = 330, x = (viewW - w) / 2, y = (viewH - h) / 2;
      panel(g, x, y, w, h);
      g.textAlign = "left";
      g.font = "700 15px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#fbbf24";
      g.fillText("Quest log", x + 18, y + 28);
      W.quests.forEach(function (q, i) {
        var s = qstate(q);
        var ly = y + 58 + i * 42;
        g.font = "700 12.5px ui-sans-serif, system-ui, sans-serif";
        g.fillStyle = s.state === "done" ? "#34d399" : s.state === "ready" ? "#fbbf24" : "#e2e8f0";
        g.fillText(q.title, x + 24, ly);
        g.font = "500 11px ui-sans-serif, system-ui, sans-serif";
        g.fillStyle = "#94a3b8";
        var meta = s.state === "offered" ? "not started · talk to " + npcName(q.giver)
          : s.state === "done" ? "complete"
            : s.state === "ready" ? "return to " + npcName(q.giver)
              : s.progress + " / " + q.need;
        g.fillText(meta, x + 24, ly + 16);
      });
      g.font = "600 11px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "rgba(148,163,184,.9)";
      g.fillText("Q close", x + 18, y + h - 14);
    }

    function drawMap(g) {
      var m = onMap();
      var size = Math.min(viewW, viewH) - 100;
      var x = (viewW - size) / 2, y = (viewH - size) / 2;
      panel(g, x, y, size + 40, size + 40);
      var ox = x + 20, oy = y + 20;
      var scale = size / m.w;
      g.save();
      g.beginPath();
      g.rect(ox, oy, size, size);
      g.clip();
      var prefix = state.map === "dungeon" ? "d" : "o";
      for (var ty = 0; ty < m.h; ty++) {
        for (var tx = 0; tx < m.w; tx++) {
          if (!state.explored[prefix + tx + "," + ty]) continue;
          g.fillStyle = minimapColor(m.tiles[ty][tx]);
          g.fillRect(ox + tx * scale, oy + ty * scale, Math.ceil(scale), Math.ceil(scale));
        }
      }
      if (state.map === "overworld") {
        W.towns.forEach(function (t) {
          g.fillStyle = "#fbbf24";
          g.fillRect(ox + t.x * scale - 2, oy + t.y * scale - 2, 4, 4);
          g.font = "600 10px ui-sans-serif, system-ui, sans-serif";
          g.fillStyle = "#f8fafc";
          g.textAlign = "left";
          g.fillText(t.name, ox + t.x * scale + 5, oy + t.y * scale + 3);
        });
        g.fillStyle = "#ef4444";
        g.fillRect(ox + W.dungeon.x * scale - 2, oy + W.dungeon.y * scale - 2, 4, 4);
      }
      var p = player();
      g.fillStyle = "#22d3ee";
      g.fillRect(ox + p.x * scale - 2, oy + p.y * scale - 2, 4, 4);
      g.restore();
      g.font = "600 11px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "rgba(148,163,184,.9)";
      g.textAlign = "center";
      g.fillText("M close · explored ground only", viewW / 2, y + size + 30);
    }

    function drawPause(g) {
      var w = 360, h = 350, x = (viewW - w) / 2, y = (viewH - h) / 2;
      panel(g, x, y, w, h);
      g.textAlign = "left";
      g.font = "700 16px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#fbbf24";
      g.fillText("Paused", x + 20, y + 30);
      MENU.forEach(function (item, i) {
        var ly = y + 62 + i * 30;
        if (i === state.menu) {
          g.fillStyle = "rgba(34,211,238,.14)";
          g.fillRect(x + 12, ly - 18, w - 24, 26);
          g.fillStyle = "#22d3ee";
          g.fillText("▸", x + 20, ly);
        }
        g.font = "600 13px ui-sans-serif, system-ui, sans-serif";
        g.fillStyle = i === state.menu ? "#f8fafc" : "#cbd5e1";
        var label = item;
        if (/slot/.test(item)) {
          var info = slotInfo(parseInt(item.slice(-1), 10));
          if (info) label += " · L" + info.level + " · " + info.gold + "g";
          else label += " · empty";
        }
        g.fillText(label, x + 40, ly);
      });
      g.font = "600 10.5px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "rgba(148,163,184,.9)";
      g.fillText("↑↓ · space · Esc", x + 20, y + h - 14);
    }

    function drawHelp(g) {
      var w = 560, h = 300, x = (viewW - w) / 2, y = (viewH - h) / 2;
      panel(g, x, y, w, h);
      g.textAlign = "left";
      g.font = "700 16px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#fbbf24";
      g.fillText("Controls", x + 20, y + 30);
      var lines = [
        "Move: WASD or arrow keys",
        "Talk / enter: space or E",
        "Attack: F or J",
        "Bag: I · Quests: Q · Map: M",
        "Pause, save, load: Esc",
        "Touch: left pad moves, A talks, B attacks"
      ];
      g.font = "500 13px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#e2e8f0";
      lines.forEach(function (line, i) { g.fillText(line, x + 24, y + 66 + i * 26); });
      g.font = "600 11px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "rgba(148,163,184,.9)";
      g.fillText("space / Esc back", x + 20, y + h - 14);
    }

    function drawDead(g) {
      g.fillStyle = "rgba(10,4,8,.72)";
      g.fillRect(0, 0, viewW, viewH);
      g.textAlign = "center";
      g.font = "800 34px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#f87171";
      g.fillText("You fell", viewW / 2, viewH / 2 - 20);
      g.font = "500 14px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#e2e8f0";
      g.fillText("space wakes you in " + (W.towns[0] ? W.towns[0].name : "town") + " · 20% gold lost",
        viewW / 2, viewH / 2 + 16);
    }

    function drawTouch(g) {
      if (!state.touch) return;
      var cx = 92, cy = viewH - 92, r = 62;
      g.globalAlpha = 0.32;
      g.fillStyle = "#e2e8f0";
      g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2); g.fill();
      g.globalAlpha = 0.8;
      g.font = "700 18px ui-sans-serif, system-ui, sans-serif";
      g.fillStyle = "#0b1020";
      g.textAlign = "center";
      g.fillText("▲", cx, cy - 26);
      g.fillText("▼", cx, cy + 34);
      g.fillText("◀", cx - 34, cy + 6);
      g.fillText("▶", cx + 34, cy + 6);

      g.globalAlpha = 0.4;
      g.fillStyle = "#22d3ee";
      g.beginPath(); g.arc(viewW - 150, viewH - 96, 32, 0, Math.PI * 2); g.fill();
      g.fillStyle = "#fbbf24";
      g.beginPath(); g.arc(viewW - 78, viewH - 60, 26, 0, Math.PI * 2); g.fill();
      g.globalAlpha = 0.95;
      g.fillStyle = "#0b1020";
      g.font = "800 14px ui-sans-serif, system-ui, sans-serif";
      g.fillText("A", viewW - 150, viewH - 91);
      g.fillText("B", viewW - 78, viewH - 55);

      // small menu chip, under the minimap
      g.globalAlpha = 0.36;
      g.fillStyle = "#e2e8f0";
      g.beginPath(); g.arc(viewW - 36, 192, 22, 0, Math.PI * 2); g.fill();
      g.globalAlpha = 0.9;
      g.fillStyle = "#0b1020";
      g.font = "800 15px ui-sans-serif, system-ui, sans-serif";
      g.fillText("☰", viewW - 36, 197);
      g.globalAlpha = 1;
    }

    /* Gradients are immutable and expensive to build (the 2D backend sets one
     * up per call), so keep one sky + one vignette per context and palette. */
    var gradCache = typeof WeakMap === "function" ? new WeakMap() : null;
    var gradList = [];
    function ensureGrads(g) {
      var key = viewW + "x" + viewH + "|" + (pal.ink || "") + "|" + (pal.wall || "");
      var hit = null;
      if (gradCache) hit = gradCache.get(g) || null;
      else {
        for (var i = 0; i < gradList.length; i++) {
          if (gradList[i].ctx === g) { hit = gradList[i]; break; }
        }
      }
      if (hit && hit.key === key && hit.sky && hit.vignette) return hit;

      var sky = g.createLinearGradient(0, 0, 0, viewH);
      sky.addColorStop(0, shade(pal.deep || "#0d2233", 1.18));
      sky.addColorStop(1, shade(pal.deep || "#0d2233", 0.82));

      var vig = g.createRadialGradient(viewW / 2, viewH / 2, viewH * 0.3,
        viewW / 2, viewH / 2, viewH * 0.8);
      vig.addColorStop(0, "rgba(0,0,0,0)");
      vig.addColorStop(1, "rgba(0,0,0,.42)");

      var entry = { ctx: g, key: key, sky: sky, vignette: vig };
      if (gradCache) gradCache.set(g, entry);
      else { if (hit) gradList.splice(gradList.indexOf(hit), 1); gradList.push(entry); }
      return entry;
    }

    function draw(g) {
      if (!g) g = ctx;
      g.save();
      // Keep the engine's device-pixel-ratio transform in place; resetting it
      // here would draw a half-size world in the corner on retina screens.
      g.clearRect(0, 0, viewW, viewH);
      var doc = canvas && canvas.ownerDocument
        || (typeof document !== "undefined" ? document : null);
      var back = ensureBackdrops(doc);
      if (back) {
        g.drawImage(back.sky, 0, 0, viewW, viewH);
      } else {
        var gr = ensureGrads(g);
        g.fillStyle = gr.sky;
        g.fillRect(0, 0, viewW, viewH);
      }

      var tcache = ensureTerrain(doc);
      if (tcache) {
        var sx = Math.round(viewW / 2 - ((state.cam.x - state.cam.y) * (TW / 2) + tcache.cx));
        var sy = Math.round(viewH / 2 - ((state.cam.x + state.cam.y) * (TH / 2) + tcache.cy));
        // Blit only the visible crop, not the whole world-sized cache.
        var srcX = Math.max(0, -sx), srcY = Math.max(0, -sy);
        var srcW = Math.min(tcache.canvas.width - srcX, viewW);
        var srcH = Math.min(tcache.canvas.height - srcY, viewH);
        if (srcW > 0 && srcH > 0) {
          g.drawImage(tcache.canvas, srcX, srcY, srcW, srcH,
            srcX + sx, srcY + sy, srcW, srcH);
        }
      } else {
        drawGround(g);
        drawDecor(g);
      }
      drawActors(g);

      if (back) {
        g.drawImage(back.vig, 0, 0, viewW, viewH);
      } else {
        var gr2 = ensureGrads(g);
        g.fillStyle = gr2.vignette;
        g.fillRect(0, 0, viewW, viewH);
      }

      drawHud(g);
      drawTouch(g);

      if (state.mode === "dialogue") drawDialogue(g);
      if (state.mode === "shop") drawShop(g);
      if (state.mode === "inventory") drawInventory(g);
      if (state.mode === "quests") drawQuests(g);
      if (state.mode === "map") drawMap(g);
      if (state.mode === "pause") drawPause(g);
      if (state.mode === "help") drawHelp(g);
      if (state.mode === "dead") drawDead(g);

      if (state.toast && state.toastT > 0) {
        g.font = "600 13px ui-sans-serif, system-ui, sans-serif";
        var tw = g.measureText(state.toast).width + 34;
        var tx = (viewW - tw) / 2, ty = viewH - 58;
        panel(g, tx, ty - 24, tw, 34);
        g.fillStyle = "#f8fafc";
        g.textAlign = "center";
        g.fillText(state.toast, viewW / 2, ty - 2);
      }
      g.restore();
    }

    /* --------------------------------------------------------- touch input */
    function pointerToAction(px, py) {
      if (Math.hypot(px - (viewW - 36), py - 192) < 30) return "pause";
      var dpadX = 92, dpadY = viewH - 92;
      if (Math.hypot(px - dpadX, py - dpadY) < 78) {
        var dx = px - dpadX, dy = py - dpadY;
        if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? "right" : "left";
        return dy > 0 ? "down" : "up";
      }
      if (Math.hypot(px - (viewW - 150), py - (viewH - 96)) < 42) return "interact";
      if (Math.hypot(px - (viewW - 78), py - (viewH - 60)) < 36) return "attack";
      return null;
    }

    function localPoint(ev) {
      var r = canvas.getBoundingClientRect();
      return {
        x: (ev.clientX - r.left) * viewW / (r.width || viewW),
        y: (ev.clientY - r.top) * viewH / (r.height || viewH)
      };
    }

    if (canvas && canvas.addEventListener) {
      canvas.addEventListener("pointerdown", function (ev) {
        var p = localPoint(ev);
        if (state.mode === "dialogue") { advanceDialogue(); return; }
        if (state.mode === "dead") { respawn(); return; }
        if (state.mode === "shop") { buy(); return; }
        if (state.mode === "pause") { menuChoose(); return; }
        var action = pointerToAction(p.x, p.y);
        if (action) {
          state.touch = true;
          state.pointer = ev.pointerId;
          pressed[action] = 1;
          if (E.press) E.press(action);
          if (ev.preventDefault) ev.preventDefault();
          if (canvas.setPointerCapture) { try { canvas.setPointerCapture(ev.pointerId); } catch (e) {} }
        }
      });
      var release = function (ev) {
        if (state.pointer !== ev.pointerId) return;
        ["up", "down", "left", "right", "interact", "attack", "pause"].forEach(function (a) {
          if (pressed[a]) { delete pressed[a]; if (E.release) E.release(a); }
        });
        state.pointer = null;
      };
      canvas.addEventListener("pointerup", release);
      canvas.addEventListener("pointercancel", release);
      canvas.addEventListener("pointerleave", release);
    }

    function start() {
      reveal();
      if (E.update !== undefined) {
        E.update = update;
        E.draw = draw;
        E.start && E.start();
      }
      return game;
    }

    var game = {
      start: start,
      stop: function () { if (E.stop) E.stop(); },
      update: update,
      draw: draw,
      renderOnce: function () { draw(ctx); },
      state: state,
      world: function () { return W; },
      player: player,
      engine: function () { return E; },
      save: save,
      load: load,
      slots: function () { return [1, 2, 3].map(slotInfo); },
      enterDungeon: enterDungeon,
      leaveDungeon: leaveDungeon,
      interact: interact,
      attack: attack,
      heal: usePotion,
      palette: function () { return pal; }
    };
    return game;
  }

  root.toolrxRpg2 = { create: create };
})(typeof self !== "undefined" ? self : this);

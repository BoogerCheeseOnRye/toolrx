#!/usr/bin/env python3
"""Behaviour tests for the browser skills + build templates.

The Pages build runs `toolrx/web/skills.js` directly, so this exercises the real
code in Node: command matching, multi-step planning, `prev` threading, and the
deterministic HTML templates. No server and no browser required.
"""

import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NODE = shutil.which("node")

JS = r"""
const fs = require('fs');
const FIXTURES = JSON.parse(fs.readFileSync(process.argv[6], 'utf8'));
global.self = global;
global.fetch = () => Promise.resolve({
  ok: true,
  json: () => Promise.resolve(JSON.parse(fs.readFileSync(process.argv[1], 'utf8'))),
});
const store = {};
global.localStorage = {
  getItem: k => Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null,
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.CustomEvent = class { constructor(type, opts) { this.type = type; this.detail = opts && opts.detail; } };
global.dispatchEvent = () => {};
global.toolrxRouter = { load: () => ({}), route: () => ({ tool: 'none', args: {}, confidence: 0 }) };
eval(fs.readFileSync(process.argv[2], 'utf8'));
eval(fs.readFileSync(process.argv[3], 'utf8'));
const WEB = require('path').dirname(process.argv[4]);
eval(fs.readFileSync(require('path').join(WEB, 'engine2d.js'), 'utf8'));
eval(fs.readFileSync(require('path').join(WEB, 'engine2d.embed.js'), 'utf8'));
eval(fs.readFileSync(require('path').join(WEB, 'engine3d.js'), 'utf8'));
eval(fs.readFileSync(require('path').join(WEB, 'engine3d.embed.js'), 'utf8'));
eval(fs.readFileSync(require('path').join(WEB, 'worldgen.js'), 'utf8'));
eval(fs.readFileSync(require('path').join(WEB, 'worldgen.embed.js'), 'utf8'));
eval(fs.readFileSync(require('path').join(WEB, 'rpg2.js'), 'utf8'));
eval(fs.readFileSync(require('path').join(WEB, 'rpg2.embed.js'), 'utf8'));
eval(fs.readFileSync(require('path').join(WEB, 'patches.js'), 'utf8'));
eval(fs.readFileSync(require('path').join(WEB, 'lang.js'), 'utf8'));
self.toolrxLang.configure(JSON.parse(fs.readFileSync(process.argv[5], 'utf8')));
eval(fs.readFileSync(process.argv[4], 'utf8'));

(async () => {
  await self.toolrxSkills.init('commands.json');
  const files = { 'notes.txt': 'one two three four five' };
  const state = { html: '', kind: '', theme: 'dark', files: {} };
  const memory = {};
  const ctx = {
    fs: {
      exists: p => Object.prototype.hasOwnProperty.call(files, p),
      read: p => files[p],
      write: (p, c) => { files[p] = String(c); return 'wrote ' + p; },
      list: () => Object.keys(files).join('\n'),
    },
    preview: () => state.html,
    theme: t => { state.theme = t; return true; },
    build: (kind, desc) => {
      const p = self.toolrxTemplates.project(kind, desc, { theme: state.theme });
      state.html = p.html;
      state.kind = p.kind;
      state.files = p.files;
      Object.keys(p.files).forEach(k => { files['projects/' + p.slug + '/' + k] = p.files[k]; });
      return 'built ' + Object.keys(p.files).join(',');
    },
    webPage: info => {
      const p = self.toolrxTemplates.webPage(Object.assign({}, info, { theme: state.theme }));
      state.html = p.html;
      state.kind = p.kind;
      state.lastTitle = p.title;
      state.lastSlug = p.slug;
      state.files = p.files;
      Object.keys(p.files).forEach(k => { files['projects/' + p.slug + '/' + k] = p.files[k]; });
      return 'built ' + p.title + ' → projects/' + p.slug + ' (' + Object.keys(p.files).length + ' files)';
    },
    architecture: (kind, desc) => self.toolrxTemplates.architecture(kind, desc, { theme: state.theme }),
    blueprint: (kind, desc) => ({ text: self.toolrxTemplates.brief(kind, desc) }),
    project: {
      new: n => 'created ' + n, list: () => 'proj-a\nproj-b', open: s => 'opened ' + s,
      rename: (s, n) => 'renamed ' + s + ' to ' + n, remove: s => 'deleted ' + s,
      files: () => 'index.html\nstyles.css\napp.js',
    },
    chat: (who, text) => text, history: () => [{ who: 'toolrx', text: 'earlier' }],
    memory: {
      get: k => memory[k],
      set: (k, v) => { memory[k] = v; return v; },
      remove: k => { delete memory[k]; },
      clear: () => { Object.keys(memory).forEach(k => { delete memory[k]; }); },
      keys: () => Object.keys(memory),
    },
    web: {
      search: async q => ({ text: 'summary about ' + q + '.', source: 'https://en.wikipedia.org/wiki/' + q,
                           title: q.replace(/\b\w/g, c => c.toUpperCase()) }),
      define: async w => ({ text: w + ': a test definition', source: 'https://dictionaryapi.dev/' }),
      weather: async p => ({ text: p + ': 7°C · clear', source: 'https://open-meteo.com/' }),
      answer: async q => ({ text: 'instant answer for ' + q, source: 'https://duckduckgo.com/' }),
    },
    fallback: async step => {
      const m = /^read\s+(.+)$/i.exec(step);
      const text = m && files[m[1]] ? files[m[1]] : ('fallback:' + step);
      return { text: text, error: false, via: 'router.test' };
    },
  };
  const run = async q => {
    const res = await self.toolrxSkills.runPrompt(q, ctx);
    return res.map(r => ({
      step: r.step, text: r.text, error: !!r.error, via: r.via || '',
      tool: r.tool || '', args: r.args || null, source: r.source || '',
      ms: r.ms,
    }));
  };
  const out = {};
  out.count = self.toolrxSkills.count();
  out.catalog = self.toolrxSkills.catalog('build', '', 5);
  out.catalogCat = self.toolrxSkills.catalog('', 'memory', 100);
  out.catalogEmpty = self.toolrxSkills.catalog('zzzznotacommand', '', 10);
  out.catalogRpg = self.toolrxSkills.catalog('rpg', '', 12);
  out.catalogFill = self.toolrxSkills.catalog('tetris', '', 8);
  const specOf = (k, d) => {
    const s = self.toolrxTemplates.spec(k, d);
    return { spec: s, line: self.toolrxTemplates.specLine(s) };
  };
  out.spec = {
    p3d: specOf('3d platformer', 'with a neon city theme'),
    isoRpg: specOf('isometric rpg', 'in a desert with 3 quests'),
    shooter: specOf('top-down shooter', 'pixel art, 3 levels'),
    maze: specOf('first-person maze', 'low-poly'),
    racing: specOf('racer', '2d at night, seed 42'),
    rpg: specOf('rpg', ''),
    repeat: specOf('top-down shooter', 'pixel art, 3 levels'),
    seed: specOf('platformer', 'seed 42'),
    tower: specOf('tower defense', '')
  };
  out.engine = {};
  for (const kind of ['platformer', 'snake', 'breakout', 'shooter', 'racer']) {
    const p = self.toolrxTemplates.project(kind, '', {});
    out.engine[kind] = {
      files: Object.keys(p.files), html: p.html,
      src: p.files['engine2d.js'] || '', spec: p.specLine || ''
    };
  }
  out.engine3d = {};
  for (const [kind, desc] of [['platformer', '3d low-poly'],
                              ['maze', 'first-person low-poly'],
                              ['racer', '3d low-poly']]) {
    const p = self.toolrxTemplates.project(kind, desc, {});
    out.engine3d[kind] = {
      files: Object.keys(p.files), html: p.html,
      src: p.files['engine3d.js'] || '', spec: p.specLine || '',
      htmlSource: p.files['index.html'] || ''
    };
  }
  out.engine3dRuntime = await new Promise(resolve => {
    const calls = { update: 0, draw: 0, fills: 0, mode: '', culled: 0 };
    const grad = { addColorStop() {} };
    const ctx2d = new Proxy({}, {
      get(t, p) {
        if (p === 'createLinearGradient' || p === 'createRadialGradient') return () => grad;
        if (p === 'fill') return () => { calls.fills++; };
        return () => {};
      },
      set() { return true; },
    });
    const canvas = {
      width: 0, height: 0,
      getContext: t => (t === '2d' ? ctx2d : null),
      addEventListener() {},
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 320, height: 180 }),
    };
    const E = self.toolrxEngine3d.create({ canvas, width: 320, height: 180, sky: '#102030' });
    calls.mode = E.mode;
    E.update = () => { calls.update++; };
    E.draw = () => {
      calls.draw++;
      E.clearScene();
      E.box({ x: 0, y: 1, z: 4, w: 2, h: 2, d: 2, color: '#ff8800' });
      E.box({ x: 3, y: 1, z: -6, w: 2, h: 2, d: 2, color: '#22cc88' });
      E.sprite({ x: -2, y: 1, z: 5, w: 1, h: 1, color: '#ffffff' });
      // Behind the camera: must be clipped away, not drawn.
      E.box({ x: 0, y: 1, z: -30, w: 2, h: 2, d: 2, color: '#ff0000' });
    };
    E.camera.x = 0; E.camera.y = 1.6; E.camera.z = 0; E.camera.yaw = 0; E.camera.pitch = 0;
    E.renderOnce();
    let frames = 0;
    const prevRaf = global.requestAnimationFrame;
    global.requestAnimationFrame = fn => {
      if (frames++ < 3) setTimeout(() => fn(frames * 16), 0);
      return frames;
    };
    E.start();
    setTimeout(() => {
      E.stop();
      global.requestAnimationFrame = prevRaf;
      resolve(calls);
    }, 160);
  });
  out.specV3 = (() => {
    const prompt = 'a huge space rpg with crafting and 6 quests, 3 levels, '
      + '12 enemies, 8 npcs, 4 items, sub-theme nebula, 96x96 world';
    const rich = self.toolrxTemplates.project('rpg', prompt, {});
    const again = self.toolrxTemplates.project('rpg', prompt, {});
    const plain = self.toolrxTemplates.project('calculator', 'a tip calculator', {});
    const tight = self.toolrxTemplates.spec('rpg', 'sub-theme nebula 96x96 world');
    const raw = rich.files['content.js'] || '';
    const content = JSON.parse(raw.replace(/^[\s\S]*?window\.toolrxContent = /, '')
      .replace(/;\s*$/, ''));
    return {
      spec: rich.spec, line: rich.specLine,
      tightSubtheme: tight.subtheme,
      files: Object.keys(rich.files).sort(),
      hasTag: /src="content\.js"/.test(rich.html),
      tagBeforeApp: rich.html.indexOf('src="content.js"') < rich.html.indexOf('src="app.js"'),
      summary: /toolrx-content/.test(rich.html)
        && rich.html.indexOf('toolrx-content') < rich.html.indexOf('<footer>'),
      readme: rich.files['README.md'], arch: rich.files['ARCHITECTURE.md'],
      worldTag: /SIZE=96\b/.test(rich.files['app.js'] || '')
        && /"quests":6/.test(rich.files['app.js'] || '')
        && /counts:/.test(rich.files['app.js'] || ''),
      content,
      same: JSON.stringify(rich.files) === JSON.stringify(again.files)
        && rich.html === again.html,
      plainFiles: Object.keys(plain.files).sort(),
      plainHasContent: /content\.js/.test(plain.html) || !!plain.files['content.js'],
    };
  })();
  out.contentWorld = (() => {
    const make = counts => self.toolrxWorldgen.generate({
      seed: 4242, size: 96, theme: self.toolrxWorldgen.defaultTheme, counts,
    });
    const counts = { towns: 4, enemies: 9, npcs: 5, quests: 7 };
    const a = make(counts), b = make(counts), base = make(null);
    return {
      towns: a.towns.length, enemies: a.enemies.length,
      npcs: a.npcs.length, quests: a.quests.length,
      baseTowns: base.towns.length, baseEnemies: base.enemies.length,
      same: JSON.stringify(a.tiles) === JSON.stringify(b.tiles)
        && JSON.stringify(a.npcs) === JSON.stringify(b.npcs)
        && JSON.stringify(a.quests) === JSON.stringify(b.quests),
      npcIdsUnique: new Set(a.npcs.map(n => n.id)).size === a.npcs.length,
      questGivers: a.quests.filter(q => q.giver).length,
    };
  })();
  out.rpgWorld = (() => {
    const make = seed => self.toolrxWorldgen.generate({
      seed, size: 64, theme: self.toolrxWorldgen.defaultTheme,
    });
    const a = make(12345), b = make(12345), c = make(999);
    const big = self.toolrxWorldgen.generate({
      seed: 5, size: 96, theme: self.toolrxWorldgen.defaultTheme,
    });
    return {
      size: a.size, seed: a.seed,
      towns: a.towns.length, npcs: a.npcs.length, quests: a.quests.length,
      enemies: a.enemies.length, pickups: a.pickups.length,
      townNames: a.towns.map(t => t.name),
      sameTiles: JSON.stringify(a.tiles) === JSON.stringify(b.tiles),
      sameNpcs: a.npcs.map(n => n.name).join(',') === b.npcs.map(n => n.name).join(','),
      diffTiles: JSON.stringify(a.tiles) !== JSON.stringify(c.tiles),
      dungeonRooms: a.dungeonMap.rooms.length,
      hasBoss: !!(a.dungeonMap.boss && a.dungeonMap.boss.hp > 0),
      startWalkable: a.walkable(a.start.x, a.start.y),
      bigSize: big.size, bigTowns: big.towns.length,
      questGivers: a.quests.filter(q => q.giver).length,
    };
  })();
  out.rpgProject = (() => {
    const p = self.toolrxTemplates.project('rpg', 'an rpg based on india', {});
    return {
      files: Object.keys(p.files).sort(),
      hasWorldgenTag: /src="worldgen\.js"/.test(p.html),
      hasRpgTag: /src="rpg2\.js"/.test(p.html),
      engineTagOnce: (p.html.match(/src="engine2d\.js"/g) || []).length,
      appCreates: /toolrxRpg2\.create/.test(p.files['app.js'] || ''),
      appHasBoss: /Asura King/.test(p.files['app.js'] || ''),
      worldSrc: /toolrxWorldgen/.test(p.files['worldgen.js'] || ''),
    };
  })();
  out.rpgRuntime = (() => {
    const grad = { addColorStop() {} };
    const calls = { fills: 0, texts: 0 };
    const ctx = new Proxy({}, {
      get(t, p) {
        if (p === 'createLinearGradient' || p === 'createRadialGradient') return () => grad;
        if (p === 'measureText') return s => ({ width: String(s).length * 7 });
        if (p === 'fill') return () => { calls.fills++; };
        if (p === 'fillText') return () => { calls.texts++; };
        return () => {};
      },
      set() { return true; },
    });
    const canvas = {
      width: 960, height: 540,
      getContext: () => ctx,
      addEventListener() {},
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 960, height: 540 }),
    };
    const E = {
      canvas, ctx, width: 960, height: 540,
      tap: () => false, held: () => false,
      bind() {}, press() {}, release() {}, beep() {}, start() {}, stop() {},
      update: null, draw: null,
    };
    const W = self.toolrxWorldgen.generate({
      seed: 7, size: 64, theme: self.toolrxWorldgen.defaultTheme,
    });
    const G = self.toolrxRpg2.create({
      engine: E, canvas, world: W, theme: W.theme, width: 960, height: 540,
    });
    G.start();
    G.renderOnce();
    for (let i = 0; i < 6; i++) G.update(1 / 60);
    G.enterDungeon();
    G.renderOnce();
    const inDungeon = G.state.map;
    G.leaveDungeon();
    const back = G.state.map;
    const saved = G.save(2);
    const loaded = G.load(2);
    return {
      fills: calls.fills, texts: calls.texts, inDungeon, back, saved, loaded,
      quests: G.world().quests.length, npcs: G.world().npcs.length,
      mode: G.state.mode, level: G.player().level,
      slots: G.slots().map(s => !!s),
    };
  })();
  out.engineRuntime = await new Promise(resolve => {    const calls = { update: 0, draw: 0, ctx: false };
    const grad = { addColorStop() {} };
    const canvas = {
      width: 0, height: 0,
      getContext: () => ctx,
      addEventListener() {},
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 320, height: 180 }),
    };
    const ctx = new Proxy({}, {
      get(t, p) {
        if (p === 'createLinearGradient' || p === 'createRadialGradient') return () => grad;
        if (p === 'canvas') return canvas;
        return () => {};
      },
      set() { return true; },
    });
    let frames = 0;
    const prevRaf = global.requestAnimationFrame;
    global.requestAnimationFrame = fn => {
      if (frames++ < 4) setTimeout(() => fn(frames * 16), 0);
      return frames;
    };
    const E = self.toolrxEngine2d.create({ canvas, width: 320, height: 180 });
    // Games assign these after create(); the loop must pick them up.
    E.update = () => { calls.update++; };
    E.draw = c => { calls.draw++; calls.ctx = c === ctx; };
    E.start();
    setTimeout(() => {
      E.stop();
      global.requestAnimationFrame = prevRaf;
      resolve(calls);
    }, 180);
  });
  out.multiply = await run('multiply 67 and 420');
  out.square = await run('square 67');
  out.chain = await run('convert 5 km to miles then square the result');
  out.read = await run('read notes.txt then count the words');
  out.pronoun = await run('capital of france then uppercase it');
  out.steps = self.toolrxSkills.splitPrompt('one then two; three -> four');
  out.limits = self.toolrxSkills.limits;
  out.splitInfo = {
    connector: self.toolrxSkills.splitPromptInfo('one then two; three -> four'),
    numbered: self.toolrxSkills.splitPromptInfo('1. read notes.txt\n2. count the words'),
    multi: self.toolrxSkills.splitPromptInfo('read notes.txt\ncount the words'),
    sentences: self.toolrxSkills.splitPromptInfo(
      ('list the files in the current directory and show the uptime for this machine right now. ')
        .repeat(3).trim()),
    long: self.toolrxSkills.splitPromptInfo('word '.repeat(600)),
  };
  out.planPreview = {
    multi: self.toolrxSkills.planPreview('read notes.txt then count the words'),
    single: self.toolrxSkills.planPreview('read notes.txt'),
    tooLong: self.toolrxSkills.planPreview('word '.repeat(1700)),
    tooMany: self.toolrxSkills.planPreview(
      Array.from({ length: 41 }, (_, i) => (i + 1) + '. read notes.txt').join('\n')),
  };
  out.limitRun = await run('word '.repeat(1700));
  {
    const fallback = ctx.fallback;
    ctx.fallback = async () => ({ text: 'boom', error: true, via: 'test.fail' });
    out.planStop = await run('multiply 6 and 7 then zzzznotacommand then multiply 2 and 3');
    ctx.fallback = fallback;
  }
  out.compose = {};
  for (const q of [
    'build a huge space rpg game with crafting',
    'build a small cyberpunk platformer game',
    'build a medieval roguelike game with quests',
    'build an epic underwater farming sim with weather',
    'build a sprawling astral exploration game with dialogue trees',
    'build a pirate tower defense game',
    'build a pixel art tetris game',
    'build a large maze game',
  ]) {
    const m = self.toolrxSkills.match(q);
    out.compose[q] = m && { op: m.op, args: m.args };
  }
  out.composeBuild = await run('build a huge space rpg game with crafting');
  out.composeKind = state.kind;
  out.build = await run('build a calculator app');
  out.buildHtml = state.html;
  out.calcFiles = Object.keys(state.files).sort();
  state.html = '';
  out.build2 = await run('build a calculator app');
  out.buildSame = out.buildHtml === state.html;
  state.html = '';
  out.buildTodo = await run('build me a todo list');
  out.todoHtml = state.html;
  out.games = {};
  for (const kind of ['rpg', 'platformer', 'snake', 'breakout', 'pong', '2048',
                      'minesweeper', 'tetris', 'maze', 'adventure', 'typing']) {
    const r = await run('build a ' + kind + ' game');
    out.games[kind] = { kind: state.kind, files: Object.keys(state.files).sort(),
                        html: state.html.length, ok: !r[0].error };
  }
  out.genres = {};
  {
    const prompts = {
      twinstick: 'build a twin-stick shooter game',
      roguelike: 'build a roguelike game',
      towerdefense: 'build a tower defense game',
      merges: 'build a match-3 puzzle game',
      farmingsim: 'build a farming sim game',
      cardbattler: 'build a card battler game',
      rhythm: 'build a rhythm game',
      explore: 'build a low-poly exploration game',
      waveshooter: 'build a wave shooter game',
      builder: 'build a block builder game'
    };
    for (const [name, q] of Object.entries(prompts)) {
      const r = await run(q);
      const js = state.files['app.js'] || '';
      let syntax = 'ok';
      try { new Function(js); } catch (e) { syntax = e.message; }
      out.genres[name] = {
        ok: !r.some(x => x.error), via: r[0] ? r[0].via : '',
        kind: state.kind,
        title: ((state.html.match(/<h1>([^<]*)<\/h1>/) || [])[1] || ''),
        files: Object.keys(state.files).sort(),
        js: js,
        arch: state.files['ARCHITECTURE.md'] || '',
        html: state.html.length,
        syntax: syntax,
      };
    }
  }
  out.genrePlans = {};
  for (const q of ['plan a twin-stick shooter', 'plan a roguelike',
                   'plan a tower defense', 'plan a match-3 puzzle',
                   'plan a farming sim', 'plan a card battler',
                   'plan a rhythm game', 'plan a low-poly exploration',
                   'plan a wave shooter', 'plan a block builder']) {
    const r = await run(q);
    out.genrePlans[q] = {
      ok: !r.some(x => x.error), via: r[0] ? r[0].via : '',
      text: r[0] ? String(r[0].text || '') : '',
    };
  }
  out.sites = {};
  for (const [q, kind] of [['build a social media website', 'social'],
                           ['build a blog', 'blog'],
                           ['build a forum website', 'forum'],
                           ['build a chat app', 'chat']]) {
    const r = await run(q);
    out.sites[kind] = { kind: state.kind, files: Object.keys(state.files).sort(),
                        html: state.html.length, ok: !r[0].error };
  }
  out.plan = await run('plan an rpg');
  out.blueprint = await run('blueprint a todo app');
  out.newProject = await run('new project notes');
  out.listProjects = await run('list projects');
  out.openProject = await run('open project notes');
  out.deleteProject = await run('delete this project');
  out.showFiles = await run('show project files');
  out.chatHello = await run('hello');
  out.chatFeel = await run('i feel anxious');
  out.chatName = await run('remember my name is ada');
  out.chatWho = await run('what is my name');
  out.chatJoke = await run('tell me a joke');
  out.chatGreetings = ['hi', 'hello', 'hey'].map(q => self.toolrxSkills.chat(q, ctx));
  out.chatUnknown = self.toolrxSkills.chat('blorp wobble', ctx);
  out.chatFeelings = ['i am stuck', 'i feel anxious', 'i am tired', 'i feel lost']
    .map(q => self.toolrxSkills.chat(q, ctx));
  out.memory = {};
  out.memory.rememberColor = await run('remember my favorite color is teal');
  out.memory.recallColor = await run('what is my favorite color');
  out.memory.rememberDog = await run('remember my dog is max');
  out.memory.recallDog = await run('what do you remember about my dog');
  out.memory.rememberCode = await run('remember that the launch code is 42');
  out.memory.recallCode = await run('what is my launch code');
  out.memory.note = await run('make a note that the meeting moved to friday');
  out.memory.recallMissing = await run('what is my shoe size');
  memory.last_build = { title: 'Calculator', kind: 'calculator', desc: 'a calculator app', slug: 'calculator' };
  out.memory.list = await run('what do you remember');
  out.memory.context = await run('what did i build last');
  out.memory.forgetColor = await run('forget my favorite color');
  out.memory.afterForget = await run('what is my favorite color');
  out.memory.forgetName = await run('forget my name');
  out.memory.nameAfterForget = await run('what is my name');
  out.memory.clear = await run('forget everything');
  out.memory.afterClear = await run('what do you remember');
  out.webBuild = {};
  {
    const r = await run('wikipedia ada lovelace then build a page about it');
    out.webBuild.pipeline = {
      steps: r.length, via: r.map(x => x.via), ok: !r.some(x => x.error),
      text: r[1] ? r[1].text : '', title: state.lastTitle || '',
      slug: state.lastSlug || '', html: state.html, files: Object.keys(state.files).sort(),
      css: state.files['styles.css'] || '', js: state.files['app.js'] || '',
    };
  }
  {
    const r = await run('build a page about grace hopper');
    out.webBuild.topic = {
      steps: r.length, via: r[0] ? r[0].via : '', ok: !r[0].error,
      title: state.lastTitle || '', slug: state.lastSlug || '',
      html: state.html, files: Object.keys(state.files).sort(),
    };
  }
  {
    const r = await run('build a page about it');
    out.webBuild.noPrev = { via: r[0] ? r[0].via : '', error: !!r[0].error, text: r[0] ? r[0].text : '' };
  }
  {
    const r = await run('wikipedia ada lovelace then summarize it then build a page about it');
    out.webBuild.summary = {
      steps: r.length, via: r.map(x => x.via), ok: !r.some(x => x.error),
      source: r[1] ? r[1].source : '', title: state.lastTitle || '', html: state.html,
    };
  }
  out.variants = {};
  for (const q of ['build a tetris game with 3d elements',
                   'build an rpg based on king arthur',
                   'build an rpg based on india']) {
    const r = await run(q);
    out.variants[q] = {
      ok: !r[0].error, via: r[0].via || '',
      kind: state.kind,
      html: state.html,
      title: ((state.html.match(/<h1>([^<]*)<\/h1>/) || [])[1] || ''),
      files: Object.keys(state.files).sort(),
      css: state.files['styles.css'] || '',
      js: state.files['app.js'] || '',
    };
  }
  out.syntax = {};
  for (const [kind, desc] of [['tetris', 'a tetris game with 3d elements'],
                              ['rpg', 'an rpg based on king arthur'],
                              ['rpg', 'an rpg based on india'],
                              ['rpg', 'an rpg set in space'],
                              ['rpg', 'an rpg noir detective'],
                              ['rpg', 'an rpg based on greek myth'],
                              ['rpg', 'an rpg based on japan'],
                              ['rpg', 'an rpg based on egypt'],
                              ['rpg', 'an rpg based on the ocean'],
                              ['rpg', 'an rpg based on the wild west'],
                              ['rpg', 'an rpg based on cyberpunk']]) {
    const p = self.toolrxTemplates.project(kind, desc, { theme: 'dark' });
    try { new Function(p.files['app.js']); out.syntax[kind + ':' + desc] = 'ok'; }
    catch (e) { out.syntax[kind + ':' + desc] = e.message; }
  }
  out.themes = {};
  for (const q of ['build an rpg based on greek myth',
                   'build an rpg based on japan',
                   'build an rpg based on egypt',
                   'build an rpg based on the ocean',
                   'build an rpg based on the wild west',
                   'build an rpg based on cyberpunk',
                   'build an rpg noir detective']) {
    const r = await run(q);
    out.themes[q] = {
      ok: !r[0].error, kind: state.kind,
      title: ((state.html.match(/<h1>([^<]*)<\/h1>/) || [])[1] || ''),
      html: state.html,
      css: state.files['styles.css'] || '',
      js: state.files['app.js'] || '',
    };
  }
  // Theme/title pass: the shipped pack list, generated default titles, and
  // exact seed replay. These call the templates directly so the session
  // counter advances exactly as it does for ten separate builds.
  out.rpgPacks = self.toolrxTemplates.themePacks();
  out.rpgDeterministic = (() => {
    const a = self.toolrxTemplates.project('rpg', 'build an rpg based on india', { theme: 'dark' });
    const b = self.toolrxTemplates.project('rpg', 'build an rpg based on india', { theme: 'dark' });
    return {
      title: a.title, seed: a.spec.seed,
      same: a.title === b.title && a.spec.seed === b.spec.seed && a.html === b.html,
    };
  })();
  out.rpgDefaults = (() => {
    const titles = [], slugs = [], htmls = [];
    for (let i = 0; i < 10; i++) {
      const p = self.toolrxTemplates.project('rpg', 'build an rpg', { theme: 'dark' });
      titles.push(p.title); slugs.push(p.slug); htmls.push(p.html);
    }
    const a = self.toolrxTemplates.project('rpg', 'build an rpg seed 7', { theme: 'dark' });
    const b = self.toolrxTemplates.project('rpg', 'build an rpg seed 7', { theme: 'dark' });
    const grammar = self.toolrxTemplates.rpgGrammarTitle(14);
    return {
      titles, slugs, uniqueTitles: new Set(titles).size,
      uniqueSlugs: new Set(slugs).size, uniqueHtml: new Set(htmls).size,
      seed7: { a: a.title, b: b.title, seed: a.spec.seed,
               same: a.html === b.html && a.title === b.title },
      grammar,
    };
  })();
  out.newThemes = {};
  for (const q of ['build an rpg in the frost',
                   'build an rpg in a volcano',
                   'build an rpg with mushrooms',
                   'build an rpg in the sky islands',
                   'build an rpg with clockwork',
                   'build an rpg in a dream',
                   'build an rpg in a plague',
                   'build an rpg on an archipelago',
                   'build an rpg in the verdant forest',
                   'build an rpg among the stars']) {
    const p = self.toolrxTemplates.project('rpg', q, { theme: 'dark' });
    out.newThemes[q] = {
      title: p.title,
      theme: p.spec.theme,
      places: (p.files['app.js'].match(/"places":\[[^\]]*\]/) || [''])[0],
      css: p.files['styles.css'] || '',
      js: p.files['app.js'] || '',
      html: p.html,
    };
  }
  // Real sandbox rename flow: build one RPG, then refer to it by a stale name
  // and by "it". The same project must be re-themed, not duplicated.
  await self.toolrxWeb.init('model.json');
  self.toolrxWeb.reset();
  out.sandbox = {};
  out.sandbox.engineBuild = (await self.toolrxWeb.prompt('build a platformer game'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  let eng = self.toolrxWeb.project();
  out.sandbox.engine = {
    slug: eng.slug,
    files: eng.files.slice().sort(),
    previewHasEngine: /toolrxEngine2d/.test(self.toolrxWeb.preview().html),
    previewHasExternalTag: /src=["']engine2d\.js/.test(self.toolrxWeb.preview().html),
    readme: self.toolrxWeb.projectFile(eng.slug, 'README.md'),
    arch: self.toolrxWeb.projectFile(eng.slug, 'ARCHITECTURE.md')
  };
  out.sandbox.engine3dBuild = (await self.toolrxWeb.prompt('build a 3d platformer game'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  const eng3 = self.toolrxWeb.project();
  out.sandbox.engine3d = {
    slug: eng3.slug,
    files: eng3.files.slice().sort(),
    previewHasEngine: /toolrxEngine3d/.test(self.toolrxWeb.preview().html),
    previewHasExternalTag: /src=["']engine3d\.js/.test(self.toolrxWeb.preview().html),
    previewHasCreate: /toolrxEngine3d\.create/.test(self.toolrxWeb.preview().html),
  };
  const h1 = html => ((String(html).match(/<h1>([^<]*)<\/h1>/) || [])[1] || '');
  out.sandbox.content = {};
  out.sandbox.content.build = (await self.toolrxWeb.prompt(
    'build a huge space rpg game with crafting'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  const cp = self.toolrxWeb.project();
  out.sandbox.content.project = {
    slug: cp.slug,
    files: cp.files.slice().sort(),
    hasContent: cp.files.indexOf('content.js') >= 0,
    previewHasData: /toolrxContent/.test(self.toolrxWeb.preview().html),
    previewExternal: /src=["']content\.js/.test(self.toolrxWeb.preview().html),
  };
  out.sandbox.build = (await self.toolrxWeb.prompt('build an rpg based on king arthur'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  let p = self.toolrxWeb.project();
  out.sandbox.first = { slug: p.slug, name: p.name, h1: h1(p.html), desc: p.desc };
  out.sandbox.rpgPreview = {
    files: p.files.slice().sort(),
    hasWorldgen: /toolrxWorldgen/.test(self.toolrxWeb.preview().html),
    hasRpg: /toolrxRpg2/.test(self.toolrxWeb.preview().html),
    external: /src=["'](?:worldgen|rpg2|engine2d)\.js/.test(self.toolrxWeb.preview().html),
  };
  out.sandbox.stale = (await self.toolrxWeb.prompt('change the name from verdant wood rpg to india'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  p = self.toolrxWeb.project();
  out.sandbox.afterStale = {
    slug: p.slug, name: p.name, h1: h1(p.html), desc: p.desc,
    css: self.toolrxWeb.projectFile(p.slug, 'styles.css'),
    js: self.toolrxWeb.projectFile(p.slug, 'app.js'),
    bundled: p.html,
  };
  out.sandbox.pronoun = (await self.toolrxWeb.prompt('rename it to camelot'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  p = self.toolrxWeb.project();
  out.sandbox.afterPronoun = { slug: p.slug, name: p.name, h1: h1(p.html), desc: p.desc };
  // Project-aware edits: these must change the project's own files and the
  // re-bundled preview, not regenerate either from the template.
  out.edits = {};
  const editRun = async q => (await self.toolrxWeb.prompt(q))
    .map(r => ({ via: r.via || '', text: r.text || '', error: !!r.error }));
  out.edits.title = await editRun('change the page title to camelot field notes');
  let ep = self.toolrxWeb.project();
  let idx = self.toolrxWeb.projectFile(ep.slug, 'index.html');
  out.edits.afterTitle = {
    slug: ep.slug, name: ep.name, h1: h1(ep.html),
    pageTitle: (idx.match(/<title>([^<]*)<\/title>/) || [])[1] || '',
    readme: (self.toolrxWeb.projectFile(ep.slug, 'README.md').match(/^# .*$/m) || [''])[0],
    previewHas: ep.html.indexOf('camelot field notes') !== -1,
  };
  out.edits.theme = await editRun('make this project light');
  ep = self.toolrxWeb.project();
  idx = self.toolrxWeb.projectFile(ep.slug, 'index.html');
  out.edits.afterTheme = {
    htmlClass: (idx.match(/<html[^>]*class="([^"]*)"/) || [])[1] || '',
    previewTheme: self.toolrxWeb.preview().theme,
    title: h1(ep.html), name: ep.name,
  };
  out.edits.toggle = await editRun('add a theme toggle');
  ep = self.toolrxWeb.project();
  idx = self.toolrxWeb.projectFile(ep.slug, 'index.html');
  let ejs = self.toolrxWeb.projectFile(ep.slug, 'app.js');
  out.edits.afterToggle = {
    button: /id="themeToggle"/.test(idx),
    handler: /getElementById\('themeToggle'\)/.test(ejs),
    previewButton: /id="themeToggle"/.test(ep.html),
    previewScript: /getElementById\('themeToggle'\)/.test(ep.html),
    jsValid: (() => { try { new Function(ejs); return true; } catch (e) { return e.message; } })(),
  };
  out.edits.toggleAgain = await editRun('add a theme toggle');
  ep = self.toolrxWeb.project();
  idx = self.toolrxWeb.projectFile(ep.slug, 'index.html');
  out.edits.toggleCount = (idx.match(/id="themeToggle"/g) || []).length;
  out.edits.note = await editRun('add a footer note saying offline copy for ada');
  ep = self.toolrxWeb.project();
  idx = self.toolrxWeb.projectFile(ep.slug, 'index.html');
  out.edits.afterNote = {
    file: /offline copy for ada/.test(idx),
    preview: /offline copy for ada/.test(ep.html),
    hasId: /id="projectNote"/.test(idx),
  };
  out.edits.noteAgain = await editRun('add a footer note saying second note');
  ep = self.toolrxWeb.project();
  idx = self.toolrxWeb.projectFile(ep.slug, 'index.html');
  out.edits.noteCount = (idx.match(/id="projectNote"/g) || []).length;
  out.edits.afterNoteAgain = {
    firstGone: !/offline copy for ada/.test(idx),
    second: /second note/.test(idx),
  };
  const css0 = self.toolrxWeb.projectFile(ep.slug, 'styles.css');
  out.edits.write = self.toolrxWeb.writeProjectFile(
    ep.slug, 'styles.css', css0 + '\n.write-marker{color:rgb(1,2,3)}\n');
  ep = self.toolrxWeb.project();
  out.edits.afterWrite = {
    preview: /\.write-marker\{color:rgb\(1,2,3\)\}/.test(ep.html),
    file: /\.write-marker\{color:rgb\(1,2,3\)\}/.test(
      self.toolrxWeb.projectFile(ep.slug, 'styles.css')),
  };
  out.edits.writeMissing = (() => {
    try { self.toolrxWeb.writeProjectFile(ep.slug, 'nope.txt', 'x'); return 'no error'; }
    catch (e) { return e.message; }
  })();
  out.edits.writeTooBig = (() => {
    try { self.toolrxWeb.writeProjectFile(ep.slug, 'styles.css', 'x'.repeat(9000)); return 'no error'; }
    catch (e) { return e.message; }
  })();
  out.edits.dark = await editRun('make it dark');
  ep = self.toolrxWeb.project();
  idx = self.toolrxWeb.projectFile(ep.slug, 'index.html');
  ejs = self.toolrxWeb.projectFile(ep.slug, 'app.js');
  out.edits.afterDark = {
    htmlClass: (idx.match(/<html[^>]*class="([^"]*)"/) || [])[1] || '',
    previewTheme: self.toolrxWeb.preview().theme,
    title: h1(ep.html), toggle: /id="themeToggle"/.test(idx),
    note: /second note/.test(idx),
    marker: /\.write-marker\{color:rgb\(1,2,3\)\}/.test(ep.html),
  };
  out.edits.bundle = {
    hasStyle: /<style>/.test(ep.html), hasScript: /<script>/.test(ep.html),
    noLink: !/href="styles.css"/.test(ep.html), noSrc: !/src="app.js"/.test(ep.html),
    label: /offline · project preview/.test(ep.html),
    titleTag: /<title>camelot field notes · toolrx<\/title>/.test(ep.html),
  };
  out.edits.open = await editRun('open project camelot-rpg');
  ep = self.toolrxWeb.project();
  out.edits.afterOpen = { slug: ep.slug, title: h1(ep.html), theme: self.toolrxWeb.preview().theme };

  // Step 19: composable edits run through the real sandbox, so this covers
  // command routing, the patch engine, project persistence, and undo.
  out.patches = {};
  const pRun = async q => (await self.toolrxWeb.prompt(q))
    .map(r => ({ via: r.via || '', text: r.text || '', error: !!r.error }));
  const snap = () => {
    const cur = self.toolrxWeb.project();
    const map = {};
    cur.files.forEach(f => { map[f] = self.toolrxWeb.projectFile(cur.slug, f); });
    return { slug: cur.slug, files: map, html: cur.html };
  };
  const sameMap = (a, b) => {
    const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
    if (ka.join(',') !== kb.join(',')) return false;
    return ka.every(k => a[k] === b[k]);
  };
  const jsCheck = text => {
    try { new Function(text); return 'ok'; } catch (e) { return e.message; }
  };
  const specLineOf = text => ((String(text).match(/^spec · .*$/m) || [''])[0]);

  self.toolrxWeb.reset();
  await pRun('build a platformer game');
  const platBase = snap();
  out.patches.base = {
    slug: platBase.slug, files: Object.keys(platBase.files).sort(),
    engine3d: 'engine3d.js' in platBase.files,
    spec: specLineOf(platBase.files['ARCHITECTURE.md']),
  };

  const stack = ['add double jump', 'add three enemy types', 'add a quest',
                 'add day/night', 'add sound', 'make it harder'];
  out.patches.steps = [];
  for (const q of stack) {
    const before = snap();
    const r = await pRun(q);
    const after = snap();
    const changed = Object.keys(before.files)
      .filter(f => after.files[f] !== before.files[f])
      .concat(Object.keys(after.files).filter(f => !(f in before.files)))
      .sort();
    out.patches.steps.push({
      q, via: r[0].via, text: r[0].text, error: !!r[0].error,
      changed, files: Object.keys(after.files).sort(),
      syntax: jsCheck(after.files['app.js']),
      arch: after.files['ARCHITECTURE.md'],
      spec: specLineOf(after.files['ARCHITECTURE.md']),
      preview: after.html,
    });
  }
  const stacked = snap();
  out.patches.stacked = {
    files: Object.keys(stacked.files).sort(),
    syntax: jsCheck(stacked.files['app.js']),
    arch: stacked.files['ARCHITECTURE.md'],
    spec: specLineOf(stacked.files['ARCHITECTURE.md']),
    previewHasDoubleJump: /function doubleJump/.test(stacked.html),
    previewHasQuest: /function questCheck/.test(stacked.html),
    previewHasMute: /id="muteBtn"/.test(stacked.html),
    previewHasDayNight: /id="daynight"/.test(stacked.html),
  };
  out.patches.undo = [];
  for (let i = stack.length - 1; i >= 0; i--) {
    const r = await pRun('undo');
    out.patches.undo.push({ text: r[0].text, error: !!r[0].error });
  }
  const afterUndo = snap();
  out.patches.restored = {
    lossless: sameMap(platBase.files, afterUndo.files),
    htmlSame: platBase.html === afterUndo.html,
    files: Object.keys(afterUndo.files).sort(),
    spec: specLineOf(afterUndo.files['ARCHITECTURE.md']),
  };
  out.patches.undoEmpty = (await pRun('undo'))[0].text;

  // World size on the seeded RPG, with undo restoring the exact constant.
  self.toolrxWeb.reset();
  await pRun('build an rpg seed 7');
  const rpgBase = snap();
  const worldBefore = (/var SEED=\d+,SIZE=(\d+);/.exec(rpgBase.files['app.js']) || [])[1];
  const worldEdit = await pRun('make the world 120x120');
  const rpgAfter = snap();
  const worldAfter = (/var SEED=\d+,SIZE=(\d+);/.exec(rpgAfter.files['app.js']) || [])[1];
  await pRun('undo');
  const rpgBack = snap();
  out.patches.world = {
    via: worldEdit[0].via, text: worldEdit[0].text, before: worldBefore, after: worldAfter,
    spec: specLineOf(rpgAfter.files['ARCHITECTURE.md']),
    htmlMentions: rpgAfter.html.indexOf('120×120') !== -1,
    restored: (/var SEED=\d+,SIZE=(\d+);/.exec(rpgBack.files['app.js']) || [])[1],
    lossless: sameMap(rpgBase.files, rpgBack.files),
  };
  out.patches.worldReject = (await pRun('make the world 900x900'))[0].text;

  // Isometric camera on a 3D exploration build.
  self.toolrxWeb.reset();
  await pRun('build a low-poly exploration game');
  const isoBase = snap();
  const isoRun = await pRun('switch to isometric');
  const isoAfter = snap();
  out.patches.isometric = {
    via: isoRun[0].via, text: isoRun[0].text,
    fn: /function isometricCamera/.test(isoAfter.files['app.js']),
    syntax: jsCheck(isoAfter.files['app.js']),
    preview: /function isometricCamera/.test(isoAfter.html),
  };
  await pRun('undo');
  out.patches.isometricRestore = {
    fn: /function isometricCamera/.test(snap().files['app.js']),
    lossless: sameMap(isoBase.files, snap().files),
  };

  // make it 3d rebuilds through the templates and undo removes the engine.
  self.toolrxWeb.reset();
  await pRun('build a platformer game');
  const tdBase = snap();
  const tdRun = await pRun('make it 3d');
  const tdAfter = snap();
  out.patches.threeD = {
    via: tdRun[0].via, text: tdRun[0].text,
    files: Object.keys(tdAfter.files).sort(),
    hasEngine3d: 'engine3d.js' in tdAfter.files,
    hasEngine2d: 'engine2d.js' in tdAfter.files,
    spec: specLineOf(tdAfter.files['ARCHITECTURE.md']),
    preview: /toolrxEngine3d/.test(tdAfter.html),
    syntax: jsCheck(tdAfter.files['app.js']),
  };
  await pRun('undo');
  const tdBack = snap();
  out.patches.threeDUndo = {
    files: Object.keys(tdBack.files).sort(),
    hasEngine3d: 'engine3d.js' in tdBack.files,
    lossless: sameMap(tdBase.files, tdBack.files),
  };

  // Honest rejections for edits that do not fit the project.
  self.toolrxWeb.reset();
  await pRun('build a tower defense game');
  const tdTower = snap();
  const rejectDouble = await pRun('add double jump');
  out.patches.reject = {
    doubleJump: rejectDouble[0].text,
    unchanged: sameMap(tdTower.files, snap().files),
  };
  const bossRun = await pRun('add a boss');
  const bossAfter = snap();
  out.patches.boss = {
    via: bossRun[0].via, text: bossRun[0].text,
    fn: /function spawnBoss/.test(bossAfter.files['app.js']),
    syntax: jsCheck(bossAfter.files['app.js']),
    preview: /function spawnBoss/.test(bossAfter.html),
    spec: specLineOf(bossAfter.files['ARCHITECTURE.md']),
  };
  await pRun('undo');
  out.patches.bossUndo = sameMap(tdTower.files, snap().files);
  self.toolrxWeb.reset();
  await pRun('build a calculator app');
  out.patches.reject.calculator = (await pRun('add sound'))[0].text;
  self.toolrxWeb.reset();
  await pRun('build a top-down shooter game');
  out.patches.reject.shooterIso = (await pRun('switch to isometric'))[0].text;
  const routeEdit = await pRun('add a quest');
  const routeUndo = await pRun('undo');
  const routeLang = await self.toolrxSkills.runPrompt('switch to spanish', ctx);
  out.patches.route = {
    edit: routeEdit[0].via, undo: routeUndo[0].via, lang: routeLang[0].via,
  };

  // Step 30: a two-to-five patch bundle is atomic, growth adds real modules,
  // and the undo depth is configurable (default 16, here 3).
  out.growth = {};
  self.toolrxWeb.reset();
  await pRun('build a platformer game');
  const bundleBase = snap();
  const bundle = await pRun('add double jump and sound and a quest');
  const bundleAfter = snap();
  const bundleFail = await pRun('add double jump and a boss');
  const bundleFailAfter = snap();
  out.growth.bundle = {
    via: bundle[0].via, text: bundle[0].text,
    fns: ['doubleJump', 'soundToggle', 'questCheck']
      .map(fn => new RegExp('function ' + fn + '\\b').test(bundleAfter.files['app.js'])),
    files: Object.keys(bundleAfter.files).sort(),
    preview: /function doubleJump/.test(bundleAfter.html)
      && /function soundToggle/.test(bundleAfter.html),
    syntax: jsCheck(bundleAfter.files['app.js']),
    failVia: bundleFail[0].via,
    failText: bundleFail[0].text,
    failAtomic: sameMap(bundleAfter.files, bundleFailAfter.files),
    failKeptBoss: !/function spawnBoss/.test(bundleFailAfter.files['app.js']),
  };
  await pRun('undo');
  out.growth.bundleUndo = sameMap(bundleBase.files, snap().files);

  self.toolrxWeb.reset();
  await pRun('build a platformer game');
  const growBase = snap();
  const growRun = await pRun('grow project');
  const growAfter = snap();
  out.growth.grow = {
    via: growRun[0].via, text: growRun[0].text,
    files: Object.keys(growAfter.files).sort(),
    tags: ['core/state.js', 'ui/render.js', 'data/seed.js', 'content/seed.js']
      .every(p => growAfter.files['index.html'].indexOf('src="' + p + '"') >= 0),
    appModules: /toolrxProject\.modules/.test(growAfter.files['app.js']),
    coreSyntax: jsCheck(growAfter.files['core/state.js']),
    uiSyntax: jsCheck(growAfter.files['ui/render.js']),
    dataSyntax: jsCheck(growAfter.files['data/seed.js']),
    previewInlined: /toolrxCore/.test(growAfter.html) && /toolrxUI/.test(growAfter.html),
    previewExternal: /src=["'](?:core|ui|data|content)\//.test(growAfter.html),
    cssUntouched: growBase.files['styles.css'] === growAfter.files['styles.css'],
    tagsBeforeApp: growAfter.files['index.html'].indexOf('src="app.js"')
      > growAfter.files['index.html'].indexOf('src="core/state.js"'),
  };
  await pRun('undo');
  out.growth.growUndo = sameMap(growBase.files, snap().files);

  self.toolrxWeb.reset();
  await pRun('build a platformer game');
  const sysRun = await pRun('add crafting system');
  const sysAfter = snap();
  const expandRun = await pRun('expand module content');
  const expandAfter = snap();
  out.growth.system = {
    via: sysRun[0].via, text: sysRun[0].text,
    hasFile: !!sysAfter.files['systems/crafting.js'],
    registers: /registry\.register\("crafting"/.test(sysAfter.files['systems/crafting.js'] || ''),
    syntax: jsCheck(sysAfter.files['systems/crafting.js'] || ''),
    expandVia: expandRun[0].via,
    hasContentModule: !!expandAfter.files['content/seed.js'],
    tags: (expandAfter.files['index.html'].match(/src="(?:systems|content)\//g) || []).length,
    preview: /toolrxSystems/.test(expandAfter.html)
      && /toolrxContentIndex/.test(expandAfter.html),
  };
  try { localStorage.setItem('toolrx.undo.depth', '3'); } catch (e) { /* ignore */ }
  self.toolrxWeb.reset();
  await pRun('build a platformer game');
  const depthBase = snap();
  for (const q of ['add double jump', 'add sound', 'add a quest', 'make it harder']) {
    await pRun(q);
  }
  let undos = 0;
  for (let i = 0; i < 6; i++) {
    const r = await pRun('undo');
    if (/nothing to undo/.test(r[0].text)) break;
    undos++;
  }
  const depthAfter = snap();
  out.growth.undoDepth = {
    undos,
    notBase: !sameMap(depthBase.files, depthAfter.files),
    hasDoubleJump: /function doubleJump/.test(depthAfter.files['app.js']),
    hasHardMode: /HARD_MODE/.test(depthAfter.files['app.js']),
    hasSound: /function soundToggle/.test(depthAfter.files['app.js']),
    files: Object.keys(depthAfter.files).sort(),
  };
  try { localStorage.removeItem('toolrx.undo.depth'); } catch (e) { /* ignore */ }

  self.toolrxWeb.reset();
  out.sandbox.olympusBuild = (await self.toolrxWeb.prompt('build an rpg based on greek myth'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  ep = self.toolrxWeb.project();
  out.sandbox.afterOlympus = {
    slug: ep.slug, name: ep.name, title: h1(ep.html),
    js: self.toolrxWeb.projectFile(ep.slug, 'app.js'),
  };
  out.sandbox.olympusRename = (await self.toolrxWeb.prompt('rename it to egypt'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  ep = self.toolrxWeb.project();
  out.sandbox.afterOlympusRename = {
    slug: ep.slug, name: ep.name, title: h1(ep.html),
    js: self.toolrxWeb.projectFile(ep.slug, 'app.js'),
    bundled: ep.html,
  };
  out.wiki = await run('wikipedia ada lovelace');
  out.define = await run('define serendipity');
  out.weather = await run('weather in reykjavik');
  out.summaryChain = await run('wikipedia ada lovelace then summarize it');
  // Simulate a page reload: evaluate a fresh sandbox against the same
  // localStorage. The active project must resume in the preview.
  eval(fs.readFileSync(process.argv[4], 'utf8'));
  out.resume = {
    active: self.toolrxWeb.project() ? self.toolrxWeb.project().slug : '',
    html: self.toolrxWeb.defaultPreview(),
    title: self.toolrxWeb.preview().title,
  };
  // Two identical default RPG prompts in one session must create two projects
  // with different names; the previous install would have collapsed them.
  self.toolrxWeb.reset();
  await self.toolrxWeb.init('model.json');
  out.sandbox.defaults = {};
  out.sandbox.defaults.first = (await self.toolrxWeb.prompt('build an rpg'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  const def1 = self.toolrxWeb.project();
  out.sandbox.defaults.one = { slug: def1.slug, name: def1.name };
  out.sandbox.defaults.second = (await self.toolrxWeb.prompt('build an rpg'))
    .map(r => ({ via: r.via || '', text: r.text || '' }));
  const def2 = self.toolrxWeb.project();
  out.sandbox.defaults.two = { slug: def2.slug, name: def2.name };
  out.sandbox.defaults.count = self.toolrxWeb.projects().length;
  const dp = self.toolrxLang.detectProgramming;
  const dn = self.toolrxLang.detectNatural;
  out.language = {
    cpp: dp('#include <iostream>\nint main(){std::cout<<"hi";}'),
    csharp: dp('using System; namespace A { class B {} }'),
    rust: dp('fn main() { let mut x = 1; }'),
    python: dp('def f(x):\n    return x + 1'),
    typescript: dp('const x: string = "a"'),
    lua: dp('--[[ comment ]] local function f() end'),
    glsl: dp('#version 330\nvoid main(){gl_Position=vec4(0.0);}'),
    html: dp('<html><body><script>let x=1</script></body></html>'),
    es: dn('Hola, ¿puedes crear un juego de naves?'),
    fr: dn('Peux-tu construire un jeu de plates-formes ?'),
    de: dn('Baue ein 3D-RPG mit 5 Quests.'),
    hi: dn('क्या आप एक शूटर गेम बना सकते हैं?'),
    ja: dn('三角形の面積を計算して'),
    han: dn('漢字文章'),
    one: dn('no'),
    english: dn('what time is it'),
    normalized: [
      self.toolrxLang.normalize('Hola, ¿puedes crear un juego de naves?'),
      self.toolrxLang.normalize('Peux-tu construire un jeu de plates-formes ?'),
      self.toolrxLang.normalize('Baue ein 3D-RPG mit 5 Quests.'),
      self.toolrxLang.normalize('5 किमी को मील में बदलो'),
      self.toolrxLang.normalize('ゲームを作って'),
    ],
  };
  out.library = {
    stats: (await run('library stats'))[0],
    find: (await run('find a book about shaders'))[0],
    findPcg: (await run('what do i have on procedural generation'))[0],
    language: (await run('list books by language c++'))[0],
    level: (await run('list beginner books'))[0],
    missing: (await run('find a book about quaternions'))[0],
    next: (await run('what should i read next'))[0],
    after: (await run('what should i read after programming-2d-games'))[0],
    gaps: (await run('library gaps'))[0],
    detect: (await run('what programming language is this: #include <iostream>'))[0],
    natural: (await run('what natural language is this: Hola, ¿puedes crear un juego de naves?'))[0],
    chain: await run('library stats then find a book about pcg'),
  };
  out.libraryPanel = (() => {
    const all = self.toolrxSkills.libraryPanel('', { limit: 20 });
    const hit = self.toolrxSkills.libraryPanel('shaders', { limit: 5 });
    const beginner = self.toolrxSkills.libraryPanel('', {
      limit: 20,
      keep: r => ((r.classification || {}).level === 'beginner'),
    });
    const one = self.toolrxSkills.libraryPanel('', {
      limit: 20,
      keep: r => r.id !== 'cpp-complete-guide',
    });
    return {
      total: all.total, rows: all.rows.length,
      first: all.rows[0],
      hitTotal: hit.total, hit: hit.rows[0],
      beginner: beginner.total, filtered: one.total,
    };
  })();
  out.langIntents = FIXTURES.intents.map(f => {
    const n = self.toolrxLang.normalize(f.text);
    return {
      lang: f.lang, text: f.text, want: f.want,
      got: n.text, hit: n.lang, interpreted: !!n.interpreted,
    };
  });
  out.reply = {};
  out.reply.set = (await run('reply in spanish'))[0];
  out.reply.stored = global.localStorage.getItem('toolrx.reply.lang');
  out.reply.greeting = self.toolrxSkills.chat('hola', ctx);
  out.reply.localized = (await run('Hola, ¿puedes crear un juego de naves?'))[0];
  out.reply.status = (await run('what language are you replying in'))[0];
  out.reply.noCommand = (await self.toolrxSkills.runPrompt(
    'zzzznotacommand', Object.assign({}, ctx, { fallback: null })))[0];
  out.reply.bad = (await run('reply in klingon'))[0];
  out.reply.off = (await run('reply in english'))[0];
  out.reply.after = global.localStorage.getItem('toolrx.reply.lang');
  out.reply.alias = self.toolrxLang.replyLang('Español');
  out.reply.fallback = self.toolrxLang.say('xx', 'greeting');
  out.reply.packs = ['en', 'es', 'fr', 'de', 'hi', 'ja'].map(c => ({
    code: c, name: self.toolrxLang.replyName(c),
    greeting: self.toolrxLang.say(c, 'greeting'),
    replyIn: self.toolrxLang.say(c, 'reply_in'),
  }));
  out.langFixtures = {
    programming: FIXTURES.programming.map(f => ({
      text: f.text, lang: f.lang, hit: dp(f.text),
    })),
    natural: FIXTURES.natural.map(f => ({
      text: f.text, lang: f.lang, hit: dn(f.text),
    })),
    ambiguous: FIXTURES.ambiguous.map(f => ({
      text: f.text, also: f.also, hit: dn(f.text),
    })),
    unknown: FIXTURES.unknown.map(f => ({
      text: f.text, hit: dn(f.text),
    })),
  };
  out.langPerf = (() => {
    const small = '#include <iostream>\nint main(){std::cout<<"hi";}\n'.repeat(20);
    const large = small.repeat(64);
    const timed = (fn, text) => {
      for (let i = 0; i < 3; i++) fn(text);
      const t0 = performance.now();
      fn(text);
      return +(performance.now() - t0).toFixed(3);
    };
    return {
      smallBytes: small.length, largeBytes: large.length,
      smallMs: timed(dp, small), largeMs: timed(dp, large),
    };
  })();
  out.libraryScale = (() => {
    const lib = self.toolrxSkills.library();
    const original = lib.records;
    const many = [];
    for (let i = 0; i < 10000; i++) {
      many.push({
        id: 'bench-' + i, title: 'Benchmark Book ' + i, authors: [], year: 2020,
        parts: [],
        classification: {
          topics: [i % 2 ? 'shaders' : 'cpp'],
          programming_languages: ['cpp'], natural_languages: ['en'],
        },
        reading: { status: 'unread', priority: 1, next: [] },
        search: {
          aliases: ['bench ' + i], keywords: ['synthetic ' + i],
          summary: 'Synthetic record ' + i,
        },
      });
    }
    lib.records = many;
    const timed = (q) => {
      let best = Infinity;
      for (let i = 0; i < 15; i++) {
        const t0 = performance.now();
        self.toolrxSkills.librarySearch(q, 5);
        best = Math.min(best, performance.now() - t0);
      }
      return +best.toFixed(3);
    };
    const allMs = timed('synthetic');
    const missMs = timed('zzzznot');
    const found = /Benchmark Book 9999/.test(
      self.toolrxSkills.librarySearch('synthetic 9999', 5));
    let panelMs = Infinity, panelRows = 0;
    for (let i = 0; i < 10; i++) {
      const t0 = performance.now();
      const panel = self.toolrxSkills.libraryPanel('synthetic', { limit: 60 });
      panelMs = Math.min(panelMs, performance.now() - t0);
      panelRows = panel.rows.length;
    }
    lib.records = original;
    return {
      records: many.length, allMs: allMs, missMs: missMs, found: found,
      panelMs: +panelMs.toFixed(3), panelRows: panelRows,
    };
  })();
  console.log(JSON.stringify(out));
})();
"""


@unittest.skipUnless(NODE, "node is not installed")
class SkillsBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proc = subprocess.run(
            [NODE, "-e", JS,
             os.path.join(ROOT, "toolrx", "web", "commands.json"),
             os.path.join(ROOT, "toolrx", "web", "skills.js"),
             os.path.join(ROOT, "toolrx", "web", "templates.js"),
             os.path.join(ROOT, "toolrx", "web", "sandbox.js"),
             os.path.join(ROOT, "toolrx", "web", "i18n.json"),
             os.path.join(ROOT, "tests", "lang_fixtures.json")],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-3000:])
        cls.out = json.loads(proc.stdout)

    def test_library_loaded(self):
        self.assertGreaterEqual(self.out["count"], 2500)
        self.assertGreaterEqual(len(self.out["catalog"]), 1)
        for row in self.out["catalog"]:
            self.assertTrue("build" in row["d"].lower() or row["op"] == "build", row)
        self.assertTrue(all(r["c"] == "memory" for r in self.out["catalogCat"]))
        self.assertGreaterEqual(len(self.out["catalogCat"]), 40)
        self.assertEqual(self.out["catalogEmpty"], [])
        rpg = self.out["catalogRpg"]
        self.assertTrue(rpg)
        self.assertTrue(all("rpg" in r["d"].lower() for r in rpg))
        self.assertEqual(len({r["d"] for r in rpg}), len(rpg))
        tetris = self.out["catalogFill"]
        self.assertTrue(tetris)
        self.assertTrue(all("tetris" in r["d"].lower() for r in tetris))
        self.assertTrue(all("{" not in r["d"] for r in tetris))

    def test_programming_language_detection(self):
        lang = self.out["language"]
        cases = {
            "cpp": ("cpp", 0.90),
            "csharp": ("csharp", 0.80),
            "rust": ("rust", 0.90),
            "python": ("python", 0.90),
            "typescript": ("typescript", 0.80),
            "lua": ("lua", 0.85),
            "glsl": ("glsl", 0.90),
        }
        for key, (code, floor) in cases.items():
            hit = lang[key]
            self.assertEqual(hit["lang"], code, key)
            self.assertGreaterEqual(hit["confidence"], floor, key)
        html = lang["html"]
        self.assertEqual(html["lang"], "html")
        self.assertIn("javascript", html["alternatives"])

    def test_natural_language_detection_and_ambiguity(self):
        lang = self.out["language"]
        for key, code in (("es", "es"), ("fr", "fr"), ("de", "de"),
                          ("hi", "hi"), ("ja", "ja"), ("english", "en")):
            hit = lang[key]
            self.assertEqual(hit["lang"], code, key)
            self.assertGreaterEqual(hit["confidence"], 0.80, key)
        han = lang["han"]
        self.assertIsNone(han["lang"])
        self.assertIn("zh", han["ambiguous"])
        self.assertIn("ja", han["ambiguous"])
        self.assertEqual(lang["one"]["lang"], None)

    def test_programming_fixture_matrix(self):
        rows = self.out["langFixtures"]["programming"]
        self.assertGreaterEqual(len(rows), 40)
        for row in rows:
            self.assertEqual(row["hit"]["lang"], row["lang"], row["text"])

    def test_natural_fixture_matrix(self):
        rows = self.out["langFixtures"]["natural"]
        self.assertGreaterEqual(len(rows), 30)
        for row in rows:
            self.assertEqual(row["hit"]["lang"], row["lang"], row["text"])

    def test_ambiguous_and_unknown_stay_honest(self):
        for row in self.out["langFixtures"]["ambiguous"]:
            self.assertIsNone(row["hit"]["lang"], row["text"])
            for code in row["also"]:
                self.assertIn(code, row["hit"]["ambiguous"])
        for row in self.out["langFixtures"]["unknown"]:
            self.assertIsNone(row["hit"]["lang"], row["text"])

    def test_language_detection_speed(self):
        perf = self.out["langPerf"]
        self.assertGreaterEqual(perf["smallBytes"], 500)
        self.assertGreaterEqual(perf["largeBytes"], 50000)
        self.assertLess(perf["smallMs"], 5, perf)
        self.assertLess(perf["largeMs"], 20, perf)

    def test_localized_intents_normalize_to_english(self):
        cases = [
            ("build a shooter game", "es"),
            ("build a platformer game", "fr"),
            ("build a 3d rpg", "de"),
            ("convert 5 km to miles", "hi"),
            ("build a game", "ja"),
        ]
        for hit, (text, code) in zip(self.out["language"]["normalized"], cases):
            self.assertTrue(hit["interpreted"], hit)
            self.assertEqual(hit["text"], text, hit)
            self.assertEqual(hit["lang"], code, hit)

    def test_localized_intents_cover_priority_languages(self):
        rows = self.out["langIntents"]
        counts = {}
        for row in rows:
            self.assertTrue(row["interpreted"], row)
            self.assertEqual(row["got"], row["want"], row)
            self.assertEqual(row["hit"], row["lang"], row)
            counts[row["lang"]] = counts.get(row["lang"], 0) + 1
        self.assertGreaterEqual(len(rows), 75)
        for code in ("es", "fr", "de", "hi", "ja"):
            self.assertGreaterEqual(counts.get(code, 0), 15, code)

    def test_reply_language_preference_persists(self):
        r = self.out["reply"]
        self.assertEqual(r["stored"], "es")
        self.assertEqual(r["alias"], "es")
        self.assertIn("respondiendo en Spanish", r["set"]["text"])
        self.assertIn("Hola", r["greeting"])
        self.assertIn("interpretado como", r["localized"]["text"])
        self.assertIn("build a shooter game", r["localized"]["text"])
        self.assertIn("respondiendo en", r["status"]["text"])
        self.assertIn("ningún comando", r["noCommand"]["text"])
        self.assertTrue(r["bad"]["error"])
        self.assertIn("desconocido", r["bad"]["text"])
        self.assertEqual(r["after"], "en")
        en = next(p for p in r["packs"] if p["code"] == "en")
        self.assertEqual(r["fallback"], en["greeting"])
        for pack in r["packs"]:
            self.assertTrue(pack["greeting"], pack)
            self.assertIn("{lang}", pack["replyIn"], pack)

    def test_archive_catalog_commands(self):
        lib = self.out["library"]
        self.assertIn("10 records", lib["stats"]["text"])
        self.assertIn("cpp", lib["stats"]["text"])
        self.assertIn("Developing Simple Games with OpenGL", lib["find"]["text"])
        self.assertIn("why:", lib["find"]["text"])
        self.assertIn("Procedural Content Generation", lib["findPcg"]["text"])
        self.assertIn("books tagged cpp", lib["language"]["text"])
        self.assertIn("books at beginner level", lib["level"]["text"])
        self.assertIn("A Complete Guide to Programming in C++", lib["level"]["text"])
        self.assertIn("not in the archive", lib["missing"]["text"])
        self.assertIn("next up", lib["next"]["text"])
        self.assertIn("Developing Simple Games with OpenGL", lib["after"]["text"])
        self.assertIn("library gaps:", lib["gaps"]["text"])
        self.assertIn("thin language coverage", lib["gaps"]["text"])
        self.assertIn("C++", lib["detect"]["text"])
        self.assertIn("Spanish", lib["natural"]["text"])
        self.assertEqual(len(lib["chain"]), 2)
        self.assertIn("Procedural Content Generation", lib["chain"][1]["text"])
        self.assertFalse(lib["find"]["error"])

    def test_library_panel_rows_and_filters(self):
        p = self.out["libraryPanel"]
        self.assertEqual(p["total"], 10)
        self.assertEqual(p["rows"], 10)
        self.assertEqual(p["first"]["level"], "beginner")
        self.assertIn("cpp", p["first"]["programming"])
        self.assertEqual(p["hitTotal"], 1)
        self.assertIn("shaders", p["hit"]["topics"])
        self.assertTrue(p["hit"]["reason"])
        self.assertGreaterEqual(p["beginner"], 7)
        self.assertEqual(p["filtered"], 9)

    def test_archive_search_scales_to_ten_thousand_records(self):
        scale = self.out["libraryScale"]
        self.assertEqual(scale["records"], 10000)
        self.assertTrue(scale["found"])
        self.assertLess(scale["missMs"], 5, scale)
        self.assertLess(scale["allMs"], 10, scale)
        self.assertEqual(scale["panelRows"], 60, scale)
        self.assertLess(scale["panelMs"], 10, scale)

    def test_build_spec_parses_dimension_view_art_scale_seed(self):
        s = self.out["spec"]
        self.assertEqual(s["p3d"]["spec"]["dim"], "3D")
        self.assertEqual(s["p3d"]["spec"]["view"], "side-scroller")
        self.assertEqual(s["isoRpg"]["spec"]["view"], "isometric")
        self.assertEqual(s["isoRpg"]["spec"]["scale"], "3 quests")
        self.assertEqual(s["shooter"]["spec"]["view"], "top-down")
        self.assertEqual(s["shooter"]["spec"]["scale"], "3 levels")
        self.assertEqual(s["maze"]["spec"]["view"], "first-person")
        self.assertEqual(s["maze"]["spec"]["dim"], "3D")
        self.assertEqual(s["maze"]["spec"]["art"], "low-poly")
        self.assertEqual(s["racing"]["spec"]["seed"], 42)
        self.assertEqual(s["racing"]["spec"]["theme"], "night")
        self.assertEqual(s["seed"]["spec"]["seed"], 42)

    def test_spec_is_deterministic_and_explains_closest_match(self):
        self.assertEqual(self.out["spec"]["shooter"]["spec"],
                         self.out["spec"]["repeat"]["spec"])
        self.assertEqual(self.out["spec"]["tower"]["spec"]["genre"], "towerdefense")
        self.assertNotIn("requested", self.out["spec"]["tower"]["line"])
        self.assertIn("seed", self.out["spec"]["rpg"]["line"])

    def test_engine_3d_projects_ship_the_shared_runtime(self):
        for kind in ("platformer", "maze", "racer"):
            e = self.out["engine3d"][kind]
            self.assertIn("engine3d.js", e["files"])
            self.assertIn('src="engine3d.js"', e["html"])
            self.assertEqual(e["html"].count('src="engine3d.js"'), 1,
                             "engine3d tag must appear once or the preview double-inlines")
            self.assertNotIn('src="engine2d.js"', e["html"])
            self.assertIn("3D", e["spec"])
            self.assertIn("toolrxEngine3d", e["src"])
            self.assertIn("3d", e["spec"].lower())

    def test_engine_3d_falls_back_to_canvas_and_draws(self):
        r = self.out["engine3dRuntime"]
        self.assertEqual(r["mode"], "canvas", "no WebGL should select the 2d fallback")
        self.assertGreater(r["update"], 0, "3d loop never called E.update")
        self.assertGreater(r["draw"], 0, "3d loop never called E.draw")
        self.assertGreater(r["fills"], 0, "3d fallback never filled a polygon")

    def test_engine_projects_ship_the_shared_runtime(self):
        for kind in ("platformer", "snake", "breakout", "shooter", "racer"):
            e = self.out["engine"][kind]
            self.assertIn("engine2d.js", e["files"])
            self.assertIn('src="engine2d.js"', e["html"])
            self.assertEqual(e["html"].count('src="engine2d.js"'), 1,
                             "engine tag must appear once or the preview double-inlines")
            self.assertGreater(len(e["src"]), 4000)
            self.assertIn("toolrxEngine2d", e["src"])

    def test_engine_runs_handlers_assigned_after_create(self):
        r = self.out["engineRuntime"]
        self.assertGreater(r["update"], 0, "engine loop never called E.update")
        self.assertGreater(r["draw"], 0, "engine loop never called E.draw")
        self.assertTrue(r["ctx"], "E.draw should receive the 2d context")

    def test_preview_inlines_the_engine_and_keeps_files(self):
        e = self.out["sandbox"]["engine"]
        self.assertIn("engine2d.js", e["files"])
        self.assertTrue(e["previewHasEngine"])
        self.assertFalse(e["previewHasExternalTag"])
        self.assertIn("engine2d.js", e["readme"])
        self.assertIn("engine2d.js", e["arch"])
        self.assertIn("spec ·", self.out["sandbox"]["engineBuild"][0]["text"])

    def test_preview_inlines_the_3d_engine(self):
        e = self.out["sandbox"]["engine3d"]
        self.assertIn("engine3d.js", e["files"])
        self.assertNotIn("engine2d.js", e["files"])
        self.assertTrue(e["previewHasEngine"], "3d preview must inline the runtime")
        self.assertFalse(e["previewHasExternalTag"], "preview cannot fetch external files")
        self.assertTrue(e["previewHasCreate"])

    def test_rpg_world_is_large_seeded_and_reproducible(self):
        w = self.out["rpgWorld"]
        self.assertGreaterEqual(w["size"], 64)
        self.assertGreaterEqual(w["towns"], 3)
        self.assertGreaterEqual(w["npcs"], 6)
        self.assertGreaterEqual(w["quests"], 3)
        self.assertGreaterEqual(w["enemies"], 18)
        self.assertGreaterEqual(w["dungeonRooms"], 4)
        self.assertTrue(w["hasBoss"])
        self.assertTrue(w["startWalkable"])
        self.assertTrue(w["sameTiles"], "same seed must reproduce the map")
        self.assertTrue(w["sameNpcs"], "same seed must reproduce the cast")
        self.assertTrue(w["diffTiles"], "different seeds must differ")
        self.assertGreaterEqual(w["bigSize"], 96)
        self.assertGreaterEqual(w["bigTowns"], 4)
        self.assertGreaterEqual(w["questGivers"], 3)
        self.assertEqual(len(set(w["townNames"])), len(w["townNames"]))

    def test_rpg_project_ships_worldgen_and_runtime(self):
        r = self.out["rpgProject"]
        for f in ("engine2d.js", "worldgen.js", "rpg2.js", "app.js"):
            self.assertIn(f, r["files"])
        self.assertTrue(r["hasWorldgenTag"])
        self.assertTrue(r["hasRpgTag"])
        self.assertEqual(r["engineTagOnce"], 1,
                         "engine2d tag must appear once or preview double-inlines")
        self.assertTrue(r["appCreates"])
        self.assertTrue(r["appHasBoss"])
        self.assertTrue(r["worldSrc"])

    def test_rpg_runtime_draws_and_saves(self):
        r = self.out["rpgRuntime"]
        self.assertGreater(r["fills"], 0, "rpg drew no tiles")
        self.assertGreater(r["texts"], 0, "rpg drew no hud text")
        self.assertEqual(r["inDungeon"], "dungeon")
        self.assertEqual(r["back"], "overworld")
        self.assertTrue(r["saved"])
        self.assertTrue(r["loaded"])
        self.assertGreaterEqual(r["quests"], 3)
        self.assertEqual(r["mode"], "play")
        self.assertTrue(r["slots"][1])

    def test_rpg_preview_inlines_all_shared_runtimes(self):
        r = self.out["sandbox"]["rpgPreview"]
        for f in ("engine2d.js", "worldgen.js", "rpg2.js"):
            self.assertIn(f, r["files"])
        self.assertTrue(r["hasWorldgen"])
        self.assertTrue(r["hasRpg"])
        self.assertFalse(r["external"], "previews cannot fetch shared runtimes")

    def test_math_prompts(self):
        self.assertEqual(self.out["multiply"][0]["text"], "28140")
        self.assertEqual(self.out["square"][0]["text"], "4489")
        self.assertFalse(self.out["multiply"][0]["error"])

    def test_every_step_reports_its_own_timing(self):
        for key in ("multiply", "square", "chain", "build"):
            for step in self.out[key]:
                self.assertIsInstance(step["ms"], (int, float), key)
                self.assertGreaterEqual(step["ms"], 0, key)

    def test_multi_step_threads_previous_output(self):
        steps = self.out["chain"]
        self.assertEqual(len(steps), 2)
        self.assertIn("3.1068", steps[0]["text"])
        value = float(steps[1]["text"])
        self.assertAlmostEqual(value, 3.1068559612 ** 2, places=4)

    def test_previous_file_feeds_text_count(self):
        steps = self.out["read"]
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[1]["text"], "5 words")

    def test_pronoun_uses_previous_result(self):
        steps = self.out["pronoun"]
        self.assertEqual(steps[0]["text"], "Paris")
        self.assertEqual(steps[1]["text"], "PARIS")

    def test_planner_splits_on_semicolon_and_arrow(self):
        self.assertEqual(self.out["steps"], ["one", "two", "three", "four"])

    def test_limits_match_the_shared_contract(self):
        self.assertEqual(self.out["limits"], {"single": 2000, "plan": 8000, "steps": 40})

    def test_split_info_handles_connectors_lines_and_sentences(self):
        info = self.out["splitInfo"]
        self.assertEqual(info["connector"]["steps"],
                         ["one", "two", "three", "four"])
        self.assertEqual(info["numbered"]["steps"],
                         ["read notes.txt", "count the words"])
        self.assertEqual(info["multi"]["steps"],
                         ["read notes.txt", "count the words"])
        sentence = ("list the files in the current directory and show the uptime "
                    "for this machine right now.")
        self.assertEqual(info["sentences"]["steps"], [sentence] * 3)
        self.assertTrue(info["long"]["plan"])
        self.assertGreater(info["long"]["total"], 1)
        self.assertTrue(all(len(s) <= 2000 for s in info["long"]["steps"]))

    def test_plan_preview_lists_steps_before_running(self):
        preview = self.out["planPreview"]
        self.assertTrue(preview["multi"]["plan"])
        self.assertFalse(preview["multi"]["blocked"])
        self.assertEqual([s["text"] for s in preview["multi"]["steps"]],
                         ["read notes.txt", "count the words"])
        self.assertEqual([s["exact"] for s in preview["multi"]["steps"]], [False, True])
        self.assertFalse(preview["single"]["plan"])
        self.assertTrue(preview["tooLong"]["blocked"])
        self.assertIn("8000", preview["tooLong"]["reason"])
        self.assertTrue(preview["tooMany"]["blocked"])
        self.assertIn("40", preview["tooMany"]["reason"])

    def test_over_cap_prompt_returns_one_limit_error(self):
        self.assertEqual(len(self.out["limitRun"]), 1)
        self.assertEqual(self.out["limitRun"][0]["via"], "limit")
        self.assertTrue(self.out["limitRun"][0]["error"])
        self.assertIn("8000", self.out["limitRun"][0]["text"])

    def test_plan_stops_at_the_first_failed_step(self):
        steps = self.out["planStop"]
        self.assertEqual(len(steps), 2, steps)
        self.assertFalse(steps[0]["error"])
        self.assertEqual(steps[0]["text"], "42")
        self.assertTrue(steps[1]["error"])

    def test_long_compositions_keep_kind_and_modifiers(self):
        cases = {
            "build a huge space rpg game with crafting":
                ("rpg", ["huge space", "crafting"]),
            "build a small cyberpunk platformer game":
                ("platformer", ["small cyberpunk"]),
            "build a medieval roguelike game with quests":
                ("roguelike", ["medieval", "quests"]),
            "build an epic underwater farming sim with weather":
                ("farming sim", ["epic underwater", "weather"]),
            "build a sprawling astral exploration game with dialogue trees":
                ("exploration", ["sprawling astral", "dialogue trees"]),
            "build a pirate tower defense game":
                ("tower defense", ["pirate"]),
            "build a pixel art tetris game":
                ("tetris", ["pixel art"]),
            "build a large maze game":
                ("maze", ["large"]),
        }
        for query, (kind, words) in cases.items():
            hit = self.out["compose"][query]
            self.assertTrue(hit, query)
            self.assertEqual(hit["op"], "build", query)
            self.assertEqual(hit["args"].get("kind"), kind, query)
            desc = hit["args"].get("desc", "")
            for word in words:
                self.assertIn(word, desc, f"{query}: {desc!r}")
        self.assertFalse(self.out["composeBuild"][0]["error"])
        self.assertEqual(self.out["composeKind"], "rpg")

    def test_build_spec_v3_parses_features_counts_subtheme_and_size(self):
        s = self.out["specV3"]["spec"]
        self.assertEqual(s["features"], ["crafting"])
        self.assertEqual(s["subtheme"], "nebula")
        self.assertEqual(self.out["specV3"]["tightSubtheme"], "nebula")
        self.assertEqual(s["size"], 96)
        self.assertEqual(s["levels"], 3)
        self.assertEqual(s["counts"], {"levels": 3, "quests": 6, "npcs": 8,
                                       "enemies": 12, "items": 4})
        line = self.out["specV3"]["line"]
        for bit in ("features crafting", "6 quests", "8 npcs", "12 enemies",
                    "4 items", "3 levels", "96×96", "sub-theme nebula"):
            self.assertIn(bit, line)

    def test_content_module_is_real_seeded_and_deterministic(self):
        r = self.out["specV3"]
        self.assertEqual(r["files"], ["ARCHITECTURE.md", "README.md", "app.js",
                                      "content.js", "engine2d.js", "index.html",
                                      "rpg2.js", "styles.css", "worldgen.js"])
        self.assertTrue(r["hasTag"])
        self.assertTrue(r["tagBeforeApp"])
        self.assertTrue(r["summary"])
        c = r["content"]
        self.assertEqual(c["version"], 3)
        self.assertEqual(c["seed"], r["spec"]["seed"])
        self.assertEqual(c["features"], ["crafting"])
        self.assertEqual(c["subtheme"], "nebula")
        self.assertEqual(c["size"], 96)
        self.assertEqual(len(c["levels"]), 3)
        self.assertEqual(len(c["quests"]), 6)
        self.assertEqual(len(c["npcs"]), 8)
        self.assertEqual(len(c["enemies"]), 12)
        self.assertEqual(len(c["items"]), 4)
        self.assertTrue(r["same"], "same request must produce the same content tree")
        self.assertIn("## Content module", r["readme"])
        self.assertIn("content.js", r["readme"])
        self.assertIn("content.js", r["arch"])

    def test_plain_builds_stay_five_files_without_content(self):
        r = self.out["specV3"]
        self.assertEqual(r["plainFiles"],
                         ["ARCHITECTURE.md", "README.md", "app.js", "index.html",
                          "styles.css"])
        self.assertFalse(r["plainHasContent"])

    def test_rpg_passes_world_size_and_counts_to_worldgen(self):
        self.assertTrue(self.out["specV3"]["worldTag"])

    def test_worldgen_honours_explicit_counts(self):
        w = self.out["contentWorld"]
        self.assertEqual(w["towns"], 4)
        self.assertGreater(w["enemies"], 0)
        self.assertLessEqual(w["enemies"], 9)
        self.assertEqual(w["npcs"], 5)
        self.assertEqual(w["quests"], 7)
        self.assertTrue(w["same"], "counts must replay exactly for one seed")
        self.assertTrue(w["npcIdsUnique"])
        self.assertEqual(w["baseTowns"], 5, "no counts keeps the size default")
        self.assertGreaterEqual(w["baseEnemies"], 18)

    def test_sandbox_preview_inlines_content_js(self):
        c = self.out["sandbox"]["content"]
        self.assertTrue(c["build"][0].get("text"))
        self.assertTrue(c["project"]["hasContent"], c["project"]["files"])
        self.assertTrue(c["project"]["previewHasData"])
        self.assertFalse(c["project"]["previewExternal"],
                         "previews cannot fetch content.js")

    def test_build_produces_a_real_page(self):
        self.assertTrue(self.out["buildHtml"].startswith("<!doctype html>"))
        self.assertIn("<title>Calculator", self.out["buildHtml"])
        self.assertIn("</html>", self.out["buildHtml"])
        self.assertIn("<title>Todo list", self.out["todoHtml"])
        self.assertFalse(self.out["build"][0]["error"])

    def test_build_is_deterministic(self):
        self.assertTrue(self.out["buildSame"], "same prompt produced a different page")

    def test_build_writes_a_multi_file_project(self):
        files = self.out["calcFiles"]
        self.assertEqual(files, ["ARCHITECTURE.md", "README.md", "app.js", "index.html", "styles.css"])
        # styles and script must be linked, not inlined
        html = self.out["buildHtml"]
        self.assertIn('href="styles.css"', html)
        self.assertIn('src="app.js"', html)
        self.assertNotIn("<style>", html)

    def test_games_build_with_real_files(self):
        expected = {"rpg", "platformer", "snake", "breakout", "pong", "2048",
                    "minesweeper", "tetris", "maze", "adventure", "typing"}
        for name in expected:
            g = self.out["games"][name]
            self.assertTrue(g["ok"], name)
            self.assertEqual(g["kind"], name, name)
            self.assertIn("index.html", g["files"], name)
            self.assertIn("app.js", g["files"], name)
            self.assertGreater(g["html"], 1000, name)

    def test_step_18_genres_build_real_offline_projects(self):
        expected = {
            "twinstick": ("Twin-stick arena", "engine2d.js"),
            "roguelike": ("Roguelike dungeon", "engine2d.js"),
            "towerdefense": ("Tower defense", "engine2d.js"),
            "merges": ("Merge garden", "engine2d.js"),
            "farmingsim": ("Harvest days", "engine2d.js"),
            "cardbattler": ("Card battler", None),
            "rhythm": ("Rhythm lanes", "engine2d.js"),
            "explore": ("Low-poly island", "engine3d.js"),
            "waveshooter": ("Wave shooter", "engine3d.js"),
            "builder": ("Block builder", "engine3d.js"),
        }
        titles = set()
        for name, (title, engine) in expected.items():
            g = self.out["genres"][name]
            self.assertTrue(g["ok"], name)
            self.assertEqual(g["via"], "build", name)
            self.assertEqual(g["kind"], name, name)
            self.assertEqual(g["title"], title, name)
            self.assertEqual(g["syntax"], "ok", name)
            self.assertGreater(g["html"], 1000, name)
            for f in ("index.html", "styles.css", "app.js", "README.md", "ARCHITECTURE.md"):
                self.assertIn(f, g["files"], name)
            if engine:
                self.assertIn(engine, g["files"], name)
            else:
                self.assertNotIn("engine2d.js", g["files"], name)
                self.assertNotIn("engine3d.js", g["files"], name)
            self.assertIn("## State", g["arch"], name)
            self.assertIn("## Extension points", g["arch"], name)
            titles.add(g["title"])
        self.assertEqual(len(titles), len(expected))

    def test_step_18_genre_plans_print_the_brief(self):
        expected = {
            'plan a twin-stick shooter': 'twin-stick arena',
            'plan a roguelike': 'roguelike dungeon',
            'plan a tower defense': 'tower defense',
            'plan a match-3 puzzle': 'merge garden',
            'plan a farming sim': 'harvest days',
            'plan a card battler': 'card battler',
            'plan a rhythm game': 'rhythm lanes',
            'plan a low-poly exploration': 'low-poly island',
            'plan a wave shooter': 'wave shooter',
            'plan a block builder': 'block builder',
        }
        for q, name in expected.items():
            p = self.out["genrePlans"][q]
            self.assertTrue(p["ok"], q)
            self.assertEqual(p["via"], "plan", q)
            low = p["text"].lower()
            self.assertIn(name, low, q)
            self.assertIn("state", low, q)
            self.assertIn("build order", low, q)

    def test_3d_build_variant_has_real_3d_markers(self):
        v = self.out["variants"]["build a tetris game with 3d elements"]
        self.assertTrue(v["ok"])
        self.assertEqual(v["kind"], "tetris")
        self.assertEqual(v["title"], "Tetris 3D")
        self.assertIn("perspective", v["css"])
        self.assertIn("rotateX", v["css"])
        self.assertNotIn("canvas{transform:none}", v["css"])
        # the renderer projects cuboids and paints depth-sorted faces
        self.assertIn("D3=true", v["js"])
        self.assertIn("function p3", v["js"])
        self.assertIn("function addCube", v["js"])
        self.assertIn("faces.sort", v["js"])
        self.assertIn("draw3d()", v["js"])

    def test_rpg_settings_produce_different_previews(self):
        arthur = self.out["variants"]["build an rpg based on king arthur"]
        india = self.out["variants"]["build an rpg based on india"]
        self.assertEqual(arthur["kind"], "rpg")
        self.assertEqual(india["kind"], "rpg")
        self.assertEqual(arthur["title"], "Camelot RPG")
        self.assertEqual(india["title"], "Bharata RPG")
        self.assertNotEqual(arthur["html"], india["html"])
        self.assertIn("Black Knight", arthur["js"])
        self.assertIn("Asura King", india["js"])
        self.assertIn("#2f5d43", arthur["css"] + arthur["js"])
        self.assertIn("#3f6b4a", india["css"] + india["js"])

    def test_additional_rpg_packs_are_distinct(self):
        expected = {
            "build an rpg based on greek myth": ("Olympus RPG", "the Titan", "#4f6b4a"),
            "build an rpg based on japan": ("Sakura RPG", "the Shogun", "#8a4f6b"),
            "build an rpg based on egypt": ("Nile RPG", "the Pharaoh", "#5f6b2f"),
            "build an rpg based on the ocean": ("Abyss RPG", "the Leviathan", "#2a6b6b"),
            "build an rpg based on the wild west": ("Frontier RPG", "the Outlaw", "#5e4a2a"),
            "build an rpg based on cyberpunk": ("Neon RPG", "the Architect", "#4c2f6b"),
            "build an rpg noir detective": ("Rain City RPG", "the Fixer", "#36424a"),
        }
        titles = set()
        pages = set()
        for prompt, (title, marker, colour) in expected.items():
            t = self.out["themes"][prompt]
            self.assertTrue(t["ok"], prompt)
            self.assertEqual(t["kind"], "rpg", prompt)
            self.assertEqual(t["title"], title, prompt)
            self.assertIn(marker, t["js"], prompt)
            self.assertIn(colour, t["css"] + t["js"], prompt)
            titles.add(t["title"])
            pages.add(t["html"])
        self.assertEqual(len(titles), len(expected))
        self.assertEqual(len(pages), len(expected))

    def test_rpg_pack_list_and_default_titles_advance(self):
        d = self.out["rpgDefaults"]
        self.assertEqual(len(self.out["rpgPacks"]), 20)
        self.assertEqual(len(set(self.out["rpgPacks"])), 20)
        self.assertEqual(d["uniqueTitles"], 10, d["titles"])
        self.assertEqual(d["uniqueSlugs"], 10, d["slugs"])
        self.assertEqual(d["uniqueHtml"], 10)
        self.assertRegex(d["grammar"], r"^[A-Z][a-z]+ [A-Z][a-z]+ RPG$")
        self.assertEqual(d["seed7"]["seed"], 7)
        self.assertEqual(d["seed7"]["a"], "Nile RPG")
        self.assertTrue(d["seed7"]["same"])

    def test_named_rpg_theme_stays_deterministic(self):
        d = self.out["rpgDeterministic"]
        self.assertEqual(d["title"], "Bharata RPG")
        self.assertTrue(d["same"], d)

    def test_new_rpg_packs_are_distinct(self):
        expected = {
            "build an rpg in the frost": (
                "Frostfall RPG", "the Pale Warden", "Hoarfrost Gate", "#4a7f8c"),
            "build an rpg in a volcano": (
                "Cinderforge RPG", "the Ember Tyrant", "The Molten Stair", "#7a3b24"),
            "build an rpg with mushrooms": (
                "Mycelia RPG", "the Spore Mother", "Breathing Canopy", "#6b7d3a"),
            "build an rpg in the sky islands": (
                "Aether Reach RPG", "the Storm Marshal", "Windward Isles", "#4f7a8c"),
            "build an rpg with clockwork": (
                "Clockwork RPG", "the Regulator", "The Escapement", "#7a6334"),
            "build an rpg in a dream": (
                "Reverie RPG", "the Dream Eater", "Moon Gate", "#5a4f8c"),
            "build an rpg in a plague": (
                "Blightfall RPG", "the Blight Herald", "The Wasting Fields", "#6b6b3a"),
            "build an rpg on an archipelago": (
                "Tidewreck RPG", "the Admiral", "The Green Isles", "#3f7a5a"),
            "build an rpg in the verdant forest": (
                "Verdant Wood RPG", "the Warden", "Verdant Hollow", "#1f513a"),
            "build an rpg among the stars": (
                "Astral RPG", "the Void Herald", "The Comet Road", "#4a4f8c"),
        }
        titles = set()
        pages = set()
        for prompt, (title, marker, place, colour) in expected.items():
            t = self.out["newThemes"][prompt]
            self.assertEqual(t["title"], title, prompt)
            self.assertEqual(t["theme"], title[:-4], prompt)
            self.assertIn(marker, t["js"], prompt)
            self.assertIn(place, t["places"], prompt)
            self.assertIn(colour, t["css"] + t["js"], prompt)
            titles.add(t["title"])
            pages.add(t["html"])
        self.assertEqual(len(titles), len(expected))
        self.assertEqual(len(pages), len(expected))

    def test_consecutive_default_rpg_builds_are_not_collapsed(self):
        d = self.out["sandbox"]["defaults"]
        self.assertEqual(d["first"][0]["via"], "build")
        self.assertEqual(d["second"][0]["via"], "build")
        self.assertNotEqual(d["one"]["name"], d["two"]["name"])
        self.assertNotEqual(d["one"]["slug"], d["two"]["slug"])
        self.assertEqual(d["count"], 2)

    def test_renaming_an_rpg_to_a_new_pack_rethemes_it(self):
        s = self.out["sandbox"]
        self.assertEqual(s["olympusBuild"][0]["via"], "build")
        self.assertEqual(s["afterOlympus"]["title"], "Olympus RPG")
        self.assertIn("the Titan", s["afterOlympus"]["js"])
        self.assertEqual(s["olympusRename"][0]["via"], "project.rename")
        self.assertEqual(s["afterOlympusRename"]["slug"], s["afterOlympus"]["slug"])
        self.assertEqual(s["afterOlympusRename"]["title"], "Nile RPG")
        self.assertIn("the Pharaoh", s["afterOlympusRename"]["js"])
        self.assertNotIn("the Titan", s["afterOlympusRename"]["js"])
        self.assertIn("the Pharaoh", s["afterOlympusRename"]["bundled"])
        self.assertNotIn("the Titan", s["afterOlympusRename"]["bundled"])

    def test_generated_variant_scripts_are_valid_javascript(self):
        for name, status in self.out["syntax"].items():
            self.assertEqual(status, "ok", name)

    def test_sandbox_rename_rethemes_the_same_project(self):
        s = self.out["sandbox"]
        self.assertEqual(s["build"][0]["via"], "build")
        self.assertEqual(s["first"]["slug"], "camelot-rpg")
        self.assertEqual(s["first"]["h1"], "Camelot RPG")
        self.assertEqual(s["stale"][0]["via"], "project.rename")
        # stale old name falls back to the active project, not a new project
        self.assertEqual(s["afterStale"]["slug"], s["first"]["slug"])
        self.assertEqual(s["afterStale"]["name"], "India")
        self.assertEqual(s["afterStale"]["h1"], "Bharata RPG")
        self.assertIn("Asura King", s["afterStale"]["js"])
        self.assertIn("Asura King", s["afterStale"]["bundled"])
        self.assertNotIn("Black Knight", s["afterStale"]["bundled"])
        # "it" resolves to the active project and re-themes again
        self.assertEqual(s["pronoun"][0]["via"], "project.rename")
        self.assertEqual(s["afterPronoun"]["slug"], s["first"]["slug"])
        self.assertEqual(s["afterPronoun"]["name"], "Camelot")
        self.assertEqual(s["afterPronoun"]["h1"], "Camelot RPG")

    def test_project_title_edit_changes_real_files_and_preview(self):
        e = self.out["edits"]
        self.assertEqual(e["title"][0]["via"], "project.title")
        self.assertFalse(e["title"][0]["error"])
        after = e["afterTitle"]
        self.assertEqual(after["slug"], "camelot-rpg")
        self.assertEqual(after["h1"], "camelot field notes")
        self.assertEqual(after["pageTitle"], "camelot field notes · toolrx")
        self.assertEqual(after["readme"], "# camelot field notes")
        self.assertTrue(after["previewHas"])

    def test_project_theme_edit_preserves_files_and_preview(self):
        e = self.out["edits"]
        self.assertEqual(e["theme"][0]["via"], "project.theme")
        self.assertEqual(e["afterTheme"]["htmlClass"], "light")
        self.assertEqual(e["afterTheme"]["previewTheme"], "light")
        # the title edit survived the theme switch
        self.assertEqual(e["afterTheme"]["title"], "camelot field notes")
        self.assertEqual(e["afterDark"]["htmlClass"], "dark")
        self.assertEqual(e["afterDark"]["previewTheme"], "dark")
        self.assertEqual(e["afterDark"]["title"], "camelot field notes")
        self.assertTrue(e["afterDark"]["toggle"])
        self.assertTrue(e["afterDark"]["note"])

    def test_theme_toggle_is_real_and_idempotent(self):
        e = self.out["edits"]
        self.assertEqual(e["toggle"][0]["via"], "project.themeToggle")
        self.assertTrue(e["afterToggle"]["button"])
        self.assertTrue(e["afterToggle"]["handler"])
        self.assertTrue(e["afterToggle"]["previewButton"])
        self.assertTrue(e["afterToggle"]["previewScript"])
        self.assertEqual(e["afterToggle"]["jsValid"], True)
        self.assertEqual(e["toggleCount"], 1)

    def test_footer_note_edits_and_replaces(self):
        e = self.out["edits"]
        self.assertEqual(e["note"][0]["via"], "project.note")
        self.assertTrue(e["afterNote"]["file"])
        self.assertTrue(e["afterNote"]["preview"])
        self.assertTrue(e["afterNote"]["hasId"])
        self.assertEqual(e["noteCount"], 1)
        self.assertTrue(e["afterNoteAgain"]["firstGone"])
        self.assertTrue(e["afterNoteAgain"]["second"])

    def test_project_files_can_be_edited_directly(self):
        e = self.out["edits"]
        self.assertIn("wrote projects/camelot-rpg/styles.css", e["write"])
        self.assertTrue(e["afterWrite"]["preview"])
        self.assertTrue(e["afterWrite"]["file"])
        self.assertTrue(e["afterDark"]["marker"])
        self.assertIn("no such file", e["writeMissing"])
        self.assertIn("exceeds", e["writeTooBig"])

    def test_project_preview_is_bundled_from_edited_files(self):
        b = self.out["edits"]["bundle"]
        self.assertTrue(b["hasStyle"])
        self.assertTrue(b["hasScript"])
        self.assertTrue(b["noLink"])
        self.assertTrue(b["noSrc"])
        self.assertTrue(b["label"])
        self.assertTrue(b["titleTag"])

    def test_reopening_a_project_keeps_edits(self):
        o = self.out["edits"]["afterOpen"]
        self.assertEqual(o["slug"], "camelot-rpg")
        self.assertEqual(o["title"], "camelot field notes")
        self.assertEqual(o["theme"], "dark")

    def test_composable_edits_change_real_files_and_spec(self):
        p = self.out["patches"]
        self.assertEqual(p["base"]["files"],
                         ["ARCHITECTURE.md", "README.md", "app.js",
                          "engine2d.js", "index.html", "styles.css"])
        self.assertFalse(p["base"]["engine3d"])
        self.assertIn("2D side-scroller", p["base"]["spec"])
        expected = {
            "add double jump": "double jump",
            "add three enemy types": "three enemy types",
            "add a quest": "quest",
            "add day/night": "day/night",
            "add sound": "sound",
            "make it harder": "harder",
        }
        for step in p["steps"]:
            q = step["q"]
            self.assertFalse(step["error"], q)
            self.assertEqual(step["via"], "edit.apply", q)
            self.assertEqual(step["syntax"], "ok", q)
            self.assertIn("app.js", step["changed"], q)
            self.assertIn("ARCHITECTURE.md", step["changed"], q)
            self.assertIn("## Applied edits", step["arch"], q)
            self.assertIn("+" + expected[q], step["spec"], q)
            self.assertGreater(len(step["preview"]), 1000, q)

    def test_composable_edits_stack_without_conflict(self):
        s = self.out["patches"]["stacked"]
        self.assertEqual(s["syntax"], "ok")
        for label in ("double jump", "three enemy types", "quest",
                      "day/night", "sound", "harder"):
            self.assertIn("+" + label, s["spec"])
        self.assertTrue(s["previewHasDoubleJump"])
        self.assertTrue(s["previewHasQuest"])
        self.assertTrue(s["previewHasMute"])
        self.assertTrue(s["previewHasDayNight"])

    def test_undo_restores_every_file_exactly(self):
        p = self.out["patches"]
        self.assertEqual(len(p["undo"]), 6)
        for u in p["undo"]:
            self.assertFalse(u["error"], u["text"])
            self.assertIn("undid", u["text"])
        self.assertTrue(p["restored"]["lossless"], p["restored"])
        self.assertTrue(p["restored"]["htmlSame"], p["restored"])
        self.assertNotIn("+", p["restored"]["spec"])
        self.assertEqual(p["restored"]["files"][-1], "styles.css")
        self.assertNotIn("engine3d.js", p["restored"]["files"])
        self.assertIn("nothing to undo", p["undoEmpty"])

    def test_world_size_patch_resizes_and_undoes(self):
        w = self.out["patches"]["world"]
        self.assertEqual(w["via"], "edit.apply")
        self.assertEqual(w["before"], "64")
        self.assertEqual(w["after"], "120")
        self.assertIn("120×120", w["spec"])
        self.assertTrue(w["htmlMentions"])
        self.assertEqual(w["restored"], "64")
        self.assertTrue(w["lossless"])
        self.assertIn("32 and 256", self.out["patches"]["worldReject"])

    def test_isometric_patch_drives_the_camera(self):
        i = self.out["patches"]["isometric"]
        self.assertEqual(i["via"], "edit.apply")
        self.assertTrue(i["fn"], i["text"])
        self.assertEqual(i["syntax"], "ok")
        self.assertTrue(i["preview"])
        self.assertFalse(self.out["patches"]["isometricRestore"]["fn"])
        self.assertTrue(self.out["patches"]["isometricRestore"]["lossless"])

    def test_make_it_3d_rebuilds_and_undo_removes_the_engine(self):
        d = self.out["patches"]["threeD"]
        self.assertEqual(d["via"], "edit.apply")
        self.assertTrue(d["hasEngine3d"], d["files"])
        self.assertFalse(d["hasEngine2d"], d["files"])
        self.assertTrue(d["spec"].startswith("spec · 3D"), d["spec"])
        self.assertTrue(d["preview"])
        self.assertEqual(d["syntax"], "ok")
        u = self.out["patches"]["threeDUndo"]
        self.assertFalse(u["hasEngine3d"], u["files"])
        self.assertTrue(u["lossless"], u["files"])

    def test_patch_rejections_stay_honest(self):
        r = self.out["patches"]["reject"]
        self.assertIn("no jump", r["doubleJump"])
        self.assertTrue(r["unchanged"], "a rejected edit must not touch files")
        self.assertIn("no audio", r["calculator"])
        self.assertIn("3D", r["shooterIso"])

    def test_boss_patch_and_edit_routing(self):
        p = self.out["patches"]
        b = p["boss"]
        self.assertEqual(b["via"], "edit.apply")
        self.assertTrue(b["fn"], b["text"])
        self.assertEqual(b["syntax"], "ok")
        self.assertTrue(b["preview"])
        self.assertIn("+boss", b["spec"])
        self.assertTrue(p["bossUndo"])
        self.assertEqual(p["route"]["edit"], "edit.apply")
        self.assertEqual(p["route"]["undo"], "edit.undo")
        self.assertEqual(p["route"]["lang"], "lang.reply")

    def test_patch_bundle_is_atomic_and_one_undo(self):
        b = self.out["growth"]["bundle"]
        self.assertEqual(b["via"], "edit.apply.many")
        self.assertEqual(b["fns"], [True, True, True], b["text"])
        self.assertEqual(b["syntax"], "ok")
        self.assertTrue(b["preview"])
        self.assertEqual(b["failVia"], "edit.apply.many")
        self.assertIn("not edited", b["failText"])
        self.assertTrue(b["failAtomic"], "a failed bundle must change no files")
        self.assertTrue(b["failKeptBoss"])
        self.assertTrue(self.out["growth"]["bundleUndo"])

    def test_growth_adds_real_modules_and_inlines_them(self):
        g = self.out["growth"]["grow"]
        self.assertEqual(g["via"], "project.grow")
        for name in ("core/state.js", "ui/render.js", "data/seed.js",
                     "content/seed.js"):
            self.assertIn(name, g["files"])
        self.assertTrue(g["tags"])
        self.assertTrue(g["tagsBeforeApp"])
        self.assertTrue(g["appModules"])
        self.assertEqual(g["coreSyntax"], "ok")
        self.assertEqual(g["uiSyntax"], "ok")
        self.assertEqual(g["dataSyntax"], "ok")
        self.assertTrue(g["previewInlined"])
        self.assertFalse(g["previewExternal"])
        self.assertTrue(g["cssUntouched"], "growth must not regenerate unrelated files")
        self.assertTrue(self.out["growth"]["growUndo"])

    def test_module_and_system_growth(self):
        s = self.out["growth"]["system"]
        self.assertEqual(s["via"], "system.add")
        self.assertTrue(s["hasFile"])
        self.assertTrue(s["registers"])
        self.assertEqual(s["syntax"], "ok")
        self.assertEqual(s["expandVia"], "module.expand")
        self.assertTrue(s["hasContentModule"])
        self.assertEqual(s["tags"], 2)
        self.assertTrue(s["preview"])

    def test_undo_depth_is_configurable(self):
        d = self.out["growth"]["undoDepth"]
        self.assertEqual(d["undos"], 3)
        self.assertTrue(d["notBase"])
        self.assertTrue(d["hasDoubleJump"])
        self.assertFalse(d["hasHardMode"])
        self.assertFalse(d["hasSound"])

    def test_reload_resumes_the_active_project_preview(self):
        r = self.out["resume"]
        self.assertEqual(r["active"], "olympus-rpg")
        self.assertEqual(r["title"], "Egypt")
        self.assertIn("<title>Nile RPG · toolrx</title>", r["html"])
        self.assertIn("the Pharaoh", r["html"])
        self.assertIn("offline · project preview", r["html"])

    def test_site_templates_build(self):
        for name in ("social", "blog", "forum", "chat"):
            s = self.out["sites"][name]
            self.assertTrue(s["ok"], name)
            self.assertEqual(s["kind"], name, name)
            self.assertIn("index.html", s["files"], name)
            self.assertIn("ARC" + "HITECTURE.md", s["files"], name)

    def test_architecture_and_blueprint(self):
        plan = self.out["plan"][0]
        self.assertFalse(plan["error"])
        self.assertIn("build order", plan["text"])
        self.assertIn("state", plan["text"])
        self.assertIn("modules", self.out["blueprint"][0]["text"].lower())
        self.assertIn("state", self.out["blueprint"][0]["text"].lower())

    def test_project_commands(self):
        self.assertEqual(self.out["newProject"][0]["via"], "project.new")
        self.assertEqual(self.out["listProjects"][0]["via"], "project.list")
        self.assertEqual(self.out["openProject"][0]["via"], "project.open")
        self.assertEqual(self.out["deleteProject"][0]["via"], "project.delete")
        self.assertEqual(self.out["showFiles"][0]["via"], "project.files")
        self.assertIn("index.html", self.out["showFiles"][0]["text"])

    def test_chat_is_conversational_and_remembers_a_name(self):
        self.assertEqual(self.out["chatHello"][0]["via"], "chat")
        self.assertTrue(self.out["chatHello"][0]["text"].strip())
        self.assertEqual(self.out["chatFeel"][0]["via"], "chat")
        self.assertIn("anxious", self.out["chatFeel"][0]["text"].lower())
        self.assertIn("Ada", self.out["chatName"][0]["text"])
        self.assertIn("Ada", self.out["chatWho"][0]["text"])
        self.assertTrue(self.out["chatJoke"][0]["text"].strip())

    def test_casual_greetings_are_not_therapy_flavored(self):
        for text in self.out["chatGreetings"]:
            low = text.lower()
            self.assertNotIn("but listening", low)
            self.assertNotIn("what's on your mind", low)
            self.assertNotIn("what is on your mind", low)
            self.assertTrue(any(w in low for w in ("build", "make", "tool")), text)

    def test_unknown_chat_is_practical_not_a_reflection(self):
        text = self.out["chatUnknown"]
        self.assertIn("matching command", text.lower())
        self.assertIn("build", text.lower())
        self.assertNotIn("what's underneath", text.lower())
        self.assertNotIn("say more", text.lower())

    def test_feeling_replies_are_always_well_formed(self):
        for text in self.out["chatFeelings"]:
            self.assertTrue(text.strip())
            self.assertNotIn("undefined", text.lower())

    def test_web_results_carry_a_source(self):
        wiki = self.out["wiki"][0]
        self.assertEqual(wiki["via"], "web.search")
        self.assertIn("ada lovelace", wiki["text"])
        self.assertTrue(wiki["source"].startswith("https://"))
        self.assertEqual(self.out["define"][0]["via"], "web.define")
        self.assertEqual(self.out["weather"][0]["via"], "web.weather")
        chain = self.out["summaryChain"]
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[1]["via"], "text.summarize")
        self.assertIn("summary about ada lovelace", chain[1]["text"])

    def test_memory_remembers_and_recalls_facts(self):
        mem = self.out["memory"]
        self.assertEqual(mem["rememberColor"][0]["via"], "memory.remember")
        self.assertIn("favorite color", mem["rememberColor"][0]["text"])
        self.assertEqual(mem["recallColor"][0]["via"], "memory.recall")
        self.assertIn("teal", mem["recallColor"][0]["text"])
        self.assertEqual(mem["recallDog"][0]["via"], "memory.recall")
        self.assertIn("max", mem["recallDog"][0]["text"].lower())
        self.assertIn("42", mem["recallCode"][0]["text"])
        self.assertIn("launch code", mem["recallCode"][0]["text"])
        self.assertIn("don't have anything saved", mem["recallMissing"][0]["text"])

    def test_memory_notes_and_listing(self):
        mem = self.out["memory"]
        self.assertEqual(mem["note"][0]["via"], "memory.note")
        self.assertIn("friday", mem["note"][0]["text"])
        listing = mem["list"][0]
        self.assertEqual(listing["via"], "memory.list")
        self.assertIn("favorite color", listing["text"])
        self.assertIn("friday", listing["text"])
        self.assertIn("last build: Calculator", listing["text"])
        context = mem["context"][0]
        self.assertEqual(context["via"], "memory.context")
        self.assertIn("Calculator", context["text"])
        self.assertIn("projects/calculator", context["text"])

    def test_memory_forget_and_clear(self):
        mem = self.out["memory"]
        self.assertEqual(mem["forgetColor"][0]["via"], "memory.forget")
        self.assertIn("forgot", mem["forgetColor"][0]["text"])
        self.assertIn("don't have anything saved", mem["afterForget"][0]["text"])
        self.assertEqual(mem["forgetName"][0]["via"], "memory.forget")
        self.assertNotIn("Ada", mem["nameAfterForget"][0]["text"])
        self.assertEqual(mem["clear"][0]["via"], "memory.forget")
        self.assertIn("cleared", mem["clear"][0]["text"])
        self.assertIn("don't have anything saved", mem["afterClear"][0]["text"])

    def test_web_lookup_feeds_a_page_build(self):
        wb = self.out["webBuild"]["pipeline"]
        self.assertTrue(wb["ok"])
        self.assertEqual(wb["steps"], 2)
        self.assertEqual(wb["via"], ["web.search", "build.web"])
        self.assertIn("projects/ada-lovelace", wb["text"])
        self.assertEqual(wb["title"], "Ada Lovelace")
        self.assertEqual(wb["slug"], "ada-lovelace")
        self.assertIn("summary about ada lovelace", wb["html"].lower())
        self.assertIn("https://en.wikipedia.org/wiki/ada lovelace", wb["html"].lower())
        self.assertIn("from the web", wb["html"].lower())
        self.assertEqual(wb["files"], ["ARCHITECTURE.md", "README.md", "app.js",
                                       "index.html", "styles.css"])
        self.assertIn("styles.css", wb["html"])
        self.assertIn("app.js", wb["html"])
        self.assertIn('getElementById("prog")', wb["js"])

    def test_explicit_topic_builds_a_page(self):
        tb = self.out["webBuild"]["topic"]
        self.assertTrue(tb["ok"])
        self.assertEqual(tb["via"], "build.web")
        self.assertEqual(tb["title"], "Grace Hopper")
        self.assertEqual(tb["slug"], "grace-hopper")
        self.assertIn("grace hopper", tb["html"].lower())
        self.assertEqual(tb["files"], ["ARCHITECTURE.md", "README.md", "app.js",
                                       "index.html", "styles.css"])

    def test_page_build_without_context_fails_honestly(self):
        np = self.out["webBuild"]["noPrev"]
        self.assertEqual(np["via"], "build.web")
        self.assertTrue(np["error"])
        self.assertIn("wikipedia", np["text"].lower())

    def test_summary_keeps_the_source_for_a_page_build(self):
        s = self.out["webBuild"]["summary"]
        self.assertTrue(s["ok"])
        self.assertEqual(s["via"], ["web.search", "text.summarize", "build.web"])
        self.assertEqual(s["source"], "https://en.wikipedia.org/wiki/ada lovelace")
        self.assertIn("https://en.wikipedia.org/wiki/ada lovelace", s["html"].lower())
        self.assertEqual(s["title"], "Ada Lovelace")


if __name__ == "__main__":
    unittest.main(verbosity=2)

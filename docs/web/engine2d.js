/* toolrx shared 2D engine.
 *
 * A tiny deterministic runtime for generated games: fixed-step loop, input,
 * camera, tilemaps, sprites, AABB physics, particles, and WebAudio beeps.
 * No dependencies and no network. Projects ship this file as a real asset;
 * the preview inlines the same source so it stays self-contained.
 *
 * Exposes: self.toolrxEngine2d = { create, hash, rng, overlap }
 */
(function (root) {
  "use strict";

  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }

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

  function overlap(a, b) {
    return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  }

  function create(o) {
    o = o || {};
    var canvas = o.canvas;
    if (!canvas || !canvas.getContext) throw new Error("engine2d needs a canvas");
    var ctx = canvas.getContext("2d");
    var W = o.width || canvas.width || 640;
    var H = o.height || canvas.height || 360;
    var step = o.step || 1 / 60;
    var bg = o.background || "#080d1a";
    var dpr = 1, running = false, paused = false, acc = 0, last = 0;
    var held = {}, taps = {};
    var keymap = {};
    var pointer = { x: 0, y: 0, down: false, clicked: false };
    var camera = { x: 0, y: 0 };
    var particles = [];
    var timers = [];
    var audio = { on: o.sound !== false, ctx: null };
    function noop() {}
    function now() {
      return typeof performance !== "undefined" && performance.now
        ? performance.now() : Date.now();
    }

    function resize() {
      dpr = Math.min(3, root.devicePixelRatio || 1);
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.imageSmoothingEnabled = false;
    }

    function actionFor(key) {
      for (var a in keymap) {
        if (keymap[a].indexOf(key) >= 0) return a;
      }
      return null;
    }

    function onKeyDown(e) {
      var a = actionFor(e.key);
      if (!a) return;
      if (!held[a]) taps[a] = true;
      held[a] = true;
      if (e.preventDefault) e.preventDefault();
    }

    function onKeyUp(e) {
      var a = actionFor(e.key);
      if (a) {
        held[a] = false;
        if (e.preventDefault) e.preventDefault();
      }
    }

    function point(e) {
      var r = canvas.getBoundingClientRect();
      pointer.x = (e.clientX - r.left) * (W / (r.width || W));
      pointer.y = (e.clientY - r.top) * (H / (r.height || H));
    }

    function onDown(e) {
      point(e);
      pointer.down = true;
      pointer.clicked = true;
      if (e.preventDefault) e.preventDefault();
    }

    function onUp(e) {
      pointer.down = false;
      if (e.preventDefault) e.preventDefault();
    }

    function frame(t) {
      if (!running) return;
      if (!last) last = t;
      var dt = (t - last) / 1000;
      last = t;
      if (!isFinite(dt) || dt < 0) dt = 0;
      if (dt > 0.25) dt = 0.25;
      if (!paused) {
        acc += dt;
        var guard = 0;
        while (acc >= step && guard++ < 8) {
          update(step);
          acc -= step;
        }
      }
      render();
      requestAnimationFrame(frame);
    }

    function update(dt) {
      E.update(dt);
      for (var i = timers.length - 1; i >= 0; i--) {
        var tm = timers[i];
        tm.t += dt;
        while (tm.t >= tm.every) {
          tm.t -= tm.every;
          tm.fn();
        }
      }
      for (var p = particles.length - 1; p >= 0; p--) {
        var q = particles[p];
        q.life -= dt;
        if (q.life <= 0) {
          particles.splice(p, 1);
          continue;
        }
        q.vy += (q.gravity || 0) * dt;
        q.x += q.vx * dt;
        q.y += q.vy * dt;
      }
    }

    function render() {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.save();
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);
      E.draw(ctx);
      ctx.restore();
      taps = {};
      pointer.clicked = false;
    }

    function press(a) {
      if (!held[a]) taps[a] = true;
      held[a] = true;
    }

    function release(a) { held[a] = false; }

    function normKey(k) {
      if (k === "Space" || k === "spacebar") return " ";
      return k.length === 1 ? k.toLowerCase() : k;
    }

    var E = {
      canvas: canvas,
      ctx: ctx,
      width: W,
      height: H,
      camera: camera,
      pointer: pointer,
      particles: particles,

      /* Games assign these after create(), so the loop must read them off E
       * rather than capturing a handler once at construction. */
      update: o.update || noop,
      draw: o.draw || noop,

      resize: resize,

      start: function () {
        if (running) return E;
        running = true;
        paused = false;
        last = 0;
        resize();
        requestAnimationFrame(frame);
        return E;
      },

      stop: function () { running = false; return E; },
      pause: function () { paused = true; return E; },
      resume: function () { paused = false; last = 0; return E; },
      toggle: function () { paused = !paused; last = 0; return E; },

      bind: function (map) {
        Object.keys(map).forEach(function (a) {
          keymap[a] = map[a].map(normKey);
        });
        return E;
      },

      bindButtons: function (sel) {
        var nodes = document.querySelectorAll(sel || "[data-k]");
        Array.prototype.forEach.call(nodes, function (el) {
          var a = el.getAttribute("data-k");
          var down = function (e) {
            if (e.preventDefault) e.preventDefault();
            press(a);
          };
          var up = function (e) {
            if (e.preventDefault) e.preventDefault();
            release(a);
          };
          el.addEventListener("pointerdown", down);
          el.addEventListener("pointerup", up);
          el.addEventListener("pointercancel", up);
          el.addEventListener("pointerleave", up);
          el.addEventListener("contextmenu", function (e) { e.preventDefault(); });
        });
        return E;
      },

      held: function (a) { return !!held[a]; },
      tap: function (a) {
        if (taps[a]) { delete taps[a]; return true; }
        return false;
      },
      press: press,
      release: release,

      every: function (sec, fn) {
        timers.push({ t: 0, every: Math.max(0.01, sec), fn: fn });
        return E;
      },

      clear: function (color) {
        ctx.fillStyle = color || bg;
        ctx.fillRect(0, 0, W, H);
      },

      follow: function (x, y, smooth, worldW, worldH) {
        smooth = smooth == null ? 0.14 : smooth;
        camera.x += (x - W / 2 - camera.x) * smooth;
        camera.y += (y - H / 2 - camera.y) * smooth;
        if (worldW) camera.x = clamp(camera.x, 0, Math.max(0, worldW - W));
        if (worldH) camera.y = clamp(camera.y, 0, Math.max(0, worldH - H));
        return E;
      },

      rect: function (x, y, w, h, color) {
        ctx.fillStyle = color;
        ctx.fillRect(x, y, w, h);
      },

      circle: function (x, y, r, color) {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
      },

      line: function (x1, y1, x2, y2, color, width) {
        ctx.strokeStyle = color;
        ctx.lineWidth = width || 1;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      },

      text: function (str, x, y, size, color, align) {
        ctx.fillStyle = color || "#e6edf7";
        ctx.font = "600 " + (size || 14) + "px ui-monospace,monospace";
        ctx.textAlign = align || "left";
        ctx.textBaseline = "middle";
        ctx.fillText(String(str), x, y);
      },

      sprite: function (img, sx, sy, sw, sh, dx, dy, dw, dh) {
        if (!img) return E;
        ctx.drawImage(img, sx, sy, sw, sh, dx, dy, dw || sw, dh || sh);
        return E;
      },

      tiles: function (grid, size, colors, ox, oy) {
        ox = ox || 0;
        oy = oy || 0;
        for (var y = 0; y < grid.length; y++) {
          var row = grid[y];
          for (var x = 0; x < row.length; x++) {
            var c = colors[row[x]];
            if (!c) continue;
            ctx.fillStyle = c;
            ctx.fillRect(ox + x * size, oy + y * size, size, size);
          }
        }
        return E;
      },

      aabb: overlap,

      physics: function (b, solids, dt, opts) {
        opts = opts || {};
        var g = opts.gravity == null ? 1800 : opts.gravity;
        var maxFall = opts.maxFall || 900;
        b.vy = Math.min(maxFall, b.vy + g * dt);
        b.x += b.vx * dt;
        for (var i = 0; i < solids.length; i++) {
          var s = solids[i];
          if (!overlap(b, s)) continue;
          if (b.vx > 0) b.x = s.x - b.w;
          else if (b.vx < 0) b.x = s.x + s.w;
          b.vx = 0;
        }
        b.y += b.vy * dt;
        b.on = false;
        for (var j = 0; j < solids.length; j++) {
          var t = solids[j];
          if (!overlap(b, t)) continue;
          if (b.vy > 0) {
            b.y = t.y - b.h;
            b.vy = 0;
            b.on = true;
          } else if (b.vy < 0) {
            b.y = t.y + t.h;
            b.vy = 0;
          }
        }
        return b;
      },

      burst: function (x, y, color, n, opts) {
        opts = opts || {};
        n = n || 8;
        var speed = opts.speed || 90;
        var life = opts.life || 0.5;
        for (var i = 0; i < n; i++) {
          var a = (i / n) * Math.PI * 2 + Math.random() * 0.4;
          var v = speed * (0.5 + Math.random());
          particles.push({
            x: x, y: y, vx: Math.cos(a) * v, vy: Math.sin(a) * v,
            life: life * (0.6 + Math.random() * 0.7), max: life,
            gravity: opts.gravity || 0, color: color, size: opts.size || 3
          });
        }
        return E;
      },

      drawParticles: function () {
        for (var i = 0; i < particles.length; i++) {
          var p = particles[i];
          ctx.globalAlpha = Math.max(0, p.life / p.max);
          ctx.fillStyle = p.color;
          ctx.fillRect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
        }
        ctx.globalAlpha = 1;
        return E;
      },

      beep: function (freq, dur, type, vol) {
        if (!audio.on) return E;
        try {
          if (!audio.ctx) {
            var AC = root.AudioContext || root.webkitAudioContext;
            if (!AC) return E;
            audio.ctx = new AC();
          }
          var a = audio.ctx;
          var osc = a.createOscillator();
          var gain = a.createGain();
          var d = dur || 0.08;
          osc.type = type || "square";
          osc.frequency.value = freq || 440;
          gain.gain.value = vol == null ? 0.035 : vol;
          osc.connect(gain);
          gain.connect(a.destination);
          osc.start();
          gain.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + d);
          osc.stop(a.currentTime + d);
        } catch (e) { /* audio is optional */ }
        return E;
      },

      mute: function (on) {
        audio.on = on === undefined ? !audio.on : !!on;
        return audio.on;
      },

      store: function (key, val) {
        try {
          if (val === undefined) return root.localStorage.getItem(key);
          root.localStorage.setItem(key, String(val));
        } catch (e) { /* private mode */ }
        return val;
      },

      hash: hash,
      rng: rng
    };

    if (typeof root.addEventListener === "function") {
      root.addEventListener("keydown", onKeyDown);
      root.addEventListener("keyup", onKeyUp);
    }
    canvas.addEventListener("pointermove", point);
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointercancel", onUp);
    canvas.addEventListener("pointerleave", function () { pointer.down = false; });
    canvas.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    resize();
    return E;
  }

  root.toolrxEngine2d = { create: create, hash: hash, rng: rng, overlap: overlap };
})(typeof self !== "undefined" ? self : this);

/* toolrx shared 3D engine.
 *
 * A small WebGL1 renderer for generated games: perspective camera, flat-shaded
 * boxes, camera-facing billboards, and one batched draw call per frame. When
 * WebGL is missing or blocked, the same scene renders through a Canvas2D
 * painter's-algorithm fallback with near-plane clipping, so a game still runs.
 *
 * Exposes: self.toolrxEngine3d = { create, hash, rng }
 */
(function (root) {
  "use strict";

  var LIGHT = (function () {
    var v = [0.38, 0.86, 0.34], n = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    return [v[0] / n, v[1] / n, v[2] / n];
  })();

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

  function hex(color) {
    var c = String(color || "#8899aa").replace("#", "");
    if (c.length === 3) c = c[0] + c[0] + c[1] + c[1] + c[2] + c[2];
    var n = parseInt(c.slice(0, 6), 16);
    if (!isFinite(n)) n = 0x8899aa;
    return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255];
  }

  function shade(rgb, mul) {
    return [clamp(rgb[0] * mul, 0, 1), clamp(rgb[1] * mul, 0, 1), clamp(rgb[2] * mul, 0, 1)];
  }

  function css(rgb) {
    return "rgb(" + Math.round(rgb[0] * 255) + "," + Math.round(rgb[1] * 255) + ","
      + Math.round(rgb[2] * 255) + ")";
  }

  function faceShade(n) {
    var d = Math.max(0, n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]);
    return 0.55 + 0.45 * d;
  }

  /* Unit cube faces, in half-extent space. Winding is irrelevant: culling is
   * off so the same list feeds WebGL and the Canvas fallback. */
  var FACES = [
    { n: [0, 1, 0], v: [[-1, 1, -1], [1, 1, -1], [1, 1, 1], [-1, 1, 1]] },
    { n: [0, -1, 0], v: [[-1, -1, 1], [1, -1, 1], [1, -1, -1], [-1, -1, -1]] },
    { n: [0, 0, -1], v: [[-1, -1, -1], [-1, 1, -1], [1, 1, -1], [1, -1, -1]] },
    { n: [0, 0, 1], v: [[-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]] },
    { n: [-1, 0, 0], v: [[-1, -1, -1], [-1, -1, 1], [-1, 1, 1], [-1, 1, -1]] },
    { n: [1, 0, 0], v: [[1, -1, -1], [1, 1, -1], [1, 1, 1], [1, -1, 1]] }
  ];

  function mat4mul(a, b) {
    var o = new Float32Array(16);
    for (var c = 0; c < 4; c++) {
      for (var r = 0; r < 4; r++) {
        o[c * 4 + r] = a[r] * b[c * 4] + a[4 + r] * b[c * 4 + 1]
          + a[8 + r] * b[c * 4 + 2] + a[12 + r] * b[c * 4 + 3];
      }
    }
    return o;
  }

  function perspective(fov, aspect, near, far) {
    var f = 1 / Math.tan(fov / 2), nf = 1 / (near - far);
    return new Float32Array([
      f / aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (far + near) * nf, -1,
      0, 0, 2 * far * near * nf, 0
    ]);
  }

  function viewMatrix(cam, pitch) {
    var cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw);
    var cp = Math.cos(pitch), sp = Math.sin(pitch);
    var fx = sy * cp, fy = -sp, fz = cy * cp;
    var rx = cy, ry = 0, rz = -sy;
    var ux = fy * rz - fz * ry, uy = fz * rx - fx * rz, uz = fx * ry - fy * rx;
    var tx = cam.x, ty = cam.y, tz = cam.z;
    return new Float32Array([
      rx, ux, -fx, 0,
      ry, uy, -fy, 0,
      rz, uz, -fz, 0,
      -(rx * tx + ry * ty + rz * tz),
      -(ux * tx + uy * ty + uz * tz),
      (fx * tx + fy * ty + fz * tz),
      1
    ]);
  }

  function create(o) {
    o = o || {};
    var canvas = o.canvas;
    if (!canvas || !canvas.getContext) throw new Error("engine3d needs a canvas");
    var W = o.width || canvas.width || 640;
    var H = o.height || canvas.height || 360;
    var fov = (o.fov || 60) * Math.PI / 180;
    var near = o.near || 0.12;
    var far = o.far || 240;
    var sky = o.sky || "#0b1226";
    var step = o.step || 1 / 60;
    var dpr = 1, running = false, paused = false, acc = 0, last = 0;
    var held = {}, taps = {}, keymap = {};
    var timers = [];
    var audio = { on: o.sound !== false, ctx: null };
    var camera = { x: 0, y: 2.2, z: -6, yaw: 0, pitch: 0.16 };
    var boxes = [], sprites = [];
    var gl = null, mode = "canvas", ctx2d = null;
    var program = null, buf = null, uMVP = null, verts = new Float32Array(6 * 1024);
    var vertCount = 0;

    function resize() {
      dpr = Math.min(mode === "webgl" ? 2 : 2, root.devicePixelRatio || 1);
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      if (mode === "webgl") {
        gl.viewport(0, 0, canvas.width, canvas.height);
      } else {
        ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx2d.imageSmoothingEnabled = false;
      }
    }

    function initGL() {
      try {
        gl = canvas.getContext("webgl", { alpha: false, antialias: true, depth: true });
        if (!gl) gl = canvas.getContext("experimental-webgl", { alpha: false });
      } catch (e) { gl = null; }
      if (!gl) return false;
      var vs = "attribute vec3 aPos;attribute vec3 aCol;uniform mat4 uMVP;"
        + "varying vec3 vCol;void main(){gl_Position=uMVP*vec4(aPos,1.0);vCol=aCol;}";
      var fs = "precision mediump float;varying vec3 vCol;"
        + "void main(){gl_FragColor=vec4(vCol,1.0);}";
      function sh(type, src) {
        var s = gl.createShader(type);
        gl.shaderSource(s, src);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) return null;
        return s;
      }
      var v = sh(gl.VERTEX_SHADER, vs), f = sh(gl.FRAGMENT_SHADER, fs);
      if (!v || !f) { gl = null; return false; }
      program = gl.createProgram();
      gl.attachShader(program, v);
      gl.attachShader(program, f);
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) { gl = null; return false; }
      gl.useProgram(program);
      buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      var aPos = gl.getAttribLocation(program, "aPos");
      var aCol = gl.getAttribLocation(program, "aCol");
      gl.enableVertexAttribArray(aPos);
      gl.enableVertexAttribArray(aCol);
      gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 24, 0);
      gl.vertexAttribPointer(aCol, 3, gl.FLOAT, false, 24, 12);
      uMVP = gl.getUniformLocation(program, "uMVP");
      gl.enable(gl.DEPTH_TEST);
      gl.disable(gl.CULL_FACE);
      var c = hex(sky);
      gl.clearColor(c[0], c[1], c[2], 1);
      return true;
    }

    if (initGL()) {
      mode = "webgl";
    } else {
      ctx2d = canvas.getContext("2d");
      if (!ctx2d) throw new Error("engine3d needs WebGL or a 2d context");
    }

    function now() {
      return typeof performance !== "undefined" && performance.now
        ? performance.now() : Date.now();
    }

    function actionFor(key) {
      for (var a in keymap) {
        if (keymap[a].indexOf(key) >= 0) return a;
      }
      return null;
    }

    function normKey(k) {
      if (k === "Space" || k === "spacebar") return " ";
      return k.length === 1 ? k.toLowerCase() : k;
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

    function press(a) {
      if (!held[a]) taps[a] = true;
      held[a] = true;
    }

    function release(a) { held[a] = false; }

    function tickTimers(dt) {
      for (var i = timers.length - 1; i >= 0; i--) {
        var tm = timers[i];
        tm.t += dt;
        while (tm.t >= tm.every) {
          tm.t -= tm.every;
          tm.fn();
        }
      }
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
          E.update(step);
          tickTimers(step);
          acc -= step;
        }
      }
      renderScene();
      taps = {};
      requestAnimationFrame(frame);
    }

    function sceneSprites() { return sprites; }

    function pushQuad(p, q, r, s, rgb) {
      /* two triangles: p q r, p r s */
      if (vertCount + 18 > verts.length / 6) {
        var grown = new Float32Array(verts.length * 2);
        grown.set(verts);
        verts = grown;
      }
      var arr = [p, q, r, p, r, s];
      for (var i = 0; i < 6; i++) {
        var v = arr[i];
        verts[vertCount++] = v[0];
        verts[vertCount++] = v[1];
        verts[vertCount++] = v[2];
        verts[vertCount++] = rgb[0];
        verts[vertCount++] = rgb[1];
        verts[vertCount++] = rgb[2];
      }
    }

    function project(v, cam, pitch, out) {
      var dx = v[0] - cam.x, dy = v[1] - cam.y, dz = v[2] - cam.z;
      var cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw);
      var x1 = dx * cy - dz * sy;
      var z1 = dx * sy + dz * cy;
      var cp = Math.cos(pitch), sp = Math.sin(pitch);
      out.x = x1;
      out.y = dy * cp + z1 * sp;
      out.z = -dy * sp + z1 * cp;
      return out;
    }

    function drawWebGL(cam, pitch) {
      vertCount = 0;
      var i, f, j, b, s, rgb, m;
      for (i = 0; i < boxes.length; i++) {
        b = boxes[i];
        var hw = (b.w == null ? 1 : b.w) / 2;
        var hh = (b.h == null ? 1 : b.h) / 2;
        var hd = (b.d == null ? 1 : b.d) / 2;
        var base = hex(b.color);
        for (f = 0; f < 6; f++) {
          var face = FACES[f];
          var col = shade(base, faceShade(face.n) * (b.light == null ? 1 : b.light));
          var q = [];
          for (j = 0; j < 4; j++) {
            var fv = face.v[j];
            q.push([b.x + fv[0] * hw, b.y + fv[1] * hh, b.z + fv[2] * hd]);
          }
          pushQuad(q[0], q[1], q[2], q[3], col);
        }
      }
      var cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw);
      for (i = 0; i < sprites.length; i++) {
        s = sprites[i];
        var sw = (s.w == null ? 0.8 : s.w) / 2, sh = (s.h == null ? 0.9 : s.h) / 2;
        var col2 = shade(hex(s.color), s.light == null ? 1 : s.light);
        var p1 = [s.x - cy * sw, s.y + sh, s.z + sy * sw];
        var p2 = [s.x + cy * sw, s.y + sh, s.z - sy * sw];
        var p3 = [s.x + cy * sw, s.y - sh, s.z - sy * sw];
        var p4 = [s.x - cy * sw, s.y - sh, s.z + sy * sw];
        pushQuad(p1, p2, p3, p4, col2);
      }
      var proj = perspective(fov, W / H, near, far);
      m = mat4mul(proj, viewMatrix(cam, pitch));
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      if (!vertCount) return;
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, verts.subarray(0, vertCount * 6), gl.DYNAMIC_DRAW);
      gl.uniformMatrix4fv(uMVP, false, m);
      gl.drawArrays(gl.TRIANGLES, 0, vertCount);
    }

    function clipNear(poly, zNear) {
      var out = [];
      for (var i = 0; i < poly.length; i++) {
        var a = poly[i], b = poly[(i + 1) % poly.length];
        var ina = a.z >= zNear, inb = b.z >= zNear;
        if (ina) out.push(a);
        if (ina !== inb) {
          var t = (zNear - a.z) / (b.z - a.z);
          out.push({
            x: a.x + (b.x - a.x) * t,
            y: a.y + (b.y - a.y) * t,
            z: zNear
          });
        }
      }
      return out;
    }

    function drawCanvas(cam, pitch) {
      var g = ctx2d;
      var skyTop = hex(sky);
      var skyLow = shade(skyTop, 1.5);
      var grad = g.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, css(skyLow));
      grad.addColorStop(1, css(shade(skyTop, 0.75)));
      g.fillStyle = grad;
      g.fillRect(0, 0, W, H);
      var focal = (H / 2) / Math.tan(fov / 2);
      var polys = [];
      var tmp = { x: 0, y: 0, z: 0 };
      var i, j, f, b, s;

      function addPoly(world, n, color, depthBias) {
        var camPts = [], depth = 0;
        for (var k = 0; k < world.length; k++) {
          project(world[k], cam, pitch, tmp);
          camPts.push({ x: tmp.x, y: tmp.y, z: tmp.z });
        }
        if (camPts.length < 3) return;
        var clipped = clipNear(camPts, near);
        if (clipped.length < 3) return;
        var scr = [], sum = 0;
        for (var q = 0; q < clipped.length; q++) {
          var p = clipped[q];
          var sc = focal / p.z;
          scr.push([W / 2 + p.x * sc, H / 2 - p.y * sc]);
          sum += p.z;
        }
        polys.push({
          pts: scr,
          depth: sum / clipped.length + (depthBias || 0),
          color: css(color)
        });
      }

      for (i = 0; i < boxes.length; i++) {
        b = boxes[i];
        var hw = (b.w == null ? 1 : b.w) / 2;
        var hh = (b.h == null ? 1 : b.h) / 2;
        var hd = (b.d == null ? 1 : b.d) / 2;
        var base = hex(b.color);
        for (f = 0; f < 6; f++) {
          var face = FACES[f];
          var world = [];
          for (j = 0; j < 4; j++) {
            var fv = face.v[j];
            world.push([b.x + fv[0] * hw, b.y + fv[1] * hh, b.z + fv[2] * hd]);
          }
          addPoly(world, face.n,
            shade(base, faceShade(face.n) * (b.light == null ? 1 : b.light)));
        }
      }
      var cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw);
      for (i = 0; i < sprites.length; i++) {
        s = sprites[i];
        var sw = (s.w == null ? 0.8 : s.w) / 2, sh = (s.h == null ? 0.9 : s.h) / 2;
        var col = shade(hex(s.color), s.light == null ? 1 : s.light);
        addPoly([
          [s.x - cy * sw, s.y + sh, s.z + sy * sw],
          [s.x + cy * sw, s.y + sh, s.z - sy * sw],
          [s.x + cy * sw, s.y - sh, s.z - sy * sw],
          [s.x - cy * sw, s.y - sh, s.z + sy * sw]
        ], [0, 0, 1], col, -0.001);
      }

      polys.sort(function (a, b2) { return b2.depth - a.depth; });
      for (i = 0; i < polys.length; i++) {
        var poly = polys[i];
        g.fillStyle = poly.color;
        g.beginPath();
        g.moveTo(poly.pts[0][0], poly.pts[0][1]);
        for (j = 1; j < poly.pts.length; j++) g.lineTo(poly.pts[j][0], poly.pts[j][1]);
        g.closePath();
        g.fill();
      }
    }

    function renderScene() {
      var pitch = clamp(camera.pitch, -1.35, 1.35);
      E.draw(E);
      if (mode === "webgl") drawWebGL(camera, pitch);
      else drawCanvas(camera, pitch);
    }

    var E = {
      canvas: canvas,
      width: W,
      height: H,
      camera: camera,
      boxes: boxes,
      sprites: sprites,
      mode: mode,
      near: near,
      far: far,

      update: o.update || function () {},
      draw: o.draw || function () {},

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

      /* Scene helpers: games clear and refill these from E.draw. */
      box: function (b) { boxes.push(b); return E; },
      sprite: function (s) { sprites.push(s); return E; },
      clearScene: function () {
        boxes.length = 0;
        sprites.length = 0;
        return E;
      },

      /* Tests and tools can render a frame without starting the RAF loop. */
      renderOnce: function () { renderScene(); return E; },

      fog: function (color) { sky = color || sky; return E; },

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
    resize();
    return E;
  }

  root.toolrxEngine3d = { create: create, hash: hash, rng: rng };
})(typeof self !== "undefined" ? self : this);

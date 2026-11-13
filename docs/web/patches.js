/* toolrx composable edits.
 *
 * Step 19 treats common follow-ups as deterministic patches against the active
 * project. A patch updates the build spec and edits real files (a named
 * function or constant in app.js, markup in index.html, rules in styles.css),
 * never the prose. Everything is synchronous and offline.
 *
 * The caller (sandbox.js) owns the active project and the undo history. This
 * module only transforms a plain {kind, desc, files, spec, edits} snapshot:
 *
 *   var r = toolrxPatches.apply("double-jump", snapshot);
 *   r.ok · r.files · r.spec · r.edits · r.changed · r.message
 *
 * A patch that does not fit the project returns ok:false with a short,
 * honest reason instead of pretending it changed something.
 *
 * Exposes: self.toolrxPatches = { apply, list, labels, has }
 */
(function (root) {
  "use strict";

  var LABELS = {
    "double-jump": "double jump",
    "enemy-types": "three enemy types",
    "boss": "boss",
    "quest": "quest",
    "day-night": "day/night",
    "sound": "sound",
    "harder": "harder",
    "world": "world size",
    "isometric": "isometric view",
    "three-d": "3D"
  };

  function clone(files) {
    var out = {};
    for (var k in files) if (Object.prototype.hasOwnProperty.call(files, k)) out[k] = files[k];
    return out;
  }

  function is3d(files) { return !!files["engine3d.js"]; }

  function append(js, code) {
    return String(js || "").replace(/\s*$/, "") + "\n\n" + code + "\n";
  }

  function addCss(files, css) {
    files["styles.css"] = String(files["styles.css"] || "").replace(/\s*$/, "") + "\n" + css + "\n";
  }

  function addBody(files, html) {
    files["index.html"] = String(files["index.html"] || "").replace(/<\/body>/i, html + "\n</body>");
  }

  function genreOf(spec, ctx) {
    return (spec && spec.genre) || (ctx && ctx.kind) || "";
  }

  /* ---------------------------------------------------------------- docs -- */
  function syncDocs(files, spec) {
    var t = root.toolrxTemplates;
    if (!t || !t.specLine) return;
    var line = t.specLine(spec);
    ["README.md", "ARCHITECTURE.md"].forEach(function (name) {
      if (!files[name]) return;
      files[name] = String(files[name]).replace(/^spec · .*$/m, line);
    });
    var edits = (spec.edits || []).slice();
    if (!edits.length) return;
    var block = "<!-- edits:start -->\n## Applied edits\n\n"
      + edits.map(function (e) { return "- " + e; }).join("\n")
      + "\n<!-- edits:end -->";
    ["README.md", "ARCHITECTURE.md"].forEach(function (name) {
      if (!files[name]) return;
      var text = String(files[name]);
      var re = /\n?<!-- edits:start -->[\s\S]*?<!-- edits:end -->\n?/;
      files[name] = re.test(text)
        ? text.replace(re, "\n" + block + "\n")
        : text.replace(/\s*$/, "") + "\n\n" + block + "\n";
    });
  }

  /* ------------------------------------------------------------- patches -- */

  function doubleJump(files, spec) {
    if (genreOf(spec) !== "platformer") {
      return { ok: false, why: "this project has no jump to double (try build a platformer)" };
    }
    var js = files["app.js"] || "";
    var m = /if\(E\.tap\('jump'\)&&P\.on\)\{P\.vy=(-?[0-9.]+);P\.on=false;E\.beep\(([^;]*)\);\}/.exec(js);
    if (!m) return { ok: false, why: "the jump handler was edited or replaced, so I can't patch it safely" };
    js = js.replace(m[0], "if(E.tap('jump'))doubleJump();");
    js = append(js, [
      "/* edit: double jump */",
      "var AIR_JUMPS=1,airJumps=AIR_JUMPS;",
      "function doubleJump(){",
      "  if(P.on)airJumps=AIR_JUMPS;",
      "  else if(airJumps<=0)return;",
      "  else airJumps--;",
      "  P.vy=" + m[1] + ";P.on=false;",
      "  E.beep(airJumps?660:520,.07,'square');",
      "}"
    ].join("\n"));
    files["app.js"] = js;
    return { ok: true, fn: "doubleJump() in app.js" };
  }

  function enemyTypes(files, spec, ctx) {
    var g = genreOf(spec, ctx);
    var js = files["app.js"] || "";
    if (js.indexOf("function makeEnemy") >= 0 || js.indexOf("function makeFoe") >= 0) {
      return { ok: false, why: "this project already has typed enemies" };
    }
    var maker = "", push = "", drawFind = "", drawRepl = "";
    if (g === "shooter") {
      push = "enemies.push({x:x,y:y,w:20,h:20,hp:1+Math.floor(wave/4),speed:34+wave*5});";
      maker = [
        "/* edit: three enemy types */",
        "var ENEMY_TYPES=['drone','dart','brute'],enemySerial=0;",
        "function makeEnemy(x,y,wave){",
        "  var t=enemySerial++%3;",
        "  var e={x:x,y:y,w:20,h:20,hp:1+Math.floor(wave/4),speed:34+wave*5,type:ENEMY_TYPES[t],color:'#fb7185'};",
        "  if(t===1){e.w=13;e.h=13;e.hp+=1;e.speed*=1.4;e.color='#fbbf24';}",
        "  else if(t===2){e.w=30;e.h=30;e.hp+=2;e.speed*=.72;e.color='#a78bfa';}",
        "  return e;",
        "}"
      ].join("\n");
      drawFind = "E.rect(e.x-e.w/2,e.y-e.h/2,e.w,e.h,'#fb7185');";
      drawRepl = "E.rect(e.x-e.w/2,e.y-e.h/2,e.w,e.h,e.color||'#fb7185');";
    } else if (g === "twinstick") {
      push = "enemies.push({x:x,y:y,r:12,hp:1+Math.floor(wave/4),speed:26+wave*7});";
      maker = [
        "/* edit: three enemy types */",
        "var ENEMY_TYPES=['orb','dart','brute'],enemySerial=0;",
        "function makeEnemy(x,y,wave){",
        "  var t=enemySerial++%3;",
        "  var e={x:x,y:y,r:12,hp:1+Math.floor(wave/4),speed:26+wave*7,type:ENEMY_TYPES[t],color:'#fb7185'};",
        "  if(t===1){e.r=9;e.hp+=1;e.speed*=1.35;e.color='#fbbf24';}",
        "  else if(t===2){e.r=17;e.hp+=2;e.speed*=.7;e.color='#a78bfa';}",
        "  return e;",
        "}"
      ].join("\n");
      drawFind = "E.circle(e.x,e.y,e.r,'#fb7185');";
      drawRepl = "E.circle(e.x,e.y,e.r,e.color||'#fb7185');";
    } else if (g === "waveshooter") {
      push = "enemies.push({x:Math.sin(a)*r,z:Math.cos(a)*r,hp:1+Math.floor(wave/2),r:1.1,speed:2.2+wave*.35});";
      maker = [
        "/* edit: three enemy types */",
        "var enemySerial=0;",
        "function makeEnemy(a,r,wave){",
        "  var t=enemySerial++%3;",
        "  var e={x:Math.sin(a)*r,z:Math.cos(a)*r,hp:1+Math.floor(wave/2),r:1.1,speed:2.2+wave*.35,type:t,color:'#fb7185'};",
        "  if(t===1){e.r=.8;e.speed*=1.45;e.color='#fbbf24';}",
        "  else if(t===2){e.r=1.6;e.hp+=1;e.speed*=.7;e.color='#a78bfa';}",
        "  return e;",
        "}"
      ].join("\n");
      drawFind = "E.box({x:e.x,y:1.3,z:e.z,w:2.2,h:1.2,d:2.2,color:'#fb7185',light:.4});";
      drawRepl = "E.box({x:e.x,y:1.3,z:e.z,w:e.r*2,h:e.r*1.1,d:e.r*2,color:e.color||'#fb7185',light:.4});";
    } else if (g === "towerdefense") {
      push = "enemies.push({seg:0,x:PATH[0][0],y:PATH[0][1],hp:hp,max:hp,speed:34+wave*3,r:9,done:false});";
      maker = [
        "/* edit: three enemy types */",
        "var enemySerial=0;",
        "function makeEnemy(hp,wave){",
        "  var t=enemySerial++%3,speed=34+wave*3,r=9,mult=1,color='#fb7185';",
        "  if(t===1){speed*=1.5;r=7;color='#fbbf24';}",
        "  else if(t===2){r=12;mult=1.8;speed*=.68;color='#a78bfa';}",
        "  var h=Math.round(hp*mult);",
        "  return {seg:0,x:PATH[0][0],y:PATH[0][1],hp:h,max:h,speed:speed,r:r,color:color,done:false};",
        "}"
      ].join("\n");
      drawFind = "E.circle(e.x,e.y,e.r,'#fb7185');";
      drawRepl = "E.circle(e.x,e.y,e.r,e.color||'#fb7185');";
    } else if (g === "roguelike") {
      push = "enemies.push({x:ex,y:ey,hp:2,dead:false});";
      maker = [
        "/* edit: three enemy types */",
        "var ENEMY_TYPES=[{glyph:'g',hp:2,color:'#fb7185'},{glyph:'w',hp:1,color:'#67e8f9'},{glyph:'b',hp:4,color:'#fbbf24'}],enemySerial=0;",
        "function makeEnemy(x,y){",
        "  var t=ENEMY_TYPES[enemySerial++%ENEMY_TYPES.length];",
        "  return {x:x,y:y,hp:t.hp,glyph:t.glyph,color:t.color,dead:false};",
        "}"
      ].join("\n");
      drawFind = "E.text('g',OX+e.x*CELL+CELL/2,OY+e.y*CELL+CELL/2,15,'#fb7185','center');";
      drawRepl = "E.text(e.glyph||'g',OX+e.x*CELL+CELL/2,OY+e.y*CELL+CELL/2,15,e.color||'#fb7185','center');";
    } else if (g === "platformer") {
      if (!is3d(files)) {
        var foes = [
          "/* edit: three enemy types */",
          "var FOES=[],foeSerial=0;",
          "function makeFoe(x,y,type){",
          "  return {x:x,y:y,w:22,h:22,type:type,speed:type===1?70:type===2?0:38,",
          "    color:type===1?'#fbbf24':type===2?'#a78bfa':'#fb7185',baseY:y,phase:foeSerial++*1.7};",
          "}",
          "function resetFoes(){FOES=[makeFoe(240,300,0),makeFoe(470,250,1),makeFoe(690,200,2),makeFoe(880,160,0)];}",
          "var baseUpdateFoes=E.update,baseDrawFoes=E.draw;",
          "E.update=function(dt){",
          "  baseUpdateFoes(dt);",
          "  FOES.forEach(function(f){",
          "    f.phase+=dt;",
          "    if(f.type===0)f.x+=Math.sin(f.phase)*f.speed*dt*.6;",
          "    else if(f.type===1){f.y=f.baseY+Math.sin(f.phase*2)*18;f.x-=f.speed*dt*.4;}",
          "    else f.y=f.baseY+Math.sin(f.phase*3)*6;",
          "    if(Math.abs(f.x-(P.x+P.w/2))<20&&Math.abs(f.y-(P.y+P.h/2))<22){",
          "      E.burst(P.x,P.y,f.color,10,{speed:100,life:.3});E.beep(140,.12,'sawtooth');reset();",
          "    }",
          "  });",
          "};",
          "E.draw=function(ctx){",
          "  baseDrawFoes(ctx);",
          "  ctx.save();ctx.translate(-E.camera.x,0);",
          "  FOES.forEach(function(f){E.rect(f.x-11,f.y-11,22,22,f.color);E.rect(f.x-5,f.y-5,3,3,'#0b1226');E.rect(f.x+2,f.y-5,3,3,'#0b1226');});",
          "  ctx.restore();",
          "};",
          "var baseResetFoes=reset;",
          "reset=function(){baseResetFoes();resetFoes();};",
          "resetFoes();"
        ].join("\n");
        files["app.js"] = append(js, foes);
        return { ok: true, fn: "makeFoe() and resetFoes() in app.js" };
      }
      return { ok: false, why: "enemy types are wired for the 2D platformer; the 3D one has no enemy spawner yet" };
    } else {
      return { ok: false, why: "enemy types are not wired for " + (LABELS[g] || g || "this project") };
    }
    if (js.indexOf(push) < 0) {
      return { ok: false, why: "the spawner was edited or replaced, so I can't add enemy types safely" };
    }
    var call = g === "towerdefense" ? "makeEnemy(hp,wave)"
      : g === "waveshooter" ? "makeEnemy(a,r,wave)" : "makeEnemy(x,y,wave)";
    js = js.replace(push, "enemies.push(" + call + ");");
    if (drawFind && js.indexOf(drawFind) >= 0) js = js.replace(drawFind, drawRepl);
    files["app.js"] = append(js, maker);
    return { ok: true, fn: "makeEnemy() in app.js" };
  }

  function boss(files, spec, ctx) {
    var g = genreOf(spec, ctx);
    var js = files["app.js"] || "";
    if (js.indexOf("function spawnBoss") >= 0) return { ok: false, why: "this project already has a boss" };
    var code = "";
    if (g === "shooter" || g === "twinstick") {
      code = [
        "/* edit: boss */",
        "var bossSpawned=false;",
        "function spawnBoss(){",
        "  bossSpawned=true;",
        "  enemies.push({x:360,y:-34,w:44,h:44,r:22,hp:18+wave*2,speed:24,color:'#a78bfa',boss:true});",
        "  E.beep(180,.2,'sawtooth');",
        "}",
        "var baseBossUpdate=E.update;",
        "E.update=function(dt){baseBossUpdate(dt);if(!bossSpawned&&!over&&score>=150)spawnBoss();};"
      ].join("\n");
      if (js.indexOf("color:'#fb7185'") < 0) {
        js = js.replace("E.rect(e.x-e.w/2,e.y-e.h/2,e.w,e.h,'#fb7185');", "E.rect(e.x-e.w/2,e.y-e.h/2,e.w,e.h,e.color||'#fb7185');")
                 .replace("E.circle(e.x,e.y,e.r,'#fb7185');", "E.circle(e.x,e.y,e.r,e.color||'#fb7185');");
      }
    } else if (g === "waveshooter") {
      code = [
        "/* edit: boss */",
        "var bossSpawned=false;",
        "function spawnBoss(){",
        "  bossSpawned=true;",
        "  enemies.push({x:0,z:34,hp:22+wave*2,r:2.6,speed:1.4,color:'#a78bfa',boss:true});",
        "  E.beep(180,.2,'sawtooth');",
        "}",
        "var baseBossUpdate=E.update;",
        "E.update=function(dt){baseBossUpdate(dt);if(!bossSpawned&&!over&&wave>=3)spawnBoss();};"
      ].join("\n");
      js = js.replace("E.box({x:e.x,y:1.3,z:e.z,w:2.2,h:1.2,d:2.2,color:'#fb7185',light:.4});",
        "E.box({x:e.x,y:1.3,z:e.z,w:e.boss?4.4:e.r*2,h:e.boss?2.4:e.r*1.1,d:e.boss?4.4:e.r*2,color:e.color||'#fb7185',light:.4});");
    } else if (g === "towerdefense") {
      code = [
        "/* edit: boss */",
        "var bossSpawned=false;",
        "function spawnBoss(){",
        "  bossSpawned=true;",
        "  enemies.push({seg:0,x:PATH[0][0],y:PATH[0][1],hp:240,max:240,speed:22,r:16,color:'#a78bfa',boss:true,done:false});",
        "  msg='a boss joins wave '+wave;hud();E.beep(180,.2,'sawtooth');",
        "}",
        "var baseBossUpdate=E.update;",
        "E.update=function(dt){baseBossUpdate(dt);if(!bossSpawned&&!over&&wave>=5)spawnBoss();};"
      ].join("\n");
      js = js.replace("E.circle(e.x,e.y,e.r,'#fb7185');", "E.circle(e.x,e.y,e.r,e.color||'#fb7185');");
    } else if (g === "roguelike") {
      code = [
        "/* edit: boss */",
        "var bossFloor=0;",
        "function spawnBoss(){",
        "  var spot=null;",
        "  for(var y=1;y<H-1&&!spot;y++)for(var x=1;x<W-1;x++){",
        "    if(open(x,y)&&!(x===player.x&&y===player.y)&&!enemyAt(x,y)){spot={x:x,y:y};break;}",
        "  }",
        "  if(!spot)return;",
        "  enemies.push({x:spot.x,y:spot.y,hp:10,glyph:'B',color:'#a78bfa',boss:true,dead:false});",
        "  msg='a warden wakes on floor '+floorNo;hud();E.beep(180,.2,'sawtooth');",
        "}",
        "var baseBossUpdate=E.update;",
        "E.update=function(dt){baseBossUpdate(dt);if(!over&&floorNo>=2&&bossFloor!==floorNo){bossFloor=floorNo;spawnBoss();}};"
      ].join("\n");
      js = js.replace("E.text('g',OX+e.x*CELL+CELL/2,OY+e.y*CELL+CELL/2,15,'#fb7185','center');",
        "E.text(e.glyph||'g',OX+e.x*CELL+CELL/2,OY+e.y*CELL+CELL/2,e.boss?18:15,e.color||'#fb7185','center');");
    } else {
      return { ok: false, why: "bosses are wired for shooter, twin-stick, wave shooter, tower defense, and roguelike" };
    }
    files["app.js"] = append(js, code);
    return { ok: true, fn: "spawnBoss() in app.js" };
  }

  function quest(files, spec, ctx) {
    var g = genreOf(spec, ctx);
    if (g === "rpg") return { ok: false, why: "this RPG already ships quests — press Q in game" };
    var table = {
      shooter: ["reach 300 points", "score", 300],
      twinstick: ["reach 300 points", "score", 300],
      waveshooter: ["reach 250 points", "score", 250],
      towerdefense: ["hold five waves", "wave", 5],
      roguelike: ["defeat five shades", "kills", 5],
      platformer: ["collect the coins", is3d(files) ? "got" : "coins.filter(function(c){return c.got;}).length", is3d(files) ? 10 : 9],
      explore: ["find all eight crystals", "found", 8],
      farmingsim: ["harvest ten crops", "harvested", 10],
      merges: ["score 200 points", "score", 200],
      rhythm: ["score 1500 points", "score", 1500],
      cardbattler: ["clear two floors", "floorNo", 2],
      builder: ["place twelve blocks", "count()", 12]
    };
    var q = table[g];
    if (!q) return { ok: false, why: "quests are wired for the game starters; " + (g || "this project") + " has no score to track" };
    var html = files["index.html"] || "";
    if (html.indexOf('id="quest"') >= 0) return { ok: false, why: "this project already has a quest" };
    files["index.html"] = html.replace("</h1>",
      '</h1>\n<div id="quest" class="pill" style="display:inline-block;margin-top:10px">quest · '
      + q[0] + " 0 / " + q[2] + "</div>");
    var js = [
      "/* edit: quest */",
      "var QUEST={name:" + JSON.stringify(q[0]) + ",target:" + q[2] + "},questDone=false;",
      "function questProgress(){return Math.min(" + q[1] + ",QUEST.target);}",
      "function questCheck(){",
      "  var el=document.getElementById('quest');if(!el)return;",
      "  var p=questProgress();",
      "  if(!questDone&&p>=QUEST.target){questDone=true;if(typeof E!=='undefined'&&E.beep)E.beep(1200,.12,'triangle');}",
      "  el.textContent='quest · '+QUEST.name+' '+p+' / '+QUEST.target+(questDone?' ✓':'');",
      "}",
      "setInterval(questCheck,250);questCheck();"
    ].join("\n");
    files["app.js"] = append(files["app.js"], js);
    return { ok: true, fn: "questCheck() in app.js" };
  }

  function dayNight(files) {
    var html = files["index.html"] || "";
    if (html.indexOf('id="daynight"') >= 0) return { ok: false, why: "this project already has a day/night cycle" };
    files["index.html"] = html.replace(/<body([^>]*)>/i, '<body$1>\n<div id="daynight" aria-hidden="true"></div>');
    addCss(files, "#daynight{position:fixed;inset:0;background:#050b18;opacity:0;pointer-events:none;z-index:2147483000}");
    files["app.js"] = append(files["app.js"], [
      "/* edit: day/night */",
      "function dayNight(t){",
      "  var el=document.getElementById('daynight');if(!el)return;",
      "  var p=((t||0)%24000)/24000;",
      "  var dark=Math.max(0,Math.sin(p*Math.PI*2-Math.PI/2));",
      "  el.style.opacity=(0.5*dark).toFixed(3);",
      "}",
      "function dayNightLoop(t){dayNight(t||0);requestAnimationFrame(dayNightLoop);}",
      "requestAnimationFrame(dayNightLoop);"
    ].join("\n"));
    return { ok: true, fn: "dayNight() in app.js" };
  }

  function sound(files, spec, ctx) {
    if (!is3d(files) && !files["engine2d.js"]) {
      return { ok: false, why: "this project has no audio engine; sound applies to game builds" };
    }
    if ((files["index.html"] || "").indexOf('id="muteBtn"') >= 0) {
      return { ok: false, why: "this project already has a sound toggle" };
    }
    addBody(files,
      '<button id="muteBtn" type="button" class="btn ghost" style="position:fixed;right:12px;bottom:12px;z-index:2147483001;padding:6px 10px;font-size:12px">sound on</button>');
    addCss(files, "#muteBtn{opacity:.85}#muteBtn:hover{opacity:1}");
    files["app.js"] = append(files["app.js"], [
      "/* edit: sound */",
      "var soundOn=true;",
      "function soundToggle(){",
      "  soundOn=!soundOn;",
      "  if(typeof E!=='undefined'&&E.mute)E.mute(soundOn);",
      "  var b=document.getElementById('muteBtn');",
      "  if(b)b.textContent=soundOn?'sound on':'muted';",
      "}",
      "var muteBtn=document.getElementById('muteBtn');",
      "if(muteBtn)muteBtn.addEventListener('click',soundToggle);",
      "document.addEventListener('keydown',function(e){if(e.key==='m'||e.key==='M')soundToggle();});"
    ].join("\n"));
    return { ok: true, fn: "soundToggle() in app.js" };
  }

  function harder(files, spec, ctx) {
    var g = genreOf(spec, ctx);
    var js = files["app.js"] || "";
    if (js.indexOf("function hardenEnemies") >= 0 || js.indexOf("HARD_MODE") >= 0) {
      return { ok: false, why: "this project is already in hard mode" };
    }
    var withEnemies = { shooter: 1, twinstick: 1, waveshooter: 1, towerdefense: 1, roguelike: 1 };
    if (withEnemies[g]) {
      var extra = [];
      if (g === "shooter") { js = js.replace("spawn-=.02", "spawn-=.035"); }
      if (g === "towerdefense") {
        js = js.replace(/lives=20/g, "lives=14");
        files["index.html"] = (files["index.html"] || "").replace(/id="lives"([^>]*)>20</, 'id="lives"$1>14<');
      }
      files["app.js"] = append(js, [
        "/* edit: harder */",
        "var HARD_MODE=1.3;",
        "function hardenEnemies(){",
        "  if(typeof enemies!=='undefined')enemies.forEach(function(e){",
        "    if(e.__hard)return;e.__hard=1;",
        "    if(e.speed)e.speed*=HARD_MODE;",
        "    e.hp=(e.hp||1)+1;",
        "    if(e.max)e.max=e.hp+1;",
        "  });",
        "  if(typeof FOES!=='undefined')FOES.forEach(function(f){if(f.__hard)return;f.__hard=1;f.speed*=HARD_MODE;});",
        "}",
        "var baseHardUpdate=E.update;",
        "E.update=function(dt){baseHardUpdate(dt);hardenEnemies();};"
      ].join("\n"));
      return { ok: true, fn: "hardenEnemies() in app.js" };
    }
    if (g === "platformer") {
      var next = js.replace("P.vx=(right?230:0)-(left?230:0)", "P.vx=(right?262:0)-(left?262:0)")
                   .replace("gravity:1500", "gravity:1800");
      if (next === js) return { ok: false, why: "the movement code was edited, so I can't raise the difficulty safely" };
      files["app.js"] = append(next, [
        "/* edit: harder */",
        "var HARD_MODE=1;"
      ].join("\n"));
      return { ok: true, fn: "movement constants in app.js" };
    }
    if (g === "farmingsim") {
      var fjs = js.replace("MAXEN=8", "MAXEN=6").replace("SELL=14", "SELL=10");
      if (fjs === js) return { ok: false, why: "the farm constants were edited, so I can't raise the difficulty safely" };
      files["app.js"] = append(fjs, "/* edit: harder */\nvar HARD_MODE=1;");
      return { ok: true, fn: "energy and price constants in app.js" };
    }
    if (g === "merges") {
      var mjs = js.replace("score=0;moves=25;", "score=0;moves=18;");
      if (mjs === js) return { ok: false, why: "the move limit was edited, so I can't raise the difficulty safely" };
      files["app.js"] = append(mjs, "/* edit: harder */\nvar HARD_MODE=1;");
      return { ok: true, fn: "move limit in app.js" };
    }
    if (g === "rhythm") {
      var rjs = js.replace("SPEED=250", "SPEED=310");
      if (rjs === js) return { ok: false, why: "the note speed was edited, so I can't raise the difficulty safely" };
      files["app.js"] = append(rjs, "/* edit: harder */\nvar HARD_MODE=1;");
      return { ok: true, fn: "note speed in app.js" };
    }
    if (g === "cardbattler") {
      files["app.js"] = append(js, [
        "/* edit: harder */",
        "var HARD_MODE=1;",
        "var baseHardFoe=newFoe;",
        "newFoe=function(){baseHardFoe();foe.atk+=2;};",
        "if(typeof foe!=='undefined'&&foe)foe.atk+=2;"
      ].join("\n"));
      return { ok: true, fn: "newFoe() in app.js" };
    }
    return { ok: false, why: "harder is wired for combat, farming, merge, rhythm, and card builds — " + (g || "this project") + " has no knob for it" };
  }

  function world(files, spec, ctx) {
    var g = genreOf(spec, ctx);
    if (g !== "rpg") return { ok: false, why: "world size applies to the seeded RPG; this is " + (g || "another project") };
    var n = parseInt(ctx && ctx.arg, 10);
    if (!isFinite(n)) n = 96;
    if (n < 32 || n > 256) return { ok: false, why: "pick a world between 32 and 256 tiles" };
    var js = files["app.js"] || "";
    if (!/var SEED=\d+,SIZE=\d+;/.test(js)) {
      return { ok: false, why: "the RPG world constants were edited, so I can't resize it safely" };
    }
    files["app.js"] = js.replace(/(var SEED=\d+,SIZE=)\d+(;)/, "$1" + n + "$2");
    files["index.html"] = (files["index.html"] || "").replace(
      /(world <b style="color:var\(--text\)">)\d+×\d+(<\/b>)/, "$1" + n + "×" + n + "$2");
    spec.scale = n + "×" + n;
    return { ok: true, fn: "SIZE constant in app.js" };
  }

  function isometric(files, spec, ctx) {
    var g = genreOf(spec, ctx);
    var js = files["app.js"] || "";
    if (js.indexOf("function isometricCamera") >= 0) return { ok: false, why: "this project is already isometric" };
    var tilt = { explore: 0.62, builder: 0.62, maze: 0.5, platformer: 0.7 }[g];
    if (!tilt || !is3d(files)) {
      return { ok: false, why: "isometric is wired for 3D explore, builder, maze, and platformer builds (this is a " + (is3d(files) ? g : "2D") + " project)" };
    }
    if (js.indexOf("E.camera.pitch") < 0) return { ok: false, why: "this project does not drive the camera, so an isometric view would do nothing" };
    var yawOffset = (g === "explore" || g === "builder") ? 0.5 : 0;
    files["app.js"] = append(js, [
      "/* edit: isometric */",
      "var ISO_YAW=" + yawOffset + ",ISO_TILT=" + tilt + ";",
      "function isometricCamera(){",
      (yawOffset
        ? "  var d=18,ya=(P.yaw||0)+ISO_YAW;E.camera.x=P.x-Math.sin(ya)*d;E.camera.z=P.z-Math.cos(ya)*d;E.camera.yaw=ya;"
        : "  E.camera.x=P.x;E.camera.z=P.z;E.camera.yaw=(P.yaw||0);"),
      "  E.camera.y=18;E.camera.pitch=ISO_TILT;",
      "}",
      "var baseIsoUpdate=E.update;",
      "E.update=function(dt){baseIsoUpdate(dt);isometricCamera();};"
    ].join("\n"));
    return { ok: true, fn: "isometricCamera() in app.js" };
  }

  function threeD(files, spec, ctx) {
    var g = genreOf(spec, ctx);
    if (spec.dim === "3D") return { ok: false, why: "this project is already 3D" };
    var t = root.toolrxTemplates;
    if (!t || !t.project) return { ok: false, why: "the build templates are not loaded" };
    var supported = { platformer: 1, maze: 1, racer: 1, snake: 1, breakout: 1, pong: 1,
      tetris: 1, minesweeper: 1, "2048": 1, shooter: 1, game: 1 };
    if (!supported[g]) {
      return { ok: false, why: "3D routing is wired for platformer, maze, racer, snake, breakout, pong, tetris, minesweeper, 2048, and shooter" };
    }
    var next = t.spec(g, String(ctx.desc || "") + " 3d", { seed: spec.seed });
    if (next.dim !== "3D") next.dim = "3D";
    var theme = /<html[^>]*class="[^"]*light/i.test(files["index.html"] || "") ? "light" : "dark";
    var built = t.project(g, ctx.desc, { spec: next, theme: theme });
    for (var k in files) if (Object.prototype.hasOwnProperty.call(files, k)) delete files[k];
    for (var f in built.files) if (Object.prototype.hasOwnProperty.call(built.files, f)) files[f] = built.files[f];
    return { ok: true, rebuilt: true, spec: built.spec, fn: "rebuilt app.js and engine3d.js" };
  }

  var PATCHES = {
    "double-jump": { run: doubleJump, repeat: false },
    "enemy-types": { run: enemyTypes, repeat: false },
    "boss": { run: boss, repeat: false },
    "quest": { run: quest, repeat: false },
    "day-night": { run: dayNight, repeat: false },
    "sound": { run: sound, repeat: false },
    "harder": { run: harder, repeat: false },
    "world": { run: world, repeat: true },
    "isometric": { run: isometric, repeat: false },
    "three-d": { run: threeD, repeat: false }
  };

  function apply(id, project, opts) {
    opts = opts || {};
    var patch = PATCHES[id];
    if (!patch) return { ok: false, message: 'unknown edit "' + id + '"' };
    project = project || {};
    var ids = (project.edits || []).slice();
    if (!patch.repeat && ids.indexOf(id) >= 0) {
      return { ok: false, message: "already applied: " + (LABELS[id] || id) };
    }
    var files = clone(project.files || {});
    var spec = {};
    for (var k in (project.spec || {})) if (Object.prototype.hasOwnProperty.call(project.spec, k)) spec[k] = project.spec[k];
    if (!spec.genre) spec.genre = project.kind;
    var ctx = {
      kind: project.kind || spec.genre,
      desc: project.desc || "",
      arg: opts.arg,
      project: project
    };
    var result;
    try { result = patch.run(files, spec, ctx); }
    catch (e) { return { ok: false, message: "the edit failed: " + (e && e.message ? e.message : String(e)) }; }
    if (!result || !result.ok) {
      return { ok: false, message: result && result.why ? result.why : "that edit does not fit this project" };
    }
    if (result.spec) spec = result.spec;
    var replayNote = "";
    if (result.rebuilt) {
      var failed = [];
      ids.forEach(function (prev) {
        if (prev === id || !PATCHES[prev]) return;
        var r = PATCHES[prev].run(files, spec, {
          kind: project.kind || spec.genre, desc: project.desc || "", arg: opts.arg, project: project
        });
        if (!r || !r.ok) failed.push(LABELS[prev] || prev);
      });
      if (failed.length) replayNote = " · could not replay: " + failed.join(", ");
    }
    if (patch.repeat) {
      if (ids.indexOf(id) < 0) ids.push(id);
    } else if (ids.indexOf(id) < 0) {
      ids.push(id);
    }
    spec.edits = ids.map(function (e) { return LABELS[e] || e; });
    if (ids.indexOf("three-d") >= 0 && spec.dim !== "3D") spec.dim = "3D";
    syncDocs(files, spec);
    return {
      ok: true,
      files: files,
      spec: spec,
      edits: ids,
      label: LABELS[id] || id,
      fn: result.fn || "",
      note: replayNote
    };
  }

  /* --------------------------------------------------- multi-file growth -- */
  /* Step 30: grow a project with real module files instead of regenerating it.
   * Modules are plain scripts (no import/export) so they load from file:// and
   * the preview bundler can inline them in document order. Each file is seeded
   * from the project spec, so growth is deterministic and additive. */
  var MODULES = {
    core: "core/state.js",
    ui: "ui/render.js",
    data: "data/seed.js",
    content: "content/seed.js"
  };
  /* Step 40: every system is a real seeded file under systems/. The order is
   * the canonical listing order used by messages and docs. */
  var SYSTEMS = ["inventory", "dialogue", "combat", "save", "quests",
                 "crafting", "ui", "audio", "weather", "particles", "ai"];

  function cloneSpec(spec) {
    return JSON.parse(JSON.stringify(spec || {}));
  }

  function moduleSource(name, spec) {
    var seed = (spec && spec.seed) || 1;
    var kind = JSON.stringify((spec && (spec.genre || spec.kind)) || "app");
    if (name === "core") {
      return [
        "/* toolrx module: core state · generated from the build spec, no model */",
        "(function (root) {",
        "  \"use strict\";",
        "  var state = {}, listeners = [];",
        "  root.toolrxCore = {",
        "    version: 1,",
        "    seed: " + seed + ",",
        "    get: function (k) { return state[k]; },",
        "    set: function (k, v) {",
        "      state[k] = v;",
        "      listeners.forEach(function (fn) { fn(k, v); });",
        "      return v;",
        "    },",
        "    on: function (fn) {",
        "      listeners.push(fn);",
        "      return function () { listeners = listeners.filter(function (f) { return f !== fn; }); };",
        "    },",
        "    keys: function () { return Object.keys(state).sort(); }",
        "  };",
        "})(typeof window !== \"undefined\" ? window : this);",
        ""
      ].join("\n");
    }
    if (name === "ui") {
      return [
        "/* toolrx module: ui helpers · generated from the build spec, no model */",
        "(function (root) {",
        "  \"use strict\";",
        "  root.toolrxUI = {",
        "    text: function (sel, text) {",
        "      var el = document.querySelector(sel);",
        "      if (el) el.textContent = text;",
        "      return !!el;",
        "    },",
        "    on: function (sel, ev, fn) {",
        "      var el = document.querySelector(sel);",
        "      if (el) el.addEventListener(ev, fn);",
        "      return !!el;",
        "    },",
        "    badge: function (label) {",
        "      var b = document.createElement(\"span\");",
        "      b.className = \"pill\";",
        "      b.textContent = label;",
        "      return b;",
        "    }",
        "  };",
        "})(typeof window !== \"undefined\" ? window : this);",
        ""
      ].join("\n");
    }
    if (name === "data") {
      return [
        "/* toolrx module: seeded data · generated from the build spec, no model */",
        "(function (root) {",
        "  \"use strict\";",
        "  function rng(a) {",
        "    return function () {",
        "      a |= 0; a = a + 0x6D2B79F5 | 0;",
        "      var t = Math.imul(a ^ a >>> 15, 1 | a);",
        "      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;",
        "      return ((t ^ t >>> 14) >>> 0) / 4294967296;",
        "    };",
        "  }",
        "  var seed = " + seed + ", roll = rng(seed);",
        "  var names = [\"ember\", \"harbor\", \"signal\", \"hollow\", \"ridge\",",
        "    \"cinder\", \"tide\", \"vault\", \"meadow\", \"spire\"];",
        "  root.toolrxData = {",
        "    seed: seed,",
        "    kind: " + kind + ",",
        "    next: function () { return roll(); },",
        "    pick: function (list) { return list[Math.floor(roll() * list.length)]; },",
        "    names: names",
        "  };",
        "})(typeof window !== \"undefined\" ? window : this);",
        ""
      ].join("\n");
    }
    return [
      "/* toolrx module: content index · generated from the build spec, no model */",
      "(function (root) {",
      "  \"use strict\";",
      "  var c = root.toolrxContent || {};",
      "  function count(name) { return (c[name] || []).length; }",
      "  root.toolrxContentIndex = {",
      "    seed: " + seed + ",",
      "    levels: count(\"levels\"),",
      "    quests: count(\"quests\"),",
      "    npcs: count(\"npcs\"),",
      "    enemies: count(\"enemies\"),",
      "    items: count(\"items\"),",
      "    features: (c.features || []).slice(),",
      "    summary: function () {",
      "      return count(\"levels\") + \" levels · \" + count(\"quests\") + \" quests · \"",
      "        + count(\"npcs\") + \" NPCs · \" + count(\"enemies\") + \" enemies\";",
      "    }",
      "  };",
      "})(typeof window !== \"undefined\" ? window : this);",
      ""
    ].join("\n");
  }

  function hashName(text) {
    var h = 2166136261, i;
    for (i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  /* Step 40: real per-system code. Each file is a plain script, carries its own
   * seeded generator, and registers one API with window.toolrxSystems. The
   * same project seed and system name always produce the same file bytes. */
  function systemSource(name, spec) {
    var seed = ((spec && spec.seed) || 1) >>> 0;
    var local = (seed ^ hashName(name)) >>> 0;
    var projectName = String((spec && (spec.genre || spec.kind || spec.theme))
      || "project").toLowerCase().replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "").slice(0, 40) || "project";
    var project = JSON.stringify(projectName);
    var head = [
      "/* toolrx system: " + name + " · seeded from the build spec, no model */",
      "(function (root) {",
      "  \"use strict\";",
      "  function rng(a) {",
      "    return function () {",
      "      a |= 0; a = a + 0x6D2B79F5 | 0;",
      "      var t = Math.imul(a ^ a >>> 15, 1 | a);",
      "      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;",
      "      return ((t ^ t >>> 14) >>> 0) / 4294967296;",
      "    };",
      "  }",
      "  var seed = " + local + ", roll = rng(seed), project = " + project + ";",
      "  var registry = root.toolrxSystems = root.toolrxSystems || {",
      "    items: {},",
      "    register: function (name, def) { this.items[name] = def; return def; },",
      "    run: function (dt) {",
      "      Object.keys(this.items).sort().forEach(function (k) {",
      "        var item = this.items[k];",
      "        if (item && item.tick) item.tick(dt || 0);",
      "      }, this);",
      "    }",
      "  };"
    ];
    var body = [];

    if (name === "inventory") {
      body = [
        "  var NAMES = [\"ember shard\", \"harbor salt\", \"signal coil\", \"ridge herb\"];",
        "  var items = NAMES.map(function (id) {",
        "    return { id: id, qty: 1 + Math.floor(roll() * 3) };",
        "  });",
        "  function find(id) {",
        "    for (var i = 0; i < items.length; i++) if (items[i].id === id) return items[i];",
        "    return null;",
        "  }",
        "  var api = {",
        "    name: \"inventory\", seed: seed, project: project, items: items,",
        "    list: function () {",
        "      return items.map(function (it) { return it.id + \" x\" + it.qty; });",
        "    },",
        "    count: function (id) { var it = find(id); return it ? it.qty : 0; },",
        "    add: function (id, n) {",
        "      var it = find(id);",
        "      if (!it) { it = { id: String(id), qty: 0 }; items.push(it); }",
        "      it.qty += Math.max(0, n || 1);",
        "      return it.qty;",
        "    },",
        "    remove: function (id, n) {",
        "      var it = find(id);",
        "      if (!it) return 0;",
        "      it.qty = Math.max(0, it.qty - Math.max(0, n || 1));",
        "      return it.qty;",
        "    },",
        "    total: function () {",
        "      return items.reduce(function (n, it) { return n + it.qty; }, 0);",
        "    },",
        "    state: function () {",
        "      return { name: \"inventory\", seed: seed, items: api.list(), total: api.total() };",
        "    }",
        "  };"
      ];
    } else if (name === "dialogue") {
      body = [
        "  var LINES = {",
        "    keeper: [\"the gate remembers you\", \"bring light before the bell\", \"nothing leaves without a name\"],",
        "    scout: [\"tracks east of the ridge\", \"the fog moved against the wind\", \"two shapes, then none\"],",
        "    smith: [\"heat first, then patience\", \"this metal wants a story\", \"come back with both hands\"]",
        "  };",
        "  var cursor = {};",
        "  var api = {",
        "    name: \"dialogue\", seed: seed, project: project, lines: LINES,",
        "    speakers: function () { return Object.keys(LINES).sort(); },",
        "    line: function (who, index) {",
        "      var list = LINES[who] || LINES.keeper;",
        "      var i = Math.max(0, Math.floor(index || 0)) % list.length;",
        "      return list[i];",
        "    },",
        "    say: function (who) {",
        "      var key = LINES[who] ? who : \"keeper\";",
        "      var i = cursor[key] || 0;",
        "      cursor[key] = i + 1;",
        "      return { who: key, line: api.line(key, i) };",
        "    },",
        "    state: function () {",
        "      return { name: \"dialogue\", seed: seed, said: cursor };",
        "    }",
        "  };"
      ];
    } else if (name === "combat") {
      body = [
        "  var TYPES = [\"drone\", \"brute\", \"dart\"];",
        "  var foes = TYPES.map(function (type, i) {",
        "    return {",
        "      type: type,",
        "      hp: 2 + Math.floor(roll() * 4),",
        "      atk: 1 + Math.floor(roll() * 3),",
        "      alive: true",
        "    };",
        "  });",
        "  var api = {",
        "    name: \"combat\", seed: seed, project: project, foes: foes,",
        "    roster: function () {",
        "      return foes.map(function (f) {",
        "        return f.type + \" hp \" + f.hp + (f.alive ? \"\" : \" down\");",
        "      });",
        "    },",
        "    strike: function (index, power) {",
        "      var f = foes[Math.max(0, Math.min(foes.length - 1, index || 0))];",
        "      if (!f || !f.alive) return { ok: false, why: \"that foe is already down\" };",
        "      var dmg = Math.max(1, (power || 2) + Math.floor(roll() * 2));",
        "      f.hp -= dmg;",
        "      if (f.hp <= 0) { f.hp = 0; f.alive = false; }",
        "      return { ok: true, type: f.type, damage: dmg, hp: f.hp, alive: f.alive };",
        "    },",
        "    state: function () {",
        "      return { name: \"combat\", seed: seed, foes: api.roster() };",
        "    }",
        "  };"
      ];
    } else if (name === "save") {
      body = [
        "  var KEY = \"toolrx.save.\" + project;",
        "  var memory = null;",
        "  var api = {",
        "    name: \"save\", seed: seed, project: project, key: KEY,",
        "    save: function (state) {",
        "      var text = JSON.stringify(state == null ? {} : state);",
        "      try {",
        "        if (root.localStorage) { root.localStorage.setItem(KEY, text); return true; }",
        "      } catch (e) { /* fall through to memory */ }",
        "      memory = text;",
        "      return true;",
        "    },",
        "    load: function () {",
        "      var text = memory;",
        "      try {",
        "        if (root.localStorage) {",
        "          var stored = root.localStorage.getItem(KEY);",
        "          if (stored) text = stored;",
        "        }",
        "      } catch (e) { /* use memory */ }",
        "      if (!text) return null;",
        "      try { return JSON.parse(text); } catch (e) { return null; }",
        "    },",
        "    clear: function () {",
        "      memory = null;",
        "      try { if (root.localStorage) root.localStorage.removeItem(KEY); } catch (e) { /* ignore */ }",
        "      return true;",
        "    },",
        "    state: function () { return { name: \"save\", seed: seed, key: KEY, stored: !!api.load() }; }",
        "  };"
      ];
    } else if (name === "quests") {
      body = [
        "  var TITLES = [\"first light\", \"the quiet road\", \"a debt of salt\", \"the last signal\"];",
        "  var quests = TITLES.map(function (title, i) {",
        "    return { id: \"q\" + (i + 1), title: title, status: \"open\" };",
        "  });",
        "  function find(id) {",
        "    for (var i = 0; i < quests.length; i++) if (quests[i].id === id) return quests[i];",
        "    return null;",
        "  }",
        "  var api = {",
        "    name: \"quests\", seed: seed, project: project, quests: quests,",
        "    open: function () {",
        "      return quests.filter(function (q) { return q.status === \"open\"; });",
        "    },",
        "    start: function (id) {",
        "      var q = find(id);",
        "      if (!q) return null;",
        "      if (q.status === \"open\") q.status = \"active\";",
        "      return q.status;",
        "    },",
        "    complete: function (id) {",
        "      var q = find(id);",
        "      if (!q) return null;",
        "      q.status = \"done\";",
        "      return q.status;",
        "    },",
        "    progress: function () {",
        "      var done = quests.filter(function (q) { return q.status === \"done\"; }).length;",
        "      return done + \"/\" + quests.length;",
        "    },",
        "    state: function () {",
        "      return { name: \"quests\", seed: seed, progress: api.progress(), quests: quests };",
        "    }",
        "  };"
      ];
    } else if (name === "crafting") {
      body = [
        "  var RECIPES = [",
        "    { id: \"torch\", needs: { \"ember shard\": 1, \"ridge herb\": 1 }, makes: \"torch\" },",
        "    { id: \"coil\", needs: { \"signal coil\": 1 }, makes: \"tuned coil\" },",
        "    { id: \"salve\", needs: { \"harbor salt\": 1, \"ridge herb\": 2 }, makes: \"salve\" }",
        "  ];",
        "  var stock = { \"ember shard\": 2, \"harbor salt\": 2, \"signal coil\": 1, \"ridge herb\": 3 };",
        "  function recipe(id) {",
        "    for (var i = 0; i < RECIPES.length; i++) if (RECIPES[i].id === id) return RECIPES[i];",
        "    return null;",
        "  }",
        "  var api = {",
        "    name: \"crafting\", seed: seed, project: project, recipes: RECIPES, stock: stock,",
        "    canCraft: function (id) {",
        "      var r = recipe(id);",
        "      if (!r) return false;",
        "      for (var k in r.needs) {",
        "        if (Object.prototype.hasOwnProperty.call(r.needs, k)",
        "            && (stock[k] || 0) < r.needs[k]) return false;",
        "      }",
        "      return true;",
        "    },",
        "    craft: function (id) {",
        "      if (!api.canCraft(id)) return { ok: false, why: \"missing materials\" };",
        "      var r = recipe(id);",
        "      for (var k in r.needs) {",
        "        if (Object.prototype.hasOwnProperty.call(r.needs, k)) stock[k] -= r.needs[k];",
        "      }",
        "      return { ok: true, made: r.makes, left: JSON.parse(JSON.stringify(stock)) };",
        "    },",
        "    state: function () {",
        "      return { name: \"crafting\", seed: seed, stock: JSON.parse(JSON.stringify(stock)) };",
        "    }",
        "  };"
      ];
    } else if (name === "ui") {
      body = [
        "  var panels = [];",
        "  function mount(panel) {",
        "    if (typeof document === \"undefined\" || !document.body) return null;",
        "    var box = document.createElement(\"section\");",
        "    box.className = \"card toolrx-system\";",
        "    box.setAttribute(\"data-toolrx-system\", \"ui\");",
        "    var title = document.createElement(\"h2\");",
        "    title.textContent = panel.name;",
        "    box.appendChild(title);",
        "    (panel.rows || []).forEach(function (row) {",
        "      var p = document.createElement(\"p\");",
        "      p.className = \"muted small\";",
        "      p.textContent = String(row);",
        "      box.appendChild(p);",
        "    });",
        "    document.body.appendChild(box);",
        "    return box;",
        "  }",
        "  var api = {",
        "    name: \"ui\", seed: seed, project: project, panels: panels,",
        "    panel: function (name, rows) {",
        "      var panel = { name: String(name || \"status\"), rows: (rows || []).slice() };",
        "      panels.push(panel);",
        "      return mount(panel);",
        "    },",
        "    mountAll: function () {",
        "      panels.forEach(mount);",
        "      return panels.length;",
        "    },",
        "    state: function () {",
        "      return { name: \"ui\", seed: seed, panels: panels.map(function (p) { return p.name; }) };",
        "    }",
        "  };"
      ];
    } else if (name === "audio") {
      body = [
        "  var CUES = {",
        "    step: { hz: 220, ms: 40 },",
        "    pickup: { hz: 660, ms: 80 },",
        "    hit: { hz: 110, ms: 90 },",
        "    win: { hz: 880, ms: 160 }",
        "  };",
        "  var played = 0;",
        "  var api = {",
        "    name: \"audio\", seed: seed, project: project, cues: CUES,",
        "    cue: function (name) {",
        "      var spec = CUES[name] || CUES.step;",
        "      played++;",
        "      var C = root.AudioContext || root.webkitAudioContext;",
        "      if (!C) return { ok: true, played: played, silent: true, hz: spec.hz };",
        "      try {",
        "        var ctx = api.ctx || (api.ctx = new C());",
        "        var osc = ctx.createOscillator();",
        "        var gain = ctx.createGain();",
        "        osc.frequency.value = spec.hz;",
        "        gain.gain.value = 0.04;",
        "        osc.connect(gain); gain.connect(ctx.destination);",
        "        osc.start();",
        "        osc.stop(ctx.currentTime + spec.ms / 1000);",
        "        return { ok: true, played: played, hz: spec.hz };",
        "      } catch (e) {",
        "        return { ok: true, played: played, silent: true, hz: spec.hz };",
        "      }",
        "    },",
        "    state: function () { return { name: \"audio\", seed: seed, played: played }; }",
        "  };"
      ];
    } else if (name === "weather") {
      body = [
        "  var CYCLE = [\"clear\", \"rain\", \"fog\", \"storm\"];",
        "  var index = Math.floor(roll() * CYCLE.length);",
        "  var time = 0;",
        "  var api = {",
        "    name: \"weather\", seed: seed, project: project, cycle: CYCLE,",
        "    now: function () { return CYCLE[index % CYCLE.length]; },",
        "    step: function (dt) {",
        "      time += Math.max(0, dt || 0);",
        "      if (time >= 30) { time = 0; index = (index + 1) % CYCLE.length; }",
        "      return api.now();",
        "    },",
        "    tick: function (dt) { api.step(dt); },",
        "    state: function () { return { name: \"weather\", seed: seed, now: api.now(), time: time }; }",
        "  };"
      ];
    } else if (name === "particles") {
      body = [
        "  var pool = [];",
        "  var api = {",
        "    name: \"particles\", seed: seed, project: project, pool: pool,",
        "    emit: function (n) {",
        "      var count = Math.max(1, Math.min(64, n || 8));",
        "      for (var i = 0; i < count; i++) {",
        "        pool.push({",
        "          x: Math.floor(roll() * 100), y: Math.floor(roll() * 100),",
        "          vx: roll() * 2 - 1, vy: roll() * 2 - 1, life: 1",
        "        });",
        "      }",
        "      return pool.length;",
        "    },",
        "    step: function (dt) {",
        "      var d = Math.max(0, dt || 0);",
        "      pool.forEach(function (p) {",
        "        p.x += p.vx * d; p.y += p.vy * d; p.life -= d * 0.1;",
        "      });",
        "      pool = pool.filter(function (p) { return p.life > 0; });",
        "      api.pool = pool;",
        "      return pool.length;",
        "    },",
        "    tick: function (dt) { api.step(dt); },",
        "    state: function () { return { name: \"particles\", seed: seed, live: pool.length }; }",
        "  };"
      ];
    } else {
      body = [
        "  var STATES = [\"idle\", \"patrol\", \"chase\"];",
        "  var state = STATES[Math.floor(roll() * STATES.length)];",
        "  var api = {",
        "    name: \"ai\", seed: seed, project: project, states: STATES,",
        "    now: function () { return state; },",
        "    update: function (dt, distance) {",
        "      var d = distance == null ? 999 : distance;",
        "      if (d < 60) state = \"chase\";",
        "      else if (state === \"chase\") state = \"patrol\";",
        "      else if (state === \"idle\" && d < 140) state = \"patrol\";",
        "      else if (state === \"patrol\" && d > 220) state = \"idle\";",
        "      return state;",
        "    },",
        "    tick: function (dt) { api.update(dt, 999); },",
        "    state: function () { return { name: \"ai\", seed: seed, now: state }; }",
        "  };"
      ];
    }

    return head.concat(body, [
      "  registry.register(" + JSON.stringify(name) + ", api);",
      "})(typeof window !== \"undefined\" ? window : this);",
      ""
    ]).join("\n");
  }

  function systemRequest(mode, name) {
    if (mode === "system") return [String(name || "").toLowerCase()];
    if (mode === "systems") {
      var list = Array.isArray(name) ? name : String(name || "").split(/\s+/);
      return list.map(function (s) { return String(s || "").toLowerCase(); })
        .filter(Boolean);
    }
    return [];
  }

  function docRows(added, mode) {
    return added.map(function (p) {
      if (mode === "systems" || p.indexOf("systems/") === 0) {
        return "| `" + p + "` | seeded system · registers with `window.toolrxSystems` |";
      }
      return "| `" + p + "` | generated module · plain script, no build step |";
    }).join("\n");
  }

  function grow(project, which, name) {
    project = project || {};
    var files = clone(project.files || {});
    var spec = cloneSpec(project.spec || {});
    var added = [], skipped = [], mode = String(which || "project").toLowerCase();
    var wanted = String(name || "").toLowerCase();
    var requested = systemRequest(mode, name);

    if (mode === "system" || mode === "systems") {
      var seen = {};
      requested = requested.filter(function (s) {
        if (seen[s]) return false;
        seen[s] = true;
        return true;
      });
      var unknown = requested.filter(function (s) { return SYSTEMS.indexOf(s) < 0; });
      if (!requested.length || unknown.length) {
        return { ok: false, message: "unknown system \""
          + (unknown[0] || "") + "\"; try " + SYSTEMS.join(", ") };
      }
      requested.forEach(function (s) { added.push("systems/" + s + ".js"); });
    } else if (mode === "module") {
      if (!MODULES[wanted]) {
        return { ok: false, message: "unknown module \"" + wanted
          + "\"; try " + Object.keys(MODULES).join(", ") };
      }
      added.push(MODULES[wanted]);
    } else {
      added = Object.keys(MODULES).map(function (k) { return MODULES[k]; });
    }

    var fresh = [];
    added.forEach(function (p) {
      if (files[p]) skipped.push(p);
      else fresh.push(p);
    });
    if (!fresh.length) {
      return { ok: false, skipped: skipped,
        message: "already grown: " + skipped.join(", ") };
    }
    added = fresh;

    added.forEach(function (path) {
      if (path.indexOf("systems/") === 0) {
        var id = path.replace(/^systems\//, "").replace(/\.js$/, "");
        files[path] = systemSource(id, spec);
      } else {
        var mid = Object.keys(MODULES).filter(function (k) { return MODULES[k] === path; })[0];
        files[path] = moduleSource(mid, spec);
      }
    });
    var html = String(files["index.html"] || "");
    var tags = added.map(function (p) {
      return "<script src=\"" + p + "\"></script>";
    }).join("\n");
    if (html.indexOf('src="app.js"') >= 0) {
      files["index.html"] = html.replace('<script src="app.js"></script>',
        tags + "\n<script src=\"app.js\"></script>");
    } else {
      files["index.html"] = html.replace(/<\/body>/i, tags + "\n</body>");
    }
    if (files["app.js"]) {
      var isSystem = added.some(function (p) { return p.indexOf("systems/") === 0; });
      var boot = ["", "/* toolrx modules: real files beside app.js */",
        "window.toolrxProject = window.toolrxProject || { name: "
          + JSON.stringify((spec && (spec.theme || spec.genre)) || project.kind || "app")
          + ", modules: [], systems: [] };",
        "window.toolrxProject.modules = window.toolrxProject.modules || [];",
        "window.toolrxProject.systems = window.toolrxProject.systems || [];"];
      added.forEach(function (p) {
        var target = p.indexOf("systems/") === 0 ? "systems" : "modules";
        boot.push("window.toolrxProject." + target + ".push(" + JSON.stringify(p) + ");");
      });
      if (isSystem) {
        boot.push("if (window.toolrxSystems && window.toolrxSystems.run) window.toolrxSystems.run(0);");
      }
      files["app.js"] = append(files["app.js"], boot.join("\n"));
    }
    var modules = (spec.modules || []).slice();
    var systems = (spec.systems || []).slice();
    added.forEach(function (p) {
      if (p.indexOf("systems/") === 0) {
        var id = p.replace(/^systems\//, "").replace(/\.js$/, "");
        if (systems.indexOf(id) < 0) systems.push(id);
      } else if (modules.indexOf(p) < 0) {
        modules.push(p);
      }
    });
    if (modules.length) spec.modules = modules.sort();
    if (systems.length) spec.systems = systems.sort();
    if (files["README.md"]) {
      var rows = docRows(added, mode);
      files["README.md"] = String(files["README.md"])
        .replace(/\n## Run\b/, "\n" + rows + "\n\n## Run");
    }
    if (files["ARCHITECTURE.md"]) {
      var bullets = added.map(function (p) { return "- `" + p + "`"; }).join("\n");
      files["ARCHITECTURE.md"] = String(files["ARCHITECTURE.md"])
        .replace(/\n## Build order\b/, "\n" + bullets + "\n\n## Build order");
    }
    syncDocs(files, spec);
    var label;
    if (mode === "system") label = "add " + requested[0] + " system";
    else if (mode === "systems") label = "add " + requested.length + " systems ("
      + requested.join(", ") + ")";
    else if (mode === "module") label = "expand module " + wanted;
    else label = "grow project";
    return {
      ok: true,
      files: files,
      spec: spec,
      added: added,
      skipped: skipped,
      label: label,
      message: "added " + added.join(", ")
        + (skipped.length ? " · already present: " + skipped.join(", ") : "")
    };
  }

  /* Aliases used by the deterministic multi-patch command. Keep this table in
   * step with build_commands.py; `resolve` returns a patch id or ""'. */
  var ALIASES = {
    "double jump": "double-jump",
    "a double jump": "double-jump",
    "double-jump": "double-jump",
    "three enemy types": "enemy-types",
    "3 enemy types": "enemy-types",
    "enemy types": "enemy-types",
    "a boss": "boss", "boss": "boss", "boss fight": "boss", "a boss fight": "boss",
    "a quest": "quest", "quest": "quest", "quests": "quest", "a quest line": "quest",
    "day/night": "day-night", "day night": "day-night",
    "day and night": "day-night", "day night cycle": "day-night",
    "sound": "sound", "sound effects": "sound", "audio": "sound",
    "harder": "harder", "hard mode": "harder",
    "isometric": "isometric", "isometric view": "isometric",
    "3d": "three-d", "3-d": "three-d", "three-d": "three-d"
  };

  function resolve(text) {
    var s = String(text || "").toLowerCase()
      .replace(/^(?:add|give it|make it|switch to|apply)\s+/, "")
      .replace(/\s+/g, " ").trim();
    if (PATCHES[s]) return s;
    return ALIASES[s] || "";
  }

  root.toolrxPatches = {
    apply: apply,
    grow: grow,
    resolve: resolve,
    modules: function () { return Object.keys(MODULES).sort(); },
    systems: function () { return SYSTEMS.slice(); },
    labels: function () { var o = {}; for (var k in LABELS) o[k] = LABELS[k]; return o; },
    list: function () { return Object.keys(PATCHES); },
    has: function (id) { return !!PATCHES[id]; }
  };
})(typeof self !== "undefined" ? self : this);

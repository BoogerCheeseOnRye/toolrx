/* toolrx build templates.
 *
 * "build a calculator app" has to produce something real and deterministic, so
 * every template here is a complete, self-contained HTML document: no network,
 * no external assets, no model. The same request always renders the same page.
 *
 * Exposes: self.toolrxTemplates = { build, title, kinds }
 */
(function (root) {
  "use strict";

  function esc(s) {
    return String(s === undefined || s === null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  var COMMON = [
    ":root{--bg:#0b1020;--bg2:#0e1730;--panel:#121a2e;--panel2:#0d1527;--text:#e6edf7;",
    "--muted:#8fa0bd;--accent:#22d3ee;--accent2:#a78bfa;--border:#22304d;--ok:#34d399;--warn:#fbbf24;--bad:#fb7185;",
    "--shadow:0 18px 50px rgba(2,6,20,.45)}",
    "html.light{--bg:#f4f7fc;--bg2:#e9eff9;--panel:#ffffff;--panel2:#f1f5fb;--text:#0f172a;--muted:#5b6b88;",
    "--border:#d7e0ee;--shadow:0 18px 40px rgba(15,23,42,.12)}",
    "*{box-sizing:border-box}",
    "body{margin:0;min-height:100vh;color:var(--text);font:15px/1.55 ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;",
    "background:radial-gradient(1000px 600px at 15% -10%,rgba(34,211,238,.16),transparent 60%),",
    "radial-gradient(900px 500px at 100% 0%,rgba(167,139,250,.16),transparent 55%),",
    "linear-gradient(160deg,var(--bg),var(--bg2));padding:22px}",
    ".wrap{max-width:980px;margin:0 auto}.narrow{max-width:560px}",
    "header.hero{display:flex;flex-direction:column;gap:6px;margin-bottom:16px}",
    ".badge{align-self:flex-start;font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);",
    "border:1px solid rgba(34,211,238,.35);background:rgba(34,211,238,.08);padding:3px 9px;border-radius:999px}",
    "h1{font-size:clamp(22px,4vw,34px);line-height:1.15;margin:2px 0 0;letter-spacing:-.02em}",
    ".sub{color:var(--muted);margin:0;font-size:13.5px}",
    ".card{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--border);",
    "border-radius:16px;padding:18px;box-shadow:var(--shadow)}",
    ".row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}",
    ".grow{flex:1;min-width:0}",
    "input,select,textarea,button{font:inherit;color:var(--text)}",
    "input,select,textarea{background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:10px 12px;outline:none;width:100%}",
    "input:focus,select:focus,textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(34,211,238,.14)}",
    ".btn{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#04121a;border:0;border-radius:10px;",
    "padding:10px 15px;font-weight:700;cursor:pointer;white-space:nowrap;transition:transform .12s,filter .12s}",
    ".btn:hover{transform:translateY(-1px);filter:brightness(1.05)}.btn:active{transform:translateY(0)}",
    ".btn.ghost{background:var(--panel2);color:var(--text);border:1px solid var(--border);font-weight:600}",
    ".btn.danger{background:linear-gradient(135deg,var(--bad),#b91c1c);color:#fff}",
    ".muted{color:var(--muted)}.small{font-size:12px}",
    ".pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border);background:var(--panel2);",
    "padding:4px 10px;border-radius:999px;font-size:12px;color:var(--muted)}",
    ".stat{background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:12px 14px}",
    ".stat b{display:block;font-size:22px;letter-spacing:-.02em}",
    ".stat span{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}",
    ".grid{display:grid;gap:10px}",
    "footer{margin:18px auto 0;max-width:980px;color:var(--muted);font-size:11.5px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}",
    "footer b{color:var(--accent);font-weight:600}",
    "@media(max-width:560px){body{padding:14px}.card{padding:14px;border-radius:14px}}"
  ].join("");

  function shell(o) {
    var cls = o.theme === "light" ? "light" : "dark";
    return "<!doctype html>\n<html lang=\"en\" class=\"" + cls + "\">\n<head>\n" +
      "<meta charset=\"utf-8\">\n" +
      "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n" +
      "<title>" + esc(o.title) + " · toolrx</title>\n" +
      "<style>" + COMMON + (o.css || "") + "</style>\n</head>\n<body>\n" +
      "<div class=\"wrap\">\n" +
      "<header class=\"hero\"><span class=\"badge\">toolrx build</span><h1>" + esc(o.title) + "</h1>" +
      "<p class=\"sub\">" + esc(o.sub) + "</p></header>\n" +
      (o.body || "") + "\n</div>\n" +
      "<footer><span>built by <b>toolrx</b> · deterministic template · no model, no network</span>" +
      "<span id=\"stamp\">offline · single file</span></footer>\n" +
      (o.js ? "<script>\n" + o.js + "\n</script>\n" : "") +
      "</body>\n</html>\n";
  }

  /* ---------------------------------------------------------- calculator -- */
  function calculator(desc, opts) {
    var body = [
      '<div class="card">',
      '<div style="text-align:right;padding:10px 6px 16px">',
      '<div id="hist" class="muted small" style="min-height:18px"></div>',
      '<div id="out" style="font-size:clamp(30px,7vw,44px);font-weight:700;letter-spacing:-.03em;word-break:break-all">0</div>',
      '</div>',
      '<div class="keys" style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">',
      key("C", "fn"), key("⌫", "fn"), key("%", "fn"), key("÷", "op"),
      key("7"), key("8"), key("9"), key("×", "op"),
      key("4"), key("5"), key("6"), key("−", "op"),
      key("1"), key("2"), key("3"), key("+", "op"),
      key("±", "fn"), key("0"), key("."), key("=", "eq"),
      '</div>',
      '<p class="muted small" style="margin:12px 2px 0">keyboard: digits, + − * / % ( ) · Enter = · Esc clears</p>',
      '</div>'
    ].join("");
    var css = ".keys button{padding:16px 0;font-size:18px;font-weight:600;border-radius:12px;border:1px solid var(--border);" +
      "background:var(--panel2);cursor:pointer;transition:transform .08s,background .12s}" +
      ".keys button:hover{background:#1a2740}html.light .keys button:hover{background:#e6eefb}" +
      ".keys button:active{transform:scale(.97)}" +
      ".keys button.op{color:var(--accent);border-color:rgba(34,211,238,.35)}" +
      ".keys button.fn{color:var(--muted)}" +
      ".keys button.eq{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#04121a;border:0}";
    var js = [
      "var expr='';var last='';",
      "var out=document.getElementById('out'),hist=document.getElementById('hist');",
      "function render(){out.textContent=expr||'0';hist.textContent=last;}",
      "function calc(){var s=expr.replace(/×/g,'*').replace(/÷/g,'/').replace(/−/g,'-');",
      "if(!s)return;if(!/^[0-9+\\-*/().%\\s]+$/.test(s)){out.textContent='error';return;}",
      "try{var v=Function('return ('+s+')')();if(!isFinite(v))throw 0;",
      "var r=Math.round(v*1e10)/1e10;last=s+' =';expr=String(r);render();}",
      "catch(e){out.textContent='error';}}",
      "function press(k){",
      "if(k==='C'){expr='';last='';}else if(k==='⌫'){expr=expr.slice(0,-1);}",
      "else if(k==='='){calc();return;}else if(k==='±'){if(expr&&expr[0]==='-')expr=expr.slice(1);else expr='-'+expr;}",
      "else if(k==='%'){expr=expr+'%';}else{expr=expr+k;}render();}",
      "document.querySelectorAll('.keys button').forEach(function(b){b.addEventListener('click',function(){press(b.textContent);});});",
      "document.addEventListener('keydown',function(e){",
      "var k=e.key;if(k==='Enter'){press('=');e.preventDefault();}else if(k==='Escape'){press('C');}",
      "else if(k==='Backspace'){press('⌫');e.preventDefault();}",
      "else if(/^[0-9.+\\-*/%()]$/.test(k)){press(k==='*'?'×':k==='/'?'÷':k==='-'?'−':k);e.preventDefault();}});",
      "render();"
    ].join("\n");
    return shell({ title: "Calculator", sub: "keyboard ready · exact arithmetic, no surprises", body: body, css: css, js: js, theme: opts.theme });
  }

  function key(label, cls) {
    return '<button type="button" class="' + (cls || "") + '">' + label + "</button>";
  }

  /* ---------------------------------------------------------- todo list -- */
  function todo(desc, opts) {
    var body = [
      '<div class="card">',
      '<form id="add" class="row" style="margin-bottom:12px">',
      '<input id="txt" class="grow" placeholder="what needs doing?" autocomplete="off">',
      '<button class="btn" type="submit">Add</button>',
      '</form>',
      '<div class="row small muted" style="justify-content:space-between;margin-bottom:8px">',
      '<span id="count">0 open</span><button id="clear" class="btn ghost" type="button" style="padding:5px 10px;font-size:12px">clear done</button>',
      '</div>',
      '<ul id="list" style="list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:7px"></ul>',
      '<p id="empty" class="muted small" style="margin:14px 2px 0">nothing yet — add the first task above.</p>',
      '</div>'
    ].join("");
    var js = [
      "var KEY='toolrx.todo.v1';var items=[];",
      "try{items=JSON.parse(localStorage.getItem(KEY)||'[]')}catch(e){items=[]}",
      "if(!Array.isArray(items))items=[];",
      "var list=document.getElementById('list'),count=document.getElementById('count'),empty=document.getElementById('empty');",
      "function save(){try{localStorage.setItem(KEY,JSON.stringify(items))}catch(e){}}",
      "function draw(){list.innerHTML='';",
      "items.forEach(function(it,i){var li=document.createElement('li');",
      "li.style.cssText='display:flex;align-items:center;gap:9px;background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:9px 11px';",
      "var cb=document.createElement('input');cb.type='checkbox';cb.checked=!!it.done;cb.style.cssText='width:18px;height:18px;accent-color:#22d3ee';",
      "cb.addEventListener('change',function(){items[i].done=cb.checked;save();draw();});",
      "var s=document.createElement('span');s.textContent=it.text;s.style.cssText='flex:1;min-width:0;word-break:break-word'+(it.done?';opacity:.5;text-decoration:line-through':'');",
      "var x=document.createElement('button');x.type='button';x.textContent='×';x.title='delete';",
      "x.style.cssText='background:none;border:0;color:var(--muted);font-size:18px;cursor:pointer;padding:0 3px';",
      "x.addEventListener('click',function(){items.splice(i,1);save();draw();});",
      "li.append(cb,s,x);list.appendChild(li);});",
      "var open=items.filter(function(x){return !x.done}).length;",
      "count.textContent=open+' open · '+items.length+' total';",
      "empty.style.display=items.length?'none':'block';}",
      "document.getElementById('add').addEventListener('submit',function(e){e.preventDefault();",
      "var t=document.getElementById('txt').value.trim();if(!t)return;items.push({text:t,done:false});",
      "document.getElementById('txt').value='';save();draw();});",
      "document.getElementById('clear').addEventListener('click',function(){items=items.filter(function(x){return !x.done});save();draw();});",
      "draw();"
    ].join("\n");
    return shell({ title: "Todo list", sub: "add, tick off, and keep tasks in this browser", body: body, js: js, theme: opts.theme });
  }

  /* -------------------------------------------------------------- timer -- */
  function timer(desc, opts) {
    var body = [
      '<div class="card" style="text-align:center">',
      '<div id="ring" style="--p:0;width:min(260px,72vw);aspect-ratio:1;margin:6px auto 16px;border-radius:50%;',
      'background:conic-gradient(var(--accent) calc(var(--p)*1%),var(--panel2) 0);display:grid;place-items:center;position:relative">',
      '<div style="position:absolute;inset:12px;border-radius:50%;background:var(--panel);display:grid;place-items:center">',
      '<div><div id="time" style="font-size:clamp(34px,8vw,46px);font-weight:700;font-variant-numeric:tabular-nums">05:00</div>',
      '<div id="phase" class="muted small">ready</div></div></div></div>',
      '<div class="row" style="justify-content:center;margin-bottom:12px">',
      '<button class="btn ghost" type="button" data-min="1">1m</button>',
      '<button class="btn ghost" type="button" data-min="5">5m</button>',
      '<button class="btn ghost" type="button" data-min="10">10m</button>',
      '<button class="btn ghost" type="button" data-min="25">25m</button>',
      '</div>',
      '<div class="row" style="justify-content:center;margin-bottom:14px">',
      '<input id="mins" type="number" min="0" max="180" value="5" style="width:92px;text-align:center">',
      '<span class="muted">min</span>',
      '<button class="btn" id="start" type="button">Start</button>',
      '<button class="btn ghost" id="reset" type="button">Reset</button>',
      '</div>',
      '<p class="muted small" style="margin:0">a soft chime plays when the countdown reaches zero.</p>',
      '</div>'
    ].join("");
    var js = [
      "var total=300,left=300,iv=null,ring=document.getElementById('ring'),time=document.getElementById('time'),phase=document.getElementById('phase');",
      "function paint(){var m=Math.floor(left/60),s=left%60;time.textContent=('0'+m).slice(-2)+':'+('0'+s).slice(-2);",
      "ring.style.setProperty('--p',total?Math.round(100*left/total):0);}",
      "function setMin(m){stop();total=Math.max(0,Math.min(180,Math.round(m)))*60;left=total;phase.textContent='ready';paint();",
      "document.getElementById('mins').value=Math.round(total/60);}",
      "function stop(){if(iv){clearInterval(iv);iv=null;}document.getElementById('start').textContent='Start';}",
      "function chime(){try{var a=new (window.AudioContext||window.webkitAudioContext)();var o=a.createOscillator(),g=a.createGain();",
      "o.type='sine';o.frequency.value=880;g.gain.value=.22;o.connect(g);g.connect(a.destination);o.start();",
      "o.stop(a.currentTime+.5);}catch(e){}}",
      "function start(){if(iv){stop();phase.textContent='paused';return;}",
      "if(left<=0)left=total;if(!left)return;phase.textContent='running';",
      "document.getElementById('start').textContent='Pause';",
      "var end=Date.now()+left*1000;iv=setInterval(function(){left=Math.max(0,Math.round((end-Date.now())/1000));paint();",
      "if(left===0){stop();phase.textContent='done';chime();}},250);}",
      "document.querySelectorAll('[data-min]').forEach(function(b){b.addEventListener('click',function(){setMin(+b.dataset.min);});});",
      "document.getElementById('mins').addEventListener('change',function(){setMin(+this.value||0);});",
      "document.getElementById('start').addEventListener('click',start);",
      "document.getElementById('reset').addEventListener('click',function(){stop();left=total;phase.textContent='ready';paint();});",
      "paint();"
    ].join("\n");
    return shell({ title: "Countdown timer", sub: "pick a length, press start, get a chime", body: body, js: js, theme: opts.theme });
  }

  /* ---------------------------------------------------------- stopwatch -- */
  function stopwatch(desc, opts) {
    var body = [
      '<div class="card" style="text-align:center">',
      '<div id="time" style="font-size:clamp(40px,10vw,58px);font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.02em">00:00.00</div>',
      '<div class="row" style="justify-content:center;margin:16px 0 14px">',
      '<button class="btn" id="go" type="button">Start</button>',
      '<button class="btn ghost" id="lap" type="button">Lap</button>',
      '<button class="btn ghost" id="rst" type="button">Reset</button>',
      '</div>',
      '<ol id="laps" style="list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px;text-align:left"></ol>',
      '</div>'
    ].join("");
    var js = [
      "var t0=0,acc=0,iv=null;var el=document.getElementById('time'),laps=document.getElementById('laps'),go=document.getElementById('go');",
      "function ms(){return acc+(iv?Date.now()-t0:0);}",
      "function fmt(n){var m=Math.floor(n/60000),s=Math.floor(n%60000/1000),c=Math.floor(n%1000/10);",
      "return ('0'+m).slice(-2)+':'+('0'+s).slice(-2)+'.'+('0'+c).slice(-2);}",
      "function paint(){el.textContent=fmt(ms());}",
      "function start(){if(iv){acc=ms();clearInterval(iv);iv=null;go.textContent='Start';}",
      "else{t0=Date.now();iv=setInterval(paint,31);go.textContent='Stop';}}",
      "go.addEventListener('click',start);",
      "document.getElementById('rst').addEventListener('click',function(){if(iv)clearInterval(iv);iv=null;acc=0;go.textContent='Start';paint();laps.innerHTML='';});",
      "document.getElementById('lap').addEventListener('click',function(){",
      "if(!iv&&!acc)return;var li=document.createElement('li');li.textContent=fmt(ms());",
      "li.style.cssText='display:flex;justify-content:space-between;padding:8px 10px;border:1px solid var(--border);border-radius:9px;background:var(--panel2);font-variant-numeric:tabular-nums';",
      "li.innerHTML='<span class=\"muted\">lap '+(laps.children.length+1)+'</span><span>'+fmt(ms())+'</span>';laps.prepend(li);});",
      "paint();"
    ].join("\n");
    return shell({ title: "Stopwatch", sub: "start, lap, stop — hundredths of a second", body: body, js: js, theme: opts.theme });
  }

  /* -------------------------------------------------------------- notes -- */
  function notes(desc, opts) {
    var body = [
      '<div class="card">',
      '<textarea id="note" rows="14" placeholder="start typing…" style="resize:vertical;font-family:ui-monospace,monospace;font-size:13.5px;line-height:1.6"></textarea>',
      '<div class="row small muted" style="justify-content:space-between;margin-top:10px">',
      '<span id="stats">0 words · 0 chars</span>',
      '<span class="row" style="gap:7px">',
      '<button class="btn ghost" id="copy" type="button" style="padding:6px 10px;font-size:12px">copy</button>',
      '<button class="btn ghost" id="save" type="button" style="padding:6px 10px;font-size:12px">download</button>',
      '</span></div>',
      '<p class="muted small" style="margin:8px 2px 0">autosaves locally while you type. nothing is uploaded.</p>',
      '</div>'
    ].join("");
    var js = [
      "var KEY='toolrx.note.v1',el=document.getElementById('note'),stats=document.getElementById('stats');",
      "try{el.value=localStorage.getItem(KEY)||''}catch(e){}",
      "function count(){var t=el.value;var w=(t.match(/[A-Za-z0-9']+/g)||[]).length;",
      "stats.textContent=w+' words · '+t.length+' chars · '+t.split('\\n').length+' lines';",
      "try{localStorage.setItem(KEY,t)}catch(e){}}",
      "el.addEventListener('input',count);count();",
      "document.getElementById('copy').addEventListener('click',function(){",
      "el.select();try{document.execCommand('copy')}catch(e){}window.getSelection().removeAllRanges();});",
      "document.getElementById('save').addEventListener('click',function(){",
      "var b=new Blob([el.value],{type:'text/plain'}),a=document.createElement('a');",
      "a.href=URL.createObjectURL(b);a.download='notes.txt';a.click();setTimeout(function(){URL.revokeObjectURL(a.href)},1000);});"
    ].join("\n");
    return shell({ title: "Notes", sub: "a quiet place to write · autosaved in this browser", body: body, js: js, theme: opts.theme });
  }

  /* --------------------------------------------------------- tic tac toe -- */
  function tictactoe(desc, opts) {
    var body = [
      '<div class="card" style="max-width:420px;margin:0 auto;text-align:center">',
      '<div class="row" style="justify-content:space-between;margin-bottom:12px">',
      '<span class="pill">turn: <b id="turn" style="color:var(--text)">X</b></span>',
      '<span class="pill">score <b id="score" style="color:var(--text)">0 – 0</b></span>',
      '</div>',
      '<div id="board" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px"></div>',
      '<p id="msg" class="muted" style="min-height:24px;margin:12px 0 4px">X goes first.</p>',
      '<button class="btn ghost" id="new" type="button">New round</button>',
      '</div>'
    ].join("");
    var css = "#board button{aspect-ratio:1;font-size:clamp(30px,9vw,46px);font-weight:700;border-radius:12px;" +
      "border:1px solid var(--border);background:var(--panel2);cursor:pointer;color:var(--text)}" +
      "#board button.win{background:rgba(52,211,153,.18);border-color:var(--ok);color:var(--ok)}" +
      "#board button:disabled{cursor:default}";
    var js = [
      "var b=Array(9).fill(''),turn='X',over=false,wins=0,losses=0,draws=0;",
      "var board=document.getElementById('board'),msg=document.getElementById('msg'),turnEl=document.getElementById('turn'),score=document.getElementById('score');",
      "var LINES=[[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];",
      "function winner(){for(var i=0;i<LINES.length;i++){var l=LINES[i];if(b[l[0]]&&b[l[0]]===b[l[1]]&&b[l[0]]===b[l[2]])return l;}return null;}",
      "function paint(){board.innerHTML='';b.forEach(function(v,i){var x=document.createElement('button');x.type='button';x.textContent=v;",
      "x.disabled=!!v||over;x.addEventListener('click',function(){play(i)});board.appendChild(x);});}",
      "function play(i){if(over||b[i])return;b[i]=turn;var w=winner();",
      "if(w){over=true;paint();w.forEach(function(k){board.children[k].classList.add('win')});",
      "if(turn==='X')wins++;else losses++;score.textContent=wins+' – '+losses;msg.textContent=turn+' wins!';return;}",
      "if(b.every(Boolean)){over=true;paint();msg.textContent='draw — nobody wins this one.';return;}",
      "turn=turn==='X'?'O':'X';turnEl.textContent=turn;msg.textContent='turn: '+turn;paint();}",
      "document.getElementById('new').addEventListener('click',function(){b=Array(9).fill('');turn='X';over=false;turnEl.textContent='X';msg.textContent='X goes first.';paint();});",
      "paint();"
    ].join("\n");
    return shell({ title: "Tic tac toe", sub: "two players, one keyboard-free board", body: body, css: css, js: js, theme: opts.theme });
  }

  /* -------------------------------------------------------------- memory -- */
  function memory(desc, opts) {
    var body = [
      '<div class="card" style="max-width:560px;margin:0 auto">',
      '<div class="row" style="justify-content:space-between;margin-bottom:12px">',
      '<span class="pill">moves <b id="moves" style="color:var(--text)">0</b></span>',
      '<span class="pill">pairs <b id="pairs" style="color:var(--text)">0 / 8</b></span>',
      '<button class="btn ghost" id="new" type="button" style="padding:6px 11px;font-size:12px">shuffle</button>',
      '</div>',
      '<div id="board" style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px"></div>',
      '<p id="msg" class="muted" style="min-height:22px;margin:12px 0 0">flip two cards to find a pair.</p>',
      '</div>'
    ].join("");
    var css = "#board button{aspect-ratio:1;border-radius:12px;border:1px solid var(--border);background:var(--panel2);" +
      "font-size:clamp(20px,6vw,30px);cursor:pointer;color:transparent;transition:transform .12s,background .12s}" +
      "#board button.up{background:rgba(34,211,238,.14);border-color:var(--accent);color:var(--text)}" +
      "#board button.done{background:rgba(52,211,153,.16);border-color:var(--ok);color:var(--text);cursor:default}";
    var js = [
      "var ICONS=['◆','●','▲','★','✦','☂','☀','♥'];",
      "var cards=[],first=null,lock=false,moves=0,found=0;",
      "var board=document.getElementById('board'),msg=document.getElementById('msg');",
      "function seed(s){var h=2166136261;for(var i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}",
      "return function(){h+=0x6D2B79F5;var t=h;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};}",
      "var rand=seed('memory');",
      "function reset(){cards=ICONS.concat(ICONS);for(var i=cards.length-1;i>0;i--){var j=Math.floor(rand()*(i+1));var t=cards[i];cards[i]=cards[j];cards[j]=t;}",
      "first=null;lock=false;moves=0;found=0;msg.textContent='flip two cards to find a pair.';draw();}",
      "function draw(){board.innerHTML='';cards.forEach(function(v,i){var x=document.createElement('button');x.type='button';",
      "x.textContent=v;x.dataset.i=i;if(x.classList.contains('up')){}x.addEventListener('click',function(){flip(i,x)});board.appendChild(x);});}",
      "function flip(i,el){if(lock||el.classList.contains('up')||el.classList.contains('done'))return;",
      "el.classList.add('up');el.textContent=cards[i];",
      "if(first===null){first={i:i,el:el};return;}",
      "moves++;document.getElementById('moves').textContent=moves;",
      "if(cards[first.i]===cards[i]){first.el.classList.add('done');el.classList.add('done');found++;",
      "document.getElementById('pairs').textContent=found+' / 8';first=null;",
      "if(found===8)msg.textContent='solved in '+moves+' moves.';return;}",
      "lock=true;var a=first.el,b=el;first=null;",
      "setTimeout(function(){a.classList.remove('up');b.classList.remove('up');a.textContent='';b.textContent='';lock=false;},640);}",
      "document.getElementById('new').addEventListener('click',reset);reset();"
    ].join("\n");
    return shell({ title: "Memory game", sub: "eight pairs · find them all in as few moves as you can", body: body, css: css, js: js, theme: opts.theme });
  }

  /* ----------------------------------------------------------- converter -- */
  function converter(desc, opts) {
    var body = [
      '<div class="card">',
      '<label class="small muted" for="cat">category</label>',
      '<select id="cat" style="margin:4px 0 12px">',
      '<option value="length">length</option><option value="mass">mass</option>',
      '<option value="temperature">temperature</option><option value="volume">volume</option>',
      '<option value="data">data</option><option value="time">time</option><option value="speed">speed</option>',
      '</select>',
      '<div class="row" style="align-items:stretch">',
      '<div class="grow"><label class="small muted" for="amt">amount</label>',
      '<input id="amt" type="number" value="1" step="any" style="margin-top:4px;font-size:22px;font-weight:600"></div>',
      '<div class="grow"><label class="small muted" for="from">from</label><select id="from" style="margin-top:4px"></select></div>',
      '<div class="grow"><label class="small muted" for="to">to</label><select id="to" style="margin-top:4px"></select></div>',
      '</div>',
      '<div style="margin-top:16px;padding:16px;border:1px solid var(--border);border-radius:12px;background:var(--panel2)">',
      '<div id="out" style="font-size:clamp(24px,5vw,34px);font-weight:700;letter-spacing:-.02em">1 m = 3.28084 ft</div>',
      '<div id="formula" class="muted small" style="margin-top:4px">exact factor conversion</div>',
      '</div>',
      '<p class="muted small" style="margin:12px 2px 0">temperature uses the real offsets; everything else is a ratio.</p>',
      '</div>'
    ].join("");
    var js = [
      "var U={length:{m:1,km:1000,cm:.01,mm:.001,in:.0254,ft:.3048,yd:.9144,mi:1609.344,nmi:1852,",
      "label:{m:'m',km:'km',cm:'cm',mm:'mm',in:'in',ft:'ft',yd:'yd',mi:'mi',nmi:'nmi'}},",
      "mass:{kg:1,g:.001,mg:1e-6,t:1000,oz:28.349523125,lb:453.59237,st:6350.29318,",
      "label:{kg:'kg',g:'g',mg:'mg',t:'t',oz:'oz',lb:'lb',st:'st'}},",
      "volume:{l:1,ml:.001,tsp:.00492892159375,tbsp:.01478676478125,cup:.2365882365,pt:.473176473,qt:.946352946,gal:3.785411784,",
      "label:{l:'L',ml:'mL',tsp:'tsp',tbsp:'tbsp',cup:'cups',pt:'pt',qt:'qt',gal:'gal'}},",
      "data:{b:1,kb:1e3,mb:1e6,gb:1e9,tb:1e12,kib:1024,mib:1048576,gib:1073741824,",
      "label:{b:'B',kb:'KB',mb:'MB',gb:'GB',tb:'TB',kib:'KiB',mib:'MiB',gib:'GiB'}},",
      "time:{s:1,ms:.001,min:60,h:3600,day:86400,week:604800,",
      "label:{s:'s',ms:'ms',min:'min',h:'h',day:'days',week:'weeks'}},",
      "speed:{mps:1,kph:.2777777777777778,mph:.44704,knot:.5144444444444445,",
      "label:{mps:'m/s',kph:'km/h',mph:'mph',knot:'kn'}},",
      "temperature:{c:1,f:1,k:1,label:{c:'°C',f:'°F',k:'K'}}};",
      "var cat=document.getElementById('cat'),from=document.getElementById('from'),to=document.getElementById('to'),",
      "amt=document.getElementById('amt'),out=document.getElementById('out'),formula=document.getElementById('formula');",
      "function fill(){var u=Object.keys(U[cat.value]);from.innerHTML='';to.innerHTML='';",
      "u.forEach(function(k,i){var a=document.createElement('option');a.value=k;a.textContent=U[cat.value].label[k]||k;",
      "var b=a.cloneNode(true);from.appendChild(a);to.appendChild(b);if(i===1)to.value=k;});}",
      "function conv(n,a,b){if(cat.value==='temperature'){",
      "var c=a==='c'?n:a==='f'?(n-32)*5/9:n-273.15;",
      "return b==='c'?c:b==='f'?c*9/5+32:c+273.15;}",
      "var f=U[cat.value];return n*f[a]/f[b];}",
      "function paint(){var n=parseFloat(amt.value);if(!isFinite(n))n=0;var v=conv(n,from.value,to.value);",
      "var la=U[cat.value].label[from.value]||from.value,lb=U[cat.value].label[to.value]||to.value;",
      "var r=Math.round(v*1e8)/1e8;out.textContent=n+' '+la+' = '+r+' '+lb;",
      "formula.textContent=cat.value==='temperature'?'offset conversion (°C ↔ °F ↔ K)':'ratio conversion via a fixed base unit';}",
      "cat.addEventListener('change',function(){fill();paint();});",
      "[amt,from,to].forEach(function(e){e.addEventListener('input',paint);e.addEventListener('change',paint);});",
      "fill();paint();"
    ].join("\n");
    return shell({ title: "Unit converter", sub: "length, mass, temperature, volume, data, time, speed", body: body, js: js, theme: opts.theme });
  }

  /* -------------------------------------------------------------- chart -- */
  function chart(desc, opts) {
    var body = [
      '<div class="card">',
      '<div class="row" style="justify-content:space-between;margin-bottom:10px">',
      '<span class="pill">bar chart · live</span>',
      '<button class="btn ghost" id="draw" type="button" style="padding:6px 11px;font-size:12px">redraw</button>',
      '</div>',
      '<canvas id="cv" width="900" height="420" style="width:100%;height:auto;border-radius:12px;background:var(--panel2);border:1px solid var(--border)"></canvas>',
      '<label class="small muted" for="data" style="display:block;margin-top:12px">values (comma separated)</label>',
      '<input id="data" value="12, 30, 7, 41, 25, 18, 33" style="margin-top:4px">',
      '<p class="muted small" style="margin:10px 2px 0">drawn with plain canvas 2D — no chart library.</p>',
      '</div>'
    ].join("");
    var js = [
      "var cv=document.getElementById('cv'),ctx=cv.getContext('2d'),data=document.getElementById('data');",
      "function draw(){var vals=data.value.split(',').map(function(x){return parseFloat(x.trim())}).filter(function(x){return isFinite(x)});",
      "var W=cv.width,H=cv.height,pad=46,bw=(W-pad*2)/Math.max(1,vals.length);var max=Math.max.apply(null,vals.concat([1]));",
      "ctx.clearRect(0,0,W,H);",
      "var light=document.documentElement.classList.contains('light');",
      "ctx.strokeStyle=light?'#d7e0ee':'#22304d';ctx.lineWidth=1;ctx.fillStyle=light?'#5b6b88':'#8fa0bd';ctx.font='13px system-ui';",
      "for(var i=0;i<=4;i++){var y=pad+(H-pad*1.6)*i/4;ctx.beginPath();ctx.moveTo(pad,y);ctx.lineTo(W-pad/2,y);ctx.stroke();",
      "ctx.fillText(String(Math.round(max*(4-i)/4)),6,y+4);}",
      "var g=ctx.createLinearGradient(0,pad,0,H-pad);g.addColorStop(0,'#22d3ee');g.addColorStop(1,'#a78bfa');",
      "vals.forEach(function(v,i){var h=(H-pad*1.6)*(v/max);var x=pad+i*bw+bw*0.18,y=H-pad-h,w=bw*0.64;",
      "ctx.fillStyle=g;ctx.beginPath();ctx.roundRect?ctx.roundRect(x,y,w,h,8):ctx.rect(x,y,w,h);ctx.fill();",
      "ctx.fillStyle=light?'#0f172a':'#e6edf7';ctx.font='600 12px system-ui';ctx.textAlign='center';",
      "ctx.fillText(String(v),x+w/2,y-7);ctx.fillStyle=light?'#5b6b88':'#8fa0bd';ctx.font='12px system-ui';",
      "ctx.fillText('#'+(i+1),x+w/2,H-pad+20);ctx.textAlign='left';});}",
      "document.getElementById('draw').addEventListener('click',draw);",
      "data.addEventListener('input',draw);document.addEventListener('themechange',draw);draw();"
    ].join("\n");
    return shell({ title: "Bar chart", sub: "type numbers, get a deterministic chart", body: body, js: js, theme: opts.theme });
  }

  /* ---------------------------------------------------------- dashboard -- */
  function dashboard(desc, opts) {
    var body = [
      '<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:12px">',
      '<div class="stat"><span>requests</span><b id="s1">1,284</b></div>',
      '<div class="stat"><span>success</span><b id="s2">99.2%</b></div>',
      '<div class="stat"><span>p50 latency</span><b id="s3">3.1 ms</b></div>',
      '<div class="stat"><span>commands</span><b id="s4">2,700+</b></div>',
      '</div>',
      '<div class="card" style="margin-bottom:12px">',
      '<div class="row" style="justify-content:space-between;margin-bottom:8px">',
      '<b>traffic · last 24h</b><span class="pill">deterministic sample</span></div>',
      '<svg id="spark" viewBox="0 0 640 180" preserveAspectRatio="none" style="width:100%;height:170px">',
      '<defs><linearGradient id="fill" x1="0" x2="0" y1="0" y2="1">',
      '<stop offset="0" stop-color="#22d3ee" stop-opacity=".35"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/>',
      '</linearGradient></defs><path id="area" fill="url(#fill)"></path><path id="line" fill="none" stroke="#22d3ee" stroke-width="2.5"></path>',
      '</svg></div>',
      '<div class="card"><b>recent routed calls</b>',
      '<table style="width:100%;border-collapse:collapse;margin-top:8px;font-size:13px">',
      '<thead><tr class="muted small"><th align="left">query</th><th align="left">tool</th><th align="right">ms</th></tr></thead>',
      '<tbody><tr><td>multiply 67 and 420</td><td>math.binary</td><td align="right">0.2</td></tr>',
      '<tr><td>convert 5 km to miles</td><td>unit.convert</td><td align="right">0.3</td></tr>',
      '<tr><td>count the words</td><td>text.count</td><td align="right">0.1</td></tr>',
      '<tr><td>build a calculator app</td><td>build</td><td align="right">1.1</td></tr></tbody></table></div>'
    ].join("");
    var js = [
      "var vals=[6,9,7,12,10,14,18,16,21,19,24,22,28,25,30,27,33,31,36,34,40,37,44,41];",
      "var line=document.getElementById('line'),area=document.getElementById('area');",
      "var max=Math.max.apply(null,vals),W=640,H=180;",
      "var pts=vals.map(function(v,i){var x=i/(vals.length-1)*W;var y=H-12-(v/max)*(H-32);return [x,y];});",
      "line.setAttribute('d','M'+pts.map(function(p){return p[0].toFixed(1)+' '+p[1].toFixed(1)}).join(' L'));",
      "area.setAttribute('d','M0 '+H+' L'+pts.map(function(p){return p[0].toFixed(1)+' '+p[1].toFixed(1)}).join(' L')+' L'+W+' '+H+' Z');"
    ].join("\n");
    return shell({ title: "Metrics dashboard", sub: "a compact, self-contained operations view", body: body, js: js, theme: opts.theme });
  }

  /* ------------------------------------------------------------ landing -- */
  function landing(desc, opts) {
    var about = desc || "a tiny, honest tool that does one thing well";
    var body = [
      '<section class="card" style="padding:clamp(20px,5vw,44px);margin-bottom:14px;background:',
      'radial-gradient(700px 320px at 10% 0%,rgba(34,211,238,.18),transparent 65%),linear-gradient(180deg,var(--panel),var(--panel2))">',
      '<span class="badge">' + esc(about.slice(0, 46)) + '</span>',
      '<h1 style="font-size:clamp(28px,6vw,50px);max-width:16ch;margin:12px 0 10px">Built for focus, not for feeds.</h1>',
      '<p class="sub" style="max-width:52ch;font-size:15px">' + esc(about) + '. No account, no tracking, no network — just a page that loads and works.</p>',
      '<div class="row" style="margin-top:18px"><button class="btn" id="cta" type="button">Get started</button>',
      '<a class="btn ghost" href="#features" style="text-decoration:none">See features</a></div>',
      '<div id="ctaMsg" class="muted small" style="margin-top:10px;min-height:18px"></div>',
      '</section>',
      '<section id="features" class="grid" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));margin-bottom:14px">',
      feature("Instant", "Every interaction is local. Nothing waits on a round trip."),
      feature("Deterministic", "The same input always gives the same result — by construction."),
      feature("Portable", "One HTML file. Save it, mail it, host it anywhere."),
      '</section>',
      '<section class="card" style="text-align:center">',
      '<h2 style="margin:0 0 6px;font-size:20px">Ready when you are</h2>',
      '<p class="muted small" style="margin:0 0 14px">no sign-up, no cookie banner, no dark patterns.</p>',
      '<button class="btn" id="cta2" type="button">Start now</button></section>'
    ].join("");
    var js = [
      "function go(){var m=document.getElementById('ctaMsg');m.textContent='you are already here — this page is the product. ✓';}",
      "document.getElementById('cta').addEventListener('click',go);",
      "document.getElementById('cta2').addEventListener('click',go);"
    ].join("\n");
    return shell({ title: "Landing page", sub: "a clean single-page site, ready to edit", body: body, js: js, theme: opts.theme });
  }

  function feature(h, p) {
    return '<div class="card"><b style="color:var(--accent)">' + esc(h) + '</b><p class="muted small" style="margin:6px 0 0">' + esc(p) + '</p></div>';
  }

  /* ----------------------------------------------------------- markdown -- */
  function markdown(desc, opts) {
    var body = [
      '<div class="card">',
      '<div class="row" style="justify-content:space-between;margin-bottom:10px">',
      '<span class="pill">markdown · live preview</span>',
      '<button class="btn ghost" id="sample" type="button" style="padding:6px 11px;font-size:12px">load sample</button></div>',
      '<div class="md" style="display:grid;grid-template-columns:1fr 1fr;gap:10px">',
      '<textarea id="src" rows="16" style="font-family:ui-monospace,monospace;font-size:13px;resize:vertical"></textarea>',
      '<div id="prev" style="border:1px solid var(--border);border-radius:10px;padding:12px;overflow:auto;max-height:420px;background:var(--panel2)"></div>',
      '</div>',
      '<p class="muted small" style="margin:10px 2px 0">tiny renderer: headings, bold, italic, code, lists, quotes, links.</p>',
      '</div>'
    ].join("");
    var css = ".md h1,.md h2,.md h3{margin:.2em 0 .35em;line-height:1.2}.md h1{font-size:1.5em}.md h2{font-size:1.25em}" +
      ".md p{margin:.45em 0}.md ul{margin:.4em 0;padding-left:1.2em}.md blockquote{margin:.5em 0;padding:.35em .8em;" +
      "border-left:3px solid var(--accent);background:rgba(34,211,238,.07);border-radius:0 8px 8px 0}" +
      ".md code{background:rgba(148,163,184,.18);padding:1px 5px;border-radius:5px;font-size:.92em}" +
      ".md a{color:var(--accent)}.md hr{border:0;border-top:1px solid var(--border);margin:1em 0}" +
      "@media(max-width:640px){.md{grid-template-columns:1fr!important}}";
    var js = [
      "var SAMPLE='# Notes\\n\\nA **small** page with *markdown* and `inline code`.\\n\\n## Why\\n\\n- no network\\n- no build step\\n- no surprises\\n\\n> same input, same page.\\n\\n[learn more](https://example.com)\\n';",
      "var src=document.getElementById('src'),prev=document.getElementById('prev');",
      "function inline(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')",
      ".replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g,'<a href=\"$2\" rel=\"noreferrer noopener\">$1</a>')",
      ".replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\\*\\*([^*]+)\\*\\*/g,'<strong>$1</strong>')",
      ".replace(/\\*([^*]+)\\*/g,'<em>$1</em>');}",
      "function render(){var lines=src.value.split('\\n'),out=[],inList=false;",
      "function closeList(){if(inList){out.push('</ul>');inList=false;}}",
      "lines.forEach(function(raw){var l=raw.trim();",
      "if(!l){closeList();return;}",
      "if(/^### /.test(l)){closeList();out.push('<h3>'+inline(l.slice(4))+'</h3>');}",
      "else if(/^## /.test(l)){closeList();out.push('<h2>'+inline(l.slice(3))+'</h2>');}",
      "else if(/^# /.test(l)){closeList();out.push('<h1>'+inline(l.slice(2))+'</h1>');}",
      "else if(/^> /.test(l)){closeList();out.push('<blockquote>'+inline(l.slice(2))+'</blockquote>');}",
      "else if(/^- /.test(l)){if(!inList){out.push('<ul>');inList=true;}out.push('<li>'+inline(l.slice(2))+'</li>');}",
      "else if(/^---+$/.test(l)){closeList();out.push('<hr>');}",
      "else{closeList();out.push('<p>'+inline(l)+'</p>');}});closeList();",
      "prev.innerHTML=out.join('');}",
      "document.getElementById('sample').addEventListener('click',function(){src.value=SAMPLE;render();});",
      "src.addEventListener('input',render);",
      "try{src.value=localStorage.getItem('toolrx.md')||SAMPLE}catch(e){src.value=SAMPLE}",
      "src.addEventListener('input',function(){try{localStorage.setItem('toolrx.md',src.value)}catch(e){}});render();"
    ].join("\n");
    return shell({ title: "Markdown editor", sub: "type on the left, read on the right", body: body, css: css, js: js, theme: opts.theme });
  }

  /* ------------------------------------------------------------ expenses -- */
  function expenses(desc, opts) {
    var body = [
      '<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">',
      '<div class="card">',
      '<form id="add" class="grid" style="gap:8px">',
      '<input id="what" placeholder="what did you buy?" autocomplete="off">',
      '<div class="row"><input id="amt" type="number" step="0.01" min="0" placeholder="amount" class="grow">',
      '<select id="cat" style="width:130px"><option>food</option><option>transport</option><option>home</option>',
      '<option>fun</option><option>other</option></select></div>',
      '<button class="btn" type="submit">Add expense</button></form>',
      '<div id="total" style="margin-top:14px;font-size:30px;font-weight:700;letter-spacing:-.02em">$0.00</div>',
      '<div class="muted small">total spent</div>',
      '<div id="bars" style="margin-top:12px;display:flex;flex-direction:column;gap:7px"></div>',
      '</div>',
      '<div class="card"><div class="row" style="justify-content:space-between"><b>recent</b>',
      '<button class="btn ghost" id="clear" type="button" style="padding:5px 10px;font-size:12px">clear all</button></div>',
      '<ul id="list" style="list-style:none;margin:10px 0 0;padding:0;display:flex;flex-direction:column;gap:7px"></ul>',
      '<p id="empty" class="muted small" style="margin:12px 2px 0">no expenses yet.</p></div>',
      '</div>'
    ].join("");
    var js = [
      "var KEY='toolrx.expenses.v1',items=[];",
      "try{items=JSON.parse(localStorage.getItem(KEY)||'[]')}catch(e){items=[]}",
      "if(!Array.isArray(items))items=[];",
      "function save(){try{localStorage.setItem(KEY,JSON.stringify(items))}catch(e){}}",
      "function money(n){return '$'+n.toFixed(2);}",
      "function draw(){var total=items.reduce(function(a,b){return a+b.amt},0),by={};",
      "items.forEach(function(x){by[x.cat]=(by[x.cat]||0)+x.amt;});",
      "document.getElementById('total').textContent=money(total);",
      "var bars=document.getElementById('bars');bars.innerHTML='';",
      "Object.keys(by).sort(function(a,b){return by[b]-by[a]}).forEach(function(k){",
      "var p=total?by[k]/total*100:0,row=document.createElement('div');",
      "row.innerHTML='<div class=\"row small\" style=\"justify-content:space-between\"><span>'+k+'</span><span>'+money(by[k])+'</span></div>'+",
      "'<div style=\"height:6px;background:var(--panel2);border-radius:4px;overflow:hidden\"><div style=\"width:'+p.toFixed(1)+'%;height:100%;background:linear-gradient(90deg,var(--accent),var(--accent2))\"></div></div>';",
      "bars.appendChild(row);});",
      "var list=document.getElementById('list');list.innerHTML='';",
      "items.slice().reverse().forEach(function(x,i){var li=document.createElement('li');",
      "li.style.cssText='display:flex;justify-content:space-between;gap:8px;padding:8px 10px;border:1px solid var(--border);border-radius:9px;background:var(--panel2)';",
      "li.innerHTML='<span style=\"min-width:0;word-break:break-word\">'+x.what+' <span class=\"muted small\">· '+x.cat+'</span></span><b>'+money(x.amt)+'</b>';",
      "list.appendChild(li);});",
      "document.getElementById('empty').style.display=items.length?'none':'block';}",
      "document.getElementById('add').addEventListener('submit',function(e){e.preventDefault();",
      "var what=document.getElementById('what').value.trim(),amt=parseFloat(document.getElementById('amt').value);",
      "if(!what||!isFinite(amt)||amt<=0)return;items.push({what:what,amt:amt,cat:document.getElementById('cat').value});",
      "document.getElementById('what').value='';document.getElementById('amt').value='';save();draw();});",
      "document.getElementById('clear').addEventListener('click',function(){items=[];save();draw();});",
      "draw();"
    ].join("\n");
    return shell({ title: "Expense tracker", sub: "log spending · see the total and the split", body: body, js: js, theme: opts.theme });
  }

  /* -------------------------------------------------------------- clock -- */
  function clock(desc, opts) {
    var body = [
      '<div class="card" style="text-align:center;padding:clamp(24px,7vw,56px)">',
      '<div id="time" style="font-size:clamp(44px,13vw,88px);font-weight:700;letter-spacing:-.05em;font-variant-numeric:tabular-nums;line-height:1">--:--:--</div>',
      '<div id="date" class="muted" style="margin-top:8px;font-size:16px">—</div>',
      '<div class="row" style="justify-content:center;margin-top:18px">',
      '<span class="pill" id="tz">local time</span>',
      '<button class="btn ghost" id="fmt" type="button" style="padding:6px 11px;font-size:12px">24-hour</button></div>',
      '<p class="muted small" style="margin:16px 0 0">the clock reads this device\'s local timezone.</p>',
      '</div>'
    ].join("");
    var js = [
      "var h24=true;var t=document.getElementById('time'),d=document.getElementById('date');",
      "function tick(){var n=new Date();var h=n.getHours(),m=n.getMinutes(),s=n.getSeconds();",
      "var ap=h>=12?'PM':'AM';var hh=h24?h:(h%12||12);",
      "t.textContent=('0'+hh).slice(-2)+':'+('0'+m).slice(-2)+':'+('0'+s).slice(-2)+(h24?'':' '+ap);",
      "d.textContent=n.toLocaleDateString(undefined,{weekday:'long',year:'numeric',month:'long',day:'numeric'});}",
      "document.getElementById('fmt').addEventListener('click',function(){h24=!h24;this.textContent=h24?'24-hour':'12-hour';tick();});",
      "tick();setInterval(tick,1000);"
    ].join("\n");
    return shell({ title: "Clock", sub: "local time, large and legible", body: body, js: js, theme: opts.theme });
  }

  /* --------------------------------------------------------------- game -- */
  function game(desc, opts) {
    var body = [
      '<div class="card" style="max-width:520px;margin:0 auto;text-align:center">',
      '<p class="sub" style="margin:0 0 14px">I picked a whole number from 1 to 100. Guess it in as few tries as you can.</p>',
      '<div id="hint" style="font-size:clamp(22px,5vw,30px);font-weight:700;min-height:42px">make a guess</div>',
      '<form id="guess" class="row" style="justify-content:center;margin:12px 0">',
      '<input id="n" type="number" min="1" max="100" class="grow" placeholder="1–100" style="max-width:150px;text-align:center;font-size:20px;font-weight:600">',
      '<button class="btn" type="submit">Guess</button></form>',
      '<div class="row small muted" style="justify-content:center;gap:14px">',
      '<span>tries <b id="tries" style="color:var(--text)">0</b></span>',
      '<span>best <b id="best" style="color:var(--text)">—</b></span>',
      '<button class="btn ghost" id="new" type="button" style="padding:4px 9px;font-size:11.5px">new game</button></div>',
      '<p id="msg" class="muted small" style="min-height:18px;margin:12px 0 0"></p>',
      '</div>'
    ].join("");
    var js = [
      "var secret=42,tries=0,best=null,done=false;",
      "var hint=document.getElementById('hint'),msg=document.getElementById('msg'),n=document.getElementById('n');",
      "function reset(seed){var h=2166136261;for(var i=0;i<seed.length;i++){h^=seed.charCodeAt(i);h=Math.imul(h,16777619);}",
      "secret=(Math.abs(h)%100)+1;tries=0;done=false;hint.textContent='make a guess';msg.textContent='';",
      "document.getElementById('tries').textContent='0';n.value='';n.focus();}",
      "document.getElementById('guess').addEventListener('submit',function(e){e.preventDefault();",
      "if(done)return;var v=parseInt(n.value,10);if(!isFinite(v)||v<1||v>100){msg.textContent='enter a number from 1 to 100.';return;}",
      "tries++;document.getElementById('tries').textContent=tries;n.value='';n.focus();",
      "if(v===secret){done=true;hint.textContent='correct — '+secret;msg.textContent='solved in '+tries+' '+(tries===1?'try':'tries')+'.';",
      "if(best===null||tries<best){best=tries;document.getElementById('best').textContent=best;}}",
      "else if(v<secret){hint.textContent='too low';}else{hint.textContent='too high';}});",
      "document.getElementById('new').addEventListener('click',function(){reset('game'+Date.now())});",
      "reset('toolrx-game');"
    ].join("\n");
    return shell({ title: "Number guessing game", sub: "1–100 · deterministic secret, human guesses", body: body, js: js, theme: opts.theme });
  }

  /* ---------------------------------------------------------- playground -- */
  function playground(desc, opts) {
    var task = desc || "a small deterministic text tool";
    var body = [
      '<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">',
      '<div class="card"><b>input</b>',
      '<textarea id="in" rows="8" placeholder="type or paste text…" style="margin-top:8px;font-family:ui-monospace,monospace;font-size:13px"></textarea>',
      '<div class="row" style="margin-top:10px"><button class="btn" id="run" type="button">Run</button>',
      '<button class="btn ghost" id="clear" type="button">Clear</button></div>',
      '<p class="muted small" style="margin:10px 0 0">' + esc(task) + '</p></div>',
      '<div class="card"><b>output</b>',
      '<pre id="out" style="margin:8px 0 0;white-space:pre-wrap;word-break:break-word;background:var(--panel2);',
      'border:1px solid var(--border);border-radius:10px;padding:12px;min-height:210px;font:12.5px/1.6 ui-monospace,monospace">(nothing yet)</pre>',
      '<div class="row small muted" style="justify-content:space-between;margin-top:8px">',
      '<span id="stats">—</span><button class="btn ghost" id="copy" type="button" style="padding:5px 10px;font-size:12px">copy</button></div></div>',
      '</div>',
      '<div class="card" style="margin-top:12px"><b>pipeline</b>',
      '<div class="row" style="margin-top:8px">',
      '<label class="small muted row" style="gap:6px"><input type="checkbox" id="c1" checked style="width:16px;height:16px"> upper</label>',
      '<label class="small muted row" style="gap:6px"><input type="checkbox" id="c2" style="width:16px;height:16px"> reverse</label>',
      '<label class="small muted row" style="gap:6px"><input type="checkbox" id="c3" style="width:16px;height:16px"> slug</label>',
      '<label class="small muted row" style="gap:6px"><input type="checkbox" id="c4" style="width:16px;height:16px"> word count</label>',
      '</div></div>'
    ].join("");
    var js = [
      "var input=document.getElementById('in'),out=document.getElementById('out'),stats=document.getElementById('stats');",
      "function run(){var t=input.value;if(document.getElementById('c1').checked)t=t.toUpperCase();",
      "if(document.getElementById('c2').checked)t=Array.from(t).reverse().join('');",
      "if(document.getElementById('c3').checked)t=t.toLowerCase().trim().replace(/[^\\w\\s-]/g,'').replace(/[\\s_]+/g,'-').replace(/-+/g,'-');",
      "if(document.getElementById('c4').checked){var w=(t.match(/[A-Za-z0-9']+/g)||[]).length;t=t+'\\n\\n[words: '+w+']';}",
      "out.textContent=t||'(empty)';stats.textContent=input.value.length+' chars in · '+t.length+' chars out';}",
      "document.getElementById('run').addEventListener('click',run);",
      "document.getElementById('clear').addEventListener('click',function(){input.value='';out.textContent='(nothing yet)';stats.textContent='—';});",
      "document.getElementById('copy').addEventListener('click',function(){var s=document.createElement('textarea');s.value=out.textContent;",
      "document.body.appendChild(s);s.select();try{document.execCommand('copy')}catch(e){}s.remove();});",
      "input.addEventListener('input',run);run();"
    ].join("\n");
    return shell({ title: "Program playground", sub: task, body: body, js: js, theme: opts.theme });
  }

  /* ------------------------------------------------------------- welcome -- */
  function welcome(desc, opts) {
    var body = [
      '<div class="card" style="margin-bottom:12px">',
      '<b>the preview pane is live.</b>',
      '<p class="muted small" style="margin:6px 0 0">Ask for something to build and it appears here as a real, self-contained page. ',
      'Everything is generated in this tab — no model, no API, no network.</p>',
      '<div class="row" style="margin-top:12px">',
      '<span class="pill">build a calculator app</span>',
      '<span class="pill">build a todo list</span>',
      '<span class="pill">build a stopwatch</span>',
      '<span class="pill">build a unit converter</span>',
      '</div></div>',
      '<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(210px,1fr))">',
      feature("Multi-step", "read notes.txt then count the words then base64 encode it"),
      feature("Deterministic", "same prompt → same plan → same page, every time"),
      feature("Private", "the workspace and preview never leave the browser"),
      '</div>',
      '<div class="card" style="margin-top:12px">',
      '<b>try a chain</b>',
      '<p class="muted small" style="margin:6px 0 0;font-family:ui-monospace,monospace">',
      'convert 5 km to miles then square the result</p></div>'
    ].join("");
    return shell({ title: "Preview ready", sub: "the in-browser build surface", body: body, theme: opts.theme });
  }

  /* ------------------------------------------------------------- routing -- */
  var CANON = [
    [/calc/i, "calculator"],
    [/todo|task/i, "todo"],
    [/pomodoro/i, "pomodoro"],
    [/timer|countdown/i, "timer"],
    [/stopwatch/i, "stopwatch"],
    [/note|notepad/i, "notes"],
    [/tic[\s-]*tac|noughts/i, "tictactoe"],
    [/memory/i, "memory"],
    [/convert|unit/i, "converter"],
    [/chart|graph|plot/i, "chart"],
    [/dashboard|metrics|admin/i, "dashboard"],
    [/markdown/i, "markdown"],
    [/expense|budget|spend/i, "expenses"],
    [/clock|time/i, "clock"],
    [/game|guess/i, "game"],
    [/landing|website|web page|site|page/i, "landing"],
    [/program|app|tool|playground/i, "playground"]
  ];

  function canonical(kind, desc) {
    var text = String(kind || "").toLowerCase().trim();
    if (text === "pomodoro") return "pomodoro";
    if (text === "tictactoe" || text === "tic tac toe") return "tictactoe";
    for (var i = 0; i < CANON.length; i++) {
      if (CANON[i][0].test(text)) return CANON[i][1];
    }
    if (desc) {
      for (var j = 0; j < CANON.length; j++) {
        if (CANON[j][0].test(desc)) return CANON[j][1];
      }
    }
    return "playground";
  }

  function pomodoro(desc, opts) {
    var html = timer(desc, opts);
    html = html.split("Countdown timer").join("Pomodoro");
    html = html.split("pick a length, press start, get a chime").join("25 minutes of focus, then a short break");
    html = html.split('value="5"').join('value="25"');
    html = html.split(">05:00<").join(">25:00<");
    html = html.split("total=300,left=300").join("total=1500,left=1500");
    return html;
  }

  var BUILDERS = {
    calculator: calculator,
    todo: todo,
    timer: timer,
    pomodoro: pomodoro,
    stopwatch: stopwatch,
    notes: notes,
    tictactoe: tictactoe,
    memory: memory,
    converter: converter,
    chart: chart,
    dashboard: dashboard,
    landing: landing,
    markdown: markdown,
    expenses: expenses,
    clock: clock,
    game: game,
    playground: playground,
    welcome: welcome
  };

  var TITLES = {
    calculator: "Calculator", todo: "Todo list", timer: "Countdown timer",
    pomodoro: "Pomodoro", stopwatch: "Stopwatch", notes: "Notes",
    tictactoe: "Tic tac toe", memory: "Memory game", converter: "Unit converter",
    chart: "Bar chart", dashboard: "Metrics dashboard", landing: "Landing page",
    markdown: "Markdown editor", expenses: "Expense tracker", clock: "Clock",
    game: "Number guessing game", playground: "Program playground", welcome: "Preview ready"
  };

  function build(kind, desc, opts) {
    opts = opts || {};
    var real = canonical(kind, desc);
    var fn = BUILDERS[real] || BUILDERS.playground;
    return fn(String(desc || ""), { theme: opts.theme === "light" ? "light" : "dark" });
  }

  function title(kind, desc) {
    var real = canonical(kind, desc);
    if (real === "playground" && desc) return String(desc).slice(0, 60);
    return TITLES[real] || "Built page";
  }

  root.toolrxTemplates = {
    build: build,
    title: title,
    canonical: canonical,
    kinds: Object.keys(BUILDERS)
  };
})(typeof self !== "undefined" ? self : this);

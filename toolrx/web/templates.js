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
      "<span id=\"stamp\">offline · self-contained</span></footer>\n" +
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
      "speed:{mps:1,kph:1/3.6,mph:.44704,knot:1852/3600,",
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

  /* ---------------------------------------------------------------- rpg -- */
  /* ------------------------------------------------------------ themes ---- */
  function rpgTheme(desc) {
    var t = String(desc || "").toLowerCase();
    if (/arthur|camelot|knight|excalibur|round table|merlin|avalon/.test(t)) {
      return {
        title: "Camelot RPG", sub: "a knight’s road through the mist",
        intro: "You wake at the edge of the Mistwood. Find the Black Knight before the fog closes.",
        hint: "find the Black Knight in the south-east.",
        enemy: "wandering knight", boss: "the Black Knight", elder: "Merlin", shrine: "the stone circle",
        win: "The Black Knight yields. You win — Camelot’s road is open.",
        chest: "Relic: +1 potion.",
        groundA: "#1b2a24", groundB: "#203328", wall: "#2f3a4d", wall2: "#232c3d", tree: "#2f5d43"
      };
    }
    if (/india|indian|bharat|sanskrit|vedic|mughal|rajasthan|delhi|himalaya|lotus/.test(t)) {
      return {
        title: "Bharata RPG", sub: "a journey across the lotus road",
        intro: "You wake at the edge of the Bharata plain. Find the Asura King before the monsoon breaks.",
        hint: "find the Asura King in the south-east.",
        enemy: "rakshasa", boss: "the Asura King", elder: "the rishi", shrine: "the stepwell",
        win: "The Asura King falls. You win — the lotus road is safe.",
        chest: "Copper bowl: +1 potion.",
        groundA: "#2a2118", groundB: "#31261b", wall: "#4a3826", wall2: "#3a2c1e", tree: "#3f6b4a"
      };
    }
    if (/space|sci-?fi|starship|derelict|orbit|station|alien/.test(t)) {
      return {
        title: "Derelict RPG", sub: "wake the ship, survive the dark",
        intro: "You wake in a cold corridor of the Derelict. Find the Warden Core before life support fails.",
        hint: "find the Warden Core in the south-east.",
        enemy: "husk drone", boss: "the Warden Core", elder: "the ship’s log", shrine: "the airlock",
        win: "The Warden Core goes dark. You win — the ship is yours.",
        chest: "Supply cache: +1 stim.",
        groundA: "#161b2b", groundB: "#1a2033", wall: "#2c3650", wall2: "#222a40", tree: "#2d4a5a"
      };
    }
    if (/cyber|cyberpunk|neon|hacker|dystopia|chrome|synth/.test(t)) {
      return {
        title: "Neon RPG", sub: "a run through the electric rain",
        intro: "You wake in a service tunnel under Neon. Find the Architect before the grid locks down.",
        hint: "find the Architect in the south-east.",
        enemy: "chrome drone", boss: "the Architect", elder: "the fixer", shrine: "the data well",
        win: "The Architect logs out. You win — the Neon grid is yours.",
        chest: "Data shard: +1 potion.",
        groundA: "#1a1426", groundB: "#20182f", wall: "#3a2450", wall2: "#2c1b3d", tree: "#4c2f6b"
      };
    }
    if (/noir|rain|detective|gumshoe|city/.test(t)) {
      return {
        title: "Rain City RPG", sub: "a case with too many doors",
        intro: "You wake in a doorway on Rain Street. Find the Fixer before the case goes cold.",
        hint: "find the Fixer in the south-east.",
        enemy: "mugger", boss: "the Fixer", elder: "the informant", shrine: "the all-night diner",
        win: "The Fixer folds. You win — the case is closed.",
        chest: "Envelope: +1 favour.",
        groundA: "#1a1d24", groundB: "#1f232c", wall: "#343b4a", wall2: "#272d39", tree: "#36424a"
      };
    }
    if (/greek|greece|olympus|olympian|myth|zeus|athena|hades|troy|trojan|labyrinth|minotaur/.test(t)) {
      return {
        title: "Olympus RPG", sub: "a hero’s climb toward the gods",
        intro: "You wake at the foot of Olympus. Find the Titan before the storm breaks.",
        hint: "find the Titan in the south-east.",
        enemy: "shade", boss: "the Titan", elder: "the oracle", shrine: "the temple",
        win: "The Titan falls. You win — the gods return to Olympus.",
        chest: "Ambrosia: +1 potion.",
        groundA: "#1f2233", groundB: "#262a3d", wall: "#3b3f57", wall2: "#2b2f43", tree: "#4f6b4a"
      };
    }
    if (/japan|japanese|samurai|shogun|sakura|edo|kyoto|ronin|ninja|bushido/.test(t)) {
      return {
        title: "Sakura RPG", sub: "a ronin’s road under falling petals",
        intro: "You wake beneath the cedars of the Sakura Road. Find the Shogun before the blossoms fall.",
        hint: "find the Shogun in the south-east.",
        enemy: "bandit", boss: "the Shogun", elder: "the shrine maiden", shrine: "the torii gate",
        win: "The Shogun kneels. You win — the Sakura Road is quiet again.",
        chest: "Lacquer box: +1 potion.",
        groundA: "#2b1f26", groundB: "#33242c", wall: "#4a3340", wall2: "#3a2934", tree: "#8a4f6b"
      };
    }
    if (/egypt|egyptian|nile|pharaoh|pyramid|sphinx|scarab|desert|sand/.test(t)) {
      return {
        title: "Nile RPG", sub: "a walk beside the reeds of the old river",
        intro: "You wake on the bank of the Nile. Find the Pharaoh before the sandstorm rises.",
        hint: "find the Pharaoh in the south-east.",
        enemy: "scarab swarm", boss: "the Pharaoh", elder: "the scribe", shrine: "the obelisk",
        win: "The Pharaoh rests. You win — the Nile keeps its secret.",
        chest: "Canopic jar: +1 potion.",
        groundA: "#2a2114", groundB: "#332818", wall: "#4f3b1e", wall2: "#3b2c17", tree: "#5f6b2f"
      };
    }
    if (/ocean|sea|underwater|abyss|atlantis|coral|reef|submarine|deep/.test(t)) {
      return {
        title: "Abyss RPG", sub: "a dive below the last light",
        intro: "You wake on the floor of the Abyss. Find the Leviathan before the air runs out.",
        hint: "find the Leviathan in the south-east.",
        enemy: "jelly", boss: "the Leviathan", elder: "the reef keeper", shrine: "the sunken gate",
        win: "The Leviathan sleeps. You win — the Abyss is calm again.",
        chest: "Pearl: +1 potion.",
        groundA: "#10222a", groundB: "#132a34", wall: "#1f4650", wall2: "#173640", tree: "#2a6b6b"
      };
    }
    if (/west|western|cowboy|frontier|outlaw|sheriff|saloon|rustler/.test(t)) {
      return {
        title: "Frontier RPG", sub: "a ride across the dry country",
        intro: "You wake at the edge of the Frontier. Find the Outlaw before the sun goes down.",
        hint: "find the Outlaw in the south-east.",
        enemy: "rustler", boss: "the Outlaw", elder: "the sheriff", shrine: "the water tower",
        win: "The Outlaw rides off. You win — the Frontier is quiet again.",
        chest: "Canteen: +1 potion.",
        groundA: "#2b1d13", groundB: "#332317", wall: "#4d3320", wall2: "#3b2718", tree: "#5e4a2a"
      };
    }
    return null;
  }

  function applyRpgTheme(html, desc) {
    var t = rpgTheme(desc);
    if (!t) return html;
    var bossCap = t.boss.charAt(0).toUpperCase() + t.boss.slice(1);
    var pairs = [
      ["Verdant Wood RPG", t.title],
      ["explore, fight, level up — a complete tiny RPG", t.sub],
      ["You wake at the edge of the Verdant Wood. Find the Warden to the south-east.", t.intro],
      ["find the Warden in the south-east.", t.hint],
      ["The Warden falls. You win — the Verdant Wood is safe.", t.win],
      ["Chest: +1 potion.", t.chest],
      ["the Warden", t.boss],
      ["The Warden", bossCap],
      ["Warden", t.boss.replace(/^the /, "")],
      ["slime", t.enemy],
      ["Elder", t.elder],
      ["the shrine", t.shrine],
      ["#12291f", t.groundA],
      ["#123024", t.groundB],
      ["#26364f", t.wall],
      ["#1b283d", t.wall2],
      ["#1f513a", t.tree]
    ];
    for (var i = 0; i < pairs.length; i++) {
      html = html.split(pairs[i][0]).join(pairs[i][1]);
    }
    return html;
  }

  function rpg(desc, opts) {
    var body = [
      '<div class="card" style="padding:12px">',
      '<div class="row" style="justify-content:space-between;gap:6px;font-size:12px;margin-bottom:8px">',
      '<span class="pill">HP <b id="hp" style="color:var(--text)">30/30</b></span>',
      '<span class="pill">LV <b id="lv" style="color:var(--text)">1</b></span>',
      '<span class="pill">XP <b id="xp" style="color:var(--text)">0</b></span>',
      '<span class="pill">potion <b id="pot" style="color:var(--text)">1</b></span>',
      '</div>',
      '<canvas id="cv" width="640" height="416" style="width:100%;height:auto;border-radius:12px;background:#0a1420;border:1px solid var(--border);image-rendering:pixelated"></canvas>',
      '<div class="row" style="justify-content:center;margin-top:10px;gap:8px">',
      '<button class="btn ghost" data-d="up" type="button">▲</button>',
      '<button class="btn ghost" data-d="left" type="button">◀</button>',
      '<button class="btn ghost" data-d="down" type="button">▼</button>',
      '<button class="btn ghost" data-d="right" type="button">▶</button>',
      '</div>',
      '<div class="row" style="justify-content:center;margin-top:8px;gap:8px">',
      '<button class="btn ghost" id="save" type="button" style="padding:6px 11px;font-size:12px">save</button>',
      '<button class="btn ghost" id="load" type="button" style="padding:6px 11px;font-size:12px">load</button>',
      '<button class="btn ghost" id="fresh" type="button" style="padding:6px 11px;font-size:12px">new game</button>',
      '</div>',
      '<div id="log" class="muted small" style="min-height:38px;margin-top:10px;line-height:1.5">find the Warden in the south-east.</div>',
      '</div>',
      '<div id="battle" hidden style="position:fixed;inset:0;z-index:20;background:rgba(3,6,12,.82);display:grid;place-items:center;padding:16px">',
      '<div class="card" style="max-width:420px;width:100%;text-align:center">',
      '<div class="badge" style="margin:0 auto">battle</div>',
      '<h2 id="foe" style="margin:8px 0 2px;font-size:22px">slime</h2>',
      '<div class="muted small" id="foehp">10 / 10 HP</div>',
      '<div id="bl" class="muted small" style="min-height:44px;margin:12px 0;line-height:1.5"></div>',
      '<div class="row" style="justify-content:center">',
      '<button class="btn" data-b="attack" type="button">Attack</button>',
      '<button class="btn ghost" data-b="defend" type="button">Defend</button>',
      '<button class="btn ghost" data-b="heal" type="button">Potion</button>',
      '<button class="btn ghost" data-b="flee" type="button">Flee</button>',
      '</div></div></div>'
    ].join("");
    var css = '#battle[hidden]{display:none!important}' +
      '@media(max-width:560px){[data-d]{padding:12px 16px!important;font-size:16px!important}}';
    var js = [
      "var MAP=[",
      "'####################',",
      "'#..................#',",
      "'#..T....E..........#',",
      "'#......###.........#',",
      "'#..P...E.....C.....#',",
      "'#......###.........#',",
      "'#..........E.......#',",
      "'#....N.............#',",
      "'#..................#',",
      "'#.........E........#',",
      "'#..................#',",
      "'#...........B......#',",
      "'####################'];",
      "var T=32,W=20,H=13,KIND={E:{name:'slime',hp:10,atk:3,xp:8},B:{name:'the Warden',hp:44,atk:7,xp:40,boss:true}};",
      "var cv=document.getElementById('cv'),cx=cv.getContext('2d');",
      "var S,B=null,rand=(function(seed){var h=2166136261;for(var i=0;i<seed.length;i++){h^=seed.charCodeAt(i);h=Math.imul(h,16777619);}",
      "return function(){h+=0x6D2B79F5;var t=h;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;};})('verdant');",
      "function hit(lo,hi){return lo+Math.floor(rand()*(hi-lo+1));}",
      "function el(id){return document.getElementById(id);}",
      "function say(t){S.log.push(t);if(S.log.length>4)S.log.shift();el('log').textContent=S.log.join('  ·  ');}",
      "function paint(){el('hp').textContent=S.hp+'/'+S.max;el('lv').textContent=S.lv;el('xp').textContent=S.xp;el('pot').textContent=S.pot;}",
      "function fresh(){S={x:2,y:4,hp:30,max:30,lv:1,xp:0,pot:1,cleared:{},log:[],won:false};B=null;el('battle').hidden=true;say('You wake at the edge of the Verdant Wood. Find the Warden to the south-east.');draw();paint();}",
      "function draw(){var g=cx.createLinearGradient(0,0,0,cv.height);g.addColorStop(0,'#0d1b2e');g.addColorStop(1,'#0a1420');cx.fillStyle=g;cx.fillRect(0,0,cv.width,cv.height);",
      "for(var y=0;y<H;y++){for(var x=0;x<W;x++){var ch=MAP[y][x],px=x*T,py=y*T;",
      "if(ch==='#'){cx.fillStyle='#26364f';cx.fillRect(px,py,T,T);cx.fillStyle='#1b283d';cx.fillRect(px+2,py+2,T-4,T-4);}",
      "else{cx.fillStyle=(x+y)%2?'#12291f':'#123024';cx.fillRect(px,py,T,T);}",
      "if(ch==='T'){cx.fillStyle='#1f513a';cx.beginPath();cx.arc(px+16,py+16,10,0,7);cx.fill();}",
      "if(ch==='C'&&!S.cleared[x+','+y]){cx.fillStyle='#fbbf24';cx.font='20px serif';cx.textAlign='center';cx.fillText('▣',px+16,py+22);}",
      "if(ch==='N'){cx.fillStyle='#93c5fd';cx.font='20px serif';cx.textAlign='center';cx.fillText('☺',px+16,py+22);}",
      "if(ch==='E'&&!S.cleared[x+','+y]){cx.fillStyle='#fb7185';cx.font='20px serif';cx.textAlign='center';cx.fillText('◆',px+16,py+22);}",
      "if(ch==='B'&&!S.cleared[x+','+y]){cx.fillStyle='#a78bfa';cx.font='22px serif';cx.textAlign='center';cx.fillText('☠',px+16,py+23);}}}",
      "cx.fillStyle='#fffdf7';cx.beginPath();cx.arc(S.x*T+16,S.y*T+16,11,0,7);cx.fill();",
      "cx.fillStyle='#0f172a';cx.beginPath();cx.arc(S.x*T+13,S.y*T+13,2,0,7);cx.arc(S.x*T+19,S.y*T+13,2,0,7);cx.fill();}",
      "function move(dx,dy){if(B||S.won)return;var nx=S.x+dx,ny=S.y+dy,ch=MAP[ny][nx];",
      "if(ch==='#'||ch==='T')return;var key=nx+','+ny;",
      "if((ch==='E'||ch==='B')&&!S.cleared[key]){start(ch,nx,ny);return;}",
      "S.x=nx;S.y=ny;if(ch==='C'&&!S.cleared[key]){S.cleared[key]=1;S.pot++;say('Chest: +1 potion.');}",
      "if(ch==='N')say('Elder: the Warden fears a steady hand. Strike, then guard.');",
      "draw();paint();}",
      "function start(ch,x,y){var d=KIND[ch];B={ch:ch,x:x,y:y,name:d.name,hp:d.hp,max:d.hp,atk:d.atk,xp:d.xp,boss:!!d.boss,guard:false};",
      "el('battle').hidden=false;el('foe').textContent=d.name;el('bl').textContent='A '+d.name+' blocks the path.';battle();}",
      "function battle(){el('foehp').textContent=B.hp+' / '+B.max+' HP';}",
      "function endBattle(msg){el('battle').hidden=true;say(msg);B=null;draw();paint();}",
      "function win(){S.cleared[B.x+','+B.y]=1;S.xp+=B.xp;var up=false;while(S.xp>=S.lv*20){S.xp-=S.lv*20;S.lv++;S.max+=5;S.hp=S.max;up=true;}",
      "if(B.boss){S.won=true;endBattle('The Warden falls. You win — the Verdant Wood is safe. ('+(up?'level up! ':'')+')');}",
      "else endBattle((up?'Level up! ':'')+'Defeated '+B.name+'. +'+B.xp+' XP.');}",
      "function foeTurn(mult){if(!B)return;var dmg=hit(1,B.atk);if(B.guard){dmg=Math.max(1,Math.ceil(dmg/2));B.guard=false;}",
      "S.hp-=Math.round(dmg*(mult||1));if(S.hp<=0){S.hp=S.max;S.x=2;S.y=4;endBattle('You fall... and wake at the shrine. Nothing is lost but pride.');return;}",
      "battle();el('bl').textContent='The '+B.name+' hits for '+dmg+'.';paint();}",
      "function act(kind){if(!B)return;",
      "if(kind==='attack'){var d=hit(4,7)+S.lv*2;B.hp-=d;battle();el('bl').textContent='You strike for '+d+'.';",
      "if(B.hp<=0){win();return;}foeTurn(1);}",
      "else if(kind==='defend'){B.guard=true;el('bl').textContent='You raise your guard.';foeTurn(1);}",
      "else if(kind==='heal'){if(!S.pot){el('bl').textContent='No potions left.';return;}S.pot--;S.hp=Math.min(S.max,S.hp+12);paint();el('bl').textContent='You drink a potion (+12 HP).';foeTurn(1);}",
      "else if(kind==='flee'){if(B.boss){el('bl').textContent='The Warden blocks your escape.';foeTurn(1);}else endBattle('You slip away from the '+B.name+'.');}}",
      "document.querySelectorAll('[data-d]').forEach(function(b){b.addEventListener('click',function(){var d=b.dataset.d;move(d==='left'?-1:d==='right'?1:0,d==='up'?-1:d==='down'?1:0);});});",
      "document.querySelectorAll('[data-b]').forEach(function(b){b.addEventListener('click',function(){act(b.dataset.b);});});",
      "document.addEventListener('keydown',function(e){var k=e.key.toLowerCase();if(k==='arrowleft'||k==='a')move(-1,0);if(k==='arrowright'||k==='d')move(1,0);if(k==='arrowup'||k==='w')move(0,-1);if(k==='arrowdown'||k==='s')move(0,1);",
      "if(k==='1')act('attack');if(k==='2')act('defend');if(k==='3')act('heal');if(k==='4')act('flee');});",
      "el('fresh').addEventListener('click',fresh);",
      "el('save').addEventListener('click',function(){try{localStorage.setItem('toolrx.rpg.v1',JSON.stringify({S:S,x:S.x,y:S.y}));say('Game saved.');}catch(e){say('save unavailable');}});",
      "el('load').addEventListener('click',function(){try{var d=JSON.parse(localStorage.getItem('toolrx.rpg.v1'));if(d&&d.S){S=d.S;draw();paint();say('Game loaded.');}}catch(e){say('no save found');}});",
      "fresh();"
    ].join("\n");
    return applyRpgTheme(shell({ title: "Verdant Wood RPG", sub: "explore, fight, level up — a complete tiny RPG", body: body, css: css, js: js, theme: opts.theme }), desc);
  }

  /* --------------------------------------------------------- platformer -- */
  function platformer(desc, opts) {
    var body = [
      '<div class="card" style="padding:12px">',
      '<div class="row" style="justify-content:space-between;margin-bottom:8px"><span class="pill">coins <b id="score" style="color:var(--text)">0 / 8</b></span><span class="pill" id="msg">reach the flag →</span></div>',
      '<canvas id="cv" width="720" height="420" style="width:100%;height:auto;border-radius:12px;background:#0b1226;border:1px solid var(--border)"></canvas>',
      '<div class="row" style="justify-content:center;margin-top:10px;gap:10px">',
      '<button class="btn ghost" data-k="left" type="button">◀</button>',
      '<button class="btn ghost" data-k="jump" type="button">jump</button>',
      '<button class="btn ghost" data-k="right" type="button">▶</button>',
      '<button class="btn ghost" id="reset" type="button" style="padding:6px 11px;font-size:12px">reset</button>',
      '</div></div>'
    ].join("");
    var js = [
      "var cv=document.getElementById('cv'),cx=cv.getContext('2d'),msg=document.getElementById('msg'),scoreEl=document.getElementById('score');",
      "var W=720,H=420,keys={},P={x:40,y:300,w:26,h:32,vx:0,vy:0,on:false},coins=[],cam=0;",
      "var PLAT=[[0,388,720,32],[120,320,120,16],[300,270,130,16],[490,220,120,16],[620,320,100,16],[250,150,90,16],[40,210,90,16]];",
      "var GOAL={x:672,y:158,w:24,h:60};",
      "function reset(){P={x:40,y:300,w:26,h:32,vx:0,vy:0,on:false};coins=[[140,292],[160,292],[330,242],[350,242],[520,192],[540,192],[285,122],[660,292]].map(function(p){return {x:p[0],y:p[1],got:false};});msg.textContent='reach the flag →';scoreEl.textContent='0 / 8';}",
      "function loop(){var left=keys.left||keys.a,right=keys.right||keys.d;P.vx=(right?1:0)*3.4-(left?1:0)*3.4;P.vy+=0.5;if(P.vy>13)P.vy=13;",
      "P.x+=P.vx;P.y+=P.vy;P.on=false;",
      "PLAT.forEach(function(p){if(P.x+P.w>p[0]&&P.x<p[0]+p[2]&&P.y+P.h>p[1]&&P.y+P.h-P.vy<=p[1]+6&&P.vy>=0){P.y=p[1]-P.h;P.vy=0;P.on=true;}});",
      "if(P.x<0)P.x=0;if(P.x+P.w>W)P.x=W-P.w;if(P.y>H+80)reset();",
      "coins.forEach(function(c){if(!c.got&&Math.abs(P.x+P.w/2-c.x)<20&&Math.abs(P.y+P.h/2-c.y)<24){c.got=true;var n=coins.filter(function(z){return z.got}).length;scoreEl.textContent=n+' / 8';}});",
      "if(P.x+P.w>GOAL.x&&P.x<GOAL.x+GOAL.w&&P.y+P.h>GOAL.y&&P.y<GOAL.y+GOAL.h){var n=coins.filter(function(z){return z.got}).length;msg.textContent='flag reached · '+n+'/8 coins';}",
      "draw();requestAnimationFrame(loop);}",
      "function draw(){var g=cx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#0b1226');g.addColorStop(1,'#111c3a');cx.fillStyle=g;cx.fillRect(0,0,W,H);",
      "cx.fillStyle='rgba(167,139,250,.18)';for(var i=0;i<6;i++){cx.beginPath();cx.arc(80+i*120,70+(i%3)*18,26,0,7);cx.fill();}",
      "cx.fillStyle='#22d3ee';PLAT.forEach(function(p){cx.fillRect(p[0],p[1],p[2],p[3]);});",
      "cx.fillStyle='#fbbf24';coins.forEach(function(c){if(c.got)return;cx.beginPath();cx.arc(c.x,c.y,7,0,7);cx.fill();});",
      "cx.fillStyle='#34d399';cx.fillRect(GOAL.x,GOAL.y,GOAL.w,GOAL.h);cx.fillStyle='#04121a';cx.font='bold 16px system-ui';cx.fillText('GO',GOAL.x+1,GOAL.y+34);",
      "cx.fillStyle='#f8fafc';cx.fillRect(P.x,P.y,P.w,P.h);cx.fillStyle='#0f172a';cx.fillRect(P.x+5,P.y+7,6,6);cx.fillRect(P.x+16,P.y+7,6,6);}",
      "document.addEventListener('keydown',function(e){var k=e.key.toLowerCase();keys[k]=true;if(k===' '||k==='arrowup'||k==='w'){if(P.on){P.vy=-11;P.on=false;}e.preventDefault();}});",
      "document.addEventListener('keyup',function(e){keys[e.key.toLowerCase()]=false;});",
      "document.querySelectorAll('[data-k]').forEach(function(b){var k=b.dataset.k;",
      "var on=function(e){e.preventDefault();if(k==='jump'){if(P.on){P.vy=-11;P.on=false;}}else keys[k]=true;};",
      "var off=function(e){e.preventDefault();keys[k]=false;};",
      "b.addEventListener('touchstart',on,{passive:false});b.addEventListener('touchend',off,{passive:false});b.addEventListener('mousedown',on);b.addEventListener('mouseup',off);b.addEventListener('mouseleave',off);});",
      "document.getElementById('reset').addEventListener('click',reset);reset();loop();"
    ].join("\n");
    return shell({ title: "Platformer", sub: "run, jump, collect coins, reach the flag", body: body, js: js, theme: opts.theme });
  }

  /* -------------------------------------------------------------- snake -- */
  function snake(desc, opts) {
    var body = [
      '<div class="card" style="padding:12px;text-align:center">',
      '<div class="row" style="justify-content:space-between;margin-bottom:8px"><span class="pill">score <b id="score" style="color:var(--text)">0</b></span><span class="pill" id="msg">arrows / swipe</span></div>',
      '<canvas id="cv" width="480" height="360" style="width:100%;height:auto;border-radius:12px;background:#08101f;border:1px solid var(--border)"></canvas>',
      '<div class="row" style="justify-content:center;margin-top:10px"><button class="btn" id="go" type="button">Start</button><button class="btn ghost" id="reset" type="button">Reset</button></div>',
      '</div>'
    ].join("");
    var js = [
      "var cv=document.getElementById('cv'),cx=cv.getContext('2d'),G=24,C=20,scoreEl=document.getElementById('score'),msg=document.getElementById('msg');",
      "var snake,dir,next,food,score,dead,iv;",
      "function place(){var ok=false,f;while(!ok){f={x:Math.floor(Math.random()*G),y:Math.floor(Math.random()*G)};ok=!snake.some(function(s){return s.x===f.x&&s.y===f.y;});}return f;}",
      "function reset(){snake=[{x:8,y:10},{x:7,y:10},{x:6,y:10}];dir={x:1,y:0};next=dir;food=place();score=0;dead=false;scoreEl.textContent='0';msg.textContent='arrows / swipe';draw();}",
      "function step(){if(dead)return;dir=next;var h={x:snake[0].x+dir.x,y:snake[0].y+dir.y};",
      "if(h.x<0)h.x=G-1;if(h.x>=G)h.x=0;if(h.y<0)h.y=C-1;if(h.y>=C)h.y=0;",
      "if(snake.some(function(s){return s.x===h.x&&s.y===h.y;})){dead=true;msg.textContent='game over · press start';return;}",
      "snake.unshift(h);if(h.x===food.x&&h.y===food.y){score++;scoreEl.textContent=score;food=place();}else snake.pop();draw();}",
      "function draw(){cx.fillStyle='#08101f';cx.fillRect(0,0,cv.width,cv.height);var t=cv.width/G;",
      "cx.fillStyle='#fb7185';cx.beginPath();cx.arc(food.x*t+t/2,food.y*t+t/2,t*0.34,0,7);cx.fill();",
      "snake.forEach(function(s,i){cx.fillStyle=i? '#22d3ee':'#a78bfa';cx.fillRect(s.x*t+1,s.y*t+1,t-2,t-2);});}",
      "function start(){if(iv)clearInterval(iv);if(dead)reset();msg.textContent='running';iv=setInterval(step,130);}",
      "document.getElementById('go').addEventListener('click',start);document.getElementById('reset').addEventListener('click',function(){if(iv)clearInterval(iv);iv=null;reset();});",
      "document.addEventListener('keydown',function(e){var k=e.key;var d=next;if(k==='ArrowLeft'&&dir.x!==1)next={x:-1,y:0};if(k==='ArrowRight'&&dir.x!==-1)next={x:1,y:0};if(k==='ArrowUp'&&dir.y!==1)next={x:0,y:-1};if(k==='ArrowDown'&&dir.y!==-1)next={x:0,y:1};});",
      "var sx=0,sy=0;cv.addEventListener('touchstart',function(e){sx=e.touches[0].clientX;sy=e.touches[0].clientY;},{passive:true});",
      "cv.addEventListener('touchend',function(e){var dx=e.changedTouches[0].clientX-sx,dy=e.changedTouches[0].clientY-sy;",
      "if(Math.abs(dx)>Math.abs(dy)){if(dx>0&&dir.x!==-1)next={x:1,y:0};else if(dx<0&&dir.x!==1)next={x:-1,y:0};}else{if(dy>0&&dir.y!==-1)next={x:0,y:1};else if(dy<0&&dir.y!==1)next={x:0,y:-1};}},{passive:true});",
      "reset();"
    ].join("\n");
    return shell({ title: "Snake", sub: "eat, grow, don't bite yourself", body: body, js: js, theme: opts.theme });
  }

  /* ----------------------------------------------------------- breakout -- */
  function breakout(desc, opts) {
    var body = [
      '<div class="card" style="padding:12px">',
      '<div class="row" style="justify-content:space-between;margin-bottom:8px"><span class="pill">score <b id="score" style="color:var(--text)">0</b></span><span class="pill">lives <b id="lives" style="color:var(--text)">3</b></span></div>',
      '<canvas id="cv" width="720" height="460" style="width:100%;height:auto;border-radius:12px;background:#080d1a;border:1px solid var(--border)"></canvas>',
      '<p class="muted small" style="margin:8px 2px 0">move the mouse or use ← → · space to launch</p></div>'
    ].join("");
    var js = [
      "var cv=document.getElementById('cv'),cx=cv.getContext('2d'),W=720,H=460,scoreEl=document.getElementById('score'),livesEl=document.getElementById('lives');",
      "var pad={x:310,w:100,h:12},ball={x:360,y:400,r:7,vx:4.2,vy:-4.4},bricks=[],score=0,lives=3,run=false;",
      "function reset(){bricks=[];for(var r=0;r<5;r++){for(var c=0;c<9;c++)bricks.push({x:40+c*72,y:50+r*26,w:62,h:16,on:true,hp:r<2?2:1});}score=0;scoreEl.textContent='0';lives=3;livesEl.textContent='3';ball={x:360,y:400,r:7,vx:4.2,vy:-4.4};pad.x=310;run=false;}",
      "function launch(){if(run)return;run=true;ball.vx=4.2*(Math.random()<.5?-1:1);ball.vy=-4.6;}",
      "function loop(){if(run){ball.x+=ball.vx;ball.y+=ball.vy;",
      "if(ball.x<8){ball.x=8;ball.vx*=-1;}if(ball.x>W-8){ball.x=W-8;ball.vx*=-1;}if(ball.y<8){ball.y=8;ball.vy*=-1;}",
      "if(ball.y>H-8){lives--;livesEl.textContent=Math.max(0,lives);run=false;ball={x:360,y:400,r:7,vx:0,vy:0};if(lives<=0){scoreEl.textContent='game over · '+score;}}",
      "if(ball.y+ball.r>H-34&&ball.y<H-18&&ball.x>pad.x-6&&ball.x<pad.x+pad.w+6&&ball.vy>0){ball.vy=-Math.abs(ball.vy);ball.vx+=((ball.x-(pad.x+pad.w/2))/pad.w)*4;}",
      "bricks.forEach(function(b){if(!b.on)return;if(ball.x>b.x-ball.r&&ball.x<b.x+b.w+ball.r&&ball.y>b.y-ball.r&&ball.y<b.y+b.h+ball.r){b.hp--;if(b.hp<=0)b.on=false;ball.vy*=-1;score+=10;scoreEl.textContent=score;}});",
      "if(!bricks.some(function(b){return b.on;})){score+=100;scoreEl.textContent=score;reset();}}",
      "draw();requestAnimationFrame(loop);}",
      "function draw(){var g=cx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#0b1226');g.addColorStop(1,'#080d1a');cx.fillStyle=g;cx.fillRect(0,0,W,H);",
      "bricks.forEach(function(b){if(!b.on)return;cx.fillStyle=b.hp>1?'#a78bfa':'#22d3ee';cx.fillRect(b.x,b.y,b.w,b.h);});",
      "cx.fillStyle='#e2e8f0';cx.fillRect(pad.x,H-28,pad.w,12);cx.fillStyle='#fbbf24';cx.beginPath();cx.arc(ball.x,ball.y,ball.r,0,7);cx.fill();}",
      "document.addEventListener('mousemove',function(e){var r=cv.getBoundingClientRect();pad.x=Math.max(0,Math.min(W-pad.w,(e.clientX-r.left)*(W/r.width)-pad.w/2));});",
      "document.addEventListener('keydown',function(e){if(e.key==='ArrowLeft')pad.x=Math.max(0,pad.x-26);if(e.key==='ArrowRight')pad.x=Math.min(W-pad.w,pad.x+26);if(e.key===' '){e.preventDefault();launch();}});",
      "cv.addEventListener('touchmove',function(e){var r=cv.getBoundingClientRect();pad.x=Math.max(0,Math.min(W-pad.w,(e.touches[0].clientX-r.left)*(W/r.width)-pad.w/2));},{passive:true});",
      "cv.addEventListener('click',launch);reset();loop();"
    ].join("\n");
    return shell({ title: "Breakout", sub: "clear the bricks, keep the ball alive", body: body, js: js, theme: opts.theme });
  }

  /* --------------------------------------------------------------- pong -- */
  function pong(desc, opts) {
    var body = [
      '<div class="card" style="padding:12px">',
      '<div class="row" style="justify-content:center;gap:22px;margin-bottom:8px;font-size:20px;font-weight:700"><span id="you">0</span><span class="muted" style="font-size:13px">you · cpu</span><span id="cpu">0</span></div>',
      '<canvas id="cv" width="720" height="420" style="width:100%;height:auto;border-radius:12px;background:#080d1a;border:1px solid var(--border)"></canvas>',
      '<p class="muted small" style="margin:8px 2px 0">mouse or ↑ ↓ · first to 7</p></div>'
    ].join("");
    var js = [
      "var cv=document.getElementById('cv'),cx=cv.getContext('2d'),W=720,H=420;",
      "var you={y:160,h:80},cpu={y:160,h:80},ball={x:360,y:210,vx:5,vy:3},score=[0,0];",
      "function resetBall(dir){ball={x:360,y:210,vx:5*dir,vy:(Math.random()<.5?-1:1)*3.4};}",
      "function loop(){ball.x+=ball.vx;ball.y+=ball.vy;",
      "if(ball.y<8||ball.y>H-8)ball.vy*=-1;",
      "if(ball.x<18&&ball.y>you.y&&ball.y<you.y+you.h){ball.vx=Math.abs(ball.vx);ball.vy+=((ball.y-(you.y+40))/40)*2.2;}",
      "if(ball.x>W-18&&ball.y>cpu.y&&ball.y<cpu.y+cpu.h){ball.vx=-Math.abs(ball.vx);ball.vy+=((ball.y-(cpu.y+40))/40)*2.2;}",
      "if(ball.x<0){score[1]++;resetBall(1);}if(ball.x>W){score[0]++;resetBall(-1);}",
      "var target=ball.y-40;cpu.y+=(target-cpu.y)*0.075;cpu.y=Math.max(0,Math.min(H-80,cpu.y));",
      "if(score[0]>=7||score[1]>=7){document.getElementById('you').textContent=score[0]>=7?'win!':score[0];document.getElementById('cpu').textContent=score[1]>=7?'win!':score[1];}",
      "else{document.getElementById('you').textContent=score[0];document.getElementById('cpu').textContent=score[1];}",
      "draw();requestAnimationFrame(loop);}",
      "function draw(){cx.fillStyle='#080d1a';cx.fillRect(0,0,W,H);cx.strokeStyle='#1e293b';cx.setLineDash([7,9]);",
      "cx.beginPath();cx.moveTo(W/2,0);cx.lineTo(W/2,H);cx.stroke();cx.setLineDash([]);",
      "cx.fillStyle='#22d3ee';cx.fillRect(12,you.y,12,you.h);cx.fillStyle='#a78bfa';cx.fillRect(W-24,cpu.y,12,cpu.h);",
      "cx.fillStyle='#f8fafc';cx.beginPath();cx.arc(ball.x,ball.y,8,0,7);cx.fill();}",
      "document.addEventListener('mousemove',function(e){var r=cv.getBoundingClientRect();you.y=Math.max(0,Math.min(H-you.h,(e.clientY-r.top)*(H/r.height)-you.h/2));});",
      "document.addEventListener('keydown',function(e){if(e.key==='ArrowUp')you.y=Math.max(0,you.y-24);if(e.key==='ArrowDown')you.y=Math.min(H-you.h,you.y+24);});",
      "cv.addEventListener('touchmove',function(e){var r=cv.getBoundingClientRect();you.y=Math.max(0,Math.min(H-you.h,(e.touches[0].clientY-r.top)*(H/r.height)-you.h/2));},{passive:true});",
      "loop();"
    ].join("\n");
    return shell({ title: "Pong", sub: "you against a simple, beatable CPU", body: body, css: "", js: js, theme: opts.theme });
  }

  /* -------------------------------------------------------------- 2048 --- */
  function game2048(desc, opts) {
    var body = [
      '<div class="card" style="max-width:460px;margin:0 auto">',
      '<div class="row" style="justify-content:space-between;margin-bottom:10px"><span class="pill">score <b id="score" style="color:var(--text)">0</b></span><button class="btn ghost" id="new" type="button" style="padding:6px 11px;font-size:12px">new game</button></div>',
      '<div id="board" style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:8px"></div>',
      '<p id="msg" class="muted small" style="min-height:20px;margin:10px 2px 0">arrows or swipe to merge tiles · reach 2048</p></div>'
    ].join("");
    var css = "#board .t{aspect-ratio:1;display:grid;place-items:center;border-radius:8px;font-weight:800;font-size:clamp(18px,5vw,30px);background:#182238;color:#e2e8f0}" +
      "#board .t[data-v='2']{background:#1e3a5f}#board .t[data-v='4']{background:#155e75}" +
      "#board .t[data-v='8']{background:#0e7490}#board .t[data-v='16']{background:#0891b2}" +
      "#board .t[data-v='32']{background:#22d3ee;color:#04121a}#board .t[data-v='64']{background:#34d399;color:#04121a}" +
      "#board .t[data-v='128']{background:#a78bfa;color:#04121a}#board .t[data-v='256']{background:#8b5cf6;color:#fff}" +
      "#board .t[data-v='512']{background:#fbbf24;color:#04121a}#board .t[data-v='1024']{background:#fb7185;color:#04121a}" +
      "#board .t[data-v='2048']{background:#f8fafc;color:#04121a}#board .t[data-v='0']{background:#141c2e;color:transparent}";
    var js = [
      "var g,score=0,over=false,b=document.getElementById('board'),msg=document.getElementById('msg');",
      "function add(){var free=[];g.forEach(function(v,i){if(!v)free.push(i);});if(!free.length)return;g[free[Math.floor(Math.random()*free.length)]]=Math.random()<.9?2:4;}",
      "function reset(){g=Array(16).fill(0);score=0;over=false;add();add();msg.textContent='arrows or swipe to merge tiles · reach 2048';draw();}",
      "function draw(){b.innerHTML='';document.getElementById('score').textContent=score;g.forEach(function(v){var d=document.createElement('div');d.className='t';d.dataset.v=v;d.textContent=v||'';b.appendChild(d);});}",
      "function move(dx,dy){if(over)return;var before=g.join(','),m=[];for(var i=0;i<16;i++)m.push([]);",
      "for(var y=0;y<4;y++)for(var x=0;x<4;x++){var sx=x,sy=y;if(dx>0)sx=3-x;if(dy>0)sy=3-y;m[sy][sx]=g[y*4+x];}",
      "for(var y=0;y<4;y++){var line=m[y].filter(function(v){return v});var out=[];for(var i=0;i<line.length;i++){if(line[i]===line[i+1]){out.push(line[i]*2);score+=line[i]*2;i++;}else out.push(line[i]);}while(out.length<4)out.push(0);m[y]=out;}",
      "for(var y=0;y<4;y++)for(var x=0;x<4;x++){var tx=x,ty=y;if(dx>0)tx=3-x;if(dy>0)ty=3-y;g[ty*4+tx]=m[y][x];}",
      "if(g.join(',')!==before){add();draw();if(g.indexOf(2048)>=0){over=true;msg.textContent='2048 — you win! new game?';}else if(!canMove()){over=true;msg.textContent='no moves left · score '+score;}}}",
      "function canMove(){if(g.indexOf(0)>=0)return true;for(var y=0;y<4;y++)for(var x=0;x<4;x++){var v=g[y*4+x];if(x<3&&v===g[y*4+x+1])return true;if(y<3&&v===g[(y+1)*4+x])return true;}return false;}",
      "document.addEventListener('keydown',function(e){var k=e.key;if(k==='ArrowLeft'){move(-1,0);e.preventDefault();}if(k==='ArrowRight'){move(1,0);e.preventDefault();}if(k==='ArrowUp'){move(0,-1);e.preventDefault();}if(k==='ArrowDown'){move(0,1);e.preventDefault();}});",
      "var sx=0,sy=0;b.addEventListener('touchstart',function(e){sx=e.touches[0].clientX;sy=e.touches[0].clientY;},{passive:true});",
      "b.addEventListener('touchend',function(e){var dx=e.changedTouches[0].clientX-sx,dy=e.changedTouches[0].clientY-sy;if(Math.abs(dx)>Math.abs(dy))move(dx>0?1:-1,0);else move(0,dy>0?1:-1);},{passive:true});",
      "document.getElementById('new').addEventListener('click',reset);reset();"
    ].join("\n");
    return shell({ title: "2048", sub: "slide, merge, chase the 2048 tile", body: body, css: css, js: js, theme: opts.theme });
  }

  /* --------------------------------------------------------- minesweeper -- */
  function minesweeper(desc, opts) {
    var body = [
      '<div class="card" style="max-width:520px;margin:0 auto">',
      '<div class="row" style="justify-content:space-between;margin-bottom:10px"><span class="pill">mines <b id="left" style="color:var(--text)">15</b></span><span class="pill" id="msg">click to reveal · right-click to flag</span></div>',
      '<div id="board" style="display:grid;grid-template-columns:repeat(10,1fr);gap:3px;background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:5px"></div>',
      '<div class="row" style="justify-content:center;margin-top:10px"><button class="btn ghost" id="new" type="button" style="padding:6px 12px;font-size:12px">new board</button></div></div>'
    ].join("");
    var css = "#board button{aspect-ratio:1;border-radius:5px;border:1px solid var(--border);background:#1b2740;color:var(--text);font-weight:700;font-size:13px;cursor:pointer;padding:0}" +
      "#board button.open{background:#0f172a;cursor:default}" +
      "#board button.flag{background:#3f2d1a;color:#fbbf24}" +
      "#board button.boom{background:#7f1d1d}";
    var js = [
      "var N=10,M=15,cells=[],started=false,over=false,flags=0;",
      "function board(){return document.getElementById('board');}",
      "function reset(){cells=[];started=false;over=false;flags=0;document.getElementById('left').textContent=M;document.getElementById('msg').textContent='click to reveal · right-click to flag';",
      "var b=board();b.innerHTML='';for(var i=0;i<N*N;i++){cells.push({m:false,open:false,flag:false,n:0});var x=document.createElement('button');x.type='button';x.dataset.i=i;b.appendChild(x);}draw();}",
      "function plant(safe){var pool=[];for(var i=0;i<100;i++)if(i!==safe)pool.push(i);var h=2166136261;for(var k=0;k<8;k++){h^=k+7;h=Math.imul(h,16777619);}",
      "for(var m=0;m<M;m++){h+=0x6D2B79F5;var t=h;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);var r=((t^(t>>>14))>>>0)/4294967296;var idx=pool.splice(Math.floor(r*pool.length),1)[0];cells[idx].m=true;}",
      "cells.forEach(function(c,i){c.n=neighbors(i).filter(function(j){return cells[j].m}).length;});}",
      "function neighbors(i){var x=i%N,y=Math.floor(i/N),out=[];for(var dy=-1;dy<=1;dy++)for(var dx=-1;dx<=1;dx++){if(!dx&&!dy)continue;var nx=x+dx,ny=y+dy;if(nx>=0&&nx<N&&ny>=0&&ny<N)out.push(ny*N+nx);}return out;}",
      "function open(i){if(over)return;var c=cells[i];if(c.flag||c.open)return;if(!started){started=true;plant(i);}c.open=true;",
      "if(c.m){over=true;cells.forEach(function(z,j){if(z.m)z.open=true;});document.getElementById('msg').textContent='boom — new board?';draw();return;}",
      "if(!c.n)neighbors(i).forEach(function(j){if(!cells[j].open)open(j);});draw();check();}",
      "function check(){var safe=cells.filter(function(c){return !c.m;}),won=safe.every(function(c){return c.open;});if(won){over=true;document.getElementById('msg').textContent='swept — you win!';}}",
      "function draw(){var b=board();cells.forEach(function(c,i){var x=b.children[i];x.textContent=c.open?(c.m?'✹':(c.n||'')):(c.flag?'⚑':'');x.className=c.open?'open':(c.flag?'flag':'');if(c.open&&c.m)x.className+=' boom';});}",
      "board().addEventListener('click',function(e){var t=e.target;if(t.dataset.i!==undefined)open(+t.dataset.i);});",
      "board().addEventListener('contextmenu',function(e){e.preventDefault();var t=e.target;if(t.dataset.i===undefined||over)return;var c=cells[+t.dataset.i];if(c.open)return;c.flag=!c.flag;flags+=c.flag?1:-1;document.getElementById('left').textContent=Math.max(0,M-flags);draw();});",
      "document.getElementById('new').addEventListener('click',reset);reset();"
    ].join("\n");
    return shell({ title: "Minesweeper", sub: "10×10 · 15 mines · right-click to flag", body: body, css: css, js: js, theme: opts.theme });
  }

  /* ------------------------------------------------------------ tetris --- */
  function tetris(desc, opts) {
    var body = [
      '<div class="card" style="padding:12px">',
      '<div class="row" style="justify-content:space-between;margin-bottom:8px"><span class="pill">score <b id="score" style="color:var(--text)">0</b></span><span class="pill">lines <b id="lines" style="color:var(--text)">0</b></span><span class="pill" id="msg">← → ↓ · ↑ rotate · space drop</span></div>',
      '<canvas id="cv" width="420" height="520" style="width:100%;max-width:420px;display:block;margin:0 auto;border-radius:12px;background:#080d1a;border:1px solid var(--border)"></canvas>',
      '<div class="row" style="justify-content:center;margin-top:10px"><button class="btn" id="go" type="button">Start</button><button class="btn ghost" id="reset" type="button">Reset</button></div></div>'
    ].join("");
    var js = [
      "var cv=document.getElementById('cv'),cx=cv.getContext('2d'),COLS=10,ROWS=20,S=26,D3=" + (opts.d3 ? "true" : "false") + ",YAW=-0.42,PITCH=0.34,FOCAL=560,CAM=26;",
      "var SHAPES=[[[1,1,1,1]],[[1,1],[1,1]],[[0,1,0],[1,1,1]],[[1,0,0],[1,1,1]],[[0,0,1],[1,1,1]],[[1,1,0],[0,1,1]],[[0,1,1],[1,1,0]]];",
      "var COLORS=['#22d3ee','#fbbf24','#a78bfa','#fb7185','#34d399','#60a5fa','#f472b6'];",
      "var grid,piece,score,lines,iv,dead;",
      "function cell(px,py,c){cx.fillStyle=c;cx.fillRect(px+1,py+1,S-2,S-2);}",
      "function p3(x,y,z){var cy=Math.cos(YAW),sy=Math.sin(YAW),cp=Math.cos(PITCH),sp=Math.sin(PITCH);var x1=x*cy+z*sy,z1=-x*sy+z*cy,y1=y*cp-z1*sp,z2=y*sp+z1*cp,d=CAM-z2;if(d<1)d=1;var f=FOCAL/d;return {x:cv.width/2+x1*f,y:cv.height/2-y1*f,z:z2};}",
      "function shade(c,a){var r=parseInt(c.slice(1,3),16),g=parseInt(c.slice(3,5),16),b=parseInt(c.slice(5,7),16),t=a>0?255:0,p=Math.abs(a);return 'rgb('+Math.round(r+(t-r)*p)+','+Math.round(g+(t-g)*p)+','+Math.round(b+(t-b)*p)+')';}",
      "function line3(a,b,c,d,e,f){var p=p3(a,b,c),q=p3(d,e,f);cx.strokeStyle='#17233a';cx.lineWidth=1;cx.beginPath();cx.moveTo(p.x,p.y);cx.lineTo(q.x,q.y);cx.stroke();}",
      "function grid3(){for(var x=0;x<=COLS;x++)line3(x-5,-10,-0.5,x-5,10,-0.5);for(var y=0;y<=ROWS;y++)line3(-5,10-y,-0.5,5,10-y,-0.5);}",
      "function addCube(col,row,c,out){var x=col-4.5,y=9.5-row,h=0.46,v=[[[-h,-h,-h],[h,-h,-h],[h,h,-h],[-h,h,-h]],[[-h,-h,h],[h,-h,h],[h,h,h],[-h,h,h]],[[-h,h,-h],[h,h,-h],[h,h,h],[-h,h,h]],[[-h,-h,-h],[h,-h,-h],[h,-h,h],[-h,-h,h]],[[-h,-h,-h],[-h,-h,h],[-h,h,h],[-h,h,-h]],[[h,-h,-h],[h,-h,h],[h,h,h],[h,h,-h]]];var sh=[-.42,0,.36,-.55,-.16,-.26];for(var i=0;i<6;i++){var ps=[],z=0;for(var j=0;j<4;j++){var q=p3(x+v[i][j][0],y+v[i][j][1],v[i][j][2]);ps.push(q);z+=q.z;}out.push({p:ps,z:z/4,c:shade(c,sh[i])});}}",
      "function draw3d(){cx.fillStyle='#080d1a';cx.fillRect(0,0,cv.width,cv.height);grid3();var faces=[];for(var y=0;y<ROWS;y++)for(var x=0;x<COLS;x++)if(grid[y][x])addCube(x,y,grid[y][x],faces);if(piece&&!dead)piece.s.forEach(function(row,y){row.forEach(function(v,x){if(v)addCube(piece.x+x,piece.y+y,piece.c,faces);});});faces.sort(function(a,b){return a.z-b.z;});faces.forEach(function(face){cx.beginPath();cx.moveTo(face.p[0].x,face.p[0].y);for(var i=1;i<4;i++)cx.lineTo(face.p[i].x,face.p[i].y);cx.closePath();cx.fillStyle=face.c;cx.fill();cx.strokeStyle=face.c;cx.lineWidth=1;cx.stroke();});}",
      "function reset(){grid=[];for(var y=0;y<ROWS;y++){grid.push(Array(COLS).fill(''));}score=0;lines=0;dead=false;spawn();document.getElementById('score').textContent='0';document.getElementById('lines').textContent='0';document.getElementById('msg').textContent='start when ready';draw();}",
      "function spawn(){var s=SHAPES[Math.floor(Math.random()*SHAPES.length)];piece={s:JSON.parse(JSON.stringify(s)),x:Math.floor((COLS-s[0].length)/2),y:0,c:COLORS[Math.floor(Math.random()*COLORS.length)]};if(hit(piece.x,piece.y,piece.s)){dead=true;document.getElementById('msg').textContent='game over · score '+score;}}",
      "function hit(px,py,s){for(var y=0;y<s.length;y++)for(var x=0;x<s[y].length;x++){if(!s[y][x])continue;var nx=px+x,ny=py+y;if(nx<0||nx>=COLS||ny>=ROWS)return true;if(ny>=0&&grid[ny][nx])return true;}return false;}",
      "function lock(){piece.s.forEach(function(row,y){row.forEach(function(v,x){if(v&&piece.y+y>=0)grid[piece.y+y][piece.x+x]=piece.c;});});",
      "var cleared=0;grid=grid.filter(function(row){var full=row.every(function(v){return v;});if(full)cleared++;return !full;});while(grid.length<ROWS)grid.unshift(Array(COLS).fill(''));",
      "if(cleared){lines+=cleared;score+=cleared*100;document.getElementById('lines').textContent=lines;document.getElementById('score').textContent=score;}spawn();}",
      "function move(dx){if(!hit(piece.x+dx,piece.y,piece.s))piece.x+=dx;draw();}",
      "function down(){if(!hit(piece.x,piece.y+1,piece.s)){piece.y++;draw();}else{lock();draw();}}",
      "function rotate(){var s=piece.s,n=s[0].map(function(_,i){return s.map(function(r){return r[i];}).reverse();});if(!hit(piece.x,piece.y,n))piece.s=n;draw();}",
      "function drop(){while(!hit(piece.x,piece.y+1,piece.s))piece.y++;lock();draw();}",
      "function draw(){if(D3){draw3d();return;}cx.fillStyle='#080d1a';cx.fillRect(0,0,cv.width,cv.height);var ox=(cv.width-COLS*S)/2,oy=10;",
      "for(var y=0;y<ROWS;y++)for(var x=0;x<COLS;x++){cx.strokeStyle='#111a2c';cx.strokeRect(ox+x*S,oy+y*S,S,S);if(grid[y][x])cell(ox+x*S,oy+y*S,grid[y][x]);}",
      "if(piece&&!dead)piece.s.forEach(function(row,y){row.forEach(function(v,x){if(v)cell(ox+(piece.x+x)*S,oy+(piece.y+y)*S,piece.c);});});}",
      "function start(){if(dead||iv)return;iv=setInterval(function(){if(!dead)down();},520);document.getElementById('msg').textContent='running';}",
      "document.getElementById('go').addEventListener('click',start);document.getElementById('reset').addEventListener('click',function(){if(iv)clearInterval(iv);iv=null;reset();});",
      "document.addEventListener('keydown',function(e){var k=e.key;if(k==='ArrowLeft'){move(-1);e.preventDefault();}if(k==='ArrowRight'){move(1);e.preventDefault();}if(k==='ArrowDown'){down();e.preventDefault();}if(k==='ArrowUp'){rotate();e.preventDefault();}if(k===' '){drop();e.preventDefault();}});",
      "reset();"
    ].join("\n");
    return shell({
      title: opts.d3 ? "Tetris 3D" : "Tetris",
      sub: opts.d3 ? "stack, clear, survive — 10×20 with a projected 3D renderer" : "stack, clear, survive — 10×20",
      body: body,
      css: opts.d3 ? ".card canvas{transform:perspective(1600px) rotateX(3deg);box-shadow:0 30px 70px rgba(0,0,0,.6);border-radius:14px}@media(max-width:560px){.card canvas{transform:perspective(1100px) rotateX(2deg) scale(.99)}}" : "",
      js: js, theme: opts.theme
    });
  }

  /* --------------------------------------------------------------- maze -- */
  function maze(desc, opts) {
    var body = [
      '<div class="card" style="max-width:560px;margin:0 auto">',
      '<div class="row" style="justify-content:space-between;margin-bottom:8px"><span class="pill">steps <b id="steps" style="color:var(--text)">0</b></span><span class="pill" id="msg">reach the exit →</span></div>',
      '<canvas id="cv" width="525" height="375" style="width:100%;height:auto;border-radius:12px;background:#080d1a;border:1px solid var(--border)"></canvas>',
      '<div class="row" style="justify-content:center;margin-top:10px"><button class="btn ghost" id="new" type="button" style="padding:6px 12px;font-size:12px">new maze</button></div></div>'
    ].join("");
    var js = [
      "var cv=document.getElementById('cv'),cx=cv.getContext('2d'),W=21,H=15,T=25;",
      "var g,px,py,steps;",
      "function reset(){g=[];for(var y=0;y<H;y++){g.push(Array(W).fill(1));}var h=2166136261;for(var k=0;k<5;k++){h^=k+3;h=Math.imul(h,16777619);}",
      "function rnd(){h+=0x6D2B79F5;var t=h;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296;}",
      "function carve(x,y){g[y][x]=0;var d=[[2,0],[-2,0],[0,2],[0,-2]];for(var i=d.length-1;i>0;i--){var j=Math.floor(rnd()*(i+1));var t=d[i];d[i]=d[j];d[j]=t;}",
      "d.forEach(function(v){var nx=x+v[0],ny=y+v[1];if(nx>0&&nx<W-1&&ny>0&&ny<H-1&&g[ny][nx]){g[y+v[1]/2][x+v[0]/2]=0;carve(nx,ny);}});}",
      "carve(1,1);g[H-2][W-2]=0;px=1;py=1;steps=0;document.getElementById('steps').textContent='0';document.getElementById('msg').textContent='reach the exit →';draw();}",
      "function draw(){cx.fillStyle='#080d1a';cx.fillRect(0,0,cv.width,cv.height);",
      "for(var y=0;y<H;y++)for(var x=0;x<W;x++){cx.fillStyle=g[y][x]?'#22304d':'#0d1830';cx.fillRect(x*T,y*T,T-1,T-1);}",
      "cx.fillStyle='#34d399';cx.fillRect((W-2)*T, (H-2)*T,T-1,T-1);",
      "cx.fillStyle='#fbbf24';cx.beginPath();cx.arc(px*T+T/2,py*T+T/2,T*0.3,0,7);cx.fill();}",
      "function move(dx,dy){var nx=px+dx,ny=py+dy;if(nx<0||nx>=W||ny<0||ny>=H||g[ny][nx])return;px=nx;py=ny;steps++;document.getElementById('steps').textContent=steps;",
      "if(px===W-2&&py===H-2)document.getElementById('msg').textContent='solved in '+steps+' steps!';draw();}",
      "document.addEventListener('keydown',function(e){if(e.key==='ArrowLeft')move(-1,0);if(e.key==='ArrowRight')move(1,0);if(e.key==='ArrowUp')move(0,-1);if(e.key==='ArrowDown')move(0,1);});",
      "var sx=0,sy=0;cv.addEventListener('touchstart',function(e){sx=e.touches[0].clientX;sy=e.touches[0].clientY;},{passive:true});",
      "cv.addEventListener('touchend',function(e){var dx=e.changedTouches[0].clientX-sx,dy=e.changedTouches[0].clientY-sy;if(Math.abs(dx)>Math.abs(dy))move(dx>0?1:-1,0);else move(0,dy>0?1:-1);},{passive:true});",
      "document.getElementById('new').addEventListener('click',reset);reset();"
    ].join("\n");
    return shell({ title: "Maze", sub: "a generated maze · arrows or swipe", body: body, js: js, theme: opts.theme });
  }

  /* ----------------------------------------------------------- adventure -- */
  function adventure(desc, opts) {
    var body = [
      '<div class="card" style="max-width:640px;margin:0 auto">',
      '<div class="row" style="justify-content:space-between;margin-bottom:10px"><span class="pill">courage <b id="courage" style="color:var(--text)">0</b></span><span class="pill">insight <b id="insight" style="color:var(--text)">0</b></span><span class="pill">ending <b id="ending" style="color:var(--text)">—</b></span></div>',
      '<div id="scene" style="font-size:16px;line-height:1.65;min-height:120px"></div>',
      '<div id="choices" style="display:flex;flex-direction:column;gap:8px;margin-top:14px"></div>',
      '<div class="row" style="justify-content:flex-end;margin-top:12px"><button class="btn ghost" id="restart" type="button" style="padding:6px 12px;font-size:12px">restart</button></div>',
      '<p class="muted small" style="margin:10px 2px 0">a branching text RPG · your choices change the ending</p></div>'
    ].join("");
    var js = [
      "var S={courage:0,insight:0,node:'start',ending:''};",
      "var STORY={start:{t:'You wake at the mouth of the Hollow Archive. Two doors: one iron, one ivy-covered.',c:[['Open the iron door',{courage:1,node:'iron'}],['Part the ivy',{insight:1,node:'ivy'}]]},",
      "iron:{t:'The iron door groans. A bridge of black glass spans a chasm; a voice offers you safe passage for a memory.',c:[['Pay the memory',{insight:-1,node:'bridge'}],['Walk the edge',{courage:2,node:'edge'}]]},",
      "ivy:{t:'Behind the ivy is a reading room. A book writes itself as you watch.',c:[['Read the book',{insight:2,node:'book'}],['Burn it',{courage:1,node:'burn'}]]},",
      "bridge:{t:'The bridge holds. On the far side, a locked cabinet hums with light.',c:[['Pick the lock',{courage:1,node:'cabinet'}],['Knock politely',{insight:1,node:'knock'}]]},",
      "edge:{t:'You cross the black glass on foot. The voice respects you and steps aside.',c:[['Continue',{node:'cabinet'}]]},",
      "book:{t:'The book describes this exact moment. You learn the Archive is a mirror.',c:[['Step through the mirror',{insight:1,node:'mirror'}],['Close the book',{node:'cabinet'}]]},",
      "burn:{t:'The book burns. The Archive dims, then offers you its only key.',c:[['Take the key',{node:'cabinet'}]]},",
      "cabinet:{t:'The cabinet opens on a small door made of dawn light.',c:[['Open it',{node:'end'}]]},",
      "knock:{t:'A librarian made of dust answers and hands you a map of your own choices.',c:[['Follow the map',{node:'end'}]]},",
      "mirror:{t:'You step through. The room is the same, but you are older and calmer.',c:[['Return',{node:'end'}]]},",
      "end:{t:'You leave the Archive with something you did not carry in. The door closes softly.',c:[]}};",
      "function render(){var n=STORY[S.node];document.getElementById('scene').textContent=n.t;",
      "document.getElementById('courage').textContent=S.courage;document.getElementById('insight').textContent=S.insight;",
      "var box=document.getElementById('choices');box.innerHTML='';",
      "if(!n.c.length){var done=document.createElement('div');done.className='card';done.style.padding='12px';done.innerHTML='<b>Ending: '+(S.courage>S.insight?'the bold path':S.insight>S.courage?'the quiet path':'the balanced path')+'</b>';box.appendChild(done);",
      "document.getElementById('ending').textContent=S.courage>S.insight?'bold':S.insight>S.courage?'quiet':'balanced';return;}",
      "n.c.forEach(function(ch){var b=document.createElement('button');b.type='button';b.className='btn ghost';b.style.textAlign='left';b.style.padding='12px 14px';b.textContent=ch[0];",
      "b.addEventListener('click',function(){var e=ch[1];if(e.courage)S.courage+=e.courage;if(e.insight)S.insight+=e.insight;S.node=e.node;render();});box.appendChild(b);});}",
      "document.getElementById('restart').addEventListener('click',function(){S={courage:0,insight:0,node:'start',ending:''};document.getElementById('ending').textContent='—';render();});render();"
    ].join("\n");
    return shell({ title: "Hollow Archive", sub: "a branching text RPG · choices change the ending", body: body, js: js, theme: opts.theme });
  }

  /* ------------------------------------------------------------ typing --- */
  function typing(desc, opts) {
    var body = [
      '<div class="card" style="max-width:680px;margin:0 auto">',
      '<div class="row" style="justify-content:space-between;margin-bottom:12px"><span class="pill">wpm <b id="wpm" style="color:var(--text)">0</b></span><span class="pill">accuracy <b id="acc" style="color:var(--text)">100%</b></span><span class="pill">time <b id="time" style="color:var(--text)">0s</b></span></div>',
      '<div id="target" style="font:16px/1.7 ui-monospace,monospace;padding:14px;border:1px solid var(--border);border-radius:10px;background:var(--panel2);min-height:90px"></div>',
      '<textarea id="typed" rows="3" placeholder="start typing the sentence above…" style="margin-top:10px;font-family:ui-monospace,monospace;resize:vertical"></textarea>',
      '<div class="row" style="justify-content:space-between;margin-top:10px"><span id="msg" class="muted small">the timer starts on your first keystroke.</span><button class="btn ghost" id="new" type="button" style="padding:6px 12px;font-size:12px">new sentence</button></div>',
      '</div>'
    ].join("");
    var css = ".ok{color:var(--ok)}.bad{color:var(--bad);text-decoration:underline}";
    var js = [
      "var LINES=['the quick brown fox jumps over the lazy dog','a deterministic router makes the same choice every time','small tools composed well beat one large tool that does everything','practice is a loop: type, notice, adjust, repeat','the page runs offline and keeps your work in this browser'];",
      "var line='',start=0,iv=null;",
      "function paint(){var t=document.getElementById('typed').value;var html='';var ok=0;",
      "for(var i=0;i<line.length;i++){var c=line[i],u=t[i];var cls=u===undefined?'':(u===c?'ok':'bad');if(u===c)ok++;html+='<span class=\"'+cls+'\">'+c+'</span>';}",
      "document.getElementById('target').innerHTML=html;var acc=t.length?Math.round(ok/t.length*100):100;document.getElementById('acc').textContent=acc+'%';",
      "if(start){var sec=Math.max(1,(Date.now()-start)/1000);var words=ok/5;document.getElementById('wpm').textContent=Math.round(words/(sec/60));document.getElementById('time').textContent=Math.round(sec)+'s';}",
      "if(t===line){document.getElementById('msg').textContent='clean run — new sentence?';if(iv)clearInterval(iv);}}",
      "function fresh(){line=LINES[Math.floor(Math.random()*LINES.length)];document.getElementById('typed').value='';document.getElementById('typed').disabled=false;document.getElementById('typed').focus();start=0;document.getElementById('wpm').textContent='0';document.getElementById('acc').textContent='100%';document.getElementById('time').textContent='0s';document.getElementById('msg').textContent='the timer starts on your first keystroke.';paint();}",
      "document.getElementById('typed').addEventListener('input',function(){if(!start){start=Date.now();if(iv)clearInterval(iv);iv=setInterval(paint,250);}paint();});",
      "document.getElementById('new').addEventListener('click',fresh);fresh();"
    ].join("\n");
    return shell({ title: "Typing test", sub: "measure speed and accuracy on a fixed line", body: body, css: css, js: js, theme: opts.theme });
  }


  /* -------------------------------------------------------------- social -- */
  function social(desc, opts) {
    var body = [
      '<div class="grid" style="grid-template-columns:minmax(0,1fr);gap:14px">',
      '<div class="card" style="padding:14px">',
      '<div class="row" style="align-items:flex-start;gap:10px">',
      '<div class="pill" style="flex:0 0 auto">you</div>',
      '<textarea id="draft" rows="2" placeholder="what is happening?" style="flex:1;resize:vertical"></textarea>',
      '</div>',
      '<div class="row" style="justify-content:space-between;margin-top:8px">',
      '<span class="muted small" id="count">0 / 280</span>',
      '<button class="btn" id="post" type="button">Post</button>',
      '</div></div>',
      '<div id="feed" class="grid" style="gap:12px"></div>',
      '<p class="muted small" style="text-align:center">posts live in this browser only · no accounts, no network</p>',
      '</div>'
    ].join("");
    var css = [
      ".post{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--border);border-radius:14px;padding:14px}",
      ".post .who{display:flex;align-items:center;gap:8px;margin-bottom:6px}",
      ".avatar{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:12px;color:#04121a;background:linear-gradient(135deg,var(--accent),var(--accent2))}",
      ".post p{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}",
      ".acts{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}",
      ".acts button{background:transparent;border:1px solid var(--border);color:var(--muted);border-radius:999px;padding:4px 10px;font-size:12px;cursor:pointer}",
      ".acts button.on{color:var(--bad);border-color:var(--bad)}",
      ".cmt{margin-top:8px;display:flex;flex-direction:column;gap:5px}",
      ".cmt div{font-size:12.5px;background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:6px 9px}"
    ].join("");
    var js = [
      "var KEY='toolrx.social.v1',feed=document.getElementById('feed');",
      "var seed=[{id:1,who:'ada',text:'shipping a tiny tool beats planning a big one. today: one honest page.',likes:3,liked:false,time:'2h',cmts:['this is the way']},",
      "{id:2,who:'mira',text:'the best interface is the one you can explain in a sentence.',likes:5,liked:false,time:'5h',cmts:[]},",
      "{id:3,who:'jun',text:'deterministic does not mean boring. it means you can test it.',likes:2,liked:false,time:'1d',cmts:['and debug it at 2am']}];",
      "function load(){try{var raw=localStorage.getItem(KEY);if(raw){var p=JSON.parse(raw);if(Array.isArray(p))return p;}}catch(e){}return seed.slice();}",
      "var posts=load();",
      "function save(){try{localStorage.setItem(KEY,JSON.stringify(posts));}catch(e){}}",
      "function esc(s){return String(s).replace(/[&<>\"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c];});}",
      "function draw(){feed.innerHTML='';",
      "posts.forEach(function(p){var d=document.createElement('article');d.className='post';",
      "var cm=p.cmts.map(function(c){return '<div>'+esc(c)+'</div>';}).join('');",
      "d.innerHTML='<div class=\"who\"><span class=\"avatar\">'+esc(p.who.slice(0,2).toUpperCase())+'</span><b>@'+esc(p.who)+'</b><span class=\"muted small\">· '+esc(p.time)+'</span></div>'",
      "+'<p>'+esc(p.text)+'</p>'",
      "+'<div class=\"acts\"><button type=\"button\" data-like=\"'+p.id+'\" class=\"'+(p.liked?'on':'')+'\">'+(p.liked?'♥':'♡')+' '+p.likes+'</button>'",
      "+'<button type=\"button\" data-cm=\"'+p.id+'\">comment</button>'",
      "+'<button type=\"button\" data-del=\"'+p.id+'\">delete</button></div>'",
      "+'<div class=\"cmt\">'+cm+'</div>';",
      "d.querySelector('[data-cm]').addEventListener('click',function(){var t=prompt('comment on @'+p.who);if(t&&t.trim()){p.cmts.push(t.trim());save();draw();}});",
      "d.querySelector('[data-like]').addEventListener('click',function(){p.liked=!p.liked;p.likes+=p.liked?1:-1;save();draw();});",
      "d.querySelector('[data-del]').addEventListener('click',function(){posts=posts.filter(function(x){return x.id!==p.id;});save();draw();});",
      "feed.appendChild(d);});}",
      "document.getElementById('draft').addEventListener('input',function(){document.getElementById('count').textContent=this.value.length+' / 280';});",
      "document.getElementById('post').addEventListener('click',function(){var t=document.getElementById('draft').value.trim();if(!t)return;if(t.length>280)t=t.slice(0,280);",
      "posts.unshift({id:Date.now(),who:'you',text:t,likes:0,liked:false,time:'now',cmts:[]});document.getElementById('draft').value='';document.getElementById('count').textContent='0 / 280';save();draw();});",
      "draw();"
    ].join("\n");
    return shell({ title: "Tiny social feed", sub: "compose, like, comment, delete — a real feed in one page", body: body, css: css, js: js, theme: opts.theme });
  }

  /* ---------------------------------------------------------------- blog -- */
  function blog(desc, opts) {
    var body = [
      '<div class="grid" id="app" style="grid-template-columns:minmax(0,1fr);gap:14px">',
      '<div class="card" id="listCard">',
      '<div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 style="margin:0;font-size:18px">journal</h2><button class="btn ghost" id="new" type="button" style="padding:7px 12px;font-size:12px">write a post</button></div>',
      '<div id="list" class="grid" style="gap:10px"></div>',
      '</div>',
      '<div class="card" id="editCard" hidden>',
      '<div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 style="margin:0;font-size:18px">new post</h2><button class="btn ghost" id="cancel" type="button" style="padding:7px 12px;font-size:12px">cancel</button></div>',
      '<input id="title" placeholder="title" style="margin-bottom:8px">',
      '<textarea id="body" rows="8" placeholder="write something true…" style="resize:vertical"></textarea>',
      '<div class="row" style="justify-content:flex-end;margin-top:10px"><button class="btn" id="save" type="button">publish</button></div>',
      '</div>',
      '<div class="card" id="readCard" hidden>',
      '<div class="row" style="justify-content:space-between;margin-bottom:8px"><button class="btn ghost" id="back" type="button" style="padding:6px 12px;font-size:12px">← back</button><button class="btn ghost" id="del" type="button" style="padding:6px 12px;font-size:12px">delete</button></div>',
      '<h2 id="rTitle" style="margin:0 0 4px"></h2><div class="muted small" id="rMeta"></div>',
      '<div id="rBody" style="margin-top:12px;line-height:1.7"></div>',
      '</div>',
      '<p class="muted small" style="text-align:center">posts persist in this browser · one page, no server</p></div>'
    ].join("");
    var js = [
      "var KEY='toolrx.blog.v1';",
      "var seed=[{id:1,title:'why small tools',at:'2026-01-04',body:'A small tool does one thing and tells you the truth about it.\\n\\nThis journal is a single page. Adding a post appends an object to an array and redraws. That is the whole architecture.'},",
      "{id:2,title:'the shape of a page',at:'2026-01-09',body:'Every page is three parts: state, render, events.\\n\\nState is the data. Render turns data into DOM. Events change data and call render again. Keep those three separate and the page stays easy to change.'}];",
      "var posts=(function(){try{var r=localStorage.getItem(KEY);if(r){var p=JSON.parse(r);if(Array.isArray(p))return p;}}catch(e){}return seed.slice();})();",
      "var list=document.getElementById('list');",
      "function esc(s){return String(s).replace(/[&<>\"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c];});}",
      "function save(){try{localStorage.setItem(KEY,JSON.stringify(posts));}catch(e){}}",
      "function home(){document.getElementById('editCard').hidden=true;document.getElementById('readCard').hidden=true;document.getElementById('listCard').hidden=false;drawList();}",
      "function drawList(){list.innerHTML='';if(!posts.length){list.innerHTML='<p class=\"muted small\">no posts yet — write the first one.</p>';return;}",
      "posts.slice().sort(function(a,b){return b.at.localeCompare(a.at);}).forEach(function(p){var d=document.createElement('button');d.type='button';",
      "d.style.cssText='text-align:left;background:var(--panel2);border:1px solid var(--border);border-radius:12px;padding:12px;cursor:pointer;color:var(--text)';",
      "d.innerHTML='<b style=\"display:block;font-size:15px\">'+esc(p.title)+'</b><span class=\"muted small\">'+esc(p.at)+' · '+String(p.body).split(/\\s+/).filter(Boolean).length+' words</span>';",
      "d.addEventListener('click',function(){read(p.id);});list.appendChild(d);});}",
      "function read(id){var p=posts.filter(function(x){return x.id===id;})[0];if(!p)return;",
      "document.getElementById('listCard').hidden=true;document.getElementById('editCard').hidden=true;document.getElementById('readCard').hidden=false;",
      "document.getElementById('rTitle').textContent=p.title;document.getElementById('rMeta').textContent=p.at;",
      "document.getElementById('rBody').innerHTML=String(p.body).split(/\\n\\n+/).map(function(x){return '<p>'+esc(x).replace(/\\n/g,'<br>')+'</p>';}).join('');",
      "document.getElementById('del').onclick=function(){posts=posts.filter(function(x){return x.id!==id;});save();home();};}",
      "document.getElementById('new').addEventListener('click',function(){document.getElementById('listCard').hidden=true;document.getElementById('readCard').hidden=true;document.getElementById('editCard').hidden=false;document.getElementById('title').focus();});",
      "document.getElementById('cancel').addEventListener('click',home);document.getElementById('back').addEventListener('click',home);",
      "document.getElementById('save').addEventListener('click',function(){var t=document.getElementById('title').value.trim(),b=document.getElementById('body').value.trim();if(!t||!b)return;",
      "posts.push({id:Date.now(),title:t,at:new Date().toISOString().slice(0,10),body:b});document.getElementById('title').value='';document.getElementById('body').value='';save();home();});",
      "home();"
    ].join("\n");
    return shell({ title: "Journal", sub: "write, read, delete posts — state / render / events in one page", body: body, js: js, theme: opts.theme });
  }

  /* --------------------------------------------------------------- forum -- */
  function forum(desc, opts) {
    var body = [
      '<div class="card">',
      '<div class="row" style="justify-content:space-between;margin-bottom:10px"><h2 style="margin:0;font-size:18px">forum</h2><button class="btn" id="newThread" type="button">new thread</button></div>',
      '<div id="threads" class="grid" style="gap:8px"></div>',
      '<div id="thread" hidden style="margin-top:6px"></div>',
      '</div>',
      '<p class="muted small" style="text-align:center">threads + replies persist in this browser</p>'
    ].join("");
    var css = ".thread{display:flex;justify-content:space-between;gap:10px;align-items:center;background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:10px 12px;cursor:pointer}.thread:hover{border-color:var(--accent)}";
    var js = [
      "var KEY='toolrx.forum.v1';",
      "var seed=[{id:1,title:'What makes a page easy to change?',author:'ada',posts:[{who:'ada',text:'I think it is separating state from rendering.'},{who:'mira',text:'Agreed — plus one small function per event.'}]},",
      "{id:2,title:'Best way to store a tiny app?',author:'jun',posts:[{who:'jun',text:'localStorage is enough until it is not.'},{who:'ada',text:'And always wrap it in try/catch — private mode throws.'}]}];",
      "var threads=(function(){try{var r=localStorage.getItem(KEY);if(r){var p=JSON.parse(r);if(Array.isArray(p))return p;}}catch(e){}return seed.slice();})();",
      "var box=document.getElementById('threads'),view=document.getElementById('thread');",
      "function esc(s){return String(s).replace(/[&<>\"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c];});}",
      "function save(){try{localStorage.setItem(KEY,JSON.stringify(threads));}catch(e){}}",
      "function home(){view.hidden=true;box.hidden=false;box.innerHTML='';",
      "threads.forEach(function(t){var d=document.createElement('div');d.className='thread';",
      "d.innerHTML='<div><b>'+esc(t.title)+'</b><div class=\"muted small\">'+esc(t.author)+' · '+t.posts.length+' replies</div></div><span class=\"pill\">open</span>';",
      "d.addEventListener('click',function(){open(t.id);});box.appendChild(d);});}",
      "function open(id){var t=threads.filter(function(x){return x.id===id;})[0];if(!t)return;box.hidden=true;view.hidden=false;",
      "view.innerHTML='<div class=\"row\" style=\"justify-content:space-between\"><button class=\"btn ghost\" id=\"back\" type=\"button\" style=\"padding:6px 12px;font-size:12px\">← threads</button><span class=\"pill\">'+t.posts.length+' replies</span></div>'",
      "+'<h2 style=\"margin:10px 0 4px\">'+esc(t.title)+'</h2><div class=\"muted small\">started by @'+esc(t.author)+'</div>'",
      "+'<div id=\"replies\" class=\"grid\" style=\"gap:8px;margin-top:12px\"></div>'",
      "+'<div class=\"row\" style=\"margin-top:10px\"><input id=\"reply\" placeholder=\"reply…\" style=\"flex:1\"><button class=\"btn\" id=\"sendReply\" type=\"button\">Send</button></div>';",
      "var rbox=document.getElementById('replies');",
      "function paint(){rbox.innerHTML='';t.posts.forEach(function(p){var d=document.createElement('div');d.style.cssText='background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:10px';",
      "d.innerHTML='<b class=\"small\">@'+esc(p.who)+'</b><div style=\"margin-top:3px;white-space:pre-wrap\">'+esc(p.text)+'</div>';rbox.appendChild(d);});}",
      "document.getElementById('back').addEventListener('click',home);",
      "document.getElementById('sendReply').addEventListener('click',function(){var v=document.getElementById('reply').value.trim();if(!v)return;t.posts.push({who:'you',text:v});save();paint();document.getElementById('reply').value='';});",
      "paint();}",
      "document.getElementById('newThread').addEventListener('click',function(){var title=prompt('thread title');if(!title||!title.trim())return;threads.unshift({id:Date.now(),title:title.trim(),author:'you',posts:[]});save();home();});",
      "home();"
    ].join("\n");
    return shell({ title: "Forum", sub: "threads, replies, and a tiny persisted store", body: body, css: css, js: js, theme: opts.theme });
  }

  /* ---------------------------------------------------------------- chat -- */
  function chatSite(desc, opts) {
    var body = [
      '<div class="card" style="max-width:620px;margin:0 auto;display:flex;flex-direction:column;height:min(70vh,520px)">',
      '<div class="row" style="justify-content:space-between;border-bottom:1px solid var(--border);padding-bottom:10px"><b># general</b><span class="pill">you + echo bot</span></div>',
      '<div id="msgs" style="flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding:12px 2px"></div>',
      '<div class="row" style="border-top:1px solid var(--border);padding-top:10px"><input id="msg" placeholder="say something…" style="flex:1" autocomplete="off"><button class="btn" id="sendMsg" type="button">Send</button></div>',
      '</div>',
      '<p class="muted small" style="text-align:center">a real chat surface · messages persist locally · the bot answers deterministically</p>'
    ].join("");
    var css = [
      ".bubble{max-width:82%;padding:8px 11px;border-radius:12px;font-size:14px;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere}",
      ".bubble.me{align-self:flex-end;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#04121a;font-weight:600;border-bottom-right-radius:4px}",
      ".bubble.bot{align-self:flex-start;background:var(--panel2);border:1px solid var(--border);border-bottom-left-radius:4px}",
      ".bubble small{display:block;opacity:.65;font-size:10px;margin-bottom:2px;font-weight:700;letter-spacing:.05em;text-transform:uppercase}"
    ].join("");
    var js = [
      "var KEY='toolrx.chat.v1',box=document.getElementById('msgs');",
      "var msgs=(function(){try{var r=localStorage.getItem(KEY);if(r){var p=JSON.parse(r);if(Array.isArray(p)&&p.length)return p;}}catch(e){}return [{who:'bot',text:'hey — this is a real chat page. send a message and I will answer from a small deterministic script.'}];})();",
      "function esc(s){return String(s).replace(/[&<>\"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c];});}",
      "function save(){try{localStorage.setItem(KEY,JSON.stringify(msgs.slice(-60)));}catch(e){}}",
      "function paint(){box.innerHTML='';msgs.forEach(function(m){var d=document.createElement('div');d.className='bubble '+(m.who==='me'?'me':'bot');d.innerHTML='<small>'+esc(m.who==='me'?'you':'bot')+'</small>'+esc(m.text);box.appendChild(d);});box.scrollTop=box.scrollHeight;}",
      "function reply(t){var s=t.toLowerCase();",
      "if(/hello|hi|hey/.test(s))return 'hey. what are you building?';",
      "if(/help|how/.test(s))return 'try: send a message, reload the page, and see that the conversation is still here.';",
      "if(/bye|later/.test(s))return 'see you. the history stays in this browser.';",
      "if(/\\?$/.test(t))return 'good question. in this demo I answer patterns, not ideas — but the message pipeline is real.';",
      "return 'you said: \"'+t.slice(0,120)+'\". this bot is a few if-statements and an array — swap in any API later.';}",
      "function send(){var input=document.getElementById('msg'),t=input.value.trim();if(!t)return;msgs.push({who:'me',text:t});input.value='';paint();",
      "setTimeout(function(){msgs.push({who:'bot',text:reply(t)});save();paint();},320);}",
      "document.getElementById('sendMsg').addEventListener('click',send);",
      "document.getElementById('msg').addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();send();}});",
      "paint();"
    ].join("\n");
    return shell({ title: "Chat", sub: "messages, persistence, and a deterministic reply loop", body: body, css: css, js: js, theme: opts.theme });
  }

  /* --------------------------------------------------- architecture brief -- */
  var ARCH = {
    calculator: {
      files: ["index.html", "styles.css", "app.js"],
      state: "the current display string, the pending operand, and the pending operator",
      modules: ["input handling: digit / operator / equals", "expression evaluation: one function, no eval", "render: write the display and history"],
      flow: "button press → update state → render display → (on equals) evaluate → store result",
      extend: "add keyboard events, a history list, or memory keys — each is a separate function",
      steps: ["lay out the keypad with data-key attributes", "write press(key) that mutates state", "write evaluate() with explicit precedence", "render from state after every press"]
    },
    todo: {
      files: ["index.html", "styles.css", "app.js"],
      state: "an array of {id, text, done}",
      modules: ["add(text)", "toggle(id)", "remove(id)", "render(list)"],
      flow: "form submit → add → save → render; checkbox change → toggle → save → render",
      extend: "filters, due dates, drag order — keep each feature as a pure function over the array",
      steps: ["define the item shape", "render from the array only", "persist with JSON.stringify", "add one event per action"]
    },
    rpg: {
      files: ["index.html", "styles.css", "app.js"],
      state: "player {x,y,hp,max,lv,xp,pot}, battle {foe,hp,guard}, cleared map, log",
      modules: ["MAP + tile lookup", "move(dx,dy) with collision", "startBattle / act / foeTurn", "draw() from state", "save/load"],
      flow: "key or button → move/act → update state → draw or battle overlay → save on demand",
      extend: "add items, quests, more maps — the map is data, the battle is a state machine",
      steps: ["draw the tile map from a string array", "move the player with collision checks", "add a foe table and battle state", "wire attack/defend/heal as state transitions", "persist with a versioned key"]
    },
    platformer: {
      files: ["index.html", "styles.css", "app.js"],
      state: "player {x,y,vx,vy,on}, platforms[], coins[], camera",
      modules: ["input map", "physics step (gravity, collision)", "draw()", "reset()"],
      flow: "keydown sets input → physics step each frame → resolve collisions → draw",
      extend: "enemies, moving platforms, levels as data",
      steps: ["define the platform rectangles", "apply gravity and integrate position", "resolve vertical then horizontal collisions", "collect coins by rectangle overlap", "draw from state each frame"]
    },
    snake: { files: ["index.html", "styles.css", "app.js"], state: "snake array, direction, next direction, food, score", modules: ["step()", "place food", "draw()"], flow: "interval → step → collision/food → draw", extend: "speed ramp, walls, wrap toggle", steps: ["grid state", "one step per tick", "collision against self", "food placement that avoids the snake"] },
    breakout: { files: ["index.html", "styles.css", "app.js"], state: "paddle, ball, bricks, lives, score", modules: ["launch", "physics", "brick collision", "draw"], flow: "frame → move ball → bounce/collide → draw", extend: "power-ups, levels, sound", steps: ["paddle follows pointer", "ball bounces off edges", "brick grid with hp", "reset on life loss"] },
    pong: { files: ["index.html", "styles.css", "app.js"], state: "two paddles, ball, scores", modules: ["frame loop", "CPU follow with a cap", "score + reset"], flow: "frame → move ball → paddle collision → score", extend: "difficulty, two-player, spin", steps: ["draw two paddles", "reflect the ball on contact", "add a beatable CPU", "first to 7"] },
    "2048": { files: ["index.html", "styles.css", "app.js"], state: "16 tiles, score, over flag", modules: ["move(dx,dy)", "merge lines", "add random tile", "canMove"], flow: "arrow → transform grid → merge → add tile → render", extend: "undo, animations, size variants", steps: ["represent the grid as 16 values", "compress a line then merge neighbours", "spawn a tile only after a real move", "detect no-moves"] },
    minesweeper: { files: ["index.html", "styles.css", "app.js"], state: "cells {mine, open, flag, count}, first-click flag", modules: ["plant mines after first click", "flood reveal", "check win"], flow: "click → plant (once) → reveal/flood → win/lose", extend: "board sizes, timers, safe-start", steps: ["build 100 cells", "plant mines away from the first click", "count neighbours", "flood-open empty cells"] },
    tetris: { files: ["index.html", "styles.css", "app.js"], state: "grid, active piece, score, lines", modules: ["spawn", "collision", "rotate", "lock + clear"], flow: "tick/keys → move or rotate → lock → clear rows → spawn", extend: "next-piece preview, hold, levels", steps: ["define shapes as matrices", "collision against grid edges", "rotate by transposing", "clear full rows and score"] },
    maze: { files: ["index.html", "styles.css", "app.js"], state: "grid, player, steps", modules: ["seeded carve", "move with walls", "draw"], flow: "key/swipe → move if open → check exit", extend: "sizes, monsters, fog", steps: ["carve with depth-first search", "keep walls as 1s", "move only into 0s", "show step count"] },
    adventure: { files: ["index.html", "styles.css", "app.js"], state: "current node, courage, insight", modules: ["STORY object", "render node", "apply choice"], flow: "choice → adjust stats → set node → render", extend: "inventory, dice, multiple endings", steps: ["write scenes as nodes with choices", "apply effects on choice", "render from the node", "branch the ending on stats"] },
    typing: { files: ["index.html", "styles.css", "app.js"], state: "target line, typed text, start time, timer", modules: ["render diff", "accuracy", "wpm"], flow: "input → diff → accuracy + wpm → finish on exact match", extend: "word lists, difficulty, history", steps: ["render per-character diff", "start the clock on first key", "compute correct chars / elapsed", "reset on demand"] },
    social: { files: ["index.html", "styles.css", "app.js"], state: "posts [{id,who,text,likes,liked,cmts}]", modules: ["load/save", "render feed", "compose", "like", "comment", "delete"], flow: "action → mutate one post → save → render", extend: "profiles, follows, images, pagination", steps: ["model a post as data", "render from the array", "one handler per action", "persist a versioned key"] },
    blog: { files: ["index.html", "styles.css", "app.js"], state: "posts [{id,title,at,body}], view (list/edit/read)", modules: ["drawList", "read", "savePost", "delete"], flow: "view switch → render → mutate → save", extend: "tags, search, markdown, drafts", steps: ["three views, one page", "render list from data", "read view with paragraphs", "persist on publish"] },
    forum: { files: ["index.html", "styles.css", "app.js"], state: "threads [{id,title,author,posts[]}]", modules: ["list", "open thread", "reply", "new thread"], flow: "open → render replies → append → save", extend: "categories, votes, quoting", steps: ["threads contain posts", "open one thread at a time", "append replies to the thread", "persist the whole tree"] },
    chat: { files: ["index.html", "styles.css", "app.js"], state: "messages [{who,text}]", modules: ["append", "render", "deterministic reply"], flow: "send → append → render → reply → append", extend: "rooms, presence, real transport", steps: ["append and scroll", "persist the last N", "reply from a pattern function", "keep transport separate"] },
    landing: { files: ["index.html", "styles.css", "app.js"], state: "none (content only)", modules: ["hero", "features", "call to action"], flow: "static layout, one small enhancement", extend: "forms, pricing, analytics", steps: ["one message per section", "one primary action", "responsive grid", "no unnecessary script"] },
    dashboard: { files: ["index.html", "styles.css", "app.js"], state: "metrics array", modules: ["cards", "chart", "refresh"], flow: "state → card + chart render", extend: "filters, time ranges, live data", steps: ["define the metric shape", "render cards from data", "draw a simple chart", "keep refresh deterministic"] },
    game: {
      files: ["index.html", "styles.css", "app.js"],
      state: "one game object: positions, velocity, score, and a running flag",
      modules: ["input", "update(dt)", "collision", "draw()", "reset()"],
      flow: "input → update state → resolve collisions → draw → repeat on requestAnimationFrame",
      extend: "levels as data, sound, a title screen, persistence",
      steps: ["choose the state shape", "draw from state only", "add the update loop", "add collision + scoring", "add reset and pause"]
    },
    playground: {
      files: ["index.html", "styles.css", "app.js"],
      state: "the inputs and the last result",
      modules: ["a pure function per operation", "a render function", "one submit handler"],
      flow: "input → validate → call a pure function → render the result (and the error)",
      extend: "more pure functions, a history list, URL state",
      steps: ["write the function signature and return shape", "handle the empty/invalid case first", "render the result", "add one example per operation"]
    }
  };

  function archFor(kind) {
    return ARCH[kind] || ARCH.landing;
  }

  function architecture(kind, desc, opts) {
    var real = canonical(kind, desc);
    var a = archFor(real);
    var name = titleFor(real, desc);
    var body = [
      '<div class="card">',
      '<p class="muted small" style="margin-top:0">this is a build brief, not the finished app. it tells you the shape to build.</p>',
      '<h2 style="margin:10px 0 6px;font-size:18px">files</h2>',
      '<pre style="background:var(--panel2);border:1px solid var(--border);border-radius:10px;padding:12px;overflow:auto">' + esc(a.files.join("\n")) + '</pre>',
      '<h2 style="margin:16px 0 6px;font-size:18px">state</h2><p style="margin:0">' + esc(a.state) + '</p>',
      '<h2 style="margin:16px 0 6px;font-size:18px">modules</h2><ul style="margin:0;padding-left:20px">' + a.modules.map(function (m) { return "<li>" + esc(m) + "</li>"; }).join("") + '</ul>',
      '<h2 style="margin:16px 0 6px;font-size:18px">data flow</h2><p style="margin:0">' + esc(a.flow) + '</p>',
      '<h2 style="margin:16px 0 6px;font-size:18px">build order</h2><ol style="margin:0;padding-left:20px">' + a.steps.map(function (s) { return "<li>" + esc(s) + "</li>"; }).join("") + '</ol>',
      '<h2 style="margin:16px 0 6px;font-size:18px">extend it</h2><p style="margin:0">' + esc(a.extend) + '</p>',
      '</div>',
      '<p class="muted small" style="text-align:center">ask again with &quot;build it&quot; to get the finished starter</p>'
    ].join("");
    return shell({ title: "Architecture · " + name, sub: "how to build " + name.toLowerCase() + " — files, state, modules, order", body: body, theme: opts.theme });
  }

  function blueprint(kind, desc, opts) {
    var real = canonical(kind, desc);
    var a = archFor(real);
    var name = titleFor(real, desc);
    return brief(kind, desc);
  }

  function brief(kind, desc) {
    var real = canonical(kind, desc);
    var a = archFor(real);
    var name = titleFor(real, desc);
    return [
      name + " · blueprint",
      "",
      "state: " + a.state,
      "",
      "data flow: " + a.flow,
      "",
      "modules:",
    ].concat(a.modules.map(function (m) { return "  - " + m; }))
      .concat(["", "build order:"])
      .concat(a.steps.map(function (s, i) { return "  " + (i + 1) + ". " + s; }))
      .concat(["", "files:", "  " + a.files.join("\n  "), "", "extend: " + a.extend])
      .join("\n");
  }

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
    [/rpg|role[\s-]*playing/i, "rpg"],
    [/platformer|jump/i, "platformer"],
    [/snake/i, "snake"],
    [/breakout|brick/i, "breakout"],
    [/pong/i, "pong"],
    [/2048/i, "2048"],
    [/minesweeper|mine/i, "minesweeper"],
    [/tetris|block/i, "tetris"],
    [/maze|labyrinth/i, "maze"],
    [/adventure|story|text game/i, "adventure"],
    [/typing|wpm/i, "typing"],
    [/game|guess/i, "game"],
    [/social|feed|twitter|mastodon/i, "social"],
    [/forum|discussion|thread/i, "forum"],
    [/blog|journal/i, "blog"],
    [/chat|messenger/i, "chat"],
    [/landing|website|web page|site|page/i, "landing"],
    [/function|algorithm|module|library/i, "playground"],
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
    welcome: welcome,
    rpg: rpg,
    platformer: platformer,
    snake: snake,
    breakout: breakout,
    pong: pong,
    "2048": game2048,
    minesweeper: minesweeper,
    tetris: tetris,
    maze: maze,
    adventure: adventure,
    typing: typing,
    social: social,
    blog: blog,
    forum: forum,
    chat: chatSite
  };

  var TITLES = {
    calculator: "Calculator", todo: "Todo list", timer: "Countdown timer",
    pomodoro: "Pomodoro", stopwatch: "Stopwatch", notes: "Notes",
    tictactoe: "Tic tac toe", memory: "Memory game", converter: "Unit converter",
    chart: "Bar chart", dashboard: "Metrics dashboard", landing: "Landing page",
    markdown: "Markdown editor", expenses: "Expense tracker", clock: "Clock",
    game: "Number guessing game", playground: "Program playground", welcome: "Preview ready",
    rpg: "Verdant Wood RPG", platformer: "Platformer", snake: "Snake",
    breakout: "Breakout", pong: "Pong", "2048": "2048", minesweeper: "Minesweeper",
    tetris: "Tetris", maze: "Maze", adventure: "Hollow Archive",
    typing: "Typing test", social: "Tiny social feed", blog: "Journal",
    forum: "Forum", chat: "Chat"
  };

  function wants3d(desc) {
    return /\b3d\b|three[\s-]?d|isometric|perspective|voxel/i.test(String(desc || ""));
  }

  var GAME3D = {
    tetris: 1, snake: 1, breakout: 1, pong: 1, maze: 1, platformer: 1,
    minesweeper: 1, "2048": 1, game: 1
  };

  var THREE_D_CSS = "body{perspective:1500px}main,.wrap{transform-style:preserve-3d}" +
    ".card canvas{transform:rotateX(9deg) rotateY(-7deg);box-shadow:0 28px 60px rgba(0,0,0,.55);border-radius:14px}" +
    "@media(max-width:560px){.card canvas{transform:perspective(900px) rotateX(5deg) rotateY(-2deg) scale(.985)}}";

  function slugOf(s) {
    return String(s || "project").toLowerCase().replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "").slice(0, 40) || "project";
  }

  function titleFor(real, desc) {
    if (real === "rpg") {
      var th = rpgTheme(desc);
      if (th) return th.title;
    }
    if (wants3d(desc) && GAME3D[real]) return (TITLES[real] || "Game") + " 3D";
    if (real === "playground" && desc) return String(desc).slice(0, 60);
    return TITLES[real] || "Built page";
  }

  function build(kind, desc, opts) {
    opts = opts || {};
    var real = canonical(kind, desc);
    var fn = BUILDERS[real] || BUILDERS.playground;
    var d3 = wants3d(desc);
    var html = fn(String(desc || ""), {
      theme: opts.theme === "light" ? "light" : "dark",
      d3: d3,
      variant: rpgTheme(desc) ? "themed-rpg" : (d3 ? "3d" : ""),
    });
    if (d3 && GAME3D[real] && real !== "tetris") {
      html = html.replace("</style>", THREE_D_CSS + "</style>");
    }
    return html;
  }

  function title(kind, desc) {
    return titleFor(canonical(kind, desc), desc);
  }

  /* ------------------------------------------------------ multi-file build -- */
  /* Turn the bundled single-file page into a tiny real project: markup, styles,
   * script, and two documents that explain the architecture. The preview keeps
   * using the bundled page, so nothing depends on file:// fetch(). */
  function project(kind, desc, opts) {
    opts = opts || {};
    var real = canonical(kind, desc);
    var name = titleFor(real, desc);
    var html = build(real, desc, opts);
    var css = "", js = "";
    html = html.replace(/<style>([\s\S]*?)<\/style>/, function (_, inner) {
      css = inner.trim() + "\n";
      return '<link rel="stylesheet" href="styles.css">';
    });
    html = html.replace(/<script>([\s\S]*?)<\/script>/, function (_, inner) {
      js = inner.trim() + "\n";
      return '<script src="app.js"></script>';
    });
    html = html.replace(/offline · self-contained/, "offline · separate files");
    var a = archFor(real);
    var slug = real === "playground" ? "app" : real;
    if (real === "rpg" && rpgTheme(desc)) slug = slugOf(rpgTheme(desc).title);
    else if (wants3d(desc) && GAME3D[real]) slug = slugOf(real + "-3d");
    var readme = [
      "# " + name,
      "",
      "A small, self-contained " + (a.files ? "project" : "app") + " built by toolrx.",
      "No build step, no dependencies, no network. Open `index.html`.",
      "",
      "## Files",
      "",
      "| file | role |",
      "| --- | --- |",
      "| `index.html` | markup and the page shell |",
      "| `styles.css` | all presentation, including the responsive rules |",
      "| `app.js` | state, render, and event handlers |",
      "| `ARCHITECTURE.md` | the shape of the program and how to extend it |",
      "",
      "## Run",
      "",
      "```sh",
      "python3 -m http.server 8000",
      "# open http://localhost:8000",
      "```",
      "",
      "Or just double-click `index.html`. Everything runs in the browser.",
      "",
      "## How it works",
      "",
      "- state: " + a.state,
      "- flow: " + a.flow,
      "- modules: " + a.modules.join("; "),
      "",
      "## Next steps",
      "",
      a.steps.map(function (s, i) { return (i + 1) + ". " + s; }).join("\n"),
      "",
      "Then: " + a.extend + ".",
      "",
      "---",
      "",
      "Generated deterministically by toolrx · the same request produces the same files.",
      ""
    ].join("\n");
    var arch = [
      "# Architecture · " + name,
      "",
      "## State",
      "",
      a.state,
      "",
      "## Modules",
      "",
      a.modules.map(function (m) { return "- " + m; }).join("\n"),
      "",
      "## Data flow",
      "",
      a.flow,
      "",
      "## Files",
      "",
      a.files.map(function (f) { return "- `" + f + "`"; }).join("\n"),
      "",
      "## Build order",
      "",
      a.steps.map(function (s, i) { return (i + 1) + ". " + s; }).join("\n"),
      "",
      "## Extension points",
      "",
      a.extend + ".",
      "",
      "Keep state in one place. Render from state only. Give every action one",
      "handler. That is enough to grow this into something much larger.",
      ""
    ].join("\n");
    return {
      kind: real,
      slug: slug,
      title: name,
      html: html,
      files: {
        "index.html": html,
        "styles.css": css || "/* no extra styles */\n",
        "app.js": js || "/* no extra script */\n",
        "README.md": readme,
        "ARCHITECTURE.md": arch
      }
    };
  }

  root.toolrxTemplates = {
    build: build,
    title: title,
    canonical: canonical,
    project: project,
    architecture: architecture,
    blueprint: blueprint,
    brief: brief,
    kinds: Object.keys(BUILDERS)
  };
})(typeof self !== "undefined" ? self : this);

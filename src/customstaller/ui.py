"""The installer window: one HTML shell, styled entirely from the theme tokens."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .themes import css_variables

SHELL = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
__VARS__
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font:15px/1.6 var(--font);background:var(--bg);color:var(--text);overflow:hidden;-webkit-font-smoothing:antialiased}
button,input{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}

/* ---- frame ---------------------------------------------------------- */
.window{height:100vh;display:grid;grid-template-columns:264px minmax(0,1fr)}
.rail{display:flex;flex-direction:column;gap:32px;padding:28px 20px 20px;background:var(--surface);border-right:1px solid var(--border)}
.stage{display:flex;flex-direction:column;min-width:0;min-height:0}

/* ---- brand ---------------------------------------------------------- */
.brand{display:flex;align-items:center;gap:12px;padding:0 8px}
.brand .logo,.brand .mono{width:44px;height:44px;flex:none;border-radius:var(--r-control)}
.brand .logo{object-fit:cover}
.brand .mono{display:grid;place-items:center;background:var(--accent);color:var(--accent-text);font-size:1.4rem;font-weight:800;line-height:1}
.brand b{display:block;font-size:1.05rem;line-height:1.25;letter-spacing:-.01em;overflow-wrap:anywhere}
.brand small{color:var(--muted);font-size:.8rem}

/* ---- steps: a real sequence, drawn as a line that fills as you go ----- */
.steps{list-style:none;flex:1}
.steps li{position:relative;height:44px}
.steps li:not(:last-child)::after{content:"";position:absolute;left:23px;top:36px;width:2px;height:16px;background:var(--border);transition:background var(--t-page)}
.steps li.done::after{background:var(--accent)}
.step{display:flex;align-items:center;gap:12px;width:100%;height:44px;padding:0 10px;border:0;border-radius:var(--r-control);background:none;color:var(--muted);text-align:left;cursor:pointer;transition:background var(--t-fast),color var(--t-fast)}
.step:hover:not(:disabled){background:var(--surface-alt);color:var(--text)}
.step:disabled{cursor:default}
.step[aria-current=step]{color:var(--text);font-weight:600;background:var(--surface-alt)}
.dot{display:grid;place-items:center;width:28px;height:28px;flex:none;border-radius:999px;border:2px solid var(--border);background:var(--surface);font-size:.78rem;font-weight:700;transition:background var(--t-page),border-color var(--t-page),color var(--t-page)}
.step.done .dot{background:var(--accent);border-color:var(--accent);color:var(--accent-text)}
.step[aria-current=step] .dot{border-color:var(--accent);color:var(--text)}
.step[aria-current=step].done .dot{color:var(--accent-text)}
.rail-foot{color:var(--muted);font-size:.78rem;padding:0 8px}
body[data-branding=off] .rail-foot{display:none}

/* ---- page ----------------------------------------------------------- */
.page{flex:1;min-height:0;overflow:auto;padding:44px 56px 20px}
.page-inner{max-width:680px}
.page-inner.enter{animation:fade var(--t-page) ease-out}
@keyframes fade{from{opacity:0}to{opacity:1}}
.bar{display:flex;align-items:center;justify-content:flex-end;gap:10px;padding:16px 56px 24px;border-top:1px solid var(--border)}

/* ---- building blocks for tab authors --------------------------------- */
h1{font-size:2.5rem;line-height:1.1;font-weight:700;letter-spacing:-.03em;margin-bottom:14px;overflow-wrap:anywhere}
h2{font-size:1.25rem;line-height:1.3;font-weight:650;letter-spacing:-.01em;margin:28px 0 8px}
p{max-width:62ch;margin-bottom:14px}
.lead{color:var(--muted);font-size:1.1rem;margin-bottom:20px}
.muted{color:var(--muted)}
a{color:var(--accent)}
code{font:.88em var(--mono);background:var(--surface-alt);padding:2px 7px;border-radius:calc(var(--r-control) / 2 + 2px);overflow-wrap:anywhere}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);padding:20px 22px;margin:16px 0}
.row{display:flex;align-items:center;gap:12px;margin-top:14px}
.spacer{flex:1}
.stack>*+*{margin-top:12px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;background:var(--surface-alt);color:var(--muted);font-size:.8rem}
.field{display:block;margin:24px 0}
.field>span{display:block;margin-bottom:8px;color:var(--muted);font-size:.86rem}
input[type=text],input[type=password],input[type=number],select,textarea{width:100%;padding:12px 14px;background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:var(--r-control)}
input[type=text]:focus,input[type=password]:focus,input[type=number]:focus,select:focus,textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 28%,transparent)}
.check{display:flex;align-items:center;gap:10px;margin-top:18px;cursor:pointer}
.check input{width:18px;height:18px;accent-color:var(--accent)}
pre.scroll{max-height:300px;overflow:auto;padding:16px 18px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r-card);font:.82rem/1.55 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere}
.error{padding:12px 16px;border-left:3px solid var(--danger);background:var(--surface);border-radius:var(--r-control);color:var(--text)}
.bad{color:var(--danger)}

.btn{min-width:96px;padding:11px 22px;border:1px solid transparent;border-radius:var(--r-button);background:none;font-weight:600;cursor:pointer;transition:filter var(--t-fast),background var(--t-fast),border-color var(--t-fast)}
.btn.primary{background:var(--accent);color:var(--accent-text)}
.btn.primary:hover:not(:disabled){filter:brightness(1.1)}
.btn.ghost,.btn:not(.primary){border-color:var(--border)}
.btn.ghost:hover:not(:disabled),.btn:not(.primary):hover:not(:disabled){background:var(--surface-alt)}
.btn:disabled{opacity:.38;cursor:not-allowed}

.console{height:clamp(160px,38vh,300px);overflow:auto;padding:14px 16px;background:var(--console);border:1px solid var(--border);border-radius:var(--r-card);font:.83rem/1.55 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere}
.console .err{color:var(--danger)}
.progress{height:6px;margin-top:16px;border-radius:999px;background:var(--surface-alt);overflow:hidden}
#cs-bar{height:100%;width:0;border-radius:999px;background:linear-gradient(90deg,var(--accent2),var(--accent));transition:width var(--t-page) ease-out}

.bye{height:100vh;display:grid;place-content:center;text-align:center;gap:6px}
.bye h1{font-size:1.8rem;margin:0}

/* ---- top layout (config: layout = "top") and small windows -------------- */
body[data-layout=top] .window{grid-template-columns:minmax(0,1fr);grid-template-rows:auto minmax(0,1fr)}
body[data-layout=top] .rail{flex-direction:row;align-items:center;gap:20px;padding:14px 48px;border-right:0;border-bottom:1px solid var(--border)}
body[data-layout=top] .steps{display:flex;gap:0;flex-wrap:wrap}
body[data-layout=top] .steps li{height:auto}
body[data-layout=top] .steps li::after{display:none}
body[data-layout=top] .step{height:40px;width:auto;gap:8px;padding:0 10px 0 8px}
body[data-layout=top] .rail-foot{display:none}
@media (max-width:760px){
  .window{grid-template-columns:minmax(0,1fr);grid-template-rows:auto minmax(0,1fr)}
  .rail{flex-direction:row;align-items:center;gap:16px;padding:12px 16px;border-right:0;border-bottom:1px solid var(--border)}
  .steps{display:flex;gap:4px}
  .steps li{height:auto}
  .steps li::after{display:none}
  .step{height:40px;width:auto;padding:0 8px}
  .step:not([aria-current=step]) span:last-child{display:none}
  .rail-foot,.brand small{display:none}
  .page{padding:32px 24px 16px}
  .bar{padding:14px 24px 20px}
  h1{font-size:2rem}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>
</head>
<body data-layout="__LAYOUT__" data-branding="__BRANDING__">
<div class="window">
  <aside class="rail">
    <div class="brand">__BRAND__<div><b>__NAME__</b><small>Version __VERSION__</small></div></div>
    <ol class="steps" id="steps" aria-label="Setup steps"></ol>
    <div class="rail-foot">Powered by Customstaller</div>
  </aside>
  <main class="stage">
    <div class="page" id="page"><div class="page-inner" id="inner"></div></div>
    <footer class="bar">
      <button class="btn ghost" id="back" type="button">Back</button>
      <button class="btn primary" id="next" type="button">Next</button>
    </footer>
  </main>
</div>
<script>
(() => {
  const TOKEN = "__TOKEN__";
  const TABS = __TABS__;
  const $ = (s) => document.querySelector(s);
  const inner = $("#inner"), page = $("#page"), stepsEl = $("#steps");
  const backBtn = $("#back"), nextBtn = $("#next");
  const st = {index: -1, current: null, can: true, running: false, finished: false, cursor: 0, seq: 0};

  async function api(path, body) {
    const opt = {headers: {"X-CS-Token": TOKEN}};
    if (body !== undefined) {
      opt.method = "POST";
      opt.headers["Content-Type"] = "application/json";
      opt.body = JSON.stringify(body);
    }
    const res = await fetch(path, opt);
    if (!res.ok) throw new Error(path + " returned " + res.status);
    return res.json();
  }

  function renderNav() {
    stepsEl.innerHTML = "";
    TABS.forEach((t, i) => {
      const li = document.createElement("li");
      if (i < st.index) li.className = "done";
      const b = document.createElement("button");
      b.type = "button";
      b.className = "step" + (i < st.index ? " done" : "");
      if (i === st.index) b.setAttribute("aria-current", "step");
      b.disabled = st.running || i > st.index;
      const dot = document.createElement("span");
      dot.className = "dot";
      dot.textContent = i < st.index ? "\u2713" : (t.icon || String(i + 1));
      const label = document.createElement("span");
      label.textContent = t.title;
      b.append(dot, label);
      b.onclick = () => go(i);
      li.append(b);
      stepsEl.append(li);
    });
    const last = st.index === TABS.length - 1;
    backBtn.disabled = st.running || st.index <= 0;
    nextBtn.textContent = last ? "Close" : "Next";
    nextBtn.disabled = st.running || !st.can;
  }

  function show(html) {
    inner.innerHTML = html;
    inner.classList.remove("enter");
    void inner.offsetWidth;
    inner.classList.add("enter");
  }

  async function go(i) {
    if (i < 0 || i >= TABS.length) return;
    let res;
    try {
      res = await api("/api/enter", {id: TABS[i].id, from: st.current});
    } catch (e) {
      show('<div class="error">This page could not be loaded. Close setup and try again.</div>');
      return;
    }
    if (res.denied) return;
    st.index = i;
    st.current = TABS[i].id;
    st.can = res.canContinue;
    show(res.html);
    page.scrollTop = 0;
    renderNav();
    if ($("#cs-log")) {
      st.cursor = 0;
      await syncConsole();
      if (res.autoRun && !st.finished && !st.running) run();
    }
  }

  async function syncConsole() {
    const my = ++st.seq;
    const d = await api("/api/log?since=" + st.cursor);
    if (my !== st.seq) return;
    const logEl = $("#cs-log");
    if (!logEl) return;
    for (const line of d.lines) {
      const div = document.createElement("div");
      div.textContent = line;
      if (line.startsWith("Error:")) div.className = "err";
      logEl.append(div);
    }
    if (d.lines.length) logEl.scrollTop = logEl.scrollHeight;
    st.cursor = d.next;
    st.running = d.running;
    st.finished = d.finished;
    const bar = $("#cs-bar");
    if (bar) bar.style.width = Math.round(d.progress * 100) + "%";
    const btn = $("#cs-run"), status = $("#cs-status");
    if (btn) {
      btn.disabled = d.running || d.finished;
      btn.textContent = d.error ? "Try again" : d.finished ? "Done" : (btn.dataset.label || "Install");
    }
    if (status) {
      status.className = d.error ? "bad" : "muted";
      status.textContent = d.running ? "Working\u2026" : d.finished ? "Finished." : d.error ? d.error : "Ready.";
    }
    const c = await api("/api/can", {id: st.current});
    if (my !== st.seq) return;
    st.can = c.canContinue;
    renderNav();
    if (d.running) setTimeout(syncConsole, 250);
  }

  async function run() {
    const logEl = $("#cs-log");
    if (logEl) logEl.textContent = "";
    st.cursor = 0;
    st.running = true;
    renderNav();
    const btn = $("#cs-run");
    if (btn) btn.disabled = true;
    try {
      await api("/api/run", {id: st.current});
    } finally {
      await syncConsole();
    }
  }

  async function close() {
    try { await api("/api/close", {}); } catch (e) {}
    document.body.innerHTML = '<div class="bye"><h1>Setup is complete</h1><p class="muted">You can close this window.</p></div>';
    try { window.close(); } catch (e) {}
  }

  window.cs = {
    async set(key, value) {
      const r = await api("/api/set", {id: st.current, key, value});
      st.can = r.canContinue;
      renderNav();
      return r;
    },
    async call(method, ...args) {
      const r = await api("/api/call", {id: st.current, method, args});
      if (r.error) throw new Error(r.error);
      return r.result;
    },
    async refresh() {
      const r = await api("/api/render", {id: st.current});
      inner.innerHTML = r.html;
      st.can = r.canContinue;
      renderNav();
    },
    next: () => nextBtn.click(),
    back: () => backBtn.click(),
    run, close,
  };

  backBtn.onclick = () => go(st.index - 1);
  nextBtn.onclick = () => (st.index === TABS.length - 1 ? close() : go(st.index + 1));
  setInterval(() => api("/api/ping", {}).catch(() => {}), 5000);

  if (TABS.length) go(0);
  else show('<h1>No tabs yet</h1><p class="lead">Run <code>customstaller tab</code> to add some.</p>');
})();
</script>
</body>
</html>
"""


def _json_for_script(value: Any) -> str:
    """JSON that is safe to embed inside a <script> tag."""
    return (
        json.dumps(value)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_shell(
    *,
    app: dict[str, Any],
    style: dict[str, Any],
    custom_theme: dict[str, Any] | None,
    tabs: list[dict[str, str]],
    token: str,
    project_root: Path,
) -> str:
    name = str(app.get("name") or "Setup")
    logo = str(app.get("logo") or "").strip()
    logo_path = (project_root / "assets" / logo) if logo else None
    if logo_path and logo_path.is_file():
        brand = f'<img class="logo" src="/assets/{html.escape(logo, quote=True)}" alt="">'
    else:
        initial = html.escape(name.strip()[:1].upper() or "S")
        brand = f'<span class="mono" aria-hidden="true">{initial}</span>'

    layout = "top" if style.get("layout") == "top" else "sidebar"
    replacements = {
        "__TITLE__": html.escape(f"{name} Setup"),
        "__VARS__": css_variables(style, custom_theme),
        "__LAYOUT__": layout,
        "__BRANDING__": "on" if style.get("branding", True) else "off",
        "__BRAND__": brand,
        "__NAME__": html.escape(name),
        "__VERSION__": html.escape(str(app.get("version", ""))),
        "__TOKEN__": token,
        "__TABS__": _json_for_script(tabs),
    }
    out = SHELL
    for key, value in replacements.items():
        out = out.replace(key, value)
    return out

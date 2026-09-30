"""Página única del dashboard (HTML + CSS + JS en línea, sin recursos externos).

Todo texto que viene de los datos se inserta con `textContent` (nunca `innerHTML`).
"""

PAGE = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>bot-eve · Panel</title>
<style nonce="__NONCE__">
:root{
  color-scheme: light;
  --surface-1:#fcfcfb; --surface-2:#f3f2ef; --border:#dcdbd6;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#75746f;
  --series-1:#2a78d6; --grid:#e6e5e0;
  --good:#0ca30c; --warning:#fab219; --serious:#ec835a; --critical:#d03b3b;
}
@media (prefers-color-scheme: dark){
  :root{
    color-scheme: dark;
    --surface-1:#1a1a19; --surface-2:#242423; --border:#383835;
    --text-primary:#ffffff; --text-secondary:#c3c2b7; --text-muted:#9a998f;
    --series-1:#3987e5; --grid:#2e2e2c;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--surface-1);color:var(--text-primary);
  font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}
header.top{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;margin-bottom:12px}
h1{font-size:20px;margin:0}
.muted{color:var(--text-muted)} .sec{color:var(--text-secondary)}
.card{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:16px}
.card h2{font-size:17px;margin:0;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.small{font-size:13px;font-weight:400}
.badge{font-size:12px;font-weight:600;padding:2px 8px;border-radius:999px;border:1px solid var(--border);
  background:var(--surface-1);color:var(--text-primary)}
.badge.real{border-color:var(--critical);color:var(--critical)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:4px;background:var(--text-muted)}
.dot.on{background:var(--good)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:14px 0}
.kpi{background:var(--surface-1);border:1px solid var(--border);border-radius:8px;padding:8px 10px}
.kpi .l{font-size:12px;color:var(--text-secondary)} .kpi .v{font-size:19px;font-weight:600;margin-top:2px}
.alerts{display:grid;gap:6px;margin-top:10px}
.alert{border-left:4px solid var(--border);background:var(--surface-1);padding:6px 10px;border-radius:4px}
.alert.warning{border-color:var(--warning)} .alert.critical{border-color:var(--critical)}
.alert b{margin-right:6px}
h3{font-size:14px;margin:16px 0 6px;color:var(--text-secondary);font-weight:600}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:5px 8px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}
th:first-child,td:first-child{text-align:left} th{color:var(--text-secondary);font-weight:500}
.scroll{overflow-x:auto}
.chart{position:relative}
.chart svg{width:100%;height:auto;display:block;touch-action:none}
.axis{fill:var(--text-muted);font-size:11px}
.tip{position:absolute;pointer-events:none;background:var(--surface-1);border:1px solid var(--border);
  border-radius:6px;padding:6px 8px;font-size:12px;box-shadow:0 2px 8px rgba(0,0,0,.18);display:none;z-index:2}
.tip .tv{font-weight:700;font-size:14px}
.tip .key{display:inline-block;width:14px;height:0;border-top:2px solid var(--series-1);vertical-align:middle;margin-right:5px}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;align-items:center}
button{font:inherit;padding:6px 12px;border-radius:6px;border:1px solid var(--border);
  background:var(--surface-1);color:var(--text-primary);cursor:pointer}
button.danger{border-color:var(--critical);color:var(--critical);font-weight:600}
button:disabled{opacity:.45;cursor:not-allowed}
details{margin-top:8px} summary{cursor:pointer;color:var(--text-secondary)}
#msg{position:sticky;bottom:8px;margin-top:8px}
</style>
</head>
<body>
<main>
  <header class="top">
    <h1>bot-eve · Panel</h1>
    <span class="muted" id="stamp">cargando…</span>
  </header>
  <div id="bots"></div>
  <div id="msg" class="alert" hidden></div>
</main>
<script nonce="__NONCE__">
"use strict";
const fmtNum = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v)) ? "—"
  : Number(v).toLocaleString("es", {minimumFractionDigits: d, maximumFractionDigits: d});
const signed = (v, d = 2) => (v === null || v === undefined) ? "—" : (v > 0 ? "▲ +" : v < 0 ? "▼ " : "") + fmtNum(v, d);
const pct = (v, d = 2) => (v === null || v === undefined) ? "—" : (v > 0 ? "+" : "") + fmtNum(v * 100, d) + " %";
const since = s => s === null ? "—" : s < 90 ? Math.round(s) + " s" : s < 5400 ? Math.round(s / 60) + " min" : (s / 3600).toFixed(1) + " h";

// Construye DOM con textContent: los datos nunca se interpretan como HTML.
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (typeof v === "function" && k.startsWith("on")) el.addEventListener(k.slice(2), v);  // sin atributos onclick (CSP)
    else if (v !== false && v != null) el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) { if (kid == null) continue; el.append(kid.nodeType ? kid : document.createTextNode(String(kid))); }
  return el;
}
const svg = (tag, attrs) => { const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v); return el; };

let token = sessionStorage.getItem("dash_token") || "";
const cache = {};

function kpi(label, value) { return h("div", {class: "kpi"}, h("div", {class: "l"}, label), h("div", {class: "v"}, value)); }
function alertBox(level, icon, text) { return h("div", {class: "alert " + level, role: "status"}, h("b", null, icon), text); }

function table(cols, rows) {
  return h("div", {class: "scroll"}, h("table", null,
    h("thead", null, h("tr", null, cols.map(c => h("th", null, c)))),
    h("tbody", null, rows.map(r => h("tr", null, r.map(c => h("td", null, c)))))));
}

function niceTicks(lo, hi, n) {  // marcas «redondas» (1, 2, 5 × 10^k) que cubren [lo, hi]
  const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), norm = raw / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag, out = [];
  for (let v = Math.floor(lo / step) * step; ; v += step) { out.push(+v.toFixed(10)); if (v >= hi - 1e-9) break; }
  return out;
}

function lineChart(curve) {
  const W = 720, H = 220, P = {l: 56, r: 14, t: 10, b: 24};
  const box = h("div", {class: "chart"});
  if (curve.length < 2) {
    box.append(h("p", {class: "muted"}, curve.length ? "Una operación cerrada: la curva aparece con la segunda." : "Sin operaciones cerradas todavía."));
    return box;
  }
  const xs = curve.map(p => new Date(p.t).getTime()), ys = curve.map(p => p.cum_pnl);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let lo = Math.min(0, ...ys), hi = Math.max(0, ...ys); if (hi === lo) { hi += 1; lo -= 1; }
  const ticks = niceTicks(lo, hi, 4); lo = ticks[0]; hi = ticks[ticks.length - 1];
  const X = t => P.l + (W - P.l - P.r) * ((t - x0) / ((x1 - x0) || 1));
  const Y = v => P.t + (H - P.t - P.b) * (1 - (v - lo) / (hi - lo));
  const s = svg("svg", {viewBox: `0 0 ${W} ${H}`, role: "img", tabindex: "0",
    "aria-label": "P&L realizado acumulado. Usa las flechas para recorrer los puntos."});
  for (const v of ticks) {
    s.append(svg("line", {x1: P.l, x2: W - P.r, y1: Y(v), y2: Y(v), stroke: "var(--grid)", "stroke-width": 1}));
    const t = svg("text", {x: P.l - 6, y: Y(v) + 4, "text-anchor": "end", class: "axis"}); t.textContent = fmtNum(v, 0); s.append(t);
  }
  s.append(svg("line", {x1: P.l, x2: W - P.r, y1: Y(0), y2: Y(0), stroke: "var(--text-muted)", "stroke-width": 1, "stroke-dasharray": "4 3"}));
  [x0, x1].forEach((t, i) => { const tx = svg("text", {x: X(t), y: H - 6, "text-anchor": i ? "end" : "start", class: "axis"});
    tx.textContent = new Date(t).toLocaleDateString("es", {day: "2-digit", month: "short"}); s.append(tx); });
  s.append(svg("polyline", {fill: "none", stroke: "var(--series-1)", "stroke-width": 2, "stroke-linejoin": "round",
    points: curve.map((p, i) => `${X(xs[i])},${Y(ys[i])}`).join(" ")}));
  const last = curve.length - 1;
  s.append(svg("circle", {cx: X(xs[last]), cy: Y(ys[last]), r: 4.5, fill: "var(--series-1)", stroke: "var(--surface-2)", "stroke-width": 2}));
  const cross = svg("line", {y1: P.t, y2: H - P.b, stroke: "var(--text-secondary)", "stroke-width": 1, visibility: "hidden"});
  const dot = svg("circle", {r: 4.5, fill: "var(--series-1)", stroke: "var(--surface-2)", "stroke-width": 2, visibility: "hidden"});
  const tip = h("div", {class: "tip"}); s.append(cross, dot); box.append(s, tip);
  function show(i) {
    const px = X(xs[i]), py = Y(ys[i]);
    cross.setAttribute("x1", px); cross.setAttribute("x2", px); cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", px); dot.setAttribute("cy", py); dot.setAttribute("visibility", "visible");
    tip.replaceChildren(h("div", {class: "tv"}, h("span", {class: "key"}), signed(ys[i])),
      h("div", {class: "muted"}, new Date(xs[i]).toLocaleString("es")), h("div", {class: "muted"}, "operación " + (i + 1) + " de " + curve.length));
    tip.style.display = "block";
    const r = s.getBoundingClientRect(), k = r.width / W;
    tip.style.left = Math.min(Math.max(px * k + 10, 0), r.width - 150) + "px"; tip.style.top = Math.max(py * k - 54, 0) + "px";
  }
  const hide = () => { cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); tip.style.display = "none"; };
  let cur = last;
  s.addEventListener("pointermove", e => { const r = s.getBoundingClientRect(), px = (e.clientX - r.left) * (W / r.width);
    let best = 0; xs.forEach((t, i) => { if (Math.abs(X(t) - px) < Math.abs(X(xs[best]) - px)) best = i; }); cur = best; show(best); });
  s.addEventListener("pointerleave", hide); s.addEventListener("blur", hide);
  s.addEventListener("keydown", e => { if (e.key === "ArrowLeft") cur = Math.max(0, cur - 1); else if (e.key === "ArrowRight") cur = Math.min(last, cur + 1); else return; e.preventDefault(); show(cur); });
  return box;
}

async function act(i, what, name) {
  if (!confirm(what === "kill" ? `¿Parada de emergencia de «${name}»?\nCerrará sus posiciones abiertas y detendrá el bot.` : `¿Retirar el KILL de «${name}»?`)) return;
  const t = prompt("Token del panel (DASHBOARD_TOKEN):", token); if (!t) return; token = t; sessionStorage.setItem("dash_token", t);
  const r = await fetch(`/api/bots/${i}/${what}`, {method: "POST", headers: {"X-Dashboard-Token": t}});
  const body = await r.json().catch(() => ({}));
  const m = document.getElementById("msg"); m.hidden = false; m.className = "alert " + (r.ok ? "warning" : "critical");
  m.replaceChildren(h("b", null, r.ok ? "✔" : "✖"), body.message || body.detail || ("Error " + r.status)); load();
}

function botCard(b, td, enabled) {
  const st = b.status, stats = b.stats, pos = (st && st.positions) || [];
  const card = h("section", {class: "card"});
  const real = st && st.real_money;
  card.append(h("h2", null, b.name,
    st ? h("span", {class: "badge" + (real ? " real" : "")}, real ? "⚠ DINERO REAL" : "DEMO") : null,
    h("span", {class: "sec small"}, h("span", {class: "dot" + (b.online ? " on" : "")}), b.online ? "en línea" : "sin señal",
      st ? ` · actualizado hace ${since(b.age_seconds)}` : "")));
  const al = h("div", {class: "alerts"});
  if (!st) al.append(alertBox("warning", "⚠", "Sin datos todavía: el bot no se ha iniciado o escribe en otra carpeta."));
  else if (!b.online) al.append(alertBox("warning", "⚠", `El bot no da señales desde hace ${since(b.age_seconds)}. Revisa que siga en ejecución (los stops del exchange siguen activos).`));
  if (b.kill_file || (st && st.kill_active)) al.append(alertBox("critical", "⛔", "KILL activo: el bot cerrará las posiciones y se detendrá."));
  pos.filter(p => !p.protected).forEach(p => al.append(alertBox("critical", "🚨", `Posición sin stop: ${p.symbol}. Revísala a mano.`)));
  if (st && st.consecutive_errors > 0) al.append(alertBox("warning", "⚠", `${st.consecutive_errors} errores seguidos de conexión con el broker.`));
  card.append(al);
  card.append(h("div", {class: "kpis"},
    kpi("Capital", st ? fmtNum(st.equity) : "—"), kpi("P&L de hoy", st ? pct(st.day_pnl_pct) : "—"),
    kpi("Posiciones abiertas", pos.length), kpi("Operaciones cerradas", stats.trades),
    kpi("Tasa de aciertos", stats.win_rate === null ? "—" : fmtNum(stats.win_rate * 100, 0) + " %"),
    kpi("Factor de beneficio", stats.no_losses ? "∞ (sin pérdidas)" : stats.profit_factor === null ? "—" : fmtNum(stats.profit_factor)),
    kpi("P&L realizado", signed(stats.total_pnl))));
  card.append(h("h3", null, "Posiciones abiertas"));
  card.append(pos.length ? table(["Símbolo", "Cantidad", "Entrada", "Actual", "P&L", "P&L %", "Stop", "Objetivo"],
    pos.map(p => [p.symbol, fmtNum(p.qty, 6), fmtNum(p.entry_price), fmtNum(p.price), signed(p.unrealized_pnl), pct(p.unrealized_pct),
      p.protected ? fmtNum(p.stop_price) : "✖ sin stop", p.target_price ? fmtNum(p.target_price) : "—"]))
    : h("p", {class: "muted"}, "Ninguna. La estrategia opera en velas de 4 h y entra pocas veces al mes."));
  card.append(h("h3", null, "P&L realizado acumulado"));
  const curve = (td && td.curve) || [];
  card.append(lineChart(curve));
  if (curve.length) card.append(h("details", null, h("summary", null, "Ver los datos de la curva como tabla"),
    table(["Fecha", "P&L acumulado"], curve.map(p => [new Date(p.t).toLocaleString("es"), signed(p.cum_pnl)]))));
  card.append(h("h3", null, "Últimas operaciones"));
  const tr = (td && td.trades) || [];
  card.append(tr.length ? table(["Cierre", "Símbolo", "Motivo", "Entrada", "Salida", "P&L", "Retorno"],
    tr.slice(0, 15).map(t => [new Date(t.exit_time).toLocaleString("es"), t.symbol, t.reason, fmtNum(t.entry_price), fmtNum(t.exit_price), signed(t.pnl), pct(t.return_pct)]))
    : h("p", {class: "muted"}, "Todavía no hay operaciones cerradas."));
  card.append(h("div", {class: "actions"},
    h("button", {class: "danger", disabled: !enabled, title: enabled ? "" : "Define DASHBOARD_TOKEN en .env para activar las acciones", onclick: () => act(b.index, "kill", b.name)}, "Parada de emergencia"),
    h("button", {disabled: !enabled, onclick: () => act(b.index, "unkill", b.name)}, "Retirar KILL"),
    enabled ? null : h("span", {class: "muted"}, "Acciones desactivadas: falta DASHBOARD_TOKEN en .env")));
  return card;
}

async function load() {
  try {
    const ov = await (await fetch("/api/overview", {cache: "no-store"})).json();
    await Promise.all(ov.bots.map(async b => { cache[b.index] = await (await fetch(`/api/bots/${b.index}/trades`, {cache: "no-store"})).json(); }));
    document.getElementById("bots").replaceChildren(...ov.bots.map(b => botCard(b, cache[b.index], ov.actions_enabled)));
    document.getElementById("stamp").textContent = "actualizado " + new Date().toLocaleTimeString("es");
  } catch (e) {
    document.getElementById("stamp").textContent = "⚠ no se pudo leer el panel";
  }
}
load(); setInterval(load, 10000);
</script>
</body>
</html>
"""

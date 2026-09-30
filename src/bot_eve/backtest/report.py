"""Informe HTML autocontenido (sin dependencias externas): métricas, equity y operaciones."""

from __future__ import annotations

import html
import math
from pathlib import Path

import pandas as pd

_METRIC_ROWS = [
    ("Retorno total", "total_return", "pct"),
    ("Buy & hold", "buy_and_hold_return", "pct"),
    ("Retorno anualizado", "cagr", "pct"),
    ("Sharpe (anualizado)", "sharpe", "num"),
    ("Máx. drawdown", "max_drawdown", "pct"),
    ("Máx. drawdown buy & hold", "buy_and_hold_max_drawdown", "pct"),
    ("Operaciones", "trades", "int"),
    ("Win rate", "win_rate", "pct"),
    ("Profit factor", "profit_factor", "num"),
    ("Retorno medio por operación", "avg_trade_return", "pct"),
    ("Comisiones pagadas", "total_fees", "money"),
    ("Exposición", "exposure", "pct"),
    ("Entradas rechazadas (min. notional/lote)", "rejected_entries", "int"),
    ("Capital inicial", "initial_cash", "money"),
    ("Capital final", "final_equity", "money"),
]


def _fmt(value: float, kind: str) -> str:
    if value is None or value != value:
        return "—"
    if value in (float("inf"), float("-inf")):
        return "∞"
    return {
        "pct": f"{value * 100:.2f}%",
        "num": f"{value:.2f}",
        "int": f"{int(value)}",
        "money": f"{value:,.2f}",
    }[kind]


def _svg_chart(series: dict[str, pd.Series], width: int = 900, height: int = 320) -> str:
    colors = ["#2563eb", "#9ca3af", "#16a34a"]
    pad = 40
    # Escala logarítmica: una curva que pierde 99% y otra que gana 1500% deben verse ambas.
    sampled = {k: _downsample(v.clip(lower=1e-9), 900) for k, v in series.items()}
    lo = math.log(min(s.min() for s in sampled.values()))
    hi = math.log(max(s.max() for s in sampled.values()))
    span = (hi - lo) or 1.0
    t0 = min(s.index[0] for s in sampled.values())
    t1 = max(s.index[-1] for s in sampled.values())
    tspan = (t1 - t0).total_seconds() or 1.0
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Curva de equity (escala logarítmica)">'
    ]
    for frac in (0, 0.25, 0.5, 0.75, 1):
        y = pad + (height - 2 * pad) * (1 - frac)
        parts.append(
            f'<line x1="{pad}" x2="{width - pad}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
        )
        parts.append(
            f'<text x="4" y="{y + 4:.1f}" class="axis">{math.exp(lo + span * frac):,.0f}</text>'
        )
    for n, (name, s) in enumerate(sampled.items()):
        pts = " ".join(
            f"{pad + (width - 2 * pad) * (t - t0).total_seconds() / tspan:.1f},"
            f"{pad + (height - 2 * pad) * (1 - (math.log(v) - lo) / span):.1f}"
            for t, v in s.items()
        )
        parts.append(
            f'<polyline fill="none" stroke="{colors[n % 3]}" stroke-width="1.6" points="{pts}"/>'
        )
        parts.append(
            f'<text x="{pad + 10 + n * 150}" y="16" class="axis" style="fill:{colors[n % 3]}">■ {html.escape(name)}</text>'
        )
    parts.append(f'<text x="{pad}" y="{height - 8}" class="axis">{t0:%Y-%m-%d}</text>')
    parts.append(
        f'<text x="{width - pad}" y="{height - 8}" text-anchor="end" class="axis">{t1:%Y-%m-%d}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _downsample(s: pd.Series, points: int) -> pd.Series:
    if len(s) <= points:
        return s
    step = len(s) // points + 1
    out = s.iloc[::step]
    return out if out.index[-1] == s.index[-1] else pd.concat([out, s.iloc[[-1]]])


def build_report(
    title: str,
    metrics: dict,
    equity: pd.Series,
    benchmark: pd.Series,
    trades: pd.DataFrame,
    params: dict | None = None,
    notes: list[str] | None = None,
    max_trades: int = 500,
) -> str:
    rows = "".join(
        f"<tr><th>{label}</th><td>{_fmt(metrics.get(key), kind)}</td></tr>"
        for label, key, kind in _METRIC_ROWS
    )
    t = trades.tail(max_trades).copy()
    for col in ("entry_time", "exit_time"):
        t[col] = t[col].dt.strftime("%Y-%m-%d %H:%M")
    for col in ("entry_price", "exit_price", "fees", "pnl"):
        t[col] = t[col].map(lambda v: f"{v:,.4f}")
    t["return_pct"] = t["return_pct"].map(lambda v: f"{v * 100:.2f}%")
    trade_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in r) + "</tr>"
        for r in t.itertuples(index=False)
    )
    head = "".join(f"<th>{html.escape(c)}</th>" for c in trades.columns)
    note_html = "".join(f"<li>{html.escape(n)}</li>" for n in notes or [])
    param_html = html.escape(str(params)) if params else ""
    chart = _svg_chart({"Estrategia": equity, "Buy & hold": benchmark})
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{--bg:#fff;--fg:#111827;--muted:#6b7280;--line:#e5e7eb}}
@media(prefers-color-scheme:dark){{:root{{--bg:#111827;--fg:#f3f4f6;--muted:#9ca3af;--line:#374151}}}}
body{{font:14px system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:960px;margin:0 auto;padding:16px}}
table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid var(--line);padding:4px 8px;text-align:right}}
th{{text-align:left;font-weight:500}}.grid{{stroke:var(--line)}}.axis{{fill:var(--muted);font-size:11px}}
.trades{{overflow-x:auto;font-size:12px}}.trades th{{text-align:right}}small{{color:var(--muted)}}
</style></head><body>
<h1>{html.escape(title)}</h1><small>{param_html}</small>
<ul>{note_html}</ul>
{chart}
<h2>Métricas</h2><table>{rows}</table>
<h2>Operaciones <small>(últimas {min(len(trades), max_trades)} de {len(trades)})</small></h2>
<div class="trades"><table><tr>{head}</tr>{trade_rows}</table></div>
</body></html>"""


def write_report(path: Path | str, **kwargs) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(**kwargs), encoding="utf-8")
    return path

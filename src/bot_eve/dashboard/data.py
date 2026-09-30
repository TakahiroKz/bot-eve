"""Lectura (solo lectura) de los archivos de estado que escribe el motor."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)


def read_status(state_dir: Path) -> dict | None:
    path = Path(state_dir) / "status.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:  # archivo a medias o corrupto: no tumbar el dashboard
        log.warning("status.json ilegible en %s (%s)", state_dir, type(exc).__name__)
        return None


def read_trades(state_dir: Path) -> list[dict]:
    """Operaciones cerradas (las líneas dañadas se ignoran)."""
    path = Path(state_dir) / "trades.jsonl"
    trades: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return trades
    for line in lines:
        try:
            item = json.loads(line)
            if isinstance(item, dict) and "pnl" in item:
                trades.append(item)
        except ValueError:
            continue
    return trades


def trade_stats(trades: list[dict]) -> dict:
    n = len(trades)
    pnls = [float(t["pnl"]) for t in trades]
    gains, losses = sum(p for p in pnls if p > 0), -sum(p for p in pnls if p < 0)
    by_reason: dict[str, int] = {}
    for t in trades:
        by_reason[t.get("reason", "?")] = by_reason.get(t.get("reason", "?"), 0) + 1
    return {
        "trades": n,
        "wins": sum(p > 0 for p in pnls),
        "win_rate": (sum(p > 0 for p in pnls) / n) if n else None,
        "total_pnl": sum(pnls),
        # JSON no admite infinitos: sin pérdidas el factor es None y `no_losses` lo indica.
        "profit_factor": (gains / losses) if losses > 0 else None,
        "no_losses": losses == 0 and gains > 0,
        "avg_pnl": (sum(pnls) / n) if n else None,
        "best": max(pnls) if n else None,
        "worst": min(pnls) if n else None,
        "by_reason": by_reason,
    }


def pnl_curve(trades: list[dict]) -> list[dict]:
    """P&L realizado acumulado en el orden en que se cerraron las operaciones."""
    total, curve = 0.0, []
    for t in sorted(trades, key=lambda x: x.get("exit_time", "")):
        total += float(t["pnl"])
        curve.append({"t": t.get("exit_time"), "cum_pnl": round(total, 6)})
    return curve


def age_seconds(status: dict | None, now: datetime | None = None) -> float | None:
    if not status or "updated_at" not in status:
        return None
    try:
        updated = datetime.fromisoformat(status["updated_at"])
    except ValueError:
        return None
    return ((now or datetime.now(UTC)) - updated).total_seconds()

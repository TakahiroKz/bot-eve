"""Estado persistente del bot: permite reiniciar sin perder posiciones ni duplicar órdenes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Position:
    qty: float
    entry_price: float
    entry_time: str
    entry_fee_quote: float
    stop_order_id: str | None
    stop_price: float
    target_price: float | None = None


@dataclass
class Slot:
    """Una combinación estrategia + par + intervalo."""

    last_candle: str | None = None  # ISO de la última vela procesada
    position: Position | None = None


@dataclass
class State:
    version: int = 1
    day: str = ""
    day_start_equity: float = 0.0
    consecutive_errors: int = 0
    last_summary_day: str = ""  # día (broker) del último resumen diario enviado
    slots: dict[str, Slot] = field(default_factory=dict)


def slot_key(strategy: str, symbol: str, interval: str) -> str:
    return f"{strategy}|{symbol}|{interval}"


class StateStore:
    def __init__(self, directory: Path | str) -> None:
        self.dir = Path(directory)
        self.path = self.dir / "state.json"
        self.trades_path = self.dir / "trades.jsonl"
        self.kill_path = self.dir / "KILL"
        self.status_path = self.dir / "status.json"

    def load(self) -> State:
        if not self.path.exists():
            return State()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        slots = {}
        for key, slot in raw.get("slots", {}).items():
            pos = slot.get("position")
            slots[key] = Slot(slot.get("last_candle"), Position(**pos) if pos else None)
        return State(
            raw.get("version", 1),
            raw.get("day", ""),
            raw.get("day_start_equity", 0.0),
            raw.get("consecutive_errors", 0),
            raw.get("last_summary_day", ""),
            slots,
        )

    def save(self, state: State) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
        tmp.replace(self.path)  # escritura atómica

    def log_trade(self, trade: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.trades_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(trade) + "\n")

    def save_status(self, status: dict) -> None:
        """Foto del estado para el dashboard (solo lectura). Escritura atómica."""
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.status_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
        tmp.replace(self.status_path)

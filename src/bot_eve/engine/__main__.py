"""CLI del motor en vivo.

python -m bot_eve.engine check               # verifica claves, saldo, reglas y datos (no opera)
python -m bot_eve.engine check --roundtrip BTCUSDT   # compra/vende el mínimo en el TESTNET
python -m bot_eve.engine run [--once]        # arranca el bot
python -m bot_eve.engine status              # posiciones y estado guardado
python -m bot_eve.engine kill                # cierra todo y detiene el bot (archivo KILL)
python -m bot_eve.engine unkill              # quita el interruptor de emergencia
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bot_eve.common.config import Config, load_config
from bot_eve.common.logging import setup_logging
from bot_eve.engine.live import KillSwitch, LiveEngine, build_slots
from bot_eve.engine.state import StateStore
from bot_eve.execution.base import Broker, BrokerError
from bot_eve.execution.factory import make_broker


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m bot_eve.engine")
    p.add_argument("--config", type=Path)
    sub = p.add_subparsers(dest="command", required=True)
    chk = sub.add_parser("check", help="verifica la conexión sin operar")
    chk.add_argument(
        "--roundtrip", metavar="SÍMBOLO", help="compra y vende el mínimo (solo testnet)"
    )
    run = sub.add_parser("run", help="arranca el bot")
    run.add_argument("--once", action="store_true", help="una sola pasada y salir")
    run.add_argument("--yes-real-money", action="store_true", help="necesario en modo live")
    sub.add_parser("status")
    sub.add_parser("kill")
    sub.add_parser("unkill")
    return p


def check(cfg: Config, broker: Broker, roundtrip: str | None) -> int:
    ex = cfg.execution
    print(
        f"Broker: {broker.name} | modo: {ex.mode} | dinero real: {'SÍ' if broker.is_real_money else 'no'}"
    )
    print(f"Hora del servidor: {broker.now()}")
    print(f"Saldo libre {ex.quote_asset}: {broker.get_balance(ex.quote_asset):,.4f}")
    for symbol in cfg.data.symbols:
        rules = broker.get_symbol_rules(symbol)
        print(
            f"{symbol}: paso {rules.step_size}, cantidad mín. {rules.min_qty}, "
            f"notional mín. {rules.min_notional} | precio {broker.get_price(symbol):,.2f}"
        )
    for symbol in cfg.data.symbols[:1]:
        candles = broker.get_candles(symbol, "15m", 5)
        print(f"Velas 15m de {symbol}: {len(candles)} cerradas, última {candles.index[-1]}")
    active = cfg.active_strategies(ex.mode)
    if active:
        print(
            "Estrategias activas:",
            ", ".join(f"{n} (capital {c.capital_fraction:.0%})" for n, c in active.items()),
        )
    else:
        print(
            f"Estrategias activas en {ex.mode}: ninguna (todas están en etapa backtest o desactivadas)."
        )
    if roundtrip:
        return _roundtrip(cfg, broker, roundtrip)
    print("OK: la conexión funciona. No se envió ninguna orden.")
    return 0


def _roundtrip(cfg: Config, broker: Broker, symbol: str) -> int:
    """Prueba el camino completo de órdenes en el testnet: compra mínima, stop, cancelar, venta."""
    if broker.is_real_money:
        print("--roundtrip solo se permite en el testnet.")
        return 2
    rules = broker.get_symbol_rules(symbol)
    price = broker.get_price(symbol)
    qty = rules.round_qty(max(rules.min_qty, rules.min_notional * 1.2 / price))
    qty = rules.round_qty(qty + rules.step_size) if not rules.is_valid(qty, price) else qty
    print(
        f"Comprando {qty} {symbol} a mercado (≈ {qty * price:.2f} {cfg.execution.quote_asset})..."
    )
    fill = broker.market_buy(symbol, qty)
    net = rules.round_qty(fill.net_qty)
    print(f"  ejecutada: {fill.qty} @ {fill.price}, comisión {fill.fee} {fill.fee_asset}")
    stop = fill.price * 0.9
    oid = broker.place_stop_loss(symbol, net, stop, stop * 0.997)
    print(f"  stop colocado ({oid}) en {stop:.2f}: {broker.get_order(symbol, oid).status}")
    broker.cancel_order(symbol, oid)
    print(f"  stop cancelado: {broker.get_order(symbol, oid).status}")
    sold = broker.market_sell(
        symbol,
        rules.round_qty(min(net, broker.get_balance(symbol[: -len(cfg.execution.quote_asset)]))),
    )
    print(f"  vendida: {sold.qty} @ {sold.price}")
    print("OK: el camino completo de órdenes funciona en el testnet.")
    return 0


def status(store: StateStore) -> int:
    state = store.load()
    print(f"Día: {state.day or '-'} | capital al inicio del día: {state.day_start_equity:,.2f} | "
          f"errores seguidos: {state.consecutive_errors}")  # fmt: skip
    print("KILL activo" if store.kill_path.exists() else "KILL inactivo")
    open_positions = 0
    for key, slot in state.slots.items():
        if slot.position:
            p = slot.position
            open_positions += 1
            print(f"  {key}: {p.qty} @ {p.entry_price} (stop {p.stop_price}, id {p.stop_order_id})")
    print(f"Posiciones abiertas: {open_positions}")
    if store.trades_path.exists():
        print(
            f"Operaciones cerradas: {sum(1 for _ in store.trades_path.open())} ({store.trades_path})"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    cfg = load_config(args.config)
    setup_logging(cfg.logging.level, cfg.logging.file)
    store = StateStore(cfg.execution.state_dir)

    if args.command == "status":
        return status(store)
    if args.command == "kill":
        store.dir.mkdir(parents=True, exist_ok=True)
        store.kill_path.write_text("kill", encoding="utf-8")
        print(
            f"Creado {store.kill_path}. El bot cerrará las posiciones y se detendrá en su próxima pasada."
        )
        return 0
    if args.command == "unkill":
        store.kill_path.unlink(missing_ok=True)
        print("Interruptor de emergencia retirado.")
        return 0

    try:
        broker = make_broker(cfg, allow_real_money=getattr(args, "yes_real_money", False))
        if args.command == "check":
            return check(cfg, broker, args.roundtrip)
        if broker.is_real_money:
            print("⚠ MODO LIVE: se operará con DINERO REAL.")
        engine = LiveEngine(cfg, broker, store, build_slots(cfg))
        if not engine.slots:
            print(
                "No hay estrategias activas para este modo. Revisa `strategies:` en la configuración."
            )
            return 1
        if args.once:
            engine.step()
        else:
            engine.run_forever()
        return 0
    except KillSwitch as exc:
        print(f"KILL SWITCH: {exc}")
        return 3
    except (BrokerError, ValueError) as exc:
        print(f"Error: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

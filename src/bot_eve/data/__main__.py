"""CLI de datos.

python -m bot_eve.data sync      # descarga/actualiza velas y remuestrea
python -m bot_eve.data validate  # revisa la calidad de los datos guardados
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bot_eve.common.config import load_config
from bot_eve.common.logging import setup_logging
from bot_eve.data.downloader import KlineDownloader
from bot_eve.data.mt5 import DEFAULT_STORE, Mt5Client, Mt5Error, median_spread_pct, sync_symbol
from bot_eve.data.store import CandleStore
from bot_eve.data.validate import validate_candles


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m bot_eve.data")
    parser.add_argument("--config", type=Path, default=None, help="YAML de configuración")
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="descarga y actualiza velas")
    sync.add_argument("--symbols", nargs="+", help="sobrescribe los símbolos de la config")
    sync.add_argument("--start", help="mes inicial YYYY-MM (sobrescribe la config)")

    mt5 = sub.add_parser("mt5-info", help="cuenta y especificaciones de símbolos de MT5 (Windows)")
    mt5.add_argument("--symbols", nargs="+", default=["BTCUSD", "ETHUSD"])
    mt5s = sub.add_parser("mt5-sync", help="descarga historial desde MT5 (Windows)")
    mt5s.add_argument("--symbols", nargs="+", default=["BTCUSD", "ETHUSD"])
    mt5s.add_argument("--intervals", nargs="+", default=["15m", "1h", "4h"])
    mt5s.add_argument("--from", dest="start", default="2020-01", help="mes inicial YYYY-MM")
    mt5s.add_argument("--dir", type=Path, default=DEFAULT_STORE)

    val = sub.add_parser("validate", help="valida los datos guardados")
    val.add_argument("--symbols", nargs="+")
    val.add_argument("--intervals", nargs="+", help="por defecto: base y remuestreados")
    return parser


def _mt5(args, client: Mt5Client | None = None) -> int:
    try:
        client = client or Mt5Client()
        client.connect()
        if args.command == "mt5-info":
            print("CUENTA:")
            for key, value in client.account_summary().items():
                print(f"  {key}: {value}")
            for symbol in args.symbols:
                spec = client.symbol_spec(symbol)
                swap = spec.swap_long_pct_per_day
                print(
                    f"\n{symbol}: dígitos {spec.digits}, punto {spec.point}, contrato {spec.contract_size}"
                )
                print(
                    f"  lote mín {spec.volume_min} paso {spec.volume_step} máx {spec.volume_max}; stops mín {spec.stops_level} pts"
                )
                if spec.price <= 0:
                    print(
                        "  SIN COTIZACIÓN ahora (mercado cerrado o pausa diaria): repite en horario activo."
                    )
                else:
                    print(
                        f"  precio {spec.price:,.5g} | spread actual {spec.spread_points} pts"
                        f" = {spec.spread_pct:.4%}"
                    )
                    if spec.spread_points == 0:
                        print(
                            "  ⚠ spread 0: probablemente sin cotización real ahora; no lo uses para costos."
                        )
                print(
                    f"  swap largo {spec.swap_long} / corto {spec.swap_short} (modo {spec.swap_mode})"
                    + (
                        f" = {swap:.4%} por día ≈ {swap * 365:.1%} al año"
                        if swap is not None
                        else ""
                    )
                )
            print(
                "\nLa API de Python NO expone la comisión por lote: léela en «Especificación» del símbolo o"
            )
            print(
                "mide el costo real con: python -m bot_eve.engine --config config/mt5.yaml check --roundtrip SÍMBOLO"
            )
            print(
                "(en horario activo). Copia spread y swap a la configuración (spread_pct y swap_pct_per_day)."
            )
        else:
            store = CandleStore(args.dir)
            for symbol in args.symbols:
                point = client.symbol_spec(symbol).point
                for interval in args.intervals:
                    n = sync_symbol(client, store, symbol, interval, args.start)
                    spread = median_spread_pct(store, symbol, interval, point)
                    print(f"{symbol} {interval}: {n} velas | spread mediano histórico {spread:.4%}")
                    if spread == spread and spread < 1e-9:
                        print(
                            "   ⚠ spread histórico = 0: el broker no lo guarda en las velas; NO sirve para costos."
                        )
        client.shutdown()
        return 0
    except Mt5Error as exc:
        print(f"Error: {exc}")
        return 2


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    cfg = load_config(args.config)
    setup_logging(cfg.logging.level, cfg.logging.file)
    store = CandleStore(cfg.data.dir)
    symbols = args.symbols or cfg.data.symbols

    if args.command in ("mt5-info", "mt5-sync"):
        return _mt5(args)

    if args.command == "sync":
        downloader = KlineDownloader(
            store,
            base_url=cfg.data.base_url,
            interval=cfg.data.base_interval,
            workers=cfg.data.download_workers,
        )
        for symbol in symbols:
            written = downloader.sync(symbol, args.start or cfg.data.start, cfg.data.resample)
            print(f"{symbol}: {len(written)} meses actualizados")
        return 0

    intervals = args.intervals or [cfg.data.base_interval, *cfg.data.resample]
    reports_dir = Path(cfg.data.dir) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    failed = False
    for symbol in symbols:
        for interval in intervals:
            df = store.read(symbol, interval)
            report = validate_candles(df, symbol, interval)
            (reports_dir / f"{symbol}_{interval}.json").write_text(
                json.dumps(report.to_dict(), indent=2), encoding="utf-8"
            )
            status = "OK " if report.ok else "ERR"
            print(
                f"[{status}] {symbol} {interval}: {report.rows} velas, "
                f"{len(report.gaps)} huecos ({report.missing_candles} velas faltantes), "
                f"{len(report.outliers)} outliers {report.errors or ''}"
            )
            failed |= not report.ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

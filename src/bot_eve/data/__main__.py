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
from bot_eve.data.store import CandleStore
from bot_eve.data.validate import validate_candles


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m bot_eve.data")
    parser.add_argument("--config", type=Path, default=None, help="YAML de configuración")
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="descarga y actualiza velas")
    sync.add_argument("--symbols", nargs="+", help="sobrescribe los símbolos de la config")
    sync.add_argument("--start", help="mes inicial YYYY-MM (sobrescribe la config)")

    val = sub.add_parser("validate", help="valida los datos guardados")
    val.add_argument("--symbols", nargs="+")
    val.add_argument("--intervals", nargs="+", help="por defecto: base y remuestreados")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    cfg = load_config(args.config)
    setup_logging(cfg.logging.level, cfg.logging.file)
    store = CandleStore(cfg.data.dir)
    symbols = args.symbols or cfg.data.symbols

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

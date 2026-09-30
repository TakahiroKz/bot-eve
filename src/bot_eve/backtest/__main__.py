"""CLI de backtest.

  python -m bot_eve.backtest run --symbol BTCUSDT --interval 15m --strategy sma_cross \
      --params fast=10 slow=30
  python -m bot_eve.backtest walkforward --symbol BTCUSDT --interval 15m --strategy sma_cross \
      --grid fast=5,10,20 slow=30,50,100

Por defecto solo se usan datos anteriores a `backtest.holdout_start`. `--final` evalúa
únicamente el tramo reservado: úsalo una sola vez, con la estrategia ya decidida.
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from pathlib import Path

import pandas as pd

from bot_eve.backtest import base_rates as br
from bot_eve.backtest.compare import compare, summarize
from bot_eve.backtest.costs import rules_for
from bot_eve.backtest.engine import RiskSizing, run_backtest
from bot_eve.backtest.report import write_report
from bot_eve.backtest.walkforward import OBJECTIVES, split_holdout, walk_forward
from bot_eve.common.config import Config, load_config
from bot_eve.common.logging import setup_logging
from bot_eve.data.intervals import to_timedelta
from bot_eve.data.store import CandleStore
from bot_eve.strategies import REGISTRY, build_strategy


def _scalar(text: str):
    if text.lower() in ("none", "null"):
        return None
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            continue
    return text


def _parse_params(items: list[str] | None) -> dict:
    return {k: _scalar(v) for k, v in (i.split("=", 1) for i in items or [])}


def _parse_grid(items: list[str] | None) -> dict[str, list]:
    return {
        k: [_scalar(x) for x in v.split(",")] for k, v in (i.split("=", 1) for i in items or [])
    }


def _load(cfg: Config, symbol: str, interval: str, final: bool) -> pd.DataFrame:
    df = CandleStore(cfg.data.dir).read(symbol, interval)
    if df.empty:
        raise SystemExit(
            f"No hay datos de {symbol} {interval}. Ejecuta: python -m bot_eve.data sync"
        )
    dev, holdout = split_holdout(df, cfg.backtest.holdout_start)
    if final:
        print("AVISO: evaluación sobre el tramo reservado (holdout). Úsala una sola vez.")
        return holdout
    return dev


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m bot_eve.backtest")
    p.add_argument("--config", type=Path)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("run", "walkforward"):
        s = sub.add_parser(name)
        s.add_argument("--symbol", default="BTCUSDT")
        s.add_argument("--interval", default="15m")
        s.add_argument("--strategy", default="sma_cross", choices=sorted(REGISTRY))
        s.add_argument("--start")
        s.add_argument("--end")
        s.add_argument("--final", action="store_true", help="evalúa solo el holdout reservado")
        s.add_argument("--report", type=Path, help="ruta del informe HTML")
    fx = sub.add_parser("fixed", help="parámetros fijos (sin optimizar) por periodo y símbolo")
    fx.add_argument("--strategy", required=True, choices=sorted(REGISTRY))
    fx.add_argument("--params", nargs="*")
    fx.add_argument("--interval", default="4h")
    fx.add_argument("--symbols", nargs="+")
    fx.add_argument("--risk-sizing", action="store_true")
    fx.add_argument(
        "--cash", type=float, help="capital inicial (por defecto el de la configuración)"
    )
    brp = sub.add_parser(
        "base-rates", help="ventaja exigida (en R) para cubrir costos, entrando al azar"
    )
    brp.add_argument("--symbols", nargs="+")
    brp.add_argument("--interval", default="5m")
    brp.add_argument("--tp-atr", type=float, default=1.8)
    brp.add_argument("--sl-atr", type=float, default=1.2)
    brp.add_argument("--horizon", type=int, help="velas máximas de la operación")
    brp.add_argument(
        "--by-hour",
        action="store_true",
        help="desglose por bloques de 4 h del día (hora del broker)",
    )
    brp.add_argument(
        "--spread-pips",
        nargs="+",
        type=float,
        default=[0.2, 0.5, 1.0, 2.0],
        help="escenarios de spread (pips) para la tabla de sensibilidad",
    )
    sub.add_parser("list", help="estrategias disponibles y su estado en la configuración")
    cmp_ = sub.add_parser("compare", help="walk-forward de varias estrategias/pares/intervalos")
    cmp_.add_argument("--strategies", nargs="+", choices=sorted(REGISTRY))
    cmp_.add_argument("--symbols", nargs="+")
    cmp_.add_argument("--intervals", nargs="+", default=["15m", "1h"])
    cmp_.add_argument("--workers", type=int)
    cmp_.add_argument("--risk-sizing", action="store_true", help="reglas de riesgo del bot en vivo")
    cmp_.add_argument("--out", type=Path, default=None, help="CSV de salida")
    for name in ("run", "walkforward"):
        sub.choices[name].add_argument(
            "--risk-sizing",
            action="store_true",
            help="reglas de riesgo del bot en vivo (1%% por operación + stop)",
        )
    sub.choices["run"].add_argument("--params", nargs="*", help="p. ej. fast=10 slow=30")
    wf = sub.choices["walkforward"]
    wf.add_argument("--grid", nargs="+", required=True, help="p. ej. fast=5,10 slow=30,50")
    wf.add_argument("--fixed", nargs="*", help="parámetros fijos, p. ej. stop_pct=0.01")
    wf.add_argument("--train-days", type=int, default=90)
    wf.add_argument("--test-days", type=int, default=30)
    wf.add_argument("--objective", default="total_return", choices=OBJECTIVES)
    wf.add_argument("--min-trades", type=int, default=10)
    return p


def _print_metrics(m: dict) -> None:
    print(
        f"Retorno {m['total_return']:.2%} (buy&hold {m['buy_and_hold_return']:.2%}) | "
        f"Sharpe {m['sharpe']:.2f} | MaxDD {m['max_drawdown']:.2%} | "
        f"Operaciones {m['trades']} | Win rate {m['win_rate']:.1%} | "
        f"PF {m['profit_factor']:.2f} | Comisiones {m['total_fees']:.2f} | "
        f"Exposición {m['exposure']:.1%} | Rechazadas {m['rejected_entries']}"
    )


def _base_rates(cfg: Config, args) -> int:
    """Descriptivo (entradas al azar, sin parámetros ajustados): usa todos los datos disponibles."""
    barriers = br.Barriers(args.tp_atr, args.sl_atr)
    print(f"Barreras: stop {barriers.sl_atr}×ATR / objetivo {barriers.tp_atr}×ATR (R:R {barriers.rr:.2f}); "
          f"acierto al azar = {barriers.random_win:.1%}. Entradas en TODAS las velas.")  # fmt: skip
    rows, hours = [], {}
    for symbol in args.symbols or cfg.data.symbols:
        df = CandleStore(cfg.data.dir).read(symbol, args.interval)
        if df.empty:
            print(f"{symbol}: sin datos {args.interval}")
            continue
        out = br.outcomes(df, args.interval, barriers, args.horizon)
        costs = cfg.backtest.costs(symbol)
        frac = br.cost_fraction(costs)
        res = br.summarize(out, frac, barriers)
        rows.append({
            "símbolo": symbol, "velas": res["n"], "desde": str(df.index[0].date()),
            "stop%": f"{res['stop_pct_median']:.4%}", "P(obj.) azar": f"{res['p_tp']:.1%}",
            "costo usado": f"{frac:.4%}", "costo_R": f"{res['cost_R']:.2f}",
            "esperanza bruta R": f"{res['gross_R']:+.3f}", "esperanza neta R": f"{res['net_R']:+.3f}",
            "acierto necesario": f"{res['win_needed']:.1%}" if res["win_needed"] < 1 else ">100%",
            "mejora necesaria": f"{res['lift_pts']:+.1f} pts" if res["win_needed"] < 1 else "imposible",
        })  # fmt: skip
        if args.by_hour:
            hours[symbol] = br.by_hour_block(out, frac)
        if "JPY" in symbol.upper() or len(symbol) == 6 and symbol.isalpha():
            price = float(df["close"].median())
            sens = []
            for sp in args.spread_pips:
                c = br.cost_fraction(costs, sp, symbol, price)
                r = br.summarize(out, c, barriers)
                sens.append({"spread (pips)": sp, "costo_R": f"{r['cost_R']:.2f}",
                             "acierto necesario": f"{r['win_needed']:.0%}" if r["win_needed"] < 1 else ">100%",
                             "mejora": f"{r['lift_pts']:+.0f} pts" if r["win_needed"] < 1 else "imposible"})  # fmt: skip
            hours.setdefault("_sens_" + symbol, pd.DataFrame(sens))
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(pd.DataFrame(rows).to_string(index=False))
        for key, table in hours.items():
            if key.startswith("_sens_"):
                print(
                    f"\nSensibilidad al spread (comisión y slippage de la configuración) - {key[6:]}:"
                )
                print(table.to_string(index=False))
            else:
                print(f"\nPor hora del día (hora del broker) - {key}:")
                print(table.round(4).to_string())
    print(
        "\nNota: los costos de la configuración son provisionales; mídelos con `check --roundtrip` en horario activo."
    )
    return 0


def _fixed(cfg: Config, args) -> int:
    """Comprobación de consistencia: mismos parámetros, datos propios del símbolo/broker.

    Muestra por separado el periodo de desarrollo (antes de `holdout_start`) y el posterior.
    No optimiza nada.
    """
    bt = cfg.backtest
    params = _parse_params(args.params)
    risk = (
        RiskSizing(cfg.risk.risk_per_trade, cfg.risk.default_stop_pct) if args.risk_sizing else None
    )
    cut = pd.Timestamp(bt.holdout_start, tz="UTC")
    cash = args.cash or bt.initial_cash
    rows = []
    for symbol in args.symbols or cfg.data.symbols:
        df = CandleStore(cfg.data.dir).read(symbol, args.interval)
        if df.empty:
            print(f"{symbol}: sin datos {args.interval}")
            continue
        for label, start, end in (
            ("desarrollo", None, cut - pd.Timedelta(seconds=1)),
            ("posterior", cut, None),
        ):
            res = run_backtest(
                df, build_strategy(args.strategy, **params), bt.costs(symbol), rules_for(symbol),
                cash, bt.size_fraction, start=start, end=end, risk=risk,
            )  # fmt: skip
            m = res.metrics
            rows.append(
                {
                    "símbolo": symbol, "periodo": label, "desde": m["start"][:10], "hasta": m["end"][:10],
                    "retorno%": round(m["total_return"] * 100, 1), "B&H%": round(m["buy_and_hold_return"] * 100, 1),
                    "PF": round(m["profit_factor"], 2), "Sharpe": round(m["sharpe"], 2),
                    "MaxDD%": round(m["max_drawdown"] * 100, 1), "B&H_DD%": round(m["buy_and_hold_max_drawdown"] * 100, 1),
                    "ops": m["trades"], "rechazadas": m["rejected_entries"], "win%": round(m["win_rate"] * 100, 1),
                }
            )  # fmt: skip
    table = pd.DataFrame(rows)
    with pd.option_context("display.width", 200):
        print(
            f"{args.strategy} {args.params or ''} {args.interval}  capital {cash:,.0f}  (datos de {cfg.data.dir})"
        )
        print("(rechazadas = entradas que no alcanzan el lote mínimo con ese capital)")
        print(table.to_string(index=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    cfg = load_config(args.config)
    setup_logging(cfg.logging.level, None)
    bt = cfg.backtest

    if args.command == "fixed":
        return _fixed(cfg, args)
    if args.command == "base-rates":
        return _base_rates(cfg, args)
    if args.command == "list":
        for name, cls in sorted(REGISTRY.items()):
            sc = cfg.strategies.get(name)
            state = "sin configurar" if sc is None else f"enabled={sc.enabled} stage={sc.stage}"
            print(f"{name:22} {state:32} {cls.description}")
        return 0
    if args.command == "compare":
        out = args.out or bt.reports_dir / "compare.csv"
        table = compare(
            cfg,
            args.strategies or sorted(REGISTRY),
            args.symbols or cfg.data.symbols,
            args.intervals,
            args.workers,
            out,
            args.risk_sizing,
        )
        with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
            print(table.drop(columns=["trials"]).to_string(index=False))
            print("\nPROMEDIO entre pares:")
            print(summarize(table).to_string())
        print(f"\nCSV: {out}")
        return 0

    df = _load(cfg, args.symbol, args.interval, args.final)
    costs = bt.costs(args.symbol)
    rules = rules_for(args.symbol)
    risk = (
        RiskSizing(cfg.risk.risk_per_trade, cfg.risk.default_stop_pct) if args.risk_sizing else None
    )
    label = f"{args.strategy} {args.symbol} {args.interval}"
    notes = [
        f"Comisión {bt.fee_rate:.3%} y slippage {bt.slippage:.3%} por lado.",
        "Tramo reservado (holdout)." if args.final else f"Datos previos a {bt.holdout_start}.",
    ]
    if risk:
        notes.append(
            f"Sizing por riesgo: {risk.risk_per_trade:.1%} por operación, stop de emergencia {risk.default_stop_pct:.0%}."
        )

    if args.command == "run":
        params = _parse_params(args.params)
        result = run_backtest(
            df, build_strategy(args.strategy, **params), costs, rules,
            bt.initial_cash, bt.size_fraction, start=args.start, end=args.end, risk=risk,
        )  # fmt: skip
        _print_metrics(result.metrics)
        report_args = dict(
            title=label, metrics=result.metrics, equity=result.equity,
            benchmark=result.benchmark, trades=result.trades, params=result.params, notes=notes,
        )  # fmt: skip
    else:
        n = int(pd.Timedelta(days=1) / to_timedelta(args.interval))
        if args.start or args.end:
            df = df.loc[args.start : args.end]
        make = partial(build_strategy, args.strategy, **_parse_params(args.fixed))
        result = walk_forward(
            df, make, _parse_grid(args.grid), args.train_days * n, args.test_days * n,
            args.objective, args.min_trades, costs, rules, bt.initial_cash, bt.size_fraction, risk,
        )  # fmt: skip
        for w in result.windows:
            m = w.test_metrics
            print(
                f"{w.test_start:%Y-%m-%d}..{w.test_end:%Y-%m-%d} {w.best_params} "
                f"train={w.train_score:.3f} test={m['total_return']:.2%} ({m['trades']} ops)"
            )
        print("FUERA DE MUESTRA:")
        _print_metrics(result.metrics)
        notes.append(f"Walk-forward: {args.train_days}d entrenamiento / {args.test_days}d prueba.")
        report_args = dict(
            title=f"Walk-forward {label}", metrics=result.metrics, equity=result.equity,
            benchmark=result.benchmark, trades=result.trades,
            params={"grid": _parse_grid(args.grid), "objective": args.objective}, notes=notes,
        )  # fmt: skip

    if args.report:
        print("Informe:", write_report(args.report, **report_args))
    return 0


if __name__ == "__main__":
    sys.exit(main())

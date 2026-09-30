from conftest import make_candles

from bot_eve.backtest.__main__ import main
from bot_eve.backtest.costs import Costs, SymbolRules
from bot_eve.backtest.engine import run_backtest
from bot_eve.backtest.report import build_report
from bot_eve.data.store import CandleStore
from bot_eve.strategies.sma_cross import SmaCross


def test_report_contains_metrics_and_chart():
    df = make_candles("2024-01-01", 1500, freq="15min", seed=2)
    res = run_backtest(df, SmaCross(5, 20), Costs(), SymbolRules(1e-6, 1e-6, 0.0))
    html = build_report("Prueba <x>", res.metrics, res.equity, res.benchmark, res.trades)
    assert "<svg" in html and "Retorno total" in html and "Prueba &lt;x&gt;" in html
    assert "<script" not in html


def _setup(tmp_path):
    store = CandleStore(tmp_path / "store")
    df = make_candles("2024-01-01", 96 * 120, freq="15min", seed=8)
    for month, part in df.groupby(df.index.strftime("%Y-%m")):
        store.write_month("BTCUSDT", "15m", month, part)
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(
        f"data:\n  dir: {tmp_path / 'store'}\n"
        "backtest:\n  holdout_start: '2024-04-01'\n  initial_cash: 1000\n"
        "logging:\n  file: null\n"
    )
    return cfg


def test_cli_run_and_walkforward_and_holdout(tmp_path, capsys):
    cfg = _setup(tmp_path)
    rep = tmp_path / "r.html"
    base = ["--config", str(cfg)]
    assert main([*base, "run", "--params", "fast=5", "slow=20", "--report", str(rep)]) == 0
    assert rep.exists()
    assert "AVISO" not in capsys.readouterr().out

    assert main([
        *base, "walkforward", "--grid", "fast=3,5", "slow=15,30",
        "--train-days", "20", "--test-days", "10", "--min-trades", "1",
    ]) == 0  # fmt: skip
    assert "FUERA DE MUESTRA" in capsys.readouterr().out

    assert main([*base, "run", "--params", "fast=5", "slow=20", "--final"]) == 0
    assert "holdout" in capsys.readouterr().out


def test_cli_fixed_reports_both_periods_without_optimizing(tmp_path, capsys):
    cfg = _setup(tmp_path)  # holdout_start 2024-04-01, datos 15m sintéticos
    rc = main(["--config", str(cfg), "fixed", "--strategy", "sma_cross", "--params", "fast=5",
               "slow=20", "--interval", "15m", "--symbols", "BTCUSDT", "--risk-sizing"])  # fmt: skip
    out = capsys.readouterr().out
    assert rc == 0 and "desarrollo" in out and "posterior" in out and "BTCUSDT" in out
    assert "2024-03-31" in out or "2024-04-01" in out  # los periodos se separan en holdout_start

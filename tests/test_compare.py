import pytest
from conftest import volatile_candles

from bot_eve.backtest.__main__ import main
from bot_eve.backtest.compare import compare, summarize
from bot_eve.common.config import load_config
from bot_eve.data.store import CandleStore


def setup(tmp_path):
    store = CandleStore(tmp_path / "store")
    df = volatile_candles(96 * 150, seed=2)
    for month, part in df.groupby(df.index.strftime("%Y-%m")):
        store.write_month("BTCUSDT", "15m", month, part)
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text(
        f"data:\n  dir: {tmp_path / 'store'}\n  symbols: [BTCUSDT]\n"
        f"backtest:\n  holdout_start: '2030-01-01'\n  reports_dir: {tmp_path / 'rep'}\n"
        "logging:\n  file: null\n"
    )
    return cfg_path


def test_compare_runs_and_writes_csv(tmp_path):
    cfg_path = setup(tmp_path)
    cfg = load_config(cfg_path)
    out = tmp_path / "out.csv"
    table = compare(cfg, ["sma_cross", "atr_breakout"], ["BTCUSDT"], ["15m"], workers=1, out=out)
    assert len(table) == 2 and out.exists()
    assert {"return", "buy_and_hold", "pf_before_fees", "trials"} <= set(table.columns)
    assert (table["trials"] > 0).all()
    assert len(summarize(table)) == 2


def test_compare_never_reads_the_holdout(tmp_path):
    """Con el holdout a 2024-03-01 solo quedan ~60 días (< 120 de una ventana): debe
    fallar por falta de datos en lugar de completar la ventana con el tramo reservado."""
    cfg = load_config(setup(tmp_path))
    cfg.backtest.holdout_start = "2024-03-01"
    with pytest.raises(ValueError, match="No hay datos suficientes"):
        compare(cfg, ["sma_cross"], ["BTCUSDT"], ["15m"], workers=1)


def test_cli_list_and_compare(tmp_path, capsys):
    cfg_path = setup(tmp_path)
    assert main(["--config", str(cfg_path), "list"]) == 0
    assert "bollinger_reversion" in capsys.readouterr().out
    rc = main(["--config", str(cfg_path), "compare", "--strategies", "sma_cross",
               "--intervals", "15m", "--workers", "1"])  # fmt: skip
    assert rc == 0 and (tmp_path / "rep" / "compare.csv").exists()


def test_compare_with_risk_sizing_reports_criteria_columns(tmp_path):
    cfg = load_config(setup(tmp_path))
    table = compare(cfg, ["sma_cross"], ["BTCUSDT"], ["15m"], workers=1, risk_sizing=True)
    assert {"bh_sharpe", "bh_max_drawdown", "windows_pos", "windows_neg"} <= set(table.columns)
    plain = compare(cfg, ["sma_cross"], ["BTCUSDT"], ["15m"], workers=1)
    # con riesgo 1% y stop, el capital se arriesga mucho menos: drawdown claramente menor
    assert table["max_drawdown"].iloc[0] > plain["max_drawdown"].iloc[0]

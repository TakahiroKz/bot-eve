from pathlib import Path

import pytest

from bot_eve.common.config import load_config


def test_defaults_without_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg.data.symbols == ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    assert cfg.data.base_interval == "1m"


def test_loads_yaml_and_validates(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("data:\n  symbols: [ETHUSDT]\n  start: '2022-05'\n")
    cfg = load_config(f)
    assert cfg.data.symbols == ["ETHUSDT"]
    assert cfg.data.start == "2022-05"


def test_rejects_bad_start(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("data:\n  start: '2022-13'\n")
    with pytest.raises(ValueError):
        load_config(f)


def test_explicit_missing_config_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.yaml")


def test_repo_default_config_is_valid(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    assert load_config().data.start == "2020-01"


def test_strategy_stage_rules():
    from bot_eve.common.config import StrategyConfig

    off = StrategyConfig(enabled=False, stage="live")
    bt_only = StrategyConfig(enabled=True, stage="backtest")
    demo = StrategyConfig(enabled=True, stage="demo")
    live = StrategyConfig(enabled=True, stage="live")
    assert not off.allowed_in("demo")
    assert not bt_only.allowed_in("demo") and not bt_only.allowed_in("live")
    assert demo.allowed_in("demo") and not demo.allowed_in("live")
    assert live.allowed_in("demo") and live.allowed_in("live")


def test_capital_fractions_cannot_exceed_one(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text(
        "strategies:\n"
        "  a: {enabled: true, stage: live, capital_fraction: 0.7}\n"
        "  b: {enabled: true, stage: live, capital_fraction: 0.5}\n"
    )
    with pytest.raises(ValueError, match="capital_fraction"):
        load_config(f)
    f.write_text(
        "strategies:\n"
        "  a: {enabled: true, stage: live, capital_fraction: 0.7}\n"
        "  b: {enabled: false, stage: live, capital_fraction: 0.5}\n"
    )
    assert list(load_config(f).active_strategies("live")) == ["a"]


def test_repo_config_keeps_everything_in_backtest_stage(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    cfg = load_config()
    assert {"rsi_trend", "atr_breakout", "bollinger_reversion", "ema_adx"} <= set(cfg.strategies)
    assert cfg.active_strategies("demo") == {}  # nada pasa a demo sin validación

import pandas as pd
import pytest

from bot_eve.backtest.costs import SymbolRules
from bot_eve.common.config import RiskConfig
from bot_eve.risk.manager import RiskManager

RULES = SymbolRules(step_size=0.001, min_qty=0.001, min_notional=5.0)


@pytest.fixture
def risk(tmp_path):
    return RiskManager(RiskConfig(), tmp_path / "KILL")


def test_size_is_limited_by_risk_per_trade(risk):
    # equity 1000, riesgo 1% = 10; stop 2% sobre precio 100 -> 10 / (100 * 0.02) = 5
    qty = risk.position_size(1000, 100, 0.02, 1.0, RULES, available_quote=1000)
    assert qty == pytest.approx(5.0)


def test_size_is_limited_by_capital_fraction_and_cash(risk):
    # riesgo permitiría 50 unidades (stop 0.2%), pero la fracción 10% da 1 unidad
    assert risk.position_size(1000, 100, 0.002, 0.1, RULES, 1000) == pytest.approx(1.0)
    # saldo disponible de 100 USDT -> menos de 1 unidad (deja margen para comisión)
    assert risk.position_size(1000, 100, 0.002, 1.0, RULES, 100) < 1.0


def test_size_zero_when_minimums_not_met(risk):
    """Con 3.54 USDT no se alcanza el mínimo de 5 USDT por orden."""
    assert risk.position_size(3.54, 100, 0.02, 1.0, RULES, 3.54) == 0.0
    assert risk.position_size(0, 100, 0.02, 1.0, RULES, 0) == 0.0
    assert risk.position_size(1000, 100, 0.02, 0.0, RULES, 1000) == 0.0  # sin capital asignado


def test_every_position_gets_a_stop(risk):
    assert risk.stop_pct_for(None) == 0.03
    assert risk.stop_pct_for(float("nan")) == 0.03
    assert risk.stop_pct_for(-1) == 0.03
    assert risk.stop_pct_for(0.01) == 0.01
    assert risk.stop_pct_for(0.9) == 0.5  # tope


def test_stop_prices_have_limit_below_trigger(risk):
    stop, limit = risk.stop_prices(100, 0.02)
    assert stop == pytest.approx(98.0) and limit == pytest.approx(98.0 * 0.997)


def test_daily_loss_limit_and_kill_switch(risk, tmp_path):
    assert risk.can_open(1000, 1000).ok
    assert risk.can_open(980, 1000).ok  # -2% < 3%
    blocked = risk.can_open(969, 1000)  # -3.1%
    assert not blocked.ok and "pérdida diaria" in blocked.reason
    (tmp_path / "KILL").write_text("x")
    assert not risk.can_open(1000, 1000).ok and risk.kill_requested()


def test_staleness(risk):
    t0 = pd.Timestamp("2024-01-01 00:00", tz="UTC")  # vela que cerró a las 00:15
    assert not risk.is_stale(t0, "15m", pd.Timestamp("2024-01-01 00:16", tz="UTC"))
    assert risk.is_stale(t0, "15m", pd.Timestamp("2024-01-01 02:00", tz="UTC"))

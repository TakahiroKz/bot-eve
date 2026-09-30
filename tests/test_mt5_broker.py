import pandas as pd
import pytest
from fake_mt5 import FakeTradingMt5, make_rates

from bot_eve.common.config import load_config
from bot_eve.execution.base import BrokerError
from bot_eve.execution.factory import make_broker
from bot_eve.execution.mt5 import MAGIC, Mt5Broker


def broker(**kw):
    fake = FakeTradingMt5(**kw)
    return Mt5Broker("BTCUSD", mt5=fake), fake


# --- conexión y seguridad ------------------------------------------------------------------------
def test_refuses_when_algo_trading_is_off_with_clear_hint():
    with pytest.raises(BrokerError, match="Algo Trading"):
        Mt5Broker("BTCUSD", mt5=FakeTradingMt5(algo=False))


def test_refuses_without_logged_in_account():
    with pytest.raises(BrokerError, match="sesión"):
        Mt5Broker("BTCUSD", mt5=FakeTradingMt5(session=False))


def test_real_money_is_detected_from_the_account_not_the_config():
    assert not broker()[0].is_real_money
    assert broker(real=True)[0].is_real_money


def _cfg(tmp_path, **execution):
    body = "\n".join(f"  {k}: {v}" for k, v in execution.items())
    f = tmp_path / "c.yaml"
    f.write_text(
        f"execution:\n  broker: mt5\n  quote_asset: USD\n{body}\ndata:\n  symbols: [BTCUSD]\n"
    )
    return load_config(f)


def test_demo_mode_refuses_a_real_account(tmp_path, monkeypatch):
    monkeypatch.setattr("bot_eve.execution.mt5.load_mt5", lambda: FakeTradingMt5(real=True))
    with pytest.raises(BrokerError, match="REAL"):
        make_broker(_cfg(tmp_path, mode="demo"))


def test_demo_mode_accepts_a_demo_account_and_live_needs_confirmations(tmp_path, monkeypatch):
    monkeypatch.setattr("bot_eve.execution.mt5.load_mt5", lambda: FakeTradingMt5())
    assert make_broker(_cfg(tmp_path, mode="demo")).name == "mt5"
    with pytest.raises(BrokerError, match="live"):
        make_broker(_cfg(tmp_path, mode="live"))


# --- datos y reglas --------------------------------------------------------------------------------
def test_symbol_rules_are_in_asset_units():
    rules = broker()[0].get_symbol_rules("BTCUSD")
    assert (rules.step_size, rules.min_qty, rules.min_notional) == (0.01, 0.01, 0.0)
    with pytest.raises(BrokerError, match="no existe"):
        broker()[0].get_symbol_rules("XYZ")


def test_candles_exclude_forming_candle_using_server_time():
    b, fake = broker()  # el servidor va 3 h por delante de UTC
    server_now = pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=3)
    fake.rates = make_rates(50, 3600, end=server_now.isoformat())  # la última vela empieza ahora
    df = b.get_candles("BTCUSD", "1h", 100)
    assert len(df) == 49 and list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index[-1] + pd.Timedelta(hours=1) <= b.now()
    assert abs((b.now() - server_now).total_seconds()) < 5


def test_clock_syncs_on_first_call_even_right_after_boot(monkeypatch):
    import time as time_module

    monkeypatch.setattr(time_module, "monotonic", lambda: 5.0)
    b, _ = broker()
    assert abs((b.now() - (pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=3))).total_seconds()) < 5


def test_equity_includes_floating_pnl_and_buying_power_is_capped_at_1x():
    b, fake = broker()
    b.market_buy("BTCUSD", 0.1)
    fake.bid = 85000.0
    assert b.equity("USD", [("BTCUSD", 0.1)]) == pytest.approx(50000 + (85000 - 84030) * 0.1)
    assert b.buying_power("USD") <= b.equity("USD", [])  # 1x, no 1000x


# --- órdenes ----------------------------------------------------------------------------------------
def test_buy_converts_units_to_lots_and_uses_ask_and_bot_magic():
    b, fake = broker()
    fill = b.market_buy("BTCUSD", 0.237)  # se redondea al paso de 0.01
    req = fake.sent[-1]
    assert (
        req["volume"] == pytest.approx(0.23) and req["price"] == fake.ask and req["magic"] == MAGIC
    )
    assert fill.qty == pytest.approx(0.23) and fill.price == fake.ask and fill.net_qty == fill.qty
    with pytest.raises(BrokerError, match="mínimo"):
        b.market_buy("BTCUSD", 0.004)


def test_stop_loss_is_set_on_the_position_and_reported_open():
    b, fake = broker()
    b.market_buy("BTCUSD", 0.5)
    sid = b.place_stop_loss("BTCUSD", 0.5, 80000.1234, 79900.0)
    pos = next(iter(fake.positions.values()))
    assert sid == str(pos.ticket) and pos.sl == pytest.approx(80000.123)  # redondeado a 3 dígitos
    assert b.get_order("BTCUSD", sid).status == "open"


def test_stop_hit_on_server_is_reported_filled_with_costs():
    b, fake = broker()
    b.market_buy("BTCUSD", 0.5)
    sid = b.place_stop_loss("BTCUSD", 0.5, 80000.0, 79900.0)
    fake.trigger_stops(low=79000.0)
    info = b.get_order("BTCUSD", sid)
    assert info.status == "filled" and info.avg_price == 80000.0 and info.filled_qty == 0.5
    assert info.fee == pytest.approx(0.5 * 80000.0 * 0.001 + 3.0)  # comisión de salida + swap


def test_market_sell_closes_the_position_and_reports_exit_costs():
    b, fake = broker()
    b.market_buy("BTCUSD", 0.5)
    fill = b.market_sell("BTCUSD", 0.5)
    assert not fake.positions and fill.price == fake.bid
    assert fill.fee == pytest.approx(0.5 * fake.bid * 0.001 + 3.0)
    assert fake.sent[-1]["position"]  # en hedging se indica qué posición cerrar
    with pytest.raises(BrokerError, match="No hay posición"):
        b.market_sell("BTCUSD", 0.5)


def test_cancel_is_a_noop_so_a_failed_sell_keeps_the_position_protected():
    b, fake = broker()
    b.market_buy("BTCUSD", 0.5)
    sid = b.place_stop_loss("BTCUSD", 0.5, 80000.0, 79900.0)
    b.cancel_order("BTCUSD", sid)
    assert next(iter(fake.positions.values())).sl == 80000.0


def test_rejected_orders_raise_with_the_reason():
    b, fake = broker()
    fake.fail_retcode = 10019  # sin dinero
    with pytest.raises(BrokerError, match="10019"):
        b.market_buy("BTCUSD", 0.5)
    b.market_buy("BTCUSD", 0.5)
    with pytest.raises(BrokerError, match="10016"):
        b.place_stop_loss("BTCUSD", 0.5, fake.bid + 100, fake.bid + 50)  # SL por encima del precio


def test_position_closed_manually_is_reported_filled_not_lost():
    b, fake = broker()
    b.market_buy("BTCUSD", 0.5)
    sid = b.place_stop_loss("BTCUSD", 0.5, 80000.0, 79900.0)
    fake._close(next(iter(fake.positions.values())), 84500.0, fake.DEAL_REASON_CLIENT)
    assert b.get_order("BTCUSD", sid).status == "filled"
    assert b.get_order("BTCUSD", "999999").status == "unknown"

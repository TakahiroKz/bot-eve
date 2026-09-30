import ccxt
import pandas as pd
import pytest

from bot_eve.common.config import load_config
from bot_eve.execution.base import BrokerError, Fill, fee_in_quote
from bot_eve.execution.binance import BinanceBroker, to_ccxt_symbol
from bot_eve.execution.factory import make_broker


class FakeExchange:
    def __init__(self, opts):
        self.opts, self.sandbox, self.calls = opts, False, []
        self.orders = {}
        self.fail = None

    def set_sandbox_mode(self, enable):
        self.sandbox = enable

    def load_markets(self):
        self.calls.append(("load_markets",))

    def market(self, symbol):
        return {
            "info": {
                "filters": [
                    {"filterType": "LOT_SIZE", "minQty": "0.00001", "stepSize": "0.00001"},
                    {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
                ]
            }
        }

    def milliseconds(self):
        return 0

    def fetch_time(self):
        return int(pd.Timestamp("2024-01-01 01:00:30", tz="UTC").timestamp() * 1000)

    def fetch_ohlcv(self, symbol, tf, limit):
        self.calls.append(("ohlcv", symbol, tf, limit))
        base = pd.Timestamp("2024-01-01 00:00", tz="UTC")
        rows = []
        for i in range(4):  # 00:00, 00:15, 00:30, 00:45 (la última aún abierta a las 01:00:30? no)
            ts = int((base + pd.Timedelta(minutes=15 * i)).timestamp() * 1000)
            rows.append([ts, 100 + i, 101 + i, 99 + i, 100.5 + i, 10 + i])
        rows.append([int((base + pd.Timedelta(hours=1)).timestamp() * 1000), 1, 2, 0.5, 1.5, 1])
        return rows  # la última es la vela de las 01:00, en formación a las 01:00:30

    def fetch_ticker(self, symbol):
        return {"last": 123.4}

    def fetch_balance(self):
        return {"free": {"USDT": 1000.5, "BTC": 0.25}}

    def create_order(self, symbol, typ, side, amount, price=None, params=None):
        if self.fail:
            raise self.fail
        self.calls.append(("create_order", symbol, typ, side, amount, price, params))
        oid = str(len(self.orders) + 1)
        order = {"id": oid, "status": "closed", "filled": amount, "average": 100.0,
                 "timestamp": 1_700_000_000_000,
                 "fees": [{"currency": "BTC", "cost": amount * 0.001}]}  # fmt: skip
        self.orders[oid] = order
        return order

    def fetch_order(self, oid, symbol):
        if oid == "missing":
            raise ccxt.OrderNotFound("x")
        return {"id": oid, "status": "open", "filled": 0, "average": None}

    def cancel_order(self, oid, symbol):
        self.calls.append(("cancel", oid))
        if oid == "gone":
            raise ccxt.OrderNotFound("x")


def make(testnet=True, prod_data=True):
    made = []

    def factory(opts):
        ex = FakeExchange(opts)
        made.append(ex)
        return ex

    return BinanceBroker("k", "s", testnet=testnet, data_from_production=prod_data,
                         exchange_factory=factory), made  # fmt: skip


def test_symbol_conversion():
    assert to_ccxt_symbol("BTCUSDT") == "BTC/USDT"
    assert to_ccxt_symbol("BNBUSDT") == "BNB/USDT"
    with pytest.raises(BrokerError):
        to_ccxt_symbol("XYZ")


def test_testnet_uses_sandbox_and_public_data_from_production():
    broker, made = make(testnet=True, prod_data=True)
    trade_ex, data_ex = made
    assert trade_ex.sandbox and not data_ex.sandbox
    assert "apiKey" in trade_ex.opts and "apiKey" not in data_ex.opts  # datos sin claves
    assert not broker.is_real_money
    broker.get_candles("BTCUSDT", "15m", 10)
    assert any(c[0] == "ohlcv" for c in data_ex.calls)
    assert not any(c[0] == "ohlcv" for c in trade_ex.calls)


def test_live_is_flagged_as_real_money_and_not_sandboxed():
    broker, made = make(testnet=False)
    assert broker.is_real_money and not made[0].sandbox and len(made) == 1


def test_candles_exclude_the_forming_candle():
    broker, _ = make()
    df = broker.get_candles("BTCUSDT", "15m", 10)
    assert len(df) == 4 and df.index[-1] == pd.Timestamp("2024-01-01 00:45", tz="UTC")
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is not None and df["close"].dtype == float


def test_symbol_rules_are_parsed_from_exchange_filters():
    rules = make()[0].get_symbol_rules("BTCUSDT")
    assert (rules.step_size, rules.min_qty, rules.min_notional) == (1e-5, 1e-5, 5.0)


def test_market_buy_fill_accounts_for_fee_paid_in_base_asset():
    broker, _ = make()
    fill = broker.market_buy("BTCUSDT", 0.5)
    assert isinstance(fill, Fill) and fill.price == 100.0
    assert fill.fee_asset == "BTC" and fill.fee == pytest.approx(0.0005)
    assert fill.net_qty == pytest.approx(0.4995)  # lo recibido, no lo pedido
    assert fee_in_quote(fill) == pytest.approx(0.05)


def test_stop_loss_is_sent_as_stop_limit_sell():
    broker, made = make()
    oid = broker.place_stop_loss("BTCUSDT", 0.4995, 98.0, 97.7)
    call = [c for c in made[0].calls if c[0] == "create_order"][-1]
    assert call[1:6] == ("BTC/USDT", "limit", "sell", 0.4995, 97.7)
    assert call[6]["stopLossPrice"] == 98.0 and call[6]["timeInForce"] == "GTC"
    assert oid == "1"


def test_get_order_and_cancel_tolerate_missing_orders():
    broker, _ = make()
    assert broker.get_order("BTCUSDT", "5").status == "open"
    assert broker.get_order("BTCUSDT", "missing").status == "unknown"
    broker.cancel_order("BTCUSDT", "gone")  # no debe lanzar


def test_exchange_errors_are_wrapped():
    broker, made = make()
    made[0].fail = ccxt.InsufficientFunds("sin saldo")
    with pytest.raises(BrokerError, match="InsufficientFunds"):
        broker.market_buy("BTCUSDT", 1)


def test_balance_and_price():
    broker, _ = make()
    assert broker.get_balance("USDT") == 1000.5 and broker.get_balance("ETH") == 0.0
    assert broker.get_price("BTCUSDT") == 123.4


def test_server_clock_offset_is_used():
    broker, _ = make()
    assert abs((broker.now() - pd.Timestamp("2024-01-01 01:00:30", tz="UTC")).total_seconds()) < 5


# --- fábrica y protecciones de dinero real -------------------------------------------------
def cfg_with(tmp_path, **execution):
    body = "\n".join(f"  {k}: {v}" for k, v in execution.items())
    f = tmp_path / "c.yaml"
    f.write_text(f"execution:\n{body}\n")
    return load_config(f)


def test_factory_requires_keys(tmp_path, monkeypatch):
    for name in ("BINANCE_TESTNET_API_KEY", "BINANCE_TESTNET_API_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)  # sin .env
    with pytest.raises(BrokerError, match="Faltan las claves"):
        make_broker(cfg_with(tmp_path, mode="demo"))


def test_factory_builds_testnet_broker_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BINANCE_TESTNET_API_KEY", "k")
    monkeypatch.setenv("BINANCE_TESTNET_API_SECRET", "s")
    broker = make_broker(cfg_with(tmp_path, mode="demo"))
    assert not broker.is_real_money and broker.testnet


@pytest.mark.parametrize(
    ("config_flag", "cli_flag"), [(False, False), (True, False), (False, True)]
)
def test_live_needs_both_confirmations(tmp_path, monkeypatch, config_flag, cli_flag):
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_API_SECRET", "s")
    cfg = cfg_with(tmp_path, mode="live", i_understand_real_money=str(config_flag).lower())
    with pytest.raises(BrokerError, match="live"):
        make_broker(cfg, allow_real_money=cli_flag)


def test_live_with_both_confirmations_builds_real_money_broker(tmp_path, monkeypatch):
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_API_SECRET", "s")
    cfg = cfg_with(tmp_path, mode="live", i_understand_real_money="true")
    assert make_broker(cfg, allow_real_money=True).is_real_money


def test_clock_syncs_on_first_call_even_right_after_boot(monkeypatch):
    """Con el equipo recién encendido (reloj monotónico < 10 min) también debe sincronizar."""
    import time as time_module

    monkeypatch.setattr(time_module, "monotonic", lambda: 5.0)
    broker, _ = make()
    assert abs((broker.now() - pd.Timestamp("2024-01-01 01:00:30", tz="UTC")).total_seconds()) < 5
    assert len(broker.get_candles("BTCUSDT", "15m", 10)) == 4  # excluye la vela en formación

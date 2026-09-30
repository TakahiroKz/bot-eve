import pytest
from conftest import make_candles

import bot_eve.engine.__main__ as cli
from bot_eve.execution.memory import InMemoryBroker


@pytest.fixture
def cfg_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("BINANCE_TESTNET_API_KEY", "BINANCE_TESTNET_API_SECRET"):
        monkeypatch.delenv(name, raising=False)
    f = tmp_path / "c.yaml"
    f.write_text(
        f"execution:\n  state_dir: {tmp_path / 'state'}\nlogging:\n  file: null\n"
        "data:\n  symbols: [BTCUSDT]\n"
    )
    return f


def fake_broker():
    b = InMemoryBroker({"USDT": 1000.0})
    b.prices["BTCUSDT"] = 100.0
    b.candles[("BTCUSDT", "15m")] = make_candles("2024-01-01", 20, "15min")
    b.set_time("2024-01-01 06:00")
    return b


def test_kill_unkill_and_status(cfg_path, tmp_path, capsys):
    base = ["--config", str(cfg_path)]
    assert cli.main([*base, "kill"]) == 0
    assert (tmp_path / "state" / "KILL").exists()
    assert cli.main([*base, "status"]) == 0
    assert "KILL activo" in capsys.readouterr().out
    assert cli.main([*base, "unkill"]) == 0
    assert not (tmp_path / "state" / "KILL").exists()


def test_run_without_keys_fails_with_clear_message(cfg_path, capsys):
    assert cli.main(["--config", str(cfg_path), "run", "--once"]) == 2
    assert "Faltan las claves" in capsys.readouterr().out


def test_live_mode_is_refused_without_confirmations(cfg_path, capsys, monkeypatch):
    cfg_path.write_text(cfg_path.read_text().replace("execution:\n", "execution:\n  mode: live\n"))
    monkeypatch.setenv("BINANCE_API_KEY", "k")
    monkeypatch.setenv("BINANCE_API_SECRET", "s")
    assert cli.main(["--config", str(cfg_path), "run", "--once", "--yes-real-money"]) == 2
    assert "i_understand_real_money" in capsys.readouterr().out


def test_check_reports_connection_without_trading(cfg_path, monkeypatch, capsys):
    broker = fake_broker()
    monkeypatch.setattr(cli, "make_broker", lambda cfg, allow_real_money=False: broker)
    assert cli.main(["--config", str(cfg_path), "check"]) == 0
    out = capsys.readouterr().out
    assert "Saldo libre USDT" in out and "BTCUSDT" in out and "No se envió ninguna orden" in out
    assert broker.fills == []


def test_roundtrip_buys_stops_cancels_and_sells_on_testnet(cfg_path, monkeypatch, capsys):
    broker = fake_broker()
    monkeypatch.setattr(cli, "make_broker", lambda cfg, allow_real_money=False: broker)
    assert cli.main(["--config", str(cfg_path), "check", "--roundtrip", "BTCUSDT"]) == 0
    assert [f.side for f in broker.fills] == ["buy", "sell"]
    assert all(o["status"] == "canceled" for o in broker.orders.values())
    assert broker.get_balance("BTC") == pytest.approx(0.0, abs=1e-4)
    assert "camino completo" in capsys.readouterr().out


def test_roundtrip_is_refused_with_real_money(cfg_path, monkeypatch, capsys):
    broker = fake_broker()
    broker.is_real_money = True
    monkeypatch.setattr(cli, "make_broker", lambda cfg, allow_real_money=False: broker)
    assert cli.main(["--config", str(cfg_path), "check", "--roundtrip", "BTCUSDT"]) == 2
    assert broker.fills == []


def test_run_with_no_active_strategies_explains_why(cfg_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "make_broker", lambda cfg, allow_real_money=False: fake_broker())
    assert cli.main(["--config", str(cfg_path), "run", "--once"]) == 1
    assert "No hay estrategias activas" in capsys.readouterr().out

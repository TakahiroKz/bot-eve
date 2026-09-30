import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from bot_eve.common.config import Config, DashboardBot, DashboardConfig
from bot_eve.dashboard.app import create_app
from bot_eve.dashboard.data import pnl_curve, read_status, read_trades, trade_stats

TOKEN = "clave-de-prueba-123"


def write_status(path, age_s=5, **over):
    status = {
        "updated_at": (datetime.now(UTC) - timedelta(seconds=age_s)).isoformat(),
        "label": "binance demo", "mode": "demo", "real_money": False, "equity": 10000.0,
        "day_start_equity": 9900.0, "day_pnl_pct": 0.0101, "consecutive_errors": 0,
        "kill_active": False, "poll_seconds": 20, "positions": [], "slots": [],
    }  # fmt: skip
    status.update(over)
    path.mkdir(parents=True, exist_ok=True)
    (path / "status.json").write_text(json.dumps(status))


def write_trades(path, pnls, symbol="BTCUSDT"):
    path.mkdir(parents=True, exist_ok=True)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    lines = [
        json.dumps({"symbol": symbol, "pnl": p, "reason": "stop" if p < 0 else "signal",
                    "exit_time": (base + timedelta(days=i)).isoformat(), "return_pct": p / 100})
        for i, p in enumerate(pnls)
    ]  # fmt: skip
    (path / "trades.jsonl").write_text("\n".join(lines) + "\n")


@pytest.fixture
def env(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    bots = [DashboardBot(name="Bot A", state_dir=a), DashboardBot(name="Bot <b>B</b>", state_dir=b)]
    client = TestClient(
        create_app(Config(dashboard=DashboardConfig(bots=bots)), TOKEN), base_url="http://localhost"
    )
    return client, a, b


# --- datos ------------------------------------------------------------------------------------------
def test_trade_stats_and_curve():
    trades = [{"pnl": 10.0, "reason": "signal", "exit_time": "2026-01-02"},
              {"pnl": -4.0, "reason": "stop", "exit_time": "2026-01-01"},
              {"pnl": 6.0, "reason": "signal", "exit_time": "2026-01-03"}]  # fmt: skip
    st = trade_stats(trades)
    assert st["trades"] == 3 and st["wins"] == 2 and st["total_pnl"] == 12.0
    assert st["profit_factor"] == pytest.approx(16 / 4) and st["by_reason"] == {
        "signal": 2,
        "stop": 1,
    }
    assert [p["cum_pnl"] for p in pnl_curve(trades)] == [-4.0, 6.0, 12.0]  # ordenado por cierre
    empty = trade_stats([])
    assert empty["trades"] == 0 and empty["win_rate"] is None and empty["profit_factor"] is None
    winners = trade_stats([{"pnl": 5.0}])  # solo ganadoras: no hay infinito (JSON no lo admite)
    assert winners["profit_factor"] is None and winners["no_losses"] is True
    json.dumps(winners)  # debe serializarse


def test_corrupt_lines_and_files_do_not_break_the_reader(tmp_path):
    (tmp_path / "trades.jsonl").write_text(
        '{"pnl": 1.0}\nNO ES JSON\n{"sin_pnl": 1}\n[1,2]\n{"pnl": 2.0}\n'
    )
    assert [t["pnl"] for t in read_trades(tmp_path)] == [1.0, 2.0]
    (tmp_path / "status.json").write_text("{ a medias")
    assert read_status(tmp_path) is None and read_status(tmp_path / "nope") is None


# --- API ----------------------------------------------------------------------------------------------
def test_overview_reports_online_offline_and_missing(env):
    client, a, b = env
    write_status(a, age_s=5)
    write_trades(a, [10, -5, 8])
    data = client.get("/api/overview").json()
    bot_a, bot_b = data["bots"]
    assert (
        bot_a["online"] and bot_a["stats"]["trades"] == 3 and bot_a["status"]["equity"] == 10000.0
    )
    assert not bot_b["online"] and bot_b["status"] is None  # nunca arrancó
    assert data["actions_enabled"] is True
    write_status(a, age_s=3600)
    assert client.get("/api/overview").json()["bots"][0]["online"] is False  # sin latido


def test_a_bot_with_only_winning_trades_does_not_break_the_api(env):
    client, a, _ = env
    write_trades(a, [5.0, 7.0])
    write_status(a)
    body = client.get("/api/overview").json()
    assert body["bots"][0]["stats"]["no_losses"] is True
    assert client.get("/api/bots/0/trades").status_code == 200


def test_trades_endpoint_limits_orders_and_builds_curve(env):
    client, a, _ = env
    write_trades(a, list(range(1, 11)))
    body = client.get("/api/bots/0/trades?limit=3").json()
    assert [t["pnl"] for t in body["trades"]] == [10, 9, 8]  # las más recientes primero
    assert len(body["curve"]) == 10 and body["curve"][-1]["cum_pnl"] == 55
    assert client.get("/api/bots/7/trades").status_code == 404


# --- seguridad -------------------------------------------------------------------------------------------
def test_kill_requires_the_token_and_creates_the_kill_file(env):
    client, a, _ = env
    assert client.post("/api/bots/0/kill").status_code == 403
    assert client.post("/api/bots/0/kill", headers={"X-Dashboard-Token": "otra"}).status_code == 403
    assert not (a / "KILL").exists()
    ok = client.post("/api/bots/0/kill", headers={"X-Dashboard-Token": TOKEN})
    assert ok.status_code == 200 and (a / "KILL").exists()
    assert client.get("/api/overview").json()["bots"][0]["kill_file"] is True
    assert (
        client.post("/api/bots/0/unkill", headers={"X-Dashboard-Token": TOKEN}).status_code == 200
    )
    assert not (a / "KILL").exists()
    assert client.post("/api/bots/9/kill", headers={"X-Dashboard-Token": TOKEN}).status_code == 404


def test_actions_are_disabled_without_a_configured_token(tmp_path):
    bots = [DashboardBot(name="A", state_dir=tmp_path)]
    client = TestClient(
        create_app(Config(dashboard=DashboardConfig(bots=bots)), None), base_url="http://localhost"
    )
    r = client.post("/api/bots/0/kill", headers={"X-Dashboard-Token": ""})
    assert r.status_code == 403 and "DASHBOARD_TOKEN" in r.json()["detail"]
    assert not (tmp_path / "KILL").exists()
    assert client.get("/api/overview").json()["actions_enabled"] is False


def test_foreign_host_headers_are_rejected_against_dns_rebinding(env):
    client, _, _ = env
    assert client.get("/api/overview", headers={"Host": "evil.example.com"}).status_code == 400
    assert client.get("/api/overview", headers={"Host": "localhost:8765"}).status_code == 200
    assert client.get("/api/overview", headers={"Host": "127.0.0.1:8765"}).status_code == 200


def test_page_has_strict_csp_with_nonce_and_no_external_resources(env):
    client, _, _ = env
    r = client.get("/")
    csp = r.headers["content-security-policy"]
    nonce = csp.split("script-src 'nonce-")[1].split("'")[0]
    assert f'<script nonce="{nonce}">' in r.text and f'<style nonce="{nonce}">' in r.text
    assert (
        "default-src 'none'" in csp
        and "frame-ancestors 'none'" in csp
        and "unsafe-inline" not in csp
    )
    assert (
        r.headers["cache-control"] == "no-store"
        and r.headers["x-content-type-options"] == "nosniff"
    )
    assert "https://" not in r.text and "http://" not in r.text.replace(
        "http://www.w3.org/2000/svg", ""
    )
    assert "onclick=" not in r.text and 'style="' not in r.text  # incompatibles con la CSP
    assert client.get("/").headers["content-security-policy"] != csp  # nonce distinto en cada carga


def test_page_inserts_data_with_textcontent_never_innerhtml(env):
    client, _, _ = env
    assert "innerHTML" not in client.get("/").text  # un nombre como «<b>B</b>» nunca se interpreta


def test_no_docs_or_openapi_are_exposed_and_favicon_is_quiet(env):
    client, _, _ = env
    assert client.get("/docs").status_code == 404 and client.get("/openapi.json").status_code == 404
    assert client.get("/favicon.ico").status_code == 204


def test_cli_refuses_to_listen_outside_localhost(capsys):
    from bot_eve.dashboard.__main__ import main

    assert main(["--host", "0.0.0.0"]) == 2
    assert "Rechazado" in capsys.readouterr().out

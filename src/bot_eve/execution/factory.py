"""Construye el broker según la configuración, con protecciones contra dinero real accidental."""

from __future__ import annotations

import os

from bot_eve.common.config import Config
from bot_eve.execution.base import Broker, BrokerError


def _confirm_live(cfg: Config, allow_real_money: bool) -> None:
    ex = cfg.execution
    if not (ex.i_understand_real_money and allow_real_money):
        raise BrokerError(
            "Modo live: requiere `execution.i_understand_real_money: true` en la "
            "configuración Y la opción --yes-real-money en la línea de comandos."
        )


def _make_mt5(cfg: Config, allow_real_money: bool) -> Broker:
    from bot_eve.execution.mt5 import Mt5Broker

    ex = cfg.execution
    if ex.mode == "live":
        _confirm_live(cfg, allow_real_money)
    symbols = next(iter(cfg.active_strategies(ex.mode).values()), None)
    reference = (symbols.symbols[0] if symbols and symbols.symbols else None) or cfg.data.symbols[0]
    broker = Mt5Broker(reference_symbol=reference)
    # La cuenta manda, no la configuración: una demo nunca debe operar sobre una cuenta real.
    if ex.mode == "demo" and broker.is_real_money:
        broker.close()
        raise BrokerError(
            "La cuenta conectada en MT5 es REAL pero el modo es demo. Cambia a la cuenta demo en "
            "MetaTrader (y vuelve a activar Algo Trading) o revisa `execution.mode`."
        )
    return broker


def make_broker(cfg: Config, allow_real_money: bool = False) -> Broker:
    """`allow_real_money` debe venir de una opción explícita en la línea de comandos."""
    from bot_eve.execution.binance import BinanceBroker

    ex = cfg.execution
    if ex.broker == "mt5":
        return _make_mt5(cfg, allow_real_money)
    if ex.mode == "live":
        _confirm_live(cfg, allow_real_money)
        key, secret = os.getenv("BINANCE_API_KEY", ""), os.getenv("BINANCE_API_SECRET", "")
        names = "BINANCE_API_KEY / BINANCE_API_SECRET"
    else:
        key = os.getenv("BINANCE_TESTNET_API_KEY", "")
        secret = os.getenv("BINANCE_TESTNET_API_SECRET", "")
        names = "BINANCE_TESTNET_API_KEY / BINANCE_TESTNET_API_SECRET"
    if not key or not secret:
        raise BrokerError(f"Faltan las claves en el archivo .env ({names}).")
    return BinanceBroker(
        key, secret, testnet=ex.mode == "demo", data_from_production=ex.data_from_production
    )

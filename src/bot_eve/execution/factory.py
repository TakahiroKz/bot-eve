"""Construye el broker según la configuración, con protecciones contra dinero real accidental."""

from __future__ import annotations

import os

from bot_eve.common.config import Config
from bot_eve.execution.base import Broker, BrokerError


def make_broker(cfg: Config, allow_real_money: bool = False) -> Broker:
    """`allow_real_money` debe venir de una opción explícita en la línea de comandos."""
    from bot_eve.execution.binance import BinanceBroker

    ex = cfg.execution
    if ex.mode == "live":
        if not (ex.i_understand_real_money and allow_real_money):
            raise BrokerError(
                "Modo live: requiere `execution.i_understand_real_money: true` en la "
                "configuración Y la opción --yes-real-money en la línea de comandos."
            )
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

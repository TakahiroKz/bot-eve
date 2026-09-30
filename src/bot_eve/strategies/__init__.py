"""Estrategias disponibles.

Cualquier módulo nuevo en este paquete que use `@register` se descubre solo: no hay que
editar este archivo. Para quitar una estrategia basta con borrar su módulo (o ponerla en
`enabled: false` en la configuración si solo debe dejar de operar).
"""

from __future__ import annotations

import importlib
import pkgutil

from bot_eve.strategies.registry import REGISTRY, build_strategy, register

_SKIP = {"base", "registry", "indicators"}

for _mod in pkgutil.iter_modules(__path__):
    if _mod.name not in _SKIP and not _mod.name.startswith("_"):
        importlib.import_module(f"{__name__}.{_mod.name}")

__all__ = ["REGISTRY", "build_strategy", "register"]

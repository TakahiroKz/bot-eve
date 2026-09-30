"""Logging a consola y, opcionalmente, a archivo."""

from __future__ import annotations

import logging
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(level: str = "INFO", file: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if file is not None:
        file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(file, encoding="utf-8"))
    logging.basicConfig(level=level.upper(), format=_FORMAT, handlers=handlers, force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # una línea por descarga es ruido

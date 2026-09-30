# bot-eve

Bot de trading automático (Binance spot y MetaTrader 5). Ver [PLAN.md](PLAN.md) para el plan completo.

Estado: **Fase 1 (datos) completada**. Aún no hay estrategias ni ejecución.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"
```

## Datos (Fase 1)

Descarga velas de 1m desde `data.binance.vision` (datos públicos, sin API key) y genera 5m, 15m, 1h y 4h.

```bash
python -m bot_eve.data sync                        # todos los pares desde 2020-01
python -m bot_eve.data sync --symbols BTCUSDT --start 2024-01
python -m bot_eve.data validate                    # revisa calidad y escribe informes JSON
```

- Se guarda en `data_store/<SÍMBOLO>/<intervalo>/<YYYY-MM>.parquet` (ignorado por git).
- `sync` es reanudable: los meses cerrados y completos no se vuelven a descargar; el mes en curso se refresca siempre.
- `validate` deja informes en `data_store/reports/` con el detalle de huecos y outliers.
- Configuración en `config/default.yaml` (pares, mes inicial, intervalos).

Leer velas desde Python:

```python
from bot_eve.data.store import CandleStore
df = CandleStore("data_store").read("BTCUSDT", "15m", start="2024-01-01")
```

Cada vela remuestreada incluye `n_base` (cuántas velas de 1m la componen); si es menor que el intervalo, hubo un hueco.

## Desarrollo

```bash
pytest          # tests
ruff check .    # lint
ruff format .   # formato
```

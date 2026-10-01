"""Prueba pre-registrada de arbitraje estadístico (docs/SCALPING_RESEARCH.md, familia 1)."""

import itertools

import pandas as pd

from bot_eve.backtest.pairs import simulate_pairs, spread_z
from bot_eve.backtest.scalp import ScalpCosts
from bot_eve.data.store import CandleStore

SYMS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
CUT = pd.Timestamp("2025-07-01", tz="UTC")
F, S = ScalpCosts(0.0004, 0.0002), ScalpCosts(0.001, 0.0005)
store = CandleStore("data_store")
cache = {}


def trades(tf, a, b, costs, start=None, end=None):
    if (tf, a, b) not in cache:
        da, db = store.read(a, tf), store.read(b, tf)
        ix = da.index.intersection(db.index)
        da, db = da.loc[ix], db.loc[ix]
        z, beta = spread_z(da["close"], db["close"])
        cache[(tf, a, b)] = (
            da["open"].to_numpy(),
            db["open"].to_numpy(),
            z.to_numpy(),
            beta.to_numpy(),
            ix,
        )
    o1, o2, z, beta, ix = cache[(tf, a, b)]
    return simulate_pairs(o1, o2, z, beta, ix, costs=costs, start=start, end=end)


def stats(tf, costs, start=None, end=None):
    per = {
        f"{a[:-4]}/{b[:-4]}": trades(tf, a, b, costs, start, end)
        for a, b in itertools.combinations(SYMS, 2)
    }
    allt = pd.concat(per.values(), ignore_index=True)
    r = allt["ret"].to_numpy()
    g, ls = r[r > 0].sum(), -r[r < 0].sum()
    yrs = allt.groupby(allt.entry_time.dt.year)["ret"].mean().loc[2021:2025]
    return {"marco": tf, "ops": len(r), "gana%": round((r > 0).mean() * 100), "media_bp": round(r.mean() * 1e4, 1),
            "PF": round(g / ls, 2) if ls else None, "años+": f"{int((yrs > 0).sum())}/{len(yrs)}",
            "pares+": f"{sum(1 for t in per.values() if len(t) and t.ret.mean() > 0)}/6",
            "salidas": allt.reason.value_counts().to_dict()}  # fmt: skip


dev_end = CUT - pd.Timedelta(seconds=1)
pd.set_option("display.width", 200)
for label, c in [("F", F), ("S", S)]:
    print(f"DESARROLLO, costos {label}")
    print(pd.DataFrame([stats(tf, c, end=dev_end) for tf in ("15m", "1h")]).to_string(index=False))

"""Cota optimista de market making con velas de 1m (docs/SCALPING_RESEARCH.md, familia 3)."""

import numpy as np
import pandas as pd

from bot_eve.data.store import CandleStore

CUT = pd.Timestamp("2025-07-01", tz="UTC")
TAKER, SLIP, MAX_HOLD = 0.0004, 0.0002, 60
store = CandleStore("data_store")


def run(df, h, maker):
    o, hi, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    n = len(df)
    nets, kinds = [], []
    i = 1
    while i < n - 1:
        bid, ask = c[i - 1] * (1 - h), c[i - 1] * (1 + h)
        got_b, got_a = lo[i] <= bid, hi[i] >= ask
        if not (got_b or got_a):
            i += 1
            continue
        if got_b and got_a:  # viaje completo (optimista)
            nets.append(2 * h - 2 * maker)
            kinds.append("ambos")
            i += 1
            continue
        side = 1 if got_b else -1
        px = bid if got_b else ask
        tgt = px * (1 + side * 2 * h)
        j, done = i + 1, False
        while j < min(i + 1 + MAX_HOLD, n):
            if (side == 1 and hi[j] >= tgt) or (side == -1 and lo[j] <= tgt):
                nets.append(2 * h - 2 * maker)
                kinds.append("objetivo")
                done = True
                break
            j += 1
        if not done:
            j = min(i + MAX_HOLD, n - 1)
            xp = c[j] * (1 - side * SLIP)
            nets.append(side * (xp - px) / px - maker - TAKER)
            kinds.append("liquida")
        i = j + 1
    return np.array(nets), pd.Series(kinds)


rows = []
for sym in ("BTCUSDT", "ETHUSDT"):
    df = store.read(sym, "1m")
    df = df[df.index < CUT]
    for h in (0.0005, 0.001, 0.002):
        for maker in (0.00075, 0.0002, -0.0001):
            r, k = run(df, h, maker)
            rows.append({"par": sym[:3], "h_pb": h * 1e4, "maker_%": maker * 100, "viajes": len(r), "media_pb": round(r.mean() * 1e4, 2),
                         "%liquidados": round((k == "liquida").mean() * 100)})  # fmt: skip
pd.set_option("display.width", 200)
print(pd.DataFrame(rows).to_string(index=False))

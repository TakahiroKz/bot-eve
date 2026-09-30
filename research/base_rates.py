"""Tasas base de acierto con entradas al azar (triple barrera) y mejora necesaria para cubrir costos.

Reproduce la tabla de docs/AI_TRADER_PLAN.md (sección 9). Solo usa datos de desarrollo
(anteriores a backtest.holdout_start). Ejecutar desde la raíz:  python research/base_rates.py
Las velas de 4h se alinean por su hora de CIERRE: nunca se usa una vela de 4h todavía abierta.
"""
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv
from bot_eve.common.config import load_config
from bot_eve.data.store import CandleStore
from bot_eve.backtest.walkforward import split_holdout
from bot_eve.strategies import indicators as ind
COST=0.0020   # ida y vuelta: comisión 0.15% + slippage 0.05%
cfg=load_config(); store=CandleStore(cfg.data.dir)

def triple_barrier(df, tp, sl, horizon, mask=None, step=1):
    """Entra en la apertura de la vela siguiente. Gana si toca +tp antes que -sl (si ambos en la misma vela: pierde)."""
    o,h,l,c=(df[k].to_numpy() for k in ("open","high","low","close"))
    n=len(df)-horizon-2
    idx=np.arange(0,n,step)
    if mask is not None: idx=idx[mask[idx]]
    win=np.empty(len(idx),bool); los=np.empty(len(idx),bool); ret=np.empty(len(idx))
    CH=200_000
    Hw=swv(h[1:],horizon); Lw=swv(l[1:],horizon); Cw=swv(c[1:],horizon); O=o[1:]
    for a in range(0,len(idx),CH):
        ii=idx[a:a+CH]; e=O[ii]; hi=Hw[ii]; lo=Lw[ii]
        t=hi>=(e*(1+tp))[:,None]; s=lo<=(e*(1-sl))[:,None]
        ft=np.where(t.any(1),t.argmax(1),horizon+1); fs=np.where(s.any(1),s.argmax(1),horizon+1)
        w=ft<fs; lo_=fs<=ft; to=~(w|lo_)
        r=np.where(w,tp,np.where(lo_,-sl,Cw[ii][:,-1]/e-1))
        win[a:a+CH]=w; los[a:a+CH]=lo_; ret[a:a+CH]=r
    return win,los,ret

def row(label,win,los,ret,tp,sl):
    p=win.mean(); q=los.mean(); be=(sl+COST)/(tp+sl)
    return dict(caso=label,n=len(win),P_tp=f"{p:.1%}",P_sl=f"{q:.1%}",P_timeout=f"{1-p-q:.1%}",
                esperanza_bruta=f"{ret.mean():+.3%}",esperanza_neta=f"{ret.mean()-COST:+.3%}",acierto_necesario=f"{be:.1%}",
                mejora_necesaria=f"{(be-p)*100:+.1f} pts")
rows=[]
for sym in ("BTCUSDT","ETHUSDT"):
    # 1m (submuestreado cada 5 velas por memoria), 5m y 15m
    for itv,step,cases in (("1m",5,[(0.003,0.0015,60),(0.005,0.0025,60)]),
                           ("5m",1,[(0.005,0.0025,48),(0.0075,0.00375,48)]),
                           ("15m",1,[(0.010,0.005,96),(0.015,0.0075,96)])):
        df,_=split_holdout(store.read(sym,itv),cfg.backtest.holdout_start)
        for tp,sl,hz in cases:
            w,l,r=triple_barrier(df,tp,sl,hz,step=step)
            rows.append({"par":sym,"vela":itv,"TP/SL":f"+{tp:.2%}/-{sl:.2%}",**row("todas las velas",w,l,r,tp,sl)})
    # 15m con filtro de 4h: solo entrar si el último cierre de 4h está sobre su EMA(50)
    d15,_=split_holdout(store.read(sym,"15m"),cfg.backtest.holdout_start)
    d4,_=split_holdout(store.read(sym,"4h"),cfg.backtest.holdout_start)
    up=(d4["close"]>ind.ema(d4["close"],50))
    up_closed=up.copy(); up_closed.index=d4.index+pd.Timedelta(hours=4)        # disponible solo al CERRAR la vela de 4h (sin ver el futuro)
    m=up_closed.reindex(d15.index,method="ffill").fillna(False).to_numpy().astype(bool)
    for tp,sl,hz in ((0.010,0.005,96),):
        w,l,r=triple_barrier(d15,tp,sl,hz,mask=m)
        rows.append({"par":sym,"vela":"15m","TP/SL":f"+{tp:.2%}/-{sl:.2%}",**row("solo con 4h alcista",w,l,r,tp,sl)})
        w,l,r=triple_barrier(d15,tp,sl,hz,mask=~m)
        rows.append({"par":sym,"vela":"15m","TP/SL":f"+{tp:.2%}/-{sl:.2%}",**row("solo con 4h NO alcista",w,l,r,tp,sl)})
pd.set_option("display.width",250); pd.set_option("display.max_columns",20)
print(pd.DataFrame(rows).to_string(index=False))

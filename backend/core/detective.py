"""Detektif pasar (murni): temuan anomali pada bar terakhir tiap ticker.

3 sinyal: volume tak wajar, breakout 52-minggu, tren konsisten. Output dict temuan
dengan "mengapa" singkat (explainable, tanpa black box).
"""
from __future__ import annotations

import pandas as pd

from backend.core import indicators

VOL_SPIKE = 2.5      # volume >= 2.5x rata-rata 20 hari
BREAKOUT_EPS = 0.1   # close >= high52w - 0.1% dianggap breakout
STREAK_MIN = 5       # >=5 hari naik beruntun
STREAK_MIN_VOL = 500_000  # streak hanya untuk saham cukup likuid


def _findings(ticker: str, bars: pd.DataFrame) -> list[dict]:
    if bars is None or len(bars) < 60:
        return []
    enr = indicators.enrichment(bars)
    last = enr.iloc[-1]
    found: list[dict] = []
    vr = last["vol_ratio20"]
    if pd.notna(vr) and vr >= VOL_SPIKE:
        found.append(
            {
                "ticker": ticker,
                "signal": "unusual_volume",
                "value": round(float(vr), 2),
                "detail": f"volume {float(vr):.1f}x rata-rata 20 hari",
                "close": round(float(last["close"]), 3),
                "date": last["date"],
            }
        )
    d52 = last["dist_high52w_pct"]
    if pd.notna(d52) and d52 >= -BREAKOUT_EPS:
        found.append(
            {
                "ticker": ticker,
                "signal": "breakout_52w",
                "value": round(float(d52), 2),
                "detail": "close menyentuh/melampaui high 52 minggu",
                "close": round(float(last["close"]), 3),
                "date": last["date"],
            }
        )
    tail = bars.tail(STREAK_MIN + 1)
    ups = (tail["close"].diff().dropna() > 0).sum()
    avg_vol = float(bars["volume"].tail(21).head(20).mean())
    if ups >= STREAK_MIN and avg_vol >= STREAK_MIN_VOL:
        found.append(
            {
                "ticker": ticker,
                "signal": "consistent_up",
                "value": int(ups),
                "detail": f"naik {int(ups)} hari beruntun",
                "close": round(float(last["close"]), 3),
                "date": last["date"],
            }
        )
    return found


def scan(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Loop semua ticker -> DataFrame temuan (kosong bila tidak ada)."""
    rows: list[dict] = []
    for ticker, bars in data.items():
        rows.extend(_findings(ticker, bars))
    if not rows:
        return pd.DataFrame(columns=["ticker", "signal", "value", "detail"])
    return pd.DataFrame(rows).sort_values(["signal", "value"], ascending=[True, False]).reset_index(drop=True)

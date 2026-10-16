"""Mesin screening multi-kriteria (murni) - menerima bars ternormalisasi, keluarkan baris kandidat.

Semua threshold punya default masuk akal untuk saham US likuid, bisa dioverride.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from backend.core import indicators


@dataclass
class ScreenerConfig:
    min_price: float = 5.0
    max_price: float = 10_000.0
    min_avg_volume_20d: float = 250_000.0      # likuiditas
    min_dollar_vol_20d: float = 2_000_000.0    # harga x volume rata-rata
    rsi_min: float = 45.0
    rsi_max: float = 75.0
    min_chg1_pct: float = 0.0                  # hari ini tidak boleh merah
    max_dist_high52w_pct: float = -10.0        # tidak lebih dari 10% di bawah puncak
    require_uptrend: bool = True               # close > ema20 > ema50
    weights: dict = field(
        default_factory=lambda: {"vol_ratio": 0.35, "chg5": 0.25, "dist52": 0.20, "rsi_pos": 0.20}
    )


DEFAULTS = ScreenerConfig()


def score_row(row: pd.Series, cfg: ScreenerConfig) -> float:
    """Skor 0..100: momentum volume terbesar bobot, lalu chg5, kedekatan puncak, posisi RSI."""
    w = cfg.weights
    vr = min(max((row["vol_ratio20"] - 1.0) / 2.0, 0.0), 1.0)          # 1x..3x -> 0..1
    chg5 = min(max(row["chg5_pct"] / 10.0, -1.0), 1.0)                  # -10%..+10% -> -1..1 -> 0..1
    chg5_n = (chg5 + 1.0) / 2.0
    dist = min(max(1.0 + row["dist_high52w_pct"] / 25.0, 0.0), 1.0)     # 0..-25% -> 1..0
    rsi_pos = 1.0 - abs(row["rsi14"] - 60.0) / 40.0                     # ideal di 60
    rsi_pos = min(max(rsi_pos, 0.0), 1.0)
    return round(100 * (w["vol_ratio"] * vr + w["chg5"] * chg5_n + w["dist52"] * dist + w["rsi_pos"] * rsi_pos), 1)


def passes(row: pd.Series, cfg: ScreenerConfig) -> bool:
    if not (cfg.min_price <= row["close"] <= cfg.max_price):
        return False
    if row["avg_vol20"] < cfg.min_avg_volume_20d:
        return False
    if row["avg_dollar_vol20"] < cfg.min_dollar_vol_20d:
        return False
    if not (cfg.rsi_min <= row["rsi14"] <= cfg.rsi_max):
        return False
    if row["chg1_pct"] < cfg.min_chg1_pct:
        return False
    if row["dist_high52w_pct"] < cfg.max_dist_high52w_pct:
        return False
    if cfg.require_uptrend and not (row["close"] > row["ema20"] > row["ema50"]):
        return False
    return True


def screen_one(ticker: str, bars: pd.DataFrame, cfg: ScreenerConfig | None = None) -> dict | None:
    """Evaluasi 1 ticker pada bar terakhir. None = tidak lolos / data kurang."""
    cfg = cfg or DEFAULTS
    if bars is None or len(bars) < 60:
        return None
    try:
        enr = indicators.enrichment(bars)
    except ValueError:
        return None
    last = enr.iloc[-1]
    # metode likuiditas dihitung dari window 20 hari SEBELUM hari terakhir (anti lookahead)
    avg_vol20 = float(bars["volume"].tail(21).head(20).mean())
    avg_dollar20 = float((bars["close"].tail(21).head(20) * bars["volume"].tail(21).head(20)).mean())
    row = last.copy()
    row["avg_vol20"] = avg_vol20
    row["avg_dollar_vol20"] = avg_dollar20
    rec = {
        "ticker": ticker,
        "date": last["date"],
        "close": round(float(last["close"]), 3),
        "avg_vol20": round(avg_vol20, 0),
        "avg_dollar_vol20": round(avg_dollar20, 0),
        "rsi14": round(float(last["rsi14"]), 1) if pd.notna(last["rsi14"]) else None,
        "vol_ratio20": round(float(last["vol_ratio20"]), 2) if pd.notna(last["vol_ratio20"]) else None,
        "gap_pct": round(float(last["gap_pct"]), 2) if pd.notna(last["gap_pct"]) else None,
        "chg1_pct": round(float(last["chg1_pct"]), 2) if pd.notna(last["chg1_pct"]) else None,
        "chg5_pct": round(float(last["chg5_pct"]), 2) if pd.notna(last["chg5_pct"]) else None,
        "chg20_pct": round(float(last["chg20_pct"]), 2) if pd.notna(last["chg20_pct"]) else None,
        "dist_high52w_pct": round(float(last["dist_high52w_pct"]), 2) if pd.notna(last["dist_high52w_pct"]) else None,
    }
    if any(rec[k] is None for k in ("rsi14", "vol_ratio20", "dist_high52w_pct")):
        return None
    if not passes(row, cfg):
        return None
    rec["score"] = score_row(last, cfg)
    return rec


def screen_many(data: dict[str, pd.DataFrame], cfg: ScreenerConfig | None = None) -> pd.DataFrame:
    """Loop dict {ticker: bars} -> DataFrame hasil terurut skor turun."""
    rows = []
    for ticker, bars in data.items():
        rec = screen_one(ticker, bars, cfg)
        if rec is not None:
            rows.append(rec)
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["ticker", "score"])
    return out.sort_values("score", ascending=False).reset_index(drop=True)

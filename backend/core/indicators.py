"""Indikator teknikal murni (pandas saja, tanpa TA-Lib) - semua fungsi menerima DataFrame bars.

Kontrak: kolom wajib date/open/high/low/close/volume, terurut tanggal naik.
Semua fungsi TIDAK memodifikasi input.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_PERIOD = 2


def _validate(df: pd.DataFrame, need: int = MIN_PERIOD) -> pd.DataFrame:
    if df is None or len(df) < need:
        raise ValueError(f"butuh minimal {need} bar, dapat {0 if df is None else len(df)}")
    return df


def ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI standar. Kasus khusus: avg_loss=0 -> 100, avg_gain=0 -> 0."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    # default: netral 50 saat avg_gain=0 dan avg_loss=0 (harga datar)
    out = pd.Series(50.0, index=close.index, dtype="float64")
    out[close.isna()] = np.nan
    only_gain = (avg_loss == 0) & (avg_gain > 0)
    out[only_gain] = 100.0
    has_loss = avg_loss > 0
    rs = avg_gain[has_loss] / avg_loss[has_loss]
    out[has_loss] = 100 - 100 / (1 + rs)
    return out


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    _validate(df)
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Volume hari ini dibanding rata-rata `period` hari sebelumnya (tanpa hari ini)."""
    _validate(volume.to_frame("v") if isinstance(volume, pd.Series) else volume)
    avg_prev = volume.shift(1).rolling(period, min_periods=period // 2).mean()
    return volume / avg_prev.replace(0, pd.NA)


def gap_pct(df: pd.DataFrame) -> pd.Series:
    """Gap open terhadap close kemarin, dalam persen."""
    _validate(df)
    prev_close = df["close"].shift(1)
    return (df["open"] - prev_close) / prev_close * 100.0


def change_pct(close: pd.Series, period: int = 1) -> pd.Series:
    """Perubahan persen `period` hari."""
    return close.pct_change(period) * 100.0


def high_52w(df: pd.DataFrame) -> pd.Series:
    """High tertinggi 252 hari terakhir (termasuk hari ini), NaN jika data kurang."""
    _validate(df, need=5)
    return df["high"].rolling(252, min_periods=60).max()


def distance_from_high52w_pct(df: pd.DataFrame) -> pd.Series:
    """Posisi close terhadap high 252-hari SEBELUM hari ini (anti lookahead).

    0 = menyamai puncak sebelumnya, -20 = 20% di bawah puncak. Bar pertama NaN.
    """
    prev_max = (
        df["high"].shift(1).rolling(252, min_periods=60).max()
    )  # high tertinggi s.d. kemarin
    return (df["close"] - prev_max) / prev_max * 100.0


def enrichment(bars: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan semua kolom indikator ke salinan bars - satu pintu untuk screener/detective."""
    _validate(bars, need=30)
    out = bars.copy()
    out["ema20"] = ema(out["close"], 20)
    out["ema50"] = ema(out["close"], 50)
    out["rsi14"] = rsi(out["close"], 14)
    out["atr14"] = atr(out, 14)
    out["vol_ratio20"] = volume_ratio(out["volume"], 20)
    out["gap_pct"] = gap_pct(out)
    out["chg1_pct"] = change_pct(out["close"], 1)
    out["chg5_pct"] = change_pct(out["close"], 5)
    out["chg20_pct"] = change_pct(out["close"], 20)
    out["dist_high52w_pct"] = distance_from_high52w_pct(out)
    return out

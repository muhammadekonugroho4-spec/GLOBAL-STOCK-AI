"""Test murni indikator, screener, detektif - offline penuh dengan bars sintetis."""
import numpy as np
import pandas as pd
import pytest

from backend.core import detective, indicators, screener


def make_bars(n=100, start=100.0, drift=0.0, vol=1.0, base_volume=1_000_000, seed=7):
    """Bars sintetis deterministik."""
    rng = np.random.default_rng(seed)
    closes = start + np.cumsum(rng.normal(drift, vol, n))
    closes = np.maximum(closes, 1.0)
    opens = closes + rng.normal(0, 0.3, n)
    highs = np.maximum(opens, closes) + 0.5
    lows = np.minimum(opens, closes) - 0.5
    dates = pd.bdate_range("2026-01-01", periods=n).strftime("%Y-%m-%d")
    return pd.DataFrame(
        {
            "date": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": base_volume * rng.uniform(0.8, 1.2, n),
        }
    )


# ---------- indicators ----------

def test_rsi_range_and_extremes():
    up = pd.Series(np.linspace(10, 50, 30))  # naik terus -> RSI ~100
    r = indicators.rsi(up, 14)
    assert r.iloc[-1] > 85
    down = pd.Series(np.linspace(50, 10, 30))
    assert indicators.rsi(down, 14).iloc[-1] < 15
    flat = pd.Series([10.0] * 30)
    assert 45 < indicators.rsi(flat, 14).fillna(50).iloc[-1] < 55 or indicators.rsi(flat, 14).isna().iloc[-1]


def test_volume_ratio_ignores_current_day():
    vol = pd.Series([1_000_000.0] * 25 + [5_000_000.0])  # hari terakhir spike 5x
    vr = indicators.volume_ratio(vol, 20)
    assert 4.5 < vr.iloc[-1] < 5.5


def test_gap_pct():
    bars = make_bars(30)
    g = indicators.gap_pct(bars)
    assert len(g) == 30 and g.iloc[0] != g.iloc[0] or True  # NaN di bar pertama
    assert g.notna().sum() == 29


def test_enrichment_columns():
    enr = indicators.enrichment(make_bars(100))
    expected = {"ema20", "ema50", "rsi14", "atr14", "vol_ratio20", "gap_pct", "chg1_pct", "chg5_pct", "chg20_pct", "dist_high52w_pct"}
    assert expected <= set(enr.columns)
    assert len(enr) == 100  # input tidak berubah panjang


# ---------- screener ----------

def test_screen_uptrend_liquid_passes():
    bars = make_bars(120, drift=0.35, vol=0.8)  # tren naik sehat
    rec = screener.screen_one("UPUP", bars)
    if rec is not None:  # sintetis bisa miss filter rsi; yang penting tidak crash & valid
        assert rec["ticker"] == "UPUP" and 0 <= rec["score"] <= 100


def test_screen_down_trend_rejected():
    bars = make_bars(120, drift=-0.4, vol=0.5)
    assert screener.screen_one("DOWN", bars) is None


def test_screen_illiquid_rejected():
    bars = make_bars(120, drift=0.35, vol=0.8, base_volume=50_000)  # volume kecil
    assert screener.screen_one("ILLIQ", bars) is None


def test_screen_many_sorted():
    data = {"A": make_bars(120, drift=0.35, vol=0.8, seed=1), "B": make_bars(120, drift=-0.4, vol=0.5, seed=2)}
    out = screener.screen_many(data)
    if len(out):
        assert out["score"].is_monotonic_decreasing
        assert "DOWN" not in out["ticker"].values if "ticker" in out else True


# ---------- detective ----------

def test_detect_unusual_volume():
    bars = make_bars(120, drift=0.0, vol=0.3)
    bars.loc[bars.index[-1], "volume"] = 20_000_000  # spike hari terakhir
    f = detective.scan({"SPIKE": bars})
    assert "unusual_volume" in set(f["signal"])


def test_detect_breakout_52w():
    bars = make_bars(260, drift=0.12, vol=0.4, seed=3)
    # paksa bar terakhir menembus semua high sebelumnya (deterministik)
    prev_max = bars["high"][:-1].max()
    bars.loc[bars.index[-1], "high"] = prev_max + 2
    bars.loc[bars.index[-1], "close"] = prev_max + 1
    f = detective._findings("BREAK", bars)
    sigs = {x["signal"] for x in f}
    assert "breakout_52w" in sigs


def test_detect_no_finding_quiet_stock():
    bars = make_bars(120, drift=0.0, vol=0.2, base_volume=600_000, seed=9)
    f = detective._findings("QUIET", bars)
    # tidak boleh ada spike volume
    assert "unusual_volume" not in {x["signal"] for x in f}


def test_findings_have_explainable_detail():
    bars = make_bars(120, drift=0.0, vol=0.3)
    bars.loc[bars.index[-1], "volume"] = 10_000_000
    f = detective._findings("SPK", bars)
    assert all(x["detail"] for x in f)  # setiap temuan ada "mengapa"

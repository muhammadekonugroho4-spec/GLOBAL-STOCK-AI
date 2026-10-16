"""Test data_loader & job_fetch_daily - offline penuh (universe & bars palsu)."""
from pathlib import Path

import pandas as pd
import pytest

from backend.adapters.base import DataSourceError, RateLimit, RateLimitManager, SourceBlocked
from backend.adapters.stooq_adapter import looks_like_challenge, parse_stooq_csv
from backend.adapters.universe import parse_pipe_text
from backend.adapters.yf_adapter import normalize_ohlcv
from backend.core import data_loader


@pytest.fixture
def bars_dir(tmp_path) -> Path:
    return tmp_path / "bars"


def _df(dates, close=10.0, vol=1000):
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": vol,
        }
    )


# ---------- data_loader ----------

def test_merge_dedup_and_last_wins(bars_dir):
    old = _df(["2026-01-02", "2026-01-03"], close=10.0)
    new = _df(["2026-01-03", "2026-01-06"], close=11.0)  # 01-03 direvisi
    m = data_loader.merge_bars(old, new)
    assert list(m["date"]) == ["2026-01-02", "2026-01-03", "2026-01-06"]
    assert m.loc[m["date"] == "2026-01-03", "close"].iloc[0] == 11.0


def test_save_load_roundtrip(bars_dir):
    df = _df(["2026-01-02", "2026-01-03"])
    data_loader.save_bars(bars_dir, "AAPL", df)
    back = data_loader.load_bars(bars_dir, "AAPL")
    assert back is not None and len(back) == 2
    assert data_loader.load_bars(bars_dir, "TIDAKADA") is None


# ---------- yf normalize ----------

def test_normalize_multiticker_multindex():
    idx = pd.to_datetime(["2026-01-02", "2026-01-03"])
    cols = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"], ["AAPL"]], names=["Price", "Ticker"]
    )
    import numpy as np

    raw = pd.DataFrame(np.arange(10).reshape(2, 5).astype(float), index=idx, columns=cols)
    out = normalize_ohlcv(raw, "AAPL")
    assert list(out.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert len(out) == 2 and out["date"].iloc[0] == "2026-01-02"


# ---------- universe parse ----------

SAMPLE = (
    "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\n"
    "AAPL|Apple Inc.|Q|N|N|100|N|N\n"
    "TEST|Test Issue|Q|Y|N|100|N|N\n"
    "BRK/B|Berkshire unit|Q|N|N|100|N|N\n"
    "File Creation Time|1120202616:00||||||\n"
)


def test_parse_pipe_text_filters_test_issue():
    from backend.adapters.universe import _clean

    df = _clean(parse_pipe_text(SAMPLE), "NASDAQ")
    assert "TEST" not in set(df["symbol"])
    assert {"AAPL", "BRK/B"} <= set(df["symbol"])


# ---------- stooq ----------

def test_stooq_challenge_is_detected_not_forced():
    assert looks_like_challenge("<!DOCTYPE html><html><head>...crypto.subtle...")
    with pytest.raises(SourceBlocked):
        parse_stooq_csv("<!DOCTYPE html><html>challenge</html>", "AAPL")


def test_stooq_csv_ok():
    csv = "Date,Open,High,Low,Close,Volume\n2026-01-02,1,2,0.5,1.5,123\n"
    df = parse_stooq_csv(csv, "AAPL")
    assert df["close"].iloc[0] == 1.5


# ---------- rate limit ----------

def test_rate_limit_blocks_after_quota():
    rl = RateLimitManager()
    rl.configure("x", RateLimit(max_per_minute=2))
    assert rl.check("x") and rl.check("x")
    assert rl.check("x") is False


# ---------- job offline (universe palsu, fetch diblokir -> tercatat, tidak crash) ----------

def test_job_run_offline_blocked_fallback(tmp_path, monkeypatch):
    from jobs import job_fetch_daily as job

    uni = pd.DataFrame(
        {"symbol": ["AAA", "BBB"], "name": ["A Inc", "B Inc"], "exchange": ["NASDAQ"] * 2, "etf": [False, False]}
    )
    uni_path = tmp_path / "uni.parquet"
    uni.to_parquet(uni_path, index=False)

    monkeypatch.setattr(job.config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(job.config, "UNIVERSE_DIR", tmp_path / "data" / "universe")
    monkeypatch.setattr(job.config, "BARS_DIR", tmp_path / "data" / "bars")

    class BlockedBoth:
        source = "mock"

        def get_bars(self, t, s, e):
            raise SourceBlocked("simulasi challenge")

    monkeypatch.setattr(job, "fetch_one", lambda *a, **k: (_ for _ in ()).throw(SourceBlocked("x")))

    manifest = job.run(limit=2, years=1, offline_universe=uni_path)
    assert manifest["requested"] == 2
    assert manifest["ok"] == 0
    assert set(manifest["failed"]) == {"AAA", "BBB"}


def test_job_tradable_filters_weird_symbols():
    from jobs.job_fetch_daily import tradable_universe

    uni = pd.DataFrame(
        {
            "symbol": ["AAPL", "BRK/B", "FOO$", "AB^", "GOOD", "ETF1"],
            "name": ["x"] * 6,
            "etf": [False, False, False, False, False, True],
        }
    )
    out = tradable_universe(uni, 10)
    assert out == ["AAPL", "GOOD"]

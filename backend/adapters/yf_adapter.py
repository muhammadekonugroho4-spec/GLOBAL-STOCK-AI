"""Adapter yfinance: bars EOD/intraday per ticker.

Catatan versi: yfinance 1.7.x mengembalikan kolom MultiIndex (Price, Ticker)
saat download() - adapter ini menormalkan ke kolom tunggal.
"""
from __future__ import annotations

import pandas as pd

from backend.adapters.base import DataSourceError, RateLimit, RateLimitManager

BAR_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def normalize_ohlcv(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Normalkan output yfinance apa pun bentuknya -> kolom BAR_COLUMNS."""
    if df is None or len(df) == 0:
        raise DataSourceError(f"{ticker}: data kosong")
    if isinstance(df.columns, pd.MultiIndex):
        # level0=Price, level1=Ticker -> ambil blok ticker
        try:
            df = df.xs(ticker.upper(), axis=1, level=1)
        except KeyError:
            df.columns = df.columns.get_level_values(0)
    df = df.rename(
        columns={
            "Date": "date",
            "Datetime": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "close",
            "Volume": "volume",
        }
    )
    if "date" not in df.columns:  # index tanpa nama / bernama
        idx_name = df.index.name or "index"
        df = df.reset_index()
        df = df.rename(columns={idx_name: "date"})
    missing = {"open", "high", "low", "close"} - set(df.columns)
    if missing:
        raise DataSourceError(f"{ticker}: kolom hilang {sorted(missing)}")
    if "volume" not in df.columns:
        df["volume"] = 0
    out = df.reset_index()[BAR_COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out.dropna(subset=["close"]).reset_index(drop=True)


class YfAdapter:
    source = "yfinance"

    def __init__(self, rate: RateLimitManager | None = None, calls_per_minute: int = 100):
        self.rate = rate or RateLimitManager()
        self.rate.configure(self.source, RateLimit(max_per_minute=calls_per_minute))

    def get_bars(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        import yfinance as yf  # import lambat agar test core tidak butuh yfinance

        self.rate.wait_turn(self.source)
        try:
            raw = yf.download(
                ticker,
                start=start,
                end=end,
                progress=False,
                auto_adjust=True,
                threads=False,
            )
        except Exception as exc:  # network/parse error yf
            raise DataSourceError(f"{ticker}: yf.download gagal ({type(exc).__name__})") from exc
        return normalize_ohlcv(raw, ticker)

"""Adapter Stooq (fallback best-effort CSV EOD).

CATATAN: sejak Okt 2026 stooq.com kadang melayani JavaScript-challenge ke
klien non-browser (diamati dari jaringan rumah). Adapter ini TIDAK mencoba
melewati challenge - kalau respons HTML terdeteksi, raise SourceBlocked.
Dari IP GitHub Actions biasanya masih CSV biasa; job memperlakukan gagal
fallback ini sebagai catatan, bukan error fatal.
"""
from __future__ import annotations

import io

import pandas as pd
import requests

from backend.adapters.base import DataSourceError, SourceBlocked
from backend.adapters.yf_adapter import BAR_COLUMNS

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) gsai-pipeline/0.1"}
URL = "https://stooq.com/q/d/l/"


def looks_like_challenge(text: str) -> bool:
    head = text[:200].lstrip().lower()
    return "crypto.subtle" in text or head.startswith("<!doctype")


def parse_stooq_csv(text: str, ticker: str) -> pd.DataFrame:
    if looks_like_challenge(text):
        raise SourceBlocked("stooq: menerima challenge JS, dilewati tanpa dipaksa")
    df = pd.read_csv(io.StringIO(text))
    if df.empty or "Close" not in df.columns:
        raise DataSourceError(f"{ticker}: stooq CSV kosong/tak valid")
    df = df.rename(
        columns={"Date": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    )
    if "volume" not in df.columns:
        df["volume"] = 0
    return df[BAR_COLUMNS]


class StooqAdapter:
    source = "stooq"

    def __init__(self, session: requests.Session | None = None, timeout: int = 12):
        self.session = session or requests.Session()
        self.session.headers.update(UA)
        self.timeout = timeout

    def _symbol(self, ticker: str) -> str:
        return ticker.lower() if ticker.lower().endswith(".us") else f"{ticker.lower()}.us"

    def get_bars(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        d1 = start.replace("-", "")
        d2 = end.replace("-", "")
        try:
            r = self.session.get(
                URL, params={"s": self._symbol(ticker), "d1": d1, "d2": d2, "i": "d"}, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise DataSourceError(f"{ticker}: stooq request gagal ({type(exc).__name__})") from exc
        if r.status_code != 200:
            raise DataSourceError(f"{ticker}: stooq HTTP {r.status_code}")
        return parse_stooq_csv(r.text, ticker)

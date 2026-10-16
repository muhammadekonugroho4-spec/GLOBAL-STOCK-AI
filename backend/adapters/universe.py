"""Universe simbol resmi dari Nasdaq Trader (file publik harian, tanpa key).

http://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt  (Nasdaq)
http://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt   (NYSE/ARCA/NASDAQ GIMS)
"""
from __future__ import annotations

import io

import pandas as pd
import requests

from backend.adapters.base import DataSourceError

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) gsai-pipeline/0.1"}


def parse_pipe_text(text: str) -> pd.DataFrame:
    """Parse file pipe-delimited Nasdaq Trader (baris terakhir 'File Creation Time' dibuang)."""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) < 2 or "|" not in lines[0]:
        raise DataSourceError("format universe tidak dikenali")
    lines = [ln for ln in lines if not ln.startswith("File Creation Time")]
    df = pd.read_csv(io.StringIO("\n".join(lines)), sep="|")
    return df


def _clean(df: pd.DataFrame, exchange: str) -> pd.DataFrame:
    df = df[df.get("Test Issue", "N").astype(str).str.upper() == "N"].copy()
    sym_col = "Symbol" if "Symbol" in df.columns else "ACT Symbol"
    name_col = "Security Name"
    df = df.rename(columns={sym_col: "symbol"})
    out = pd.DataFrame(
        {
            "symbol": df["symbol"].astype(str).str.strip().str.upper(),
            "name": df[name_col].astype(str).str.strip(),
            "exchange": exchange,
        }
    )
    if "ETF" in df.columns:
        out["etf"] = df["ETF"].astype(str).str.upper().eq("Y")
    return out.dropna(subset=["symbol"])


def fetch_universe(timeout: int = 30) -> pd.DataFrame:
    """Gabungan Nasdaq + listed lain. Kolom: symbol, name, exchange, etf."""
    frames = []
    for url, exch in ((NASDAQ_LISTED_URL, "NASDAQ"), (OTHER_LISTED_URL, "OTHER")):
        r = requests.get(url, headers=UA, timeout=timeout)
        if r.status_code != 200:
            raise DataSourceError(f"universe {exch} HTTP {r.status_code}")
        frames.append(_clean(parse_pipe_text(r.text), exch))
    uni = pd.concat(frames, ignore_index=True).drop_duplicates(subset="symbol")
    return uni.sort_values("symbol").reset_index(drop=True)

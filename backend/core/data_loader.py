"""Membaca/menulis cache bar parquet per ticker (murni filesystem)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.adapters.yf_adapter import BAR_COLUMNS


def bars_path(bars_dir: Path, ticker: str) -> Path:
    safe = ticker.upper().replace("^", "_").replace("/", "_")
    return bars_dir / f"{safe}.parquet"


def load_bars(bars_dir: Path, ticker: str) -> pd.DataFrame | None:
    p = bars_path(bars_dir, ticker)
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    return df if len(df) else None


def merge_bars(old: pd.DataFrame | None, new: pd.DataFrame) -> pd.DataFrame:
    """Gabung historis lama + fetch baru; tanggal baru menang; urut & dedup."""
    cols = list(BAR_COLUMNS)
    new = new[cols].copy()
    if old is None or old.empty:
        merged = new
    else:
        merged = pd.concat([old[cols], new], ignore_index=True)
    merged = merged.drop_duplicates(subset="date", keep="last")
    merged = merged.sort_values("date").reset_index(drop=True)
    return merged


def save_bars(bars_dir: Path, ticker: str, df: pd.DataFrame) -> Path:
    bars_dir.mkdir(parents=True, exist_ok=True)
    p = bars_path(bars_dir, ticker)
    df.to_parquet(p, index=False)
    return p


def tail_window(bars_dir: Path, ticker: str, days: int) -> pd.DataFrame | None:
    df = load_bars(bars_dir, ticker)
    if df is None:
        return None
    return df.tail(days).reset_index(drop=True)

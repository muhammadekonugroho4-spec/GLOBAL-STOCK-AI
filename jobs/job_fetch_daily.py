"""Job harian: unduh universe resmi + bars EOD batch kecil -> parquet + manifest.

Dipanggil GitHub Actions (cron) atau manual:
    .venv/bin/python -m jobs.job_fetch_daily --limit 5 --years 3

Anti-fragil:
- gagal 1 ticker tidak menghentikan batch; dirangkum di manifest
- yfinance primer -> stooq fallback (kalau diblok challenge, dicatat lalu lanjut)
- idempotent: parquet lama di-merge, fetch ulang hari sama aman
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from backend import config
from backend.adapters.base import DataSourceError, SourceBlocked
from backend.adapters.stooq_adapter import StooqAdapter
from backend.adapters.universe import fetch_universe
from backend.adapters.yf_adapter import YfAdapter
from backend.core.data_loader import load_bars, merge_bars, save_bars

LOOKBACK_DAYS = 3  # jendela update harian (cache lama di-merge, tidak diunduh ulang)


def universe_path() -> Path:
    return config.UNIVERSE_DIR / "universe.parquet"


def refresh_universe() -> pd.DataFrame:
    uni = fetch_universe()
    config.UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    uni.to_parquet(universe_path(), index=False)
    return uni


def tradable_universe(uni: pd.DataFrame, limit: int, exclude_etf: bool = True) -> list[str]:
    df = uni
    if exclude_etf and "etf" in df.columns:
        df = df[~df["etf"].fillna(False)]
    df = df[df["symbol"].str.fullmatch(r"[A-Z]+")]  # buang warrant/unit/unsponsored ($, ^, dsb)
    return df["symbol"].tolist()[:limit]


def fetch_one(ticker: str, start: str, end: str, yf: YfAdapter, stooq: StooqAdapter) -> pd.DataFrame:
    try:
        return yf.get_bars(ticker, start, end)
    except SourceBlocked:
        raise
    except DataSourceError:
        return stooq.get_bars(ticker, start, end)


def run(limit: int, years: int, offline_universe: Path | None = None) -> dict:
    today = date.today()
    start = (today - timedelta(days=LOOKBACK_DAYS)).isoformat()
    full_start = (today - timedelta(days=int(years * 365.25))).isoformat()
    end = today.isoformat()

    if offline_universe is not None:
        uni = pd.read_parquet(offline_universe)
        uni_source = f"offline:{offline_universe.name}"
    else:
        try:
            uni = refresh_universe()
            uni_source = "nasdaqtrader:fresh"
        except Exception as exc:
            p = universe_path()
            if not p.exists():
                raise
            uni = pd.read_parquet(p)
            uni_source = f"cache:({type(exc).__name__})"

    tickers = tradable_universe(uni, limit)
    yf = YfAdapter()
    stooq = StooqAdapter()

    results: dict[str, str] = {}
    for t in tickers:
        old = load_bars(config.BARS_DIR, t)
        eff_start = start if old is not None else full_start
        try:
            bars = fetch_one(t, eff_start, end, yf, stooq)
        except SourceBlocked:
            results[t] = "fallback_blocked"
            continue
        except DataSourceError as exc:
            results[t] = f"error:{str(exc)[:60]}"
            continue
        merged = merge_bars(old, bars)
        save_bars(config.BARS_DIR, t, merged)
        results[t] = f"ok:{len(merged)}rows"

    manifest = {
        "run_date": today.isoformat(),
        "universe_source": uni_source,
        "universe_size": int(len(uni)),
        "requested": len(tickers),
        "ok": sum(1 for v in results.values() if v.startswith("ok")),
        "failed": {k: v for k, v in results.items() if not v.startswith("ok")},
        "results": results,
    }
    out = config.DATA_DIR / f"{today.isoformat()}" / "fetch_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="GLOBAL-STOCK-AI daily fetch")
    ap.add_argument("--limit", type=int, default=600, help="jumlah ticker (urut abjad)")
    ap.add_argument("--years", type=int, default=3, help="lookback saat ticker baru")
    ap.add_argument("--offline-universe", type=str, default="", help="path parquet universe (test offline)")
    args = ap.parse_args()
    offline = Path(args.offline_universe) if args.offline_universe else None
    manifest = run(args.limit, args.years, offline_universe=offline)
    print(json.dumps({k: v for k, v in manifest.items() if k != "results"}, indent=2))
    return 0 if manifest["ok"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

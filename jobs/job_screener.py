"""Job screener + detektif: baca semua parquet cache -> hasil harian CSV + manifest.

Jalan setelah fetch (lihat .github/workflows/screener.yml), atau manual:
    .venv/bin/python -m jobs.job_screener
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from backend import config
from backend.core import detective, screener
from backend.core.data_loader import load_bars


def load_all(bars_dir: Path) -> dict[str, pd.DataFrame]:
    data: dict[str, pd.DataFrame] = {}
    for p in sorted(bars_dir.glob("*.parquet")):
        df = load_bars(bars_dir, p.stem)
        if df is not None and len(df) >= 60:
            data[p.stem] = df
    return data


def run(bars_dir: Path | None = None, top: int = 50) -> dict:
    bars_dir = bars_dir or config.BARS_DIR
    data = load_all(bars_dir)
    today = date.today().isoformat()

    results = screener.screen_many(data)
    findings = detective.scan(data)

    out_dir = config.DATA_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)
    results.head(top).to_csv(out_dir / "screener_results.csv", index=False)
    findings.to_csv(out_dir / "detective_findings.csv", index=False)

    manifest = {
        "run_date": today,
        "tickers_evaluated": len(data),
        "screen_passed": int(len(results)),
        "detective_findings": int(len(findings)),
        "findings_by_signal": findings["signal"].value_counts().to_dict() if len(findings) else {},
    }
    (out_dir / "screener_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="GLOBAL-STOCK-AI screener harian")
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()
    manifest = run(top=args.top)
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["tickers_evaluated"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

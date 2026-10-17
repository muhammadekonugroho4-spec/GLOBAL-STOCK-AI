"""Job analisa AI: ambil top-N dari hasil screener terbaru -> analisa -> CSV + manifest.

    .venv/bin/python -m jobs.job_ai_analysis --top 10

Tanpa LLM key: mode mock (deterministik, CI-safe). Dengan key: Gemini lalu Groq.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from backend import config
from backend.core import ai_service, news as news_mod


def latest_screener_dir() -> Path | None:
    dirs = sorted((d for d in config.DATA_DIR.iterdir() if d.is_dir() and d.name[:2] == "20"), reverse=True)
    for d in dirs:
        if (d / "screener_results.csv").exists():
            return d
    return None


def run(top: int = 10, fetch_market_news: bool = True) -> dict:
    src = latest_screener_dir()
    if src is None:
        raise SystemExit("Belum ada hasil screener - jalankan jobs.job_screener dulu.")
    rows = pd.read_csv(src / "screener_results.csv").head(top).to_dict(orient="records")

    market_news = news_mod.fetch_market_news() if fetch_market_news else []
    market_titles = [n.title for n in market_news[:5]]

    records = []
    for row in rows:
        analysis = ai_service.analyze(row)
        rec = ai_service.to_record(analysis)
        rec["market_news_used"] = len(market_titles)
        records.append(rec)

    today = date.today().isoformat()
    out_dir = config.DATA_DIR / today
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records)
    df.to_csv(out_dir / "ai_analysis.csv", index=False)

    manifest = {
        "run_date": today,
        "source_screener": str(src.name),
        "analyzed": len(records),
        "engines": df["engine"].value_counts().to_dict() if len(df) else {},
        "market_headlines": market_titles,
    }
    (out_dir / "ai_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="GLOBAL-STOCK-AI analisa AI harian")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--no-news", action="store_true", help="lewati RSS berita pasar")
    args = ap.parse_args()
    manifest = run(top=args.top, fetch_market_news=not args.no_news)
    print(json.dumps({k: v for k, v in manifest.items() if k != "market_headlines"}, indent=2))
    return 0 if manifest["analyzed"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

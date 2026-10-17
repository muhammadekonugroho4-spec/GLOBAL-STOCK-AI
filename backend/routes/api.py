"""API dashboard - baca hasil harian dari data/YYYY-MM-DD/ (murni, tanpa hitung ulang)."""
from __future__ import annotations

import json
from datetime import date

import pandas as pd
from fastapi import APIRouter

from backend import config

router = APIRouter(prefix="/api")


def _latest_day() -> str | None:
    dirs = sorted((d.name for d in config.DATA_DIR.iterdir() if d.is_dir() and d.name[:2] == "20"), reverse=True)
    return dirs[0] if dirs else None


def _read_csv(day: str, name: str) -> list[dict]:
    p = config.DATA_DIR / day / name
    if not p.exists():
        return []
    df = pd.read_csv(p)
    return df.where(pd.notna(df), None).to_dict(orient="records")


@router.get("/screener")
def api_screener(day: str | None = None, limit: int = 50):
    d = day or _latest_day() or date.today().isoformat()
    rows = _read_csv(d, "screener_results.csv")
    mf = config.DATA_DIR / d / "screener_manifest.json"
    manifest = json.loads(mf.read_text()) if mf.exists() else {}
    return {"day": d, "manifest": manifest, "results": rows[:limit]}


@router.get("/radar")
def api_radar(day: str | None = None):
    d = day or _latest_day() or date.today().isoformat()
    rows = _read_csv(d, "detective_findings.csv")
    mf = config.DATA_DIR / d / "screener_manifest.json"
    manifest = json.loads(mf.read_text()) if mf.exists() else {}
    return {"day": d, "manifest": manifest, "findings": rows}


@router.get("/ai")
def api_ai(day: str | None = None):
    d = day or _latest_day() or date.today().isoformat()
    p = config.DATA_DIR / d / "ai_analysis.csv"
    mf = config.DATA_DIR / d / "ai_manifest.json"
    manifest = json.loads(mf.read_text()) if mf.exists() else {}
    rows: list[dict] = []
    if p.exists():
        df = pd.read_csv(p)
        for col in ("reasons", "risks"):
            if col in df.columns:
                df[col] = (
                    df[col].fillna("").astype(str).str.split(r" \| ")  # separator eksplisit, bukan tiap karakter
                )
        rows = df.where(pd.notna(df), None).to_dict(orient="records")
    return {"day": d, "manifest": manifest, "analyses": rows}

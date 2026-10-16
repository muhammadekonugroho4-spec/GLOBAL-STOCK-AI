"""Test API routes & UI fase 2 - offline (hasil palsu di data dir sementara)."""
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.main import app

client = TestClient(app)


@pytest.fixture
def data_day(tmp_path, monkeypatch):
    d = tmp_path / "2026-10-16"
    d.mkdir(parents=True)
    pd.DataFrame(
        [
            {"ticker": "AAA", "score": 80.0, "close": 12.5, "rsi14": 60.0, "vol_ratio20": 2.1,
             "chg5_pct": 5.2, "dist_high52w_pct": -1.0, "date": "2026-10-16", "avg_vol20": 1e6,
             "avg_dollar_vol20": 2e7, "gap_pct": 0.5, "chg1_pct": 1.0, "chg20_pct": 9.0},
        ]
    ).to_csv(d / "screener_results.csv", index=False)
    pd.DataFrame(
        [{"ticker": "AAA", "signal": "unusual_volume", "value": 2.5, "detail": "vol 2.5x",
          "close": 12.5, "date": "2026-10-16"}]
    ).to_csv(d / "detective_findings.csv", index=False)
    (d / "screener_manifest.json").write_text(json.dumps({"tickers_evaluated": 1, "screen_passed": 1}))
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return tmp_path


def test_api_screener(data_day):
    r = client.get("/api/screener")
    assert r.status_code == 200
    body = r.json()
    assert body["day"] == "2026-10-16"
    assert body["results"][0]["ticker"] == "AAA"
    assert body["manifest"]["tickers_evaluated"] == 1


def test_api_radar(data_day):
    r = client.get("/api/radar")
    assert r.status_code == 200
    assert r.json()["findings"][0]["signal"] == "unusual_volume"


def test_api_empty_day_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    r = client.get("/api/screener")
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_ui_screener_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "Screener" in r.text


def test_ui_radar_page():
    r = client.get("/radar")
    assert r.status_code == 200
    assert "Radar" in r.text


def test_health_still_ok():
    assert client.get("/health").json()["status"] == "ok"

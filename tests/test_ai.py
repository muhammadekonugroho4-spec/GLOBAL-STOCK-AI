"""Test AI service (mock + parser), news parser, dan job AI dengan LLM palsu - offline."""
import json
from unittest.mock import patch

import pandas as pd
import pytest

from backend.core import ai_service
from backend.core.news import parse_rss

ROW = {
    "ticker": "AMN", "close": 40.0, "score": 72.0, "rsi14": 68.0, "vol_ratio20": 1.8,
    "chg1_pct": 1.2, "chg5_pct": 12.9, "dist_high52w_pct": 4.1,
}


# ---------- mock engine (tanpa key) ----------

def test_mock_analysis_deterministic():
    a1 = ai_service._mock_analysis(ROW, has_news=False)
    a2 = ai_service._mock_analysis(ROW, has_news=False)
    assert a1.summary == a2.summary and a1.score == a2.score
    assert a1.engine == "mock"
    assert 0 <= a1.score <= 100 and a1.verdict in {"bullish", "neutral", "bearish"}
    assert a1.reasons and a1.risks


def test_analyze_without_keys_uses_mock(monkeypatch):
    monkeypatch.setattr(ai_service.config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(ai_service.config, "GROQ_API_KEY", "")
    a = ai_service.analyze(ROW, ticker_news=[])
    assert a.engine == "mock"


# ---------- LLM response parser ----------

def test_parse_llm_json_plain():
    d = ai_service._parse_llm_json('{"verdict":"bullish","score":75}')
    assert d["score"] == 75


def test_parse_llm_json_in_markdown():
    text = 'berikut hasilnya:\n```json\n{"verdict":"bearish","score":20}\n```'
    assert ai_service._parse_llm_json(text)["verdict"] == "bearish"


def test_parse_llm_json_garbage():
    assert ai_service._parse_llm_json("bukan json sama sekali") is None


# ---------- LLM path dengan mock HTTP ----------

def test_gemini_path_called_when_key_set(monkeypatch):
    monkeypatch.setattr(ai_service.config, "GEMINI_API_KEY", "FAKE")
    monkeypatch.setattr(ai_service.config, "GROQ_API_KEY", "")
    payload = {"candidates": [{"content": {"parts": [{"text": json.dumps(
        {"verdict": "bullish", "summary": "bagus", "reasons": ["r1"], "risks": ["x"], "score": 78}
    )}]}}]}
    with patch.object(ai_service.requests, "post", return_value=_resp(200, payload)) as mock_post:
        a = ai_service.analyze(ROW, ticker_news=[])
    assert a.engine == "gemini" and a.score == 78
    assert "FAKE" in mock_post.call_args.args[0]  # key dipakai di URL, tidak di-log


def test_falls_back_to_mock_when_llm_fails(monkeypatch):
    monkeypatch.setattr(ai_service.config, "GEMINI_API_KEY", "FAKE")
    monkeypatch.setattr(ai_service.config, "GROQ_API_KEY", "")
    with patch.object(ai_service.requests, "post", return_value=_resp(500, {})):
        a = ai_service.analyze(ROW, ticker_news=[])
    assert a.engine == "mock"


class _resp:
    def __init__(self, code, payload):
        self.status_code = code
        self._payload = payload

    def json(self):
        return self._payload


# ---------- news parser ----------

RSS_SAMPLE = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Saham &lt;b&gt;AMN&lt;/b&gt; naik</title><link>https://x/1</link></item>
<item><title>Berita kedua</title><link>https://x/2</link></item>
</channel></rss>"""


def test_parse_rss_strips_html():
    items = parse_rss(RSS_SAMPLE, "test")
    assert len(items) == 2
    assert items[0].title == "Saham AMN naik"  # tag HTML dibersihkan


def test_parse_rss_garbage_returns_empty():
    assert parse_rss("<html>yang ini bukan rss", "test") == []


# ---------- job dengan engine mock (offline) ----------

def test_job_ai_run_offline(tmp_path, monkeypatch):
    import jobs.job_ai_analysis as job

    data = tmp_path / "data"
    day = data / "2026-10-16"
    day.mkdir(parents=True)
    pd.DataFrame([ROW]).to_csv(day / "screener_results.csv", index=False)

    monkeypatch.setattr(job.config, "DATA_DIR", data)
    monkeypatch.setattr(ai_service.config, "GEMINI_API_KEY", "")
    monkeypatch.setattr(ai_service.config, "GROQ_API_KEY", "")
    monkeypatch.setattr(job.news_mod, "fetch_market_news", lambda *a, **k: [])
    monkeypatch.setattr(ai_service.news_mod, "fetch_ticker_news", lambda *a, **k: [])

    manifest = job.run(top=1, fetch_market_news=False)
    assert manifest["analyzed"] == 1
    assert manifest["engines"] == {"mock": 1}
    out = pd.read_csv(data / job.date.today().isoformat() / "ai_analysis.csv")
    assert out.iloc[0]["ticker"] == "AMN"
    assert "reasons" in out.columns

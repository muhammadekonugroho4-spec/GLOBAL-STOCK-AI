"""Analisa AI per ticker.

Dua mode otomatis:
- key Gemini/Groq ADA  -> ringkasan bahasa manusia dari LLM (REST langsung, tanpa SDK)
- key KOSONG           -> mode MOCK: narasi deterministik dari angka teknikal
                         (tetap berguna, idempotent, dipakai CI)

Kontrak output (sama untuk kedua mode) - AIAnalysis dataclass.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

import requests

from backend import config
from backend.core import news as news_mod

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT = 45


@dataclass
class AIAnalysis:
    ticker: str
    score: float          # 0..100
    verdict: str          # bullish / neutral / bearish
    summary: str          # 2-4 kalimat bahasa manusia
    reasons: list[str]    # poin "mengapa"
    risks: list[str]      # poin risiko
    engine: str           # gemini / groq / mock
    generated_at: str


SYSTEM_PROMPT = (
    "Kamu analis saham. Berdasarkan data teknikal & berita berikut, beri penilaian SINGKAT "
    "dalam JSON valid tanpa markdown: "
    '{"verdict":"bullish|neutral|bearish","summary":"2-3 kalimat bahasa Indonesia",'
    '"reasons":["...","..."],"risks":["...","..."],"score":0-100}. '
    "Skor: 70+=bullish kuat, 40-69=netral, <40=bearish. Jangan mengada-ada data yang tidak diberikan."
)


def _technical_facts(row: dict) -> str:
    return (
        f"Ticker {row['ticker']}: close ${row['close']}, skor screener {row['score']}, "
        f"RSI14 {row['rsi14']}, volume {row['vol_ratio20']}x rata-rata 20 hari, "
        f"perubahan 1 hari {row['chg1_pct']}%, 5 hari {row['chg5_pct']}%, "
        f"posisi {row['dist_high52w_pct']}% dari high 52 minggu."
    )


def _news_facts(items: list) -> str:
    if not items:
        return "Tidak ada berita ticker yang berhasil diambil."
    return "Berita terkait: " + "; ".join(f"'{i.title}'" for i in items[:4])


def _parse_llm_json(text: str) -> dict | None:
    """LLM kadang membungkus JSON - ambil blok {} pertama yang valid."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("` \n").removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        d = json.loads(text[start : end + 1])
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        return None


def _mock_analysis(row: dict, has_news: bool) -> AIAnalysis:
    """Deterministik dari angka - dipakai saat tidak ada LLM key."""
    vr, rsi, chg5, d52 = row["vol_ratio20"], row["rsi14"], row["chg5_pct"], row["dist_high52w_pct"]
    reasons: list[str] = []
    if vr >= 1.5:
        reasons.append(f"Volume {vr}x rata-rata menandakan akumulasi")
    if chg5 > 3:
        reasons.append(f"Momentum 5 hari kuat (+{chg5}%)")
    if d52 > -5:
        reasons.append("Harga berada dekat puncak 52 minggu (breakout area)")
    if rsi >= 70:
        risks = [f"RSI {rsi} masuk overbought, rawan koreksi teknikal"]
        verdict = "neutral" if d52 > 0 else "bullish"
    else:
        risks = ["Momentum dapat berbalik bila volume turun di sesi berikutnya"]
        verdict = "bullish"
    if not reasons:
        reasons.append("Memenuhi semua filter likuiditas dan tren naik screener")
    score = min(85.0, row["score"] + (5.0 if has_news else 0.0))
    news_note = " Ada pemberitaan terbaru seputar ticker ini." if has_news else ""
    return AIAnalysis(
        ticker=row["ticker"],
        score=round(score, 1),
        verdict=verdict,
        summary=(
            f"{row['ticker']} lolos screener dengan skor {row['score']}: tren naik, "
            f"likuiditas cukup, momentum 5 hari {chg5:+.1f}%.{news_note}"
        ),
        reasons=reasons,
        risks=risks,
        engine="mock",
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def _call_gemini(row: dict, news_text: str, api_key: str) -> AIAnalysis | None:
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": _technical_facts(row) + "\n" + news_text}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 400},
    }
    try:
        r = requests.post(f"{GEMINI_URL}?key={api_key}", json=body, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        d = _parse_llm_json(text)
        if not d:
            return None
        return AIAnalysis(
            ticker=row["ticker"],
            score=float(d.get("score", row["score"])),
            verdict=d.get("verdict", "neutral"),
            summary=d.get("summary", ""),
            reasons=list(d.get("reasons", []))[:4],
            risks=list(d.get("risks", []))[:4],
            engine="gemini",
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None


def _call_groq(row: dict, news_text: str, api_key: str) -> AIAnalysis | None:
    body = {
        "model": "llama-3.3-70b-versatile",
        "temperature": 0.3,
        "max_tokens": 400,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _technical_facts(row) + "\n" + news_text},
        ],
    }
    try:
        r = requests.post(
            GROQ_URL, json=body, headers={"Authorization": f"Bearer {api_key}"}, timeout=TIMEOUT
        )
        if r.status_code != 200:
            return None
        d = _parse_llm_json(r.json()["choices"][0]["message"]["content"])
        if not d:
            return None
        return AIAnalysis(
            ticker=row["ticker"],
            score=float(d.get("score", row["score"])),
            verdict=d.get("verdict", "neutral"),
            summary=d.get("summary", ""),
            reasons=list(d.get("reasons", []))[:4],
            risks=list(d.get("risks", []))[:4],
            engine="groq",
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None


def analyze(row: dict, ticker_news: list | None = None) -> AIAnalysis:
    """Pilih engine: gemini -> groq -> mock. Tidak pernah raise ke pemanggil."""
    ticker_news = ticker_news if ticker_news is not None else news_mod.fetch_ticker_news(row["ticker"])
    news_text = _news_facts(ticker_news)
    if config.GEMINI_API_KEY:
        a = _call_gemini(row, news_text, config.GEMINI_API_KEY)
        if a:
            return a
    if config.GROQ_API_KEY:
        a = _call_groq(row, news_text, config.GROQ_API_KEY)
        if a:
            return a
    return _mock_analysis(row, has_news=bool(ticker_news))


def to_record(a: AIAnalysis) -> dict:
    d = asdict(a)
    d["reasons"] = " | ".join(a.reasons)
    d["risks"] = " | ".join(a.risks)
    return d

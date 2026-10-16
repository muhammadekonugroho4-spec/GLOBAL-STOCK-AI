"""GLOBAL-STOCK-AI - konfigurasi terpusat (baca .env, tanpa hardcoded secret)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


ALPACA_API_KEY = _get("ALPACA_API_KEY")
ALPACA_SECRET_KEY = _get("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = _get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
ALPACA_DATA_URL = _get("ALPACA_DATA_URL", "https://data.alpaca.markets/v2")

GEMINI_API_KEY = _get("GEMINI_API_KEY")
GROQ_API_KEY = _get("GROQ_API_KEY")
FRED_API_KEY = _get("FRED_API_KEY")

TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID")

ENV = _get("GSAI_ENV", "dev")
DATA_DIR = BASE_DIR / "data"
UNIVERSE_DIR = DATA_DIR / "universe"
BARS_DIR = DATA_DIR / "bars"
FUNDAMENTALS_DIR = DATA_DIR / "fundamentals"


def missing_credentials(*names: str) -> list[str]:
    """Kembalikan daftar nama env yang masih kosong (untuk /health, tanpa nilai)."""
    return [n for n in names if not _get(n)]

"""GLOBAL-STOCK-AI - FastAPI app (Fase 0: health + skeleton)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from backend import config

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    for sub in ("", "universe", "bars", "fundamentals"):
        (config.DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="GLOBAL-STOCK-AI", version=VERSION, lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": VERSION,
        "env": config.ENV,
        "missing_credentials": config.missing_credentials(
            "ALPACA_API_KEY",
            "ALPACA_SECRET_KEY",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
            "FRED_API_KEY",
            "TELEGRAM_BOT_TOKEN",
        ),
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return (
        "<html><head><title>GLOBAL-STOCK-AI</title></head><body>"
        "<h1>GLOBAL-STOCK-AI</h1>"
        f"<p>v{VERSION} - Fase 0 skeleton berjalan.</p>"
        '<p><a href="/health">/health</a> | <a href="/docs">/docs</a></p>'
        "</body></html>"
    )

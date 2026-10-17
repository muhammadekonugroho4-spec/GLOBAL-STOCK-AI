"""GLOBAL-STOCK-AI - FastAPI app (Fase 2: screener + radar UI)."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend import config
from backend.routes.api import router as api_router

VERSION = "0.2.0"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    for sub in ("", "universe", "bars", "fundamentals"):
        (config.DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="GLOBAL-STOCK-AI", version=VERSION, lifespan=lifespan)
app.include_router(api_router)
app.mount("/static", __import__("fastapi.staticfiles", fromlist=["StaticFiles"]).StaticFiles(
    directory=str(Path(__file__).parent / "static")), name="static")


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
def index(request: Request):
    return TEMPLATES.TemplateResponse(request, "screener.html")


@app.get("/radar", response_class=HTMLResponse)
def radar(request: Request):
    return TEMPLATES.TemplateResponse(request, "radar.html")


@app.get("/ai", response_class=HTMLResponse)
def ai_page(request: Request):
    return TEMPLATES.TemplateResponse(request, "ai.html")

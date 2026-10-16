"""Test /health dan skeleton Fase 0 - tanpa network, tanpa .env asli."""
from fastapi.testclient import TestClient

from backend import config
from backend.main import VERSION, app

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == VERSION
    assert isinstance(body["missing_credentials"], list)


def test_health_does_not_leak_secret_values():
    r = client.get("/health")
    text = r.text.lower()
    assert "alpaca_api_key=" not in text  # hanya nama field, bukan nilai
    if config.ALPACA_API_KEY:
        assert config.ALPACA_API_KEY not in text


def test_index_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "GLOBAL-STOCK-AI" in r.text


def test_data_dirs_created(tmp_path, monkeypatch):
    d = tmp_path / "data"
    monkeypatch.setattr(config, "DATA_DIR", d)
    import asyncio
    from backend.main import lifespan

    async def run():
        async with lifespan(None):
            pass

    asyncio.run(run())
    assert (d / "universe").is_dir()
    assert (d / "bars").is_dir()
    assert (d / "fundamentals").is_dir()

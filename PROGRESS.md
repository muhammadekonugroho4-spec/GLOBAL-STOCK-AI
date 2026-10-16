# PROGRESS - GLOBAL-STOCK-AI

| Fase | Status | Tanggal | Catatan |
|------|--------|---------|---------|
| 0 | ✅ SELESAI | 2026-10-16 | Kerangka sesuai §3, venv py3.14, `/health` 200, pytest 4/4 lulus, `.env.example` + `.gitignore` aman |
| 1 | ✅ SELESAI | 2026-10-16 | Pipeline: universe nasdaqtrader 13.270 simbol; yf primer + stooq fallback (challenge JS = ditandai, tidak dipaksa); parquet idempotent; workflow Actions siap. Smoke: 5/5 ticker OK (752 bar, 3 thn). pytest 13/13. Commit `6296e5e` |
| 1b | ✅ LIVE | 2026-10-16 | Repo GitHub terhubung; run Actions pertama sukses: **595/600 ticker** (5 gagal tercatat di manifest), universe fresh 13.270, auto-commit `data: fetch harian 2026-10-16`. Fix: filter warrant/unit + tangkap timeout stooq |
| 2-7 | ⬜ Belum | - | Lihat PROMPT_PROJECT_GLOBAL_STOCK_AI.md §5 |

## Verifikasi Fase 0
- `.venv/bin/python -m pytest -q` → `4 passed`
- `uvicorn backend.main:app` → `GET /health` 200 (status ok, daftar missing_credentials tanpa nilai secret)
- `GET /` 200 (halaman skeleton)

## Cara menjalankan lokal
```bash
cd /home/kaltaraid/Documents/GLOBAL-STOCK-AI
.venv/bin/python -m uvicorn backend.main:app --reload --port 8100
# buka http://127.0.0.1:8100/health
```

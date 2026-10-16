# PROMPT PROYEK: GLOBAL-STOCK-AI
> Saham internasional (prioritas US) — data gratis selamanya, AI analisa, auto buy/sell via paper-trading.
> Total biaya target: **$0 (bukan trial, free tier permanen)**.

---

## 0. IDENTITAS PROYEK

- Nama: **GLOBAL-STOCK-AI** (kode pendek: `gsai`)
- Lokasi: `/home/kaltaraid/Documents/GLOBAL-STOCK-AI`
- Tujuan akhir: website + bot yang bisa (1) screening saham luar negeri, (2) analisa AI,
  (3) auto buy/sell **realistis** lewat broker paper-trading, (4) jurnal & evaluasi otomatis.
- Bahasa kode: Python 3.11+ · UI: FastAPI + Jinja2 + PWA (polanya sama dengan WEB-SCREENING).
- Prinsip kerja:
  1. **Gratis selamanya** — hanya free tier permanen, tanpa kartu kredit, tanpa trial.
  2. **Legal** — tidak scrape agresif, tidak bypass paywall/ToS, hormati rate limit.
  3. **Modular** — 1 sumber data mati → tinggal ganti adapter, tidak rombak sistem.
  4. **Bukti dulu, uang kemudian** — wajib backtest + paper trade konsisten sebelum live (live tidak masuk scope MVP).

---

## 1. SUMBER DATA GRATIS SELAMANYA (VERIFIED FREE TIER, BUKAN TRIAL)

| # | Sumber | Jenis data | Batas free | API key? | Peran dalam proyek |
|---|--------|-----------|-----------|----------|--------------------|
| 1 | **yfinance** (Yahoo) | OHLCV intraday+daily, ~seluruh dunia (US, JP `.T`, EU `.L/.DE`, dll), fundamental ringkas, berita | ketat tapi ada (pakai cache) | tidak | Sumber utama harga & universe global |
| 2 | **Stooq** (`stooq.com/q/d/l/?s=...&i=d`) | CSV EOD historis panjang, US/EU/Asia/forex | longgar, tanpa key | tidak | Cadangan + backfill historis panjang |
| 3 | **Alpaca Market Data (IEX feed)** | Quote/trade real-time US + bar 1m | 200 req/menit | ya (gratis permanen) | Data real-time untuk bot |
| 4 | **Alpaca Paper Trading** | Eksekusi order nyata (uang virtual), streaming | gratis selamanya | ya | **Mesin auto buy/sell** |
| 5 | **Finnhub free** | Quote real-time, berita, earnings calendar | 60 call/menit | ya (gratis permanen) | Cadangan harga + kalender earnings |
| 6 | **Twelve Data free** | OHLCV multi-negara, forex | 800/hari | ya (gratis permanen) | Cadangan pasar non-US |
| 7 | **SEC EDGAR** | Laporan keuangan resmi 10-K/10-Q, full-text search | 10 req/detik (fair use) | tidak | Fundamental otentik (tidak ada di Yahoo dengan rapi) |
| 8 | **Nasdaq Trader files** (`nasdaqtrader.com/symboldirectory`) | Daftar simbol NYSE/Nasdaq lengkap + status | file publik harian | tidak | Universe screener resmi (bukan hardcoded) |
| 9 | **FRED API** | Data makro (suku bunga, inflasi, DGS10, dll) | longgar | ya (gratis permanen) | Konteks regime pasar untuk AI |
| 10 | **RSS berita** (Yahoo Finance RSS, MT Newswires via Yahoo, MarketWatch RSS) | Headline per ticker | publik | tidak | Input sentimen AI |
| 11 | **Gemini API free tier / Groq free tier** | LLM untuk analisa | quota harian cukup | ya (gratis permanen) | Otak analisa AI (sama seperti WEB-SCREENING) |

**Aturan rotasi:** setiap sumber dibungkus `DataAdapter` dengan antarmuka sama
(`get_bars()`, `get_quote()`, `get_fundamentals()`). `RateLimitManager` melacak kuota
per sumber per hari; kalau satu sumber habis/di-blok → fallback otomatis ke sumber berikutnya.

---

## 2. INFRASTRUKTUR $0

| Kebutuhan | Solusi gratis | Catatan |
|-----------|--------------|---------|
| Fetch data terjadwal (cron) | **GitHub Actions** (public repo = unlimited menit) | Job harian fetch → tulis CSV/Parquet → auto-commit ke repo (pola "git as database", sudah terbukti di WEB-SCREENING) |
| Hosting API web | **Render free** (750 jam/bln, sleep 15 mnt) atau **Hugging Face Spaces** (FastAPI via Docker, selalu hidup) | HF Spaces dipilih sebagai utama, Render cadangan |
| Wake-up ping anti-sleep | GitHub Actions cron tiap 10 menit → `GET /health` | Gratis |
| Frontend/PWA | Dilayani FastAPI langsung (satu layanan saja) | Manifest + service worker seperti WEB-SCREENING |
| Database | **SQLite** untuk state runtime + **CSV/Parquet di git** untuk historis | Nol biaya, versioned, bisa di-audit |
| Notifikasi | **Telegram Bot API** | Gratis, sekaligus remote control bot |

---

## 3. STRUKTUR FOLDER (TIRUAN WEB-SCREENING + PENINGKATAN)

```
GLOBAL-STOCK-AI/
├── backend/
│   ├── main.py                 # FastAPI app + health + scheduler
│   ├── auth.py                 # login sederhana (bcrypt), pola WEB-SCREENING
│   ├── core/                   # logika murni, TANPA dependensi network → mudah dites
│   │   ├── data_loader.py      # baca cache parquet/csv dari folder data/
│   │   ├── screener.py         # mesin screening multi-pasar
│   │   ├── indicators.py       # EMA, RSI, ATR, volume analysis (versi sendiri, tanpa TA-Lib)
│   │   ├── signals.py          # aturan entry/exit → output sinyal terstruktur
│   │   ├── backtest.py         # backtest engine vektor (cukup pandas, no lib berat)
│   │   ├── risk.py             # position sizing, max daily loss, circuit breaker
│   │   ├── ai_service.py       # panggil Gemini/Groq (port dari WEB-SCREENING)
│   │   ├── detective.py        # "detektif" ala alpha_features.py: unusual volume, gap, breakout
│   │   ├── formatter.py        # format angka/tabel untuk UI & Telegram
│   │   └── archive.py          # snapshot harian → data/YYYY-MM-DD/ + auto-commit message
│   ├── adapters/               # SEMUA yang sentuh internet, terpisah dari core
│   │   ├── base.py             # DataAdapter interface + RateLimitManager
│   │   ├── yf_adapter.py       # yfinance
│   │   ├── stooq_adapter.py    # stooq CSV
│   │   ├── alpaca_adapter.py   # market data IEX + eksekusi order
│   │   ├── finnhub_adapter.py
│   │   ├── edgar_adapter.py    # SEC EDGAR (requests + JSON API)
│   │   ├── fred_adapter.py
│   │   ├── news_adapter.py     # gabungan RSS
│   │   └── broker_paper.py     # BrokerAdapter: order() → alpaca paper (nanti bisa ganti live)
│   ├── routes/
│   │   ├── api.py              # JSON API dashboard
│   │   └── bot_api.py          # endpoint untuk Telegram webhook
│   ├── templates/              # index, screener, radar, portofolio, jurnal, backtest
│   ├── static/                 # PWA: manifest.json, icon-192/512, service worker
│   └── models/                 # pydantic models
├── bot/
│   ├── telegram_bridge.py      # kontrol & laporan harian via Telegram
│   └── trader.py               # loop: sinyal → risk check → broker_paper.order()
├── jobs/                       # dipanggil GitHub Actions (CLI murni)
│   ├── job_fetch_daily.py      # fetch EOD semua pasar → parquet → commit
│   ├── job_screener.py         # jalankan screener → hasil harian
│   ├── job_archive.py          # snapshot + rekap
│   └── job_trader.py           # siklus trading paper (bisa jalan tiap 15 mnt market hours)
├── data/                       # OUTPUT (di-commit git = database gratisan)
│   ├── universe/               # daftar simbol dari Nasdaq Trader
│   ├── bars/                   # parquet per ticker (EOD)
│   ├── fundamentals/
│   └── YYYY-MM-DD/             # snapshot harian screener & portofolio
├── tests/                      # pytest untuk core/ (wajib untuk backtest & risk)
├── .github/workflows/
│   ├── fetch-daily.yml         # cron 22:00 UTC (setelah market close US)
│   ├── trader.yml              # cron */15 selama jam pasar US
│   └── keepalive.yml           # ping /health
├── .env.example                # daftar key (nilai kosong)
├── requirements.txt
└── railway.json                # disiapkan kalau mau deploy Railway (opsional)
```

**Kontrak penting (jangan dilanggar):**
- `core/` TIDAK boleh import library network — semua I/O lewat `adapters/` (mudah mock & test).
- Semua sumber data punya `RateLimitManager` — satu file konfigurasi kuota, bukan hardcoded.
- Semua API key lewat `.env`; file `.env` WAJIB ada di `.gitignore` sejak commit pertama.
- Data historis disimpan parquet per ticker, appfile naming `bars/{exchange}/{ticker}.parquet`.

---

## 4. FITUR (MVP → LANJUTAN)

### MVP (Fase 1–4)
1. **Universe otomatis** — unduh daftar simbol resmi Nasdaq Trader tiap hari (bukan hardcode).
2. **Screener global** — filter: likuiditas min, harga > $5, gap %, volume rasio, RSI, jarak EMA.
3. **Radar detektif** — port ide `alpha_features.py`: aksi volume tak wajar, breakout 52-minggu, konsistensi naik.
4. **Analisa AI** — per ticker: ringkas fundamental + berita + teknikal → skor & alasan bahasa manusia.
5. **Dashboard PWA** — halaman: Market Overview, Screener, Radar, AI Analisa, Portofolio Paper.
6. **Paper trading** — sinyal → `risk.py` (sizing % modal, max loss harian, max posisi) → order Alpaca paper.
7. **Jurnal otomatis** — tiap order dicatat + dievaluasi 5 hari kemudian (AI memberi "pelajaran").

### Lanjutan (Fase 5+) — ide pembeda
8. **Backtest-before-trade**: sinyal yang sama diuji 3 tahun ke belakang; order paper hanya
   dieksekusi kalau backtest menang (winrate & profit factor minimum). AI tidak boleh order
   tanpa bukti historis — ini pembeda terbesar dari bot "vibes".
9. **Regime filter (FRED)** — kalau yield 10Y/spread makro ekstrem, bot otomatis memperkecil ukuran posisi.
10. **Liga strategi** — 3 strategi berjalan paralel di paper (mis. momentum, mean-reversion, AI-fundamental),
    papan skor mingguan, modal dialokasikan ulang ke strategi juara (Kelly fraksional).
11. **Explainable signals** — setiap sinyal punya "mengapa saya beli" 3 kalimat; tidak ada black box.
12. **Circuit breaker** — drawdown hari ini > X% → trading berhenti otomatis + notifikasi Telegram.
13. **Earnings guard** — cek kalender earnings (Finnhub); tidak buka posisi H-2 sampai H+1 laporan.

---

## 5. ROADMAP & DEFINISI SELESAI

| Fase | Hasil | Definisi selesai |
|------|-------|------------------|
| 0 | Kerangka proyek | Folder sesuai §3, `.gitignore` (`.env`, `data/cache/`), `.env.example`, venv, pytest jalan, `GET /health` 200 |
| 1 | Data pipeline | `job_fetch_daily` sukses commit parquet ≥500 ticker US via Actions; fallback yf→stooq teruji |
| 2 | Screener + Radar | Halaman screener tampil <5 detik dari cache; radar menghasilkan ≥1 temuan di hari pasar aktif |
| 3 | AI analisa | Untuk 10 ticker teratas: ringkasan AI + skor tersimpan harian; kuota LLM tidak jebol (cache 24 jam) |
| 4 | Paper trading | 1 siklus lengkap: sinyal → risk → order Alpaca paper → tercatat di jurnal → laporan Telegram |
| 5 | Backtest gate | Strategi momentum lolos backtest 3 thn (winrate & PF laporan jelas); order diblokir kalau gagal gate |
| 6 | Liga + regime | 3 strategi paralel + papan skor + FRED regime filter aktif |
| 7 | Hardening | tests core ≥80% lulus, circuit breaker teruji (simulasi), dokumentasi README |

---

## 6. ATURAN KEAMANAN & BATASAN

1. `.env` tidak pernah di-commit; key di GitHub Actions pakai **Secrets**.
2. Rate limit tiap sumber dihormati; tidak ada retry beruntun tanpa backoff.
3. Live trading (uang asli) **di luar scope** sampai paper trade stabil ≥3 bulan dan pemilik
   memutuskan sendiri; broker adapter dirancang agar perpindahan itu hanya ganti 1 env var.
4. Tidak menjanjikan "dijamin profit" di UI; tampilkan disclaimer + statistik backtest apa adanya.
5. Log tidak pernah berisi nilai API key / token.

---

## 7. CARA PAKAI FILE INI

Setiap mulai sesi kerja baru, berikan ke asisten hanya **satu fase**:
`"Kerjakan Fase <N> dari /home/kaltaraid/Documents/GLOBAL-STOCK-AI/PROMPT_PROJECT_GLOBAL_STOCK_AI.md. Ikuti kontrak §3 dan definisi selesai §5. Laporkan file yang berubah + hasil verifikasi."`

Aturan untuk asisten: jangan melompat fase, jangan menambah layanan berbayar tanpa izin,
selalu tulis test untuk `core/`, dan tutup sesi dengan commit berpesan `feat(fase-N): ...`.

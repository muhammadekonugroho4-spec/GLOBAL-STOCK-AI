"""Berita publik untuk konteks AI - RSS resmi tanpa key, best-effort (gagal = kosong).

Sumber terverifikasi (17 Okt 2026): MarketWatch topstories + DJ feeds.
Yahoo per-ticker 429 dari jaringan ini - dicoba terakhir, gagal diabaikan.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) gsai-news/0.1"}
MARKET_FEEDS = [
    "https://www.marketwatch.com/rss/topstories",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
]
TICKER_FEED = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"

_CLEAN = re.compile(r"<[^>]+>")


@dataclass
class NewsItem:
    title: str
    link: str
    source: str


def parse_rss(text: str, source: str, limit: int = 10) -> list[NewsItem]:
    """Parse RSS/Atom minimalis via stdlib - konten feed dipercaya hanya sebagai data."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    items: list[NewsItem] = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if title:
            items.append(NewsItem(title=_CLEAN.sub("", title)[:200], link=link, source=source))
        if len(items) >= limit:
            return items
    for it in root.iter("{http://www.w3.org/2005/Atom}entry"):
        title = (it.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        if title:
            items.append(NewsItem(title=_CLEAN.sub("", title)[:200], link="", source=source))
        if len(items) >= limit:
            return items
    return items


def fetch_market_news(timeout: int = 10, per_feed: int = 5) -> list[NewsItem]:
    out: list[NewsItem] = []
    for url in MARKET_FEEDS:
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            if r.status_code == 200:
                out.extend(parse_rss(r.text, url.split("/")[2], per_feed))
        except requests.RequestException:
            continue
    return out


def fetch_ticker_news(ticker: str, timeout: int = 6) -> list[NewsItem]:
    try:
        r = requests.get(TICKER_FEED.format(ticker=ticker), headers=UA, timeout=timeout)
        if r.status_code == 200:
            return parse_rss(r.text, "yahoo", 5)
    except requests.RequestException:
        pass
    return []  # best-effort: 429/challenge = tanpa berita ticker

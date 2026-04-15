"""
pipeline.py — web_scraping skill (v2)
--------------------------------------
Entry point skill web_scraping untuk agent web_scraper.
Membaca daftar URL dari sources_config.json — tidak ada URL hardcode.

Supported source types:
  listing → fetch halaman daftar berita → extract link artikel → filter relevan
  article → fetch URL artikel langsung → ambil konten
  rss     → parse RSS/Atom XML feed → paling clean

Location: /workspaces/web_scraper/skills/web_scraping/pipeline.py
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sources import load_sources, load_defaults, SECTOR_KEYWORDS, KNOWN_TICKERS
from fetcher import fetch
from parser  import (parse_articles_html, deduplicate,
                     aggregate_sentiment, classify_sentiment,
                     extract_tickers, clean_text)
from cache   import get as cache_get, set as cache_set, build_minimal_output


# ── RSS Parser ────────────────────────────────────────────────────────────────

def parse_rss(xml_content: str, source_name: str, ticker_filter: str = "") -> list[dict]:
    """
    Parse RSS atau Atom feed XML.
    RSS adalah format paling reliable — struktur baku, tidak tergantung HTML.
    """
    articles = []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"  ⚠️  RSS parse error ({source_name}): {e}")
        return []

    # Deteksi format: RSS vs Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    is_atom = root.tag.endswith("feed") or "atom" in root.tag.lower()

    if is_atom:
        items = root.findall(".//atom:entry", ns) or root.findall("entry")
    else:
        items = root.findall(".//item")

    for item in items:
        # Title
        title_el = (item.find("title") or
                    item.find("{http://www.w3.org/2005/Atom}title"))
        title = clean_text(
            title_el.text or title_el.get("value", "") if title_el is not None else "",
            max_chars=200
        )

        if not title or len(title) < 10:
            continue

        # Filter ticker jika diminta
        if ticker_filter and ticker_filter.upper() not in title.upper():
            # Cek juga di description
            desc_el = (item.find("description") or
                       item.find("{http://www.w3.org/2005/Atom}summary") or
                       item.find("{http://www.w3.org/2005/Atom}content"))
            desc_text = desc_el.text if desc_el is not None else ""
            if ticker_filter.upper() not in (desc_text or "").upper():
                continue

        # URL
        url = ""
        link_el = (item.find("link") or
                   item.find("{http://www.w3.org/2005/Atom}link"))
        if link_el is not None:
            url = link_el.text or link_el.get("href", "")

        # Summary / Description
        desc_el = (item.find("description") or
                   item.find("{http://www.w3.org/2005/Atom}summary") or
                   item.find("{http://www.w3.org/2005/Atom}content"))
        summary = ""
        if desc_el is not None and desc_el.text:
            summary = clean_text(desc_el.text, max_chars=300)
        if not summary:
            summary = title

        # Published date
        pub_el = (item.find("pubDate") or
                  item.find("{http://www.w3.org/2005/Atom}published") or
                  item.find("{http://www.w3.org/2005/Atom}updated"))
        published_at = datetime.now(timezone.utc).isoformat()
        if pub_el is not None and pub_el.text:
            from parser import parse_date
            parsed = parse_date(pub_el.text)
            if parsed:
                published_at = parsed

        sentiment, score = classify_sentiment(title + " " + summary)
        tickers = extract_tickers(title + " " + summary)

        articles.append({
            "title":            title,
            "summary":          summary,
            "url":              url.strip() if url else "",
            "source":           source_name,
            "publishedAt":      published_at,
            "sentiment":        sentiment,
            "sentimentScore":   score,
            "tickersMentioned": tickers,
        })

    return articles


# ── Dispatch per Source Type ──────────────────────────────────────────────────

def fetch_from_source(source: dict, ticker_filter: str = "",
                      keyword_filter: str = "") -> list[dict]:
    """
    Fetch dan parse artikel dari satu sumber berdasarkan type-nya.

    Args:
        source:         source config dari sources_config.json
        ticker_filter:  filter artikel yang menyebut ticker ini (opsional)
        keyword_filter: filter artikel yang mengandung keyword ini (opsional)

    Returns:
        list artikel yang sudah diparse
    """
    source_name  = source.get("name", "Unknown")
    source_type  = source.get("type", "listing")
    urls         = source.get("urls", [])
    rate_limit   = source.get("rate_limit_s", 2)
    ticker_filt  = source.get("ticker_filter", True)

    # Query string untuk filter
    query = ticker_filter or keyword_filter or ""

    articles = []

    for url in urls:
        html = fetch(url, rate_limit_s=rate_limit)
        if not html:
            continue

        if source_type == "rss":
            found = parse_rss(html, source_name,
                              ticker_filter=query if ticker_filt else "")

        elif source_type == "article":
            # URL artikel langsung — ambil seluruh konten
            found = _parse_article_page(html, url, source_name, query)

        else:  # listing (default)
            found = parse_articles_html(html, source, query=query)

        articles.extend(found)
        print(f"  ✓ {source_name} [{source_type}] ({url[:50]}...): {len(found)} artikel")

    return articles


def _parse_article_page(html: str, url: str, source_name: str,
                        keyword: str = "") -> list[dict]:
    """
    Parse halaman artikel tunggal — ambil judul dan konten utama.
    """
    # Coba BeautifulSoup dulu
    try:
        from bs4 import BeautifulSoup
        soup    = BeautifulSoup(html, "html.parser")

        # Hapus nav, footer, sidebar
        for tag in soup(["nav", "footer", "aside", "script", "style", "header"]):
            tag.decompose()

        # Title
        title = ""
        for sel in ["h1", "h2", ".title", ".judul", "title"]:
            el = soup.select_one(sel)
            if el:
                title = clean_text(el.get_text(), max_chars=200)
                if len(title) > 10:
                    break

        # Content paragraphs
        paragraphs = soup.find_all("p")
        content    = " ".join(p.get_text(strip=True) for p in paragraphs[:5])
        summary    = clean_text(content, max_chars=300) or title

    except ImportError:
        # Fallback regex
        title_m = re.search(r'<h1[^>]*>([^<]{10,200})</h1>', html, re.IGNORECASE)
        title   = clean_text(title_m.group(1) if title_m else "", max_chars=200)
        summary = title

    if not title or len(title) < 10:
        return []

    if keyword and keyword.lower() not in (title + summary).lower():
        return []

    sentiment, score = classify_sentiment(title + " " + summary)
    tickers = extract_tickers(title + " " + summary)

    return [{
        "title":            title,
        "summary":          summary,
        "url":              url,
        "source":           source_name,
        "publishedAt":      datetime.now(timezone.utc).isoformat(),
        "sentiment":        sentiment,
        "sentimentScore":   score,
        "tickersMentioned": tickers,
    }]


# ── Mode: scrape_news ─────────────────────────────────────────────────────────

def scrape_news(symbol: str, hours: int = 24, max_articles: int = 10) -> dict:
    symbol   = symbol.upper().strip()
    defaults = load_defaults()
    sources  = load_sources()

    print(f"📰 scrape_news: {symbol} | {hours}h | {len(sources)} sumber aktif")

    if not sources:
        return {
            "status":  "error",
            "error":   "Tidak ada sumber aktif. Isi sources_config.json terlebih dahulu.",
            "symbol":  symbol
        }

    # Cek cache
    cached = cache_get("news", f"{symbol}_{hours}h")
    if cached:
        return build_minimal_output(cached, max_articles)

    articles = []
    for source in sources:
        found = fetch_from_source(source, ticker_filter=symbol)
        articles.extend(found)

    articles = deduplicate(articles)[:max_articles * 2]
    overall  = aggregate_sentiment([a["sentiment"] for a in articles])

    full_result = {
        "symbol":           symbol,
        "scrapedAt":        datetime.now(timezone.utc).isoformat(),
        "hours":            hours,
        "overallSentiment": overall,
        "totalFound":       len(articles),
        "articles":         articles,
    }

    cache_set("news", f"{symbol}_{hours}h", full_result)
    print(f"  ✅ {len(articles)} artikel | sentimen: {overall}")
    return build_minimal_output(full_result, max_articles=5)


# ── Mode: scrape_trending ─────────────────────────────────────────────────────

def scrape_trending(hours: int = 48) -> dict:
    sources  = load_sources()
    print(f"📈 scrape_trending | {hours}h | {len(sources)} sumber")

    if not sources:
        return {"status": "error", "error": "Tidak ada sumber aktif."}

    cached = cache_get("trending", f"IDX_{hours}h")
    if cached:
        return build_minimal_output(cached)

    ticker_mentions: dict[str, dict] = {}
    headlines = []

    for source in sources:
        # Ambil semua artikel tanpa filter ticker
        articles = fetch_from_source(source, ticker_filter="", keyword_filter="saham")
        for a in articles:
            tickers = a.get("tickersMentioned", []) or extract_tickers(a.get("title",""))
            for ticker in tickers:
                if ticker not in ticker_mentions:
                    ticker_mentions[ticker] = {
                        "symbol":   ticker,
                        "mentions": 0,
                        "sector":   _guess_sector(ticker),
                        "sources":  set(),
                    }
                ticker_mentions[ticker]["mentions"] += 1
                ticker_mentions[ticker]["sources"].add(source["name"])

            if a.get("title"):
                headlines.append({
                    "ticker":      tickers[0] if tickers else "",
                    "title":       a["title"][:120],
                    "source":      a["source"],
                    "publishedAt": a.get("publishedAt","")[:10],
                    "sentiment":   a.get("sentiment","neutral"),
                })

    top_tickers = sorted(
        [{"symbol": k, **{kk: vv for kk, vv in v.items() if kk != "sources"},
          "sources": list(v["sources"])}
         for k, v in ticker_mentions.items()],
        key=lambda x: x["mentions"], reverse=True
    )[:10]

    sector_counts: dict[str, int] = {}
    for t in top_tickers:
        s = t.get("sector", "")
        if s:
            sector_counts[s] = sector_counts.get(s, 0) + t["mentions"]
    top_sectors = sorted(sector_counts, key=sector_counts.get, reverse=True)[:3]

    full_result = {
        "scrapedAt":    datetime.now(timezone.utc).isoformat(),
        "hours":        hours,
        "topTickers":   top_tickers,
        "topSectors":   top_sectors,
        "headlines":    headlines[:15],
        "totalTickers": len(top_tickers),
    }

    cache_set("trending", f"IDX_{hours}h", full_result)
    print(f"  ✅ {len(top_tickers)} ticker trending | sectors: {top_sectors}")
    return build_minimal_output(full_result)


# ── Mode: scrape_sector ───────────────────────────────────────────────────────

def scrape_sector(sector: str, hours: int = 48) -> dict:
    keywords = SECTOR_KEYWORDS.get(sector)
    sources  = load_sources()

    if not keywords:
        return {
            "status": "error",
            "error":  f"Sektor '{sector}' tidak dikenal. Pilihan: {list(SECTOR_KEYWORDS.keys())}"
        }

    print(f"🏭 scrape_sector: {sector} | {hours}h | {len(sources)} sumber")

    cached = cache_get("sector", f"{sector}_{hours}h")
    if cached:
        return build_minimal_output(cached)

    articles      = []
    tickers_found = set()

    for source in sources:
        # Gunakan keyword pertama yang paling spesifik sebagai filter
        primary_keyword = keywords[0]
        found = fetch_from_source(source, keyword_filter=primary_keyword)
        for a in found:
            for t in a.get("tickersMentioned", []):
                tickers_found.add(t)
        articles.extend(found)

    articles = deduplicate(articles)[:15]
    overall  = aggregate_sentiment([a["sentiment"] for a in articles])

    full_result = {
        "sector":           sector,
        "scrapedAt":        datetime.now(timezone.utc).isoformat(),
        "hours":            hours,
        "overallSentiment": overall,
        "tickersMentioned": list(tickers_found),
        "totalFound":       len(articles),
        "articles":         articles,
    }

    cache_set("sector", f"{sector}_{hours}h", full_result)
    print(f"  ✅ {len(articles)} artikel | tickers: {list(tickers_found)[:5]}")
    return build_minimal_output(full_result, max_articles=5)


# ── Helper ────────────────────────────────────────────────────────────────────

def _guess_sector(ticker: str) -> str:
    sector_map = {
        "BBCA":"banking","BBRI":"banking","BMRI":"banking","BBNI":"banking",
        "ITMG":"coal_mining","ADRO":"coal_mining","PTBA":"coal_mining",
        "TLKM":"telco","EXCL":"telco","ISAT":"telco",
        "ICBP":"consumer","INDF":"consumer","UNVR":"consumer",
        "ASII":"automotive","SMSM":"automotive",
        "ANTM":"mining_metals","INCO":"mining_metals","MDKA":"mining_metals",
        "BSDE":"property","SMRA":"property","CTRA":"property",
        "PGAS":"energy","MEDC":"energy","AKRA":"energy",
    }
    return sector_map.get(ticker, "")


# ── Entry Point ───────────────────────────────────────────────────────────────

def run(input: dict) -> dict:
    """
    Main entry point — dipanggil OpenClaw skill runner.

    Input fields:
      mode         : "scrape_news" | "scrape_trending" | "scrape_sector"
      symbol       : ticker IDX (untuk scrape_news)
      sector       : nama sektor (untuk scrape_sector)
      hours        : lookback window (default 24)
      max_articles : jumlah artikel max (default 10)
    """
    mode         = input.get("mode", "scrape_news")
    hours        = int(input.get("hours", 24))
    max_articles = int(input.get("max_articles", 10))

    if mode == "scrape_news":
        symbol = input.get("symbol", "").upper().strip()
        if not symbol:
            return {"status": "error", "error": "symbol wajib untuk scrape_news"}
        return scrape_news(symbol, hours, max_articles)

    elif mode == "scrape_trending":
        return scrape_trending(hours)

    elif mode == "scrape_sector":
        sector = input.get("sector", "").lower().strip()
        if not sector:
            return {"status": "error", "error": "sector wajib untuk scrape_sector"}
        return scrape_sector(sector, hours)

    else:
        return {
            "status": "error",
            "error":  f"Mode tidak dikenal: '{mode}'. Gunakan: scrape_news | scrape_trending | scrape_sector"
        }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="{}")
    args = parser.parse_args()

    try:
        result = run(json.loads(args.input))
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False))
        sys.exit(1)

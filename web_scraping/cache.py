"""
cache.py
--------
File-based cache untuk hasil scraping.
Mencegah hit ulang ke sumber yang sama dalam waktu dekat.

Location: /workspaces/web_scraper/skills/web_scraping/cache.py
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

CACHE_DIR     = "/workspaces/web_scraper/data/cache"
CACHE_TTL_S   = 1800  # 30 menit — jangan scrape sumber yang sama terlalu sering


def _cache_key(mode: str, identifier: str) -> str:
    """Build cache file path."""
    date = datetime.now().strftime("%Y%m%d")
    safe = identifier.replace("/", "_").replace(":", "_")
    return str(Path(CACHE_DIR) / f"{mode}_{safe}_{date}.json")


def get(mode: str, identifier: str) -> dict | None:
    """
    Ambil cached result jika masih fresh.
    Returns None jika tidak ada cache atau sudah expired.
    """
    path = _cache_key(mode, identifier)
    if not Path(path).exists():
        return None

    try:
        stat = os.stat(path)
        age  = time.time() - stat.st_mtime
        if age > CACHE_TTL_S:
            return None  # Cache expired

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  💾 Cache hit: {mode}/{identifier} ({age:.0f}s ago)")
        return data

    except Exception:
        return None


def set(mode: str, identifier: str, data: dict):
    """Simpan result ke cache."""
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    path = _cache_key(mode, identifier)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                **data,
                "_cached_at": datetime.now(timezone.utc).isoformat()
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️  Cache write failed: {e}")


def build_minimal_output(full_result: dict, max_articles: int = 5) -> dict:
    """
    Buat versi minimal dari hasil scraping untuk dikembalikan ke LLM.
    Full data tetap tersimpan di cache file — LLM hanya dapat ringkasan.

    Ini mencegah ribuan token artikel membanjiri context LLM.
    """
    articles     = full_result.get("articles", [])
    top_articles = articles[:max_articles]

    return {
        "symbol":           full_result.get("symbol"),
        "sector":           full_result.get("sector"),
        "scrapedAt":        full_result.get("scrapedAt"),
        "overallSentiment": full_result.get("overallSentiment", "unavailable"),
        "totalFound":       full_result.get("totalFound", 0),
        "articles": [
            {
                "title":       a.get("title", ""),
                "summary":     a.get("summary", "")[:200],
                "source":      a.get("source", ""),
                "publishedAt": a.get("publishedAt", "")[:10],  # date only
                "sentiment":   a.get("sentiment", "neutral"),
                "url":         a.get("url", ""),
            }
            for a in top_articles
        ],
        "topTickers":  full_result.get("topTickers", []),
        "topSectors":  full_result.get("topSectors", []),
        "cache_path":  full_result.get("cache_path", ""),
    }

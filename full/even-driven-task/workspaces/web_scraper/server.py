"""
server.py — web_scraper agent
Location: /workspaces/web_scraper/server.py
Run with: python server.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Shared modules from /workspaces/shared/
sys.path.insert(0, "/workspaces/shared")
from agent_server import AgentServer
from task_contract import SkillName

LOGS_DIR    = "/workspaces/web_scraper/logs"
CONFIG_PATH = "/workspaces/web_scraper/config/sources.json"
MEMORY_PATH = "/workspaces/web_scraper/MEMORY.md"

# Default sources if config missing
DEFAULT_SOURCES = [
    { "name": "Kontan",         "base_url": "https://www.kontan.co.id",      "priority": 1 },
    { "name": "Bisnis",         "base_url": "https://www.bisnis.com",         "priority": 2 },
    { "name": "CNBC Indonesia", "base_url": "https://www.cnbcindonesia.com",  "priority": 3 },
    { "name": "IDX",            "base_url": "https://www.idx.co.id",          "priority": 4 },
    { "name": "Investing.id",   "base_url": "https://id.investing.com",       "priority": 5 },
    { "name": "Detik Finance",  "base_url": "https://finance.detik.com",      "priority": 6 },
]


class WebScraperServer(AgentServer):

    def __init__(self):
        super().__init__(agent_id="web_scraper", port=8002)
        self.register_skill(SkillName.SCRAPE_NEWS,     self.scrape_news)
        self.register_skill(SkillName.SCRAPE_TRENDING, self.scrape_trending)
        self.register_skill(SkillName.SCRAPE_SECTOR,   self.scrape_sector)

        os.makedirs(LOGS_DIR, exist_ok=True)
        self.sources = self._load_sources()
        self.log.info(f"Loaded {len(self.sources)} news sources")

    # ── Skills ────────────────────────────────────────────────────────────────

    def scrape_news(self, payload: dict) -> dict:
        """
        Fetch and structure news articles for a specific IDX ticker.
        Queries each source in priority order, stops at max_articles.
        """
        symbol       = payload.get("symbol", "").upper()
        hours        = payload.get("hours", 24)
        max_articles = payload.get("max_articles", 10)

        if not symbol:
            return { "status": "error", "reason": "symbol_required" }

        t_start  = time.time()
        articles = []

        for source in self.sources:
            if len(articles) >= max_articles:
                break
            fetched = self._fetch_news_from_source(source, symbol, hours)
            articles.extend(fetched)

        # Deduplicate by title similarity
        articles = self._deduplicate(articles)[:max_articles]

        # Overall sentiment
        overall = self._aggregate_sentiment(articles)

        result = {
            "symbol":          symbol,
            "scrapedAt":       datetime.now(timezone.utc).isoformat(),
            "hours":           hours,
            "overallSentiment": overall,
            "totalFound":      len(articles),
            "articles":        articles
        }

        self._log_scrape("scrape_news", symbol, len(articles), time.time() - t_start)
        return result

    def scrape_trending(self, payload: dict) -> dict:
        """
        Identify trending IDX tickers and hot sectors from news sources.
        """
        market = payload.get("market", "IDX")
        hours  = payload.get("hours", 48)
        t_start = time.time()

        ticker_mentions: dict[str, dict] = {}
        headlines = []

        for source in self.sources[:4]:  # Top 4 sources for trending
            items = self._fetch_trending_from_source(source, hours)
            for item in items:
                ticker = item.get("ticker", "")
                if ticker:
                    if ticker not in ticker_mentions:
                        ticker_mentions[ticker] = {
                            "symbol":    ticker,
                            "mentions":  0,
                            "sentiment": "neutral",
                            "sector":    ""
                        }
                    ticker_mentions[ticker]["mentions"] += 1
                headlines.append(item)

        # Sort by mention count
        top_tickers = sorted(
            ticker_mentions.values(),
            key=lambda x: x["mentions"],
            reverse=True
        )[:10]

        result = {
            "market":         market,
            "scrapedAt":      datetime.now(timezone.utc).isoformat(),
            "hours":          hours,
            "topTickers":     top_tickers,
            "topSectors":     self._extract_top_sectors(top_tickers),
            "recentHeadlines": headlines[:20]
        }

        self._log_scrape("scrape_trending", market, len(top_tickers), time.time() - t_start)
        return result

    def scrape_sector(self, payload: dict) -> dict:
        """
        Fetch news for an entire IDX sector.
        """
        sector  = payload.get("sector", "")
        hours   = payload.get("hours", 48)
        t_start = time.time()

        if not sector:
            return { "status": "error", "reason": "sector_required" }

        # Sector → search keywords mapping
        sector_keywords = {
            "banking":      ["bank", "perbankan", "kredit", "BI rate"],
            "coal_mining":  ["batubara", "coal", "tambang batu bara"],
            "telco":        ["telekomunikasi", "telco", "seluler", "internet"],
            "consumer":     ["consumer", "FMCG", "ritel", "konsumen"],
            "automotive":   ["otomotif", "mobil", "kendaraan"],
            "mining_metals":["nikel", "emas", "tembaga", "mineral"],
            "property":     ["properti", "real estate", "perumahan"],
        }
        keywords = sector_keywords.get(sector, [sector])

        articles = []
        tickers_found = set()

        for source in self.sources:
            fetched = self._fetch_sector_news(source, keywords, hours)
            for a in fetched:
                articles.append(a)
                for t in a.get("tickers_mentioned", []):
                    tickers_found.add(t)

        articles = self._deduplicate(articles)[:20]
        overall  = self._aggregate_sentiment(articles)

        result = {
            "sector":           sector,
            "scrapedAt":        datetime.now(timezone.utc).isoformat(),
            "hours":            hours,
            "overallSentiment": overall,
            "tickersMentioned": list(tickers_found),
            "totalFound":       len(articles),
            "articles":         articles
        }

        self._log_scrape("scrape_sector", sector, len(articles), time.time() - t_start)
        return result

    # ── Internal Scraping ─────────────────────────────────────────────────────

    def _fetch_news_from_source(self, source: dict, symbol: str, hours: int) -> list:
        """
        Fetch news articles for a ticker from one source.
        Replace search_url construction with actual source-specific selectors
        from config/sources.json.
        """
        source_name = source["name"]
        base_url    = source["base_url"]
        articles    = []

        # Build search URL — customize per source
        search_urls = {
            "Kontan":         f"{base_url}/search?q={symbol}",
            "Bisnis":         f"{base_url}/search?keywords={symbol}",
            "CNBC Indonesia": f"{base_url}/search/?query={symbol}",
            "IDX":            f"{base_url}/id/berita/siaran-pers",
            "Investing.id":   f"{base_url}/search/?q={symbol}",
            "Detik Finance":  f"{base_url}/search/?query={symbol}",
        }

        url = search_urls.get(source_name)
        if not url:
            return []

        html = self._http_get(url)
        if not html:
            return []

        # Parse articles from HTML
        # In production: use CSS selectors from config/sources.json
        # Placeholder — returns empty until selectors are configured
        return articles

    def _fetch_trending_from_source(self, source: dict, hours: int) -> list:
        """Fetch trending tickers from one source's most-read section."""
        # Placeholder — implement with actual CSS selectors per source
        return []

    def _fetch_sector_news(self, source: dict, keywords: list, hours: int) -> list:
        """Fetch sector news using keyword search."""
        # Placeholder — implement with actual CSS selectors per source
        return []

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def _http_get(self, url: str, timeout: int = 10) -> str | None:
        """Fetch URL, handle rate limits and errors per SOUL.md rules."""
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; IDXNewsBot/1.0)",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8"
        }
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Rate limited — wait and retry once
                time.sleep(10)
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        return resp.read().decode("utf-8", errors="replace")
                except Exception:
                    return None
            elif e.code in (403, 503):
                self.log.warning(f"Source blocked ({e.code}): {url}")
                return None
            return None
        except Exception as e:
            self.log.warning(f"HTTP error for {url}: {e}")
            return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _classify_sentiment(self, text: str) -> tuple[str, float]:
        """
        Rule-based sentiment classification per SOUL.md.
        Returns (label, score).
        """
        text_lower = text.lower()

        positive_signals = [
            "laba", "untung", "naik", "tumbuh", "rekor", "dividen", "akuisisi",
            "ekspansi", "profit", "gain", "upgrade", "strong", "bullish",
            "kinerja positif", "melampaui ekspektasi"
        ]
        negative_signals = [
            "rugi", "turun", "anjlok", "gagal", "default", "masalah", "hutang",
            "penurunan", "downgrade", "bearish", "loss", "melemah",
            "tertekan", "sanksi", "investigasi"
        ]

        pos_count = sum(1 for w in positive_signals if w in text_lower)
        neg_count = sum(1 for w in negative_signals if w in text_lower)

        if pos_count > neg_count:
            score = min(0.5 + pos_count * 0.1, 1.0)
            return "positive", round(score, 2)
        elif neg_count > pos_count:
            score = min(0.5 + neg_count * 0.1, 1.0)
            return "negative", round(score, 2)
        return "neutral", 0.5

    def _aggregate_sentiment(self, articles: list) -> str:
        if not articles:
            return "unavailable"
        counts = {"positive": 0, "negative": 0, "neutral": 0}
        for a in articles:
            counts[a.get("sentiment", "neutral")] += 1
        pos, neg, neu = counts["positive"], counts["negative"], counts["neutral"]
        if pos > neg and pos > neu:
            return "positive"
        if neg > pos and neg > neu:
            return "negative"
        if pos > 0 and neg > 0:
            return "mixed"
        return "neutral"

    def _deduplicate(self, articles: list) -> list:
        """Remove duplicate articles by title Jaccard similarity > 0.8."""
        seen  = []
        dedup = []
        for a in articles:
            title_tokens = set(a.get("title", "").lower().split())
            is_dup = False
            for s in seen:
                inter = title_tokens & s
                union = title_tokens | s
                if union and len(inter) / len(union) > 0.8:
                    is_dup = True
                    break
            if not is_dup:
                dedup.append(a)
                seen.append(title_tokens)
        return dedup

    def _extract_top_sectors(self, tickers: list) -> list:
        """Extract unique sectors from ticker list."""
        sectors = set()
        for t in tickers:
            if t.get("sector"):
                sectors.add(t["sector"])
        return list(sectors)[:3]

    def _extract_tickers(self, text: str) -> list:
        """Find 4-letter uppercase IDX tickers in text."""
        import re
        return list(set(re.findall(r'\b[A-Z]{4}\b', text)))

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_sources(self) -> list:
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f).get("sources", DEFAULT_SOURCES)
        except Exception:
            self.log.warning("config/sources.json not found — using defaults")
            return DEFAULT_SOURCES

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log_scrape(self, task: str, target: str, found: int, duration: float):
        entry = json.dumps({
            "ts":       datetime.now(timezone.utc).isoformat(),
            "task":     task,
            "target":   target,
            "found":    found,
            "duration_s": round(duration, 2)
        })
        with open(f"{LOGS_DIR}/scrape_log.jsonl", "a") as f:
            f.write(entry + "\n")

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def _update_heartbeat(self):
        hb = {
            "agent_id":  "web_scraper",
            "status":    "ok",
            "last_ping": datetime.now(timezone.utc).isoformat(),
            "port":      self.port,
            "components": {
                "sources_total":     len(self.sources),
                "sources_reachable": len(self.sources)  # updated after actual scrape
            }
        }
        os.makedirs("/workspaces/web_scraper", exist_ok=True)
        with open("/workspaces/web_scraper/heartbeat.json", "w") as f:
            json.dump(hb, f, indent=2)


if __name__ == "__main__":
    WebScraperServer().start()
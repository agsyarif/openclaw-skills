# AGENTS: web_scraper

## Position in System
web_scraper is a downstream agent. It receives tasks from orchestrator only.
It does not call other agents. It does not initiate anything autonomously.

```
orchestrator
    ├──→ web_scraper.scrape_news(symbol, hours, max_articles)
    ├──→ web_scraper.scrape_trending(market, hours)
    └──→ web_scraper.scrape_sector(sector, hours)
```

---

## Upstream: orchestrator

All task inputs arrive as structured JSON.

```json
// scrape_news
{ "task": "scrape_news", "symbol": "ITMG", "hours": 24, "max_articles": 10 }

// scrape_trending
{ "task": "scrape_trending", "market": "IDX", "hours": 48 }

// scrape_sector
{ "task": "scrape_sector", "sector": "coal_mining", "hours": 48 }
```

---

## Output Schemas

### scrape_news → NewsResult
```json
{
  "symbol": "ITMG",
  "scrapedAt": "ISO8601",
  "hours": 24,
  "overallSentiment": "positive | negative | neutral | mixed",
  "totalFound": 3,
  "articles": [
    {
      "title": "string",
      "summary": "string (max 500 chars)",
      "url": "string",
      "source": "Kontan | Bisnis | CNBC Indonesia | idx.co.id | Investing.com | Detik Finance",
      "publishedAt": "ISO8601",
      "sentiment": "positive | negative | neutral",
      "sentimentScore": 0.75
    }
  ]
}
```

### scrape_trending → TrendingResult
```json
{
  "market": "IDX",
  "scrapedAt": "ISO8601",
  "hours": 48,
  "topTickers": [
    { "symbol": "BBCA", "mentions": 12, "sentiment": "positive", "sector": "banking" }
  ],
  "topSectors": ["banking", "coal_mining"],
  "recentHeadlines": [
    { "ticker": "BBCA", "title": "string", "source": "string", "publishedAt": "ISO8601" }
  ]
}
```

### scrape_sector → SectorResult
```json
{
  "sector": "coal_mining",
  "scrapedAt": "ISO8601",
  "overallSentiment": "positive | negative | neutral | mixed",
  "tickersMentioned": ["ITMG", "ADRO"],
  "articles": []
}
```

---

## Workspace Structure
```
/workspaces/web_scraper/
├── IDENTITY.md
├── SOUL.md
├── AGENTS.md
├── TOOLS.md
├── HEARTBEAT.md
├── BOOTSTRAP.md
├── MEMORY.md
├── heartbeat.json
├── skills/
│   ├── scrape_news/
│   │   └── run.py
│   ├── scrape_trending/
│   │   └── run.py
│   └── scrape_sector/
│       └── run.py
├── config/
│   └── sources.json         ← source URLs, selectors, rate limit settings
└── logs/
    └── scrape_log.jsonl     ← one entry per scrape job
```

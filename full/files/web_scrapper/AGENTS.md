# AGENTS: web_scraper

## Position in System

web_scraper is a downstream agent. It receives tasks from orchestrator only.
It does not call other agents. It does not initiate anything autonomously.

```
orchestrator
    └──→ web_scraper / web_scraping
```

---

## Upstream: orchestrator

All task inputs arrive as structured JSON via skill `web_scraping`.

```json
// scrape_news — berita untuk satu ticker
{ "mode": "scrape_news", "symbol": "ITMG", "hours": 24, "max_articles": 10 }

// scrape_trending — ticker IDX yang sedang trending
{ "mode": "scrape_trending", "hours": 48 }

// scrape_sector — berita per sektor IDX
{ "mode": "scrape_sector", "sector": "banking", "hours": 48 }
```

Available sectors: `banking`, `coal_mining`, `telco`, `consumer`,
`automotive`, `mining_metals`, `property`, `energy`

---

## Output Schemas

### scrape_news → NewsResult

```json
{
  "symbol": "ITMG",
  "scrapedAt": "ISO8601",
  "hours": 24,
  "overallSentiment": "positive | negative | neutral | mixed | unavailable",
  "totalFound": 3,
  "articles": [
    {
      "title": "string",
      "summary": "string (max 300 chars)",
      "url": "string",
      "source": "string (dari sources_config.json)",
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
  "scrapedAt": "ISO8601",
  "hours": 48,
  "topTickers": [
    {
      "symbol": "BBCA",
      "mentions": 12,
      "sector": "banking",
      "sources": ["Kontan"]
    }
  ],
  "topSectors": ["banking", "coal_mining"],
  "headlines": [
    {
      "ticker": "BBCA",
      "title": "string",
      "source": "string",
      "publishedAt": "ISO8601",
      "sentiment": "positive"
    }
  ],
  "totalTickers": 10
}
```

### scrape_sector → SectorResult

```json
{
  "sector": "coal_mining",
  "scrapedAt": "ISO8601",
  "hours": 48,
  "overallSentiment": "positive | negative | neutral | mixed",
  "tickersMentioned": ["ITMG", "ADRO"],
  "totalFound": 8,
  "articles": []
}
```

---

## News Sources

Sources dikonfigurasi di `/workspaces/web_scraper/config/sources_config.json`.
Tidak ada URL hardcode di dalam kode — semua diambil dari config file.

Supported source types:

- `rss` — RSS/Atom XML feed (paling direkomendasikan)
- `listing` — Halaman daftar berita (di-parse HTML-nya)
- `article` — URL artikel langsung

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
│   └── web_scraping/         ← skill utama
│       ├── SKILL.md
│       ├── pipeline.py       ← entry point
│       ├── sources.py        ← load config + sector keywords
│       ├── fetcher.py        ← HTTP layer + rate limiting
│       ├── parser.py         ← HTML/RSS parser + sentiment
│       └── cache.py          ← file-based cache (TTL 30 menit)
├── config/
│   └── sources_config.json   ← daftar URL sumber (diisi user)
├── data/
│   └── cache/                ← hasil scrape tersimpan di sini
└── logs/
    └── scrape_log.jsonl
```

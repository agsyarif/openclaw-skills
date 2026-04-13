# MEMORY: web_scraper

## Source Config Cache
Loaded from `config/sources.json` on startup. Not written here.
Kept in MEMORY.md for reference — edit sources.json to change.

```json
{
  "sources": [
    { "name": "Kontan",         "base_url": "https://www.kontan.co.id",         "priority": 1 },
    { "name": "Bisnis",         "base_url": "https://www.bisnis.com",            "priority": 2 },
    { "name": "CNBC Indonesia", "base_url": "https://www.cnbcindonesia.com",     "priority": 3 },
    { "name": "IDX",            "base_url": "https://www.idx.co.id",             "priority": 4 },
    { "name": "Investing.id",   "base_url": "https://id.investing.com",          "priority": 5 },
    { "name": "Detik Finance",  "base_url": "https://finance.detik.com",         "priority": 6 }
  ]
}
```

## Temporarily Blocked Sources
Sources that returned 403/503 in recent scrapes.
Auto-cleared after 1 hour.
```json
[]
```
Example: `[{ "source": "Bisnis", "blocked_until": "ISO8601", "reason": "403" }]`

## Scrape Stats (last 24h)
Updated after each scrape job. Used for heartbeat component status.
```json
{
  "total_jobs": 0,
  "total_articles": 0,
  "last_job_at": null,
  "avg_duration_s": 0.0
}
```

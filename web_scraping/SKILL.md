---
name: web_scraping
agent: web_scraper
description: "Scrape berita keuangan Indonesia dari sumber terpercaya (Kontan, Bisnis, CNBC Indonesia, IDX, dll). Dukung 3 mode: scrape_news (per ticker), scrape_trending (ticker trending IDX), scrape_sector (per sektor). Output minimal untuk mencegah context flood ke LLM."
version: "1.0.0"
entry: pipeline.py
---

# Skill: web_scraping

## Mode yang Tersedia

### 1. scrape_news
Scrape berita untuk satu ticker IDX.
```
Input : { "mode": "scrape_news", "symbol": "ITMG", "hours": 24, "max_articles": 10 }
Output: { "symbol", "overallSentiment", "totalFound", "articles": [...] }
```

### 2. scrape_trending
Cari ticker IDX yang sedang trending di berita.
```
Input : { "mode": "scrape_trending", "hours": 48 }
Output: { "topTickers": [...], "topSectors": [...], "headlines": [...] }
```

### 3. scrape_sector
Scrape berita untuk satu sektor IDX.
```
Input : { "mode": "scrape_sector", "sector": "banking", "hours": 48 }
Sectors: banking, coal_mining, telco, consumer, automotive, mining_metals, property, energy
Output: { "sector", "overallSentiment", "tickersMentioned": [...], "articles": [...] }
```

## Output Rules
- Semua artikel punya: title, summary (max 300 chars), url, source, publishedAt, sentiment
- Output ke LLM dibatasi maksimal 5 artikel + overall sentiment
- Full data disimpan ke: /workspaces/web_scraper/data/cache/{symbol}_{date}.json

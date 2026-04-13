# AGENTS: orchestrator

## Architecture
```
[User / API]
     │
     ▼
[orchestrator]
     ├──→ [fin_analyst]    ← signal store, IDX market data, report generation, screening
     ├──→ [web_scraper]    ← news scraping, sentiment, trending tickers
     └──→ [ml_processor]   ← RAG knowledge base, video ingestion
```

---

## fin_analyst

**Workspace**: `/workspaces/fin_analyst/`

### get_latest_signal
Returns the most recent consensus data received from the existing stock analysis system.
Data is stored locally — this is a read from cache, not a live API call.
```json
// Input
{ "symbol": "ITMG" }

// Output
{
  "symbol": "ITMG",
  "name": "Indo Tambangraya Megah",
  "trendConsensus": "CONTINUING",
  "actionIfHolding": "HOLD",
  "actionIfNotHolding": "WAIT",
  "instructions": {
    "holding": "string",
    "not_holding": "string"
  },
  "consensusScore": "3/3",
  "consensusInt": 3,
  "avgConfidencePct": 0,
  "lastPrice": "string",
  "receivedAt": "ISO8601",
  "status": "ok | not_found | stale"
}
```
`status: stale` if signal is older than 8 hours (outside normal market cycle).

### generate_report
Synthesizes signal + news + RAG context into a full ReportObject.
```json
// Input
{
  "signal": {},
  "news": {},
  "rag_context": {},
  "user_position": "holding | not_holding | unknown"
}

// Output — ReportObject
{
  "ticker": "ITMG",
  "company": "string",
  "generatedAt": "ISO8601",
  "signal": {
    "trend": "CONTINUING",
    "actionIfHolding": "HOLD",
    "actionIfNotHolding": "WAIT",
    "consensusScore": "3/3",
    "confidencePct": 0,
    "dataQuality": "full | partial | insufficient",
    "receivedAt": "ISO8601"
  },
  "instructions": { "holding": "string", "not_holding": "string" },
  "newsSentiment": {
    "overall": "positive | negative | neutral | mixed | unavailable",
    "summary": "string",
    "conflictsWithSignal": false,
    "articles": []
  },
  "ragContext": {
    "available": true,
    "insight": "string",
    "sources": []
  },
  "reasoning": "string",
  "disclaimer": "string"
}
```

### scan_market_movers
Returns top gainers, losers, and high-volume stocks from IDX market data.
```json
// Input
{ "limit": 10 }

// Output
{
  "scannedAt": "ISO8601",
  "topGainers": [{ "symbol": "", "changePct": 0.0, "volume": 0 }],
  "topLosers":  [{ "symbol": "", "changePct": 0.0, "volume": 0 }],
  "highVolume":  [{ "symbol": "", "volume": 0 }]
}
```

### screen_candidates
Filters and ranks stocks for the screening workflow.
```json
// Input
{ "trending": {}, "movers": {}, "rag_context": {} }

// Output
{
  "candidates": [
    {
      "symbol": "BBCA",
      "company": "string",
      "sector": "string",
      "signal": {},
      "thesis": "string",
      "score": 0.0
    }
  ],
  "generatedAt": "ISO8601"
}
```

---

## web_scraper

**Workspace**: `/workspaces/web_scraper/`

### scrape_news
```json
// Input
{ "symbol": "ITMG", "hours": 24, "max_articles": 10 }

// Output
{
  "symbol": "ITMG",
  "scrapedAt": "ISO8601",
  "overallSentiment": "positive | negative | neutral | mixed",
  "articles": [
    {
      "title": "string",
      "summary": "string",
      "url": "string",
      "source": "string",
      "publishedAt": "ISO8601",
      "sentiment": "positive | negative | neutral",
      "sentimentScore": 0.0
    }
  ],
  "totalFound": 0
}
```
Sources (priority): Kontan → Bisnis → CNBC Indonesia → idx.co.id → Investing.com/id

### scrape_trending
```json
// Input
{ "market": "IDX", "hours": 48 }

// Output
{
  "scrapedAt": "ISO8601",
  "trendingTickers": ["BBCA", "TLKM"],
  "sectors": ["banking", "telco"],
  "headlines": [{ "ticker": "", "title": "", "sentiment": "" }]
}
```

---

## ml_processor

**Workspace**: `/workspaces/ml_processor/`

### rag_query
```json
// Input
{ "query": "string", "top_k": 4, "domain_filter": null }

// Output
{
  "query": "string",
  "answer": "string",
  "sources": [{ "video_id": "", "video_title": "", "start": 0, "end": 0, "topic": "", "score": 0.0 }],
  "confidence": "high | medium | low | no_context",
  "model": "qwen2.5:9b",
  "duration_s": 0.0
}
```

### video_content_analysis
```json
// Input
{ "video_path": "string", "language": "id", "model_size": "medium" }

// Output
{ "video_id": "string", "status": "success | failed", "chunks_indexed": 0, "training_records": 0 }
```

---

## Parallelism Guide
| Workflow         | Parallel steps                          | Sequential after    |
|------------------|-----------------------------------------|---------------------|
| stock_analysis   | get_latest_signal + scrape_news + rag   | generate_report     |
| stock_screening  | scrape_trending + scan_market_movers + rag | screen_candidates |
| watchlist_scan   | get_latest_signal per ticker (batched)  | format table        |
| news_only        | (single agent, no parallelism needed)   | —                   |
| knowledge_query  | (single agent, no parallelism needed)   | —                   |

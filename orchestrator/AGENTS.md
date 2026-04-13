# AGENTS: orchestrator

## System Architecture

```
[User / API Client]
        │
        ▼
  [orchestrator]  ←── coordinates all agents, delivers final report
        │
        ├──────────────────────────────────────────┐
        │                                          │
        ▼                                          ▼
  [fin_analyst]                            [web_scraper]
  Core analyst agent                       IDX news scraper
  - Interprets existing system signal      - Scrapes berita saham IDX
  - Synthesizes all data sources           - Extracts sentiment
  - Generates full report                  - Returns structured news feed
        │
        ├──→ [Existing Stock Analysis API]   ← Pre-computed signals, consensus, instructions
        └──→ [ml_processor → rag_engine]     ← Domain knowledge from video knowledge base
```

---

## Agent: fin_analyst

- Workspace : `/workspaces/fin_analyst/`
- Heartbeat : `/workspaces/fin_analyst/heartbeat.json`
- Primary role : Signal interpretation + report generation for IDX stocks

### Skill: fetch_signal

- Entry : `skills/fetch_signal/run.py`
- Purpose : Call existing stock analysis API, parse and validate response
- Input:
  ```json
  { "symbol": "ITMG", "contextId": 10 }
  ```
- Output (normalized from existing API response):
  ```json
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
    "lastPrice": "0",
    "fetchedAt": "ISO8601"
  }
  ```

### Skill: generate_report

- Entry : `skills/generate_report/run.py`
- Purpose : Synthesize signal + news + RAG context → full analysis report
- Input:
  ```json
  {
    "signal": {},
    "news": [],
    "rag_context": {},
    "user_position": "holding | not_holding | unknown"
  }
  ```
- Output (ReportObject):
  ```json
  {
    "ticker": "ITMG",
    "company": "Indo Tambangraya Megah",
    "generatedAt": "ISO8601",
    "signal": {
      "trend": "CONTINUING",
      "action": "HOLD",
      "consensusScore": "3/3",
      "confidencePct": 0,
      "dataQuality": "full | partial | insufficient"
    },
    "instructions": {
      "holding": "string",
      "not_holding": "string"
    },
    "newsSentiment": {
      "overall": "positive | negative | neutral | mixed | unavailable",
      "summary": "string",
      "articles": [{ "title": "", "source": "", "url": "", "publishedAt": "" }],
      "conflictsWithSignal": true
    },
    "knowledgeContext": {
      "available": true,
      "insight": "string",
      "sources": []
    },
    "reasoning": "string",
    "disclaimer": "Analisa ini bersifat informatif dan tidak merupakan rekomendasi investasi resmi.",
    "dataFreshness": {
      "signalAge": "string",
      "newsAge": "string",
      "priceAge": "string"
    }
  }
  ```

---

## Agent: web_scraper

- Workspace : `/workspaces/web_scraper/`
- Heartbeat : `/workspaces/web_scraper/heartbeat.json`
- Primary role : Scrape and structure IDX-related news and market sentiment

### Skill: scrape_news

- Entry : `skills/scrape_news/run.py`
- Input:
  ```json
  { "symbol": "ITMG", "hours": 24, "max_articles": 10 }
  ```
- Output:
  ```json
  {
    "symbol": "ITMG",
    "scrapedAt": "ISO8601",
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
    "overallSentiment": "positive | negative | neutral | mixed",
    "totalFound": 0
  }
  ```
- News sources to scrape (priority order):
  1. Kontan.co.id
  2. Bisnis.com
  3. CNBC Indonesia
  4. IDX official announcements (idx.co.id)
  5. Investing.com/id

---

## Agent: ml_processor

- Workspace : `/workspaces/ml_processor/`
- Heartbeat : `/workspaces/ml_processor/heartbeat.json`
- Primary role : Video knowledge base and domain knowledge retrieval

### Skill: rag_engine (read)

- Entry : `skills/rag_engine/generate.py` → `rag_query()`
- When called : fin_analyst requests domain context for a sector or concept
- Input:
  ```json
  {
    "query": "coal mining sector IDX ITMG outlook",
    "top_k": 4,
    "domain_filter": null
  }
  ```
- Output: Standard rag_engine output (see ml_processor/AGENTS.md)

### Skill: video_content_analysis (write)

- Entry : `skills/video_content_analysis/pipeline.py`
- When called : User explicitly adds a new video to the knowledge base
- Does NOT affect real-time analysis flow

---

## External System: Existing Stock Analysis API

- Type : REST API (user-owned external system)
- Auth : Configured in `/workspaces/fin_analyst/config/api.json`
- Base URL : (set in config — not hardcoded here)
- Key endpoint : `GET /analysis?symbol={TICKER}&contextId={ID}`
- Response : See example in SOUL.md and fin_analyst/IDENTITY.md
- SLA : Expected < 3s response time
- On timeout : Retry once after 2s, then fail and report to orchestrator

---

## Communication Flow (Full Analysis Request)

```
User: "Analisa ITMG"
  │
  ▼
orchestrator
  ├─ check_heartbeat(fin_analyst)        → UP
  ├─ check_heartbeat(web_scraper)        → UP
  ├─ check_heartbeat(ml_processor)       → UP
  │
  ├─ fin_analyst.fetch_signal("ITMG")
  │    └─ calls existing stock API
  │    └─ returns: signal object
  │
  ├─ web_scraper.scrape_news("ITMG", hours=24)   [parallel]
  │    └─ returns: articles + sentiment
  │
  ├─ ml_processor.rag_query("ITMG coal mining")  [parallel]
  │    └─ returns: insight + sources
  │
  └─ fin_analyst.generate_report(signal, news, rag_context)
       └─ returns: ReportObject
  │
  ▼
orchestrator formats ReportObject → delivers to user
```

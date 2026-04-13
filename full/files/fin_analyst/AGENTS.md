# AGENTS: fin_analyst

## Position in System
fin_analyst is a downstream agent. It receives tasks from orchestrator only.
It does not initiate contact with other agents.
News and RAG data are passed in by orchestrator — fin_analyst does not call
web_scraper or ml_processor directly.

```
orchestrator
    ├──→ fin_analyst.get_latest_signal(symbol)
    └──→ fin_analyst.generate_report(signal, news, rag, position)
    └──→ fin_analyst.scan_market_movers()
    └──→ fin_analyst.screen_candidates(trending, movers, rag)
    └──→ fin_analyst.receive_signal(payload)    ← called by existing system push
```

---

## Upstream: orchestrator (task delegation)

All inputs arrive as structured JSON. No natural language.

```json
// get_latest_signal
{ "task": "get_latest_signal", "symbol": "ITMG" }

// generate_report
{ "task": "generate_report", "signal": {}, "news": {}, "rag_context": {}, "user_position": "holding | not_holding | unknown" }

// scan_market_movers
{ "task": "scan_market_movers", "limit": 10 }

// screen_candidates
{ "task": "screen_candidates", "trending": {}, "movers": {}, "rag_context": {} }
```

---

## Upstream: existing stock analysis system (push)

The external system calls `receive_signal` via webhook or direct write.
This is the ONLY way signal data enters fin_analyst.

```json
// Incoming push payload (existing system format)
{
  "data": [{
    "stockId": 545,
    "trendConsensus": "CONTINUING",
    "actionIfHolding": "HOLD",
    "actionIfNotHolding": "WAIT",
    "finalInstructions": {
      "holding": "string",
      "not_holding": "string"
    },
    "consensusScore": "3/3",
    "avgConfidencePct": 0,
    "lastPrice": "0",
    "createdAt": "ISO8601",
    "stock": { "symbol": "ITMG", "name": "Indo Tambangraya Megah" }
  }]
}
```

Storage path: `/workspaces/fin_analyst/data/signals/ITMG.json`

---

## External Dependency: IDX Market Data API

- Config: `/workspaces/fin_analyst/config/market_data.json`
- Purpose: Real-time and historical price, volume, market cap for IDX stocks
- Used by: `scan_market_movers`, `screen_candidates`
- Timeout: 5s

```json
// config/market_data.json
{
  "provider": "string",
  "base_url": "string",
  "api_key": "string",
  "timeout_s": 5
}
```

---

## Workspace Structure
```
/workspaces/fin_analyst/
├── IDENTITY.md
├── SOUL.md
├── AGENTS.md
├── TOOLS.md
├── HEARTBEAT.md
├── BOOTSTRAP.md
├── MEMORY.md
├── heartbeat.json
├── config/
│   ├── market_data.json    ← IDX market data API credentials
│   └── api.json            ← (legacy, if existing system uses pull mode)
├── data/
│   └── signals/            ← one JSON file per ticker, updated on push
│       ├── ITMG.json
│       ├── BBCA.json
│       └── ...
└── logs/
    ├── signal_log.jsonl    ← every received push logged here
    └── report_log.jsonl    ← every generated report logged here
```

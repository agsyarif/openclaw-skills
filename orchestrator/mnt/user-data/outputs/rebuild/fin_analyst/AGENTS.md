# AGENTS: fin_analyst

## Position in System
fin_analyst is a downstream agent — it receives tasks from the orchestrator only.
It does not initiate contact with other agents directly.
Data from web_scraper and ml_processor is passed to fin_analyst by the orchestrator,
already structured. fin_analyst does not call these agents itself.

```
orchestrator
    │
    ├──→ fin_analyst.fetch_signal     ← calls existing stock API
    │
    └──→ fin_analyst.generate_report  ← receives: signal + news + rag_context
                                         from orchestrator (already fetched)
```

---

## Upstream: orchestrator

The orchestrator is the only caller of fin_analyst.
All inputs arrive as structured JSON payloads — no raw natural language.

### Accepted task payloads:

**fetch_signal:**
```json
{
  "task": "fetch_signal",
  "from": "orchestrator",
  "payload": {
    "symbol": "ITMG",
    "contextId": 10
  }
}
```

**generate_report:**
```json
{
  "task": "generate_report",
  "from": "orchestrator",
  "payload": {
    "signal": { },
    "news": { },
    "rag_context": { },
    "user_position": "holding | not_holding | unknown"
  }
}
```

---

## External Dependency: Stock Analysis API

- Config file : `/workspaces/fin_analyst/config/api.json`
- Schema:
  ```json
  {
    "base_url": "https://your-stock-api.com",
    "api_key": "YOUR_KEY_HERE",
    "context_id": 10,
    "timeout_s": 5,
    "retry_count": 1,
    "retry_delay_s": 2
  }
  ```
- Key endpoint: `GET {base_url}/analysis?symbol={TICKER}&contextId={contextId}`
- Auth header : `Authorization: Bearer {api_key}` (adjust to your actual auth method)

### Response mapping (existing API → normalized signal):
```
data[0].trendConsensus          → signal.trend
data[0].actionIfHolding         → signal.actionIfHolding
data[0].actionIfNotHolding      → signal.actionIfNotHolding
data[0].finalInstructions       → signal.instructions
data[0].consensusScore          → signal.consensusScore (string)
data[0].consensusScore.split("/")[0] → signal.consensusInt (integer)
data[0].avgConfidencePct        → signal.avgConfidencePct
data[0].lastPrice               → signal.lastPrice
data[0].stock.symbol            → signal.symbol
data[0].stock.name              → signal.name
data[0].createdAt               → signal.fetchedAt
```

---

## Workspace Structure
```
/workspaces/fin_analyst/
├── IDENTITY.md
├── SOUL.md
├── AGENTS.md
├── heartbeat.json
├── config/
│   └── api.json              ← stock API credentials and settings
├── skills/
│   ├── fetch_signal/
│   │   └── run.py            ← calls stock API, returns normalized signal
│   └── generate_report/
│       └── run.py            ← synthesizes all data → ReportObject
├── data/
│   └── reports/              ← optional: saved reports per ticker per date
└── logs/
    └── analysis_log.jsonl    ← one entry per report generated
```

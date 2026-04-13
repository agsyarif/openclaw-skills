# BOOTSTRAP: orchestrator

## Purpose
Startup sequence for the orchestrator. Run on every cold start
before accepting any user input or API request.

---

## Startup Sequence

### Step 1 — Load core files (in order)
```
IDENTITY.md  → role and agent registry
SOUL.md      → routing rules and delegation protocol
AGENTS.md    → agent schemas and communication map
TOOLS.md     → available tools
USER.md      → user preferences and defaults
```
If any file is unreadable → HALT and report which file is missing.

### Step 2 — Health checks
```
check_heartbeat(fin_analyst)     ← CRITICAL — halt if DOWN
check_heartbeat(web_scraper)     ← IMPORTANT — warn if DOWN, continue
check_heartbeat(ml_processor)    ← OPTIONAL — warn if DOWN, continue
```

Verify existing stock API reachability:
```
GET {STOCK_API_BASE_URL}/health  (or /ping)
Timeout: 3s
If unreachable → warn, do not halt (user may want to use other features)
```

### Step 3 — Validate knowledge base
```
Check: /workspaces/ml_processor/data/vector_store/
If empty → note: "Knowledge base empty — ml_processor enrichment unavailable"
If ready → note: number of chunks and indexed videos
```

### Step 4 — Load watchlist (if exists)
```
Read: /workspaces/orchestrator/data/watchlist.json
Format: { "tickers": ["BBCA", "TLKM", "ITMG"], "updatedAt": "ISO8601" }
If file missing → initialize empty watchlist, create file
```

### Step 5 — Ready
```json
{
  "event": "orchestrator_ready",
  "timestamp": "<ISO8601>",
  "agents": {
    "fin_analyst": "UP | DOWN",
    "web_scraper": "UP | DOWN",
    "ml_processor": "UP | DOWN"
  },
  "stock_api": "reachable | unreachable",
  "knowledge_base": "ready | empty | missing",
  "watchlist_count": 0
}
```
Write to: `/workspaces/orchestrator/logs/startup_log.jsonl`

---

## Startup Checklist

| Check                        | Critical? | If Fail                                           |
|------------------------------|-----------|---------------------------------------------------|
| IDENTITY.md readable         | Yes       | HALT                                              |
| SOUL.md readable             | Yes       | HALT                                              |
| AGENTS.md readable           | Yes       | HALT                                              |
| fin_analyst UP               | Yes       | HALT — no analysis possible without it            |
| Existing stock API reachable | Yes       | Warn — signal fetch will fail                     |
| web_scraper UP               | No        | Warn — reports will lack news sentiment           |
| ml_processor UP              | No        | Warn — reports will lack knowledge base context   |
| Ollama reachable             | No        | Warn — RAG and video processing unavailable       |
| watchlist.json exists        | No        | Create empty file, continue                       |
| logs/ directory writable     | No        | Create directory, continue                        |

---

## Data Directory Structure
```
/workspaces/orchestrator/
├── IDENTITY.md
├── SOUL.md
├── AGENTS.md
├── BOOTSTRAP.md
├── HEARTBEAT.md
├── TOOLS.md
├── USER.md
├── heartbeat.json          ← orchestrator self-heartbeat
├── data/
│   └── watchlist.json      ← user's tracked tickers
└── logs/
    ├── startup_log.jsonl
    ├── interaction_log.jsonl
    └── error_log.jsonl
```

## Warm Start (new conversation, same process)
- Re-read USER.md
- Re-check all heartbeats
- Re-load watchlist.json
- Skip disk and API checks (assume stable)

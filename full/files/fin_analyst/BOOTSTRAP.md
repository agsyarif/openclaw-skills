# BOOTSTRAP: fin_analyst

## Cold Start Sequence

```
1. Load IDENTITY.md, SOUL.md, AGENTS.md, TOOLS.md   ← required
2. Read config/market_data.json                      ← if missing, log warning, continue
3. Ensure data/signals/ directory exists             ← create if missing
4. Ensure logs/ directory exists                     ← create if missing
5. Count signal files → report in heartbeat
6. Write initial heartbeat.json
7. Ready — accept tasks from orchestrator
```

No blocking checks. If market_data.json is missing, screening features degrade gracefully.
Signal store being empty is not a startup error — it means no push has arrived yet.

---

## Signal Reception Setup
fin_analyst must expose a `receive_signal` endpoint for the existing system to push data.
Endpoint configuration is outside this file — see infrastructure setup docs.

On each received push:
1. `receive_signal` validates and stores to `data/signals/{SYMBOL}.json`
2. Logs to `signal_log.jsonl`
3. Updates `heartbeat.json` with `last_signal_received`

---

## Directory Structure
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
│   ├── market_data.json
│   └── api.json
├── data/
│   └── signals/
└── logs/
    ├── signal_log.jsonl
    └── report_log.jsonl
```

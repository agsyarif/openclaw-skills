# Agent Network Reference

## Ports

| Agent        | Port | Notify Endpoint | Health Endpoint        |
| ------------ | ---- | --------------- | ---------------------- |
| orchestrator | 8000 | —               | GET /health            |
|              |      | POST /callback  | (receives from agents) |
| fin_analyst  | 8001 | POST /notify    | GET /health            |
| web_scraper  | 8002 | POST /notify    | GET /health            |
| ml_processor | 8003 | POST /notify    | GET /health            |

## Startup Order

```
1. fin_analyst   → python /workspaces/fin_analyst/server.py
2. web_scraper   → python /workspaces/web_scraper/server.py
3. ml_processor  → python /workspaces/ml_processor/server.py
4. orchestrator  → python /workspaces/orchestrator/server.py
```

Each agent is independent — order only matters if orchestrator
needs agents ready before accepting user requests.

## Shared Filesystem

```
/workspaces/shared/
├── tasks/           ← task files written by orchestrator
├── results/         ← result files written by agent workers
└── task_contract.py ← imported by all agents (shared contracts)
```

## Communication Pattern

```
orchestrator
  1. write task → /shared/tasks/<task_id>.json
  2. POST /notify to agent port
     { task_id, task_file, skill, from_agent }
  3. wait for callback (event-driven)

agent worker
  1. receive POST /notify
  2. spawn background thread
  3. read task file
  4. execute skill
  5. write result → /shared/results/<task_id>.json
  6. POST /callback to orchestrator:8000
     { task_id, status, result_file, from_agent, duration_s }

orchestrator
  7. receive POST /callback
  8. set event → unblocks waiting delegate()
  9. read result file
```

## Timeout Defaults by Skill

| Skill                  | Timeout |
| ---------------------- | ------- |
| get_latest_signal      | 5s      |
| generate_report        | 15s     |
| scrape_news            | 20s     |
| scrape_trending        | 25s     |
| rag_query              | 15s     |
| scan_market_movers     | 10s     |
| screen_candidates      | 20s     |
| video_content_analysis | 3600s   |

# HEARTBEAT: web_scraper

## Self-Heartbeat
Write to `/workspaces/web_scraper/heartbeat.json` after each completed task.

```json
{
  "agent_id": "web_scraper",
  "status": "ok | degraded | error",
  "last_ping": "ISO8601",
  "active_task": null,
  "components": {
    "sources_reachable": 5,
    "sources_total": 6,
    "last_successful_scrape": "ISO8601 | null"
  }
}
```

## Status Rules
- `ok` — at least 3 of 6 sources reachable in last scrape
- `degraded` — 1–2 sources reachable
- `error` — 0 sources reachable or last scrape failed entirely

## Source Availability
Tracked per scrape job in `logs/scrape_log.jsonl`.
Do not ping sources just for heartbeat — use cached result from last scrape.

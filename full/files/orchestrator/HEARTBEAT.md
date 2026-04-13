# HEARTBEAT: orchestrator

## When to Use
Read heartbeat files ONLY when user explicitly requests system status.
Do NOT check heartbeats before routine task delegation — attempt tasks directly.

---

## Agent Heartbeat Paths
| Agent        | File                                          |
|--------------|-----------------------------------------------|
| fin_analyst  | `/workspaces/fin_analyst/heartbeat.json`      |
| web_scraper  | `/workspaces/web_scraper/heartbeat.json`      |
| ml_processor | `/workspaces/ml_processor/heartbeat.json`     |

## Heartbeat Schema
```json
{
  "agent_id": "string",
  "status": "ok | degraded | error",
  "last_ping": "ISO8601",
  "active_task": null,
  "components": {}
}
```

## Status Evaluation
```
age = seconds since last_ping

age < 60  AND status = ok        → UP    🟢
age < 300                        → STALE 🟡
age ≥ 300 OR file missing        → DOWN  🔴
status = error                   → DOWN  🔴
```

## Status Output (chat)
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖥  SYSTEM STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 fin_analyst    UP   (Xs ago)
🟢 web_scraper    UP   (Xs ago)
🟡 ml_processor   STALE (Xs ago)
📦 Knowledge Base  N chunks / M videos
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Self-Heartbeat
Orchestrator writes to `/workspaces/orchestrator/heartbeat.json` after each completed task.
```json
{
  "agent_id": "orchestrator",
  "status": "ok",
  "last_ping": "ISO8601",
  "requests_served": 0
}
```

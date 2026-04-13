# HEARTBEAT: fin_analyst

## Self-Heartbeat
Write to `/workspaces/fin_analyst/heartbeat.json` after each completed task.

```json
{
  "agent_id": "fin_analyst",
  "status": "ok | degraded | error",
  "last_ping": "ISO8601",
  "active_task": null,
  "components": {
    "signal_store": "ok | empty",
    "market_data_api": "ok | unreachable | timeout"
  },
  "signals_stored": 0,
  "last_signal_received": "ISO8601 | null"
}
```

## Component Status Rules

### signal_store
- `ok` — at least one signal file exists in `/data/signals/`
- `empty` — no signal files (existing system has not pushed yet)

### market_data_api
- Check by reading last successful query timestamp from `logs/signal_log.jsonl`
- Do not ping the API just for heartbeat — use cached result
- `ok` — last successful query < 10 min ago
- `unreachable` — last query failed or > 10 min ago
- Set to `ok` by default until a query actually fails

## Degraded State
Set `status: degraded` if:
- `signal_store = empty` (cannot serve any analysis)
- `market_data_api = unreachable` (screening and movers unavailable)

Remain `status: ok` for all other conditions — partial capability is still ok.

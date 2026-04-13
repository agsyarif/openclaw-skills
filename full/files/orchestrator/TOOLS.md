# TOOLS: orchestrator

## Philosophy
Tools are things the orchestrator executes directly — no agent delegation.
Keep this list minimal. If it needs a model or external data, it's an agent task.

---

## delegate(agent, skill, payload)
Route a task to a registered agent skill.
- No pre-check. Attempt immediately.
- On timeout or error: apply degradation rules from SOUL.md.
- Timeouts: 30s default | 120s for video_content_analysis

---

## read_watchlist() → string[]
Read `/workspaces/orchestrator/data/watchlist.json`.
Returns ticker array. Returns `[]` if file missing.

## write_watchlist(tickers: string[])
Overwrite watchlist file with new ticker array.
Validate: each ticker must be 4 uppercase letters (IDX format).

## add_ticker(symbol) / remove_ticker(symbol)
Convenience wrappers around read/write watchlist.

---

## read_memory() → object
Read `/workspaces/orchestrator/MEMORY.md` or `memory.md`.
Returns parsed session context (positions, preferences set this session).

## write_memory(key, value)
Append or update a key in MEMORY.md.
Only called when user explicitly says "remember this" or "simpan".

---

## format_report(report_object) → string
Convert a ReportObject from fin_analyst into the chat template defined in SOUL.md.
Pure formatting — no logic, no data fetching.

## format_screening(candidates) → string
Convert screen_candidates output into the screening template from SOUL.md.

## format_watchlist_table(signals[]) → string
Convert array of get_latest_signal results into compact watchlist table.

---

## check_all_agents() → status_object
Read heartbeat files for all agents. Used ONLY for explicit `status` requests.
Do NOT call this before regular task delegation.
```json
{
  "fin_analyst":  { "status": "UP|STALE|DOWN", "age_s": 0 },
  "web_scraper":  { "status": "UP|STALE|DOWN", "age_s": 0 },
  "ml_processor": { "status": "UP|STALE|DOWN", "age_s": 0 }
}
```

---

## log_interaction(entry)
Append to `/workspaces/orchestrator/logs/interaction_log.jsonl`.
Called after every completed request. Non-blocking — do not wait for confirmation.
```json
{
  "ts": "ISO8601",
  "mode": "chat | api",
  "intent": "analysis | screening | news | knowledge | video | watchlist | status",
  "ticker": "ITMG | null",
  "agents_called": [],
  "status": "success | partial | error",
  "duration_s": 0.0
}
```

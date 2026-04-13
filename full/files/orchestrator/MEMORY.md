# MEMORY: orchestrator

## Purpose
Stores context that should persist within or across sessions.
Orchestrator reads this on every warm start.
Write here only when user explicitly says "simpan", "remember", or "ingat ini".

---

## Session Context (cleared each new session unless marked persistent)

### Active Positions
```json
{}
```
Example after user says "saya holding ITMG":
```json
{ "ITMG": "holding", "BBCA": "not_holding" }
```

### Active Filters
```json
{}
```
Example: `{ "default_news_hours": 48, "domain_filter": "mining" }`

---

## Persistent Memory (survives across sessions)

### User Preferences
```json
{}
```
Write here when user says "simpan preferensi ini" or "always use X".

### Watchlist Notes
```json
{}
```
Per-ticker notes user has asked to remember.
Example: `{ "ITMG": "monitoring for breakout above 27500" }`

---

## Write Rules
1. Only write when user explicitly requests it
2. Session context entries expire at session end unless user says "simpan"
3. Persistent entries remain until user says "hapus" or "forget"
4. Never auto-infer what to remember — wait for explicit instruction
5. Log each write with timestamp in `logs/memory_log.jsonl`

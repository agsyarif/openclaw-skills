# MEMORY: fin_analyst

## Purpose
Stores persistent context that fin_analyst needs across task executions.
Unlike orchestrator MEMORY.md (session-scoped), this is primarily operational state.

---

## Signal Reception State
```json
{
  "last_push_received": "ISO8601 | null",
  "total_signals_stored": 0,
  "symbols_with_signals": []
}
```
Updated automatically on every `receive_signal` call.

---

## Sector Map (manual, update when needed)
Maps IDX tickers to their sector for context enrichment in reports and screening.
```json
{
  "BBCA": "banking",
  "BBRI": "banking",
  "BMRI": "banking",
  "TLKM": "telco",
  "ASII": "automotive",
  "ITMG": "coal_mining",
  "ADRO": "coal_mining",
  "ANTM": "mining_metals",
  "TPIA": "petrochemical",
  "ICBP": "consumer_goods"
}
```
Used by: `generate_report` (to form RAG query), `screen_candidates` (sector grouping).

---

## Screening History (last 7 days)
```json
[]
```
Each entry: `{ "date": "YYYY-MM-DD", "candidates": ["BBCA", "ITMG"], "trigger": "user_request" }`
Prevents recommending same candidates repeatedly in short succession.

---

## Write Policy
- `signal_reception_state` — auto-updated, no user trigger needed
- `sector_map` — manual update by developer only
- `screening_history` — auto-updated after each screen_candidates call

# TOOLS: fin_analyst

## read_signal(symbol) → object
Read `/workspaces/fin_analyst/data/signals/{SYMBOL}.json`.
Returns parsed signal object. Returns `null` if file not found.

## write_signal(symbol, payload)
Write normalized signal to `/workspaces/fin_analyst/data/signals/{SYMBOL}.json`.
Called only by `receive_signal` skill. Overwrites previous entry.

## read_all_signals() → object[]
Read all files in `/workspaces/fin_analyst/data/signals/`.
Used by watchlist scan and screening flows.
Returns array of signal objects sorted by `receivedAt` descending.

---

## query_market_data(endpoint, params) → object
HTTP GET to IDX market data API (config: `config/market_data.json`).
Timeout: 5s. No retry. Returns partial data if available.

---

## compute_signal_age(receivedAt) → { hours, status }
Compute how old a signal is relative to now (WIB).
Returns `{ hours: N, status: "ok | stale | very_stale" }`.
Thresholds defined in SOUL.md.

---

## log_signal(payload)
Append to `/workspaces/fin_analyst/logs/signal_log.jsonl`.
```json
{ "ts": "ISO8601", "symbol": "ITMG", "event": "received | rejected", "consensusScore": "3/3" }
```

## log_report(summary)
Append to `/workspaces/fin_analyst/logs/report_log.jsonl`.
```json
{ "ts": "ISO8601", "ticker": "ITMG", "dataQuality": "full | partial | insufficient", "duration_s": 0.0 }
```

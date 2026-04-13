# TOOLS: orchestrator

## Purpose
Tools directly available to the orchestrator — actions it performs itself
without delegating to a sub-agent.

---

## Tool: check_heartbeat
Evaluate the health of a registered agent.
- Input  : `agent_id` (string)
- Output : `{ status: "UP|STALE|DOWN|DEGRADED", age_s: N, components: {} }`
- Logic  : Defined in HEARTBEAT.md
- Always run before `delegate_task`

---

## Tool: delegate_task
Send a structured task payload to a registered agent skill.
- Always preceded by `check_heartbeat`
- Input:
  ```json
  {
    "to": "fin_analyst | web_scraper | ml_processor",
    "skill": "fetch_signal | generate_report | scrape_news | rag_query | video_content_analysis",
    "payload": {}
  }
  ```
- Output: Agent skill response (see AGENTS.md for schemas)
- Timeout: 30s default, 120s for video_content_analysis

---

## Tool: read_file
Read any readable file from the workspace.
- Scope : Read-only — orchestrator NEVER writes to agent workspaces
- Use for: heartbeat.json, run_log.json, config files, reports

---

## Tool: write_log
Append a structured entry to an orchestrator log file.
- Target : `/workspaces/orchestrator/logs/` only
- Files  : `interaction_log.jsonl`, `error_log.jsonl`, `startup_log.jsonl`
- Schema (interaction):
  ```json
  {
    "timestamp": "ISO8601",
    "mode": "chat | api",
    "intent": "analysis | news | rag | status | video_process | watchlist",
    "ticker": "ITMG | null",
    "agents_called": ["fin_analyst", "web_scraper"],
    "status": "success | partial | error",
    "report_confidence": "high | medium | low | null",
    "duration_s": 0.0
  }
  ```

---

## Tool: manage_watchlist
Read, add, or remove tickers from the user's watchlist.
- File   : `/workspaces/orchestrator/data/watchlist.json`
- Schema : `{ "tickers": ["BBCA", "TLKM"], "updatedAt": "ISO8601" }`
- Operations:
  - `list`   → return current watchlist
  - `add`    → append ticker (uppercase, 4 chars, validate IDX format)
  - `remove` → remove ticker
  - `scan`   → iterate all tickers, call fetch_signal for each → return brief summary table

### Watchlist scan output (chat mode):
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 WATCHLIST SCAN — [Date WIB]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TICKER  TREND          HOLDING    NOT HOLDING  CONSENSUS
BBCA    CONTINUING     HOLD       WAIT         3/3
TLKM    REVERSING      SELL       AVOID        2/3
ITMG    CONSOLIDATING  HOLD       ACCUMULATE   3/3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ketik "analisa [TICKER]" untuk report lengkap.
```

---

## Tool: format_report
Convert a raw ReportObject from fin_analyst into human-readable chat output.
- Input  : ReportObject (see AGENTS.md)
- Output : Formatted string using the template in SOUL.md
- Rules  :
  - Always include disclaimer
  - Flag data quality issues inline
  - Highlight conflicts between signal and news sentiment

---

## Tool Execution Order (standard analysis flow)

```
1. check_heartbeat(fin_analyst)            ← critical gate
2. check_heartbeat(web_scraper)            ← optional enrichment
3. check_heartbeat(ml_processor)           ← optional enrichment
4. delegate_task(fin_analyst, fetch_signal, { symbol })
5. delegate_task(web_scraper, scrape_news, { symbol })   [parallel with 6]
6. delegate_task(ml_processor, rag_query, { query })     [parallel with 5]
7. delegate_task(fin_analyst, generate_report, { signal, news, rag })
8. format_report(ReportObject)
9. write_log(interaction entry)
```

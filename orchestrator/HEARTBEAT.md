# HEARTBEAT: orchestrator

## Purpose
Health monitoring protocol for all agents and external dependencies.
Check before every task delegation.

---

## Agent Heartbeat Files

| Agent        | Heartbeat Path                              | Check Before Skill        |
|--------------|---------------------------------------------|---------------------------|
| fin_analyst  | `/workspaces/fin_analyst/heartbeat.json`    | Every analysis request    |
| web_scraper  | `/workspaces/web_scraper/heartbeat.json`    | Every news scrape request |
| ml_processor | `/workspaces/ml_processor/heartbeat.json`   | Every RAG request         |

### Expected Schema (all agents):
```json
{
  "agent_id": "fin_analyst",
  "status": "ok | degraded | error",
  "last_ping": "ISO8601",
  "active_task": null,
  "components": {
    "stock_api": "ok | unreachable | timeout",
    "ollama": "ok | unreachable",
    "chromadb": "ok | empty | missing"
  }
}
```

---

## Health Evaluation Rules

```
age = now - last_ping (in seconds)

age < 60  AND status = "ok"        → UP
age < 300 OR status = "degraded"   → STALE
age > 300 OR file missing          → DOWN
status = "error"                   → DOWN
```

### Response per status:

**UP** → delegate normally, no warning

**STALE** → warn user:
> "⚠️ [agent] merespons [N] detik lalu. Mungkin sedang lambat."
> Proceed with caution, set longer timeout.

**DOWN** → block if critical, warn if optional:
> "❌ [agent] tidak merespons. [Recovery steps]"

---

## Component-Level Checks

### fin_analyst — stock_api component
```
If stock_api = "unreachable":
  → "❌ Tidak bisa mengambil signal dari sistem analisa.
      Periksa koneksi ke stock analysis API."
  → Block analysis request entirely
```

### ml_processor — ollama + chromadb
```
If ollama = "unreachable":
  → Skip RAG enrichment, note in report: "[Konteks video tidak tersedia — Ollama offline]"

If chromadb = "empty":
  → Skip RAG enrichment, note: "[Knowledge base kosong — belum ada video diproses]"
```

### web_scraper
```
If DOWN or timeout:
  → Skip news enrichment, note in report: "[Berita tidak tersedia saat ini]"
  → Do NOT block analysis — proceed with signal + RAG only
```

---

## External Dependency: Stock Analysis API

- Not an agent — no heartbeat file
- Check via direct HTTP ping before every fetch_signal call
- Endpoint : `{STOCK_API_BASE_URL}/health`
- Timeout  : 3 seconds
- On fail  : Retry once (2s delay) → if still fail → report to user, block analysis

---

## Orchestrator Self-Heartbeat

Write to `/workspaces/orchestrator/heartbeat.json` every 30s and after each task:
```json
{
  "agent_id": "orchestrator",
  "status": "ok",
  "last_ping": "ISO8601",
  "active_task": null,
  "uptime_s": 0,
  "agents_up": ["fin_analyst", "web_scraper", "ml_processor"],
  "agents_down": [],
  "requests_served": 0
}
```

---

## Quick Status Summary (for "status" command)

When user asks for system status, return:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🖥️  STATUS SISTEM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 fin_analyst     : UP (last ping: Xs ago)
🟢 web_scraper     : UP (last ping: Xs ago)
🟡 ml_processor    : STALE (last ping: Xs ago)
🟢 Stock API       : Reachable
📦 Knowledge Base  : N chunks, M videos indexed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

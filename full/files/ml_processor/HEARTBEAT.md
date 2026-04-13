# HEARTBEAT: ml_processor

## Self-Heartbeat
Write to `/workspaces/ml_processor/heartbeat.json` after each completed task.

```json
{
  "agent_id": "ml_processor",
  "status": "ok | degraded | error",
  "last_ping": "ISO8601",
  "active_task": null,
  "components": {
    "ollama":   "ok | unreachable",
    "chromadb": "ok | empty | missing"
  },
  "kb_stats": {
    "chunks": 0,
    "videos": 0
  },
  "training_records": 0
}
```

## Component Status Rules

### ollama
- `ok` — last rag_query Ollama call succeeded
- `unreachable` — last call failed or no rag_query has been run yet
- Do NOT ping Ollama just for heartbeat — use result from last actual call

### chromadb
- `ok`      — collection exists and count > 0
- `empty`   — collection exists but count = 0 (no videos processed yet)
- `missing` — vector_store directory or collection does not exist

## Agent Status Rules
- `ok`       — both components ok, OR ollama=unreachable but chromadb=ok (RAG degraded but ingest possible)
- `degraded` — chromadb=empty (no knowledge to serve) OR ollama=unreachable (no RAG)
- `error`    — chromadb=missing (cannot function at all)

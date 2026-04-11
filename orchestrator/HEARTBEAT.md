# HEARTBEAT: orchestrator

## Purpose
Defines how the orchestrator monitors the health of all registered agents.
Read this before delegating any task to verify the target agent is available.

---

## Agent Health Registry

### ml_processor
- Heartbeat file : `/workspaces/ml_processor/heartbeat.json`
- Expected schema:
  ```json
  {
    "agent_id": "ml_processor",
    "status": "ok | degraded | error",
    "last_ping": "<ISO8601 timestamp>",
    "ollama": "ok | unreachable",
    "chromadb": "ok | empty | missing",
    "active_task": null
  }
  ```
- Healthy if     : `status = "ok"` AND `last_ping` within last 60 seconds
- Degraded if    : `status = "degraded"` OR `last_ping` between 60–300 seconds
- Down if        : File missing OR `status = "error"` OR `last_ping` older than 300 seconds

---

## Health Check Protocol

Before every task delegation, run this check:

```
1. Read /workspaces/ml_processor/heartbeat.json
2. Parse last_ping → compute age in seconds
3. Evaluate:
   age < 60s  AND status = "ok"       → UP       → proceed with delegation
   age < 300s OR status = "degraded"  → STALE    → warn user, proceed with caution
   age > 300s OR file missing         → DOWN     → do NOT delegate, report to user
```

### If agent is STALE:
> "⚠️ ml_processor last responded [N] seconds ago. It may be slow or restarting.
> Proceeding anyway — if this fails, check the agent logs."

### If agent is DOWN:
> "❌ ml_processor is not responding. Cannot process your request.
> Recovery steps:
> 1. Check if the agent process is running
> 2. Verify Ollama is running: `ollama serve`
> 3. Check agent logs at /workspaces/ml_processor/logs/"

---

## Sub-Component Health (inside ml_processor)

Even when ml_processor is UP, individual components may fail.
Check `heartbeat.json` sub-fields before specific skill calls:

| Skill                   | Required sub-component | Field to check        |
|-------------------------|------------------------|-----------------------|
| rag_engine              | Ollama + ChromaDB      | `ollama`, `chromadb`  |
| video_content_analysis  | Ollama + ffmpeg        | `ollama`              |

### If `ollama = "unreachable"`:
> "⚠️ The local LLM (Ollama) is not running. Both rag_engine and video_content_analysis
> require Ollama. Ask ml_processor to run: `ollama serve`"

### If `chromadb = "empty"`:
> "ℹ️ The knowledge base is empty. To answer questions about video content,
> process a video first: `pipeline.py <video_path>`"

### If `chromadb = "missing"`:
> "⚠️ Vector store not found. Run video_content_analysis to initialize it."

---

## Orchestrator Self-Heartbeat

The orchestrator also writes its own heartbeat for external monitoring:
- File : `/workspaces/orchestrator/heartbeat.json`
- Update: Every 30 seconds while running, and after every task completion
- Schema:
  ```json
  {
    "agent_id": "orchestrator",
    "status": "ok",
    "last_ping": "<ISO8601>",
    "active_task": null,
    "agents_monitored": ["ml_processor"],
    "agents_up": ["ml_processor"],
    "agents_down": []
  }
  ```

---

## Health Summary Table

| Status   | Meaning                              | Orchestrator Action             |
|----------|--------------------------------------|---------------------------------|
| UP       | Agent healthy, last_ping < 60s       | Delegate normally               |
| STALE    | Agent slow or restarting, 60-300s    | Warn user, delegate with caution|
| DOWN     | Agent unreachable or crashed         | Block delegation, report error  |
| DEGRADED | Agent up but sub-component failing   | Delegate only supported skills  |

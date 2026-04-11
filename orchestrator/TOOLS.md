# TOOLS: orchestrator

## Purpose
Defines the tools directly available to the orchestrator.
These are actions the orchestrator can perform itself, without delegating to another agent.

---

## Tool Registry

### 1. read_file
Read any `.md` or `.json` file from the workspace filesystem.

- Use for : Reading agent configs, heartbeat files, run logs, interaction logs
- Scope   : Read-only — orchestrator never writes to agent workspaces directly
- Examples:
  ```
  read_file("/workspaces/ml_processor/heartbeat.json")
  read_file("/workspaces/ml_processor/data/processed/tutorial_ml/run_log.json")
  read_file("/workspaces/orchestrator/logs/interaction_log.jsonl")
  ```

---

### 2. write_log
Append a structured entry to an orchestrator log file.

- Use for : Logging interactions, errors, startup events
- Scope   : Write-only to `/workspaces/orchestrator/logs/`
- Log files:
  - `startup_log.jsonl` — one entry per orchestrator startup
  - `interaction_log.jsonl` — one entry per user request handled
  - `error_log.jsonl` — one entry per failed delegation or agent error
- Entry schema (interaction):
  ```json
  {
    "timestamp": "<ISO8601>",
    "mode": "chat | api",
    "user_input": "string",
    "intent": "rag_query | video_process | system_status | direct",
    "delegated_to": "ml_processor | none",
    "skill": "rag_engine | video_content_analysis | none",
    "status": "success | error | partial",
    "duration_s": 0.0
  }
  ```

---

### 3. check_heartbeat
Read and evaluate the heartbeat file of a registered agent.

- Use for : Health check before every task delegation
- Input   : agent_id (string)
- Output  : `{ status: "UP" | "STALE" | "DOWN" | "DEGRADED", details: {} }`
- Logic   : Defined in HEARTBEAT.md — read that file for full evaluation rules

---

### 4. delegate_task
Send a structured task payload to a registered agent skill.

- Use for : Routing user requests to ml_processor skills
- Input   :
  ```json
  {
    "to": "ml_processor",
    "skill": "rag_engine | video_content_analysis",
    "payload": {}
  }
  ```
- Prerequisite : Always run `check_heartbeat` first
- Returns : Agent skill output (see AGENTS.md for output schemas)

---

### 5. list_processed_videos
List all videos that have been successfully processed by ml_processor.

- Use for : Answering "what videos are in the knowledge base?" questions
- Implementation:
  ```
  Scan: /workspaces/ml_processor/data/processed/
  For each subdirectory:
    Read run_log.json → check status == "success"
    Read summary.json → get overall.title_suggestion and overall.domain
  Return: list of { video_id, title, domain, processed_at }
  ```

---

### 6. check_vector_store
Check if the ChromaDB knowledge base is populated and ready.

- Use for : Answering "is the knowledge base ready?" and pre-flight check before rag queries
- Implementation:
  ```
  Read: /workspaces/ml_processor/heartbeat.json → chromadb field
  OR
  Delegate lightweight stats call to ml_processor → rag_engine/inspect.py
  ```
- Returns : `{ status: "ready" | "empty" | "missing", chunk_count: N, videos: [] }`

---

## Tool Usage Rules

1. **Always `check_heartbeat` before `delegate_task`** — never delegate blind
2. **Never write to agent workspaces** — orchestrator is read-only on other agent directories
3. **Always `write_log` after every user interaction** — for auditability
4. **`list_processed_videos` before answering "what do you know about?"** — gives accurate answer
5. **Do not call tools in parallel for the same user request** — sequential, predictable execution

---

## Tool Execution Order (standard flow)

```
User request received
        │
        ▼
1. check_heartbeat(ml_processor)
        │ UP? → continue │ DOWN? → report error, stop
        ▼
2. [optional] check_vector_store     ← only for rag queries
        │
        ▼
3. delegate_task(ml_processor, skill, payload)
        │
        ▼
4. synthesize and format response
        │
        ▼
5. write_log(interaction entry)
```

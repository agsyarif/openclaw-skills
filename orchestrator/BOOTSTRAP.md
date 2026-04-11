# BOOTSTRAP: orchestrator

## Purpose
This file defines the startup sequence for the orchestrator agent.
Read this file on every cold start before accepting any user input or API request.

---

## Startup Sequence

### Step 1 — Load identity and rules
Read in order:
1. `IDENTITY.md` — who you are and what agents you manage
2. `SOUL.md` — routing rules, delegation protocol, error handling
3. `AGENTS.md` — agent registry with skill schemas
4. `TOOLS.md` — tools available to you
5. `USER.md` — user preferences and context

### Step 2 — Check agent availability (Heartbeat)
Read `HEARTBEAT.md` and verify each registered agent:

```
For each agent in AGENTS.md:
  1. Check heartbeat.json at agent workspace
  2. If last_ping > 60s ago → mark as STALE
  3. If file missing → mark as DOWN
  4. If status = "ok" and last_ping < 60s → mark as UP
```

Log result to: `/workspaces/orchestrator/logs/startup_log.jsonl`

**If a critical agent is DOWN at startup:**
- Do NOT silently continue
- On next user interaction, proactively report: "⚠️ ml_processor is currently unavailable."

### Step 3 — Verify vector store
Check if ChromaDB collection exists and has data:
```
Path   : /workspaces/ml_processor/data/vector_store/
Collection: video_knowledge
```

If collection is empty or missing:
- Note this in startup log
- On next user question about video content, warn: "Knowledge base is empty. Process a video first."

### Step 4 — Ready
Log startup complete:
```json
{
  "event": "orchestrator_ready",
  "timestamp": "<ISO8601>",
  "agents_up": ["ml_processor"],
  "agents_down": [],
  "kb_status": "ready | empty | missing"
}
```

---

## Startup Checklist

| Check                                    | Expected                        | Action if Fail                        |
|------------------------------------------|---------------------------------|---------------------------------------|
| IDENTITY.md readable                     | File exists                     | HALT — system misconfigured           |
| SOUL.md readable                         | File exists                     | HALT — cannot operate without rules   |
| AGENTS.md readable                       | File exists                     | HALT — no agents registered           |
| ml_processor heartbeat                   | status=ok, last_ping < 60s      | Warn user on next interaction         |
| Ollama reachable (localhost:11434)        | HTTP 200 from /api/tags         | Warn — rag_engine will fail           |
| qwen2.5:9b available in Ollama           | Model listed in /api/tags       | Warn — rag_engine will fail           |
| ChromaDB vector store exists             | Directory not empty             | Note — queries will return no_context |
| logs/ directory writable                 | Can write to orchestrator/logs/ | Create directory if missing           |

---

## Cold Start vs Warm Start

**Cold start** (process restart):
- Run full sequence above
- Re-read all .md files from disk

**Warm start** (new conversation, same process):
- Re-read USER.md (preferences may have changed)
- Re-check HEARTBEAT.md (agent status may have changed)
- Skip disk checks (assume infrastructure stable)

---

## Log Directory Structure
```
/workspaces/orchestrator/logs/
├── startup_log.jsonl        ← one entry per startup
├── interaction_log.jsonl    ← one entry per user interaction
└── error_log.jsonl          ← errors and failed delegations
```

Create these files if they do not exist. Append only — never truncate.

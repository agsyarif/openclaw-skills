# BOOTSTRAP: orchestrator

## Cold Start Sequence

Run once on process start. Prioritize speed — skip non-critical checks.

```
1. Load IDENTITY.md, SOUL.md, AGENTS.md, TOOLS.md, USER.md  ← required
2. Load MEMORY.md (or memory.md)                            ← if exists, load session context
3. Load watchlist.json                                      ← if missing, init as []
4. Ensure logs/ directory exists                            ← create if missing
5. Ready — accept first request
```

No blocking health checks on startup.
If a file in step 1 is unreadable → halt and report the missing file.
Everything else: best-effort, continue regardless.

---

## Warm Start (new conversation, same process)

```
1. Re-read USER.md    ← preferences may have been updated
2. Re-read MEMORY.md  ← pick up session context
3. Re-load watchlist.json
```

---

## Directory Structure

```
/workspaces/orchestrator/
├── IDENTITY.md
├── SOUL.md
├── AGENTS.md
├── TOOLS.md
├── USER.md
├── HEARTBEAT.md
├── BOOTSTRAP.md
├── MEMORY.md           ← session + persistent memory
├── heartbeat.json
├── data/
│   └── watchlist.json
└── logs/
    ├── interaction_log.jsonl
    └── error_log.jsonl
```

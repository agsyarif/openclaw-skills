# BOOTSTRAP: web_scraper

## Cold Start Sequence
```
1. Load IDENTITY.md, SOUL.md, AGENTS.md, TOOLS.md   ← required
2. Read config/sources.json                          ← if missing, log warning, continue
3. Ensure logs/ directory exists                     ← create if missing
4. Write initial heartbeat.json
5. Ready — accept tasks from orchestrator
```

No blocking checks. Agent is ready as soon as config is loaded.
If config/sources.json is missing → use hardcoded default source list from IDENTITY.md.

## Directory Structure
```
/workspaces/web_scraper/
├── IDENTITY.md
├── SOUL.md
├── AGENTS.md
├── TOOLS.md
├── HEARTBEAT.md
├── BOOTSTRAP.md
├── MEMORY.md
├── heartbeat.json
├── config/
│   └── sources.json
├── skills/
│   ├── scrape_news/run.py
│   ├── scrape_trending/run.py
│   └── scrape_sector/run.py
└── logs/
    └── scrape_log.jsonl
```

# BOOTSTRAP: ml_processor

## Cold Start Sequence
```
1. Load IDENTITY.md, SOUL.md, AGENTS.md, TOOLS.md   ← required
2. Ensure data/raw/ exists                           ← create if missing
3. Ensure data/processed/ exists                     ← create if missing
4. Ensure data/vector_store/ exists                  ← create if missing
5. Ensure data/training_sets/ exists                 ← create if missing
6. Ensure logs/ exists                               ← create if missing
7. Check ChromaDB collection → set chromadb status
8. Write initial heartbeat.json
9. Ready — accept tasks from orchestrator
```

Ollama is NOT checked on startup — only checked at first rag_query call.
Missing directories are created silently — not startup errors.

## First-Run Notes
On a completely fresh install:
- `data/vector_store/` will be empty → chromadb status = `empty`
- This is normal — process a video first to populate the knowledge base
- rag_query will return `no_context` until at least one video is ingested

## Ollama Setup (one-time, manual)
```bash
ollama serve
ollama pull qwen2.5:9b
```
These are run by the developer, not by bootstrap.

## Directory Structure
```
/workspaces/ml_processor/
├── IDENTITY.md
├── SOUL.md
├── AGENTS.md
├── TOOLS.md
├── HEARTBEAT.md
├── BOOTSTRAP.md
├── MEMORY.md
├── heartbeat.json
├── skills/
│   ├── rag_engine/
│   └── video_content_analysis/
├── data/
│   ├── raw/
│   ├── processed/
│   ├── vector_store/
│   └── training_sets/
└── logs/
    ├── rag_log.jsonl
    └── ingest_log.jsonl
```

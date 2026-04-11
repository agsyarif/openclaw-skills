# AGENTS: ml_processor

## Overview

This file defines all connections between ml_processor and other agents or skills
within the OpenClaw system. ml_processor can receive tasks from the orchestrator,
consume data from web_scraper, and serve knowledge to fin_analyst or other agents.

---

## Owned Skills (Local)

### video_content_analysis

- Path : `skills/video_content_analysis/`
- Entry point : `pipeline.py <video_path> [--skip-embed] [--skip-jsonl] [--force]`
- Input : Video file (mp4, mkv, webm, avi) in `/data/raw/`
- Output :
  - `/data/processed/{video_id}/transcript_raw.json`
  - `/data/processed/{video_id}/transcript_clean.json`
  - `/data/processed/{video_id}/summary.json`
  - `/data/processed/{video_id}/run_log.json`
  - `/data/vector_store/` (ChromaDB — via chunk_and_embed)
  - `/data/training_sets/{video_id}.jsonl` + `combined_latest.jsonl`
- Depends on : Ollama (qwen2.5:9b), ffmpeg, Whisper, ChromaDB

### rag_engine

- Path : `skills/rag_engine/`
- Entry point : `generate.py` → `rag_query(query, top_k, domain_filter, video_filter)`
- Input : Natural language query string
- Output : `{ query, answer, sources, confidence, model, duration_s }`
- Reads from : `/data/vector_store/` (ChromaDB, collection: `video_knowledge`)
- Depends on : Ollama (qwen2.5:9b), ChromaDB
- Access : Read-only on vector store — never writes

---

## Upstream Agents (Send data TO ml_processor)

### orchestrator

- Agent path : `/agents/orchestrator/`
- Workspace : `/workspaces/orchestrator/`
- Relationship : ml_processor receives task assignments from orchestrator
- Task format :
  ```json
  {
    "task": "process_video",
    "payload": {
      "video_path": "/workspaces/ml_processor/data/raw/lecture_01.mp4",
      "language": "id",
      "domain": "teknologi"
    }
  }
  ```
- Expected response:
  ```json
  {
    "status": "success",
    "video_id": "lecture_01",
    "chunks_indexed": 48,
    "training_records": 144
  }
  ```

### web_scraper

- Agent path : `/agents/web_scraper/`
- Workspace : `/workspaces/web_scraper/`
- Relationship : web_scraper may deliver downloaded video files or transcripts
  into `/workspaces/ml_processor/data/raw/` for processing
- Trigger : File appears in `/data/raw/` with a `.ready` sentinel file
- Sentinel format: `{video_id}.ready` — signals the file is fully downloaded
- Protocol : ml_processor polls for `.ready` files; processes them in order

---

## Downstream Agents (ml_processor serves data TO these)

### fin_analyst

- Agent path : `/agents/fin_analyst/`
- Workspace : `/workspaces/fin_analyst/`
- Relationship : fin_analyst may query ml_processor's knowledge base via rag_engine
  to enrich financial analysis with domain-specific video content
- Call method :

  ```python
  # fin_analyst calls this directly
  from ml_processor.skills.rag_engine.generate import rag_query

  result = rag_query(
      query="What did the video say about interest rate trends?",
      domain_filter="keuangan",
      top_k=4
  )
  ```

- Access level : Query only — fin_analyst cannot trigger video processing

### orchestrator (downstream)

- Relationship : ml_processor reports task completion back to orchestrator
- Report format:
  ```json
  {
    "agent": "ml_processor",
    "task_id": "task_abc123",
    "status": "success" | "failed",
    "summary": "Processed lecture_01.mp4 — 48 chunks indexed, 144 training records added",
    "artifacts": [
      "/data/processed/lecture_01/summary.json",
      "/data/training_sets/lecture_01.jsonl"
    ]
  }
  ```

---

## Global Skills Used

### common_search

- Path : `/global_skills/common_search/`
- When used : If ml_processor needs to look up supplementary information
  not available in the local knowledge base
- Access : Registered in agent.json under `global_skills`

### file_utility

- Path : `/global_skills/file_utility/`
- When used : File format conversion, moving files between directories,
  checking file integrity before processing
- Access : Registered in agent.json under `global_skills`

---

## agent.json Reference

```json
{
  "agent_id": "ml_processor",
  "workspace": "/workspaces/ml_processor",
  "skills": [
    {
      "name": "video_content_analysis",
      "path": "skills/video_content_analysis/pipeline.py",
      "trigger": "manual",
      "description": "Process raw video into transcript, summary, and vector embeddings"
    },
    {
      "name": "rag_engine",
      "path": "skills/rag_engine/generate.py",
      "entry_function": "rag_query",
      "trigger": "auto",
      "description": "Answer questions from video knowledge base via local RAG pipeline"
    }
  ],
  "global_skills": ["common_search", "file_utility"],
  "upstream_agents": ["orchestrator", "web_scraper"],
  "downstream_agents": ["fin_analyst", "orchestrator"],
  "llm": {
    "provider": "ollama",
    "model": "qwen2.5:9b",
    "base_url": "http://localhost:11434"
  }
}
```

---

## Communication Protocol Summary

```
orchestrator
    │  assigns task (process_video)
    ▼
ml_processor
    │  runs video_content_analysis pipeline
    │  indexes chunks into ChromaDB
    │  reports completion to orchestrator
    │
    │  also serves knowledge via rag_engine
    ▼
fin_analyst / orchestrator / other agents
    │  call rag_query() directly
    ▼
ChromaDB (video_knowledge collection)
    + Ollama qwen2.5:9b
    → structured answer with sources
```

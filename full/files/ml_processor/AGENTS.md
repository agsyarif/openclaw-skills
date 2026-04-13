# AGENTS: ml_processor

## Position in System
ml_processor is a downstream agent. Receives tasks from orchestrator only.
Does not call other agents. Does not initiate tasks autonomously.

```
orchestrator
    ├──→ ml_processor.rag_query(query, top_k, domain_filter)
    └──→ ml_processor.video_content_analysis(video_path, language, model_size)
```

---

## Upstream: orchestrator

```json
// rag_query
{
  "task": "rag_query",
  "query": "coal mining sector IDX outlook",
  "top_k": 4,
  "domain_filter": null,
  "video_filter": null
}

// video_content_analysis
{
  "task": "video_content_analysis",
  "video_path": "/workspaces/ml_processor/data/raw/lecture_01.mp4",
  "language": "id",
  "model_size": "medium",
  "force": false
}
```

---

## Output Schemas

### rag_query → RAGResult
```json
{
  "query": "string",
  "answer": "string",
  "sources": [
    {
      "video_id": "string",
      "video_title": "string",
      "start": 0.0,
      "end": 0.0,
      "topic": "string",
      "chunk": "string (max 200 chars)",
      "score": 0.0
    }
  ],
  "model": "qwen2.5:9b",
  "confidence": "high | medium | low | no_context | error",
  "retrieved_chunks": 4,
  "duration_s": 0.0
}
```

### video_content_analysis → IngestResult
```json
{
  "video_id": "string",
  "status": "success | failed | skipped",
  "skipped_reason": "already_processed | null",
  "steps_completed": ["extract_audio", "transcribe", "segment_clean", "summarize", "embed", "build_jsonl"],
  "failed_at": "step_name | null",
  "chunks_indexed": 0,
  "training_records": 0,
  "duration_s": 0.0
}
```

---

## Workspace Structure
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
│   │   ├── ollama_client.py    ← shared Ollama interface
│   │   ├── retrieve.py         ← ChromaDB query
│   │   ├── rerank.py           ← hybrid BM25 + semantic rerank
│   │   ├── generate.py         ← RAG orchestrator (entry point)
│   │   ├── inspect.py          ← debug: KB stats
│   │   └── query.py            ← CLI for manual testing
│   └── video_content_analysis/
│       ├── extract_audio.py
│       ├── transcribe.py
│       ├── segment_and_clean.py
│       ├── summarize.py
│       ├── chunk_and_embed.py
│       ├── build_training_jsonl.py
│       └── pipeline.py         ← entry point
└── data/
    ├── raw/                    ← incoming video files
    ├── processed/              ← per-video outputs
    ├── vector_store/           ← ChromaDB
    └── training_sets/          ← JSONL datasets
```

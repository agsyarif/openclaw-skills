# AGENTS: orchestrator

## Registered Agents

### ml_processor
- Workspace     : `/workspaces/ml_processor/`
- Agent config  : `/agents/ml_processor/agent.json`
- Heartbeat     : `/workspaces/ml_processor/heartbeat.json`
- Status        : Active

#### Skills exposed by ml_processor:

**rag_engine**
- Entry         : `skills/rag_engine/generate.py` → `rag_query()`
- Trigger       : User question about video content
- Input payload :
  ```json
  {
    "query": "string",
    "top_k": 4,
    "top_n": 10,
    "domain_filter": "string | null",
    "video_filter": "string | null",
    "temperature": 0.2
  }
  ```
- Output schema :
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
        "chunk": "string",
        "score": 0.0
      }
    ],
    "model": "qwen2.5:9b",
    "retrieved_chunks": 4,
    "confidence": "high | medium | low | no_context | error",
    "duration_s": 0.0
  }
  ```

**video_content_analysis**
- Entry         : `skills/video_content_analysis/pipeline.py`
- Trigger       : New video file to process
- Input payload :
  ```json
  {
    "video_path": "/workspaces/ml_processor/data/raw/<filename>",
    "language": "id",
    "model_size": "medium",
    "skip_embed": false,
    "skip_jsonl": false,
    "force": false
  }
  ```
- Output schema :
  ```json
  {
    "video_id": "string",
    "status": "success | failed",
    "steps": {},
    "total_duration_s": 0.0,
    "artifacts": {
      "summary": "string",
      "chunks_indexed": 0,
      "training_records": 0
    }
  }
  ```

---

## Agent Communication Map

```
[User / API]
     │
     ▼
[orchestrator]
     │
     ├──→ [ml_processor] → rag_engine           (knowledge query)
     │
     └──→ [ml_processor] → video_content_analysis  (video ingestion)
```

---

## Planned Agents (Not Yet Active)

| Agent       | Planned Capability                        | Status   |
|-------------|-------------------------------------------|----------|
| web_scraper | Web crawling, video URL downloading       | Planned  |
| fin_analyst | Financial report analysis, chart parsing  | Planned  |

When these agents are registered, update this file and HEARTBEAT.md accordingly.

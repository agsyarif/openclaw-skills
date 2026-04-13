# MEMORY: ml_processor

## Knowledge Base State
Updated after every video ingestion and after startup stats check.
```json
{
  "total_chunks": 0,
  "total_videos": 0,
  "indexed_videos": [],
  "total_training_records": 0,
  "last_ingest_at": null,
  "last_rag_query_at": null
}
```

## Processed Video Index
Tracks which videos have been successfully ingested.
Avoids re-reading all run_log.json files on every request.
```json
[]
```
Each entry:
```json
{
  "video_id": "string",
  "title": "string",
  "domain": "string",
  "chunks": 0,
  "processed_at": "ISO8601"
}
```
Updated automatically by video_content_analysis on success.

## Domain Vocabulary
Known domains in the knowledge base — used to set domain_filter in RAG queries.
Auto-built from processed video metadata. Manual additions allowed.
```json
[]
```
Example: `["teknologi", "analisa_teknikal", "coal_mining", "banking"]`

## Fine-Tuning Readiness
```json
{
  "training_records": 0,
  "minimum_recommended": 500,
  "ready_for_finetuning": false
}
```
Updated after each video ingestion.
When `ready_for_finetuning` becomes true, log a notice to orchestrator
(do not auto-trigger training — wait for explicit user instruction).

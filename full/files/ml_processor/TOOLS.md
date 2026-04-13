# TOOLS: ml_processor

## check_ollama() → bool
Ping `http://localhost:11434/api/tags`. Timeout: 3s.
Returns true if reachable AND qwen2.5:9b is listed.
Called only at the start of rag_query — not on every request.

## get_collection() → collection | error
Open ChromaDB persistent client at `/data/vector_store/`.
Get or create collection `video_knowledge` with cosine similarity.
Returns error object if path unreadable.

## collection_stats() → { count, videos, domains }
Read all metadata from ChromaDB collection.
Returns chunk count, list of indexed video IDs, list of domains.
Used by inspect.py and heartbeat.

---

## read_run_log(video_id) → object | null
Read `/data/processed/{video_id}/run_log.json`.
Returns null if file does not exist.
Used to check if a video was already successfully processed.

## write_run_log(video_id, entry)
Write or overwrite `/data/processed/{video_id}/run_log.json`.

---

## append_training_data(video_id, records[])
Append records to `/data/training_sets/{video_id}.jsonl`
AND append same records to `/data/training_sets/combined_latest.jsonl`.
Append only — never truncate either file.

## count_training_records() → int
Count lines in `combined_latest.jsonl`. Used for readiness threshold check.
Threshold: 500 records minimum before fine-tuning is recommended.

---

## log_rag(entry)
Append to `/workspaces/ml_processor/logs/rag_log.jsonl`.
```json
{ "ts": "ISO8601", "query": "string", "confidence": "high", "chunks": 4, "duration_s": 0.0 }
```

## log_ingest(entry)
Append to `/workspaces/ml_processor/logs/ingest_log.jsonl`.
```json
{ "ts": "ISO8601", "video_id": "string", "status": "success", "chunks": 48, "duration_s": 420.0 }
```

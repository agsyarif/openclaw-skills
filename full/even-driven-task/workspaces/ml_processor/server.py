"""
server.py — ml_processor agent
Location: /workspaces/ml_processor/server.py
Run with: python server.py
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Shared modules from /workspaces/shared/
sys.path.insert(0, "/workspaces/shared")
from agent_server import AgentServer
from task_contract import SkillName

# ml_processor skill modules
sys.path.insert(0, "/workspaces/ml_processor/skills/rag_engine")
sys.path.insert(0, "/workspaces/ml_processor/skills/video_content_analysis")

VECTOR_STORE_PATH = "/workspaces/ml_processor/data/vector_store"
LOGS_DIR          = "/workspaces/ml_processor/logs"
MEMORY_PATH       = "/workspaces/ml_processor/MEMORY.md"


class MLProcessorServer(AgentServer):

    def __init__(self):
        super().__init__(agent_id="ml_processor", port=8003)
        self.register_skill(SkillName.RAG_QUERY,      self.rag_query)
        self.register_skill(SkillName.VIDEO_ANALYSIS, self.video_content_analysis)

        os.makedirs(LOGS_DIR, exist_ok=True)
        os.makedirs(VECTOR_STORE_PATH, exist_ok=True)

        # Check ChromaDB on startup
        self._chromadb_status = self._check_chromadb()
        self.log.info(f"ChromaDB status: {self._chromadb_status}")

        # Check Ollama on startup (non-blocking)
        self._ollama_status = "unknown"  # checked on first rag_query

    # ── Skills ────────────────────────────────────────────────────────────────

    def rag_query(self, payload: dict) -> dict:
        """
        Retrieve-Augmented Generation using local ChromaDB + Ollama.
        Follows SOUL.md rules: grounded answers only, source attribution always.
        """
        query         = payload.get("query", "")
        top_k         = payload.get("top_k", 4)
        top_n         = payload.get("top_n", 10)
        domain_filter = payload.get("domain_filter")
        video_filter  = payload.get("video_filter")

        if not query:
            return { "confidence": "error", "answer": "query is required", "sources": [] }

        # Check Ollama once per server lifetime (cached)
        if self._ollama_status == "unknown":
            self._ollama_status = self._check_ollama()

        if self._ollama_status != "ok":
            return {
                "confidence": "error",
                "answer":     "Ollama not available. Run: ollama serve",
                "sources":    [],
                "query":      query
            }

        if self._chromadb_status == "missing":
            return {
                "confidence": "error",
                "answer":     "Vector store missing. Process a video first.",
                "sources":    [],
                "query":      query
            }

        if self._chromadb_status == "empty":
            return {
                "confidence": "no_context",
                "answer":     "Knowledge base is empty. Process a video first.",
                "sources":    [],
                "query":      query
            }

        t_start = time.time()

        try:
            # Import and call the existing rag_engine generate.py
            from generate import rag_query as _rag_query
            result = _rag_query(
                query=query,
                top_n=top_n,
                top_k=top_k,
                domain_filter=domain_filter,
                video_filter=video_filter,
                temperature=0.1,
                verbose=False
            )
        except ImportError:
            # Fallback: direct implementation if generate.py not found
            result = self._rag_query_direct(query, top_k, domain_filter)
        except Exception as e:
            self.log.exception(f"RAG query failed: {query}")
            return {
                "confidence": "error",
                "answer":     f"RAG execution error: {str(e)}",
                "sources":    [],
                "query":      query
            }

        self._log_rag(query, result.get("confidence"), top_k, time.time() - t_start)
        return result

    def video_content_analysis(self, payload: dict) -> dict:
        """
        Long-running video ingestion pipeline.
        extract_audio → transcribe → segment → summarize → embed → jsonl
        """
        video_path = payload.get("video_path", "")
        language   = payload.get("language", "id")
        model_size = payload.get("model_size", "medium")
        force      = payload.get("force", False)

        if not video_path:
            return { "status": "failed", "error": "video_path is required" }

        if not Path(video_path).exists():
            return { "status": "failed", "error": f"File not found: {video_path}" }

        video_id   = Path(video_path).stem
        output_dir = f"/workspaces/ml_processor/data/processed/{video_id}"

        # Check if already processed
        run_log_path = Path(output_dir) / "run_log.json"
        if not force and run_log_path.exists():
            try:
                with open(run_log_path) as f:
                    existing = json.load(f)
                if existing.get("status") == "success":
                    return {
                        "status":          "skipped",
                        "skipped_reason":  "already_processed",
                        "video_id":        video_id,
                        "chunks_indexed":  existing.get("steps", {}).get("5a_embed", {}).get("chunks", 0),
                        "training_records": 0
                    }
            except Exception:
                pass

        t_start = time.time()

        try:
            from pipeline import run_pipeline
            run_log = run_pipeline(
                video_path=video_path,
                skip_embed=False,
                skip_jsonl=False,
                force=force,
                model_size=model_size,
                language=language
            )
        except ImportError:
            self.log.error("pipeline.py not found in skills/video_content_analysis/")
            return { "status": "failed", "error": "pipeline module not found" }
        except Exception as e:
            self.log.exception(f"Video pipeline failed: {video_path}")
            return { "status": "failed", "error": str(e) }

        duration = time.time() - t_start
        success  = run_log.get("status") == "success"

        # Update ChromaDB status after successful ingest
        if success:
            self._chromadb_status = "ok"
            self._update_memory(video_id, output_dir)

        result = {
            "video_id":         video_id,
            "status":           run_log.get("status"),
            "steps_completed":  list(run_log.get("steps", {}).keys()),
            "failed_at":        run_log.get("failed_at"),
            "chunks_indexed":   run_log.get("steps", {}).get("5a_embed", {}).get("chunks", 0),
            "training_records": self._count_training_records(),
            "duration_s":       round(duration, 1)
        }

        self._log_ingest(video_id, run_log.get("status"), result["chunks_indexed"], duration)
        return result

    # ── RAG Direct Fallback ───────────────────────────────────────────────────

    def _rag_query_direct(self, query: str, top_k: int, domain_filter) -> dict:
        """Direct RAG implementation if generate.py import fails."""
        import urllib.request, urllib.error

        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except ImportError:
            return { "confidence": "error", "answer": "chromadb not installed", "sources": [], "query": query }

        try:
            client     = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
            ef         = embedding_functions.DefaultEmbeddingFunction()
            collection = client.get_collection("video_knowledge", embedding_function=ef)
        except Exception as e:
            return { "confidence": "error", "answer": str(e), "sources": [], "query": query }

        where    = {"domain": {"$eq": domain_filter}} if domain_filter else None
        n        = min(top_k, collection.count())
        kw       = {"query_texts": [query], "n_results": n, "include": ["documents", "metadatas", "distances"]}
        if where:
            kw["where"] = where

        results  = collection.query(**kw)
        docs     = results["documents"][0]
        metas    = results["metadatas"][0]
        dists    = results["distances"][0]

        chunks   = []
        for doc, meta, dist in zip(docs, metas, dists):
            score = max(0.0, 1.0 - dist / 2.0)
            chunks.append({ "chunk": doc, "score": score, "meta": meta })

        if not chunks:
            return { "confidence": "no_context", "answer": "No relevant content found.", "sources": [], "query": query }

        top_score   = chunks[0]["score"]
        confidence  = "high" if top_score >= 0.6 else "medium" if top_score >= 0.3 else "low"
        context_str = "\n\n".join(f"[{i+1}] {c['chunk']}" for i, c in enumerate(chunks))

        prompt = (
            f"Answer based ONLY on the following context:\n\n{context_str}\n\n"
            f"Question: {query}\n\nAnswer:"
        )

        payload = json.dumps({
            "model": "qwen2.5:9b", "stream": False,
            "options": {"temperature": 0.1},
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(
            "http://localhost:11434/api/chat", data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            answer = json.loads(resp.read())["message"]["content"].strip()

        sources = [{
            "video_id":    c["meta"].get("video_id", ""),
            "video_title": c["meta"].get("video_title", ""),
            "start":       float(c["meta"].get("start", 0)),
            "end":         float(c["meta"].get("end", 0)),
            "topic":       c["meta"].get("topic", ""),
            "score":       round(c["score"], 4)
        } for c in chunks]

        return { "query": query, "answer": answer, "sources": sources,
                 "confidence": confidence, "model": "qwen2.5:9b" }

    # ── Checks ────────────────────────────────────────────────────────────────

    def _check_ollama(self) -> str:
        import urllib.request, urllib.error
        try:
            req  = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data   = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                found  = any("qwen2.5" in m for m in models)
                status = "ok" if found else "model_missing"
                self.log.info(f"Ollama: {status} | models: {models}")
                return status
        except Exception as e:
            self.log.warning(f"Ollama not reachable: {e}")
            return "unreachable"

    def _check_chromadb(self) -> str:
        try:
            import chromadb
            client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
            names  = [c.name for c in client.list_collections()]
            if "video_knowledge" not in names:
                return "empty"
            col = client.get_collection("video_knowledge")
            return "ok" if col.count() > 0 else "empty"
        except Exception:
            return "missing"

    # ── Memory / Stats ────────────────────────────────────────────────────────

    def _update_memory(self, video_id: str, output_dir: str):
        """Update MEMORY.md processed video index after successful ingest."""
        try:
            summary_path = Path(output_dir) / "summary.json"
            if summary_path.exists():
                with open(summary_path) as f:
                    summary = json.load(f)
                overall = summary.get("overall", {})
                self.log.info(
                    f"Indexed: {video_id} | domain: {overall.get('domain')} "
                    f"| chunks: {summary.get('total_blocks', 0)}"
                )
        except Exception as e:
            self.log.warning(f"Memory update failed: {e}")

    def _count_training_records(self) -> int:
        combined = Path("/workspaces/ml_processor/data/training_sets/combined_latest.jsonl")
        if not combined.exists():
            return 0
        try:
            with open(combined) as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log_rag(self, query: str, confidence: str, top_k: int, duration: float):
        entry = json.dumps({
            "ts":         datetime.now(timezone.utc).isoformat(),
            "query":      query[:100],
            "confidence": confidence,
            "top_k":      top_k,
            "duration_s": round(duration, 2)
        })
        with open(f"{LOGS_DIR}/rag_log.jsonl", "a") as f:
            f.write(entry + "\n")

    def _log_ingest(self, video_id: str, status: str, chunks: int, duration: float):
        entry = json.dumps({
            "ts":         datetime.now(timezone.utc).isoformat(),
            "video_id":   video_id,
            "status":     status,
            "chunks":     chunks,
            "duration_s": round(duration, 1)
        })
        with open(f"{LOGS_DIR}/ingest_log.jsonl", "a") as f:
            f.write(entry + "\n")

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def _update_heartbeat(self):
        try:
            import chromadb
            client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
            col    = client.get_collection("video_knowledge")
            chunks = col.count()
        except Exception:
            chunks = 0

        status = "error" if self._chromadb_status == "missing" else \
                 "degraded" if self._chromadb_status == "empty" else "ok"

        hb = {
            "agent_id":  "ml_processor",
            "status":    status,
            "last_ping": datetime.now(timezone.utc).isoformat(),
            "port":      self.port,
            "components": {
                "ollama":   self._ollama_status,
                "chromadb": self._chromadb_status
            },
            "kb_stats": {
                "chunks": chunks
            },
            "training_records": self._count_training_records()
        }
        with open("/workspaces/ml_processor/heartbeat.json", "w") as f:
            json.dump(hb, f, indent=2)


if __name__ == "__main__":
    MLProcessorServer().start()
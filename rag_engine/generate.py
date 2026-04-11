"""
generate.py
-----------
RAG orchestrator utama: retrieve → rerank → generate via Ollama.
Ini adalah entry point utama rag_engine yang dipanggil oleh agent lain.

Usage (sebagai modul — dipanggil agent):
    from generate import rag_query

    result = rag_query("Apa itu supervised learning?")
    print(result["answer"])

Usage (CLI):
    python generate.py "Apa itu supervised learning?"
    python generate.py "Cara training model" --domain teknologi --top-k 6
"""

import json
import sys
import time
from typing import Optional

from ollama_client import (
    DEFAULT_TOP_K, DEFAULT_TOP_N, OLLAMA_MODEL,
    check_ollama, collection_stats, ollama_chat
)
from rerank import rerank
from retrieve import retrieve

# ── System Prompt untuk RAG ───────────────────────────────────────────────────
RAG_SYSTEM_PROMPT = """Kamu adalah asisten yang menjawab pertanyaan berdasarkan KONTEKS yang diberikan.

Aturan ketat:
1. Jawab HANYA berdasarkan informasi yang ada di dalam KONTEKS
2. Jika informasi tidak ada di konteks, katakan "Informasi ini tidak tersedia dalam knowledge base"
3. Jangan mengarang atau menambahkan informasi dari luar konteks
4. Jika pertanyaan ambigu, jawab berdasarkan interpretasi yang paling masuk akal dari konteks
5. Sertakan timestamp video jika relevan untuk membantu pengguna menemukan bagian yang dimaksud
6. Gunakan bahasa yang sama dengan pertanyaan pengguna"""

LOW_CONFIDENCE_THRESHOLD = 0.30   # jika semua chunk di bawah ini, tandai low_confidence


def build_context_prompt(query: str, chunks: list[dict]) -> str:
    """
    Bangun prompt RAG dengan konteks dari chunk-chunk yang diretrieve.

    Format konteks menyertakan sumber (video, timestamp, topik) agar
    model bisa merujuk ke sumber yang spesifik dalam jawabannya.
    """
    context_parts = []

    for i, chunk in enumerate(chunks, 1):
        start_m = int(chunk["start"] // 60)
        start_s = int(chunk["start"] % 60)
        end_m   = int(chunk["end"] // 60)
        end_s   = int(chunk["end"] % 60)
        ts      = f"{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}"

        context_parts.append(
            f"[Sumber {i}] Video: {chunk['video_title']} | Waktu: {ts} | Topik: {chunk['topic']}\n"
            f"{chunk['chunk']}"
        )

    context_str = "\n\n---\n\n".join(context_parts)

    return f"""KONTEKS dari knowledge base video:

{context_str}

---

PERTANYAAN: {query}

Berikan jawaban yang komprehensif berdasarkan konteks di atas."""


def rag_query(
    query: str,
    top_n: int = DEFAULT_TOP_N,
    top_k: int = DEFAULT_TOP_K,
    domain_filter: Optional[str] = None,
    video_filter: Optional[str] = None,
    temperature: float = 0.2,
    verbose: bool = False
) -> dict:
    """
    Entry point utama RAG engine.

    Pipeline: retrieve → rerank → generate

    Args:
        query:         pertanyaan dari user atau agent lain
        top_n:         jumlah kandidat chunk dari ChromaDB (sebelum rerank)
        top_k:         jumlah chunk yang masuk ke prompt LLM (setelah rerank)
        domain_filter: filter domain (contoh: "teknologi", "kesehatan")
        video_filter:  filter ke satu video_id tertentu
        temperature:   kreativitas jawaban (0.0=deterministik, 1.0=kreatif)
        verbose:       print progress ke stdout

    Returns:
        dict berisi:
          - query:            pertanyaan original
          - answer:           jawaban dari model
          - sources:          list chunk yang dipakai (dengan metadata)
          - model:            nama model Ollama yang dipakai
          - retrieved_chunks: jumlah chunk yang dipakai
          - confidence:       "high" | "medium" | "low" | "no_context"
          - duration_s:       total waktu eksekusi dalam detik
    """
    t_start = time.time()

    # ── Cek prerequisite ──────────────────────────────────────────────────────
    if not check_ollama(verbose=False):
        return {
            "query":  query,
            "answer": "❌ Ollama tidak tersedia. Jalankan `ollama serve` terlebih dahulu.",
            "sources": [],
            "model":  OLLAMA_MODEL,
            "retrieved_chunks": 0,
            "confidence": "error",
            "duration_s": 0
        }

    # ── Step 1: Retrieve ──────────────────────────────────────────────────────
    if verbose:
        print(f"🔍 Retrieve: top_n={top_n}, domain={domain_filter or 'all'}, video={video_filter or 'all'}")

    try:
        candidates = retrieve(
            query=query,
            top_n=top_n,
            domain_filter=domain_filter,
            video_filter=video_filter
        )
    except ValueError as e:
        return {
            "query":  query,
            "answer": f"❌ {e}",
            "sources": [],
            "model":  OLLAMA_MODEL,
            "retrieved_chunks": 0,
            "confidence": "no_context",
            "duration_s": round(time.time() - t_start, 2)
        }

    if not candidates:
        return {
            "query":  query,
            "answer": "Tidak ditemukan informasi yang relevan dalam knowledge base. "
                      "Pastikan video sudah diproses oleh video_content_analysis.",
            "sources": [],
            "model":  OLLAMA_MODEL,
            "retrieved_chunks": 0,
            "confidence": "no_context",
            "duration_s": round(time.time() - t_start, 2)
        }

    if verbose:
        print(f"   ✓ {len(candidates)} kandidat ditemukan")

    # ── Step 2: Rerank ────────────────────────────────────────────────────────
    if verbose:
        print(f"⚖️  Rerank: hybrid scoring → top_k={top_k}")

    ranked_chunks = rerank(candidates, query, top_k=top_k)

    if verbose:
        for i, c in enumerate(ranked_chunks, 1):
            print(f"   [{i}] hybrid={c['hybrid_score']:.3f} | {c['video_title']} | {c['topic'][:40]}")

    # ── Tentukan confidence level ─────────────────────────────────────────────
    top_score = ranked_chunks[0]["hybrid_score"] if ranked_chunks else 0.0
    if top_score >= 0.6:
        confidence = "high"
    elif top_score >= LOW_CONFIDENCE_THRESHOLD:
        confidence = "medium"
    else:
        confidence = "low"

    # ── Step 3: Generate ──────────────────────────────────────────────────────
    if verbose:
        print(f"🤖 Generate: model={OLLAMA_MODEL}, confidence={confidence}")

    prompt = build_context_prompt(query, ranked_chunks)

    # Tambahkan catatan low confidence ke system prompt jika perlu
    system = RAG_SYSTEM_PROMPT
    if confidence == "low":
        system += "\n\nCATATAN: Konteks yang tersedia mungkin tidak terlalu relevan dengan pertanyaan. " \
                  "Sampaikan keterbatasan ini dalam jawaban jika perlu."

    answer = ollama_chat(prompt, system=system, temperature=temperature)

    # ── Susun output ──────────────────────────────────────────────────────────
    sources = [
        {
            "video_id":    c["video_id"],
            "video_title": c["video_title"],
            "start":       c["start"],
            "end":         c["end"],
            "topic":       c["topic"],
            "chunk":       c["chunk"][:200] + "..." if len(c["chunk"]) > 200 else c["chunk"],
            "score":       c["hybrid_score"]
        }
        for c in ranked_chunks
    ]

    duration = round(time.time() - t_start, 2)

    if verbose:
        print(f"\n✅ Selesai dalam {duration}s")

    return {
        "query":            query,
        "answer":           answer,
        "sources":          sources,
        "model":            OLLAMA_MODEL,
        "retrieved_chunks": len(ranked_chunks),
        "confidence":       confidence,
        "duration_s":       duration
    }


def print_result(result: dict):
    """Pretty-print hasil rag_query ke stdout."""
    conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴", "no_context": "⭕", "error": "❌"}

    print(f"\n{'='*60}")
    print(f"❓ Query      : {result['query']}")
    print(f"🎯 Confidence : {conf_icon.get(result['confidence'], '?')} {result['confidence']}")
    print(f"⏱️  Durasi     : {result['duration_s']}s")
    print(f"🤖 Model      : {result['model']}")
    print(f"{'='*60}\n")

    print(f"💬 Jawaban:\n{result['answer']}\n")

    if result["sources"]:
        print(f"📚 Sumber ({len(result['sources'])} chunk):")
        for i, src in enumerate(result["sources"], 1):
            start_m = int(src["start"] // 60)
            start_s = int(src["start"] % 60)
            end_m   = int(src["end"] // 60)
            end_s   = int(src["end"] % 60)
            ts      = f"{start_m:02d}:{start_s:02d}-{end_m:02d}:{end_s:02d}"
            print(f"  [{i}] {src['video_title']} [{ts}] — {src['topic']} (score: {src['score']:.3f})")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG query ke knowledge base video")
    parser.add_argument("query",      help="Pertanyaan yang ingin dijawab")
    parser.add_argument("--top-k",    type=int,   default=DEFAULT_TOP_K, help=f"Chunk ke prompt (default: {DEFAULT_TOP_K})")
    parser.add_argument("--top-n",    type=int,   default=DEFAULT_TOP_N, help=f"Kandidat retrieve (default: {DEFAULT_TOP_N})")
    parser.add_argument("--domain",   default=None, help="Filter domain")
    parser.add_argument("--video",    default=None, help="Filter video_id")
    parser.add_argument("--temp",     type=float, default=0.2, help="Temperature (default: 0.2)")
    parser.add_argument("--verbose",  action="store_true",  help="Tampilkan progress detail")
    parser.add_argument("--json",     action="store_true",  help="Output sebagai JSON")
    args = parser.parse_args()

    result = rag_query(
        query=args.query,
        top_k=args.top_k,
        top_n=args.top_n,
        domain_filter=args.domain,
        video_filter=args.video,
        temperature=args.temp,
        verbose=args.verbose
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_result(result)

"""
retrieve.py
-----------
Query ChromaDB vector store dan kembalikan chunk-chunk relevan
beserta metadata dan similarity score.

Usage:
    python retrieve.py "apa itu machine learning?" [--top-n 10] [--domain teknologi]
"""

import sys
from typing import Optional

from ollama_client import DEFAULT_TOP_N, get_collection


def retrieve(
    query: str,
    top_n: int = DEFAULT_TOP_N,
    domain_filter: Optional[str] = None,
    video_filter: Optional[str] = None
) -> list[dict]:
    """
    Retrieve chunk-chunk relevan dari ChromaDB berdasarkan query.

    Args:
        query:         teks query dari user/agent
        top_n:         jumlah chunk yang diambil dari ChromaDB (sebelum rerank)
        domain_filter: filter berdasarkan domain (contoh: "teknologi", "kesehatan")
        video_filter:  filter berdasarkan video_id tertentu

    Returns:
        list of dict, masing-masing berisi:
          - chunk:      teks chunk
          - score:      similarity score (0.0 - 1.0, makin tinggi makin relevan)
          - video_id:   ID video sumber
          - video_title: judul video
          - block_id:   nomor blok dalam video
          - start/end:  timestamp dalam video (detik)
          - topic:      topik blok (dari summarize.py)
          - summary:    ringkasan blok
          - keywords:   kata kunci blok
          - domain:     domain konten
    """
    collection = get_collection()

    total_chunks = collection.count()
    if total_chunks == 0:
        return []

    # Bangun where clause untuk filter (ChromaDB where syntax)
    where: Optional[dict] = None
    if domain_filter and video_filter:
        where = {
            "$and": [
                {"domain":   {"$eq": domain_filter}},
                {"video_id": {"$eq": video_filter}}
            ]
        }
    elif domain_filter:
        where = {"domain": {"$eq": domain_filter}}
    elif video_filter:
        where = {"video_id": {"$eq": video_filter}}

    # Pastikan top_n tidak melebihi total dokumen
    n_results = min(top_n, total_chunks)

    query_kwargs: dict = {
        "query_texts": [query],
        "n_results":   n_results,
        "include":     ["documents", "metadatas", "distances"]
    }
    if where:
        query_kwargs["where"] = where

    results = collection.query(**query_kwargs)

    # Flatten hasil ChromaDB (selalu wrapped dalam list karena batch query)
    docs      = results["documents"][0]
    metas     = results["metadatas"][0]
    distances = results["distances"][0]

    chunks = []
    for doc, meta, dist in zip(docs, metas, distances):
        # ChromaDB dengan cosine space mengembalikan distance (0=identik, 2=berlawanan)
        # Konversi ke similarity score 0.0-1.0
        score = max(0.0, 1.0 - (dist / 2.0))

        chunks.append({
            "chunk":       doc,
            "score":       round(score, 4),
            "video_id":    meta.get("video_id", ""),
            "video_title": meta.get("video_title", ""),
            "block_id":    meta.get("block_id", ""),
            "chunk_index": meta.get("chunk_index", ""),
            "start":       float(meta.get("start", 0)),
            "end":         float(meta.get("end", 0)),
            "topic":       meta.get("topic", ""),
            "summary":     meta.get("summary", ""),
            "keywords":    meta.get("keywords", ""),
            "domain":      meta.get("domain", ""),
        })

    return chunks


def format_timestamp(seconds: float) -> str:
    """Konversi detik ke format MM:SS untuk display."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


def print_chunks(chunks: list[dict], query: str = ""):
    """Pretty-print hasil retrieve untuk debugging."""
    if query:
        print(f"\n🔍 Query: '{query}'")
    print(f"📦 Ditemukan {len(chunks)} chunk:\n")

    for i, c in enumerate(chunks, 1):
        ts = f"{format_timestamp(c['start'])} - {format_timestamp(c['end'])}"
        print(f"  [{i}] Score: {c['score']:.3f} | {c['video_title']} | {ts}")
        print(f"       Topik  : {c['topic']}")
        print(f"       Chunk  : {c['chunk'][:120]}...")
        print()


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Retrieve chunks dari vector store")
    parser.add_argument("query",          help="Teks query")
    parser.add_argument("--top-n",        type=int, default=DEFAULT_TOP_N, help="Jumlah hasil (default: 10)")
    parser.add_argument("--domain",       default=None, help="Filter domain")
    parser.add_argument("--video",        default=None, help="Filter video_id")
    args = parser.parse_args()

    try:
        chunks = retrieve(
            query=args.query,
            top_n=args.top_n,
            domain_filter=args.domain,
            video_filter=args.video
        )
        print_chunks(chunks, args.query)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

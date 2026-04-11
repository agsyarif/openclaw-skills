"""
inspect.py
----------
Tool debug untuk melihat isi vector store ChromaDB.
Berguna untuk verifikasi setelah video_content_analysis berjalan.

Usage:
    python inspect.py                        # statistik keseluruhan
    python inspect.py --video tutorial_ml    # lihat chunks dari video tertentu
    python inspect.py --domain teknologi     # filter per domain
    python inspect.py --search "machine learning" --top 5  # semantic search debug
"""

import sys
from typing import Optional

from ollama_client import COLLECTION_NAME, VECTOR_STORE_PATH, collection_stats, get_collection


def show_stats():
    """Tampilkan statistik keseluruhan vector store."""
    print(f"\n{'='*55}")
    print(f"📊 VECTOR STORE STATS")
    print(f"   Path      : {VECTOR_STORE_PATH}")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"{'='*55}")

    stats = collection_stats()

    if stats.get("error") == "collection_not_found":
        print(f"\n⭕ Collection belum ada.")
        print(f"   Jalankan video_content_analysis/pipeline.py untuk memproses video pertama.\n")
        return

    count   = stats["count"]
    videos  = stats["videos"]
    domains = stats["domains"]

    print(f"\n📦 Total chunk : {count}")
    print(f"🎬 Video       : {len(videos)} video")
    print(f"🏷️  Domain      : {', '.join(domains) or '(tidak ada)'}")

    if videos:
        print(f"\n📋 Daftar video yang diindeks:")
        col = get_collection()
        for vid in videos:
            result     = col.get(where={"video_id": {"$eq": vid}}, include=["metadatas"])
            metas      = result["metadatas"]
            n_chunks   = len(metas)
            title      = metas[0].get("video_title", vid) if metas else vid
            domain     = metas[0].get("domain", "-") if metas else "-"
            print(f"   • {vid}")
            print(f"     Judul  : {title}")
            print(f"     Domain : {domain}")
            print(f"     Chunks : {n_chunks}")
    print()


def show_video_chunks(video_id: str, limit: int = 5):
    """Tampilkan chunk-chunk dari video tertentu."""
    print(f"\n🎬 Chunks dari video: '{video_id}'")
    print(f"{'='*55}")

    col    = get_collection()
    result = col.get(
        where={"video_id": {"$eq": video_id}},
        include=["documents", "metadatas"]
    )

    docs  = result["documents"]
    metas = result["metadatas"]

    if not docs:
        print(f"⚠️  Tidak ada chunk untuk video '{video_id}'")
        print(f"   Pastikan nama video_id sudah benar (gunakan --stats untuk melihat daftar).\n")
        return

    print(f"Total: {len(docs)} chunk | Menampilkan {min(limit, len(docs))} pertama\n")

    for i, (doc, meta) in enumerate(zip(docs[:limit], metas[:limit]), 1):
        start = float(meta.get("start", 0))
        end   = float(meta.get("end", 0))
        sm    = int(start // 60); ss = int(start % 60)
        em    = int(end // 60);   es = int(end % 60)
        ts    = f"{sm:02d}:{ss:02d} - {em:02d}:{es:02d}"

        print(f"  [{i}] Blok {meta.get('block_id','?')} | {ts}")
        print(f"       Topik  : {meta.get('topic', '-')}")
        print(f"       Chunk  : {doc[:150]}...")
        print()


def show_domain_chunks(domain: str, limit: int = 5):
    """Tampilkan chunk-chunk dari domain tertentu."""
    print(f"\n🏷️  Chunks dengan domain: '{domain}'")
    print(f"{'='*55}")

    col    = get_collection()
    result = col.get(
        where={"domain": {"$eq": domain}},
        include=["documents", "metadatas"]
    )

    docs  = result["documents"]
    metas = result["metadatas"]

    if not docs:
        print(f"⚠️  Tidak ada chunk untuk domain '{domain}'\n")
        return

    print(f"Total: {len(docs)} chunk | Menampilkan {min(limit, len(docs))} pertama\n")

    for i, (doc, meta) in enumerate(zip(docs[:limit], metas[:limit]), 1):
        print(f"  [{i}] {meta.get('video_title', meta.get('video_id', '-'))}")
        print(f"       Topik  : {meta.get('topic', '-')}")
        print(f"       Chunk  : {doc[:150]}...")
        print()


def debug_search(query: str, top_n: int = 5):
    """
    Semantic search debug — tampilkan raw ChromaDB results
    sebelum rerank, berguna untuk diagnosa kualitas retrieval.
    """
    from retrieve import retrieve

    print(f"\n🔬 DEBUG SEARCH: '{query}'")
    print(f"{'='*55}")

    chunks = retrieve(query=query, top_n=top_n)

    if not chunks:
        print("⚠️  Tidak ada hasil\n")
        return

    print(f"Top {len(chunks)} hasil (semantic only, sebelum rerank):\n")
    for i, c in enumerate(chunks, 1):
        sm = int(c["start"] // 60); ss = int(c["start"] % 60)
        em = int(c["end"] // 60);   es = int(c["end"] % 60)
        ts = f"{sm:02d}:{ss:02d}-{em:02d}:{es:02d}"

        print(f"  [{i}] score={c['score']:.4f} | {c['video_title']} | [{ts}]")
        print(f"       Topik  : {c['topic']}")
        print(f"       Chunk  : {c['chunk'][:120]}...")
        print()


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inspect isi vector store ChromaDB")
    parser.add_argument("--video",   default=None, help="Tampilkan chunks dari video_id tertentu")
    parser.add_argument("--domain",  default=None, help="Tampilkan chunks dari domain tertentu")
    parser.add_argument("--search",  default=None, help="Debug semantic search")
    parser.add_argument("--limit",   type=int, default=5, help="Jumlah chunk yang ditampilkan (default: 5)")
    parser.add_argument("--top",     type=int, default=5, help="Top-N untuk debug search (default: 5)")
    args = parser.parse_args()

    try:
        if args.search:
            show_stats()
            debug_search(args.search, top_n=args.top)
        elif args.video:
            show_stats()
            show_video_chunks(args.video, limit=args.limit)
        elif args.domain:
            show_stats()
            show_domain_chunks(args.domain, limit=args.limit)
        else:
            show_stats()

    except ValueError as e:
        print(f"\n❌ {e}\n")
        sys.exit(1)

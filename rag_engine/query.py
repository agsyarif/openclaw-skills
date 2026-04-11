"""
query.py
--------
CLI interaktif untuk query knowledge base RAG secara manual.
Berguna untuk testing, demo, dan debugging.

Mode 1 — Query tunggal:
    python query.py "Apa itu machine learning?"
    python query.py "Cara training model" --domain teknologi --top-k 6

Mode 2 — Sesi interaktif (REPL):
    python query.py --interactive

Mode 3 — Batch query dari file:
    python query.py --batch queries.txt
"""

import json
import sys
from pathlib import Path

from generate import print_result, rag_query
from inspect import show_stats
from ollama_client import DEFAULT_TOP_K, DEFAULT_TOP_N, check_ollama


def interactive_session(
    top_k: int = DEFAULT_TOP_K,
    top_n: int = DEFAULT_TOP_N,
    domain_filter=None,
    video_filter=None,
    temperature: float = 0.2
):
    """
    Sesi REPL interaktif untuk query berulang.
    Ketik 'exit' atau 'quit' untuk keluar.
    Ketik 'stats' untuk melihat statistik vector store.
    Ketik 'help' untuk daftar perintah.
    """
    print(f"\n{'='*60}")
    print(f"🤖 RAG Engine — Sesi Interaktif")
    print(f"   Model  : qwen2.5:9b via Ollama")
    print(f"   Top-K  : {top_k} | Top-N: {top_n}")
    if domain_filter:
        print(f"   Domain : {domain_filter}")
    if video_filter:
        print(f"   Video  : {video_filter}")
    print(f"   Perintah: 'exit'|'quit' keluar, 'stats' lihat DB, 'help' bantuan")
    print(f"{'='*60}\n")

    # Cek Ollama sekali di awal
    if not check_ollama(verbose=True):
        print("❌ Sesi tidak bisa dimulai — Ollama tidak tersedia.\n")
        return

    while True:
        try:
            query = input("❓ Query: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Sesi selesai.")
            break

        if not query:
            continue

        # Perintah khusus
        if query.lower() in ("exit", "quit", "keluar"):
            print("\n👋 Sesi selesai.\n")
            break

        if query.lower() == "stats":
            show_stats()
            continue

        if query.lower() == "help":
            print("""
Perintah tersedia:
  exit / quit / keluar  — keluar dari sesi
  stats                 — tampilkan statistik vector store
  help                  — tampilkan bantuan ini
  <pertanyaan>          — tanya apa saja tentang isi video

Tips:
  - Pertanyaan spesifik → hasil lebih akurat
  - Sebutkan topik/domain dalam pertanyaan jika perlu
  - Warna confidence: 🟢 tinggi | 🟡 sedang | 🔴 rendah
""")
            continue

        # RAG query
        result = rag_query(
            query=query,
            top_k=top_k,
            top_n=top_n,
            domain_filter=domain_filter,
            video_filter=video_filter,
            temperature=temperature,
            verbose=False
        )
        print_result(result)


def batch_query(
    file_path: str,
    top_k: int = DEFAULT_TOP_K,
    top_n: int = DEFAULT_TOP_N,
    output_json: bool = False
):
    """
    Jalankan batch query dari file teks (satu query per baris).
    Berguna untuk evaluasi atau regression testing.

    Args:
        file_path:   path ke file query (satu query per baris, # untuk komentar)
        top_k:       jumlah chunk per query
        output_json: simpan hasil ke file JSON
    """
    queries_path = Path(file_path)
    if not queries_path.exists():
        print(f"❌ File tidak ditemukan: {file_path}")
        sys.exit(1)

    with open(queries_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    queries = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]

    if not queries:
        print("⚠️  Tidak ada query valid di file.\n")
        return

    print(f"\n📋 Batch mode: {len(queries)} query dari '{file_path}'\n")

    results = []
    for i, query in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] {query[:60]}...")
        result = rag_query(query=query, top_k=top_k, top_n=top_n, verbose=False)
        results.append(result)

        # Print ringkas
        conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴", "no_context": "⭕", "error": "❌"}
        icon = conf_icon.get(result["confidence"], "?")
        print(f"  {icon} {result['confidence']} | {result['duration_s']}s | {result['retrieved_chunks']} chunks\n")

    # Simpan hasil jika diminta
    if output_json:
        out_path = queries_path.with_suffix(".results.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"✅ Hasil disimpan ke: {out_path}")

    # Summary
    total     = len(results)
    high      = sum(1 for r in results if r["confidence"] == "high")
    medium    = sum(1 for r in results if r["confidence"] == "medium")
    low       = sum(1 for r in results if r["confidence"] == "low")
    no_ctx    = sum(1 for r in results if r["confidence"] == "no_context")
    avg_dur   = sum(r["duration_s"] for r in results) / total if total else 0

    print(f"\n{'='*50}")
    print(f"📊 SUMMARY BATCH")
    print(f"   Total query : {total}")
    print(f"   🟢 High     : {high} ({100*high//total}%)")
    print(f"   🟡 Medium   : {medium} ({100*medium//total}%)")
    print(f"   🔴 Low      : {low} ({100*low//total}%)")
    print(f"   ⭕ No ctx   : {no_ctx} ({100*no_ctx//total}%)")
    print(f"   ⏱️  Avg durasi: {avg_dur:.1f}s")
    print(f"{'='*50}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="CLI interaktif untuk RAG Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python query.py "Apa itu supervised learning?"
  python query.py "Cara training model" --domain teknologi
  python query.py --interactive
  python query.py --batch queries.txt --output-json
        """
    )

    parser.add_argument("query",          nargs="?",  default=None,
                        help="Pertanyaan tunggal (opsional jika pakai --interactive atau --batch)")
    parser.add_argument("--interactive",  action="store_true",
                        help="Mode sesi interaktif (REPL)")
    parser.add_argument("--batch",        default=None, metavar="FILE",
                        help="Batch mode: path ke file query (satu query per baris)")
    parser.add_argument("--top-k",        type=int, default=DEFAULT_TOP_K,
                        help=f"Chunk ke prompt LLM (default: {DEFAULT_TOP_K})")
    parser.add_argument("--top-n",        type=int, default=DEFAULT_TOP_N,
                        help=f"Kandidat dari ChromaDB (default: {DEFAULT_TOP_N})")
    parser.add_argument("--domain",       default=None,
                        help="Filter domain (contoh: teknologi, kesehatan)")
    parser.add_argument("--video",        default=None,
                        help="Filter ke satu video_id tertentu")
    parser.add_argument("--temp",         type=float, default=0.2,
                        help="Temperature model (default: 0.2)")
    parser.add_argument("--verbose",      action="store_true",
                        help="Tampilkan progress detail pipeline")
    parser.add_argument("--json",         action="store_true",
                        help="Output sebagai JSON (untuk single query)")
    parser.add_argument("--output-json",  action="store_true",
                        help="Simpan hasil batch ke file .results.json")
    parser.add_argument("--stats",        action="store_true",
                        help="Tampilkan statistik vector store dan keluar")

    args = parser.parse_args()

    # Mode: stats only
    if args.stats:
        show_stats()
        sys.exit(0)

    # Mode: batch
    if args.batch:
        batch_query(
            file_path=args.batch,
            top_k=args.top_k,
            top_n=args.top_n,
            output_json=args.output_json
        )
        sys.exit(0)

    # Mode: interactive REPL
    if args.interactive or not args.query:
        interactive_session(
            top_k=args.top_k,
            top_n=args.top_n,
            domain_filter=args.domain,
            video_filter=args.video,
            temperature=args.temp
        )
        sys.exit(0)

    # Mode: single query
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

    # Exit code: 1 jika no_context atau error
    sys.exit(0 if result["confidence"] not in ("no_context", "error") else 1)

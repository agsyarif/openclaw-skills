"""
rerank.py
---------
Re-scoring chunk hasil retrieve menggunakan hybrid scoring:
  - Skor semantik dari ChromaDB (cosine similarity)
  - Skor leksikal dari keyword overlap (BM25-style sederhana)
  - Deduplication chunk yang sangat mirip satu sama lain

Tidak membutuhkan model tambahan — pure Python.

Usage (sebagai modul):
    from rerank import rerank
    top_chunks = rerank(chunks, query, top_k=4)
"""

import math
import re
from typing import Optional

from ollama_client import DEFAULT_TOP_K

# Bobot hybrid scoring
SEMANTIC_WEIGHT = 0.65   # bobot skor dari ChromaDB embedding
LEXICAL_WEIGHT  = 0.35   # bobot skor keyword overlap

# Threshold deduplication — chunk dengan overlap teks > ini dianggap duplikat
DEDUP_THRESHOLD = 0.75

# Stopwords sederhana Bahasa Indonesia + Inggris
STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan", "untuk",
    "adalah", "pada", "tidak", "dalam", "juga", "akan", "ada", "kita",
    "atau", "sudah", "bisa", "mereka", "saya", "anda", "kamu", "dia",
    "the", "a", "an", "is", "are", "was", "were", "of", "in", "to",
    "and", "or", "for", "with", "this", "that", "it", "as", "be",
    "by", "at", "from", "on", "not", "but", "have", "has", "had"
}


def tokenize(text: str) -> list[str]:
    """
    Tokenisasi sederhana: lowercase, hapus tanda baca, buang stopwords.
    """
    tokens = re.findall(r'\b\w+\b', text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def bm25_score(query_tokens: list[str], doc_tokens: list[str],
               k1: float = 1.5, b: float = 0.75,
               avg_doc_len: float = 100.0) -> float:
    """
    BM25 scoring sederhana untuk satu dokumen.

    Args:
        query_tokens:  token dari query
        doc_tokens:    token dari dokumen
        k1, b:         BM25 hyperparameter (nilai standar)
        avg_doc_len:   rata-rata panjang dokumen (estimasi)

    Returns:
        BM25 score (float, tidak dinormalisasi)
    """
    if not doc_tokens or not query_tokens:
        return 0.0

    doc_len  = len(doc_tokens)
    tf_map   = {}
    for token in doc_tokens:
        tf_map[token] = tf_map.get(token, 0) + 1

    score = 0.0
    for token in set(query_tokens):
        tf = tf_map.get(token, 0)
        if tf == 0:
            continue

        # IDF sederhana: log(1 + 1/df) — kita asumsikan df=1 karena tidak ada corpus stats
        idf = math.log(2.0)

        # TF dengan saturasi BM25
        numerator   = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * doc_len / avg_doc_len)
        score += idf * (numerator / denominator)

    return score


def normalize_scores(chunks: list[dict], field: str) -> list[dict]:
    """
    Normalisasi field skor ke range 0.0-1.0 (min-max scaling).
    Operasi in-place pada list yang diberikan.
    """
    values = [c[field] for c in chunks]
    min_v  = min(values)
    max_v  = max(values)

    if max_v == min_v:
        for c in chunks:
            c[field] = 1.0 if max_v > 0 else 0.0
    else:
        for c in chunks:
            c[field] = (c[field] - min_v) / (max_v - min_v)

    return chunks


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """
    Jaccard similarity antara dua teks (token-level).
    Digunakan untuk deduplication.

    Returns:
        float 0.0-1.0 (1.0 = identik)
    """
    tokens_a = set(tokenize(text_a))
    tokens_b = set(tokenize(text_b))

    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union        = tokens_a | tokens_b
    return len(intersection) / len(union)


def deduplicate(chunks: list[dict], threshold: float = DEDUP_THRESHOLD) -> list[dict]:
    """
    Hapus chunk yang sangat mirip satu sama lain.
    Prioritaskan chunk dengan hybrid_score lebih tinggi.

    Chunks diasumsikan sudah diurutkan by hybrid_score descending.
    """
    kept = []
    for candidate in chunks:
        is_duplicate = False
        for existing in kept:
            sim = jaccard_similarity(candidate["chunk"], existing["chunk"])
            if sim >= threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            kept.append(candidate)
    return kept


def rerank(
    chunks: list[dict],
    query: str,
    top_k: int = DEFAULT_TOP_K,
    dedup: bool = True
) -> list[dict]:
    """
    Re-rank chunks dengan hybrid scoring (semantik + leksikal) lalu ambil top-K.

    Args:
        chunks:  output dari retrieve.retrieve() — list of chunk dict
        query:   teks query original
        top_k:   jumlah chunk final yang dikembalikan
        dedup:   aktifkan deduplication (default: True)

    Returns:
        list of chunk dict (top_k terbaik), dengan field tambahan:
          - lexical_score:  skor BM25 dinormalisasi
          - hybrid_score:   skor gabungan semantik + leksikal
    """
    if not chunks:
        return []

    query_tokens = tokenize(query)

    # Hitung avg doc length untuk BM25
    all_doc_tokens = [tokenize(c["chunk"]) for c in chunks]
    avg_doc_len    = sum(len(t) for t in all_doc_tokens) / len(all_doc_tokens)

    # Hitung lexical score untuk setiap chunk
    for chunk, doc_tokens in zip(chunks, all_doc_tokens):
        chunk["lexical_score"] = bm25_score(query_tokens, doc_tokens, avg_doc_len=avg_doc_len)

    # Normalisasi lexical score ke 0-1
    if any(c["lexical_score"] > 0 for c in chunks):
        normalize_scores(chunks, "lexical_score")
    else:
        for c in chunks:
            c["lexical_score"] = 0.0

    # Hitung hybrid score
    for chunk in chunks:
        chunk["hybrid_score"] = round(
            SEMANTIC_WEIGHT * chunk["score"] +
            LEXICAL_WEIGHT  * chunk["lexical_score"],
            4
        )

    # Urutkan by hybrid_score descending
    chunks.sort(key=lambda c: c["hybrid_score"], reverse=True)

    # Deduplication sebelum cut top-K
    if dedup:
        chunks = deduplicate(chunks)

    return chunks[:top_k]


# ── Main (debug) ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Test rerank dengan data dummy.
    Untuk test real: gunakan query.py atau generate.py
    """
    dummy_chunks = [
        {
            "chunk": "Machine learning adalah cabang dari kecerdasan buatan yang memungkinkan komputer belajar dari data.",
            "score": 0.85,
            "video_id": "tutorial_ml", "video_title": "Pengantar ML",
            "block_id": "0", "chunk_index": "0",
            "start": 0.0, "end": 45.0,
            "topic": "Definisi Machine Learning",
            "summary": "Penjelasan dasar ML",
            "keywords": "machine learning, AI, data",
            "domain": "teknologi"
        },
        {
            "chunk": "Supervised learning menggunakan data berlabel untuk melatih model prediksi.",
            "score": 0.72,
            "video_id": "tutorial_ml", "video_title": "Pengantar ML",
            "block_id": "1", "chunk_index": "0",
            "start": 45.0, "end": 90.0,
            "topic": "Supervised Learning",
            "summary": "Penjelasan supervised learning",
            "keywords": "supervised learning, label, prediksi",
            "domain": "teknologi"
        },
        {
            "chunk": "Machine learning adalah cabang AI yang belajar dari data dan pengalaman.",
            "score": 0.80,
            "video_id": "tutorial_ml", "video_title": "Pengantar ML",
            "block_id": "0", "chunk_index": "1",
            "start": 0.0, "end": 45.0,
            "topic": "Definisi Machine Learning",
            "summary": "Penjelasan dasar ML",
            "keywords": "machine learning, AI, data",
            "domain": "teknologi"
        },
    ]

    query = "apa itu machine learning?"
    ranked = rerank(dummy_chunks, query, top_k=2)

    print(f"Query: '{query}'")
    print(f"Top {len(ranked)} setelah rerank:\n")
    for i, c in enumerate(ranked, 1):
        print(f"  [{i}] hybrid={c['hybrid_score']:.3f} | semantic={c['score']:.3f} | lexical={c['lexical_score']:.3f}")
        print(f"       {c['chunk'][:100]}...")
        print()

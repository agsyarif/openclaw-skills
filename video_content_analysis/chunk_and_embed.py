"""
chunk_and_embed.py
------------------
Potong teks menjadi chunk, embed, dan simpan ke ChromaDB untuk RAG.
Setiap video yang diproses akan di-upsert (aman dijalankan ulang).

Usage:
    python chunk_and_embed.py <path_ke_summary.json>

Membutuhkan:
    pip install chromadb
"""

import hashlib
import json
import sys
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

# --- Konfigurasi ---
VECTOR_STORE_PATH = "/workspaces/ml_processor/data/vector_store"
COLLECTION_NAME   = "video_knowledge"
CHUNK_SIZE        = 512   # karakter per chunk
CHUNK_OVERLAP     = 64    # overlap antar chunk untuk menjaga konteks
MIN_CHUNK_CHARS   = 30    # chunk lebih pendek dari ini diabaikan


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Potong teks menggunakan sliding window dengan overlap.

    Args:
        text:       teks yang akan dipotong
        chunk_size: ukuran maksimal chunk dalam karakter
        overlap:    jumlah karakter overlap antar chunk

    Returns:
        list of string chunks
    """
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    chunks = []
    start  = 0
    step   = chunk_size - overlap

    while start < len(text):
        end   = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if len(chunk) >= MIN_CHUNK_CHARS:
            chunks.append(chunk)
        start += step

    return chunks


def make_chunk_id(video_id: str, block_id: int, chunk_index: int) -> str:
    """Buat ID deterministik untuk setiap chunk (aman untuk upsert)."""
    raw = f"{video_id}_{block_id}_{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def embed_and_store(summary_path: str) -> int:
    """
    Baca summary.json, chunk teks, embed, dan upsert ke ChromaDB.

    Args:
        summary_path: path ke summary.json

    Returns:
        jumlah total chunk yang di-upsert
    """
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    video_id = Path(summary_path).parent.name
    overall  = data.get("overall", {})
    domain   = overall.get("domain", "general")
    title    = overall.get("title_suggestion", video_id)

    # Setup ChromaDB
    chroma_client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    ef = embedding_functions.DefaultEmbeddingFunction()  # all-MiniLM-L6-v2

    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )

    docs, ids, metas = [], [], []

    for block in data["blocks"]:
        analysis     = block.get("analysis", {})
        raw_text     = block["text"]
        summary_text = analysis.get("summary", "")
        topic        = analysis.get("topic", "")
        keywords     = ", ".join(analysis.get("keywords", []))

        chunks = chunk_text(raw_text)

        for i, chunk in enumerate(chunks):
            chunk_id = make_chunk_id(video_id, block["block_id"], i)

            docs.append(chunk)
            ids.append(chunk_id)
            metas.append({
                # Identitas
                "video_id":    video_id,
                "video_title": title,
                "block_id":    str(block["block_id"]),
                "chunk_index": str(i),
                # Waktu dalam video
                "start":       str(block["start"]),
                "end":         str(block["end"]),
                # Konteks semantik (berguna untuk retrieval)
                "topic":       topic,
                "summary":     summary_text,
                "keywords":    keywords,
                "domain":      domain,
            })

    if not docs:
        print("⚠️  Tidak ada chunk yang dihasilkan. Periksa summary.json.")
        return 0

    # Upsert dalam batch (aman untuk re-run)
    BATCH_SIZE = 100
    for i in range(0, len(docs), BATCH_SIZE):
        collection.upsert(
            documents=docs[i:i+BATCH_SIZE],
            ids=ids[i:i+BATCH_SIZE],
            metadatas=metas[i:i+BATCH_SIZE]
        )

    total = collection.count()
    print(f"✅ {len(docs)} chunk di-upsert ke collection '{COLLECTION_NAME}'")
    print(f"📊 Total chunk dalam collection: {total}")
    return len(docs)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python chunk_and_embed.py <summary.json>")
        sys.exit(1)

    embed_and_store(sys.argv[1])

"""
ollama_client.py
----------------
Shared interface ke Ollama dan ChromaDB.
Semua script rag_engine mengimport dari sini.

Konfigurasi terpusat — ubah di sini untuk semua script sekaligus.
"""

import json
import urllib.error
import urllib.request

import chromadb
from chromadb.utils import embedding_functions

# ── Konfigurasi — edit di sini ────────────────────────────────────────────────
OLLAMA_BASE_URL   = "http://localhost:11434"
OLLAMA_MODEL      = "qwen2.5:9b"
VECTOR_STORE_PATH = "/workspaces/ml_processor/data/vector_store"
COLLECTION_NAME   = "video_knowledge"

# Retrieval defaults
DEFAULT_TOP_N = 10   # jumlah kandidat dari ChromaDB sebelum rerank
DEFAULT_TOP_K = 4    # jumlah chunk final yang masuk ke prompt LLM


# ── Ollama ────────────────────────────────────────────────────────────────────

def ollama_chat(
    prompt: str,
    system: str = "",
    temperature: float = 0.2,
    model: str = None
) -> str:
    """
    Kirim chat completion ke Ollama.

    Args:
        prompt:      pesan user
        system:      system prompt (opsional)
        temperature: 0.0-1.0 (default 0.2 untuk RAG — sedikit kreatif tapi tetap akurat)
        model:       override model (default: OLLAMA_MODEL)

    Returns:
        teks respons dari model

    Raises:
        RuntimeError: jika Ollama tidak bisa dihubungi
    """
    target_model = model or OLLAMA_MODEL

    payload: dict = {
        "model":   target_model,
        "stream":  False,
        "options": {"temperature": temperature},
        "messages": []
    }

    if system:
        payload["messages"].append({"role": "system", "content": system})
    payload["messages"].append({"role": "user", "content": prompt})

    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["message"]["content"].strip()
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Tidak bisa terhubung ke Ollama di {OLLAMA_BASE_URL}.\n"
            f"Jalankan: ollama serve\n"
            f"Detail  : {e}"
        )


def check_ollama(verbose: bool = True) -> bool:
    """
    Cek apakah Ollama berjalan dan model tersedia.

    Returns:
        True jika OK, False jika tidak
    """
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data   = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]

            model_base = OLLAMA_MODEL.split(":")[0]
            found = any(model_base in m for m in models)

            if not found and verbose:
                print(f"⚠️  Model '{OLLAMA_MODEL}' tidak ditemukan.")
                print(f"   Jalankan: ollama pull {OLLAMA_MODEL}")
                print(f"   Model tersedia: {', '.join(models) or '(tidak ada)'}")
            return found
    except Exception as e:
        if verbose:
            print(f"⚠️  Ollama tidak berjalan di {OLLAMA_BASE_URL}: {e}")
            print(f"   Jalankan: ollama serve")
        return False


# ── ChromaDB ──────────────────────────────────────────────────────────────────

def get_collection(create_if_missing: bool = False):
    """
    Ambil ChromaDB collection video_knowledge.

    Args:
        create_if_missing: jika True, buat collection baru jika belum ada.
                           Untuk rag_engine: selalu False (read-only).

    Returns:
        chromadb.Collection

    Raises:
        ValueError: jika collection tidak ditemukan dan create_if_missing=False
    """
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    ef     = embedding_functions.DefaultEmbeddingFunction()  # all-MiniLM-L6-v2

    existing = [c.name for c in client.list_collections()]

    if COLLECTION_NAME not in existing:
        if create_if_missing:
            return client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"}
            )
        raise ValueError(
            f"Collection '{COLLECTION_NAME}' tidak ditemukan di vector store.\n"
            f"Jalankan video_content_analysis/pipeline.py untuk memproses video terlebih dahulu."
        )

    return client.get_collection(name=COLLECTION_NAME, embedding_function=ef)


def collection_stats() -> dict:
    """
    Statistik collection: jumlah chunk, daftar video, daftar domain.

    Returns:
        dict berisi count, videos, domains
    """
    try:
        col = get_collection()
        total = col.count()

        if total == 0:
            return {"count": 0, "videos": [], "domains": []}

        # Ambil semua metadata (hanya metadata, bukan dokumen)
        result  = col.get(include=["metadatas"])
        metas   = result["metadatas"]

        videos  = sorted(set(m.get("video_id", "unknown") for m in metas))
        domains = sorted(set(m.get("domain", "unknown") for m in metas))

        return {
            "count":   total,
            "videos":  videos,
            "domains": domains
        }
    except ValueError:
        return {"count": 0, "videos": [], "domains": [], "error": "collection_not_found"}

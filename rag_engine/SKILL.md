---
name: rag_engine
description: "Gunakan skill ini ketika ml_processor agent perlu menjawab pertanyaan berbasis konten video yang sudah diproses, melakukan retrieval dokumen dari vector store, atau menghasilkan jawaban menggunakan model lokal (Ollama). Trigger: agent menerima pertanyaan tentang konten video, query pencarian knowledge base, atau permintaan generate teks berbasis konteks. Skill ini membaca dari ChromaDB vector store yang diisi oleh video_content_analysis."
version: "1.0.0"
author: "ml_processor"
compatibility: "OpenClaw Agent Runtime — ml_processor workspace"
dependencies:
  - python >= 3.10
  - chromadb (vector store, sama dengan yang dipakai video_content_analysis)
  - ollama berjalan di localhost:11434
  - model di-pull: qwen2.5:9b (ollama pull qwen2.5:9b)
  - TIDAK membutuhkan API key apapun
reads_from:
  - /workspaces/ml_processor/data/vector_store/   ← ChromaDB dari video_content_analysis
---

# Skill: rag_engine

## Tujuan Skill

Skill ini menjadi **lapisan retrieval dan generasi** di atas knowledge base yang dibangun oleh `video_content_analysis`. Alur kerjanya:

```
Query dari agent/user
      ↓
retrieve.py     → cari chunk relevan dari ChromaDB
      ↓
rerank.py       → skor ulang & filter chunk terbaik
      ↓
generate.py     → kirim konteks + query ke Ollama → jawaban
      ↓
Respons terstruktur
```

Skill ini **tidak** menulis ke vector store — hanya membaca. Penulisan dilakukan oleh `video_content_analysis/chunk_and_embed.py`.

---

## Struktur File Skill

```
/workspaces/ml_processor/skills/rag_engine/
├── SKILL.md              ← File ini
├── ollama_client.py      ← Shared client Ollama (chat + embed)
├── retrieve.py           ← Query ChromaDB → chunks relevan
├── rerank.py             ← Re-scoring & deduplication chunks
├── generate.py           ← RAG: retrieve + rerank + generate
├── inspect.py            ← Debug: lihat isi vector store
└── query.py              ← CLI interaktif untuk query manual
```

---

## Alur Detail

### Retrieval Strategy

RAG engine ini menggunakan **hybrid retrieval** dua tahap:

```
[1] Semantic Search (ChromaDB cosine similarity)
        ↓
    Top-N chunks (default N=10)
        ↓
[2] Re-ranking (BM25-style keyword overlap scoring)
        ↓
    Top-K chunks (default K=4)
        ↓
[3] Context assembly → Ollama generate
```

Dua tahap ini penting karena embedding saja kadang melewatkan chunk yang secara leksikal sangat relevan (keyword exact match), sedangkan keyword search saja tidak menangkap makna semantik.

### Format Output Generate

```json
{
  "query": "pertanyaan original",
  "answer": "jawaban dari model",
  "sources": [
    {
      "video_id": "tutorial_ml",
      "video_title": "Pengantar Machine Learning",
      "start": 120.5,
      "end": 180.2,
      "topic": "Supervised Learning",
      "chunk": "teks chunk yang dipakai...",
      "score": 0.87
    }
  ],
  "model": "qwen2.5:9b",
  "retrieved_chunks": 4
}
```

---

## Panduan Per Script

### ollama_client.py — Shared Ollama Interface

Dipakai oleh semua script lain. Satu tempat untuk konfigurasi model dan URL.

### retrieve.py — ChromaDB Query

Query vector store dengan filter opsional (domain, video_id).
Mengembalikan chunks beserta metadata dan similarity score.

### rerank.py — Re-scoring

Skor ulang chunks berdasarkan keyword overlap dengan query.
Gabungkan skor semantik + leksikal, ambil top-K.

### generate.py — RAG Orchestrator

Entry point utama. Memanggil retrieve → rerank → prompt assembly → Ollama generate.

### inspect.py — Debug & Monitoring

Lihat statistik collection, list video yang sudah diindeks, preview chunks.

### query.py — CLI Interaktif

Interface command-line untuk query manual. Berguna untuk testing dan debugging.

---

## Konfigurasi

Semua konfigurasi ada di `ollama_client.py`:

```python
OLLAMA_BASE_URL  = "http://localhost:11434"
OLLAMA_MODEL     = "qwen2.5:9b"
VECTOR_STORE_PATH = "/workspaces/ml_processor/data/vector_store"
COLLECTION_NAME  = "video_knowledge"
```

Untuk ganti model atau URL Ollama, cukup edit di satu tempat.

---

## Cara Pakai

### 1. Dari Python (dipanggil agent lain)

```python
from generate import rag_query

result = rag_query(
    query="Apa itu supervised learning?",
    top_k=4,
    domain_filter=None   # atau "teknologi" untuk filter domain spesifik
)

print(result["answer"])
print(result["sources"])
```

### 2. Dari CLI (manual / testing)

```bash
# Query tunggal
python query.py "Apa itu supervised learning?"

# Query dengan filter domain
python query.py "Cara membuat model klasifikasi" --domain teknologi

# Query dengan lebih banyak konteks
python query.py "Jelaskan proses training model" --top-k 6

# Lihat isi vector store
python inspect.py

# Lihat chunks dari video tertentu
python inspect.py --video tutorial_ml
```

---

## Rules (untuk SOUL.md ml_processor)

```markdown
## Rules: rag_engine

1. rag_engine hanya MEMBACA dari vector store — tidak pernah menulis atau menghapus.
2. Jika vector store kosong atau collection tidak ada, kembalikan pesan informatif, jangan crash.
3. Selalu sertakan 'sources' dalam output — agent lain perlu tahu dari mana jawaban berasal.
4. Jika confidence score semua chunks < 0.3, tandai jawaban sebagai "low_confidence".
5. Gunakan domain_filter jika query jelas merujuk domain tertentu untuk hasil lebih presisi.
6. Jangan pernah membuat jawaban tanpa konteks — jika tidak ada chunk relevan, katakan tidak tahu.
7. top_k default = 4. Naikkan ke 6-8 hanya untuk pertanyaan yang sangat luas/kompleks.
```

---

## Troubleshooting

| Error | Penyebab | Solusi |
|---|---|---|
| `Collection 'video_knowledge' not found` | Belum ada video yang diproses | Jalankan `video_content_analysis/pipeline.py` dulu |
| `Ollama connection refused` | Ollama tidak berjalan | `ollama serve` |
| `Model not found` | Model belum di-pull | `ollama pull qwen2.5:9b` |
| Jawaban tidak relevan | Chunk yang di-retrieve kurang tepat | Coba naikkan `top_n` di retrieve atau perluas query |
| `chromadb.errors.InvalidDimensionException` | Embedding model berubah | Hapus vector store dan re-embed semua video |

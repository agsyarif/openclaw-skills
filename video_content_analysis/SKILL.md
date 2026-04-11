---
name: video_content_analysis
description: "Gunakan skill ini ketika ml_processor agent menerima file video atau URL video dan perlu mengekstrak isi, mentranskripsikan audio, mensegmentasi konten, dan menghasilkan summary terstruktur sebagai text. Output akhir adalah file .jsonl siap pakai untuk RAG engine atau pipeline model_training. Trigger: ada file video di /workspaces/ml_processor/data/raw/, atau agent menerima perintah 'analisis video', 'proses video', 'ekstrak konten video'."
version: "1.0.0"
author: "ml_processor"
compatibility: "OpenClaw Agent Runtime — ml_processor workspace"
dependencies:
  - ffmpeg >= 4.4
  - openai-whisper (openai/whisper) atau faster-whisper
  - python >= 3.10
  - anthropic sdk (untuk summarization via Claude API)
  - chromadb (untuk output ke RAG vector store)
output_destinations:
  - /workspaces/ml_processor/data/processed/      ← transcript & chunks mentah
  - /workspaces/ml_processor/data/training_sets/  ← JSONL siap training
  - /workspaces/ml_processor/data/vector_store/   ← embedding untuk RAG
---

# Skill: video_content_analysis

## Tujuan Skill

Skill ini mengubah file video menjadi pengetahuan terstruktur yang dapat dikonsumsi oleh:
1. **RAG Engine** — untuk retrieval langsung tanpa training ulang
2. **model_training skill** — sebagai dataset fine-tuning LLM

Skill ini **tidak** melakukan training. Ia hanya memproduksi teks dan embedding.

---

## Struktur File Skill

```
/workspaces/ml_processor/skills/video_content_analysis/
├── SKILL.md                  ← File ini
├── extract_audio.py          ← Ekstrak audio dari video
├── transcribe.py             ← Transkripsi audio → teks (Whisper)
├── segment_and_clean.py      ← Segmentasi + normalisasi teks
├── summarize.py              ← Summarisasi per segmen via Claude API
├── chunk_and_embed.py        ← Chunking + embedding → vector store
├── build_training_jsonl.py   ← Konversi ke format JSONL untuk training
└── pipeline.py               ← Orchestrator: jalankan semua step sekaligus
```

---

## Alur Kerja (Pipeline)

```
[Video Input]
      │
      ▼
[1] extract_audio.py
      │  Output: /data/processed/{video_id}/audio.wav
      ▼
[2] transcribe.py
      │  Output: /data/processed/{video_id}/transcript_raw.json
      │          (per-segment dengan timestamps)
      ▼
[3] segment_and_clean.py
      │  Output: /data/processed/{video_id}/transcript_clean.json
      │          (teks bersih, dikelompokkan per topik/jeda)
      ▼
[4] summarize.py
      │  Output: /data/processed/{video_id}/summary.json
      │          (ringkasan per segmen + ringkasan keseluruhan)
      ▼
      ├──→ [5a] chunk_and_embed.py  → /data/vector_store/  (untuk RAG)
      │
      └──→ [5b] build_training_jsonl.py → /data/training_sets/  (untuk fine-tune)
```

Jalankan semuanya sekaligus via `pipeline.py`, atau step-by-step jika debugging.

---

## Panduan Per Script

### [1] extract_audio.py

**Tujuan:** Ekstrak audio dari video dalam format WAV mono 16kHz (optimal untuk Whisper).

```python
# extract_audio.py
import subprocess
import os
from pathlib import Path

def extract_audio(video_path: str, output_dir: str) -> str:
    """
    Ekstrak audio dari video menjadi WAV mono 16kHz.

    Args:
        video_path: path ke file video (mp4, mkv, avi, webm, dll)
        output_dir: direktori output

    Returns:
        path ke file audio WAV yang dihasilkan
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_id = video_path.stem
    audio_path = output_dir / f"audio.wav"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",                    # hapus video stream
        "-acodec", "pcm_s16le",   # format WAV
        "-ar", "16000",           # sample rate 16kHz (optimal Whisper)
        "-ac", "1",               # mono channel
        str(audio_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg gagal: {result.stderr}")

    print(f"✅ Audio diekstrak: {audio_path} ({os.path.getsize(audio_path) / 1e6:.1f} MB)")
    return str(audio_path)


if __name__ == "__main__":
    import sys
    video_path = sys.argv[1]
    video_id = Path(video_path).stem
    output_dir = f"/workspaces/ml_processor/data/processed/{video_id}"
    extract_audio(video_path, output_dir)
```

**Catatan penting:**
- Selalu gunakan `-y` agar ffmpeg tidak hang menunggu konfirmasi overwrite
- 16kHz mono adalah standar Whisper — jangan ubah
- Format WAV PCM tidak ter-compress, ukurannya besar tapi kompatibel sempurna

---

### [2] transcribe.py

**Tujuan:** Transkripsi audio menggunakan Whisper dengan output per-segmen beserta timestamp.

```python
# transcribe.py
import json
import time
from pathlib import Path
import whisper  # pip install openai-whisper

# Alternatif lebih cepat: from faster_whisper import WhisperModel

def transcribe_audio(audio_path: str, output_dir: str,
                     model_size: str = "medium",
                     language: str = None) -> str:
    """
    Transkripsi audio → JSON dengan segmen + timestamp.

    Args:
        audio_path:  path ke file WAV
        output_dir:  direktori output
        model_size:  "tiny" | "base" | "small" | "medium" | "large-v3"
                     Rekomendasi: "medium" untuk bahasa Indonesia
        language:    kode bahasa ISO 639-1, None = auto-detect
                     Contoh: "id" untuk Indonesia, "en" untuk Inggris

    Returns:
        path ke file transcript_raw.json
    """
    output_dir = Path(output_dir)
    output_path = output_dir / "transcript_raw.json"

    print(f"⏳ Memuat Whisper model '{model_size}'...")
    model = whisper.load_model(model_size)

    print(f"🎙️  Transkripsi dimulai: {audio_path}")
    start = time.time()

    result = model.transcribe(
        audio_path,
        language=language,          # None = auto-detect
        word_timestamps=True,       # aktifkan timestamp per kata
        verbose=False
    )

    elapsed = time.time() - start
    print(f"✅ Selesai dalam {elapsed:.1f}s — {len(result['segments'])} segmen ditemukan")

    # Simpan output terstruktur
    output = {
        "metadata": {
            "audio_path": str(audio_path),
            "model": model_size,
            "language_detected": result.get("language"),
            "duration_seconds": result["segments"][-1]["end"] if result["segments"] else 0,
            "transcribed_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        },
        "segments": [
            {
                "id": i,
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
                "words": seg.get("words", [])  # per-word timestamps
            }
            for i, seg in enumerate(result["segments"])
        ],
        "full_text": result["text"].strip()
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"📄 Transcript disimpan: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    import sys
    audio_path = sys.argv[1]
    output_dir = str(Path(audio_path).parent)
    transcribe_audio(audio_path, output_dir, language="id")
```

**Pilihan model Whisper:**

| Model | VRAM | Akurasi | Kecepatan | Rekomendasi |
|---|---|---|---|---|
| `tiny` | ~1GB | Rendah | Sangat cepat | Testing saja |
| `base` | ~1GB | Cukup | Cepat | Video pendek |
| `medium` | ~5GB | Bagus | Sedang | **Default** |
| `large-v3` | ~10GB | Terbaik | Lambat | GPU kuat |

**Untuk bahasa Indonesia:** minimal gunakan `medium`. Model `small` ke bawah sering salah pada aksen/dialek lokal.

---

### [3] segment_and_clean.py

**Tujuan:** Gabungkan segmen-segmen kecil Whisper menjadi paragraf bermakna, bersihkan noise teks.

```python
# segment_and_clean.py
import json
import re
from pathlib import Path

# Durasi minimal satu "blok topik" dalam detik
MIN_SEGMENT_DURATION = 30.0
# Durasi maksimal sebelum dipaksa potong
MAX_SEGMENT_DURATION = 120.0

def clean_text(text: str) -> str:
    """Bersihkan artefak transkripsi umum."""
    # Hapus filler words yang tidak bermakna
    fillers = r'\b(eh|um|uh|hmm|eee|mmm|ya ya ya)\b'
    text = re.sub(fillers, '', text, flags=re.IGNORECASE)
    # Rapikan spasi ganda
    text = re.sub(r'\s+', ' ', text)
    # Hapus tanda baca berulang
    text = re.sub(r'[\.]{3,}', '...', text)
    return text.strip()

def merge_segments(segments: list, min_dur: float, max_dur: float) -> list:
    """
    Gabungkan segmen pendek menjadi blok bermakna.
    Potong paksa jika blok sudah melebihi max_dur.
    """
    merged = []
    current = None

    for seg in segments:
        if current is None:
            current = {
                "start": seg["start"],
                "end": seg["end"],
                "texts": [seg["text"]]
            }
        else:
            current_duration = current["end"] - current["start"]
            seg_adds = seg["end"] - current["end"]

            if current_duration + seg_adds > max_dur:
                # Paksa potong, simpan current, mulai baru
                merged.append(current)
                current = {
                    "start": seg["start"],
                    "end": seg["end"],
                    "texts": [seg["text"]]
                }
            else:
                current["end"] = seg["end"]
                current["texts"].append(seg["text"])

            # Cek apakah sudah cukup panjang untuk di-commit
            if (current["end"] - current["start"]) >= min_dur:
                merged.append(current)
                current = None

    if current:
        merged.append(current)

    return merged

def process_transcript(transcript_path: str, output_dir: str) -> str:
    """
    Baca transcript_raw.json, merge & bersihkan, simpan transcript_clean.json.

    Returns:
        path ke transcript_clean.json
    """
    output_dir = Path(output_dir)
    output_path = output_dir / "transcript_clean.json"

    with open(transcript_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    segments = raw["segments"]
    merged = merge_segments(segments, MIN_SEGMENT_DURATION, MAX_SEGMENT_DURATION)

    clean_blocks = []
    for i, block in enumerate(merged):
        raw_text = " ".join(block["texts"])
        clean = clean_text(raw_text)

        if len(clean) < 20:  # skip blok terlalu pendek (noise)
            continue

        clean_blocks.append({
            "block_id": i,
            "start": round(block["start"], 2),
            "end": round(block["end"], 2),
            "duration": round(block["end"] - block["start"], 2),
            "text": clean,
            "char_count": len(clean)
        })

    output = {
        "metadata": raw["metadata"],
        "total_blocks": len(clean_blocks),
        "blocks": clean_blocks
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(clean_blocks)} blok bersih disimpan: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    import sys
    transcript_path = sys.argv[1]
    output_dir = str(Path(transcript_path).parent)
    process_transcript(transcript_path, output_dir)
```

---

### [4] summarize.py

**Tujuan:** Hasilkan ringkasan per blok dan ringkasan keseluruhan menggunakan Claude API.

```python
# summarize.py
import json
import time
from pathlib import Path
import anthropic

client = anthropic.Anthropic()  # Baca ANTHROPIC_API_KEY dari env

SYSTEM_PROMPT = """Kamu adalah asisten yang menganalisis konten video.
Tugasmu adalah merangkum setiap segmen dengan ringkas, akurat, dan terstruktur.
Selalu gunakan bahasa yang sama dengan teks input.
Jangan tambahkan opini atau informasi di luar teks yang diberikan."""

def summarize_block(block_text: str, block_id: int, context: str = "") -> dict:
    """
    Summarize satu blok teks dengan konteks opsional dari blok sebelumnya.

    Returns:
        dict berisi summary, keywords, dan topic
    """
    context_note = f"\nKonteks dari segmen sebelumnya: {context}" if context else ""

    prompt = f"""Analisis segmen teks berikut dari sebuah video:{context_note}

--- TEKS SEGMEN ---
{block_text}
---

Berikan output dalam format JSON:
{{
  "topic": "topik utama 1 kalimat",
  "summary": "ringkasan 2-4 kalimat",
  "keywords": ["kata", "kunci", "penting"],
  "questions_answered": ["pertanyaan apa yang dijawab segmen ini"]
}}

Hanya output JSON, tanpa teks lain."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences jika ada
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback jika model tidak mengikuti format
        result = {
            "topic": f"Segmen {block_id}",
            "summary": raw[:500],
            "keywords": [],
            "questions_answered": []
        }

    return result

def summarize_all(clean_transcript_path: str, output_dir: str) -> str:
    """
    Summarize semua blok + buat ringkasan keseluruhan video.

    Returns:
        path ke summary.json
    """
    output_dir = Path(output_dir)
    output_path = output_dir / "summary.json"

    with open(clean_transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    blocks = data["blocks"]
    summarized_blocks = []
    context_window = ""  # Kirimkan summary blok sebelumnya sebagai konteks

    print(f"📝 Summarizing {len(blocks)} blok...")

    for block in blocks:
        print(f"  → Blok {block['block_id']} ({block['start']}s - {block['end']}s)...")
        summary = summarize_block(block["text"], block["block_id"], context_window)

        enriched = {**block, "analysis": summary}
        summarized_blocks.append(enriched)

        # Update context untuk blok berikutnya (hanya ambil topic)
        context_window = summary.get("topic", "")
        time.sleep(0.3)  # Rate limiting dasar

    # Buat ringkasan keseluruhan video
    print("📋 Membuat ringkasan keseluruhan...")
    all_summaries = "\n".join(
        f"[{b['start']}s] {b['analysis']['summary']}"
        for b in summarized_blocks
    )

    overall_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"""Berikut adalah rangkuman dari setiap segmen video:

{all_summaries}

Buat ringkasan keseluruhan video dalam format JSON:
{{
  "title_suggestion": "judul video yang tepat",
  "overall_summary": "ringkasan keseluruhan 3-6 kalimat",
  "main_topics": ["topik utama 1", "topik utama 2"],
  "domain": "bidang/domain konten ini (misal: teknologi, kesehatan, keuangan)",
  "estimated_audience": "target audiens konten ini"
}}

Hanya output JSON, tanpa teks lain."""
        }]
    )

    overall_raw = overall_response.content[0].text.strip()
    overall_raw = overall_raw.replace("```json", "").replace("```", "").strip()

    try:
        overall = json.loads(overall_raw)
    except json.JSONDecodeError:
        overall = {"overall_summary": overall_raw}

    output = {
        "metadata": data["metadata"],
        "overall": overall,
        "blocks": summarized_blocks
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Summary disimpan: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    import sys
    clean_path = sys.argv[1]
    output_dir = str(Path(clean_path).parent)
    summarize_all(clean_path, output_dir)
```

---

### [5a] chunk_and_embed.py

**Tujuan:** Potong teks menjadi chunk 512 token, embed, simpan ke ChromaDB untuk RAG.

```python
# chunk_and_embed.py
import json
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions
import hashlib

# Config
VECTOR_STORE_PATH = "/workspaces/ml_processor/data/vector_store"
COLLECTION_NAME   = "video_knowledge"
CHUNK_SIZE        = 512    # karakter per chunk (bukan token, untuk simplisitas)
CHUNK_OVERLAP     = 50     # overlap antar chunk

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Potong teks dengan sliding window + overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    return [c.strip() for c in chunks if len(c.strip()) > 30]

def embed_and_store(summary_path: str) -> int:
    """
    Baca summary.json, chunk semua teks, embed, simpan ke ChromaDB.

    Returns:
        jumlah chunk yang disimpan
    """
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Setup ChromaDB
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    ef = embedding_functions.DefaultEmbeddingFunction()  # all-MiniLM-L6-v2
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )

    video_id = Path(summary_path).parent.name
    domain   = data["overall"].get("domain", "general")
    docs, ids, metas = [], [], []

    # Chunk dari teks setiap blok
    for block in data["blocks"]:
        raw_text    = block["text"]
        summary_txt = block["analysis"]["summary"]
        topic       = block["analysis"]["topic"]

        # Simpan chunk dari raw text + summary sebagai metadata
        for i, chunk in enumerate(chunk_text(raw_text, CHUNK_SIZE, CHUNK_OVERLAP)):
            chunk_id = hashlib.md5(f"{video_id}_{block['block_id']}_{i}".encode()).hexdigest()

            docs.append(chunk)
            ids.append(chunk_id)
            metas.append({
                "video_id":   video_id,
                "block_id":   block["block_id"],
                "start":      block["start"],
                "end":        block["end"],
                "topic":      topic,
                "summary":    summary_txt,
                "domain":     domain,
                "chunk_index": i
            })

    # Batch upsert ke ChromaDB
    if docs:
        collection.upsert(documents=docs, ids=ids, metadatas=metas)

    print(f"✅ {len(docs)} chunk disimpan ke vector store (collection: {COLLECTION_NAME})")
    return len(docs)


if __name__ == "__main__":
    import sys
    embed_and_store(sys.argv[1])
```

---

### [5b] build_training_jsonl.py

**Tujuan:** Konversi summary.json ke format JSONL untuk fine-tuning LLM.

```python
# build_training_jsonl.py
import json
from pathlib import Path
from datetime import datetime

TRAINING_SET_DIR = "/workspaces/ml_processor/data/training_sets"

def build_jsonl(summary_path: str) -> str:
    """
    Buat file JSONL dari summary.json untuk fine-tuning.

    Format output per baris:
    {"prompt": "...", "completion": "...", "meta": {...}}

    Returns:
        path ke file JSONL yang dihasilkan
    """
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    video_id = Path(summary_path).parent.name
    domain   = data["overall"].get("domain", "general")
    audience = data["overall"].get("estimated_audience", "umum")
    records  = []

    for block in data["blocks"]:
        text     = block["text"]
        analysis = block["analysis"]

        # Pasangan QA dari questions_answered
        for question in analysis.get("questions_answered", []):
            if len(question) > 10:
                records.append({
                    "prompt": question,
                    "completion": analysis["summary"],
                    "meta": {
                        "video_id": video_id,
                        "block_id": block["block_id"],
                        "domain": domain,
                        "type": "qa"
                    }
                })

        # Summarization task
        records.append({
            "prompt": f"Ringkas teks berikut:\n\n{text}",
            "completion": analysis["summary"],
            "meta": {
                "video_id": video_id,
                "block_id": block["block_id"],
                "domain": domain,
                "type": "summarization"
            }
        })

        # Topic extraction task
        records.append({
            "prompt": f"Apa topik utama dari teks ini?\n\n{text}",
            "completion": analysis["topic"],
            "meta": {
                "video_id": video_id,
                "block_id": block["block_id"],
                "domain": domain,
                "type": "topic_extraction"
            }
        })

    # Simpan per-video
    output_dir = Path(TRAINING_SET_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_jsonl_path = output_dir / f"{video_id}.jsonl"
    with open(video_jsonl_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Update combined_latest.jsonl (append, tidak replace)
    combined_path = output_dir / "combined_latest.jsonl"
    with open(combined_path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"✅ {len(records)} record ditulis ke {video_jsonl_path}")
    print(f"✅ combined_latest.jsonl diperbarui ({combined_path})")
    return str(video_jsonl_path)


if __name__ == "__main__":
    import sys
    build_jsonl(sys.argv[1])
```

---

### [6] pipeline.py — Orchestrator Utama

**Gunakan ini untuk menjalankan semua step sekaligus.**

```python
# pipeline.py
"""
Orchestrator untuk video_content_analysis pipeline.

Usage:
    python pipeline.py <path_ke_video> [--skip-embed] [--skip-jsonl]

Contoh:
    python pipeline.py /workspaces/ml_processor/data/raw/tutorial_ml.mp4
    python pipeline.py /workspaces/ml_processor/data/raw/tutorial_ml.mp4 --skip-embed
"""

import argparse
import json
import time
from pathlib import Path

from extract_audio        import extract_audio
from transcribe           import transcribe_audio
from segment_and_clean    import process_transcript
from summarize            import summarize_all
from chunk_and_embed      import embed_and_store
from build_training_jsonl import build_jsonl

BASE_PROCESSED = "/workspaces/ml_processor/data/processed"

def run_pipeline(video_path: str, skip_embed: bool = False, skip_jsonl: bool = False):
    video_path = Path(video_path)
    video_id   = video_path.stem
    output_dir = Path(BASE_PROCESSED) / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"🎬 Pipeline: {video_path.name}")
    print(f"📁 Output dir: {output_dir}")
    print(f"{'='*50}\n")

    run_log = {
        "video_id": video_id,
        "video_path": str(video_path),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "steps": {}
    }

    try:
        # Step 1: Extract Audio
        print("[ Step 1/5 ] Ekstrak audio...")
        t = time.time()
        audio_path = extract_audio(str(video_path), str(output_dir))
        run_log["steps"]["extract_audio"] = {"status": "ok", "duration": round(time.time()-t, 1)}

        # Step 2: Transcribe
        print("\n[ Step 2/5 ] Transkripsi audio...")
        t = time.time()
        transcript_path = transcribe_audio(audio_path, str(output_dir), language="id")
        run_log["steps"]["transcribe"] = {"status": "ok", "duration": round(time.time()-t, 1)}

        # Step 3: Segment & Clean
        print("\n[ Step 3/5 ] Segmentasi & pembersihan teks...")
        t = time.time()
        clean_path = process_transcript(transcript_path, str(output_dir))
        run_log["steps"]["segment_and_clean"] = {"status": "ok", "duration": round(time.time()-t, 1)}

        # Step 4: Summarize
        print("\n[ Step 4/5 ] Summarisasi via Claude API...")
        t = time.time()
        summary_path = summarize_all(clean_path, str(output_dir))
        run_log["steps"]["summarize"] = {"status": "ok", "duration": round(time.time()-t, 1)}

        # Step 5a: Embed ke vector store
        if not skip_embed:
            print("\n[ Step 5a/5 ] Embedding ke vector store...")
            t = time.time()
            n_chunks = embed_and_store(summary_path)
            run_log["steps"]["embed"] = {"status": "ok", "chunks": n_chunks, "duration": round(time.time()-t, 1)}
        else:
            print("\n[ Step 5a/5 ] SKIP embedding (--skip-embed)")

        # Step 5b: Build training JSONL
        if not skip_jsonl:
            print("\n[ Step 5b/5 ] Build training JSONL...")
            t = time.time()
            jsonl_path = build_jsonl(summary_path)
            run_log["steps"]["build_jsonl"] = {"status": "ok", "duration": round(time.time()-t, 1)}
        else:
            print("\n[ Step 5b/5 ] SKIP build JSONL (--skip-jsonl)")

        run_log["status"] = "success"

    except Exception as e:
        run_log["status"] = "failed"
        run_log["error"]  = str(e)
        print(f"\n❌ Pipeline gagal: {e}")
        raise

    finally:
        # Selalu simpan run log
        log_path = output_dir / "run_log.json"
        with open(log_path, "w") as f:
            json.dump(run_log, f, indent=2)
        print(f"\n📋 Run log: {log_path}")

    print(f"\n✅ Pipeline selesai untuk: {video_id}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video_path", help="Path ke file video")
    parser.add_argument("--skip-embed", action="store_true")
    parser.add_argument("--skip-jsonl", action="store_true")
    args = parser.parse_args()
    run_pipeline(args.video_path, args.skip_embed, args.skip_jsonl)
```

---

## Format Output

### transcript_raw.json
```json
{
  "metadata": { "language_detected": "id", "duration_seconds": 1823 },
  "segments": [
    { "id": 0, "start": 0.0, "end": 4.2, "text": "Halo semua, selamat datang..." }
  ],
  "full_text": "Halo semua, selamat datang..."
}
```

### summary.json
```json
{
  "overall": {
    "title_suggestion": "Pengantar Machine Learning untuk Pemula",
    "domain": "teknologi/machine learning",
    "overall_summary": "Video ini menjelaskan..."
  },
  "blocks": [
    {
      "block_id": 0, "start": 0.0, "end": 45.3,
      "text": "teks asli...",
      "analysis": {
        "topic": "Pengenalan konsep ML",
        "summary": "Pembicara menjelaskan...",
        "keywords": ["machine learning", "supervised"],
        "questions_answered": ["Apa itu machine learning?"]
      }
    }
  ]
}
```

### combined_latest.jsonl (per baris)
```jsonl
{"prompt": "Apa itu machine learning?", "completion": "Machine learning adalah...", "meta": {"video_id": "tutorial_ml", "type": "qa"}}
{"prompt": "Ringkas teks berikut:\n\nTeks asli...", "completion": "Ringkasan...", "meta": {"video_id": "tutorial_ml", "type": "summarization"}}
```

---

## Rules (untuk SOUL.md ml_processor)

```markdown
## Rules: video_content_analysis

1. SELALU simpan run_log.json di setiap folder output video — wajib untuk audit trail.
2. JANGAN hapus file di /data/processed/ — setiap video harus tetap bisa di-trace.
3. Jika transcribe gagal, BERHENTI — jangan lanjut ke step berikutnya.
4. combined_latest.jsonl hanya boleh di-APPEND, tidak pernah di-overwrite.
5. Gunakan video_id dari nama file (tanpa ekstensi) sebagai primary key di semua output.
6. Jika video sudah pernah diproses (cek run_log.json ada dan status=success), SKIP kecuali ada flag --force.
7. Language default = "id" (Indonesia). Ubah hanya jika video jelas berbahasa lain.
```

---

## Troubleshooting

| Error | Penyebab | Solusi |
|---|---|---|
| `ffmpeg: command not found` | ffmpeg belum terinstall | `apt install ffmpeg` |
| `CUDA out of memory` | Model Whisper terlalu besar | Turunkan ke `medium` atau `small` |
| `JSONDecodeError` di summarize.py | Claude API tidak return JSON | Sudah ada fallback, cek isi raw response di log |
| `collection already exists` | ChromaDB sudah ada collection | Normal — `get_or_create_collection` aman |
| `combined_latest.jsonl corrupt` | Append gagal di tengah jalan | Rebuild dari per-video JSONL: `cat /data/training_sets/*.jsonl > combined_latest.jsonl` |

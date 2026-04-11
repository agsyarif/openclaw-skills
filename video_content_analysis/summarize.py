"""
summarize.py
------------
Summarisasi per blok dan keseluruhan video menggunakan model lokal via Ollama.
Default model: qwen2.5:9b (tanpa API key, tanpa cloud)

Usage:
    python summarize.py <path_ke_transcript_clean.json>

Membutuhkan:
    - Ollama berjalan di localhost:11434
    - Model sudah di-pull: ollama pull qwen2.5:9b
"""

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ── Konfigurasi Ollama ────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "qwen2.5:9b"   # sesuaikan jika nama model berbeda di sistem Anda

SYSTEM_PROMPT = """Kamu adalah asisten analisis konten video yang akurat dan terstruktur.
Tugasmu adalah merangkum setiap segmen konten secara ringkas dan akurat.
Aturan:
- Selalu gunakan bahasa yang sama dengan teks input
- Jangan tambahkan opini, asumsi, atau informasi di luar teks
- Jika teks tidak jelas, tetap rangkum berdasarkan yang ada
- Output harus selalu valid JSON
- Jangan gunakan markdown atau teks tambahan di luar JSON"""


# ── Ollama Client ─────────────────────────────────────────────────────────────

def ollama_chat(prompt: str, system: str = "", temperature: float = 0.1) -> str:
    """
    Kirim request ke Ollama API (http://localhost:11434/api/chat).

    Args:
        prompt:      pesan user
        system:      system prompt
        temperature: 0.0-1.0, rendah = lebih deterministik (bagus untuk JSON output)

    Returns:
        teks respons dari model
    """
    payload = {
        "model":  OLLAMA_MODEL,
        "stream": False,
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
            f"Pastikan Ollama sudah berjalan: `ollama serve`\n"
            f"Detail: {e}"
        )


def check_ollama() -> bool:
    """Cek apakah Ollama berjalan dan model yang dibutuhkan tersedia."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data   = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]

            # Prefix match — karena Ollama menyimpan nama seperti "qwen2.5:9b" atau "qwen2.5:9b-instruct"
            model_base = OLLAMA_MODEL.split(":")[0]
            found = any(model_base in m for m in models)

            if not found:
                print(f"  Model tersedia: {', '.join(models) or '(tidak ada)'}")
                print(f"  Jalankan: ollama pull {OLLAMA_MODEL}")
                return False
            return True
    except Exception as e:
        print(f"  Detail error: {e}")
        print(f"  Jalankan: ollama serve")
        return False


def parse_json_response(raw: str, block_id: int, fallback: dict) -> dict:
    """
    Parse JSON dari respons model dengan beberapa strategi fallback.

    Qwen3 dengan extended thinking menghasilkan <think>...</think> di awal,
    kita strip dulu sebelum parse.
    """
    # 1. Hapus thinking block jika ada (Qwen3 extended thinking mode)
    if "<think>" in raw and "</think>" in raw:
        raw = raw[raw.index("</think>") + len("</think>"):].strip()

    # 2. Strip markdown fences
    raw = raw.replace("```json", "").replace("```", "").strip()

    # 3. Coba parse langsung
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 4. Ekstrak JSON object dari dalam teks (jika ada narasi di sekitar JSON)
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # 5. Fallback: struktur default dengan raw text sebagai summary
    print(f"     ⚠️  JSON parse gagal untuk blok {block_id}, menggunakan fallback")
    return {**fallback, "summary": raw[:400] if raw else fallback.get("summary", "")}


# ── Summarization Functions ───────────────────────────────────────────────────

def summarize_block(block_text: str, block_id: int, context: str = "") -> dict:
    """
    Summarize satu blok teks menggunakan Ollama (model lokal).

    Args:
        block_text: teks asli dari blok
        block_id:   nomor blok (untuk logging dan fallback label)
        context:    topik dari blok sebelumnya (untuk menjaga kontinuitas narasi)

    Returns:
        dict berisi: topic, summary, keywords, questions_answered
    """
    context_note = (
        f"\nKonteks dari segmen sebelumnya: {context}\n"
        if context else ""
    )

    prompt = f"""Analisis segmen teks berikut dari sebuah video:{context_note}

--- TEKS SEGMEN ---
{block_text}
---

Berikan output HANYA dalam format JSON berikut (tanpa teks lain, tanpa markdown):
{{
  "topic": "topik utama dalam 1 kalimat singkat",
  "summary": "ringkasan 2-4 kalimat yang menangkap poin utama",
  "keywords": ["kata", "kunci", "penting", "dari", "segmen"],
  "questions_answered": ["pertanyaan spesifik yang dijawab segmen ini"]
}}"""

    raw = ollama_chat(prompt, system=SYSTEM_PROMPT, temperature=0.1)

    return parse_json_response(raw, block_id, fallback={
        "topic":              f"Segmen {block_id}",
        "summary":            "",
        "keywords":           [],
        "questions_answered": []
    })


def summarize_overall(summarized_blocks: list) -> dict:
    """
    Buat ringkasan keseluruhan video dari kumpulan summary per blok.

    Args:
        summarized_blocks: list blok yang sudah memiliki field 'analysis'

    Returns:
        dict berisi: title_suggestion, overall_summary, main_topics,
                     domain, estimated_audience, content_type
    """
    all_summaries = "\n".join(
        f"[{b['start']}s - {b['end']}s] {b['analysis'].get('summary', '')}"
        for b in summarized_blocks
    )

    prompt = f"""Berikut adalah ringkasan dari setiap segmen video secara berurutan:

{all_summaries}

Berikan ringkasan keseluruhan video dalam format JSON berikut (tanpa teks lain):
{{
  "title_suggestion": "judul video yang deskriptif dan tepat",
  "overall_summary": "ringkasan keseluruhan isi video dalam 3-5 kalimat",
  "main_topics": ["topik utama 1", "topik utama 2", "topik utama 3"],
  "domain": "bidang/domain konten ini (contoh: teknologi, kesehatan, keuangan, pendidikan)",
  "estimated_audience": "deskripsi singkat target audiens konten ini",
  "content_type": "jenis konten (contoh: tutorial, presentasi, wawancara, kuliah, review)"
}}"""

    raw = ollama_chat(prompt, system=SYSTEM_PROMPT, temperature=0.1)

    return parse_json_response(raw, -1, fallback={
        "title_suggestion":   "Video Tanpa Judul",
        "overall_summary":    "",
        "main_topics":        [],
        "domain":             "umum",
        "estimated_audience": "umum",
        "content_type":       "tidak diketahui"
    })


def summarize_all(clean_transcript_path: str, output_dir: str) -> str:
    """
    Entry point utama: summarize semua blok + ringkasan keseluruhan video.

    Args:
        clean_transcript_path: path ke transcript_clean.json
        output_dir:            direktori untuk menyimpan output

    Returns:
        path ke summary.json
    """
    output_dir  = Path(output_dir)
    output_path = output_dir / "summary.json"

    # Cek Ollama tersedia sebelum memulai proses yang panjang
    print(f"🔍 Memeriksa Ollama ({OLLAMA_BASE_URL})...")
    if not check_ollama():
        raise RuntimeError(
            f"Ollama tidak tersedia atau model '{OLLAMA_MODEL}' belum di-pull. "
            f"Lihat pesan di atas untuk langkah selanjutnya."
        )
    print(f"✅ Ollama OK — model: {OLLAMA_MODEL}")

    with open(clean_transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    blocks = data["blocks"]
    print(f"📝 Summarizing {len(blocks)} blok...")

    summarized_blocks = []
    context_window    = ""  # Topik blok sebelumnya sebagai jembatan konteks

    for block in blocks:
        print(
            f"  → Blok {block['block_id']} "
            f"({block['start']}s - {block['end']}s)...",
            end=" ", flush=True
        )
        analysis      = summarize_block(block["text"], block["block_id"], context_window)
        topic_preview = analysis.get("topic", "")[:55]
        print(f"✓ [{topic_preview}]")

        summarized_blocks.append({**block, "analysis": analysis})

        # Carry forward topik — tanpa sleep karena model lokal tidak ada rate limit
        context_window = analysis.get("topic", "")

    # Ringkasan keseluruhan video
    print("\n📋 Membuat ringkasan keseluruhan video...")
    overall = summarize_overall(summarized_blocks)
    print(f"  Domain : {overall.get('domain', '-')}")
    print(f"  Judul  : {overall.get('title_suggestion', '-')}")
    print(f"  Tipe   : {overall.get('content_type', '-')}")

    # Susun output final
    output = {
        "metadata": {
            **data["metadata"],
            "summarized_with": OLLAMA_MODEL,
            "ollama_url":      OLLAMA_BASE_URL
        },
        "overall": overall,
        "blocks":  summarized_blocks
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Summary disimpan: {output_path}")
    return str(output_path)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python summarize.py <transcript_clean.json>")
        sys.exit(1)

    clean_path = sys.argv[1]
    output_dir = str(Path(clean_path).parent)

    summarize_all(clean_path, output_dir)
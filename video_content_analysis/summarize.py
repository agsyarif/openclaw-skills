"""
summarize.py
------------
Summarisasi per blok dan keseluruhan video menggunakan Claude API.
Output disimpan sebagai summary.json.

Usage:
    python summarize.py <path_ke_transcript_clean.json>

Membutuhkan:
    ANTHROPIC_API_KEY di environment variable
"""

import json
import sys
import time
from pathlib import Path

import anthropic

client = anthropic.Anthropic()  # Baca ANTHROPIC_API_KEY dari env

CLAUDE_MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """Kamu adalah asisten analisis konten video yang akurat dan terstruktur.
Tugasmu adalah merangkum setiap segmen konten secara ringkas dan akurat.
Aturan:
- Selalu gunakan bahasa yang sama dengan teks input
- Jangan tambahkan opini, asumsi, atau informasi di luar teks
- Jika teks tidak jelas, tetap rangkum berdasarkan yang ada
- Output harus selalu valid JSON"""


def summarize_block(block_text: str, block_id: int, context: str = "") -> dict:
    """
    Summarize satu blok teks.

    Args:
        block_text: teks asli dari blok
        block_id:   nomor blok (untuk logging)
        context:    topik dari blok sebelumnya (untuk kontinuitas)

    Returns:
        dict dengan topic, summary, keywords, questions_answered
    """
    context_note = (
        f"\nKonteks dari segmen sebelumnya: {context}\n"
        if context else ""
    )

    prompt = f"""Analisis segmen teks berikut dari sebuah video:{context_note}

--- TEKS SEGMEN ---
{block_text}
---

Berikan output HANYA dalam format JSON ini (tanpa teks lain, tanpa markdown):
{{
  "topic": "topik utama dalam 1 kalimat singkat",
  "summary": "ringkasan 2-4 kalimat yang menangkap poin utama",
  "keywords": ["kata", "kunci", "penting", "dari", "segmen"],
  "questions_answered": ["pertanyaan spesifik yang dijawab segmen ini"]
}}"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback graceful — jangan crash pipeline
        return {
            "topic":               f"Segmen {block_id}",
            "summary":             raw[:400],
            "keywords":            [],
            "questions_answered":  []
        }


def summarize_overall(summarized_blocks: list) -> dict:
    """
    Buat ringkasan keseluruhan video dari kumpulan summary per blok.

    Returns:
        dict dengan title_suggestion, overall_summary, main_topics, domain, estimated_audience
    """
    all_summaries = "\n".join(
        f"[{b['start']}s - {b['end']}s] {b['analysis']['summary']}"
        for b in summarized_blocks
    )

    prompt = f"""Berikut adalah ringkasan dari setiap segmen video secara berurutan:

{all_summaries}

Berikan ringkasan keseluruhan video dalam format JSON ini (tanpa teks lain):
{{
  "title_suggestion": "judul video yang deskriptif dan tepat",
  "overall_summary": "ringkasan keseluruhan isi video dalam 3-5 kalimat",
  "main_topics": ["topik utama 1", "topik utama 2", "topik utama 3"],
  "domain": "bidang/domain konten ini (contoh: teknologi, kesehatan, keuangan, pendidikan)",
  "estimated_audience": "deskripsi singkat target audiens konten ini",
  "content_type": "jenis konten (contoh: tutorial, presentasi, wawancara, kuliah, review)"
}}"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "title_suggestion":   "Video Tanpa Judul",
            "overall_summary":    raw[:600],
            "main_topics":        [],
            "domain":             "umum",
            "estimated_audience": "umum",
            "content_type":       "tidak diketahui"
        }


def summarize_all(clean_transcript_path: str, output_dir: str) -> str:
    """
    Entry point utama: summarize semua blok + keseluruhan video.

    Args:
        clean_transcript_path: path ke transcript_clean.json
        output_dir:            direktori untuk menyimpan output

    Returns:
        path ke summary.json
    """
    output_dir  = Path(output_dir)
    output_path = output_dir / "summary.json"

    with open(clean_transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    blocks = data["blocks"]
    print(f"📝 Summarizing {len(blocks)} blok via Claude API...")

    summarized_blocks = []
    context_window    = ""  # Topik dari blok sebelumnya sebagai konteks

    for block in blocks:
        print(f"  → Blok {block['block_id']} ({block['start']}s - {block['end']}s)...", end=" ")
        analysis = summarize_block(block["text"], block["block_id"], context_window)
        print(f"✓ [{analysis['topic'][:50]}...]")

        enriched_block = {**block, "analysis": analysis}
        summarized_blocks.append(enriched_block)

        # Carry forward topik untuk kontinuitas
        context_window = analysis.get("topic", "")

        # Rate limiting dasar — hindari throttling API
        time.sleep(0.4)

    # Ringkasan keseluruhan
    print("\n📋 Membuat ringkasan keseluruhan video...")
    overall = summarize_overall(summarized_blocks)
    print(f"  Domain: {overall.get('domain', '-')}")
    print(f"  Judul:  {overall.get('title_suggestion', '-')}")

    # Susun output final
    output = {
        "metadata": data["metadata"],
        "overall":  overall,
        "blocks":   summarized_blocks
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Summary disimpan: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python summarize.py <transcript_clean.json>")
        sys.exit(1)

    clean_path = sys.argv[1]
    output_dir = str(Path(clean_path).parent)

    summarize_all(clean_path, output_dir)

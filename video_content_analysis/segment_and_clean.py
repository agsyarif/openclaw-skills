"""
segment_and_clean.py
--------------------
Gabungkan segmen-segmen pendek dari Whisper menjadi blok bermakna,
lalu bersihkan noise/filler dari teks transkripsi.

Usage:
    python segment_and_clean.py <path_ke_transcript_raw.json>
"""

import json
import re
import sys
from pathlib import Path

# --- Konfigurasi segmentasi ---
MIN_SEGMENT_DURATION = 30.0   # detik minimal per blok
MAX_SEGMENT_DURATION = 120.0  # detik maksimal sebelum dipaksa potong
MIN_CHAR_LENGTH      = 20     # blok dengan teks kurang dari ini akan dibuang (noise)

# Filler words umum (Indonesia + English)
FILLER_PATTERN = re.compile(
    r'\b(eh|um|uh|hmm|eee|mmm|ya ya ya|nah|iya iya|gitu|'
    r'kayak gitu|kan|tuh|deh|dong|sih|loh|nih)\b',
    flags=re.IGNORECASE
)


def clean_text(text: str) -> str:
    """
    Bersihkan artefak transkripsi umum.
    - Hapus filler words
    - Rapikan spasi ganda
    - Normalisasi tanda baca berulang
    """
    text = FILLER_PATTERN.sub('', text)
    text = re.sub(r'\s+', ' ', text)           # spasi ganda
    text = re.sub(r'[\.]{3,}', '...', text)   # elipsis berlebihan
    text = re.sub(r'\s([,\.\!\?])', r'\1', text)  # spasi sebelum tanda baca
    return text.strip()


def merge_segments(segments: list, min_dur: float, max_dur: float) -> list:
    """
    Gabungkan segmen Whisper yang pendek menjadi blok bermakna.

    Logika:
    - Terus gabungkan segmen selama durasi < min_dur
    - Potong paksa jika durasi akan melebihi max_dur
    - Commit blok jika sudah >= min_dur
    """
    if not segments:
        return []

    merged = []
    current = {
        "start": segments[0]["start"],
        "end":   segments[0]["end"],
        "texts": [segments[0]["text"]]
    }

    for seg in segments[1:]:
        current_dur = current["end"] - current["start"]
        added_dur   = seg["end"] - current["end"]

        if current_dur + added_dur > max_dur:
            # Paksa potong: simpan current, mulai blok baru
            merged.append(current)
            current = {
                "start": seg["start"],
                "end":   seg["end"],
                "texts": [seg["text"]]
            }
        else:
            # Lanjut akumulasi
            current["end"] = seg["end"]
            current["texts"].append(seg["text"])

            # Commit jika sudah cukup panjang
            if (current["end"] - current["start"]) >= min_dur:
                merged.append(current)
                current = None
                break  # lanjut ke next iteration

    # Tangani sisa current
    if current is not None:
        merged.append(current)

    # Proses sisa segments jika ada yang belum diproses
    # (karena break di atas)
    last_end = merged[-1]["end"] if merged else 0
    remaining = [s for s in segments if s["start"] >= last_end]

    if remaining and remaining != segments:
        merged.extend(merge_segments(remaining, min_dur, max_dur))

    return merged


def process_transcript(transcript_path: str, output_dir: str) -> str:
    """
    Baca transcript_raw.json, merge & bersihkan segmen, simpan transcript_clean.json.

    Args:
        transcript_path: path ke transcript_raw.json
        output_dir:      direktori untuk menyimpan output

    Returns:
        path ke transcript_clean.json
    """
    output_dir  = Path(output_dir)
    output_path = output_dir / "transcript_clean.json"

    with open(transcript_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    segments = raw["segments"]
    print(f"📊 Input: {len(segments)} segmen Whisper mentah")

    merged = merge_segments(segments, MIN_SEGMENT_DURATION, MAX_SEGMENT_DURATION)
    print(f"🔀 Hasil merge: {len(merged)} blok")

    # Bersihkan dan filter
    clean_blocks = []
    skipped      = 0

    for i, block in enumerate(merged):
        raw_text = " ".join(block["texts"])
        clean    = clean_text(raw_text)

        if len(clean) < MIN_CHAR_LENGTH:
            skipped += 1
            continue

        clean_blocks.append({
            "block_id":   i,
            "start":      round(block["start"], 2),
            "end":        round(block["end"], 2),
            "duration":   round(block["end"] - block["start"], 2),
            "text":       clean,
            "char_count": len(clean),
            "word_count": len(clean.split())
        })

    if skipped > 0:
        print(f"🗑️  {skipped} blok dibuang (terlalu pendek/noise)")

    output = {
        "metadata":     raw["metadata"],
        "total_blocks": len(clean_blocks),
        "blocks":       clean_blocks
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(clean_blocks)} blok bersih disimpan: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python segment_and_clean.py <transcript_raw.json>")
        sys.exit(1)

    transcript_path = sys.argv[1]
    output_dir      = str(Path(transcript_path).parent)

    process_transcript(transcript_path, output_dir)

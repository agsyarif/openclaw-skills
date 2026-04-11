"""
transcribe.py
-------------
Transkripsi audio menggunakan OpenAI Whisper.
Output berupa JSON dengan segmen per timestamp.

Usage:
    python transcribe.py <path_ke_audio.wav> [model_size] [language]

Contoh:
    python transcribe.py /data/processed/tutorial/audio.wav medium id
"""

import json
import sys
import time
from pathlib import Path

import whisper  # pip install openai-whisper

# Untuk GPU yang terbatas, alternatif lebih cepat:
# from faster_whisper import WhisperModel  # pip install faster-whisper


def transcribe_audio(
    audio_path: str,
    output_dir: str,
    model_size: str = "medium",
    language: str = None
) -> str:
    """
    Transkripsi audio → JSON terstruktur dengan per-segmen timestamp.

    Args:
        audio_path:  path ke file WAV
        output_dir:  direktori untuk menyimpan output
        model_size:  "tiny" | "base" | "small" | "medium" | "large-v3"
                     Default "medium" — minimal untuk bahasa Indonesia
        language:    kode ISO 639-1, None = auto-detect
                     "id" = Indonesia, "en" = Inggris

    Returns:
        path ke transcript_raw.json
    """
    output_dir  = Path(output_dir)
    output_path = output_dir / "transcript_raw.json"

    print(f"⏳ Memuat Whisper model '{model_size}'...")
    model = whisper.load_model(model_size)

    print(f"🎙️  Transkripsi dimulai: {Path(audio_path).name}")
    start_time = time.time()

    result = model.transcribe(
        audio_path,
        language=language,       # None = auto-detect
        word_timestamps=True,    # aktifkan timestamp per kata
        verbose=False
    )

    elapsed = time.time() - start_time
    n_segments = len(result["segments"])
    print(f"✅ Selesai dalam {elapsed:.1f}s — {n_segments} segmen ditemukan")

    # Bentuk output terstruktur
    output = {
        "metadata": {
            "audio_path":        str(audio_path),
            "model":             model_size,
            "language_detected": result.get("language"),
            "duration_seconds":  result["segments"][-1]["end"] if result["segments"] else 0,
            "total_segments":    n_segments,
            "transcribed_at":    time.strftime("%Y-%m-%dT%H:%M:%S")
        },
        "segments": [
            {
                "id":    i,
                "start": round(seg["start"], 3),
                "end":   round(seg["end"], 3),
                "text":  seg["text"].strip(),
                "words": [
                    {
                        "word":  w["word"],
                        "start": round(w["start"], 3),
                        "end":   round(w["end"], 3)
                    }
                    for w in seg.get("words", [])
                ]
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
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <audio.wav> [model_size] [language]")
        sys.exit(1)

    audio_path  = sys.argv[1]
    model_size  = sys.argv[2] if len(sys.argv) > 2 else "medium"
    language    = sys.argv[3] if len(sys.argv) > 3 else "id"
    output_dir  = str(Path(audio_path).parent)

    transcribe_audio(audio_path, output_dir, model_size=model_size, language=language)

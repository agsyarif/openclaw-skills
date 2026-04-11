"""
extract_audio.py
----------------
Ekstrak audio dari video menjadi WAV mono 16kHz.
Format ini optimal untuk Whisper ASR.

Usage:
    python extract_audio.py <path_ke_video>
"""

import os
import subprocess
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

    audio_path = output_dir / "audio.wav"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",                  # hapus video stream
        "-acodec", "pcm_s16le", # format WAV uncompressed
        "-ar", "16000",         # sample rate 16kHz (standar Whisper)
        "-ac", "1",             # mono channel
        str(audio_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg gagal untuk '{video_path.name}':\n{result.stderr}"
        )

    size_mb = os.path.getsize(audio_path) / 1e6
    print(f"✅ Audio diekstrak: {audio_path} ({size_mb:.1f} MB)")
    return str(audio_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extract_audio.py <path_ke_video>")
        sys.exit(1)

    video_path = sys.argv[1]
    video_id   = Path(video_path).stem
    output_dir = f"/workspaces/ml_processor/data/processed/{video_id}"

    extract_audio(video_path, output_dir)

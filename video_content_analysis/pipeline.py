"""
pipeline.py
-----------
Orchestrator utama untuk video_content_analysis skill.
Jalankan semua step secara berurutan dengan logging dan error handling.

Usage:
    python pipeline.py <path_ke_video> [options]

Options:
    --skip-embed    Lewati step embedding ke vector store
    --skip-jsonl    Lewati step build training JSONL
    --force         Proses ulang meski sudah pernah diproses sebelumnya
    --model         Whisper model size: tiny|base|small|medium|large-v3 (default: medium)
    --language      Kode bahasa ISO 639-1 (default: id)

Contoh:
    python pipeline.py /workspaces/ml_processor/data/raw/tutorial_ml.mp4
    python pipeline.py /workspaces/ml_processor/data/raw/tutorial_ml.mp4 --model large-v3
    python pipeline.py /workspaces/ml_processor/data/raw/tutorial_ml.mp4 --skip-embed --force
"""

import argparse
import json
import sys
import time
from pathlib import Path

# ── Import semua step skill ──────────────────────────────────────────────────
from extract_audio        import extract_audio
from transcribe           import transcribe_audio
from segment_and_clean    import process_transcript
from summarize            import summarize_all
from chunk_and_embed      import embed_and_store
from build_training_jsonl import build_jsonl

BASE_PROCESSED = "/workspaces/ml_processor/data/processed"


def is_already_processed(output_dir: Path) -> bool:
    """Cek apakah video ini sudah pernah diproses sukses sebelumnya."""
    run_log_path = output_dir / "run_log.json"
    if not run_log_path.exists():
        return False
    with open(run_log_path) as f:
        log = json.load(f)
    return log.get("status") == "success"


def save_run_log(output_dir: Path, run_log: dict):
    """Simpan run log ke file."""
    log_path = output_dir / "run_log.json"
    with open(log_path, "w") as f:
        json.dump(run_log, f, indent=2, ensure_ascii=False)


def run_pipeline(
    video_path: str,
    skip_embed: bool  = False,
    skip_jsonl: bool  = False,
    force: bool       = False,
    model_size: str   = "medium",
    language: str     = "id"
) -> dict:
    """
    Jalankan full pipeline video_content_analysis.

    Returns:
        run_log dict berisi status dan info setiap step
    """
    video_path = Path(video_path)
    video_id   = video_path.stem
    output_dir = Path(BASE_PROCESSED) / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"🎬 VIDEO CONTENT ANALYSIS PIPELINE")
    print(f"   Video   : {video_path.name}")
    print(f"   Video ID: {video_id}")
    print(f"   Output  : {output_dir}")
    print(f"{'='*55}\n")

    # Cek apakah sudah pernah diproses
    if not force and is_already_processed(output_dir):
        print(f"⏭️  Video '{video_id}' sudah pernah diproses.")
        print(f"   Gunakan --force untuk memproses ulang.")
        with open(output_dir / "run_log.json") as f:
            return json.load(f)

    run_log = {
        "video_id":   video_id,
        "video_path": str(video_path),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "model_size":  model_size,
            "language":    language,
            "skip_embed":  skip_embed,
            "skip_jsonl":  skip_jsonl,
        },
        "steps": {},
        "status": "running"
    }

    # Simpan log awal
    save_run_log(output_dir, run_log)

    def run_step(step_name: str, fn, *args):
        """Helper: jalankan satu step, log hasilnya."""
        print(f"\n[ {step_name} ]")
        t = time.time()
        try:
            result = fn(*args)
            duration = round(time.time() - t, 1)
            run_log["steps"][step_name] = {"status": "ok", "duration_s": duration}
            save_run_log(output_dir, run_log)
            return result
        except Exception as e:
            duration = round(time.time() - t, 1)
            run_log["steps"][step_name] = {
                "status":    "failed",
                "duration_s": duration,
                "error":     str(e)
            }
            run_log["status"] = "failed"
            run_log["failed_at"] = step_name
            save_run_log(output_dir, run_log)
            print(f"  ❌ Gagal: {e}")
            raise

    try:
        # ── Step 1: Extract Audio ────────────────────────────────────────────
        audio_path = run_step(
            "1_extract_audio",
            extract_audio,
            str(video_path), str(output_dir)
        )

        # ── Step 2: Transcribe ───────────────────────────────────────────────
        transcript_path = run_step(
            "2_transcribe",
            transcribe_audio,
            audio_path, str(output_dir), model_size, language
        )

        # ── Step 3: Segment & Clean ──────────────────────────────────────────
        clean_path = run_step(
            "3_segment_and_clean",
            process_transcript,
            transcript_path, str(output_dir)
        )

        # ── Step 4: Summarize ────────────────────────────────────────────────
        summary_path = run_step(
            "4_summarize",
            summarize_all,
            clean_path, str(output_dir)
        )

        # ── Step 5a: Embed ke vector store ───────────────────────────────────
        if not skip_embed:
            n_chunks = run_step(
                "5a_embed",
                embed_and_store,
                summary_path
            )
            run_log["steps"]["5a_embed"]["chunks"] = n_chunks
        else:
            print("\n[ 5a_embed ] ⏭️  SKIP (--skip-embed)")
            run_log["steps"]["5a_embed"] = {"status": "skipped"}

        # ── Step 5b: Build training JSONL ─────────────────────────────────────
        if not skip_jsonl:
            jsonl_path = run_step(
                "5b_build_jsonl",
                build_jsonl,
                summary_path
            )
            run_log["steps"]["5b_build_jsonl"]["output"] = jsonl_path
        else:
            print("\n[ 5b_build_jsonl ] ⏭️  SKIP (--skip-jsonl)")
            run_log["steps"]["5b_build_jsonl"] = {"status": "skipped"}

        # ── Selesai ───────────────────────────────────────────────────────────
        run_log["status"]      = "success"
        run_log["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        total_time = sum(
            s.get("duration_s", 0)
            for s in run_log["steps"].values()
            if isinstance(s, dict)
        )
        run_log["total_duration_s"] = round(total_time, 1)

    except Exception:
        # Error sudah di-log di dalam run_step
        pass

    finally:
        save_run_log(output_dir, run_log)

    # ── Print summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    if run_log["status"] == "success":
        print(f"✅ Pipeline SELESAI: {video_id}")
        print(f"⏱️  Total waktu: {run_log.get('total_duration_s', '?')}s")
    else:
        print(f"❌ Pipeline GAGAL di step: {run_log.get('failed_at', '?')}")
        print(f"   Lihat run_log.json untuk detail: {output_dir / 'run_log.json'}")
    print(f"{'='*55}\n")

    return run_log


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Video Content Analysis Pipeline untuk ml_processor agent"
    )
    parser.add_argument("video_path",   help="Path ke file video yang akan diproses")
    parser.add_argument("--skip-embed", action="store_true",  help="Lewati embedding ke vector store")
    parser.add_argument("--skip-jsonl", action="store_true",  help="Lewati build training JSONL")
    parser.add_argument("--force",      action="store_true",  help="Proses ulang meski sudah pernah diproses")
    parser.add_argument("--model",      default="medium",     help="Whisper model size (default: medium)")
    parser.add_argument("--language",   default="id",         help="Kode bahasa ISO 639-1 (default: id)")

    args = parser.parse_args()

    log = run_pipeline(
        video_path  = args.video_path,
        skip_embed  = args.skip_embed,
        skip_jsonl  = args.skip_jsonl,
        force       = args.force,
        model_size  = args.model,
        language    = args.language
    )

    sys.exit(0 if log["status"] == "success" else 1)

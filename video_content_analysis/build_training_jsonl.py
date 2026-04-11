"""
build_training_jsonl.py
-----------------------
Konversi summary.json ke format JSONL untuk fine-tuning LLM.
Setiap video menghasilkan file JSONL individual + di-append ke combined_latest.jsonl

Usage:
    python build_training_jsonl.py <path_ke_summary.json>
"""

import json
import sys
from pathlib import Path

TRAINING_SET_DIR = "/workspaces/ml_processor/data/training_sets"


def build_qa_pairs(block: dict, video_id: str, domain: str) -> list[dict]:
    """
    Bangun pasangan prompt-completion dari satu blok.
    Menghasilkan 3 jenis task:
    1. QA (dari questions_answered)
    2. Summarization
    3. Topic extraction
    """
    analysis = block.get("analysis", {})
    raw_text = block["text"]
    summary  = analysis.get("summary", "")
    topic    = analysis.get("topic", "")
    keywords = analysis.get("keywords", [])
    qa_list  = analysis.get("questions_answered", [])

    records = []
    base_meta = {
        "video_id": video_id,
        "block_id": block["block_id"],
        "domain":   domain,
        "start":    block["start"],
        "end":      block["end"],
    }

    # --- Task 1: QA ---
    for question in qa_list:
        if len(question.strip()) > 10 and len(summary) > 10:
            records.append({
                "prompt":     question.strip(),
                "completion": summary,
                "meta":       {**base_meta, "type": "qa"}
            })

    # --- Task 2: Summarization ---
    if len(raw_text) > 50 and len(summary) > 10:
        records.append({
            "prompt":     f"Ringkas teks berikut:\n\n{raw_text}",
            "completion": summary,
            "meta":       {**base_meta, "type": "summarization"}
        })

    # --- Task 3: Topic extraction ---
    if len(raw_text) > 50 and len(topic) > 5:
        records.append({
            "prompt":     f"Apa topik utama dari teks ini?\n\n{raw_text}",
            "completion": topic,
            "meta":       {**base_meta, "type": "topic_extraction"}
        })

    # --- Task 4: Keyword extraction (jika ada keywords) ---
    if keywords and len(raw_text) > 50:
        kw_string = ", ".join(keywords)
        records.append({
            "prompt":     f"Sebutkan kata-kata kunci penting dari teks ini:\n\n{raw_text}",
            "completion": kw_string,
            "meta":       {**base_meta, "type": "keyword_extraction"}
        })

    return records


def build_jsonl(summary_path: str) -> str:
    """
    Bangun file JSONL training dari summary.json.

    Output:
    - /training_sets/{video_id}.jsonl    ← per-video
    - /training_sets/combined_latest.jsonl ← append ke combined

    Returns:
        path ke file JSONL per-video
    """
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    video_id = Path(summary_path).parent.name
    overall  = data.get("overall", {})
    domain   = overall.get("domain", "general")

    output_dir = Path(TRAINING_SET_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_records = []

    for block in data["blocks"]:
        records = build_qa_pairs(block, video_id, domain)
        all_records.extend(records)

    # Simpan per-video
    video_jsonl_path = output_dir / f"{video_id}.jsonl"
    with open(video_jsonl_path, "w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Append ke combined (JANGAN overwrite)
    combined_path = output_dir / "combined_latest.jsonl"
    with open(combined_path, "a", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Statistik per task type
    type_counts = {}
    for rec in all_records:
        t = rec["meta"]["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    print(f"✅ {len(all_records)} record ditulis ke {video_jsonl_path}")
    print(f"   Breakdown:")
    for task_type, count in type_counts.items():
        print(f"   - {task_type}: {count} record")
    print(f"✅ combined_latest.jsonl diperbarui: {combined_path}")

    return str(video_jsonl_path)


def count_combined() -> int:
    """Hitung total record di combined_latest.jsonl."""
    combined_path = Path(TRAINING_SET_DIR) / "combined_latest.jsonl"
    if not combined_path.exists():
        return 0
    with open(combined_path, "r") as f:
        return sum(1 for line in f if line.strip())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_training_jsonl.py <summary.json>")
        sys.exit(1)

    build_jsonl(sys.argv[1])

    total = count_combined()
    print(f"\n📊 Total record di combined_latest.jsonl: {total}")
    if total < 500:
        print(f"   ℹ️  Masih perlu lebih banyak data untuk fine-tuning ({total}/500 record minimum).")
        print(f"   ✅ Gunakan RAG engine dulu sambil kumpulkan lebih banyak video.")
    else:
        print(f"   ✅ Dataset sudah cukup untuk memulai fine-tuning!")

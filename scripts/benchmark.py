"""Benchmark rep counting on real, hand-labelled clips.

1. Put clips in benchmarks/clips/
2. List them in benchmarks/labels.csv:   file,exercise,true_reps
3. Run from the repo root:               python scripts/benchmark.py

Writes benchmarks/RESULTS.md with per-clip results, rep-count accuracy and pose-model latency.
"""
import csv
import statistics
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from services.analysis.video_analyzer import analyze_video  # noqa: E402

BENCH_DIR = ROOT / "benchmarks"
LABELS = BENCH_DIR / "labels.csv"
RESULTS = BENCH_DIR / "RESULTS.md"


def load_labels():
    if not LABELS.exists():
        sys.exit(f"Missing {LABELS.relative_to(ROOT)}. See benchmarks/README.md.")

    with LABELS.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("file") and not r["file"].startswith("#")]

    if not rows:
        sys.exit("labels.csv has no clips yet. See benchmarks/README.md.")

    return rows


def percentile(values, pct):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))]


def main():
    rows = load_labels()
    results = []
    all_inference = []

    for row in rows:
        path = BENCH_DIR / "clips" / row["file"]
        if not path.exists():
            print(f"skip  {row['file']} (file not found)")
            continue

        started = time.perf_counter()
        analysis = analyze_video(str(path), row["exercise"])
        wall = time.perf_counter() - started

        true_reps = int(row["true_reps"])
        counted = analysis.report.rep_count
        all_inference += analysis.inference_ms

        results.append({
            "file": row["file"],
            "exercise": row["exercise"],
            "true": true_reps,
            "counted": counted,
            "error": counted - true_reps,
            "coverage": analysis.report.pose_coverage,
            "frames": analysis.frame_count,
            "duration": analysis.duration,
            "fps": analysis.frame_count / wall if wall else 0,
        })
        print(f"done  {row['file']}: counted {counted} / {true_reps}")

    if not results:
        sys.exit("No clips were found on disk.")

    total_true = sum(r["true"] for r in results)
    exact = sum(1 for r in results if r["error"] == 0)
    abs_errors = [abs(r["error"]) for r in results]
    rep_accuracy = f"{1 - sum(abs_errors) / total_true:.1%}" if total_true else "n/a"

    lines = [
        "# Rep counting benchmark",
        "",
        f"_Generated {date.today().isoformat()} by `scripts/benchmark.py` on {len(results)} hand-labelled clips._",
        "",
        "| Metric | Value |",
        "| :--- | ---: |",
        f"| Clips with exactly the right rep count | {exact}/{len(results)} ({exact / len(results):.0%}) |",
        f"| Rep-level accuracy (1 - total abs error / true reps) | {rep_accuracy} |",
        f"| Mean absolute error per clip | {statistics.mean(abs_errors):.2f} reps |",
        f"| Pose model latency p50 / p95 | {percentile(all_inference, 50):.1f} / {percentile(all_inference, 95):.1f} ms per frame |",
        f"| End-to-end throughput (decode + model + draw + encode) | {statistics.mean(r['fps'] for r in results):.0f} frames/s |",
        "",
        "| Clip | Exercise | True reps | Counted | Error | Pose found |",
        "| :--- | :--- | ---: | ---: | ---: | ---: |",
    ]
    lines += [
        f"| {r['file']} | {r['exercise']} | {r['true']} | {r['counted']} | {r['error']:+d} | {r['coverage']:.0%} |"
        for r in results
    ]

    RESULTS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {RESULTS.relative_to(ROOT)}")
    print("\n".join(lines[4:10]))


if __name__ == "__main__":
    main()

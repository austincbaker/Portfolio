#!/usr/bin/env python3
"""
Standalone script to analyze JSONL checkpoint files and generate final evaluation report.

Usage:
    python analyze_checkpoint.py <checkpoint.jsonl> [-o OUTPUT_FILE]

Example:
    python analyze_checkpoint.py evaluation_20251126_103015.checkpoint.jsonl
    python analyze_checkpoint.py evaluation_20251126_103015.checkpoint.jsonl -o final_analysis.json
"""

import json
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict
from typing import Optional


@dataclass
class VideoCheckpoint:
    """Checkpoint data for a single video."""
    video_name: str
    timestamp: str
    num_questions: int
    results: list[dict]
    completed: bool = True


@dataclass
class EvaluationResult:
    video_name: str
    question_type: str
    prompt: str
    answers: list[str]
    correct_answer: str
    correct_index: int
    model_response: str
    model_selected_index: Optional[int]
    is_correct: bool
    error: Optional[str] = None


def load_checkpoint_file(checkpoint_path: Path) -> tuple[list[EvaluationResult], dict]:

    all_results = []
    video_stats = {}
    lines_read = 0
    lines_failed = 0

    if not checkpoint_path.exists():
        print(f"Error: Checkpoint file not found: {checkpoint_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue

                lines_read += 1
                try:
                    data = json.loads(line)
                    checkpoint = VideoCheckpoint(**data)


                    for result_dict in checkpoint.results:
                        try:
                            result = EvaluationResult(**result_dict)
                            all_results.append(result)
                        except TypeError as e:
                            lines_failed += 1
                            print(f"Warning: Failed to parse result in {checkpoint.video_name}: {e}",
                                  file=sys.stderr)
                            continue


                    video_stats[checkpoint.video_name] = {
                        'num_questions': checkpoint.num_questions,
                        'timestamp': checkpoint.timestamp
                    }

                except json.JSONDecodeError as e:
                    lines_failed += 1
                    print(f"Warning: Failed to parse JSON line {lines_read}: {e}", file=sys.stderr)
                    continue
                except TypeError as e:
                    lines_failed += 1
                    print(f"Warning: Invalid checkpoint format at line {lines_read}: {e}",
                          file=sys.stderr)
                    continue

    except IOError as e:
        print(f"Error reading checkpoint file: {e}", file=sys.stderr)
        sys.exit(1)

    if lines_read == 0:
        print("Error: Checkpoint file is empty", file=sys.stderr)
        sys.exit(1)

    if lines_failed > 0:
        print(f"Warning: {lines_failed}/{lines_read} lines failed to parse", file=sys.stderr)

    return all_results, video_stats


def compute_summary(results: list[EvaluationResult]) -> dict:

    if not results:
        print("Error: No evaluation results to analyze", file=sys.stderr)
        sys.exit(1)

    total = len(results)
    correct = sum(1 for r in results if r.is_correct)
    accuracy = correct / total if total > 0 else 0.0


    by_type = defaultdict(lambda: {"total": 0, "correct": 0})
    for r in results:
        by_type[r.question_type]["total"] += 1
        if r.is_correct:
            by_type[r.question_type]["correct"] += 1

    accuracy_by_type = {}
    for qtype, counts in sorted(by_type.items()):
        t, c = counts["total"], counts["correct"]
        accuracy_by_type[qtype] = {
            "total": t,
            "correct": c,
            "accuracy": c / t if t > 0 else 0.0,
        }

    return {
        "total_questions": total,
        "correct_count": correct,
        "accuracy": accuracy,
        "accuracy_by_type": accuracy_by_type,
    }


def print_analysis_report(summary: dict, video_stats: dict, checkpoint_path: Path) -> None:

    print("\n" + "=" * 70)
    print("CHECKPOINT ANALYSIS REPORT")
    print("=" * 70)
    print(f"\nCheckpoint file: {checkpoint_path}")
    print(f"Analysis timestamp: {datetime.now().isoformat()}")

    print("\n" + "-" * 70)
    print("SUMMARY STATISTICS")
    print("-" * 70)
    print(f"Total videos evaluated: {len(video_stats)}")
    print(f"Total questions: {summary['total_questions']}")
    print(f"Correct answers: {summary['correct_count']}")
    print(f"Overall accuracy: {summary['accuracy']:.2%}")

    print("\n" + "-" * 70)
    print("ACCURACY BY QUESTION TYPE")
    print("-" * 70)

    for qtype, stats in summary['accuracy_by_type'].items():
        accuracy_pct = stats['accuracy'] * 100
        print(f"  {qtype:35s}: {stats['correct']:5d}/{stats['total']:5d} ({accuracy_pct:6.2f}%)")

    print("\n" + "-" * 70)
    print("VIDEO STATISTICS")
    print("-" * 70)
    print(f"Number of videos: {len(video_stats)}")

    if video_stats:

        sample_videos = sorted(video_stats.items())[:5]
        print("\nSample videos (first 5):")
        for video_name, stats in sample_videos:
            print(f"  {video_name}")
            print(f"    Questions: {stats['num_questions']}")
            print(f"    Timestamp: {stats['timestamp']}")

    print("\n" + "=" * 70 + "\n")


def save_final_analysis(summary: dict, video_stats: dict, results: list[EvaluationResult],
                        output_path: Path, checkpoint_path: Path) -> None:

    output_data = {
        "timestamp": datetime.now().isoformat(),
        "checkpoint_source": str(checkpoint_path),
        "total_questions": summary['total_questions'],
        "correct_count": summary['correct_count'],
        "accuracy": summary['accuracy'],
        "accuracy_by_type": summary['accuracy_by_type'],
        "total_videos_evaluated": len(video_stats),
        "video_stats": video_stats,
        "results": [asdict(r) for r in results],
    }

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Final analysis saved to: {output_path}")
    except IOError as e:
        print(f"Error saving output file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze JSONL checkpoint file and generate final evaluation report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_checkpoint.py evaluation_20251126_103015.checkpoint.jsonl
  python analyze_checkpoint.py evaluation_20251126_103015.checkpoint.jsonl -o final_analysis.json
  python analyze_checkpoint.py /path/to/checkpoint.jsonl -o /path/to/output.json
        """
    )

    parser.add_argument(
        "checkpoint_file",
        type=Path,
        help="Path to checkpoint JSONL file"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Path to save final analysis JSON (optional)"
    )

    args = parser.parse_args()

    checkpoint_path = args.checkpoint_file.resolve()

    print(f"Loading checkpoint file: {checkpoint_path}")
    results, video_stats = load_checkpoint_file(checkpoint_path)

    print(f"Loaded {len(results)} evaluation results from {len(video_stats)} videos")
    print("Computing summary statistics...")

    summary = compute_summary(results)

    print_analysis_report(summary, video_stats, checkpoint_path)

    if args.output:
        output_path = args.output.resolve()
        print(f"Saving final analysis to: {output_path}")
        save_final_analysis(summary, video_stats, results, output_path, checkpoint_path)

    print("Analysis complete!")


if __name__ == "__main__":
    main()
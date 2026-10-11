"""
Multi-GPU parallel evaluation runner using subprocess isolation.

Distributes videos across multiple GPUs using separate processes.
Each GPU worker is a completely independent subprocess with its own
CUDA context, avoiding the common issues with Python multiprocessing and CUDA.
"""
import json
import sys
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
import argparse
from collections import defaultdict

from ..templates import SECONDARY_QUESTION_TYPES


def get_completed_videos(checkpoint_dir: Path) -> set[str]:

    completed = set()

    if not checkpoint_dir.exists():
        return completed

    for checkpoint_file in checkpoint_dir.glob("checkpoint_gpu*.jsonl"):
        try:
            with open(checkpoint_file, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        video_name = data.get("video_name")
                        if video_name:
                            completed.add(video_name)
        except Exception as e:
            print(f"Warning: Error reading {checkpoint_file}: {e}")

    return completed


def merge_checkpoints(checkpoint_dir: Path, output_path: Path, config: dict) -> dict:

    all_results = []
    video_stats = {}


    for checkpoint_file in sorted(checkpoint_dir.glob("checkpoint_gpu*.jsonl")):
        print(f"Reading {checkpoint_file.name}...")
        with open(checkpoint_file, 'r') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    video_name = data["video_name"]
                    video_stats[video_name] = {
                        "gpu_id": data["gpu_id"],
                        "num_questions": data["num_questions"],
                        "num_correct": data.get("num_correct", 0),
                        "timestamp": data["timestamp"],
                    }
                    all_results.extend(data["results"])


    primary_results = [r for r in all_results if r.get("question_type") not in SECONDARY_QUESTION_TYPES]
    secondary_results = [r for r in all_results if r.get("question_type") in SECONDARY_QUESTION_TYPES]

    def _type_stats(results):
        by_type = defaultdict(lambda: {"total": 0, "correct": 0})
        for r in results:
            qtype = r.get("question_type", "unknown")
            by_type[qtype]["total"] += 1
            if r.get("is_correct", False):
                by_type[qtype]["correct"] += 1
        return {
            qtype: {"total": c["total"], "correct": c["correct"],
                    "accuracy": c["correct"] / c["total"] if c["total"] > 0 else 0.0}
            for qtype, c in by_type.items()
        }

    p_total = len(primary_results)
    p_correct = sum(1 for r in primary_results if r.get("is_correct", False))
    s_total = len(secondary_results)
    s_correct = sum(1 for r in secondary_results if r.get("is_correct", False))

    output_data = {
        "timestamp": datetime.now().isoformat(),
        "model_path": config.get("model_path", "unknown"),
        "num_frames": config.get("num_frames", 8),
        "primary_total_questions": p_total,
        "primary_correct_count": p_correct,
        "primary_accuracy": p_correct / p_total if p_total > 0 else 0.0,
        "primary_accuracy_by_type": _type_stats(primary_results),
        "secondary_total_questions": s_total,
        "secondary_correct_count": s_correct,
        "secondary_accuracy": s_correct / s_total if s_total > 0 else 0.0,
        "secondary_accuracy_by_type": _type_stats(secondary_results),
        "total_videos_evaluated": len(video_stats),
        "video_stats": video_stats,
        "results": all_results,
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    return output_data


def run_parallel_evaluation(
    annotations_path: str,
    video_dir: str,
    output_dir: str,
    num_gpus: int = 1,
    model_path: str = "AIDC-AI/Ovis2.5-9B",
    num_frames: int = 8,
    num_distractors: int = 5,
    thinking_budget: int = 128,
    max_new_tokens: int = 64,
    stagger_delay: float = 30.0,
    resume: bool = True,
    questions_file: str | None = None,
) -> dict:


    with open(annotations_path, 'r') as f:
        annotations = json.load(f)

    if isinstance(annotations, dict) and "annotations" in annotations:
        annotations = annotations["annotations"]


    if questions_file:
        with open(questions_file, 'r') as f:
            questions_data = json.load(f)
        questions_by_video = questions_data.get("questions_by_video", {})
        all_video_names = sorted(questions_by_video.keys())
    else:
        all_video_names = sorted(set(a.get("video_name") for a in annotations if a.get("video_name")))

    print("=" * 70)
    print("MULTI-GPU PARALLEL EVALUATION (Subprocess Mode)")
    print("=" * 70)
    print(f"Total videos in annotations: {len(all_video_names)}")
    print(f"GPUs requested: {num_gpus}")
    print(f"Model: {model_path}")
    print(f"Questions: {questions_file or 'on-the-fly generation'}")
    print(f"Stagger delay: {stagger_delay}s between GPU starts")
    print(f"Resume mode: {resume}")
    print()


    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    checkpoint_dir = output_path / "checkpoints"
    checkpoint_dir.mkdir(exist_ok=True)

    videos_dir = output_path / "video_assignments"
    videos_dir.mkdir(exist_ok=True)

    logs_dir = output_path / "logs"
    logs_dir.mkdir(exist_ok=True)


    completed_videos = set()
    if resume:
        completed_videos = get_completed_videos(checkpoint_dir)
        if completed_videos:
            print(f"Found {len(completed_videos)} already-completed videos in checkpoints")


    video_names = [v for v in all_video_names if v not in completed_videos]

    if not video_names:
        print("All videos have already been processed!")
        print("Use --no-resume to start fresh, or check the checkpoint files.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_output = output_path / f"evaluation_{timestamp}.json"
        return merge_checkpoints(checkpoint_dir, final_output, {"model_path": model_path, "num_frames": num_frames})

    print(f"Videos to process: {len(video_names)} (skipping {len(completed_videos)} already done)")
    print()


    if not resume:
        for old_file in checkpoint_dir.glob("checkpoint_gpu*.jsonl"):
            old_file.unlink()
    for old_file in videos_dir.glob("videos_gpu*.json"):
        old_file.unlink()

    video_batches = [[] for _ in range(num_gpus)]
    for i, video in enumerate(video_names):
        gpu_idx = i % num_gpus
        video_batches[gpu_idx].append(video)

    print("Video distribution:")
    for i, batch in enumerate(video_batches):
        print(f"  GPU {i}: {len(batch)} videos")
    print()


    video_files = []
    for gpu_id in range(num_gpus):
        video_file = videos_dir / f"videos_gpu{gpu_id}.json"
        with open(video_file, 'w') as f:
            json.dump(video_batches[gpu_id], f)
        video_files.append(video_file)


    worker_module = "prompt_generator.evaluation.gpu_worker"


    processes = []
    log_files = []

    print(f"Starting {num_gpus} GPU worker processes...")
    print()

    for gpu_id in range(num_gpus):
        if not video_batches[gpu_id]:
            print(f"GPU {gpu_id}: No videos assigned, skipping")
            continue


        stdout_log = logs_dir / f"gpu{gpu_id}_stdout.log"
        stderr_log = logs_dir / f"gpu{gpu_id}_stderr.log"

        stdout_file = open(stdout_log, 'w')
        stderr_file = open(stderr_log, 'w')
        log_files.extend([stdout_file, stderr_file])


        cmd = [
            sys.executable, "-m", worker_module,
            "--gpu-id", str(gpu_id),
            "--videos-file", str(video_files[gpu_id]),
            "--annotations", annotations_path,
            "--video-dir", video_dir,
            "--checkpoint-dir", str(checkpoint_dir),
            "--model-path", model_path,
            "--num-frames", str(num_frames),
            "--num-distractors", str(num_distractors),
            "--thinking-budget", str(thinking_budget),
            "--max-new-tokens", str(max_new_tokens),
        ]

        if questions_file:
            cmd.extend(["--questions-file", questions_file])

        env = os.environ.copy()
        env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        if os.environ.get("DEVICE_MAP"):
            print(f"Starting GPU {gpu_id} worker (DEVICE_MAP={os.environ['DEVICE_MAP']}, all GPUs visible)...")
        else:
            env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
            print(f"Starting GPU {gpu_id} worker (CUDA_VISIBLE_DEVICES={gpu_id})...")


        proc = subprocess.Popen(
            cmd,
            stdout=stdout_file,
            stderr=stderr_file,
            env=env,
            cwd=os.getcwd(),
        )
        processes.append((gpu_id, proc))

        if gpu_id < num_gpus - 1 and stagger_delay > 0:
            print(f"  Waiting {stagger_delay}s before starting next worker...")
            time.sleep(stagger_delay)

    print()
    print(f"All {len(processes)} workers started. Monitoring progress...")
    print(f"Logs available in: {logs_dir}")
    print()


    start_time = time.time()
    completed = set()
    failed = []

    while len(completed) < len(processes):
        time.sleep(10)

        for gpu_id, proc in processes:
            if gpu_id in completed:
                continue

            ret = proc.poll()
            if ret is not None:
                completed.add(gpu_id)
                elapsed = time.time() - start_time

                if ret == 0:

                    stdout_log = logs_dir / f"gpu{gpu_id}_stdout.log"
                    try:
                        with open(stdout_log, 'r') as f:
                            lines = f.readlines()

                            for line in reversed(lines):
                                if "FINISHED" in line:
                                    print(f"GPU {gpu_id} completed: {line.strip()}")
                                    break
                            else:
                                print(f"GPU {gpu_id} completed (exit code 0) after {elapsed:.1f}s")
                    except:
                        print(f"GPU {gpu_id} completed (exit code 0) after {elapsed:.1f}s")
                else:
                    failed.append(gpu_id)
                    print(f"GPU {gpu_id} FAILED with exit code {ret} after {elapsed:.1f}s")

                    stderr_log = logs_dir / f"gpu{gpu_id}_stderr.log"
                    try:
                        with open(stderr_log, 'r') as f:
                            lines = f.readlines()[-10:]
                            print(f"  Last error lines:")
                            for line in lines:
                                print(f"    {line.rstrip()}")
                    except:
                        pass


        active = len(processes) - len(completed)
        if active > 0:
            elapsed = time.time() - start_time
            print(f"  [{elapsed/60:.1f}m elapsed] {len(completed)}/{len(processes)} workers completed, {active} active")


    for f in log_files:
        f.close()

    total_time = time.time() - start_time
    print()
    print(f"All workers finished in {total_time/60:.1f} minutes")

    if failed:
        print(f"WARNING: {len(failed)} workers failed: GPU(s) {failed}")
        print(f"Check logs in {logs_dir} for details")


    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_output = output_path / f"evaluation_{timestamp}.json"

    print()
    print("Merging results from checkpoints...")

    final_results = merge_checkpoints(
        checkpoint_dir,
        final_output,
        {"model_path": model_path, "num_frames": num_frames}
    )


    print()
    print("=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)
    print(f"Total videos evaluated: {final_results['total_videos_evaluated']}")
    print(f"Primary questions: {final_results['primary_total_questions']}")
    print(f"Primary correct: {final_results['primary_correct_count']}")
    print(f"Primary accuracy: {final_results['primary_accuracy']:.2%}")
    print()
    print("Primary accuracy by question type:")
    for qtype, stats in sorted(final_results['primary_accuracy_by_type'].items()):
        print(f"  {qtype}: {stats['correct']}/{stats['total']} ({stats['accuracy']:.2%})")
    print()
    print(f"Secondary questions: {final_results['secondary_total_questions']}")
    print(f"Secondary correct: {final_results['secondary_correct_count']}")
    print(f"Secondary accuracy: {final_results['secondary_accuracy']:.2%}")
    print()
    print("Secondary accuracy by question type:")
    for qtype, stats in sorted(final_results['secondary_accuracy_by_type'].items()):
        print(f"  {qtype}: {stats['correct']}/{stats['total']} ({stats['accuracy']:.2%})")
    print()
    print(f"Results saved to: {final_output}")
    print(f"Checkpoints in: {checkpoint_dir}")
    print(f"Logs in: {logs_dir}")

    return final_results


def main():
    parser = argparse.ArgumentParser(
        description="Run parallel evaluation across multiple GPUs"
    )
    parser.add_argument(
        "annotations_json",
        help="Path to JSON file containing video annotations",
    )
    parser.add_argument(
        "video_dir",
        help="Directory containing video files",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="./results",
        help="Directory for output files (default: ./results)",
    )
    parser.add_argument(
        "-g", "--num-gpus",
        type=int,
        default=1,
        help="Number of GPUs to use (default: 1)",
    )
    parser.add_argument(
        "-m", "--model-path",
        default="AIDC-AI/Ovis2.5-9B",
        help="HuggingFace model path (default: AIDC-AI/Ovis2.5-9B)",
    )
    parser.add_argument(
        "-f", "--num-frames",
        type=int,
        default=8,
        help="Number of frames per video (default: 8)",
    )
    parser.add_argument(
        "-d", "--num-distractors",
        type=int,
        default=5,
        help="Number of distractor answers (default: 5)",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=128,
        help="Model thinking budget (default: 128)",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=64,
        help="Max tokens to generate (default: 64)",
    )
    parser.add_argument(
        "--stagger-delay",
        type=float,
        default=30.0,
        help="Seconds to wait between starting each GPU worker (default: 30)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Resume from existing checkpoints, skipping completed videos (default: True)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh, ignoring any existing checkpoints",
    )
    parser.add_argument(
        "--questions-file",
        type=str,
        default=None,
        help="Path to pre-generated questions JSON file (skips on-the-fly generation in workers)",
    )

    args = parser.parse_args()


    resume = args.resume and not args.no_resume

    run_parallel_evaluation(
        annotations_path=args.annotations_json,
        video_dir=args.video_dir,
        output_dir=args.output_dir,
        num_gpus=args.num_gpus,
        model_path=args.model_path,
        num_frames=args.num_frames,
        num_distractors=args.num_distractors,
        thinking_budget=args.thinking_budget,
        max_new_tokens=args.max_new_tokens,
        stagger_delay=args.stagger_delay,
        resume=resume,
        questions_file=args.questions_file,
    )


if __name__ == "__main__":
    main()
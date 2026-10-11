#!/usr/bin/env python3
"""
Standalone GPU worker script.

This script runs as a completely separate process for each GPU.
CUDA_VISIBLE_DEVICES is set via environment variable BEFORE this script runs.

Usage:
    CUDA_VISIBLE_DEVICES=0 python -m prompt_generator.evaluation.gpu_worker \
        --gpu-id 0 \
        --videos-file /path/to/videos_gpu0.json \
        --annotations /path/to/annotations.json \
        --video-dir /path/to/videos \
        --checkpoint-dir /path/to/checkpoints \
        --model-path AIDC-AI/Ovis2.5-9B
"""
import argparse
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

def get_time():
    return datetime.now().isoformat(' ', timespec='seconds')

def main():
    parser = argparse.ArgumentParser(description="GPU Worker for video evaluation")
    parser.add_argument("--gpu-id", type=int, required=True, help="GPU ID (for logging)")
    parser.add_argument("--videos-file", type=str, required=True, help="JSON file with list of video names")
    parser.add_argument("--annotations", type=str, required=True, help="Path to annotations JSON")
    parser.add_argument("--video-dir", type=str, required=True, help="Directory containing videos")
    parser.add_argument("--checkpoint-dir", type=str, required=True, help="Directory for checkpoints")
    parser.add_argument("--model-path", type=str, default="AIDC-AI/Ovis2.5-9B")
    parser.add_argument("--num-frames", type=int, default=8)
    parser.add_argument("--num-distractors", type=int, default=7)
    parser.add_argument("--thinking-budget", type=int, default=128)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--use-torch-compile", action="store_true", default=True)
    parser.add_argument("--no-torch-compile", action="store_true")
    parser.add_argument("--questions-file", type=str, default=None,
                        help="Path to pre-generated questions JSON (skips on-the-fly generation)")

    args = parser.parse_args()

    gpu_id = args.gpu_id

    cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", "NOT SET")
    print(f"[GPU {gpu_id}] [{get_time()}] Starting worker")
    print(f"[GPU {gpu_id}] [{get_time()}] CUDA_VISIBLE_DEVICES = {cuda_visible}")
    print(f"[GPU {gpu_id}] [{get_time()}] Model: {args.model_path}")
    sys.stdout.flush()

    import torch

    if not torch.cuda.is_available():
        print(f"[GPU {gpu_id}] [{get_time()}] ERROR: CUDA not available!", file=sys.stderr)
        sys.exit(1)

    print(f"[GPU {gpu_id}] [{get_time()}] CUDA device count: {torch.cuda.device_count()}")
    print(f"[GPU {gpu_id}] [{get_time()}] Device name: {torch.cuda.get_device_name(0)}")
    print(f"[GPU {gpu_id}] [{get_time()}] Device memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    sys.stdout.flush()


    from .model_loader import ModelConfig, create_loader
    from .model_loader.registry import resolve_model_path
    from .video_processor import VideoProcessorConfig, create_video_processor
    from .evaluator import EvaluationResult


    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from prompt_generator.generator import GeneratedQuestion


    with open(args.videos_file, 'r') as f:
        video_names = json.load(f)

    print(f"[GPU {gpu_id}] [{get_time()}] Assigned {len(video_names)} videos")
    sys.stdout.flush()


    args.model_path = resolve_model_path(args.model_path)
    print(f"[GPU {gpu_id}] [{get_time()}] Resolved model path: {args.model_path}")
    sys.stdout.flush()


    with open(args.annotations, 'r') as f:
        annotations = json.load(f)

    if isinstance(annotations, dict) and "annotations" in annotations:
        annotations = annotations["annotations"]


    video_set = set(video_names)
    batch_annotations = [a for a in annotations if a.get("video_name") in video_set]


    pregenerated_questions = None
    if args.questions_file:
        with open(args.questions_file, 'r') as f:
            questions_data = json.load(f)
        pregenerated_questions = questions_data.get("questions_by_video", {})
        total_pregenerated = sum(
            len(qs) for v, qs in pregenerated_questions.items() if v in video_set
        )
        print(f"[GPU {gpu_id}] [{get_time()}] Loaded pre-generated questions: {total_pregenerated} questions for {len(video_set)} assigned videos")
        sys.stdout.flush()


    use_compile = args.use_torch_compile and not args.no_torch_compile

    device_map = os.environ.get("DEVICE_MAP") or None
    if device_map:
        print(f"[GPU {gpu_id}] [{get_time()}] Using device_map={device_map}")
        sys.stdout.flush()

    model_config = ModelConfig(
        model_path=args.model_path,
        thinking_budget=args.thinking_budget,
        max_new_tokens=args.max_new_tokens,
        use_torch_compile=use_compile,
        use_flash_attention=True,
        device_map=device_map,
    )

    video_config = VideoProcessorConfig(num_frames=args.num_frames)


    model_loader = create_loader(model_config)
    video_processor = create_video_processor(video_config, use_fast=True)

    model_loader.ensure_packages()


    print(f"[GPU {gpu_id}] [{get_time()}] Loading model...")
    sys.stdout.flush()

    try:
        model_loader.load()
        print(f"[GPU {gpu_id}] [{get_time()}] Model loaded, warming up...")
        sys.stdout.flush()
        model_loader.warmup(num_frames=args.num_frames)
        print(f"[GPU {gpu_id}] [{get_time()}] Model ready")
        sys.stdout.flush()
    except Exception as e:
        print(f"[GPU {gpu_id}] [{get_time()}] ERROR loading model: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


    checkpoint_path = Path(args.checkpoint_dir) / f"checkpoint_gpu{gpu_id}.jsonl"
    video_dir_path = Path(args.video_dir)


    completed_videos = set()
    if checkpoint_path.exists():
        try:
            with open(checkpoint_path, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        completed_videos.add(data.get("video_name"))
            if completed_videos:
                print(f"[GPU {gpu_id}] [{get_time()}] Found {len(completed_videos)} already-completed videos in checkpoint")
                sys.stdout.flush()
        except Exception as e:
            print(f"[GPU {gpu_id}] [{get_time()}] Warning: Error reading checkpoint: {e}")


    videos_to_process = [v for v in video_names if v not in completed_videos]
    print(f"[GPU {gpu_id}] [{get_time()}] Videos to process: {len(videos_to_process)} (skipping {len(completed_videos)} already done)")
    sys.stdout.flush()

    if not videos_to_process:
        print(f"[GPU {gpu_id}] [{get_time()}] All assigned videos already completed!")
        model_loader.unload()
        sys.exit(0)


    total_questions = 0
    total_correct = 0

    try:
        for idx, video_name in enumerate(videos_to_process, start=1):
            print(f"[GPU {gpu_id}] [{get_time()}] [{idx}/{len(videos_to_process)}] Processing {video_name}")
            sys.stdout.flush()

            if pregenerated_questions is not None:

                question_dicts = pregenerated_questions.get(video_name, [])
                if not question_dicts:
                    print(f"[GPU {gpu_id}] [{get_time()}] No pre-generated questions for {video_name}, skipping")
                    continue
                questions = [
                    GeneratedQuestion(
                        video_name=qd["video_name"],
                        question_type=qd["question_type"],
                        prompt=qd["prompt"],
                        answers=qd["answers"],
                        correct_answer=qd["correct_answer"],
                        correct_index=qd["correct_index"],
                    )
                    for qd in question_dicts
                ]
            else:


                raise RuntimeError(
                    f"On-the-fly question generation is disabled. "
                    f"Pass a pre-generated questions JSON file via --questions-file."
                )


            video_path = video_dir_path / video_name
            try:
                frames = video_processor.extract_frames(video_path)
            except Exception as e:
                print(f"[GPU {gpu_id}] [{get_time()}] Failed to extract frames from {video_name}: {e}")
                continue


            video_results = []
            video_correct = 0

            for q_idx, q in enumerate(questions, start=1):
                print(f"[GPU {gpu_id}] [{get_time()}]   Question {q_idx}/{len(questions)}:")
                print(f"[GPU {gpu_id}] [{get_time()}]     Type: {q.question_type}")
                print(f"[GPU {gpu_id}] [{get_time()}]     Q: {q.prompt}")
                print(f"[GPU {gpu_id}] [{get_time()}]     Options:")
                for i, answer in enumerate(q.answers):
                    marker = "+" if i == q.correct_index else " "
                    print(f"[GPU {gpu_id}] [{get_time()}]       {marker} {i + 1}. {answer}")
                sys.stdout.flush()

                try:

                    prompt_lines = [
                        "Watch this video carefully and answer the following multiple-choice question.",
                        "Select ONLY the number (1, 2, 3, etc.) of the correct answer.",
                        "",
                        f"Question: {q.prompt}",
                        "",
                        "Options:",
                    ]
                    for i, answer in enumerate(q.answers):
                        prompt_lines.append(f"{i + 1}. {answer}")
                    prompt_lines.extend(["", "Answer with ONLY the option number (e.g., '1' or '2')."])
                    formatted_prompt = "\n".join(prompt_lines)


                    try:
                        response = model_loader.generate_response(frames, formatted_prompt)
                    except (ValueError, RuntimeError) as ve:
                        error_msg = str(ve).lower()
                        if "max_new_tokens" in error_msg or "token" in error_msg or "length" in error_msg:

                            print(f"[GPU {gpu_id}] [{get_time()}] Token limit hit, retrying with reduced settings...")
                            try:
                                response = model_loader.generate_response(
                                    frames,
                                    formatted_prompt,
                                    override_max_tokens=32,
                                    override_thinking_budget=0,
                                )
                            except Exception as retry_err:
                                print(f"[GPU {gpu_id}] [{get_time()}] Retry also failed: {retry_err}")
                                continue
                        else:
                            raise


                    selected_index = None
                    response_clean = response.strip()


                    single_digit = re.search(r"^(\d)$", response_clean)
                    if single_digit:
                        idx_val = int(single_digit.group(1)) - 1
                        if 0 <= idx_val < len(q.answers):
                            selected_index = idx_val

                    if selected_index is None:
                        for pattern in [r"(?:answer|option|choice)[\s:]*(\d)", r"^(\d)\.", r"^\((\d)\)", r"(\d)(?:\s|$)"]:
                            match = re.search(pattern, response_clean, re.IGNORECASE)
                            if match:
                                idx_val = int(match.group(1)) - 1
                                if 0 <= idx_val < len(q.answers):
                                    selected_index = idx_val
                                    break

                    is_correct = selected_index == q.correct_index
                    if is_correct:
                        video_correct += 1


                    status = "CORRECT" if is_correct else "WRONG"
                    selected_marker = f" (selected: {selected_index + 1})" if selected_index is not None else " (no valid selection)"
                    print(f"[GPU {gpu_id}] [{get_time()}]     Model Response: {response}")
                    print(f"[GPU {gpu_id}] [{get_time()}]     Status: {status}{selected_marker}")
                    sys.stdout.flush()

                    result = EvaluationResult(
                        video_name=q.video_name,
                        question_type=q.question_type,
                        prompt=q.prompt,
                        answers=q.answers,
                        correct_answer=q.correct_answer,
                        correct_index=q.correct_index,
                        model_response=response,
                        model_selected_index=selected_index,
                        is_correct=is_correct,
                    )
                    video_results.append(result)

                except Exception as e:
                    print(f"[GPU {gpu_id}] [{get_time()}] Error on question: {e}")
                    torch.cuda.empty_cache()
                    continue
                finally:
                    torch.cuda.empty_cache()


            if video_results:
                checkpoint_data = {
                    "video_name": video_name,
                    "gpu_id": gpu_id,
                    "timestamp": datetime.now().isoformat(),
                    "num_questions": len(video_results),
                    "num_correct": video_correct,
                    "results": [asdict(r) for r in video_results]
                }

                with open(checkpoint_path, 'a') as f:
                    f.write(json.dumps(checkpoint_data) + '\n')

                total_questions += len(video_results)
                total_correct += video_correct

                acc = video_correct / len(video_results) * 100
                print(f"[GPU {gpu_id}] [{get_time()}] Completed {video_name}: {video_correct}/{len(video_results)} ({acc:.1f}%)")
                sys.stdout.flush()

    finally:
        print(f"[GPU {gpu_id}] [{get_time()}] Unloading model...")
        model_loader.unload()
        torch.cuda.empty_cache()


    overall_acc = (total_correct / total_questions * 100) if total_questions > 0 else 0
    print(f"[GPU {gpu_id}] [{get_time()}] FINISHED: {len(video_names)} videos, {total_questions} questions, {total_correct} correct ({overall_acc:.1f}%)")
    sys.stdout.flush()


if __name__ == "__main__":
    main()

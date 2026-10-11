"""
Evaluation runner with support for:
- Multiple VLM families (Ovis, Qwen, InternVL, NVILA, etc.)
- Frame caching
- Async prefetching
- Hardware-accelerated decoding
- Multi-GPU support (via parallel_runner or device_map)
"""
import argparse
import json
import sys
from pathlib import Path

from .model_loader.base import ModelConfig
from .model_loader.registry import resolve_model_path
from .video_processor import VideoProcessorConfig
from .evaluator import VideoQuestionEvaluator, save_evaluation_results


def load_annotations(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        if "annotations" in data:
            return data["annotations"]
        return [data]
    else:
        raise ValueError(f"Unexpected JSON structure in {path}")


def progress_printer(current: int, total: int, result) -> None:
    status = "CORRECT" if result.is_correct else "WRONG"
    if result.error:
        status = f"ERROR: {result.error}"

    print(f"[{current}/{total}] {result.video_name}")
    print(f"  Type: {result.question_type}")
    print(f"  Question: {result.prompt}")
    print(f"  Answer Options:")
    for i, answer in enumerate(result.answers):
        marker = "+" if i == result.correct_index else " "
        selected = "<-" if i == result.model_selected_index else ""
        print(f"    {marker} {i + 1}. {answer} {selected}")
    print(f"  Model Response: {result.model_response}")
    print(f"  Status: {status}")
    print()


def checkpoint_progress_printer(
    current: int,
    total: int,
    result,
    video_name=None,
    question_num=None,
    total_questions=None,
    status=None
) -> None:

    if status == "starting":
        print(f"\n[{current}/{total}] {video_name} - Processing questions...")
    elif status == "completed":
        print(f"  + Completed - Checkpoint saved")
    elif result is not None:
        status_symbol = "+" if result.is_correct else "x"
        if question_num == 1:
            print(f"  ", end="")
        print(status_symbol, end="")
        if question_num % 10 == 0 or question_num == total_questions:
            print(f" [{question_num}/{total_questions}]")
        sys.stdout.flush()


def detect_model_family(model_path: str) -> str:

    path_lower = model_path.lower()
    if "qwen" in path_lower and "vl" in path_lower:
        return "Qwen VL"
    elif "internvl" in path_lower:
        return "InternVL"
    elif "ovis" in path_lower:
        return "Ovis"
    elif "nvila" in path_lower or "longvila" in path_lower:
        return "NVILA"
    elif "vila" in path_lower:
        return "VILA"
    elif "minicpm" in path_lower:
        return "MiniCPM"
    elif "llama" in path_lower and "vision" in path_lower:
        return "Llama Vision"
    elif "phi" in path_lower:
        return "Phi Vision"
    return "Unknown"


def run_evaluation(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate vision-language models on video questions"
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
        "-n",
        "--num-questions",
        type=int,
        default=10,
        help="Number of questions to evaluate (default: 10)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="Directory for output JSON file (default: current directory)",
    )
    parser.add_argument(
        "-m",
        "--model-path",
        default="AIDC-AI/Ovis2.5-9B",
        help="HuggingFace model path (default: AIDC-AI/Ovis2.5-9B)",
    )
    parser.add_argument(
        "-f",
        "--num-frames",
        type=int,
        default=8,
        help="Number of frames to extract from each video (default: 8)",
    )
    parser.add_argument(
        "-d",
        "--num-distractors",
        type=int,
        default=7,
        help="Number of distractor answers per question (default: 7, giving 8 total options)",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=256,
        help="Thinking budget for Ovis models (default: 256)",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=128,
        help="Max new tokens for generation (default: 128)",
    )
    parser.add_argument(
        "--image-size",
        type=int,
        default=448,
        help="Image resize dimension (default: 448)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check video/annotation matching, don't run evaluation",
    )
    parser.add_argument(
        "--all-questions",
        action="store_true",
        help="Generate all question types for all videos (ignores -n)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh evaluation, ignoring existing checkpoint",
    )
    parser.add_argument(
        "--questions-json",
        type=str,
        default=None,
        help="Path to pre-generated questions JSON file (skips question generation)",
    )

    parser.add_argument(
        "-g",
        "--num-gpus",
        type=int,
        default=1,
        help="Number of GPUs for parallel evaluation (default: 1)",
    )
    parser.add_argument(
        "--device-map",
        type=str,
        default=None,
        help="Device map for large models: 'auto', 'balanced', or None (default: None)",
    )
    parser.add_argument(
        "--dtype",
        type=str,
        default="bfloat16",
        choices=["float16", "bfloat16", "float32"],
        help="Model data type (default: bfloat16)",
    )


    parser.add_argument(
        "--no-torch-compile",
        action="store_true",
        help="Disable torch.compile optimization",
    )
    parser.add_argument(
        "--no-flash-attention",
        action="store_true",
        help="Disable flash attention",
    )
    parser.add_argument(
        "--no-async",
        action="store_true",
        help="Disable async frame prefetching",
    )
    parser.add_argument(
        "--no-fast-video",
        action="store_true",
        help="Disable hardware-accelerated video decoding (use OpenCV)",
    )
    parser.add_argument(
        "--no-batching",
        action="store_true",
        help="Disable batch inference",
    )
    parser.add_argument(
        "--prefetch-count",
        type=int,
        default=2,
        help="Number of videos to prefetch (default: 2)",
    )
    parser.add_argument(
        "--black-frames",
        action="store_true",
        help="Feed the model solid black frames instead of real video frames (sanity check for cheating)",
    )

    parsed = parser.parse_args(args)

    try:
        annotations = load_annotations(parsed.annotations_json)
    except FileNotFoundError:
        print(f"Error: File not found: {parsed.annotations_json}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    video_dir = Path(parsed.video_dir)
    if not video_dir.exists():
        print(f"Error: Video directory not found: {video_dir}", file=sys.stderr)
        sys.exit(1)


    parsed.model_path = resolve_model_path(parsed.model_path)


    model_family = detect_model_family(parsed.model_path)
    is_ovis = "ovis" in parsed.model_path.lower()

    if parsed.num_gpus > 1:
        if not parsed.all_questions:
            print("Error: Multi-GPU mode requires --all-questions flag", file=sys.stderr)
            sys.exit(1)

        from .parallel_runner import run_parallel_evaluation

        print(f"Running parallel evaluation across {parsed.num_gpus} GPUs...")
        print(f"Model: {parsed.model_path} ({model_family})")
        run_parallel_evaluation(
            annotations_path=parsed.annotations_json,
            video_dir=parsed.video_dir,
            output_dir=parsed.output_dir,
            num_gpus=parsed.num_gpus,
            model_path=parsed.model_path,
            num_frames=parsed.num_frames,
            num_distractors=parsed.num_distractors,
            thinking_budget=parsed.thinking_budget,
            max_new_tokens=parsed.max_new_tokens,
        )
        return


    model_config = ModelConfig(
        model_path=parsed.model_path,
        max_new_tokens=parsed.max_new_tokens,
        image_size=(parsed.image_size, parsed.image_size),
        dtype=parsed.dtype,
        device_map=parsed.device_map,
        use_torch_compile=not parsed.no_torch_compile,
        use_flash_attention=not parsed.no_flash_attention,
        enable_batching=not parsed.no_batching,
        enable_thinking=is_ovis,
        thinking_budget=parsed.thinking_budget if is_ovis else 0,
    )

    video_config = VideoProcessorConfig(
        num_frames=parsed.num_frames,
        prefetch_count=parsed.prefetch_count,
        use_black_frames=parsed.black_frames,
    )

    print("=" * 60)
    print("MULTI-MODEL VLM EVALUATION RUNNER")
    print("=" * 60)
    print(f"Model: {parsed.model_path}")
    print(f"Model family: {model_family}")
    print(f"Data type: {parsed.dtype}")
    print(f"Device map: {parsed.device_map or 'single GPU'}")
    print(f"Video directory: {video_dir}")
    print(f"Total annotations: {len(annotations)} entries")
    print(f"Frames per video: {parsed.num_frames}")
    print(f"Image size: {parsed.image_size}x{parsed.image_size}")
    print()
    print("Optimizations:")
    print(f"  torch.compile: {'ON' if not parsed.no_torch_compile else 'OFF'}")
    print(f"  Flash attention: {'ON' if not parsed.no_flash_attention else 'OFF'}")
    print(f"  Async prefetch: {'ON' if not parsed.no_async else 'OFF'}")
    print(f"  Fast video decode: {'ON' if not parsed.no_fast_video else 'OFF'}")
    print(f"  Batch inference: {'ON' if not parsed.no_batching else 'OFF'}")
    if is_ovis:
        print(f"  Thinking budget: {parsed.thinking_budget}")
    print(f"  Max new tokens: {parsed.max_new_tokens}")
    print(f"  Black frames (sanity check): {'ON' if parsed.black_frames else 'OFF'}")
    print()

    if parsed.all_questions:
        print("Mode: ALL QUESTIONS on ALL VIDEOS")
    else:
        print(f"Questions to evaluate: {parsed.num_questions}")
    print()

    print("Scanning video directory and matching with annotations...")

    evaluator = VideoQuestionEvaluator(
        annotations=annotations,
        video_dir=video_dir,
        model_config=model_config,
        video_config=video_config,
        num_distractors=parsed.num_distractors,
        use_async_loading=not parsed.no_async,
        use_fast_video=not parsed.no_fast_video,
    )

    print()

    if parsed.check_only:
        stats = evaluator.get_availability_stats()
        print("=" * 60)
        print("VIDEO AVAILABILITY CHECK")
        print("=" * 60)
        print(f"Total videos in directory: {stats['total_videos_in_dir']}")
        print(f"Total annotations provided: {len(annotations)}")
        print(f"Matched annotations with videos: {stats['matched']}")
        print(f"\nReady to evaluate {stats['matched']} video(s)")
        print("\nTo run evaluation, remove --check-only flag")
        return

    print(f"Loading {model_family} model (this may take a moment)...")
    evaluator.load_model()
    print("Model loaded successfully.")


    try:
        mem = evaluator.get_memory_usage()
        if "allocated_mb" in mem:
            print(f"GPU memory allocated: {mem['allocated_mb']:.0f} MB")
    except (AttributeError, TypeError):
        pass
    print()

    progress_cb = None if parsed.quiet else progress_printer

    try:
        if parsed.all_questions:
            output_dir = Path(parsed.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            checkpoint_path = None
            output_path = None

            if not parsed.no_resume:
                existing_checkpoints = sorted(output_dir.glob("evaluation_*.checkpoint.jsonl"))
                if existing_checkpoints:
                    checkpoint_path = existing_checkpoints[-1]
                    timestamp_from_checkpoint = checkpoint_path.stem.replace(".checkpoint", "")
                    output_path = output_dir / f"{timestamp_from_checkpoint}.json"
                    print(f"Found existing checkpoint: {checkpoint_path}")

            if checkpoint_path is None:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                model_short = parsed.model_path.split("/")[-1].replace("-", "_")
                checkpoint_path = output_dir / f"evaluation_{model_short}_{timestamp}.checkpoint.jsonl"
                output_path = output_dir / f"evaluation_{model_short}_{timestamp}.json"
                if parsed.no_resume:
                    print(f"Starting fresh evaluation (--no-resume)")
                else:
                    print(f"No existing checkpoint found, starting new evaluation")

            checkpoint_cb = None if parsed.quiet else checkpoint_progress_printer

            print(f"Checkpoint file: {checkpoint_path}")
            print(f"Output file: {output_path}")
            print()


            if parsed.questions_json:
                print(f"Using pre-generated questions from: {parsed.questions_json}")
                print()
                results = evaluator.evaluate_from_pregenerated(
                    questions_json_path=parsed.questions_json,
                    checkpoint_path=checkpoint_path,
                    output_path=output_path,
                    resume=not parsed.no_resume,
                    max_retries=3,
                    progress_callback=checkpoint_cb,
                )
            else:
                results = evaluator.evaluate_all_with_checkpoint(
                    checkpoint_path=checkpoint_path,
                    output_path=output_path,
                    resume=not parsed.no_resume,
                    max_retries=3,
                    progress_callback=checkpoint_cb,
                )

            print()
            print("=" * 60)
            print("EVALUATION SUMMARY")
            print("=" * 60)
            print(f"Model: {results['model_path']}")
            print(f"Model family: {model_family}")
            print(f"Total videos evaluated: {results['total_videos_evaluated']}")
            print(f"Total questions: {results['total_questions']}")
            print(f"Correct: {results['correct_count']}")
            print(f"Overall accuracy: {results['accuracy']:.2%}")
            print()
            print("Accuracy by question type:")
            for qtype, stats in sorted(results['accuracy_by_type'].items()):
                print(f"  {qtype}: {stats['correct']}/{stats['total']} ({stats['accuracy']:.2%})")
            print()
            print(f"Results saved to: {output_path}")
            print(f"Checkpoint saved to: {checkpoint_path}")

            return

        else:
            summary = evaluator.evaluate_random(
                num_questions=parsed.num_questions,
                progress_callback=progress_cb,
            )
    finally:
        evaluator.unload_model()

    output_file = save_evaluation_results(summary, parsed.output_dir)

    print("=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Model: {summary.model_path}")
    print(f"Model family: {model_family}")
    print(f"Total questions: {summary.total_questions}")
    print(f"Correct: {summary.correct_count}")
    print(f"Overall accuracy: {summary.accuracy:.2%}")
    print()
    print("Accuracy by question type:")
    for qtype, stats in sorted(summary.accuracy_by_type.items()):
        print(f"  {qtype}: {stats['correct']}/{stats['total']} ({stats['accuracy']:.2%})")
    print()
    print(f"Results saved to: {output_file}")


if __name__ == "__main__":
    run_evaluation()
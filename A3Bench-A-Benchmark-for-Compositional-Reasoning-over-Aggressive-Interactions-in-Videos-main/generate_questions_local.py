#!/usr/bin/env python3
"""
Standalone question generation script -- no model or GPU required.
Run locally to pre-generate the questions JSON for later evaluation.

Version 2.0: Uses category-based distribution (Simple, Compound, Complex, Counting,
Identification) for comprehensive evaluation across question difficulty levels.

Usage:
    python generate_questions_local.py annotations.json
    python generate_questions_local.py annotations.json -o my_questions.json
    python generate_questions_local.py annotations.json -d 7
    python generate_questions_local.py annotations.json --sample 0.5
    python generate_questions_local.py annotations.json --sample 20 --seed 42
"""
import sys
import os


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prompt_generator.hardness import (
    DEFAULT_RECIPES,
    HardnessRecipe,
    apply_hardness_profile,
)
from prompt_generator.generator import QuestionGenerator
from prompt_generator.templates import (
    QuestionType,
    QuestionCategory,
    QUESTIONS_PER_CATEGORY,
    QUESTION_CATEGORIES,
    SECONDARY_QUESTION_TYPES,
)
from prompt_generator.distribution import CategoryDistributor

import argparse
import json
import math
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path


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


def sample_annotations(
    annotations: list[dict],
    sample: float | int | None,
    seed: int | None,
) -> list[dict]:

    if sample is None:
        return annotations

    n = len(annotations)
    if isinstance(sample, float):
        count = max(1, math.ceil(n * sample))
    else:
        count = min(int(sample), n)

    rng = random.Random(seed)
    return rng.sample(annotations, count)


def _load_custom_recipes(path: str) -> dict[str, HardnessRecipe]:

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Custom recipe file {path!r} must be a top-level object")
    out = dict(DEFAULT_RECIPES)
    for qtype, counts in raw.items():
        if not isinstance(counts, dict):
            raise ValueError(f"Recipe for {qtype!r} must be an object, got {type(counts).__name__}")
        out[qtype] = HardnessRecipe({str(k): int(v) for k, v in counts.items()})
    return out


def _split_into_parts(
    output: dict,
    output_path: Path,
    num_parts: int,
) -> list[Path]:

    videos = list(output["questions_by_video"].items())
    total = len(videos)

    base, extra = divmod(total, num_parts)
    written: list[Path] = []
    cursor = 0
    for i in range(num_parts):
        size = base + (1 if i < extra else 0)
        chunk = dict(videos[cursor:cursor + size])
        cursor += size
        chunk_questions = [q for qs in chunk.values() for q in qs]

        part_meta = dict(output["metadata"])
        part_meta["num_videos"] = len(chunk)
        part_meta["num_questions"] = len(chunk_questions)
        part_meta["split"] = {"part": i + 1, "total": num_parts}

        part_output = {
            "metadata": part_meta,
            "questions_by_video": chunk,
        }

        part_path = output_path.with_name(
            f"{output_path.stem}_part{i + 1}of{num_parts}{output_path.suffix}"
        )
        with open(part_path, "w", encoding="utf-8") as f:
            json.dump(part_output, f, indent=2, ensure_ascii=False)
        written.append(part_path)
    return written


def generate_questions_for_all_videos(
    annotations_path: str,
    output_path: str,
    num_distractors: int = 7,
    trick_probability: float = 0.0,
    sample: float | int | None = None,
    seed: int | None = None,
    hardness_profile: str = "balanced",
    recipe_path: str | None = None,
    split: int = 1,
) -> dict:

    annotations = load_annotations(annotations_path)
    print(f"Loaded {len(annotations)} annotations")


    if hardness_profile == "custom":
        if not recipe_path:
            raise ValueError("--hardness-profile custom requires --recipe PATH")
        base_recipes = _load_custom_recipes(recipe_path)
        recipes = apply_hardness_profile(base_recipes, "custom")
    else:
        recipes = apply_hardness_profile(DEFAULT_RECIPES, hardness_profile)


    generator = QuestionGenerator(annotations, num_distractors=num_distractors, trick_probability=trick_probability, recipes=recipes)
    distributor = CategoryDistributor()


    subset = sample_annotations(annotations, sample, seed)
    if sample is not None:
        print(f"Prototype mode: generating questions for {len(subset)}/{len(annotations)} videos"
              + (f" (seed={seed})" if seed is not None else ""))

    all_questions = []
    skipped_count = 0
    category_counts = defaultdict(int)
    type_counts = defaultdict(int)

    total = len(subset)
    for idx, entry in enumerate(subset, 1):
        video_name = entry.get("video_name") or entry.get("file_name", "unknown")
        print(f"\r[{idx}/{total}] Generating questions for: {video_name}", end="", flush=True)

        video_questions = generator.generate_distributed_questions_for_video(
            entry, distributor
        )

        for question in video_questions:
            question_dict = {
                "video_name": question.video_name,
                "question_type": question.question_type,
                "is_secondary": question.question_type in SECONDARY_QUESTION_TYPES,
                "is_trick": question.is_trick,
                "prompt": question.prompt,
                "answers": question.answers,
                "correct_answer": question.correct_answer,
                "correct_index": question.correct_index,
                "option_hardness": getattr(question, "option_hardness", None),
            }
            all_questions.append(question_dict)


            qtype = QuestionType(question.question_type)
            category = QUESTION_CATEGORIES.get(qtype)
            if category:
                category_counts[category.value] += 1
            type_counts[question.question_type] += 1

    print()


    questions_by_video = {}
    for q in all_questions:
        video = q["video_name"]
        if video not in questions_by_video:
            questions_by_video[video] = []
        questions_by_video[video].append(q)


    num_videos = len(subset)
    expected_per_category = {
        cat.value: num_videos * count
        for cat, count in QUESTIONS_PER_CATEGORY.items()
    }

    print("\n" + "=" * 60)
    print("DISTRIBUTION VALIDATION")
    print("=" * 60)
    for category, expected in sorted(expected_per_category.items()):
        actual = category_counts[category]
        deviation = abs(actual - expected) / expected if expected > 0 else 0
        status = "OK  " if deviation < 0.05 else "WARN"
        print(f"  {status} {category:12s}: {actual:5d}/{expected:5d} ({deviation:6.1%} deviation)")

    output = {
        "metadata": {
            "version": "2.0",
            "generation_method": "category_distribution",
            "num_videos": len(questions_by_video),
            "num_questions": len(all_questions),
            "num_distractors": num_distractors,
            "trick_probability": trick_probability,
            "prototype_mode": sample is not None,
            "sample": sample,
            "seed": seed,
            "total_annotations": len(annotations),
            "hardness_profile": hardness_profile,
            "distribution_config": {
                cat.value: count for cat, count in QUESTIONS_PER_CATEGORY.items()
            },
            "category_counts": dict(category_counts),
            "question_counts_by_type": dict(type_counts),
            "skipped_questions": skipped_count,
        },
        "questions_by_video": questions_by_video,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if split and split > 1:
        num_videos_out = len(questions_by_video)
        if split > num_videos_out:
            raise ValueError(
                f"--split {split} exceeds number of videos with questions "
                f"({num_videos_out}); nothing would be written for some parts"
            )
        written = _split_into_parts(output, output_path, split)
        print(f"\nSplit into {split} parts:")
        for p in written:
            print(f"  {p}")
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("GENERATION SUMMARY")
    print("=" * 60)
    print(f"  Videos: {len(questions_by_video)}")
    print(f"  Total questions: {len(all_questions)}")
    if questions_by_video:
        print(f"  Questions per video: {len(all_questions) / len(questions_by_video):.1f}")
    print(f"\nQuestions by category:")
    for category in sorted(category_counts.keys()):
        count = category_counts[category]
        print(f"  {category:12s}: {count:5d}")
    print(f"\nQuestions by type:")
    for qtype, count in sorted(type_counts.items()):
        print(f"  {qtype:40s}: {count:5d}")
    if not (split and split > 1):
        print(f"\nSaved to: {output_path}")

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Pre-generate questions for all videos (no model/GPU required)"
    )
    parser.add_argument(
        "annotations_json",
        help="Path to JSON file containing video annotations",
    )
    parser.add_argument(
        "-o", "--output",
        default=f"generated_questions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        help="Output JSON file path (default: generated_questions_<timestamp>.json)",
    )
    parser.add_argument(
        "-d", "--num-distractors",
        type=int,
        default=7,
        help="Number of wrong answers per question (default: 7, giving 8 total options)",
    )
    parser.add_argument(
        "--trick-probability",
        type=float,
        default=0.10,
        help="Fraction of questions that are trick questions with a 'none' correct answer (default: 0.10)",
    )
    parser.add_argument(
        "--sample",
        type=float,
        default=None,
        help="Prototype mode: fraction (0, 1] or whole number of videos to sample "
             "(e.g. 0.5 for half, 20 for 20 videos)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible sampling (only used with --sample)",
    )
    parser.add_argument(
        "--hardness-profile",
        choices=["easy", "balanced", "hard", "custom", "frequency_inverted"],
        default="balanced",
        help=(
            "Difficulty profile for distractor generation. "
            "'custom' requires --recipe PATH. "
            "'frequency_inverted' (experimental) applies the standalone "
            "frequency-saturation layout to compound_aggressor_action_victim, "
            "interaction_summary, and sequence_verification; other qtypes "
            "use the hard distractor mix underneath."
        ),
    )
    parser.add_argument(
        "--recipe",
        default=None,
        help="Path to a JSON file of per-qtype HardnessRecipe overrides "
             "(only used with --hardness-profile custom). Schema: "
             "{'<qtype>': {'<category>': <count>, ...}, ...}",
    )
    parser.add_argument(
        "--split",
        type=int,
        default=1,
        help="Split the output across N files (partitioned by video, "
             "balanced). With --split 3 and -o foo.json, writes "
             "foo_part1of3.json, foo_part2of3.json, foo_part3of3.json. "
             "Each part is a self-contained JSON so it can go straight to "
             "text_only_eval.py or the frame-based eval pipeline. After "
             "evaluating all parts, merge results with combine_eval_results.py.",
    )

    args = parser.parse_args()


    sample = args.sample
    if sample is not None and sample >= 1:
        sample = int(sample)

    if args.hardness_profile == "custom" and not args.recipe:
        parser.error("--hardness-profile custom requires --recipe PATH")
    if args.split < 1:
        parser.error("--split must be >= 1")

    try:
        generate_questions_for_all_videos(
            args.annotations_json,
            args.output,
            args.num_distractors,
            trick_probability=args.trick_probability,
            sample=sample,
            seed=args.seed,
            hardness_profile=args.hardness_profile,
            recipe_path=args.recipe,
            split=args.split,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

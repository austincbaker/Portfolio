"""
Pre-generate questions for all videos and save to a static JSON file.
This allows reusing the same questions across different models.

Version 2.0: Uses category-based distribution (Simple, Compound, Complex, Counting,
Identification) for comprehensive evaluation across question difficulty levels.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from .generator import QuestionGenerator
from .templates import (
    QuestionType,
    QuestionCategory,
    QUESTIONS_PER_CATEGORY,
    QUESTION_CATEGORIES,
)
from .distribution import CategoryDistributor


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
        raise ValueError(f"Unexpected data format in {path}")


def generate_questions_for_all_videos(
    annotations_path: str,
    output_path: str,
    num_distractors: int = 7,
    trick_probability: float = 0.10,
) -> dict:


    annotations = load_annotations(annotations_path)
    print(f"Loaded {len(annotations)} annotations")


    generator = QuestionGenerator(annotations, num_distractors=num_distractors, trick_probability=trick_probability)
    distributor = CategoryDistributor()


    all_questions = []
    skipped_count = 0
    category_counts = defaultdict(int)
    type_counts = defaultdict(int)

    for entry in annotations:
        video_name = entry.get("file_name", entry.get("video_name", "unknown"))


        video_questions = generator.generate_distributed_questions_for_video(
            entry, distributor
        )

        for question in video_questions:
            question_dict = {
                "video_name": question.video_name,
                "question_type": question.question_type,
                "is_trick": question.is_trick,
                "prompt": question.prompt,
                "answers": question.answers,
                "correct_answer": question.correct_answer,
                "correct_index": question.correct_index,
            }
            all_questions.append(question_dict)


            qtype = QuestionType(question.question_type)
            category = QUESTION_CATEGORIES.get(qtype)
            if category:
                category_counts[category.value] += 1
            type_counts[question.question_type] += 1


    questions_by_video = {}
    for q in all_questions:
        video = q["video_name"]
        if video not in questions_by_video:
            questions_by_video[video] = []
        questions_by_video[video].append(q)


    num_videos = len(annotations)
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
        status = "✓" if deviation < 0.05 else "⚠"
        print(f"  {status} {category:12s}: {actual:5d}/{expected:5d} ({deviation:6.1%} deviation)")


    output = {
        "metadata": {
            "version": "2.0",
            "generation_method": "category_distribution",
            "num_videos": len(questions_by_video),
            "num_questions": len(all_questions),
            "num_distractors": num_distractors,
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

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("GENERATION SUMMARY")
    print("=" * 60)
    print(f"  Videos: {len(questions_by_video)}")
    print(f"  Total questions: {len(all_questions)}")
    print(f"  Questions per video: {len(all_questions) / len(questions_by_video):.1f}")
    print(f"\nQuestions by category:")
    for category in sorted(category_counts.keys()):
        count = category_counts[category]
        print(f"  {category:12s}: {count:5d}")
    print(f"\nQuestions by type:")
    for qtype, count in sorted(type_counts.items()):
        print(f"  {qtype:40s}: {count:5d}")
    print(f"\nSaved to: {output_path}")

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Pre-generate questions for all videos"
    )
    parser.add_argument(
        "annotations_json",
        help="Path to JSON file containing video annotations",
    )
    parser.add_argument(
        "-o", "--output",
        default="generated_questions.json",
        help="Output JSON file path (default: generated_questions.json)",
    )
    parser.add_argument(
        "-d", "--num-distractors",
        type=int,
        default=7,
        help="Number of distractor answers per question (default: 7, giving 8 total options)",
    )
    parser.add_argument(
        "-t", "--trick-probability",
        type=float,
        default=0.10,
        help="Probability of generating trick questions (default: 0.10)",
    )

    args = parser.parse_args()

    try:
        generate_questions_for_all_videos(
            args.annotations_json,
            args.output,
            args.num_distractors,
            args.trick_probability,
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

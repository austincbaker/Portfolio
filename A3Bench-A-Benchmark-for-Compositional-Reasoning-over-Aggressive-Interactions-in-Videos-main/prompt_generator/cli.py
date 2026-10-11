import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .generator import QuestionGenerator, GeneratedQuestion


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


def format_question_for_display(q: GeneratedQuestion, index: int) -> str:
    lines = [
        f"Question {index + 1}: [{q.video_name}]",
        f"Type: {q.question_type}",
        f"Prompt: {q.prompt}",
        "Answers:",
    ]
    for i, answer in enumerate(q.answers):
        marker = "*" if i == q.correct_index else " "
        lines.append(f"  {marker} {i + 1}. {answer}")
    lines.append(f"Correct: Option {q.correct_index + 1}")
    lines.append("")
    return "\n".join(lines)


def save_output(questions: list[GeneratedQuestion], output_dir: str) -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"questions_{timestamp}.json"
    filepath = output_path / filename

    output_data = {
        "generated_at": datetime.now().isoformat(),
        "total_questions": len(questions),
        "questions": [asdict(q) for q in questions],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    return str(filepath)


def run_cli(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate multiple-choice questions from video annotations"
    )
    parser.add_argument(
        "input_json",
        help="Path to JSON file containing video annotations",
    )
    parser.add_argument(
        "-n",
        "--num-questions",
        type=int,
        default=10,
        help="Number of questions to generate (default: 10)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="Directory for output JSON file (default: current directory)",
    )
    parser.add_argument(
        "-d",
        "--num-distractors",
        type=int,
        default=7,
        help="Number of distractor answers per question (default: 7, giving 8 total options)",
    )
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Allow duplicate video/question type combinations",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress stdout output (only save to file)",
    )

    parsed = parser.parse_args(args)

    try:
        annotations = load_annotations(parsed.input_json)
    except FileNotFoundError:
        print(f"Error: File not found: {parsed.input_json}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {parsed.input_json}: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not annotations:
        print("Error: No annotations found in input file", file=sys.stderr)
        sys.exit(1)

    generator = QuestionGenerator(annotations, num_distractors=parsed.num_distractors)
    questions = generator.generate_questions(
        count=parsed.num_questions,
        allow_duplicates=parsed.allow_duplicates,
    )

    if not questions:
        print("Error: Could not generate any questions from annotations", file=sys.stderr)
        sys.exit(1)

    output_file = save_output(questions, parsed.output_dir)

    if not parsed.quiet:
        print(f"Generated {len(questions)} questions")
        print(f"Saved to: {output_file}")
        print("-" * 60)
        for i, q in enumerate(questions):
            print(format_question_for_display(q, i))

    print(f"\nOutput saved to: {output_file}")
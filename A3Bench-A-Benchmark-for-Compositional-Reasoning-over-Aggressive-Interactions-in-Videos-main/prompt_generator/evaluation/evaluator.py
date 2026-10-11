"""
Optimized video question evaluator with frame caching and async prefetching.
"""
import re
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict
from typing import Optional, Callable


from ..generator import GeneratedQuestion
from ..templates import SECONDARY_QUESTION_TYPES
from .model_loader import ModelConfig, create_loader
from .video_processor import (
    VideoProcessor,
    VideoProcessorConfig,
    FastVideoProcessor,
    AsyncFrameLoader,
    create_video_processor
)


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
    model_selected_index: int | None
    is_correct: bool
    error: str | None = None


@dataclass
class EvaluationSummary:
    total_questions: int
    correct_count: int
    accuracy: float
    accuracy_by_type: dict[str, dict]
    results: list[EvaluationResult]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    model_path: str = ""
    num_frames: int = 8


def _compute_type_stats(results: list) -> dict:

    by_type = defaultdict(lambda: {"total": 0, "correct": 0})
    for r in results:
        by_type[r.question_type]["total"] += 1
        if r.is_correct:
            by_type[r.question_type]["correct"] += 1
    return {
        qtype: {
            "total": counts["total"],
            "correct": counts["correct"],
            "accuracy": counts["correct"] / counts["total"] if counts["total"] > 0 else 0.0,
        }
        for qtype, counts in by_type.items()
    }


class VideoQuestionEvaluator:
    """
    Optimized video question evaluator with:
    - Frame caching per video (extracts once, reuses for all questions)
    - Async frame prefetching
    - Batch inference support
    - Hardware-accelerated video decoding
    """

    def __init__(
        self,
        annotations: list[dict],
        video_dir: str | Path,
        model_config: ModelConfig | None = None,
        video_config: VideoProcessorConfig | None = None,
        num_distractors: int = 5,
        use_async_loading: bool = True,
        use_fast_video: bool = True,
    ):
        self.video_dir = Path(video_dir)
        self.model_config = model_config or ModelConfig()
        self.video_config = video_config or VideoProcessorConfig()
        self.num_distractors = num_distractors
        self.use_async_loading = use_async_loading


        self.available_videos = self._scan_available_videos()
        self.annotations, flattened_annotations = self._filter_annotations_by_videos(annotations)

        if not self.annotations:
            self._report_matching_error(flattened_annotations)
            raise ValueError(
                f"No videos found in {video_dir} matching annotation entries. "
                f"Found {len(self.available_videos)} videos in directory but none match annotations."
            )

        print(f"Found {len(self.available_videos)} videos in directory")
        print(f"Matched {len(self.annotations)} annotations with available videos")




        self.model_loader = create_loader(self.model_config)


        self.video_processor = create_video_processor(self.video_config, use_fast=use_fast_video)


        self.async_loader: Optional[AsyncFrameLoader] = None


        self._current_video_frames: Optional[tuple[str, list]] = None

    def _report_matching_error(self, flattened_annotations: list[dict]) -> None:

        print("\n" + "=" * 70, file=sys.stderr)
        print("ERROR: No matching videos found", file=sys.stderr)
        print("=" * 70, file=sys.stderr)

        sample_videos = sorted(list(self.available_videos))[:5]
        print(f"\nSample video filenames in directory ({len(self.available_videos)} total):", file=sys.stderr)
        for v in sample_videos:
            print(f"  - {v}", file=sys.stderr)

        sample_annotations = []
        for entry in flattened_annotations[:5]:
            if isinstance(entry, dict):
                sample_annotations.append(entry.get("video_name", "MISSING"))

        print(f"\nSample video names in annotations ({len(flattened_annotations)} total):", file=sys.stderr)
        for v in sample_annotations:
            print(f"  - {v}", file=sys.stderr)

        print("\nPossible issues:", file=sys.stderr)
        print("  1. File extension mismatch (.mp4 vs .avi vs no extension)", file=sys.stderr)
        print("  2. Different naming convention (underscores vs hyphens)", file=sys.stderr)
        print("  3. Wrong video directory path", file=sys.stderr)
        print("=" * 70, file=sys.stderr)

    def _scan_available_videos(self) -> set[str]:

        if not self.video_dir.exists():
            raise FileNotFoundError(f"Video directory not found: {self.video_dir}")

        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm'}
        available = set()

        for file in self.video_dir.iterdir():
            if file.is_file() and file.suffix.lower() in video_extensions:
                available.add(file.name)

        return available

    def _filter_annotations_by_videos(self, annotations: list[dict]) -> tuple[list[dict], list[dict]]:

        flattened_annotations = []
        for entry in annotations:
            if isinstance(entry, list):
                flattened_annotations.extend(entry)
            elif isinstance(entry, dict):
                flattened_annotations.append(entry)
            else:
                print(f"Warning: Unexpected annotation type: {type(entry)}", file=sys.stderr)
                continue

        filtered = []
        skipped = []

        for entry in flattened_annotations:
            if not isinstance(entry, dict):
                print(f"Warning: Skipping non-dict entry: {type(entry)}", file=sys.stderr)
                continue

            video_name = entry.get("video_name", "")
            if video_name in self.available_videos:
                filtered.append(entry)
            else:
                skipped.append(video_name)

        if skipped:
            print(f"Skipped {len(skipped)} annotations with missing videos")
            if len(skipped) <= 10:
                print(f"  Missing: {', '.join(skipped)}")

        return filtered, flattened_annotations

    def get_availability_stats(self) -> dict:

        return {
            "total_videos_in_dir": len(self.available_videos),
            "total_annotations": len(self.annotations),
            "matched": len(self.annotations),
            "available_videos": sorted(list(self.available_videos)),
        }

    def load_checkpoint(self, checkpoint_path: Path) -> dict[str, VideoCheckpoint]:

        completed = {}

        if not checkpoint_path.exists():
            return completed

        try:
            with open(checkpoint_path, 'r') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        checkpoint = VideoCheckpoint(**data)
                        if checkpoint.completed:
                            completed[checkpoint.video_name] = checkpoint
        except Exception as e:
            print(f"Warning: Error loading checkpoint: {e}", file=sys.stderr)
            print("Starting fresh evaluation", file=sys.stderr)
            return {}

        return completed

    def save_video_checkpoint(
        self,
        checkpoint_path: Path,
        video_name: str,
        results: list[EvaluationResult]
    ) -> None:

        checkpoint = VideoCheckpoint(
            video_name=video_name,
            timestamp=datetime.now().isoformat(),
            num_questions=len(results),
            results=[asdict(r) for r in results],
            completed=True
        )

        with open(checkpoint_path, 'a') as f:
            f.write(json.dumps(asdict(checkpoint)) + '\n')

    def convert_checkpoint_to_final(
        self,
        checkpoint_path: Path,
        output_path: Path
    ) -> dict:

        all_results = []
        video_stats = {}

        with open(checkpoint_path, 'r') as f:
            for line in f:
                if line.strip():
                    checkpoint = VideoCheckpoint(**json.loads(line))
                    for result_dict in checkpoint.results:
                        all_results.append(EvaluationResult(**result_dict))
                    video_stats[checkpoint.video_name] = {
                        'num_questions': checkpoint.num_questions,
                        'timestamp': checkpoint.timestamp
                    }

        summary = self._compute_summary(all_results)

        primary = [r for r in summary.results if r.question_type not in SECONDARY_QUESTION_TYPES]
        secondary = [r for r in summary.results if r.question_type in SECONDARY_QUESTION_TYPES]

        p_total = len(primary)
        p_correct = sum(1 for r in primary if r.is_correct)
        s_total = len(secondary)
        s_correct = sum(1 for r in secondary if r.is_correct)

        output_data = {
            "timestamp": summary.timestamp,
            "model_path": summary.model_path,
            "num_frames": summary.num_frames,
            "primary_total_questions": p_total,
            "primary_correct_count": p_correct,
            "primary_accuracy": p_correct / p_total if p_total > 0 else 0.0,
            "primary_accuracy_by_type": _compute_type_stats(primary),
            "secondary_total_questions": s_total,
            "secondary_correct_count": s_correct,
            "secondary_accuracy": s_correct / s_total if s_total > 0 else 0.0,
            "secondary_accuracy_by_type": _compute_type_stats(secondary),
            "total_videos_evaluated": len(video_stats),
            "video_stats": video_stats,
            "results": [asdict(r) for r in summary.results],
        }

        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        return output_data

    def load_model(self) -> None:
        self.model_loader.load()

        self.model_loader.warmup(num_frames=self.video_config.num_frames)

    def unload_model(self) -> None:
        self.model_loader.unload()
        if self.async_loader:
            self.async_loader.shutdown()
            self.async_loader = None

    def _get_frames_for_video(self, video_path: Path) -> list:

        video_key = str(video_path)


        if self._current_video_frames and self._current_video_frames[0] == video_key:
            return self._current_video_frames[1]


        if self.async_loader:
            return self.async_loader.get_frames(video_path)


        frames = self.video_processor.extract_frames(video_path)
        self._current_video_frames = (video_key, frames)
        return frames

    def _cache_frames_for_video(self, video_name: str, frames: list) -> None:

        video_key = str(self.video_dir / video_name)
        self._current_video_frames = (video_key, frames)

    def evaluate_question(
        self, question: GeneratedQuestion
    ) -> EvaluationResult:

        video_path = self.video_dir / question.video_name

        try:
            frames = self._get_frames_for_video(video_path)
        except (FileNotFoundError, RuntimeError) as e:
            return self._create_error_result(question, str(e))

        return self._evaluate_with_frames(question, frames)

    def evaluate_question_with_frames(
        self,
        question: GeneratedQuestion,
        frames: list
    ) -> EvaluationResult:

        return self._evaluate_with_frames(question, frames)

    def _evaluate_with_frames(
        self,
        question: GeneratedQuestion,
        frames: list
    ) -> EvaluationResult:

        formatted_prompt = self._format_prompt(question)

        try:
            response = self.model_loader.generate_response(frames, formatted_prompt)
        except Exception as e:
            return self._create_error_result(question, f"Model error: {str(e)}")

        selected_index = self._parse_model_response(response, question.answers)
        is_correct = selected_index == question.correct_index

        return EvaluationResult(
            video_name=question.video_name,
            question_type=question.question_type,
            prompt=question.prompt,
            answers=question.answers,
            correct_answer=question.correct_answer,
            correct_index=question.correct_index,
            model_response=response,
            model_selected_index=selected_index,
            is_correct=is_correct,
        )

    def _create_error_result(
        self,
        question: GeneratedQuestion,
        error: str
    ) -> EvaluationResult:

        return EvaluationResult(
            video_name=question.video_name,
            question_type=question.question_type,
            prompt=question.prompt,
            answers=question.answers,
            correct_answer=question.correct_answer,
            correct_index=question.correct_index,
            model_response="",
            model_selected_index=None,
            is_correct=False,
            error=error,
        )

    def evaluate_video_questions(
        self,
        video_name: str,
        questions: list[GeneratedQuestion],
        progress_callback: Optional[Callable] = None,
        video_num: int = 0,
        total_videos: int = 0,
    ) -> list[EvaluationResult]:

        video_path = self.video_dir / video_name


        try:
            frames = self.video_processor.extract_frames(video_path)
        except (FileNotFoundError, RuntimeError) as e:

            return [self._create_error_result(q, str(e)) for q in questions]


        self._cache_frames_for_video(video_name, frames)

        results = []


        if (self.model_config.enable_batching and
            len(questions) >= 2):
            results = self._evaluate_batch_with_frames(
                questions, frames, progress_callback, video_num, total_videos
            )
        else:

            for q_idx, question in enumerate(questions, start=1):
                result = self._evaluate_with_frames(question, frames)
                results.append(result)

                if progress_callback:
                    progress_callback(
                        video_num, total_videos, result,
                        video_name=video_name,
                        question_num=q_idx,
                        total_questions=len(questions)
                    )

        return results

    def _evaluate_batch_with_frames(
        self,
        questions: list[GeneratedQuestion],
        frames: list,
        progress_callback: Optional[Callable],
        video_num: int,
        total_videos: int,
    ) -> list[EvaluationResult]:


        prompts = [self._format_prompt(q) for q in questions]


        try:
            responses = self.model_loader.generate_responses_batch(frames, prompts)
        except Exception as e:

            results = []
            for q_idx, question in enumerate(questions, start=1):
                result = self._evaluate_with_frames(question, frames)
                results.append(result)
                if progress_callback:
                    progress_callback(
                        video_num, total_videos, result,
                        video_name=question.video_name,
                        question_num=q_idx,
                        total_questions=len(questions)
                    )
            return results


        results = []
        for q_idx, (question, response) in enumerate(zip(questions, responses), start=1):
            selected_index = self._parse_model_response(response, question.answers)
            is_correct = selected_index == question.correct_index

            result = EvaluationResult(
                video_name=question.video_name,
                question_type=question.question_type,
                prompt=question.prompt,
                answers=question.answers,
                correct_answer=question.correct_answer,
                correct_index=question.correct_index,
                model_response=response,
                model_selected_index=selected_index,
                is_correct=is_correct,
            )
            results.append(result)

            if progress_callback:
                progress_callback(
                    video_num, total_videos, result,
                    video_name=question.video_name,
                    question_num=q_idx,
                    total_questions=len(questions)
                )

        return results

    def evaluate_batch(
        self,
        questions: list[GeneratedQuestion],
        progress_callback=None,
    ) -> EvaluationSummary:
        results = []

        for i, question in enumerate(questions):
            result = self.evaluate_question(question)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, len(questions), result)

        return self._compute_summary(results)












    def load_pregenerated_questions(self, questions_json_path: str) -> dict[str, list[dict]]:

        with open(questions_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        questions_by_video = data.get("questions_by_video", {})
        metadata = data.get("metadata", {})

        total_questions = sum(len(qs) for qs in questions_by_video.values())
        print(f"Loaded {total_questions} pre-generated questions from {questions_json_path}")
        print(f"  Videos: {metadata.get('num_videos', len(questions_by_video))}")
        print(f"  Question types: {', '.join(metadata.get('question_types', []))}")

        return questions_by_video

    def evaluate_from_pregenerated(
        self,
        questions_json_path: str,
        checkpoint_path: Path,
        output_path: Path,
        resume: bool = True,
        max_retries: int = 3,
        progress_callback=None,
    ) -> dict:


        questions_by_video = self.load_pregenerated_questions(questions_json_path)


        completed_videos = {}
        if resume:
            completed_videos = self.load_checkpoint(checkpoint_path)
            if completed_videos:
                print(f"Found checkpoint with {len(completed_videos)} completed videos")
                print(f"Resuming evaluation...")


        if resume and completed_videos:
            remaining_videos = {
                v: qs for v, qs in questions_by_video.items()
                if v not in completed_videos
            }
        else:
            remaining_videos = questions_by_video


        available_remaining = {}
        for video_name, questions in remaining_videos.items():
            if video_name in self.available_videos:
                available_remaining[video_name] = questions
            else:
                print(f"Warning: Skipping {video_name} - video file not found")

        remaining_videos = available_remaining

        total_videos = len(questions_by_video)
        completed_count = len(completed_videos)
        remaining_count = len(remaining_videos)

        print(f"\nTotal videos: {total_videos}")
        print(f"Completed: {completed_count}")
        print(f"Remaining: {remaining_count}")
        print()


        if self.use_async_loading and remaining_count > 1:
            self.async_loader = AsyncFrameLoader(
                self.video_processor,
                prefetch_count=self.video_config.prefetch_count,
                max_cache_size=3
            )


        video_list = sorted(remaining_videos.keys())


        failed_videos = []

        for video_idx, video_name in enumerate(video_list, start=1):
            question_dicts = remaining_videos[video_name]
            current_video_num = completed_count + video_idx


            if self.async_loader and video_idx < len(video_list):
                next_videos = [
                    self.video_dir / v
                    for v in video_list[video_idx:video_idx + 2]
                ]
                self.async_loader.prefetch_batch(next_videos)

            if progress_callback:
                progress_callback(current_video_num, total_videos, None,
                                video_name=video_name, status="starting")


            video_questions = []
            for q_dict in question_dicts:
                question = GeneratedQuestion(
                    video_name=q_dict["video_name"],
                    question_type=q_dict["question_type"],
                    prompt=q_dict["prompt"],
                    answers=q_dict["answers"],
                    correct_answer=q_dict["correct_answer"],
                    correct_index=q_dict["correct_index"],
                )
                video_questions.append(question)

            if not video_questions:
                print(f"  Warning: No questions for {video_name}", file=sys.stderr)
                continue


            retry_count = 0
            success = False
            video_results = []
            last_error = None

            while retry_count <= max_retries and not success:
                try:
                    video_results = self.evaluate_video_questions(
                        video_name,
                        video_questions,
                        progress_callback,
                        current_video_num,
                        total_videos,
                    )
                    success = True

                except Exception as e:
                    retry_count += 1
                    last_error = str(e)
                    if retry_count <= max_retries:
                        print(f"  Warning: Error on {video_name} (attempt {retry_count}/{max_retries}): {e}")
                        print(f"  Retrying...")
                    else:
                        print(f"  Failed {video_name} after {max_retries} retries: {e}")

            if success:
                self.save_video_checkpoint(checkpoint_path, video_name, video_results)

                if progress_callback:
                    progress_callback(current_video_num, total_videos, None,
                                    video_name=video_name, status="completed")
            else:
                failed_videos.append((video_name, last_error))
                print(f"  Skipping {video_name} after failed retries")


        if self.async_loader:
            self.async_loader.shutdown()
            self.async_loader = None


        print("\nConverting checkpoint to final JSON...")
        final_results = self.convert_checkpoint_to_final(checkpoint_path, output_path)

        if failed_videos:
            print(f"\nWarning: {len(failed_videos)} videos failed after retries:")
            for video_name, error in failed_videos:
                print(f"  - {video_name}: {error}")

        print(f"\nEvaluation complete!")
        print(f"Results saved to {output_path}")
        print(f"Checkpoint saved to {checkpoint_path}")

        return final_results

    def evaluate_all_with_checkpoint(
        self,
        checkpoint_path: Path,
        output_path: Path,
        resume: bool = True,
        max_retries: int = 3,
        progress_callback=None,
    ) -> dict:


        completed_videos = {}
        if resume:
            completed_videos = self.load_checkpoint(checkpoint_path)
            if completed_videos:
                print(f"Found checkpoint with {len(completed_videos)} completed videos")
                print(f"Resuming evaluation...")


        all_videos = {}
        for annotation in self.annotations:
            video_name = annotation.get('video_name')
            if video_name:
                if video_name not in all_videos:
                    all_videos[video_name] = []
                all_videos[video_name].append(annotation)


        if resume and completed_videos:
            remaining_videos = {
                v: anns for v, anns in all_videos.items()
                if v not in completed_videos
            }
        else:
            remaining_videos = all_videos

        total_videos = len(all_videos)
        completed_count = len(completed_videos)
        remaining_count = len(remaining_videos)

        print(f"\nTotal videos: {total_videos}")
        print(f"Completed: {completed_count}")
        print(f"Remaining: {remaining_count}")
        print()


        if self.use_async_loading and remaining_count > 1:
            self.async_loader = AsyncFrameLoader(
                self.video_processor,
                prefetch_count=self.video_config.prefetch_count,
                max_cache_size=3
            )


        video_list = sorted(remaining_videos.keys())


        failed_videos = []

        for video_idx, video_name in enumerate(video_list, start=1):
            video_annotations = remaining_videos[video_name]
            current_video_num = completed_count + video_idx


            if self.async_loader and video_idx < len(video_list):
                next_videos = [
                    self.video_dir / v
                    for v in video_list[video_idx:video_idx + 2]
                ]
                self.async_loader.prefetch_batch(next_videos)

            if progress_callback:
                progress_callback(current_video_num, total_videos, None,
                                video_name=video_name, status="starting")






            raise RuntimeError(
                f"On-the-fly question generation is disabled. "
                f"Pass a pre-generated questions JSON file instead."
            )

            if not video_questions:
                print(f"  Warning: No questions generated for {video_name}", file=sys.stderr)
                continue


            retry_count = 0
            success = False
            video_results = []
            last_error = None

            while retry_count <= max_retries and not success:
                try:
                    video_results = self.evaluate_video_questions(
                        video_name,
                        video_questions,
                        progress_callback,
                        current_video_num,
                        total_videos,
                    )
                    success = True

                except Exception as e:
                    retry_count += 1
                    last_error = str(e)
                    if retry_count <= max_retries:
                        print(f"  Warning: Error on {video_name} (attempt {retry_count}/{max_retries}): {e}")
                        print(f"  Retrying...")
                    else:
                        print(f"  Failed {video_name} after {max_retries} retries: {e}")

            if success:
                self.save_video_checkpoint(checkpoint_path, video_name, video_results)

                if progress_callback:
                    progress_callback(current_video_num, total_videos, None,
                                    video_name=video_name, status="completed")
            else:
                failed_videos.append((video_name, last_error))
                print(f"  Skipping {video_name} after failed retries")


        if self.async_loader:
            self.async_loader.shutdown()
            self.async_loader = None


        print("\nConverting checkpoint to final JSON...")
        final_results = self.convert_checkpoint_to_final(checkpoint_path, output_path)

        if failed_videos:
            print(f"\nWarning: {len(failed_videos)} videos failed after retries:")
            for video_name, error in failed_videos:
                print(f"  - {video_name}: {error}")

        print(f"\nEvaluation complete!")
        print(f"Results saved to {output_path}")
        print(f"Checkpoint saved to {checkpoint_path}")

        return final_results

    def _format_prompt(self, question: GeneratedQuestion) -> str:
        lines = [
            "Watch this video carefully and answer the following multiple-choice question.",
            "Select ONLY the number (1, 2, 3, etc.) of the correct answer.",
            "",
            f"Question: {question.prompt}",
            "",
            "Options:",
        ]

        for i, answer in enumerate(question.answers):
            lines.append(f"{i + 1}. {answer}")

        lines.extend([
            "",
            "Answer with ONLY the option number (e.g., '1' or '2').",
        ])

        return "\n".join(lines)

    def _parse_model_response(
        self, response: str, answers: list[str]
    ) -> int | None:
        response_clean = response.strip()

        single_digit = re.search(r"^(\d)$", response_clean)
        if single_digit:
            idx = int(single_digit.group(1)) - 1
            if 0 <= idx < len(answers):
                return idx

        patterns = [
            r"(?:answer|option|choice)[\s:]*(\d)",
            r"^(\d)\.",
            r"^\((\d)\)",
            r"(\d)(?:\s|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, response_clean, re.IGNORECASE)
            if match:
                idx = int(match.group(1)) - 1
                if 0 <= idx < len(answers):
                    return idx

        response_lower = response_clean.lower()
        for i, answer in enumerate(answers):
            if answer.lower() in response_lower:
                return i

        return None

    def _compute_summary(self, results: list[EvaluationResult]) -> EvaluationSummary:
        total = len(results)
        correct = sum(1 for r in results if r.is_correct)
        accuracy = correct / total if total > 0 else 0.0

        by_type = defaultdict(lambda: {"total": 0, "correct": 0})
        for r in results:
            by_type[r.question_type]["total"] += 1
            if r.is_correct:
                by_type[r.question_type]["correct"] += 1

        accuracy_by_type = {}
        for qtype, counts in by_type.items():
            t, c = counts["total"], counts["correct"]
            accuracy_by_type[qtype] = {
                "total": t,
                "correct": c,
                "accuracy": c / t if t > 0 else 0.0,
            }

        return EvaluationSummary(
            total_questions=total,
            correct_count=correct,
            accuracy=accuracy,
            accuracy_by_type=accuracy_by_type,
            results=results,
            model_path=self.model_config.model_path,
            num_frames=self.video_config.num_frames,
        )


def save_evaluation_results(
    summary: EvaluationSummary, output_dir: str | Path
) -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"evaluation_{timestamp}.json"
    filepath = output_path / filename

    primary = [r for r in summary.results if r.question_type not in SECONDARY_QUESTION_TYPES]
    secondary = [r for r in summary.results if r.question_type in SECONDARY_QUESTION_TYPES]

    p_total = len(primary)
    p_correct = sum(1 for r in primary if r.is_correct)
    s_total = len(secondary)
    s_correct = sum(1 for r in secondary if r.is_correct)

    output_data = {
        "timestamp": summary.timestamp,
        "model_path": summary.model_path,
        "num_frames": summary.num_frames,
        "primary_total_questions": p_total,
        "primary_correct_count": p_correct,
        "primary_accuracy": p_correct / p_total if p_total > 0 else 0.0,
        "primary_accuracy_by_type": _compute_type_stats(primary),
        "secondary_total_questions": s_total,
        "secondary_correct_count": s_correct,
        "secondary_accuracy": s_correct / s_total if s_total > 0 else 0.0,
        "secondary_accuracy_by_type": _compute_type_stats(secondary),
        "results": [asdict(r) for r in summary.results],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    return str(filepath)

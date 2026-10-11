"""
Category-based question distribution system.

This module provides the CategoryDistributor class which implements
a deterministic round-robin algorithm for distributing questions across
videos while ensuring even usage of all question types within each category.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

from .templates import (
    QuestionCategory,
    QuestionType,
    QUESTION_CATEGORIES,
    QUESTIONS_PER_CATEGORY,
    QUESTION_TEMPLATES,
)

if TYPE_CHECKING:
    from .generator import QuestionGenerator


class CategoryDistributor:
    """
    Distributes questions across videos using category-based round-robin selection.

    Ensures:
    - Even distribution of question types within each category
    - No duplicate question types per video
    - Deterministic results (same input -> same output)
    """

    def __init__(self):


        self.types_by_category = self._group_types_by_category()



        self.rotation_indices: dict[QuestionCategory, int] = {
            cat: 0 for cat in QuestionCategory
        }



        self.video_count = 0

    def _group_types_by_category(self) -> dict[QuestionCategory, list[QuestionType]]:

        groups: dict[QuestionCategory, list[QuestionType]] = defaultdict(list)

        for qtype, category in QUESTION_CATEGORIES.items():
            groups[category].append(qtype)


        return {
            cat: sorted(types, key=lambda t: t.value)
            for cat, types in groups.items()
        }

    def select_questions_for_video(
        self,
        entry: dict,
        generator: "QuestionGenerator",
    ) -> list[QuestionType]:

        selected: list[QuestionType] = []
        used_types: set[QuestionType] = set()


        for category in [
            QuestionCategory.SIMPLE,
            QuestionCategory.COMPOUND,
            QuestionCategory.COMPLEX,
            QuestionCategory.COUNTING,
            QuestionCategory.IDENTIFICATION,
        ]:
            num_needed = QUESTIONS_PER_CATEGORY[category]
            available_types = self.types_by_category[category]


            for _ in range(num_needed):
                attempts = 0
                max_attempts = len(available_types) * 2

                while attempts < max_attempts:

                    idx = self.rotation_indices[category] % len(available_types)
                    qtype = available_types[idx]
                    self.rotation_indices[category] += 1
                    attempts += 1


                    if qtype in used_types:
                        continue




                    if (
                        qtype == QuestionType.COMPOUND_AGGRESSOR_VICTIM
                        and self.video_count % 2 == 1
                    ):
                        continue

                    if self._can_generate(entry, qtype, generator):
                        selected.append(qtype)
                        used_types.add(qtype)
                        break
                else:
                    \
\
                    video_name = entry.get("file_name", entry.get("video_name", "unknown"))
                    print(
                        f"Warning: Could not find valid {category.value} question "
                        f"for {video_name}"
                    )

        self.video_count += 1
        return selected

    def _can_generate(
        self,
        entry: dict,
        qtype: QuestionType,
        generator: "QuestionGenerator",
    ) -> bool:

        if qtype == QuestionType.ROLE_IDENTIFICATION:
            return generator._can_generate_role_identification(entry)
        if qtype == QuestionType.SEQUENCE_VERIFICATION:
            return generator._can_generate_sequence_verification(entry)
        template = QUESTION_TEMPLATES[qtype]
        return generator._has_required_fields(entry, template)

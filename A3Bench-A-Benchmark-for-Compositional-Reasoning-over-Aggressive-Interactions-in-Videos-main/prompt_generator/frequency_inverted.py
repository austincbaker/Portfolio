"""Standalone frequency-inverted question builder.

Experimental alternative to the Fake-Entry recipe path. The professor's
proposal: construct distractors that saturate the per-property frequency
distribution so a text-only model that picks "majority vote over option
values" cannot identify the correct answer by marginal frequency alone.

The 8-option layout is rigid:

    [role_reversal]        (B, A, a_gt)
    [correct]              (A, B, a_gt)
    [frequency_saturation] (A, B, d1)   (X 3 per action)
    [frequency_saturation] (B, A, d1)
    [frequency_saturation] (A, A, d1)
    [frequency_saturation] (A, B, d2)
    [frequency_saturation] (B, A, d2)
    [frequency_saturation] (B, B, d2)

Where (A, B) = (entry.aggressor, entry.victim) and (d1, d2) are two non-GT
actions sampled from bank.actions. The property marginals are flat:
aggressor-A 4 / aggressor-B 4, victim-A 4 / victim-B 4, action a_gt 2 /
d1 3 / d2 3. The correct (A, B, a_gt) triple is unique -- no distractor
matches it on all three slots.

Scope: applied only to qtypes whose template renders the full
(aggressor, action, victim) triple --
compound_aggressor_action_victim, interaction_summary, sequence_verification.
Other qtypes fall back to the balanced Fake-Entry path.

G11 (refuse generic slots): if entry.aggressor or entry.victim isn't
specific, the builder returns None so the caller walks to the balanced
recipe.
"""

from __future__ import annotations

import random
from typing import Optional

from prompt_generator.answer_bank import AnswerBank
from prompt_generator.hardness import _is_specific


_SATURATION_SKELETON = [
    ("d1", "A", "B"),
    ("d1", "B", "A"),
    ("d1", "A", "A"),
    ("d2", "A", "B"),
    ("d2", "B", "A"),
    ("d2", "B", "B"),
]


def _render(template, entry: dict, agg, vic, action: str) -> str:

    fake = {**entry, "aggressor": agg, "victim": vic, "action": action}
    return template.correct_answer_builder(fake)


def _pick_distractor_actions(
    bank: AnswerBank, a_gt: str, n: int = 2
) -> Optional[list[str]]:

    a_gt_lower = a_gt.lower() if isinstance(a_gt, str) else None
    pool = [a for a in bank.actions if a.lower() != a_gt_lower]
    if len(pool) < n:
        return None
    return random.sample(pool, n)


def build_frequency_inverted_question(
    entry: dict,
    template,
    bank: AnswerBank,
    num_distractors: int = 7,
) -> Optional[tuple[list[str], list[str], int]]:

    if num_distractors != 7:


        return None

    A = entry.get("aggressor")
    B = entry.get("victim")
    a_gt = entry.get("action")
    if not (_is_specific(A) and _is_specific(B) and _is_specific(a_gt)):
        return None
    if not isinstance(a_gt, str):
        return None

    num_retries = 5
    for _ in range(num_retries):
        distractor_actions = _pick_distractor_actions(bank, a_gt, n=2)
        if distractor_actions is None:
            return None
        d1, d2 = distractor_actions


        options: list[tuple[str, str]] = []
        correct_idx_canonical = 1


        options.append((_render(template, entry, B, A, a_gt), "role_reversal"))

        options.append((_render(template, entry, A, B, a_gt), "correct"))

        role_map = {"A": A, "B": B}
        action_map = {"d1": d1, "d2": d2}
        for action_key, agg_key, vic_key in _SATURATION_SKELETON:
            options.append((
                _render(
                    template, entry,
                    role_map[agg_key], role_map[vic_key], action_map[action_key],
                ),
                "frequency_saturation",
            ))

        # Uniqueness: the 8 rendered strings must be distinct.
        texts = [t for t, _ in options]
        if len(set(texts)) == len(texts):

            indexed = list(enumerate(options))
            random.shuffle(indexed)
            new_correct_idx = next(
                i for i, (orig_i, _) in enumerate(indexed) if orig_i == correct_idx_canonical
            )
            shuffled = [pair for _, pair in indexed]
            answers = [t for t, _ in shuffled]
            hardness = [h for _, h in shuffled]
            return answers, hardness, new_correct_idx


        continue

    return None

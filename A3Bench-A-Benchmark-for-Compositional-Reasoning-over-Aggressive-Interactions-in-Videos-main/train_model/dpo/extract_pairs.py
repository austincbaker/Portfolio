#!/usr/bin/env python3
"""Phase 4: extract DPO preference pairs.

For each train-split question, build a (chosen, rejected[]) preference pair
where `chosen` is the correct answer (optionally prefixed with CoT reasoning)
and `rejected[]` are distractors selected from that question's multiple-choice
options.

Distractor selection strategies (--selection-strategy):

    fixed        -- Always pick the hardest distractors (default, original
                    behavior). Ignores --eval-results.

    hard_mining  -- Adaptive: if the model already answers a question correctly
                    (per --eval-results), pick easier distractors (the model
                    doesn't need hard signal here). If the model gets it wrong,
                    pick the hardest distractors (concentrate signal on weak
                    points). Falls back to fixed when no eval result exists
                    for a question.

    curriculum   -- Inverse of hard_mining: hard distractors for correct
                    questions (push further), easy for incorrect (scaffold up).
                    Ablation to test whether direction matters.

Adaptive pipeline (Phases 3.5 + 4):

    1. Train CoT-SFT (Phase 3) as usual
    2. Eval the CoT-SFT checkpoint on TRAINING questions:
           python train_model/eval/run_evaluation.py \\
               --config train_model/configs/eval_train.yaml
    3. Extract adaptive pairs:
           python train_model/dpo/extract_pairs.py \\
               --eval-results train_model/data/eval_train_cot.json \\
               --selection-strategy hard_mining
    4. Run DPO/ADPO (Phase 5) on the adaptive pairs
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


from prompt_generator.hardness import classify_distractor, HARDNESS_PRIORITY


def select_rejected_adaptive(
    classified: list[tuple[int, str, str]],
    model_correct: bool | None,
    strategy: str,
    n: int,
) -> list[tuple[int, str, str]]:

    if not classified or n <= 0:
        return []

    want_hardest = True

    if strategy == "hard_mining":
        if model_correct is None:
            want_hardest = True
        elif model_correct:
            want_hardest = False
        else:
            want_hardest = True
    elif strategy == "curriculum":
        if model_correct is None:
            want_hardest = True
        elif model_correct:
            want_hardest = True
        else:
            want_hardest = False


    sorted_items = sorted(
        classified,
        key=lambda x: HARDNESS_PRIORITY.get(x[2], 99),
        reverse=(not want_hardest),
    )
    return sorted_items[:n]


def _load_eval_results(path: str) -> dict[tuple[str, str], bool]:

    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "results" in data:
        results = data["results"]
    elif isinstance(data, list):
        results = data
    else:
        print(f"WARNING: unexpected eval results format; expected list or dict with 'results' key")
        results = []
    out: dict[tuple[str, str], bool] = {}
    for r in results:
        vname = r.get("video_name", "")
        prompt = r.get("prompt", "")
        is_correct = r.get("is_correct")
        if vname and prompt and is_correct is not None:
            out[(vname, prompt)] = bool(is_correct)
    return out


def _load_annotations(annotations_path: str) -> dict[str, dict]:
    with open(annotations_path, encoding="utf-8") as f:
        rows = json.load(f)
    out: dict[str, dict] = {}
    for r in rows:
        key = r.get("file_name") or r.get("video_name")
        if key:
            out[key] = r
    return out


def extract_preference_pairs(
    questions_path: str = "train_model/data/generated_questions.json",
    cot_chains_path: str = "train_model/data/cot_chains.json",
    output_path: str = "train_model/data/preference_pairs.json",
    train_split_path: str = "train_model/data/sft_train.json",
    annotations_path: str = "annotations.json",
    num_rejected_per_chosen: int = 5,
    seed: int = 42,
    eval_results_path: str | None = None,
    selection_strategy: str = "fixed",
):
    import random
    random.seed(seed)

    with open(questions_path, encoding="utf-8") as f:
        questions_data = json.load(f)
    questions_by_video = questions_data["questions_by_video"]


    if Path(train_split_path).exists():
        with open(train_split_path, encoding="utf-8") as f:
            train_examples = json.load(f)
        train_videos = {ex["video_name"] for ex in train_examples}
        before = len(questions_by_video)
        questions_by_video = {v: qs for v, qs in questions_by_video.items()
                              if v in train_videos}
        print(f"Train-split filter: kept {len(questions_by_video)}/{before} videos")
    else:
        print(f"WARNING: {train_split_path} not found; no train/val/test split guard.")

    annotations = _load_annotations(annotations_path)
    print(f"Loaded {len(annotations)} annotation records")


    cot_by_video_qidx: dict = {}
    if Path(cot_chains_path).exists():
        with open(cot_chains_path, encoding="utf-8") as f:
            cot_examples = json.load(f)
        for ex in cot_examples:
            key = (ex.get("video_name"), ex.get("question_index", 0))
            if ex.get("used_cot") and "reasoning_chain" in ex:
                cot_by_video_qidx[key] = ex["reasoning_chain"]
        print(f"Loaded {len(cot_by_video_qidx)} CoT chains")
    else:
        print("No CoT chains found; preference pairs will use direct answers")

    correctness_map: dict[tuple[str, str], bool] = {}
    if eval_results_path and Path(eval_results_path).exists():
        correctness_map = _load_eval_results(eval_results_path)
        print(f"Loaded {len(correctness_map)} eval results for adaptive selection")
    elif eval_results_path:
        print(f"WARNING: eval results not found at {eval_results_path}; "
              "falling back to fixed selection")

    preference_pairs = []
    pair_stats: Counter = Counter()
    adaptive_stats: Counter = Counter()
    skipped_noann = 0

    for video_name, questions in questions_by_video.items():
        ann = annotations.get(video_name, {})
        if not ann:
            skipped_noann += 1
            continue
        for q_idx, q in enumerate(questions):
            if q.get("is_secondary") or q.get("is_trick"):
                continue

            qtype = q["question_type"]
            correct_answer = q["correct_answer"]
            answers = q["answers"]
            correct_index = q.get("correct_index", -1)

            reasoning_chain = cot_by_video_qidx.get((video_name, q_idx))


            if correct_index < 0 or correct_index >= len(answers):
                continue
            correct_letter = chr(ord("A") + correct_index)
            chosen = {
                "answer": f"{correct_letter}) {correct_answer}",
                "reasoning": reasoning_chain,
            }

            if q.get("option_hardness"):
                labeled = [
                    (i, a, h) for i, (a, h) in enumerate(zip(answers, q["option_hardness"]))
                    if h != "correct"
                ]
                classified = [(i, a, h) for i, a, h in labeled]
            else:
                classified = []
                for i, a in enumerate(answers):
                    if i == correct_index or a == correct_answer:
                        continue
                    classified.append((i, a, classify_distractor(qtype, a, correct_answer, ann)))

            model_correct = correctness_map.get((video_name, q["prompt"]))
            top = select_rejected_adaptive(
                classified, model_correct, selection_strategy,
                num_rejected_per_chosen,
            )
            if selection_strategy != "fixed":
                if model_correct is None:
                    adaptive_stats["no_eval_fallback"] += 1
                elif model_correct:
                    adaptive_stats["model_correct"] += 1
                else:
                    adaptive_stats["model_wrong"] += 1


            rejected = [
                {
                    "answer": f"{chr(ord('A') + idx)}) {d}",
                    "hardness": h,
                    "index": idx,
                    "text": d,
                }
                for idx, d, h in top
            ]
            if not rejected:
                continue
            for _, _, h in top:
                pair_stats[h] += 1

            preference_pairs.append({
                "video_name": video_name,
                "question_type": qtype,
                "prompt": q["prompt"],
                "video_context": "",
                "chosen": chosen,
                "rejected": rejected,
                "all_answers": answers,
                "correct_index": correct_index,
            })

    if skipped_noann:
        print(f"Skipped {skipped_noann} videos with no annotation record")

    print(f"\nExtracted {len(preference_pairs)} preference pairs")
    print("Hardness distribution (over all kept rejected responses):")
    for h, c in sorted(pair_stats.items(), key=lambda x: HARDNESS_PRIORITY.get(x[0], 99)):
        print(f"  {h:25s}: {c:6,}")

    if selection_strategy != "fixed" and adaptive_stats:
        print(f"\nAdaptive selection stats (strategy={selection_strategy}):")
        for k in ("model_correct", "model_wrong", "no_eval_fallback"):
            if adaptive_stats[k]:
                print(f"  {k:20s}: {adaptive_stats[k]:6,}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(preference_pairs, f, indent=2)
    print(f"\nSaved to {output_path}")

    if preference_pairs:
        avg_rej = sum(len(p["rejected"]) for p in preference_pairs) / len(preference_pairs)
        with_cot = sum(1 for p in preference_pairs if p["chosen"].get("reasoning"))
        print(f"  Total pairs: {len(preference_pairs):,}")
        print(f"  Avg rejected per pair: {avg_rej:.2f}")
        print(f"  With CoT reasoning: {with_cot}")

    return preference_pairs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default="train_model/data/generated_questions.json")
    parser.add_argument("--cot-chains", default="train_model/data/cot_chains.json")
    parser.add_argument("--output", default="train_model/data/preference_pairs.json")
    parser.add_argument("--train-split", default="train_model/data/sft_train.json")
    parser.add_argument("--annotations", default="annotations.json")
    parser.add_argument("--num-rejected", type=int, default=5)
    parser.add_argument("--eval-results", default=None,
                        help="Path to eval results JSON for adaptive rejection selection")
    parser.add_argument("--selection-strategy", default="fixed",
                        choices=["fixed", "hard_mining", "curriculum"],
                        help="Rejected distractor selection strategy (default: fixed)")
    args = parser.parse_args()

    extract_preference_pairs(
        questions_path=args.questions,
        cot_chains_path=args.cot_chains,
        output_path=args.output,
        train_split_path=args.train_split,
        annotations_path=args.annotations,
        num_rejected_per_chosen=args.num_rejected,
        eval_results_path=args.eval_results,
        selection_strategy=args.selection_strategy,
    )

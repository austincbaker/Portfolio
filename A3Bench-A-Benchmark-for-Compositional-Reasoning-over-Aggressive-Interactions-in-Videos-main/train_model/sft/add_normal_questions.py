#!/usr/bin/env python3
"""Synthesise negative-example questions for normal (no-aggression) videos.

Reads `annotations.json`, finds videos whose annotation fields read
`action: none, aggressor: none, victim: none` (the 70 `normal_ucf_crime_*.mp4`
clips), and emits a multiple-choice question of each supported question_type
whose correct answer is the "null" option (e.g. "no aggressive action is
taking place", "No individual displays aggressive behavior", etc.).

Distractors are sampled from other videos' real aggression annotations so
each question presents a plausible aggression-affirming alternative that the
model must correctly reject.

Each new question is tagged `is_trick=True` so:
    * Phase 1 / 3 SFT include them in the supervised objective.
    * Phase 4 DPO pair extraction skips them (they don't yield useful
      contrastive preferences -- the correct answer is not comparable to
      prose-describing distractors).

Invocation:
    python train_model/sft/add_normal_questions.py                # modify in place
    python train_model/sft/add_normal_questions.py --dry-run      # just print summary
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Callable


def _agg(ann: dict) -> str:
    return str(ann.get("aggressor") or "").strip()

def _vic(ann: dict) -> str:
    return str(ann.get("victim") or "").strip()

def _act(ann: dict) -> str:
    return str(ann.get("action") or "").strip()

def _env(ann: dict) -> str:
    return str(ann.get("environment") or "").strip()

def _bys(ann: dict) -> str:
    b = ann.get("bystanders") or ""
    if isinstance(b, list):
        return " and ".join(str(x).strip() for x in b if x)
    return str(b).strip()


CATALOG: dict[str, dict] = {
    "aggressor_identification": {
        "prompt": "Who in the video is performing the aggressive behavior?",
        "null": "No individual displays aggressive behavior",
        "n": 8,
        "distractor": _agg,
    },
    "perspective_aggressor": {
        "prompt": "If you were observing this scene, which person would you describe as the aggressor?",
        "null": "None of the above appear aggressive",
        "n": 8,
        "distractor": _agg,
    },
    "victim_recognition": {
        "prompt": "Which person appears to be the target or victim of the aggression shown?",
        "null": "No one appears to be victimized",
        "n": 8,
        "distractor": _vic,
    },
    "bystander_detection": {
        "prompt": "Who is present during the incident but does not directly participate?",
        "null": "No bystanders are present",
        "n": 8,
        "distractor": _bys,
    },
    "primary_action": {
        "prompt": "If there is an aggressive action taking place in this video, describe it as one of the following:",
        "null": "no aggressive action is taking place",
        "n": 8,
        "distractor": _act,
    },
    "social_appropriateness": {
        "prompt": "Which action in the video would most likely be considered socially inappropriate or aggressive?",
        "null": "No actions performed are socially inappropriate",
        "n": 8,
        "distractor": lambda a: f"The action performed by {_agg(a)}" if _agg(a) else "",
    },
    "role_identification": {
        "prompt": "Concerning the people shown, their role would best be described as:",
        "null": "No one in the video fits that description",
        "n": 4,
        "distractor": lambda a: None,
        "fixed_distractors": ["Aggressor", "Victim", "Bystander"],
    },
    "sequence_verification": {
        "prompt": "Which of the following sequences best describes the interaction shown in the video?",
        "null": "No sequences describe the video",
        "n": 8,
        "distractor": lambda a: (
            f"{_agg(a)}, who is the aggressor, performed the action of {_act(a)} against {_vic(a)}"
            if _agg(a) and _act(a) and _vic(a) else ""
        ),
    },
    "interaction_summary": {
        "prompt": "Which summary most accurately describes the interactions between the people in the video?",
        "null": "No meaningful interaction occurs",
        "n": 8,
        "distractor": lambda a: (
            f"{_agg(a)} performs action of {_act(a)} on {_vic(a)}"
            if _agg(a) and _act(a) and _vic(a) else ""
        ),
    },
    "compound_aggressor_action_victim": {
        "prompt": "Which of the following best describes what happened in the video?",
        "null": "No one did anything to anyone",
        "n": 8,
        "distractor": lambda a: (
            f"{_agg(a)} performed {_act(a)} on {_vic(a)}"
            if _agg(a) and _act(a) and _vic(a) else ""
        ),
    },
    "compound_aggressor_location": {
        "prompt": "What is the aggressor wearing and what location is the event taking place?",
        "null": "Unable to determine aggressor or location",
        "n": 8,
        "distractor": lambda a: (
            f"{_agg(a)} in {_env(a)}" if _agg(a) and _env(a) else ""
        ),
    },
    "compound_action_victims": {
        "prompt": "Describe the action taking place in the video and describe any victims that are present",
        "null": "No action; Victim: No one appears to be victimized",
        "n": 8,
        "distractor": lambda a: (
            f"{_act(a)}; Victim: {_vic(a)}" if _act(a) and _vic(a) else ""
        ),
    },
    "compound_bystander_location": {
        "prompt": "Who is present but not participating, and where is this taking place?",
        "null": "No bystanders and location unclear",
        "n": 8,
        "distractor": lambda a: (
            f"{_bys(a)} in {_env(a)}" if _bys(a) and _env(a) else ""
        ),
    },
    "scene_location": {
        "prompt": "What location or setting is the video taking place in?",
        "null": "Unclear / not shown",
        "n": 8,
        "distractor": _env,
    },
}


def _is_normal(ann: dict) -> bool:

    def _is_none(x) -> bool:
        if x is None:
            return True
        s = str(x).strip().lower()
        return s in ("", "none", "n/a", "na", "unknown")
    return all(
        _is_none(ann.get(k))
        for k in ("action", "aggressor", "victim")
    )


def _build_distractor_pool(
    annotations: list[dict], kind: str
) -> list[str]:

    out: list[str] = []
    catalog_entry = CATALOG[kind]
    for ann in annotations:
        if _is_normal(ann):
            continue
        d = catalog_entry["distractor"](ann)
        if isinstance(d, str) and d.strip() and d.lower() != catalog_entry["null"].lower():
            out.append(d)
    return list(dict.fromkeys(out))


def _build_question(
    qtype: str,
    video_name: str,
    pool: list[str],
    rng: random.Random,
) -> dict | None:
    entry = CATALOG[qtype]
    n = entry["n"]
    null = entry["null"]

    if qtype == "role_identification":
        options = list(entry["fixed_distractors"]) + [null]
    else:
        if len(pool) < n - 1:
            return None
        distractors = rng.sample(pool, n - 1)
        options = distractors + [null]

    rng.shuffle(options)
    correct_index = options.index(null)

    return {
        "video_name": video_name,
        "question_type": qtype,
        "prompt": entry["prompt"],
        "answers": options,
        "correct_answer": null,
        "correct_index": correct_index,
        "is_trick": True,
        "is_secondary": False,
    }


def synthesise_normal_questions(
    annotations_path: str = "annotations.json",
    questions_path: str = "train_model/data/generated_questions.json",
    seed: int = 42,
    dry_run: bool = False,
) -> None:
    rng = random.Random(seed)

    with open(annotations_path, encoding="utf-8") as f:
        annotations = json.load(f)
    with open(questions_path, encoding="utf-8") as f:
        qdata = json.load(f)

    annotations_by_name = {
        (a.get("file_name") or a.get("video_name")): a
        for a in annotations
    }
    qbv: dict[str, list] = qdata["questions_by_video"]


    normals = [
        n for n, a in annotations_by_name.items()
        if _is_normal(a) and n and n not in qbv
    ]
    print(f"Found {len(normals)} normal (no-aggression) videos without questions", flush=True)

    if not normals:
        print("Nothing to add.")
        return


    pools = {qt: _build_distractor_pool(annotations, qt) for qt in CATALOG}
    for qt, p in pools.items():
        print(f"  pool[{qt:35s}] = {len(p):5d} distractors", flush=True)

    added = 0
    per_type_count: dict[str, int] = {qt: 0 for qt in CATALOG}
    for video_name in sorted(normals):
        new_questions = []
        for qtype in CATALOG:
            q = _build_question(qtype, video_name, pools[qtype], rng)
            if q is not None:
                new_questions.append(q)
                per_type_count[qtype] += 1
        if new_questions:
            qbv[video_name] = new_questions
            added += len(new_questions)

    print(f"\nSynthesised {added} new trick questions across {len(normals)} normal videos")
    print("Per-type counts:")
    for qt, c in sorted(per_type_count.items(), key=lambda x: -x[1]):
        print(f"  {qt:40s} {c:5d}")

    if dry_run:
        print("\n[dry-run] not writing to disk.")
        return

    Path(questions_path).parent.mkdir(parents=True, exist_ok=True)
    with open(questions_path, "w", encoding="utf-8") as f:
        json.dump(qdata, f)
    print(f"\nWrote updated {questions_path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", default="annotations.json")
    parser.add_argument("--questions", default="train_model/data/generated_questions.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    synthesise_normal_questions(
        annotations_path=args.annotations,
        questions_path=args.questions,
        seed=args.seed,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

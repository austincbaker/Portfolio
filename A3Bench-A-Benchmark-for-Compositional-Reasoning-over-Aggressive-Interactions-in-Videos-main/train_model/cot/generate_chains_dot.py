#!/usr/bin/env python3
"""
Phase 2 (DoT variant): Generate CoT reasoning chains using Dream of Thoughts.

Instead of generating a single chain and filtering pass/fail, DoT generates
N candidate chains per example, then asks the model to select the best one
via MCQ-style prompting. This leverages the model's stronger discrimination
ability (selecting > generating) and navigates hallucinations by treating
multiple diverse samples as a candidate pool.

Based on: "Navigating Hallucinations for Reasoning of Unintentional Activities"
(arXiv:2402.19405v2)

Three-stage pipeline per example:
  Stage 1 (Description): Generate N candidate scene descriptions
           → model selects the best one
  Stage 2 (Role Assignment): Given the selected description, generate N
           candidate role assignments (aggressor/victim/bystander)
           → model selects the best one
  Stage 3 (Composition): Given description + roles, generate N candidate
           full reasoning chains leading to an answer
           → model selects the best one
  Stage 4 (Refinement): Annotation-corrected refinement of the selected chain
           (same as original pipeline Stage 2)

Supports the same --part/--total-parts splitting and checkpointing as
generate_chains.py.

Usage:
    python train_model/cot/generate_chains_dot.py \
        --train-data train_model/data/sft_train.json \
        --output train_model/data/cot_chains.json \
        --candidates 3
"""

import json
import re
import sys
import argparse
import time
from pathlib import Path
from typing import Optional
from collections import defaultdict

import torch
from transformers import AutoTokenizer, AutoModel

_COT_LETTER_RE = re.compile(r"\b([A-H])\b\s*[\)\.\:]?", re.IGNORECASE)

from train_model.common.video_dataset import (
    build_image_transform,
    _load_frames,
    build_user_content,
    register_image_context_token
)

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

COT_ELIGIBLE_TYPES = {
    "compound_aggressor_victim",
    "compound_aggressor_action_victim",
    "compound_action_victims",
    "compound_aggressor_location",
    "compound_action_location",
    "sequence_verification",
    "aggressor_identification",
    "victim_recognition",
}

SIMPLE_TYPES = {
    "primary_action",
}


def build_description_prompt(example: dict) -> str:
    return """You are analyzing a video of a social interaction. Describe what you observe:
1. How many people are visible and what are they wearing?
2. What physical actions are taking place between them?
3. What is the environment/setting?

Keep your description concise (3-5 sentences) and grounded strictly in the visual evidence."""


def build_description_selection_prompt(candidates: list[str]) -> str:
    options = "\n".join(f"{chr(65+i)}) {c}" for i, c in enumerate(candidates))
    return f"""The following are candidate descriptions of this video. Select the one that is most accurate and detailed based on what you see in the frames.

{options}

Reply with ONLY the letter of the best description."""


def build_role_prompt(description: str, example: dict) -> str:
    question = example["prompt"]
    return f"""Based on this video description:
"{description}"

And looking at the video frames, determine the roles of the people involved:
- Who is the aggressor (the person initiating the aggressive action)?
- Who is the victim (the person receiving the aggressive action)?
- Are there any bystanders (people present but not involved)?

Question being answered: {question}

Provide your role assignment in 2-3 sentences."""


def build_role_selection_prompt(candidates: list[str]) -> str:
    options = "\n".join(f"{chr(65+i)}) {c}" for i, c in enumerate(candidates))
    return f"""The following are candidate role assignments for the people in this video. Select the one that most accurately identifies who is the aggressor and who is the victim based on the visual evidence.

{options}

Reply with ONLY the letter of the best role assignment."""


def build_reasoning_prompt(description: str, roles: str, example: dict) -> str:
    question = example["prompt"]
    options = example.get("all_answers", [])

    options_block = ""
    if options:
        options_block = "\nOptions:\n" + "\n".join(
            f"{chr(65+i)}) {opt}" for i, opt in enumerate(options)
        )

    return f"""Based on this video analysis:

Scene: {description}
Roles: {roles}

Answer the following question with a step-by-step reasoning chain.

Question: {question}{options_block}

Provide your reasoning in this format:
1. Identify the people and their appearances
2. Describe the aggressive action observed
3. Assign roles based on who initiates and who receives
4. Match your analysis to the answer options
5. Final answer: give the single option letter (A, B, C, ...) followed by a period.

Keep each step concise."""


def build_reasoning_selection_prompt(candidates: list[str], example: dict) -> str:
    question = example["prompt"]
    options = example.get("all_answers", [])

    options_block = ""
    if options:
        options_block = "\nOptions:\n" + "\n".join(
            f"{chr(65+i)}) {opt}" for i, opt in enumerate(options)
        )

    candidate_block = ""
    for i, c in enumerate(candidates):
        candidate_block += f"\n--- Reasoning {chr(65+i)} ---\n{c}\n"

    return f"""Question: {question}{options_block}

The following are candidate reasoning chains for this question. Select the one with the most accurate visual observations and logical reasoning.
{candidate_block}
Reply with ONLY the letter of the best reasoning chain."""


def build_refinement_prompt(example: dict, selected_chain: str) -> str:
    context = example["video_context"]
    question = example["prompt"]
    answer = example["correct_answer"]
    options = example.get("all_answers", [])
    correct_index = example.get("correct_index", -1)
    correct_letter = (
        chr(ord("A") + correct_index) if 0 <= correct_index < len(options) else "?"
    )

    options_block = ""
    if options:
        options_block = "\nOptions:\n" + "\n".join(
            f"{chr(65+i)}) {opt}" for i, opt in enumerate(options)
        )

    return f"""You are an expert video analyst refining a reasoning chain.

Original visual reasoning:
{selected_chain}

Ground Truth Annotation:
{context}

Question: {question}{options_block}
Correct Answer: {correct_letter}) {answer}

Please review your original visual reasoning. Update it so that it leads logically to the correct answer, but maintain your original visual descriptions of the people and environment where accurate. Do not simply copy the ground truth text; integrate the ground truth facts naturally into your visual step-by-step format. The final step MUST conclude with the single option letter that matches the correct answer, e.g. "Final answer: {correct_letter}."

Provide the final corrected reasoning chain in the same 5-step format."""


def _generate_n(tokenizer, model, pixel_values, prompt: str, n_frames: int,
                n: int, max_new_tokens: int = 300) -> list[str]:

    user_content = build_user_content(n_frames, prompt)
    gen_cfg = dict(max_new_tokens=max_new_tokens, do_sample=True,
                   temperature=0.7, top_p=0.9)
    candidates = []
    for _ in range(n):
        try:
            resp = model.chat(
                tokenizer, pixel_values, user_content, gen_cfg,
                num_patches_list=[1] * n_frames,
            )
            if resp and resp.strip():
                candidates.append(resp.strip())
        except Exception as e:
            print(f"    generation error: {e}")
    return candidates


def _select_best(tokenizer, model, pixel_values, selection_prompt: str,
                 n_frames: int, n_candidates: int) -> int:

    user_content = build_user_content(n_frames, selection_prompt)
    gen_cfg = dict(max_new_tokens=10, do_sample=False)
    try:
        resp = model.chat(
            tokenizer, pixel_values, user_content, gen_cfg,
            num_patches_list=[1] * n_frames,
        )
        if resp:
            m = re.search(r"\b([A-Z])\b", resp.strip().upper())
            if m:
                idx = ord(m.group(1)) - ord("A")
                if 0 <= idx < n_candidates:
                    return idx
    except Exception as e:
        print(f"    selection error: {e}")
    return 0


def generate_dot_chain(
    tokenizer, model, example: dict, pixel_values,
    n_candidates: int = 3, max_new_tokens: int = 300,
) -> Optional[str]:

    n_frames = pixel_values.shape[0]


    desc_prompt = build_description_prompt(example)
    descriptions = _generate_n(tokenizer, model, pixel_values, desc_prompt,
                               n_frames, n_candidates, max_new_tokens=200)
    if not descriptions:
        return None

    if len(descriptions) > 1:
        sel_prompt = build_description_selection_prompt(descriptions)
        best_idx = _select_best(tokenizer, model, pixel_values, sel_prompt,
                                n_frames, len(descriptions))
        selected_desc = descriptions[best_idx]
    else:
        selected_desc = descriptions[0]


    role_prompt = build_role_prompt(selected_desc, example)
    roles = _generate_n(tokenizer, model, pixel_values, role_prompt,
                        n_frames, n_candidates, max_new_tokens=150)
    if not roles:
        return None

    if len(roles) > 1:
        sel_prompt = build_role_selection_prompt(roles)
        best_idx = _select_best(tokenizer, model, pixel_values, sel_prompt,
                                n_frames, len(roles))
        selected_roles = roles[best_idx]
    else:
        selected_roles = roles[0]


    reason_prompt = build_reasoning_prompt(selected_desc, selected_roles, example)
    chains = _generate_n(tokenizer, model, pixel_values, reason_prompt,
                         n_frames, n_candidates, max_new_tokens=max_new_tokens)
    if not chains:
        return None

    if len(chains) > 1:
        sel_prompt = build_reasoning_selection_prompt(chains, example)
        best_idx = _select_best(tokenizer, model, pixel_values, sel_prompt,
                                n_frames, len(chains))
        selected_chain = chains[best_idx]
    else:
        selected_chain = chains[0]


    refine_prompt = build_refinement_prompt(example, selected_chain)
    user_content = build_user_content(n_frames, refine_prompt)
    gen_cfg = dict(max_new_tokens=max_new_tokens, do_sample=True,
                   temperature=0.7, top_p=0.9)
    try:
        refined = model.chat(
            tokenizer, pixel_values, user_content, gen_cfg,
            num_patches_list=[1] * n_frames,
        )
        return refined.strip() if refined else selected_chain
    except Exception:
        return selected_chain


def filter_cot_chain(chain: str, correct_index: int) -> bool:
    if not chain or len(chain) < 50:
        return False
    if correct_index is None or correct_index < 0:
        return False
    tail = chain[-80:]
    m = _COT_LETTER_RE.search(tail)
    if m is None:
        return False
    return (ord(m.group(1).upper()) - ord("A")) == correct_index


def _example_key(ex: dict) -> str:
    return f"{ex['video_name']}|{ex['question_type']}|{ex['question_index']}"


def load_teacher_model(model_name: str = "OpenGVLab/InternVL2_5-8B"):
    print(f"Loading teacher model: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(
        model_name, trust_remote_code=True, use_fast=False,
    )
    model = AutoModel.from_pretrained(
        model_name, torch_dtype=torch.bfloat16, device_map="auto",
        trust_remote_code=True, low_cpu_mem_usage=True,
        attn_implementation="flash_attention_2",
    ).eval()
    model.img_context_token_id = register_image_context_token(tokenizer)
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        print(f"[OK] Teacher model loaded ({allocated:.1f} GB GPU memory)")
    return tokenizer, model


def _save_checkpoint(path, cot_results, processed_keys, failed_count, filtered_count):
    data = {
        "cot_results": cot_results,
        "processed_keys": list(processed_keys),
        "failed_count": failed_count,
        "filtered_count": filtered_count,
    }
    with open(path, "w") as f:
        json.dump(data, f)


def generate_cot_data(
    train_data_path: str = "train_model/data/sft_train.json",
    output_path: str = "train_model/data/cot_chains.json",
    model_name: str = "OpenGVLab/InternVL2_5-8B",
    n_candidates: int = 3,
    sample_rate: float = 1.0,
    dry_run: bool = False,
    part: int = 0,
    total_parts: int = 1,
):
    is_split = total_parts > 1
    checkpoint_path = output_path + ".checkpoint"

    with open(train_data_path) as f:
        examples = json.load(f)

    print(f"Loaded {len(examples)} training examples")
    print(f"DoT mode: {n_candidates} candidates per stage")

    eligible = [ex for ex in examples if ex["question_type"] in COT_ELIGIBLE_TYPES]
    simple = [ex for ex in examples if ex["question_type"] in SIMPLE_TYPES]
    other = [
        ex for ex in examples
        if ex["question_type"] not in COT_ELIGIBLE_TYPES
        and ex["question_type"] not in SIMPLE_TYPES
    ]

    print(f"  CoT-eligible (compounds/complex): {len(eligible)}")
    print(f"  Simple (direct only): {len(simple)}")
    print(f"  Other: {len(other)}")

    if is_split:
        chunk_size = (len(eligible) + total_parts - 1) // total_parts
        start = part * chunk_size
        end = min(start + chunk_size, len(eligible))
        eligible = eligible[start:end]
        print(f"  Part {part+1}/{total_parts}: processing eligible[{start}:{end}] ({len(eligible)} examples)")

    if sample_rate < 1.0:
        import random
        random.seed(42)
        eligible = random.sample(eligible, int(len(eligible) * sample_rate))
        print(f"  Sampled to {len(eligible)} for CoT generation")

    cot_results = []
    processed_keys = set()
    failed_count = 0
    filtered_count = 0

    if Path(checkpoint_path).exists():
        with open(checkpoint_path) as f:
            checkpoint_data = json.load(f)
        cot_results = checkpoint_data.get("cot_results", [])
        failed_count = checkpoint_data.get("failed_count", 0)
        filtered_count = checkpoint_data.get("filtered_count", 0)
        processed_keys = {_example_key(r) for r in cot_results}
        for k in checkpoint_data.get("processed_keys", []):
            processed_keys.add(k)
        print(f"  Resuming from checkpoint: {len(processed_keys)} already processed, {len(cot_results)} chains saved")

    remaining = [ex for ex in eligible if _example_key(ex) not in processed_keys]
    print(f"\nGenerating DoT chains for {len(remaining)} remaining examples...")

    if not remaining:
        print("All examples already processed!")
        tokenizer, model = None, None
    elif not dry_run:
        tokenizer, model = load_teacher_model(model_name)
    else:
        tokenizer, model = None, None
        print("[DRY RUN] Skipping model load")

    transform = build_image_transform(448)
    frames_dir = Path("train_model/data/frames")
    device = next(model.parameters()).device if model else "cpu"
    dtype = next(model.parameters()).dtype if model else torch.bfloat16

    start_time = time.time()
    for i, example in enumerate(remaining):
        if (i + 1) % 5 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta_min = (len(remaining) - i - 1) / rate / 60 if rate > 0 else 0
            cot_count = sum(1 for r in cot_results if r.get("used_cot"))
            print(
                f"  [{i + 1}/{len(remaining)}] {cot_count} chains "
                f"({filtered_count} filtered, {failed_count} failed) "
                f"- {rate:.3f}/s, ETA {eta_min:.0f}min"
            )

        key = _example_key(example)

        if dry_run:
            chain = "[DRY RUN] Sample DoT reasoning chain"
        else:
            try:
                pixel_values = _load_frames(
                    frames_dir, example["video_name"], 8, transform
                ).to(device=device, dtype=dtype)
            except Exception as e:
                print(f"  Failed to load frames for {example['video_name']}: {e}")
                failed_count += 1
                result = example.copy()
                result["used_cot"] = False
                cot_results.append(result)
                processed_keys.add(key)
                continue

            chain = generate_dot_chain(
                tokenizer, model, example, pixel_values,
                n_candidates=n_candidates,
            )

        processed_keys.add(key)

        if chain is None:
            failed_count += 1
            result = example.copy()
            result["used_cot"] = False
            cot_results.append(result)
        elif not filter_cot_chain(chain, example.get("correct_index", -1)):
            filtered_count += 1
            result = example.copy()
            result["used_cot"] = False
            cot_results.append(result)
        else:
            result = example.copy()
            result["reasoning_chain"] = chain
            result["used_cot"] = True
            result["method"] = "dot"
            cot_results.append(result)

        if (i + 1) % 50 == 0:
            _save_checkpoint(checkpoint_path, cot_results, processed_keys,
                             failed_count, filtered_count)
            print(f"  [checkpoint saved: {len(cot_results)} examples, "
                  f"{sum(1 for r in cot_results if r.get('used_cot'))} with CoT]")

    _save_checkpoint(checkpoint_path, cot_results, processed_keys,
                     failed_count, filtered_count)

    if not is_split:
        for example in simple:
            result = example.copy()
            result["used_cot"] = False
            cot_results.append(result)
        for example in other:
            result = example.copy()
            result["used_cot"] = False
            cot_results.append(result)

    cot_count = sum(1 for r in cot_results if r.get("used_cot"))
    print(f"\nGeneration complete:")
    print(f"  DoT chains accepted: {cot_count}")
    print(f"  Failed (kept as direct): {failed_count}")
    print(f"  Filtered (kept as direct): {filtered_count}")
    if not is_split:
        print(f"  Simple/other (direct): {len(simple) + len(other)}")
    print(f"  Total output examples: {len(cot_results)}")
    if cot_count + filtered_count > 0:
        acceptance = cot_count / (cot_count + filtered_count) * 100
        print(f"  Acceptance rate: {acceptance:.1f}% (was 46.8% with standard CoT)")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(cot_results, f, indent=2)
    print(f"\nSaved to {output_path}")

    if Path(checkpoint_path).exists():
        Path(checkpoint_path).unlink()
        print("Checkpoint cleaned up")

    by_type = defaultdict(lambda: {"total": 0, "cot": 0})
    for ex in cot_results:
        qtype = ex.get("question_type", "unknown")
        by_type[qtype]["total"] += 1
        if ex.get("used_cot"):
            by_type[qtype]["cot"] += 1

    print("\nCoT coverage by question type:")
    for qtype in sorted(by_type.keys()):
        stats = by_type[qtype]
        pct = stats["cot"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {qtype:40s}: {stats['cot']:4d}/{stats['total']:4d} ({pct:5.1f}%)")

    return cot_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate CoT chains using Dream of Thoughts (DoT)")
    parser.add_argument("--train-data", default="train_model/data/sft_train.json")
    parser.add_argument("--output", default="train_model/data/cot_chains.json")
    parser.add_argument("--model-name", default="OpenGVLab/InternVL2_5-8B")
    parser.add_argument("--candidates", type=int, default=3,
                        help="Number of candidates per DoT stage (default: 3)")
    parser.add_argument("--sample-rate", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--part", type=int, default=0)
    parser.add_argument("--total-parts", type=int, default=1)
    args = parser.parse_args()

    generate_cot_data(
        train_data_path=args.train_data,
        output_path=args.output,
        model_name=args.model_name,
        n_candidates=args.candidates,
        sample_rate=args.sample_rate,
        dry_run=args.dry_run,
        part=args.part,
        total_parts=args.total_parts,
    )

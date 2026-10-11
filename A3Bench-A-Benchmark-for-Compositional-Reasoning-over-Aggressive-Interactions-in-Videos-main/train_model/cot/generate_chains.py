#!/usr/bin/env python3
"""
Phase 2: Generate CoT reasoning chains via local InternVL2.5-8B teacher.

For compound/complex question types, uses a local InternVL2.5-8B model to
generate step-by-step reasoning that leads to the correct answer. Runs entirely
on local GPU hardware - no API costs.

Supports incremental checkpointing for SLURM requeue survival.

Input: SFT training data split (from Phase 1)
Output: JSON file with CoT chains merged into training examples
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


def build_cot_stage1_prompt(example: dict) -> str:

    question = example["prompt"]
    options = example.get("all_answers", [])

    prompt = f"""You are analyzing a video of an aggressive interaction. Generate a step-by-step reasoning chain to answer the question based purely on the visual evidence.

Question: {question}"""

    if options:
        prompt += "\nOptions:"
        for i, opt in enumerate(options):
            letter = chr(ord('A') + i)
            prompt += f"\n{letter}) {opt}"

    prompt += """

Provide your reasoning in the following format:
1. Identify key people and their roles in the video based on what you see
2. Describe the actions taking place
3. Note any relevant environmental details
4. Determine the answer step-by-step
5. Final answer: give the single option letter (A, B, C, ...) followed by a period.

Keep each step concise and grounded strictly in the visual evidence."""

    return prompt


def build_cot_stage2_prompt(example: dict, stage1_chain: str) -> str:

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
            f"{chr(ord('A') + i)}) {opt}" for i, opt in enumerate(options)
        )

    prompt = f"""You are an expert video analyst refining a reasoning chain.

Original visual reasoning:
{stage1_chain}

Ground Truth Annotation:
{context}

Question: {question}{options_block}
Correct Answer: {correct_letter}) {answer}

Please review your original visual reasoning. Update it so that it leads logically to the correct answer, but maintain your original visual descriptions of the people and environment where accurate. Do not simply copy the ground truth text; integrate the ground truth facts naturally into your visual step-by-step format. The final step MUST conclude with the single option letter that matches the correct answer, e.g. "Final answer: {correct_letter}."

Provide the final corrected reasoning chain in the same 5-step format."""
    return prompt


def load_teacher_model(model_name: str = "OpenGVLab/InternVL2_5-8B"):

    print(f"Loading teacher model: {model_name}")

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
        use_fast=False,
    )

    model = AutoModel.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
        low_cpu_mem_usage=True,
        attn_implementation="flash_attention_2",
    ).eval()
    model.img_context_token_id = register_image_context_token(tokenizer)

    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        print(f"[OK] Teacher model loaded ({allocated:.1f} GB GPU memory)")
    else:
        print("[OK] Teacher model loaded (CPU mode)")

    return tokenizer, model


def generate_cot_chain(
    tokenizer,
    model,
    example: dict,
    pixel_values,
    max_new_tokens: int = 300,
) -> Optional[str]:

    stage1_prompt = build_cot_stage1_prompt(example)
    n_frames = pixel_values.shape[0] if pixel_values is not None else 8
    user_content_stage1 = build_user_content(n_frames, stage1_prompt)

    generation_config = dict(
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
    )

    try:

        stage1_response = model.chat(
            tokenizer,
            pixel_values,
            user_content_stage1,
            generation_config,
            num_patches_list=[1] * n_frames if pixel_values is not None else None,
        )

        if not stage1_response:
            return None


        stage2_prompt = build_cot_stage2_prompt(example, stage1_response)
        user_content_stage2 = build_user_content(n_frames, stage2_prompt)

        stage2_response = model.chat(
            tokenizer,
            pixel_values,
            user_content_stage2,
            generation_config,
            num_patches_list=[1] * n_frames if pixel_values is not None else None,
        )

        return stage2_response.strip() if stage2_response else None
    except Exception as e:
        print(f"  Error generating chain: {e}")
        return None


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


def generate_cot_data(
    train_data_path: str = "train_model/data/sft_train.json",
    output_path: str = "train_model/data/cot_chains.json",
    model_name: str = "OpenGVLab/InternVL2_5-8B",
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
    print(f"\nGenerating CoT chains for {len(remaining)} remaining examples (of {len(eligible)} total)...")

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
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta_min = (len(remaining) - i - 1) / rate / 60 if rate > 0 else 0
            print(
                f"  [{i + 1}/{len(remaining)}] {len(cot_results)} chains "
                f"({filtered_count} filtered, {failed_count} failed) "
                f"- {rate:.2f}/s, ETA {eta_min:.0f}min"
            )

        key = _example_key(example)

        if dry_run:
            chain = "[DRY RUN] Sample reasoning chain for pipeline testing"
        else:
            try:
                pixel_values = _load_frames(frames_dir, example["video_name"], 8, transform).to(device=device, dtype=dtype)
            except Exception as e:
                print(f"  Failed to load frames for {example['video_name']}: {e}")
                failed_count += 1
                processed_keys.add(key)
                continue

            chain = generate_cot_chain(tokenizer, model, example, pixel_values)

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
            cot_results.append(result)


        if (i + 1) % 100 == 0:
            _save_checkpoint(checkpoint_path, cot_results, processed_keys, failed_count, filtered_count)
            print(f"  [checkpoint saved: {len(cot_results)} chains, {len(processed_keys)} processed]")


    _save_checkpoint(checkpoint_path, cot_results, processed_keys, failed_count, filtered_count)

    if not is_split:
        for example in simple:
            result = example.copy()
            result["used_cot"] = False
            cot_results.append(result)
        for example in other:
            result = example.copy()
            result["used_cot"] = False
            cot_results.append(result)

    print(f"\nGeneration complete:")
    print(f"  CoT chains: {sum(1 for r in cot_results if r.get('used_cot'))}")
    print(f"  Failed (kept as direct): {failed_count}")
    print(f"  Filtered (kept as direct): {filtered_count}")
    if not is_split:
        print(f"  Simple/other (direct): {len(simple) + len(other)}")
    print(f"  Total output examples: {len(cot_results)}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(cot_results, f, indent=2)

    print(f"\nSaved to {output_path}")


    if Path(checkpoint_path).exists():
        Path(checkpoint_path).unlink()
        print("Checkpoint cleaned up")


    by_type = defaultdict(lambda: {"total": 0, "cot": 0})
    for ex in cot_results:
        qtype = ex["question_type"]
        by_type[qtype]["total"] += 1
        if ex.get("used_cot"):
            by_type[qtype]["cot"] += 1

    print("\nCoT coverage by question type:")
    for qtype in sorted(by_type.keys()):
        stats = by_type[qtype]
        pct = stats["cot"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {qtype:40s}: {stats['cot']:4d}/{stats['total']:4d} ({pct:5.1f}%)")

    return cot_results


def _save_checkpoint(path, cot_results, processed_keys, failed_count, filtered_count):

    data = {
        "cot_results": cot_results,
        "processed_keys": list(processed_keys),
        "failed_count": failed_count,
        "filtered_count": filtered_count,
    }
    with open(path, "w") as f:
        json.dump(data, f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-data", default="train_model/data/sft_train.json")
    parser.add_argument("--output", default="train_model/data/cot_chains.json")
    parser.add_argument("--model-name", default="OpenGVLab/InternVL2_5-8B")
    parser.add_argument("--sample-rate", type=float, default=1.0,
                        help="Sample subset (0-1) for faster iteration")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't load model, just test pipeline")
    parser.add_argument("--part", type=int, default=0,
                        help="0-indexed part number for split runs")
    parser.add_argument("--total-parts", type=int, default=1,
                        help="Total number of parts (1 = no split)")
    args = parser.parse_args()

    generate_cot_data(
        train_data_path=args.train_data,
        output_path=args.output,
        model_name=args.model_name,
        sample_rate=args.sample_rate,
        dry_run=args.dry_run,
        part=args.part,
        total_parts=args.total_parts,
    )

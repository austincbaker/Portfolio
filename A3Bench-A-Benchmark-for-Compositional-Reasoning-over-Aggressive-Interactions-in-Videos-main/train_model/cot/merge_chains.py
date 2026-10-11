#!/usr/bin/env python3
"""
Merge CoT chain parts produced by split runs of generate_chains.py.

Each part file contains only the CoT-eligible examples that were assigned
to that part. This script merges them and adds back the simple/other
examples (direct answers) from the original training data.

Usage:
    python train_model/cot/merge_chains.py \
        --parts train_model/data/cot_chains_part0.json \
                train_model/data/cot_chains_part1.json \
                train_model/data/cot_chains_part2.json \
        --train-data train_model/data/sft_train.json \
        -o train_model/data/cot_chains.json
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path


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


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--parts", nargs="+", required=True, help="Part JSON files to merge")
    parser.add_argument("--train-data", default="train_model/data/sft_train.json",
                        help="Original training data (for simple/other examples)")
    parser.add_argument("-o", "--output", default="train_model/data/cot_chains.json")
    args = parser.parse_args()

    merged = []
    for p in args.parts:
        with open(p, encoding="utf-8") as f:
            part = json.load(f)
        print(f"  {p}: {len(part)} examples ({sum(1 for e in part if e.get('used_cot'))} with CoT)")
        merged.extend(part)

    with open(args.train_data, encoding="utf-8") as f:
        train_examples = json.load(f)

    non_eligible = [ex for ex in train_examples if ex["question_type"] not in COT_ELIGIBLE_TYPES]
    for ex in non_eligible:
        result = ex.copy()
        result["used_cot"] = False
        merged.append(result)

    cot_count = sum(1 for e in merged if e.get("used_cot"))
    direct_count = sum(1 for e in merged if not e.get("used_cot"))

    print(f"\nMerged output:")
    print(f"  CoT chains: {cot_count}")
    print(f"  Direct answers: {direct_count}")
    print(f"  Total: {len(merged)}")

    by_type = defaultdict(lambda: {"total": 0, "cot": 0})
    for ex in merged:
        qtype = ex.get("question_type", "unknown")
        by_type[qtype]["total"] += 1
        if ex.get("used_cot"):
            by_type[qtype]["cot"] += 1

    print("\nCoverage by question type:")
    for qtype in sorted(by_type.keys()):
        stats = by_type[qtype]
        pct = stats["cot"] / stats["total"] * 100 if stats["total"] > 0 else 0
        print(f"  {qtype:40s}: {stats['cot']:4d}/{stats['total']:4d} ({pct:5.1f}%)")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Combine ablation eval results and print a comparison table.

Reads per-stage JSON result files (produced by run_evaluation.py) and
prints a side-by-side accuracy table with deltas from the baseline stage.

Usage:
    python train_model/eval/combine_ablation.py \
        --sft train_model/eval/results_sft.json \
        --cot train_model/eval/results_cot.json \
        --dpo train_model/eval/results_dpo.json

    # Or auto-discover from a directory:
    python train_model/eval/combine_ablation.py -d train_model/eval/

    # Combine split parts first, then compare:
    python train_model/eval/combine_ablation.py \
        --cot train_model/eval/results_cot_part1.json \
              train_model/eval/results_cot_part2.json \
              train_model/eval/results_cot_part3.json \
        --dpo train_model/eval/results_dpo.json
"""

import argparse
import json
import sys
from pathlib import Path


def load_stage(paths: list[str]) -> dict | None:
    if not paths:
        return None
    parts = []
    for p in paths:
        if not Path(p).exists():
            print(f"  WARNING: {p} not found, skipping", file=sys.stderr)
            continue
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and len(data) == 1:
            data = next(iter(data.values()))
        parts.append(data)
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return merge_parts(parts)


def merge_parts(parts: list[dict]) -> dict:
    by_type = {}
    by_trick = {}
    total_samples = 0
    letter_parsed_total = 0

    for p in parts:
        n = p.get("total_samples", 0)
        total_samples += n
        lp_rate = p.get("letter_parsed_rate", 100.0)
        letter_parsed_total += int(lp_rate / 100.0 * n)

        for qt, vals in p.get("by_question_type", {}).items():
            if qt not in by_type:
                by_type[qt] = {"correct": 0, "total": 0}
            by_type[qt]["correct"] += vals["correct"]
            by_type[qt]["total"] += vals["total"]

        for tk, vals in p.get("by_trick", {}).items():
            if tk not in by_trick:
                by_trick[tk] = {"correct": 0, "total": 0}
            by_trick[tk]["correct"] += vals["correct"]
            by_trick[tk]["total"] += vals["total"]

    total_correct = sum(v["correct"] for v in by_type.values())
    return {
        "overall_accuracy": total_correct / max(1, total_samples) * 100,
        "letter_parsed_rate": letter_parsed_total / max(1, total_samples) * 100,
        "by_question_type": by_type,
        "by_trick": by_trick,
        "total_samples": total_samples,
    }


def acc(correct: int, total: int) -> float:
    return correct / max(1, total) * 100


def discover_files(directory: str) -> dict[str, list[str]]:
    d = Path(directory)
    stages = {}
    for stage in ("sft", "cot", "adpo", "dpo"):
        exact = d / f"results_{stage}.json"
        if exact.exists():
            stages[stage] = [str(exact)]
        else:
            parts = sorted(d.glob(f"results_{stage}_part*.json"))
            if parts:
                stages[stage] = [str(p) for p in parts]
    return stages


def print_table(stages: dict[str, dict], baseline: str = "sft"):
    stage_names = [s for s in ("sft", "cot", "adpo", "dpo") if s in stages]
    if not stage_names:
        print("No stages to compare.")
        return

    all_qtypes = set()
    for s in stages.values():
        all_qtypes.update(s.get("by_question_type", {}).keys())
    qtypes = sorted(all_qtypes)

    base = stages.get(baseline)

    label_w = 36
    col_w = 8
    delta_w = 9

    header_parts = [f"{'Question Type':<{label_w}}"]
    for name in stage_names:
        header_parts.append(f"{name.upper():>{col_w}}")
        if base and name != baseline:
            header_parts.append(f"{'delta':>{delta_w}}")
    header = "  ".join(header_parts)
    sep = "-" * len(header)

    print()
    print(header)
    print(sep)

    for qt in qtypes:
        parts = [f"{qt:<{label_w}}"]
        base_acc = None
        if base and qt in base.get("by_question_type", {}):
            bv = base["by_question_type"][qt]
            base_acc = acc(bv["correct"], bv["total"])

        for name in stage_names:
            s = stages[name]
            if qt in s.get("by_question_type", {}):
                v = s["by_question_type"][qt]
                a = acc(v["correct"], v["total"])
                parts.append(f"{a:>{col_w}.1f}%")
                if base and name != baseline and base_acc is not None:
                    delta = a - base_acc
                    sign = "+" if delta >= 0 else ""
                    parts.append(f"{sign}{delta:>{delta_w - 1}.1f}")
                elif name != baseline:
                    parts.append(f"{'':>{delta_w}}")
            else:
                parts.append(f"{'--':>{col_w}}")
                if name != baseline:
                    parts.append(f"{'':>{delta_w}}")
        print("  ".join(parts))

    print(sep)

    parts = [f"{'OVERALL':<{label_w}}"]
    base_overall = base["overall_accuracy"] if base else None
    for name in stage_names:
        s = stages[name]
        a = s["overall_accuracy"]
        parts.append(f"{a:>{col_w}.1f}%")
        if base and name != baseline:
            delta = a - base_overall
            sign = "+" if delta >= 0 else ""
            parts.append(f"{sign}{delta:>{delta_w - 1}.1f}")
    print("  ".join(parts))

    for trick_label, trick_key in [("Trick questions", "trick"), ("Normal questions", "normal")]:
        parts = [f"{trick_label:<{label_w}}"]
        base_trick_acc = None
        if base:
            bt = base.get("by_trick", {}).get(trick_key)
            if bt and bt["correct"] > 0:
                base_trick_acc = acc(bt["correct"], bt["total"])
        for name in stage_names:
            s = stages[name]
            t = s.get("by_trick", {}).get(trick_key)
            if t and t["correct"] > 0:
                a = acc(t["correct"], t["total"])
                parts.append(f"{a:>{col_w}.1f}%")
                if base and name != baseline and base_trick_acc is not None:
                    delta = a - base_trick_acc
                    sign = "+" if delta >= 0 else ""
                    parts.append(f"{sign}{delta:>{delta_w - 1}.1f}")
                elif name != baseline:
                    parts.append(f"{'':>{delta_w}}")
            else:
                parts.append(f"{'--':>{col_w}}")
                if name != baseline:
                    parts.append(f"{'':>{delta_w}}")
        print("  ".join(parts))

    parts = [f"{'Letter parsed':<{label_w}}"]
    for name in stage_names:
        s = stages[name]
        parts.append(f"{s['letter_parsed_rate']:>{col_w}.1f}%")
        if name != baseline:
            parts.append(f"{'':>{delta_w}}")
    print("  ".join(parts))

    parts = [f"{'Total samples':<{label_w}}"]
    for name in stage_names:
        s = stages[name]
        parts.append(f"{s['total_samples']:>{col_w},}")
        if name != baseline:
            parts.append(f"{'':>{delta_w}}")
    print("  ".join(parts))

    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-d", "--dir", help="Auto-discover result files from this directory")
    parser.add_argument("--sft", nargs="*", default=[], help="SFT result JSON(s)")
    parser.add_argument("--cot", nargs="*", default=[], help="CoT result JSON(s)")
    parser.add_argument("--adpo", nargs="*", default=[], help="ADPO result JSON(s)")
    parser.add_argument("--dpo", nargs="*", default=[], help="DPO (vanilla, alpha=0) result JSON(s)")
    parser.add_argument("--baseline", default="sft", choices=["sft", "cot", "adpo", "dpo"],
                        help="Stage to compute deltas against (default: sft)")
    args = parser.parse_args()

    file_map = {}
    if args.dir:
        file_map = discover_files(args.dir)
    if args.sft:
        file_map["sft"] = args.sft
    if args.cot:
        file_map["cot"] = args.cot
    if args.adpo:
        file_map["adpo"] = args.adpo
    if args.dpo:
        file_map["dpo"] = args.dpo

    if not file_map:
        parser.error("Provide --dir or at least one of --sft / --cot / --adpo / --dpo")

    stages = {}
    for name, paths in file_map.items():
        print(f"Loading {name}: {', '.join(paths)}", file=sys.stderr)
        result = load_stage(paths)
        if result:
            stages[name] = result

    if not stages:
        print("No valid result files found.", file=sys.stderr)
        sys.exit(1)

    if args.baseline not in stages and stages:
        args.baseline = next(iter(stages))
        print(f"Baseline {args.baseline!r} not found, using {args.baseline}", file=sys.stderr)

    print_table(stages, baseline=args.baseline)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Phase 1 -- multimodal SFT baseline.

Fine-tunes InternVL2.5-8B end-to-end (vision + LLM) on (video_frames, question)
-> answer using LoRA on the LLM attention/MLP layers plus the vision->text
projector (`mlp1`). The vision backbone (InternViT) stays frozen.

Usage:
    python train_model/sft/train.py --config train_model/configs/sft.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import json

import torch
import transformers
from peft import LoraConfig, get_peft_model
from transformers import AutoModel, AutoTokenizer, Trainer, TrainingArguments

from train_model.common.config import load_config, save_config
from train_model.common.video_dataset import (
    VideoSFTDataset,
    collate_sft,
    register_image_context_token,
)


def _dtype_from_str(s: str) -> torch.dtype:
    return {"bfloat16": torch.bfloat16, "float16": torch.float16,
            "float32": torch.float32}[s]


def setup_model(cfg: dict):
    model_name = cfg["model"]["name"]
    dtype = _dtype_from_str(cfg["model"]["torch_dtype"])
    print(f"Loading tokenizer + model: {model_name}", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModel.from_pretrained(
        model_name,
        torch_dtype=dtype,
        device_map="auto",
        trust_remote_code=True,
        attn_implementation="flash_attention_2",
    )
    model.config.use_cache = False

    model.img_context_token_id = register_image_context_token(tokenizer)


    for p in model.vision_model.parameters():
        p.requires_grad = False

    lora = cfg["lora"]
    # IMPORTANT: do NOT set task_type=CAUSAL_LM. PeftModelForCausalLM's forward


    lora_config = LoraConfig(
        r=int(lora["r"]),
        lora_alpha=int(lora["alpha"]),
        lora_dropout=float(lora["dropout"]),
        bias=str(lora["bias"]),
        target_modules=list(lora["target_modules"]),
    )
    model = get_peft_model(model, lora_config)


    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()

    print("Trainable parameter summary:", flush=True)
    model.print_trainable_parameters()
    return tokenizer, model


def _num_image_token(model) -> int:

    base = model.base_model.model if hasattr(model, "base_model") else model
    return int(base.num_image_token)


def train(cfg: dict) -> None:
    transformers.set_seed(int(cfg.get("seed", 42)))
    torch.manual_seed(int(cfg.get("seed", 42)))

    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    save_config(cfg, out_dir / "config.yaml")

    tokenizer, model = setup_model(cfg)
    nit = _num_image_token(model)
    print(f"num_image_token per patch: {nit}", flush=True)

    train_ds = VideoSFTDataset(cfg["data"]["train"], tokenizer, cfg, nit)


    val_path = cfg["data"].get("val")
    val_ds = None
    if val_path and Path(val_path).exists():
        try:
            candidate = VideoSFTDataset(val_path, tokenizer, cfg, nit)
            if len(candidate) > 0:
                val_ds = candidate
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    print(
        f"  train: {len(train_ds)}  val: {len(val_ds) if val_ds else 0}"
        + (" (no-val mode)" if val_ds is None else ""),
        flush=True,
    )

    t = cfg["training"]
    eval_enabled = val_ds is not None

    args = TrainingArguments(
        output_dir=str(out_dir),
        num_train_epochs=int(t["epochs"]),
        max_steps=int(t.get("max_steps", -1)),
        per_device_train_batch_size=int(t["per_device_train_batch_size"]),
        per_device_eval_batch_size=int(t["per_device_eval_batch_size"]),
        gradient_accumulation_steps=int(t["gradient_accumulation_steps"]),
        learning_rate=float(t["learning_rate"]),
        warmup_steps=int(t.get("warmup_steps", 0)),
        weight_decay=float(t.get("weight_decay", 0.0)),
        max_grad_norm=float(t.get("max_grad_norm", 1.0)),
        logging_steps=int(t.get("logging_steps", 25)),
        eval_steps=int(t.get("eval_steps", 500)) if eval_enabled else None,
        save_steps=int(t.get("save_steps", 500)),
        save_total_limit=int(t.get("save_total_limit", 2)),
        eval_strategy="steps" if eval_enabled else "no",
        save_strategy="steps",
        load_best_model_at_end=bool(t.get("load_best_model_at_end", True)) and eval_enabled,
        metric_for_best_model=(str(t.get("metric_for_best_model", "eval_loss"))
                               if eval_enabled else None),
        greater_is_better=False,
        bf16=bool(t.get("bf16", True)),
        gradient_checkpointing=bool(t.get("gradient_checkpointing", True)),
        gradient_checkpointing_kwargs={"use_reentrant": False},
        dataloader_num_workers=int(t.get("dataloader_num_workers", 2)),
        seed=int(cfg.get("seed", 42)),
        report_to="none",
        remove_unused_columns=False,
        label_names=["labels"],
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=collate_sft,
    )

    print("\nStarting training...", flush=True)
    trainer.train()

    print(f"\nSaving final LoRA adapter to {out_dir}", flush=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    print("Done.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="train_model/configs/sft.yaml")
    parser.add_argument("--override", action="append", default=[])
    args = parser.parse_args()
    cfg = load_config(args.config, overrides=args.override)
    train(cfg)


if __name__ == "__main__":
    main()

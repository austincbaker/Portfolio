#!/usr/bin/env python3
"""Phase 5 -- multimodal (A)DPO training.

Implements Direct Preference Optimization on top of the Phase 3 CoT-SFT
adapter, using the full InternVLChatModel forward (pixel_values + input_ids).
The reference policy is the same model with the LoRA adapter disabled via
`peft.disable_adapter()` -- no second 8B copy on the GPU.

Loss:
    margin = beta * ((pol_chosen - ref_chosen) - (pol_rejected - ref_rejected))
    L_dpo  = -logsigmoid(margin).mean()
    L_anchor = alpha * mean((pol - ref)^2) on chosen and rejected    # optional
    L = L_dpo + L_anchor

Log-probs are summed over **response tokens only** (via `response_mask`)
so the shared prompt does not dilute the preference signal.

Usage:
    python train_model/dpo/train.py --config train_model/configs/dpo.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import torch
import torch.nn.functional as F
import transformers
from peft import PeftModel
from torch.utils.data import DataLoader
from transformers import AutoModel, AutoTokenizer

from train_model.common.config import load_config, save_config
from train_model.common.video_dataset import (
    VideoDPOPairDataset,
    collate_dpo,
    register_image_context_token,
)


def _dtype_from_str(s: str) -> torch.dtype:
    return {"bfloat16": torch.bfloat16, "float16": torch.float16,
            "float32": torch.float32}[s]


def _find_adapter(path: str | Path) -> str | None:
    p = Path(path)
    if (p / "adapter_config.json").exists():
        return str(p)
    cks = sorted(p.glob("checkpoint-*"), key=lambda d: int(d.name.split("-")[-1]))
    for c in reversed(cks):
        if (c / "adapter_config.json").exists():
            return str(c)
    return None


def setup_model(cfg: dict):
    model_name = cfg["model"]["name"]
    dtype = _dtype_from_str(cfg["model"]["torch_dtype"])
    print(f"Loading tokenizer + model: {model_name}", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    base = AutoModel.from_pretrained(
        model_name,
        torch_dtype=dtype,
        device_map="auto",
        trust_remote_code=True,
        attn_implementation="flash_attention_2",
    )
    base.config.use_cache = False
    base.img_context_token_id = register_image_context_token(tokenizer)

    for p in base.vision_model.parameters():
        p.requires_grad = False

    resume_from = cfg.get("resume_from")
    adapter_path = _find_adapter(resume_from) if resume_from else None
    if adapter_path:
        print(f"Loading prior adapter from {adapter_path} (is_trainable=True)", flush=True)
        model = PeftModel.from_pretrained(base, adapter_path, is_trainable=True)
    else:
        print("No prior adapter -- starting DPO/ADPO from fresh LoRA", flush=True)
        from peft import LoraConfig, get_peft_model
        lora = cfg["lora"]
        lora_config = LoraConfig(
            r=int(lora["r"]),
            lora_alpha=int(lora["alpha"]),
            lora_dropout=float(lora["dropout"]),
            bias=str(lora["bias"]),
            target_modules=list(lora["target_modules"]),
        )
        model = get_peft_model(base, lora_config)
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()

    if bool(cfg["training"].get("gradient_checkpointing", True)):
        try:
            model.gradient_checkpointing_enable()
            print("gradient_checkpointing_enable: ok", flush=True)
        except Exception as e:
            print(f"gradient_checkpointing_enable skipped: {e}", flush=True)

    trainable = [p for p in model.parameters() if p.requires_grad]
    n_trainable = sum(p.numel() for p in trainable)
    print(f"Trainable params: {n_trainable:,}", flush=True)
    if n_trainable == 0:
        raise RuntimeError("No trainable params after loading PEFT adapter.")

    return tokenizer, model, trainable


def _num_image_token(model) -> int:
    base = model.base_model.model if hasattr(model, "base_model") else model
    return int(base.num_image_token)


def _forward_logits(model, pixel_values, input_ids, attention_mask, image_flags):

    out = model(
        pixel_values=pixel_values,
        input_ids=input_ids,
        attention_mask=attention_mask,
        image_flags=image_flags,
        use_cache=False,
        return_dict=True,
    )
    return out.logits


def _response_logprob(logits, input_ids, response_mask) -> torch.Tensor:

    shift_logits = logits[:, :-1, :]
    shift_labels = input_ids[:, 1:]
    shift_mask = response_mask[:, 1:].to(shift_logits.dtype)
    logp = F.log_softmax(shift_logits.float(), dim=-1)
    token_logp = logp.gather(-1, shift_labels.unsqueeze(-1)).squeeze(-1)
    return (token_logp * shift_mask).sum(dim=-1) / shift_mask.sum(dim=-1).clamp(min=1)


def train(cfg: dict) -> None:
    transformers.set_seed(int(cfg.get("seed", 42)))
    torch.manual_seed(int(cfg.get("seed", 42)))

    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    save_config(cfg, out_dir / "config.yaml")

    tokenizer, model, trainable = setup_model(cfg)
    nit = _num_image_token(model)

    pairs_path = cfg["pairs"]
    dataset = VideoDPOPairDataset(pairs_path, tokenizer, cfg, nit)
    print(f"  pairs: {len(dataset)} (after filtering empty rejected)", flush=True)

    t = cfg["training"]
    dpo = cfg["dpo"]
    beta = float(dpo.get("beta", 0.1))
    alpha = float(dpo.get("alpha", 0.0))
    epochs = int(t["epochs"])
    accum = int(t.get("gradient_accumulation_steps", 1))

    loader = DataLoader(
        dataset,
        batch_size=int(t["per_device_train_batch_size"]),
        shuffle=True,
        num_workers=int(t.get("dataloader_num_workers", 2)),
        collate_fn=collate_dpo,
    )

    optimizer = torch.optim.AdamW(
        trainable,
        lr=float(t["learning_rate"]),
        weight_decay=float(t.get("weight_decay", 0.0)),
    )
    total_steps = len(loader) * epochs
    warmup_steps = int(float(t.get("warmup_ratio", 0.0)) * total_steps) or int(
        t.get("warmup_steps", 0)
    )
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        lr_lambda=lambda step: min(1.0, (step + 1) / max(1, warmup_steps)),
    )

    device = next(model.parameters()).device
    save_steps = int(t.get("save_steps", 500))
    log_steps = int(t.get("logging_steps", 25))
    max_grad_norm = float(t.get("max_grad_norm", 1.0))

    mode = "ADPO" if alpha > 0 else "DPO"
    print(f"\nStarting {mode} training  beta={beta}  alpha={alpha}", flush=True)
    print(f"  {epochs} epochs × {len(loader)} steps = {total_steps} total", flush=True)

    model.train()
    optimizer.zero_grad()
    global_step = 0
    for epoch in range(epochs):
        for step, batch in enumerate(loader):
            batch = {k: v.to(device) for k, v in batch.items()}
            pixel_values = batch["pixel_values"].to(next(model.parameters()).dtype)
            image_flags = batch["image_flags"]

            with torch.no_grad(), model.disable_adapter():
                ref_c_logits = _forward_logits(
                    model, pixel_values,
                    batch["chosen_input_ids"], batch["chosen_attention_mask"],
                    image_flags,
                )
                ref_r_logits = _forward_logits(
                    model, pixel_values,
                    batch["rejected_input_ids"], batch["rejected_attention_mask"],
                    image_flags,
                )
                ref_lp_c = _response_logprob(
                    ref_c_logits, batch["chosen_input_ids"], batch["chosen_response_mask"]
                )
                ref_lp_r = _response_logprob(
                    ref_r_logits, batch["rejected_input_ids"], batch["rejected_response_mask"]
                )


            pol_c_logits = _forward_logits(
                model, pixel_values,
                batch["chosen_input_ids"], batch["chosen_attention_mask"],
                image_flags,
            )
            pol_r_logits = _forward_logits(
                model, pixel_values,
                batch["rejected_input_ids"], batch["rejected_attention_mask"],
                image_flags,
            )
            pol_lp_c = _response_logprob(
                pol_c_logits, batch["chosen_input_ids"], batch["chosen_response_mask"]
            )
            pol_lp_r = _response_logprob(
                pol_r_logits, batch["rejected_input_ids"], batch["rejected_response_mask"]
            )

            margin = beta * ((pol_lp_c - ref_lp_c) - (pol_lp_r - ref_lp_r))
            loss_dpo = -F.logsigmoid(margin).mean()
            if alpha > 0:
                anchor = ((pol_lp_c - ref_lp_c) ** 2 + (pol_lp_r - ref_lp_r) ** 2).mean()
                loss = loss_dpo + alpha * anchor
            else:
                anchor = torch.tensor(0.0, device=loss_dpo.device)
                loss = loss_dpo

            (loss / accum).backward()

            if (step + 1) % accum == 0:
                torch.nn.utils.clip_grad_norm_(trainable, max_grad_norm)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
                global_step += 1

                if global_step % log_steps == 0:
                    acc = (margin > 0).float().mean().item()
                    print(
                        f"  epoch {epoch} step {global_step}/{total_steps // accum}"
                        f" | loss {loss.item():.4f}"
                        f" | dpo {loss_dpo.item():.4f}"
                        f" | anchor {anchor.item():.4f}"
                        f" | pref-acc {acc:.3f}",
                        flush=True,
                    )
                if global_step % save_steps == 0:
                    ckpt_dir = out_dir / f"checkpoint-{global_step}"
                    model.save_pretrained(ckpt_dir)
                    tokenizer.save_pretrained(ckpt_dir)

    print(f"\nSaving final LoRA adapter to {out_dir}", flush=True)
    model.save_pretrained(out_dir)
    tokenizer.save_pretrained(out_dir)
    print("Done.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="train_model/configs/dpo.yaml")
    parser.add_argument("--override", action="append", default=[])
    args = parser.parse_args()
    cfg = load_config(args.config, overrides=args.override)
    train(cfg)


if __name__ == "__main__":
    main()

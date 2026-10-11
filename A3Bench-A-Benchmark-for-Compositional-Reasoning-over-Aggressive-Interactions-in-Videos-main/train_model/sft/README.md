# Phase 1: SFT Baseline Training

Fine-tune InternVL2.5-8B on the benchmark questions using LoRA (Low-Rank Adaptation).

## Overview

**Goal:** Establish a baseline by supervised fine-tuning on direct answers (no reasoning chains yet).

**Duration:** Weeks 1-3

**Compute:** 1 node (4x A100 80GB), ~24-48 hours

## Pipeline

### 1. Regenerate Benchmark
```bash
python train_model/sft/regenerate_benchmark.py
```

**Input:** `annotations.json` (existing)

**Output:** `train_model/data/generated_questions.json`

- Regenerates the benchmark using improved distractor builders
- `compound_aggressor_victim`: local bystander pool + role reversal (7/7 in-cast)
- `compound_aggressor_action_victim`: bystander injection + role reversal (6/7 in-cast)
- `sequence_verification`: bystander swaps (7/7 in-cast)
- Target: ~5-6 primary questions per video

### 2. Format SFT Data
```bash
python train_model/sft/format_data.py
```

**Input:** `train_model/data/generated_questions.json`, `annotations.json`

**Outputs:**
- `train_model/data/sft_train.json` (80%)
- `train_model/data/sft_val.json` (10%)
- `train_model/data/sft_test.json` (10%)

**Format:** Each example contains:
```json
{
  "video_name": "punch_facebook_001.mp4",
  "question_type": "compound_aggressor_victim",
  "question_index": 0,
  "is_trick": false,
  "video_context": "Aggressor: person in black shirt\nVictim: person in dark shirt\n...",
  "prompt": "Who was the aggressor and who was the victim?",
  "correct_answer": "Aggressor: person in black shirt; Victim: person in dark shirt",
  "all_answers": [...],
  "correct_index": 2
}
```

- **Stratified split:** Balanced distribution by question type across train/val/test
- **Phase 1 format:** Direct answers (no CoT yet; Phase 2 adds reasoning chains)

### 3. Train SFT Model
```bash
python train_model/sft/train.py \
  --train-data train_model/data/sft_train.json \
  --val-data train_model/data/sft_val.json \
  --output-dir train_model/models/sft \
  --epochs 3 \
  --batch-size 4 \
  --lr 5e-4
```

**Model:** InternVL2.5-8B + LoRA (rank 8)

**Training Config:**
- LoRA rank: 8, alpha: 16, dropout: 0.05
- Target modules: `q_proj`, `v_proj` (attention projections)
- Learning rate: 5e-4, warmup: 500 steps
- Batch size: 4 per GPU, gradient accumulation: 2
- Evaluation every 500 steps, save every 500 steps
- Early stopping on validation loss

**Output:** `train_model/models/sft/` (best checkpoint + training logs)

### 4. Evaluate
```bash
python plan2_sft/evaluate_sft.py \
  --model train_model/models/sft \
  --test-data train_model/data/sft_test.json \
  --output train_model/eval/sft_baseline_results.json
```

**Metrics:**
- Overall accuracy (exact match on answer)
- Per-question-type breakdown
- Trick vs non-trick performance

## Running the Full Pipeline

```bash
chmod +x plan2_sft/run_phase1.sh
./plan2_sft/run_phase1.sh
```

This runs all 4 steps in sequence.

## Outputs

After Phase 1:
- **Checkpoint:** `train_model/models/sft` (best model + LoRA weights)
- **Evaluation:** `train_model/eval/sft_baseline_results.json` (accuracy breakdown)
- **Training data:** `train_model/data/sft_{train,val,test}.json` (reused in Phases 2-3)

## Next Steps (Phase 2)

Phase 2 will:
1. Generate CoT reasoning chains via GPT-4o for compound/complex questions
2. Augment training data with reasoning chains
3. Fine-tune Phase 1 checkpoint on mixed data (CoT for compounds, direct for simple)

See `plan2_cot/README.md` for Phase 2 details.

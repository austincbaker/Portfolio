# Video Aggression Understanding - VLM Evaluation Pipeline

Evaluate Vision-Language Models on their ability to understand aggressive behavior in videos. The pipeline generates multiple-choice questions from annotated videos and benchmarks models on 6 question types across ~2,700 videos.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Pre-generate questions (one-time, no GPU needed)
python generate_questions_local.py annotations.json -o generated_questions.json

# 3. Run evaluation
./eval_model.sh --file generated_questions.json --model qwen-7b
```

## Project Structure

```
prompt_generator/
  generator.py              # Question generation logic
  answer_bank.py            # Distractor answer pool builder
  templates.py              # 17 question type templates
  generate_questions.py     # Module for pre-generating questions
  evaluation/
    run_evaluation.py        # Single-process evaluation CLI
    parallel_runner.py       # Multi-GPU subprocess orchestrator
    gpu_worker.py            # Per-GPU worker process
    evaluator.py             # Core evaluation logic
    video_processor.py       # Frame extraction (OpenCV/Decord)
    model_loader/
      registry.py            # Model shortcut registry
      base.py                # BaseVLMLoader interface
      ovis.py, qwen_vl.py, internvl.py, ...  # Per-family loaders

eval_model.sh               # Main entry point for running evaluations
all_model_multi_gpu.sbatch   # SLURM batch script (called by eval_model.sh)
monitor_job.sh               # Real-time job monitoring
generate_questions_local.py  # Standalone question generation script
annotations.json             # Video annotations (aggressor, victim, action, etc.)
generated_questions.json     # Pre-generated questions (output of step 2)
videos/                      # Video files directory
```

## Evaluation Workflow

### Step 1: Generate Questions

Pre-generate questions once, then reuse across all models. This ensures every model answers the exact same questions for fair comparison.

```bash
python generate_questions_local.py annotations.json -o generated_questions.json
```

Options:
- `-d NUM` - Number of distractor answers per question (default: 7, giving 8 total options)
- `-o PATH` - Output file path

This produces 6 questions per video (16,164 total for the full dataset).

### Step 2: Run Model Evaluation

**Using eval_model.sh (recommended):**

```bash
# Evaluate a single model with pre-generated questions
./eval_model.sh --file generated_questions.json --model qwen-7b

# Without pre-generated questions (generates on-the-fly)
./eval_model.sh --model ovis-9b
```

The script submits a SLURM job and automatically starts monitoring it.

**Direct sbatch submission:**

```bash
# With questions file
sbatch --export=MODEL=qwen-7b,QUESTIONS_FILE=generated_questions.json all_model_multi_gpu.sbatch

# Without questions file
sbatch --export=MODEL=internvl2.5-8b all_model_multi_gpu.sbatch
```

**Direct Python (no SLURM):**

```bash
python -m prompt_generator.evaluation.parallel_runner \
    annotations.json videos/ \
    -m qwen-7b \
    -g 4 \
    --questions-file generated_questions.json
```

### Step 3: Monitor Jobs

Jobs are monitored automatically when using `eval_model.sh`. To monitor manually:

```bash
./monitor_job.sh <SLURM_JOB_ID>
```

Checks job status every 60 seconds, tails output/error logs, and reports the final state.

### Step 4: Review Results

Results are saved to `results_<model_name>/`:
- `evaluation_<timestamp>.json` - Full results with per-question accuracy
- `checkpoints/` - Per-GPU checkpoint files (for resume support)
- `logs/` - Per-GPU stdout/stderr logs

## Available Models

Use shortcuts or full HuggingFace paths with `--model`.

### Small (2-3B)
| Shortcut | Model |
|---|---|
| `qwen-3b` | Qwen/Qwen2.5-VL-3B-Instruct |
| `internvl-2b` | OpenGVLab/InternVL3-2B |
| `ovis-2b` | AIDC-AI/Ovis2.5-2B |
| `kimi-3b` | moonshotai/Kimi-VL-A3B-Instruct |
| `kimi-3b-thinking` | moonshotai/Kimi-VL-A3B-Thinking |

### Medium (7-9B)
| Shortcut | Model |
|---|---|
| `qwen-7b` | Qwen/Qwen2.5-VL-7B-Instruct |
| `internvl-8b` | OpenGVLab/InternVL3-8B |
| `internvl2.5-8b` | OpenGVLab/InternVL2_5-8B |
| `ovis-9b` | AIDC-AI/Ovis2.5-9B |
| `ovis2-8b` | AIDC-AI/Ovis2-8B |
| `nvila-8b` | nvidia/NVILA-8B |
| `llava-video-7b` | lmms-lab/LLaVA-Video-7B-Qwen2 |
| `videollama-7b` | DAMO-NLP-SG/VideoLLaMA3-7B |
| `videochat-7b` | OpenGVLab/VideoChat-Flash-Qwen2_5-7B_InternVideo2-1B |
| `oryx-7b` | THUdyh/Oryx-7B |
| `valley-7b` | bytedance-research/Valley-Eagle-7B |
| `video-r1-7b` | Video-R1/Video-R1-7B |
| `lumian-7b` | prithivMLmods/Lumian-VLR-7B-Thinking |
| `hunyuan-7b` | TencentARC/ARC-Hunyuan-Video-7B |
| `internvideo-8b` | OpenGVLab/InternVideo2_5_Chat_8B |

### Large (11-15B)
| Shortcut | Model |
|---|---|
| `llama-11b` | meta-llama/Llama-3.2-11B-Vision |
| `nvila-15b` | nvidia/NVILA-15B |

### Extra Large (72-90B, multi-GPU required)
| Shortcut | Model |
|---|---|
| `qwen-72b` | Qwen/Qwen2.5-VL-72B-Instruct |
| `internvl-78b` | OpenGVLab/InternVL3-78B |
| `llama-90b` | meta-llama/Llama-3.2-90B-Vision |

## Question Types

Each video generates 6 questions:

| Type | What It Tests |
|---|---|
| Aggressor Identification | Who is performing the aggressive action? |
| Victim Recognition | Who is the target/victim? |
| Compound Aggressor-Victim | Identify both aggressor and victim together |
| Compound Aggressor-Action-Victim | Who did what to whom? |
| Compound Action-Victims | What action occurred and how many victims? |
| Interaction Summary | Which summary describes the full interaction? |

## Configuration

The SLURM script (`all_model_multi_gpu.sbatch`) has these defaults that can be edited directly:

| Parameter | Default | Description |
|---|---|---|
| `NUM_GPUS` | 4 | Number of GPUs for parallel evaluation |
| `NUM_FRAMES` | 8 | Video frames extracted per clip |
| `STAGGER_DELAY` | 30 | Seconds between GPU worker starts |
| `--thinking-budget` | 512 | Token budget for model reasoning |
| `--max-new-tokens` | 1024 | Max generation length |

## Checkpoint & Resume

Jobs automatically checkpoint after each video. If a job is interrupted (timeout, preemption), resubmitting the same command resumes from where it left off. Checkpoints are stored per-GPU in `results_<model>/checkpoints/`.

To start fresh and ignore existing checkpoints, add `--no-resume` to the Python command or clear the checkpoint directory.

## Annotations Format

Each entry in `annotations.json`:

```json
{
  "file_name": "punch_chatgpt_025.mp4",
  "action": "punch",
  "aggressor": "person in a dark jacket",
  "victim": "person in a dark blue long-sleeve shirt",
  "environment": "outdoor parking lot",
  "bystanders": ["person in white shirt"]
}
```

## Requirements

- Python 3.10+
- PyTorch 2.0+
- CUDA-capable GPU (H100 recommended)
- SLURM cluster (for batch submission; optional for direct Python usage)
- `pip install -r requirements.txt`
- Flash Attention 2 (optional but recommended): `pip install flash-attn --no-build-isolation`

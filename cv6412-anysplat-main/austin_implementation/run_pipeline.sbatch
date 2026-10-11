#!/bin/bash
#SBATCH --job-name=austin_pipeline
#SBATCH --partition=gpu
#SBATCH --account=group3
#SBATCH --gres=gpu:ampere:1
#SBATCH --mem=64G
#SBATCH --output=/home/au182598/cv6412-anysplat/pipeline_%j.out
#SBATCH --error=/home/au182598/cv6412-anysplat/pipeline_%j.err
#SBATCH --requeue
#SBATCH --signal=B:USR1@120
#SBATCH --open-mode=append

# ==============================================================================
# Pipeline Job
# ==============================================================================
# Runs the 6-stage pipeline on the riverview scene:
#   reconstruct -> segment -> lift_masks -> reason -> edit -> render
#
# Usage:
#   sbatch run_pipeline.sbatch
#   sbatch --export=QUERY="remove all metal objects" run_pipeline.sbatch
#   sbatch --export=IMAGE_DIR=/path/to/images run_pipeline.sbatch
#   sbatch --export=VIDEO=/path/to/video.mp4,QUERY="remove wooden objects" run_pipeline.sbatch
# ==============================================================================

# Environment setup — source miniconda3 directly (module system unavailable in sbatch)
source /home/au182598/miniconda3/etc/profile.d/conda.sh
conda activate base

# Configuration
REPO_DIR="/home/au182598/cv6412-anysplat"
IMAGE_DIR="${IMAGE_DIR:-$REPO_DIR/anysplat/examples/vrnerf/riverview}"
VIDEO="${VIDEO:-}"      # path to video file; if set, overrides IMAGE_DIR
QUERY="${QUERY:-remove all wooden objects}"
OUTPUT_DIR="${OUTPUT_DIR:-$REPO_DIR/outputs/run_${SLURM_JOB_ID}}"

# Track if we received a timeout signal
TIMEOUT_SIGNAL_RECEIVED=0

# Signal handler for graceful shutdown before timeout
handle_timeout_signal() {
    echo ""
    echo "=============================================="
    echo "TIMEOUT WARNING: Received USR1 signal"
    echo "Job will be requeued and resume from checkpoint"
    echo "Terminating workers gracefully..."
    echo "Time: $(date)"
    echo "=============================================="
    TIMEOUT_SIGNAL_RECEIVED=1

    pkill -P $$
    sleep 5

    echo "Requeueing job $SLURM_JOB_ID. Progress saved in outputs cache."
    scontrol requeue "$SLURM_JOB_ID"
}

trap 'handle_timeout_signal' USR1

# Print job info
echo "=============================================="
echo "Austin Pipeline"
echo "=============================================="
echo "Job ID:    $SLURM_JOB_ID"
echo "Node:      $SLURM_NODELIST"
echo "Input:     ${VIDEO:-$IMAGE_DIR}"
echo "Query:     $QUERY"
echo "Output:    $OUTPUT_DIR"
echo "Start:     $(date)"
echo "Requeues:  ${SLURM_RESTART_COUNT:-0}"
echo "=============================================="
echo ""

# Print GPU info
echo "GPU:"
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv
echo ""

cd "$REPO_DIR"

###################################
# Install missing dependencies    #
# Already in base: torch, torchvision, transformers,  #
#   qwen-vl-utils, einops, jaxtyping, omegaconf,      #
#   hydra-core, timm, huggingface_hub                  #
###################################
echo "=== Installing missing dependencies ==="

# Pure-python deps from AnySplat + pipeline requirements
pip install pytest sam3 --quiet
pip install dacite beartype lpips e3nn plyfile safetensors tabulate \
    scikit-image imageio colorama pydantic lightning wandb --quiet
pip install scikit-video "svg.py" colorspacious matplotlib "moviepy==1.0.3" \
    opencv-python Pillow --quiet
# open3d has no Python 3.13 wheel — skip it (not in our code path)

# xformers — needed for memory_efficient_attention in AnySplat encoder
pip install xformers --quiet

# gsplat — try PyPI (supports Python 3.13 in recent releases)
pip install gsplat --quiet

# torch-scatter — indexed wheel for torch 2.10.0 + CUDA 12.8
pip install torch-scatter -f https://data.pyg.org/whl/torch-2.10.0+cu128.html --quiet

# GroundingDINO no longer needed — SAM3 handles detection + segmentation

echo "Dependencies ready."
echo ""

###################################
# Unit tests (no GPU needed)      #
###################################
echo "=== Unit Tests ==="
python -m pytest tests/ -v
UNIT_TEST_EXIT=$?
if [ $UNIT_TEST_EXIT -ne 0 ]; then
    echo "Unit tests FAILED (exit $UNIT_TEST_EXIT) — aborting pipeline."
    exit $UNIT_TEST_EXIT
fi
echo ""

###################################
# Full pipeline                   #
###################################
echo "=== Running Full Pipeline ==="
INPUT_ARG="--image_dir $IMAGE_DIR"
if [ -n "$VIDEO" ]; then
    INPUT_ARG="--video $VIDEO"
fi
python -m pipeline \
    $INPUT_ARG \
    --query "$QUERY" \
    --output_dir "$OUTPUT_DIR" &

PYTHON_PID=$!

wait $PYTHON_PID
EXIT_CODE=$?

# Print completion info
echo ""
echo "=============================================="
if [ $TIMEOUT_SIGNAL_RECEIVED -eq 1 ]; then
    echo "Job interrupted for requeue: $(date)"
    echo "Caching means progress is preserved — will resume on next run."
elif [ $EXIT_CODE -eq 0 ]; then
    echo "Pipeline completed successfully: $(date)"
else
    echo "Pipeline failed with exit code $EXIT_CODE: $(date)"
fi
echo "=============================================="

echo ""
echo "Output images:"
ls -la "$OUTPUT_DIR/results/"*.png 2>/dev/null || echo "  (no PNG files found)"

echo ""
echo "Cache files:"
ls -la "$OUTPUT_DIR/cache/"*.pt "$OUTPUT_DIR/cache/"*.json 2>/dev/null || echo "  (no cache files found)"

exit $EXIT_CODE

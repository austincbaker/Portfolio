# DecompFormer

Language-guided 3D scene editing pipeline. Given multi-view images (or a video) and a natural language query like *"remove all wooden objects"*, the pipeline reconstructs the scene in 3D, identifies the target objects, and renders the edited scene from all viewpoints.

## Architecture

```
Input Images + Text Query
          |
          v
  ┌──────────────┐
  │  Stage 0:    │  VLM (InternVL3-14B) inspects scene images + query
  │  Semantic    │  to identify which visible objects match the edit.
  │  Router      │  Output: list of object nouns (e.g. ["chair", "shelf"])
  └──────┬───────┘
         │
  ┌──────┴───────┐
  │  Stage 1:    │  AnySplat (VGGT-1B backbone) produces a 3D Gaussian
  │  Reconstruct │  Splatting scene from uncalibrated multi-view images.
  │              │  Output: ~1.5M Gaussians + camera poses
  └──────┬───────┘
         │
  ┌──────┴───────┐
  │  Stage 2:    │  SAM3 performs text-prompted detection + segmentation
  │  Segment     │  of VLM-identified objects in each view (2D masks).
  └──────┬───────┘
         │
  ┌──────┴───────┐
  │  Stage 3:    │  Project 3D Gaussians into each camera view, look up
  │  Lift Masks  │  which 2D mask covers each projection, majority vote
  │              │  across views to assign a per-Gaussian object label.
  └──────┬───────┘
         │
  ┌──────┴───────┐
  │  Stage 4:    │  For each labeled object, mirror its Gaussians across
  │  Complete    │  the centroid plane to infer back-side geometry that
  │  Objects     │  was never observed (geometric mirroring baseline).
  └──────┬───────┘
         │
  ┌──────┴───────┐
  │  Stage 5:    │  Mark all Gaussians belonging to VLM-identified
  │  Edit        │  objects for removal. No secondary matching or
  │              │  fallback — the VLM's decision is final.
  └──────┬───────┘
         │
  ┌──────┴───────┐
  │  Stage 6:    │  Render the original, highlighted, and edited scenes
  │  Render      │  from all K input camera poses. Exports PNG previews
  │              │  and MP4 orbit videos with sRGB gamma correction.
  └──────────────┘
```

### Intermediate Visualizations

Each stage saves diagnostic images to `results/stages/`:

| File | Description |
|------|-------------|
| `stage1_pointcloud.png` | Top-down and front-view scatter plot of Gaussian means |
| `stage2_seg_01.png` ... | Segmentation mask overlays on input images |
| `stage3_labels.png` | Gaussians rendered with per-object label colors |
| `stage3_labels_legend.png` | Color-to-object legend |
| `stage4_completion.png` | Original vs mirrored back-side Gaussians |

### Caching

Every stage caches its output to `{output_dir}/cache/` as `.pt` (tensors) or `.json` (metadata). Re-running with the same output directory skips completed stages automatically. If a SLURM job times out, it requeues and resumes from the last cached stage.

## Project Structure

```
pipeline/
  __main__.py          # CLI entry point (python -m pipeline)
  run.py               # Orchestrator — wires all stages
  types.py             # Dataclass interfaces between stages
  cache.py             # load_or_run() caching helper
  image_utils.py       # Shared image loading / center-crop
  video_utils.py       # Frame extraction from video files
  semantic_router.py   # Stage 0: VLM + images → object list
  reconstruct.py       # Stage 1: AnySplat → 3D Gaussians
  segment.py           # Stage 2: SAM3 text-prompted detection + segmentation → 2D masks
  lift_masks.py        # Stage 3: 2D masks → per-Gaussian labels
  complete_objects.py   # Stage 4: Geometric mirroring completion
  edit.py              # Stage 5: Apply edits (remove labeled Gaussians)
  render.py            # Stage 6: Render views + export PNGs/MP4s
  visualize.py         # Per-stage diagnostic visualizations
  reason.py            # (Legacy) Per-object VLM property reasoning

anysplat/              # AnySplat source (VGGT-1B, feed-forward 3DGS)
tests/                 # Unit tests for core pipeline logic
```

## Requirements

- Python 3.11+
- CUDA GPU (tested on A100 80GB, A6000 49GB)
- PyTorch 2.x with CUDA support
- Key dependencies: `gsplat`, `sam3`, `transformers`, `torchvision`, `imageio`, `matplotlib`

HuggingFace models downloaded on first run:
- `OpenGVLab/InternVL3-14B` (~28GB, bfloat16)
- `lhjiang/anysplat` (VGGT-1B, ~4GB)
- `facebook/sam3`

## Usage

### Local (with GPU)

```bash
# From images
python -m pipeline \
    --image_dir path/to/images \
    --query "remove all wooden objects" \
    --output_dir outputs/my_run

# From video (extracts frames automatically at 1fps)
python -m pipeline \
    --video path/to/video.mp4 \
    --query "remove anything fragile" \
    --output_dir outputs/my_run
```

### SLURM Cluster

```bash
# Default (riverview scene, "remove all wooden objects")
sbatch run_pipeline.sbatch

# Custom query
sbatch --export=QUERY="remove all metal objects" run_pipeline.sbatch

# Custom images
sbatch --export=IMAGE_DIR=/path/to/images run_pipeline.sbatch

# Video input
sbatch --export=VIDEO=/path/to/video.mp4,QUERY="remove wooden objects" run_pipeline.sbatch
```

Logs go to `pipeline_<JOB_ID>.out` and `pipeline_<JOB_ID>.err` in the repo directory.

### Output

```
outputs/my_run/
  cache/                  # Cached stage outputs (.pt, .json)
  results/
    original.png          # First-view render of original scene
    highlighted.png       # Target objects highlighted in red
    deleted.png           # Scene with target objects removed
    original.mp4          # Orbit video of original scene
    highlighted.mp4       # Orbit video with highlights
    deleted.mp4           # Orbit video of edited scene
    stages/               # Per-stage diagnostic visualizations
```

## Input Image Guidelines

For best results, capture **6-20 images** of the scene:
- Walk around the subject, spacing shots ~20-30 degrees apart
- Keep the subject centered in frame
- Maintain consistent lighting across all shots
- Avoid motion blur — hold steady or use a tripod
- Overlap between adjacent views should be at least 50%

Single images produce flat, low-quality reconstructions (~170K Gaussians). Multi-view input produces rich 3D scenes (1.5M+ Gaussians) with proper depth and geometry.

For **video input**, the pipeline automatically extracts frames at 1fps, filters out blurry frames, and caps at 20 frames.

## Tests

```bash
python -m pytest tests/ -v
```

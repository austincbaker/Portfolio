# cv6412-anysplat

Course repository for **UCF CAP 6412 — Advanced Computer Vision, Spring 2026**.

The shared theme across every subproject is **language-guided 3D scene editing from
multi-view images**: given a set of photos (or a video) and a natural-language query
like *"remove the chair"* or *"paint the guitar blue"*, recover a 3D representation of
the scene, identify the targeted object(s), and re-render the scene after the edit.

---

## Repository layout

| Path | What it is | Owner |
|---|---|---|
| [`austin_implementation/`](austin_implementation/README.md) | **DecompFormer** — 6-stage pipeline (router → reconstruct → segment → lift_masks → complete → edit → render) using AnySplat + SAM3 + InternVL3-14B. SLURM-ready. | Austin Baker |
| `anysplat/` | Upstream **AnySplat** (VGGT-1B feed-forward 3D Gaussian Splatting), vendored. Imported as a library by `austin_implementation/` and `tina_e2e_3dvlm/`. Don't edit unless the task is explicitly about AnySplat itself. | (vendored) |

---

## Per-implementation summaries

### `austin_implementation/` — DecompFormer

Six stages, each cached to `{output_dir}/cache/` as `.pt` (tensors) or `.json`
(metadata). Reruns skip completed stages. Stage 0 uses **InternVL3-14B** to map a
free-form query to a list of object nouns; Stage 1 reconstructs the scene with
**AnySplat** into ~1.5M Gaussians; Stage 2 runs **SAM3** text-prompted segmentation
per view; Stage 3 projects each Gaussian into every camera and majority-votes
labels from the 2D masks; Stage 4 mirrors object Gaussians across their centroid
plane to fake unseen back-side geometry; Stages 5–6 apply the edit and render
PNG previews + MP4 orbit videos.

The SLURM driver (`run_pipeline.sbatch`) handles `SIGUSR1` cleanly: on cluster
timeout the job kills its workers, calls `scontrol requeue`, and the next run
resumes from the cache. Unit tests live in `austin_implementation/tests/`. See
`austin_implementation/README.md` for full usage and the architecture diagram.

---

## Contributions

| Person | Primary contribution |
|---|---|
| **Austin Baker** | DecompFormer pipeline (`austin_implementation/`), SLURM signal-handling driver, vendored AnySplat integration, SAM2→SAM3 swap, Stage 4 mirroring completion, video-input frame extraction. |
---

## Quickstart

Each pipeline has its own README with full instructions. The shortest paths:

```bash
# DecompFormer (CUDA needed)
cd austin_implementation
python -m pipeline --image_dir <dir> --query "<text>" --output_dir outputs/run_01
python -m pytest tests/ -v

```

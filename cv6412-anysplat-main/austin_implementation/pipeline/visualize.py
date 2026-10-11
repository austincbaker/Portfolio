# pipeline/visualize.py
"""Intermediate-stage visualization helpers.

Saves diagnostic images to results_dir/stages/ after each pipeline stage.
All functions catch and log exceptions so they never crash the main pipeline.
"""
import os
import sys

import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from pipeline.types import GaussiansResult, SegmentationResult, LiftResult, CompletionResult

# Distinct colors for up to 20 objects (matplotlib tab20)
_TAB20 = plt.cm.tab20.colors  # tuple of 20 (R,G,B) floats in [0,1]


def _obj_color(idx: int) -> tuple[float, float, float]:
    return _TAB20[idx % 20]


def _sh_dc(color_01: float) -> float:
    """Convert a [0,1] linear color value to a Gaussian SH DC coefficient.

    DC term contribution: color = coeff * Y_0^0 = coeff / (2*sqrt(pi)) ≈ coeff * 0.2821
    Inverse: coeff = color / 0.2821.  Clamped to the range used in edit.py (~1.7 for full red).
    """
    return color_01 / 0.2821


# ---------------------------------------------------------------------------
# Stage 1 – Gaussian point cloud
# ---------------------------------------------------------------------------

def save_stage1_pointcloud(gaussians: GaussiansResult, stages_dir: str):
    """Top-down and front-view scatter of Gaussian means colored by height/depth."""
    try:
        os.makedirs(stages_dir, exist_ok=True)
        means = gaussians.means.cpu().float().numpy()

        # Subsample for speed
        if len(means) > 50_000:
            idx = np.random.default_rng(0).choice(len(means), 50_000, replace=False)
            means = means[idx]

        x, y, z = means[:, 0], means[:, 1], means[:, 2]

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle(f"Stage 1: Gaussian Point Cloud  ({gaussians.means.shape[0]:,} Gaussians)", fontsize=13)

        sc = axes[0].scatter(x, z, c=y, cmap="viridis", s=0.4, alpha=0.5, linewidths=0)
        axes[0].set_title("Top-down view (X–Z)")
        axes[0].set_xlabel("X"); axes[0].set_ylabel("Z")
        axes[0].set_aspect("equal")
        plt.colorbar(sc, ax=axes[0], label="Y (height)")

        sc2 = axes[1].scatter(x, -y, c=z, cmap="plasma", s=0.4, alpha=0.5, linewidths=0)
        axes[1].set_title("Front view (X–Y)")
        axes[1].set_xlabel("X"); axes[1].set_ylabel("Y")
        axes[1].set_aspect("equal")
        plt.colorbar(sc2, ax=axes[1], label="Z (depth)")

        plt.tight_layout()
        path = os.path.join(stages_dir, "stage1_pointcloud.png")
        plt.savefig(path, dpi=120, bbox_inches="tight")
        plt.close()
        print(f"[viz] {path}")
    except Exception as e:
        print(f"[viz] stage1 skipped: {e}")


# ---------------------------------------------------------------------------
# Stage 2 – Segmentation mask overlays
# ---------------------------------------------------------------------------

def save_stage2_masks(image_dir: str, segments: SegmentationResult, stages_dir: str):
    """Overlay all segmentation masks on the first few input images."""
    try:
        from pipeline.image_utils import load_and_crop_images
        os.makedirs(stages_dir, exist_ok=True)

        images = load_and_crop_images(image_dir)
        n_save = min(3, len(images))

        for k in range(n_save):
            img = images[k].copy()          # uint8 [H, W, 3]
            overlay = img.astype(np.float32)
            legend_patches = []

            for obj_idx, name in enumerate(segments.object_names):
                mask = segments.masks[name][k].cpu().numpy()   # [H, W] bool
                if not mask.any():
                    continue
                color = np.array(_obj_color(obj_idx)) * 255.0
                overlay[mask] = overlay[mask] * 0.35 + color * 0.65
                legend_patches.append(
                    mpatches.Patch(color=_obj_color(obj_idx), label=name)
                )

            fig, ax = plt.subplots(figsize=(8, 8))
            ax.imshow(overlay.clip(0, 255).astype(np.uint8))
            ax.set_title(f"Stage 2: Segmentation masks — image {k + 1}/{len(images)}")
            ax.axis("off")
            if legend_patches:
                ax.legend(handles=legend_patches, loc="lower right",
                          fontsize=7, framealpha=0.85, ncol=2)

            path = os.path.join(stages_dir, f"stage2_seg_{k + 1:02d}.png")
            plt.savefig(path, dpi=120, bbox_inches="tight")
            plt.close()
            print(f"[viz] {path}")
    except Exception as e:
        print(f"[viz] stage2 skipped: {e}")


# ---------------------------------------------------------------------------
# Stage 3 – Label-colored Gaussian render
# ---------------------------------------------------------------------------

def save_stage3_labels(
    gaussians: GaussiansResult,
    lifted: LiftResult,
    decoder,
    stages_dir: str,
):
    """Render the scene with each Gaussian colored by its object label."""
    try:
        ANYSPLAT_DIR = os.path.join(os.path.dirname(__file__), "..", "anysplat")
        if ANYSPLAT_DIR not in sys.path:
            sys.path.insert(0, ANYSPLAT_DIR)
        from src.model.types import Gaussians
        import torchvision

        os.makedirs(stages_dir, exist_ok=True)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        means       = gaussians.means.to(device)
        covariances = gaussians.covariances.to(device)
        harmonics   = gaussians.harmonics.clone().to(device)
        opacities   = gaussians.opacities.to(device)
        scales      = gaussians.scales.to(device)
        rotations   = gaussians.rotations.to(device)
        labels      = lifted.labels.to(device)

        # Zero all SH bands, then write only DC per object
        harmonics[:] = 0.0
        # Unassigned → mid-gray
        for c in range(3):
            harmonics[labels == -1, c, 0] = _sh_dc(0.35)

        for obj_idx, name in enumerate(lifted.object_names):
            obj_mask = labels == obj_idx
            if not obj_mask.any():
                continue
            r, g, b = _obj_color(obj_idx)
            harmonics[obj_mask, 0, 0] = _sh_dc(r)
            harmonics[obj_mask, 1, 0] = _sh_dc(g)
            harmonics[obj_mask, 2, 0] = _sh_dc(b)

        g = Gaussians(
            means=means.unsqueeze(0),
            covariances=covariances.unsqueeze(0),
            harmonics=harmonics.unsqueeze(0),
            opacities=opacities.unsqueeze(0),
            scales=scales.unsqueeze(0),
            rotations=rotations.unsqueeze(0),
        )
        H, W = gaussians.image_size
        ext  = gaussians.extrinsics[0].to(device).unsqueeze(0).unsqueeze(0)
        intr = gaussians.intrinsics[0].to(device).unsqueeze(0).unsqueeze(0)
        near = torch.ones(1, 1, device=device) * 0.01
        far  = torch.ones(1, 1, device=device) * 100.0
        out  = decoder.rendering_fn(g, ext, intr, near, far, (H, W))
        frame = out.color[0, 0]  # [3, H, W]

        path = os.path.join(stages_dir, "stage3_labels.png")
        torchvision.utils.save_image(frame.clamp(0, 1), path)
        print(f"[viz] {path}")

        # Legend
        patches = []
        for obj_idx, name in enumerate(lifted.object_names):
            if (lifted.labels == obj_idx).any():
                n = int((lifted.labels == obj_idx).sum())
                patches.append(
                    mpatches.Patch(color=_obj_color(obj_idx), label=f"{name} ({n:,})")
                )
        patches.append(mpatches.Patch(color=(0.35, 0.35, 0.35), label="background"))

        fig, ax = plt.subplots(figsize=(4, max(3, len(patches) * 0.4)))
        ax.legend(handles=patches, loc="center", fontsize=9)
        ax.axis("off")
        ax.set_title("Stage 3: Object label legend")
        legend_path = os.path.join(stages_dir, "stage3_labels_legend.png")
        plt.savefig(legend_path, dpi=120, bbox_inches="tight")
        plt.close()
        print(f"[viz] {legend_path}")
    except Exception as e:
        print(f"[viz] stage3 skipped: {e}")


# ---------------------------------------------------------------------------
# Stage 4 – 3D completion overlay
# ---------------------------------------------------------------------------

def save_stage4_completion(
    gaussians: GaussiansResult,
    lifted: LiftResult,
    completed: CompletionResult,
    stages_dir: str,
):
    """Top-down scatter: original Gaussians (dots) + mirrored back-side (×)."""
    try:
        os.makedirs(stages_dir, exist_ok=True)

        means  = gaussians.means.cpu().float().numpy()
        labels = lifted.labels.cpu().numpy()

        rng = np.random.default_rng(0)
        if len(means) > 30_000:
            idx = rng.choice(len(means), 30_000, replace=False)
            means  = means[idx]
            labels = labels[idx]

        fig, ax = plt.subplots(figsize=(10, 8))

        # Original Gaussians colored by label
        bg_mask = labels == -1
        if bg_mask.any():
            ax.scatter(means[bg_mask, 0], means[bg_mask, 2],
                       color="lightgray", s=0.3, alpha=0.15, linewidths=0)
        for obj_idx, name in enumerate(lifted.object_names):
            m = means[labels == obj_idx]
            if len(m) == 0:
                continue
            ax.scatter(m[:, 0], m[:, 2],
                       color=_obj_color(obj_idx), s=0.8, alpha=0.5, linewidths=0)

        # Mirrored Gaussians as × markers
        patches = []
        for obj_idx, extra_m in completed.extra_means.items():
            if obj_idx >= len(lifted.object_names):
                continue
            name = lifted.object_names[obj_idx]
            em = extra_m.cpu().float().numpy()
            if len(em) > 5_000:
                em = em[rng.choice(len(em), 5_000, replace=False)]
            ax.scatter(em[:, 0], em[:, 2],
                       color=_obj_color(obj_idx), s=4.0,
                       marker="x", alpha=0.8, linewidths=0.8)
            patches.append(mpatches.Patch(color=_obj_color(obj_idx), label=name))

        ax.set_title("Stage 4: 3D completion — original (·) vs mirrored back-side (×)")
        ax.set_xlabel("X"); ax.set_ylabel("Z")
        ax.set_aspect("equal")
        if patches:
            ax.legend(handles=patches, loc="best", fontsize=7, ncol=2, framealpha=0.85)

        path = os.path.join(stages_dir, "stage4_completion.png")
        plt.savefig(path, dpi=120, bbox_inches="tight")
        plt.close()
        print(f"[viz] {path}")
    except Exception as e:
        print(f"[viz] stage4 skipped: {e}")

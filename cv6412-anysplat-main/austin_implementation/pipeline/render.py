# pipeline/render.py
"""Stage 6: Render original, highlighted, and deleted views using AnySplat's decoder.

Renders from all input camera poses and exports both per-frame PNGs and MP4 videos.
"""
import os
import sys

import imageio
import torch
import torchvision

# AnySplat imports
ANYSPLAT_DIR = os.path.join(os.path.dirname(__file__), "..", "anysplat")
sys.path.insert(0, ANYSPLAT_DIR)

from src.model.types import Gaussians

from pipeline.types import GaussiansResult, EditResult


def _to_batched_gaussians(
    means: torch.Tensor,
    covariances: torch.Tensor,
    harmonics: torch.Tensor,
    opacities: torch.Tensor,
    scales: torch.Tensor,
    rotations: torch.Tensor,
) -> Gaussians:
    """Wrap unbatched tensors into a batched Gaussians object for the decoder."""
    return Gaussians(
        means=means.unsqueeze(0),
        covariances=covariances.unsqueeze(0),
        harmonics=harmonics.unsqueeze(0),
        opacities=opacities.unsqueeze(0),
        scales=scales.unsqueeze(0),
        rotations=rotations.unsqueeze(0),
    )


def _render_view(decoder, gaussians_batched, extrinsic, intrinsic, image_size):
    """Render one view. Returns [3, H, W] RGB tensor."""
    H, W = image_size
    ext = extrinsic.unsqueeze(0).unsqueeze(0)   # [1, 1, 4, 4]
    intr = intrinsic.unsqueeze(0).unsqueeze(0)  # [1, 1, 3, 3]
    near = torch.ones(1, 1, device=ext.device) * 0.01
    far = torch.ones(1, 1, device=ext.device) * 100.0
    output = decoder.rendering_fn(gaussians_batched, ext, intr, near, far, (H, W))
    return output.color[0, 0]  # [3, H, W]


def _to_srgb(frame: torch.Tensor) -> torch.Tensor:
    """Apply sRGB gamma (linear → display) so rendered frames aren't dark."""
    return frame.clamp(0, 1).pow(1 / 2.2)


def _save_video(frames: list, path: str, fps: int = 8):
    """Save a list of [3, H, W] tensors as an MP4."""
    writer = imageio.get_writer(path, fps=fps)
    for f in frames:
        arr = (_to_srgb(f) * 255).byte().permute(1, 2, 0).cpu().numpy()
        writer.append_data(arr)
    writer.close()


def render(
    gaussians: GaussiansResult,
    edits: EditResult,
    decoder,
    results_dir: str = "outputs/results",
    num_views: int = None,
):
    """Stage 6 entry point. Renders all camera views and saves PNGs + MP4s."""
    os.makedirs(results_dir, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Move gaussians to device (may be CPU if loaded from cache)
    gaussians.means = gaussians.means.to(device)
    gaussians.covariances = gaussians.covariances.to(device)
    gaussians.harmonics = gaussians.harmonics.to(device)
    gaussians.opacities = gaussians.opacities.to(device)
    gaussians.scales = gaussians.scales.to(device)
    gaussians.rotations = gaussians.rotations.to(device)
    gaussians.extrinsics = gaussians.extrinsics.to(device)
    gaussians.intrinsics = gaussians.intrinsics.to(device)
    edits.highlight_harmonics = edits.highlight_harmonics.to(device)
    edits.delete_mask = edits.delete_mask.to(device)

    K = gaussians.extrinsics.shape[0]
    num_views = min(num_views or K, K)

    # Build Gaussian objects for each variant
    keep = ~edits.delete_mask
    orig_g = _to_batched_gaussians(
        gaussians.means, gaussians.covariances, gaussians.harmonics,
        gaussians.opacities, gaussians.scales, gaussians.rotations,
    )
    highlight_g = _to_batched_gaussians(
        gaussians.means, gaussians.covariances, edits.highlight_harmonics,
        gaussians.opacities, gaussians.scales, gaussians.rotations,
    )
    delete_g = _to_batched_gaussians(
        gaussians.means[keep], gaussians.covariances[keep], gaussians.harmonics[keep],
        gaussians.opacities[keep], gaussians.scales[keep], gaussians.rotations[keep],
    )

    frames_orig, frames_highlight, frames_delete = [], [], []

    print(f"[render] Rendering {num_views} views...")
    for i in range(num_views):
        ext = gaussians.extrinsics[i]
        intr = gaussians.intrinsics[i]

        frames_orig.append(_render_view(decoder, orig_g, ext, intr, gaussians.image_size))
        frames_highlight.append(_render_view(decoder, highlight_g, ext, intr, gaussians.image_size))
        frames_delete.append(_render_view(decoder, delete_g, ext, intr, gaussians.image_size))

        if (i + 1) % 5 == 0 or i == num_views - 1:
            print(f"[render]   {i + 1}/{num_views} views done")

    # Save first-frame PNGs for quick preview (gamma-corrected for display)
    torchvision.utils.save_image(_to_srgb(frames_orig[0]), os.path.join(results_dir, "original.png"))
    torchvision.utils.save_image(_to_srgb(frames_highlight[0]), os.path.join(results_dir, "highlighted.png"))
    torchvision.utils.save_image(_to_srgb(frames_delete[0]), os.path.join(results_dir, "deleted.png"))

    # Save MP4 videos if more than one view
    if num_views > 1:
        _save_video(frames_orig, os.path.join(results_dir, "original.mp4"))
        _save_video(frames_highlight, os.path.join(results_dir, "highlighted.mp4"))
        _save_video(frames_delete, os.path.join(results_dir, "deleted.mp4"))
        print(f"[render] Saved {num_views}-frame videos to {results_dir}/")
    else:
        print(f"[render] Saved single-view PNGs to {results_dir}/")

    print(f"  - original.png / original.mp4")
    print(f"  - highlighted.png / highlighted.mp4")
    print(f"  - deleted.png / deleted.mp4")

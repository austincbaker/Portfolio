"""Render a post-edit GaussiansResult for the rigging experiment.

The rigging pipeline is structured as:

    GaussiansResult  ─bind→  RiggedScene
    RiggedScene, delta ─apply_translate→  GaussiansResult   (new means, other fields by reference)
    GaussiansResult  ─render_rigged_view→  RGB image

So by the time we reach this module, the input is already a world-frame
GaussiansResult. This module is a thin decoder wrapper that saves a single
view as a PNG. We do not duplicate render.py's batched helpers — we import.
"""
from __future__ import annotations

import os
import sys

import torch
import torchvision

ANYSPLAT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "anysplat")
if ANYSPLAT_DIR not in sys.path:
    sys.path.insert(0, ANYSPLAT_DIR)

from pipeline.render import _to_batched_gaussians, _render_view, _to_srgb  # noqa: E402
from pipeline.types import GaussiansResult  # noqa: E402


def render_view(
    gaussians: GaussiansResult,
    decoder,
    view_idx: int = 0,
    device: torch.device | None = None,
) -> torch.Tensor:
    """Render a single camera view. Returns `[3, H, W]` RGB (linear-light).

    `decoder` (AnySplat's DecoderSplattingCUDA) has no learnable parameters,
    so we don't infer the device from it — caller may pass `device`, otherwise
    we use CUDA if available.
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Move tensors to the decoder's device (cache may be on CPU).
    means = gaussians.means.to(device)
    covariances = gaussians.covariances.to(device)
    harmonics = gaussians.harmonics.to(device)
    opacities = gaussians.opacities.to(device)
    scales = gaussians.scales.to(device)
    rotations = gaussians.rotations.to(device)
    ext = gaussians.extrinsics[view_idx].to(device)
    intr = gaussians.intrinsics[view_idx].to(device)

    batched = _to_batched_gaussians(means, covariances, harmonics, opacities, scales, rotations)
    return _render_view(decoder, batched, ext, intr, gaussians.image_size)


def render_and_save(
    gaussians: GaussiansResult,
    decoder,
    out_path: str,
    view_idx: int = 0,
) -> torch.Tensor:
    """Render one view and save as PNG (gamma-corrected for display)."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    frame = render_view(gaussians, decoder, view_idx=view_idx)
    torchvision.utils.save_image(_to_srgb(frame), out_path)
    return frame

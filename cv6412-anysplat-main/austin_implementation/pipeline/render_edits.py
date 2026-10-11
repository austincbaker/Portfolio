"""Render the original scene + a set of edited variants from a fixed camera set.

Output layout:

    <results_dir>/original/<view_idx:03d>.png
    <results_dir>/<edit_name>/<view_idx:03d>.png

Camera set: by default, all input extrinsics from `gaussians.extrinsics`.
Pass `view_indices=[...]` to subsample.

Synthetic orbit cameras are intentionally not generated here — that requires
matching AnySplat's exact c2w convention, which is best validated by the
cluster render. Reusing the input extrinsics sidesteps that.
"""
from __future__ import annotations

import os
from typing import Iterable

import torch
import torchvision

from pipeline.render import _render_view, _to_batched_gaussians, _to_srgb
from pipeline.types import GaussiansResult


def _render_all_views(
    gaussians: GaussiansResult,
    decoder,
    out_dir: str,
    view_indices: Iterable[int],
    device: torch.device,
) -> None:
    """Render each requested view and save as PNG."""
    os.makedirs(out_dir, exist_ok=True)

    means = gaussians.means.to(device)
    covariances = gaussians.covariances.to(device)
    harmonics = gaussians.harmonics.to(device)
    opacities = gaussians.opacities.to(device)
    scales = gaussians.scales.to(device)
    rotations = gaussians.rotations.to(device)
    batched = _to_batched_gaussians(means, covariances, harmonics, opacities, scales, rotations)

    for view_idx in view_indices:
        ext = gaussians.extrinsics[view_idx].to(device)
        intr = gaussians.intrinsics[view_idx].to(device)
        frame = _render_view(decoder, batched, ext, intr, gaussians.image_size)
        out_path = os.path.join(out_dir, f"{view_idx:03d}.png")
        torchvision.utils.save_image(_to_srgb(frame), out_path)


def render_edits(
    original: GaussiansResult,
    edited: dict[str, GaussiansResult],
    decoder,
    results_dir: str,
    view_indices: list[int] | None = None,
    device: torch.device | None = None,
) -> None:
    """Render `original` + each edited variant under `results_dir`.

    Args:
        original: pre-edit GaussiansResult.
        edited: {edit_name: edited_gaussians}, typically from `apply_edits_v2`.
        decoder: AnySplat decoder.
        results_dir: root output dir; subdirs `original/`, `<edit_name>/`.
        view_indices: which input views to render (default: all).
        device: cuda if available else cpu (auto if None).
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    K = original.extrinsics.shape[0]
    if view_indices is None:
        view_indices = list(range(K))
    else:
        for v in view_indices:
            if not (0 <= v < K):
                raise IndexError(f"view {v} out of range [0, {K})")

    print(f"[render_edits] {len(view_indices)} views, {1 + len(edited)} variants")

    print(f"[render_edits] original/")
    _render_all_views(original, decoder, os.path.join(results_dir, "original"),
                      view_indices, device)

    for edit_name, edited_g in edited.items():
        print(f"[render_edits] {edit_name}/")
        _render_all_views(edited_g, decoder, os.path.join(results_dir, edit_name),
                          view_indices, device)

    print(f"[render_edits] done → {results_dir}/")

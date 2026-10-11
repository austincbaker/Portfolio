# pipeline/complete_objects.py
"""Stage 4: Per-object 3D completion — infer unseen back-side geometry.

Tier A (geometric mirroring): reflect each object's Gaussians across its
centroid plane to approximate back-side geometry. Fast and camera-agnostic.
This is a baseline; swap in Amodal3R for the research-quality implementation.
"""
import torch

from pipeline.cache import load_or_run
from pipeline.types import GaussiansResult, LiftResult, CompletionResult


def _mirror_object(
    means: torch.Tensor,        # [M, 3] — Gaussians belonging to this object
    harmonics: torch.Tensor,    # [M, 3, d_sh]
    opacities: torch.Tensor,    # [M]
    scales: torch.Tensor,       # [M, 3]
    rotations: torch.Tensor,    # [M, 4]
    covariances: torch.Tensor,  # [M, 3, 3]
    view_direction: torch.Tensor,  # [3] — mean camera direction (world space)
) -> tuple[torch.Tensor, ...]:
    """Reflect Gaussians across the centroid plane perpendicular to the view direction.

    Returns mirrored (means, harmonics, opacities, scales, rotations, covariances).
    """
    centroid = means.mean(dim=0)          # [3]
    normal = view_direction / (view_direction.norm() + 1e-8)  # [3]

    # Reflect each mean across the centroid plane
    d = ((means - centroid) * normal).sum(dim=-1, keepdim=True)  # [M, 1] signed distance
    mirrored_means = means - 2.0 * d * normal  # [M, 3]

    # Keep all other attributes identical — the back side is a mirror of the front
    return mirrored_means, harmonics, opacities, scales, rotations, covariances


def _run_completion(
    gaussians: GaussiansResult,
    lifted: LiftResult,
) -> dict:
    """Build mirrored back-side Gaussians for each detected object."""
    device = gaussians.means.device

    # Estimate mean camera viewing direction from extrinsics (c2w matrices)
    # Camera looks along +Z in camera space; transform to world space
    cam_dirs = gaussians.extrinsics[:, :3, 2]  # [K, 3] — +Z column of each c2w
    view_dir = cam_dirs.mean(dim=0)            # [3]

    result = {
        "extra_means": {},
        "extra_harmonics": {},
        "extra_opacities": {},
        "extra_scales": {},
        "extra_rotations": {},
        "extra_covariances": {},
    }

    num_objects = len(lifted.object_names)
    for obj_idx in range(num_objects):
        mask = (lifted.labels == obj_idx)
        count = mask.sum().item()
        if count == 0:
            continue

        obj_name = lifted.object_names[obj_idx]
        print(f"[complete] Mirroring object {obj_idx} ({obj_name}): {count} Gaussians")

        m_means, m_harm, m_opac, m_scales, m_rots, m_covs = _mirror_object(
            gaussians.means[mask],
            gaussians.harmonics[mask],
            gaussians.opacities[mask],
            gaussians.scales[mask],
            gaussians.rotations[mask],
            gaussians.covariances[mask],
            view_dir,
        )

        # Store as CPU tensors for caching
        result["extra_means"][obj_idx] = m_means.cpu()
        result["extra_harmonics"][obj_idx] = m_harm.cpu()
        result["extra_opacities"][obj_idx] = m_opac.cpu()
        result["extra_scales"][obj_idx] = m_scales.cpu()
        result["extra_rotations"][obj_idx] = m_rots.cpu()
        result["extra_covariances"][obj_idx] = m_covs.cpu()

    return result


def complete_objects(
    gaussians: GaussiansResult,
    lifted: LiftResult,
    cache_dir: str = "outputs/cache",
) -> CompletionResult:
    """Stage 4 entry point."""
    raw = load_or_run(
        "completion",
        _run_completion,
        gaussians,
        lifted,
        fmt="pt",
        cache_dir=cache_dir,
    )
    return CompletionResult(
        extra_means=raw["extra_means"],
        extra_harmonics=raw["extra_harmonics"],
        extra_opacities=raw["extra_opacities"],
        extra_scales=raw["extra_scales"],
        extra_rotations=raw["extra_rotations"],
        extra_covariances=raw["extra_covariances"],
    )

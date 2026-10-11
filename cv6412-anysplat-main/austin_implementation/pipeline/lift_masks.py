# pipeline/lift_masks.py
"""Stage 3: Lift 2D masks to per-Gaussian 3D labels via projection + majority vote."""
import torch

from pipeline.cache import load_or_run
from pipeline.types import GaussiansResult, SegmentationResult, LiftResult


def project_gaussians_to_pixels(
    means: torch.Tensor,       # [N, 3]
    extrinsic_c2w: torch.Tensor,  # [4, 4] camera-to-world
    intrinsic_norm: torch.Tensor, # [3, 3] normalized intrinsics
    H: int,
    W: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Project 3D Gaussian means to 2D pixel coordinates for one camera.

    Returns:
        pixels: [N, 2] pixel coordinates (u, v)
        valid: [N] bool mask — True if projection is in front of camera and within image bounds
    """
    N = means.shape[0]
    device = means.device

    # Invert c2w to get w2c
    w2c = extrinsic_c2w.inverse()  # [4, 4]

    # Denormalize intrinsics
    K = intrinsic_norm.clone()
    K[0] = K[0] * W
    K[1] = K[1] * H

    # Transform to camera space: [N, 4] homogeneous
    ones = torch.ones(N, 1, device=device, dtype=means.dtype)
    means_h = torch.cat([means, ones], dim=1)  # [N, 4]
    p_cam = (w2c @ means_h.T).T[:, :3]  # [N, 3]

    # Check in front of camera (positive z in camera space)
    in_front = p_cam[:, 2] > 0  # [N]

    # Project to pixels: p_2d = K @ p_cam^T
    p_2d = (K @ p_cam.T).T  # [N, 3]
    u = p_2d[:, 0] / (p_2d[:, 2] + 1e-8)  # [N]
    v = p_2d[:, 1] / (p_2d[:, 2] + 1e-8)  # [N]

    # Check within image bounds
    in_bounds = (u >= 0) & (u < W) & (v >= 0) & (v < H)

    valid = in_front & in_bounds
    pixels = torch.stack([u, v], dim=1)  # [N, 2]

    return pixels, valid


def majority_vote_labels(
    per_view_labels: torch.Tensor,  # [K, N] int (-1 = background/no object)
    per_view_valid: torch.Tensor,   # [K, N] bool
    num_objects: int,
    min_vote_fraction: float = 0.3,
) -> torch.Tensor:
    """Majority vote across K views to assign one label per Gaussian.

    A Gaussian is only assigned an object label if:
    1. It has at least one valid projection
    2. The winning object label has more votes than background (-1)
    3. The winning label appears in at least min_vote_fraction of valid views

    Returns: [N] int labels (-1 = unassigned/background)
    """
    K, N = per_view_labels.shape
    device = per_view_labels.device

    # Count votes per object for each Gaussian: [N, num_objects]
    # Also count background votes (label == -1 among valid projections)
    votes = torch.zeros(N, num_objects, device=device, dtype=torch.long)
    bg_votes = torch.zeros(N, device=device, dtype=torch.long)

    for k in range(K):
        valid_k = per_view_valid[k]  # [N]
        labels_k = per_view_labels[k]  # [N]
        is_bg = valid_k & (labels_k == -1)
        bg_votes += is_bg.long()
        for obj_idx in range(num_objects):
            match = valid_k & (labels_k == obj_idx)
            votes[:, obj_idx] += match.long()

    # Total valid views per Gaussian
    total_valid = per_view_valid.sum(dim=0)  # [N]

    # Majority vote: take argmax of object votes
    max_votes, winner = votes.max(dim=1)  # [N], [N]

    # A Gaussian gets an object label only if:
    # - it has valid projections
    # - the object votes exceed background votes
    # - the object votes are at least min_vote_fraction of valid views
    min_votes = (total_valid.float() * min_vote_fraction).long().clamp(min=1)
    assigned = (total_valid > 0) & (max_votes > bg_votes) & (max_votes >= min_votes)

    labels = torch.where(assigned, winner, torch.tensor(-1, device=device))

    return labels


def lift_masks_core(
    means: torch.Tensor,          # [N, 3]
    extrinsics: torch.Tensor,     # [K, 4, 4] c2w
    intrinsics: torch.Tensor,     # [K, 3, 3] normalized
    masks: dict[str, torch.Tensor],  # object_name -> [K, H, W] bool
    object_names: list[str],
    H: int,
    W: int,
) -> torch.Tensor:
    """Core lifting logic. Returns [N] int labels."""
    K = extrinsics.shape[0]
    N = means.shape[0]
    num_objects = len(object_names)
    device = means.device

    per_view_labels = torch.zeros(K, N, device=device, dtype=torch.long)
    per_view_valid = torch.zeros(K, N, device=device, dtype=torch.bool)

    for k in range(K):
        pixels, valid = project_gaussians_to_pixels(
            means, extrinsics[k], intrinsics[k], H, W
        )
        per_view_valid[k] = valid

        # For valid projections, look up which mask covers the pixel
        u = pixels[:, 0].long().clamp(0, W - 1)
        v = pixels[:, 1].long().clamp(0, H - 1)

        # Default to -1 (no object), then check each object's mask
        view_labels = torch.full((N,), -1, device=device, dtype=torch.long)
        for obj_idx, name in enumerate(object_names):
            mask_k = masks[name][k].to(device)  # [H, W]
            covered = mask_k[v, u] & valid  # [N]
            view_labels[covered] = obj_idx

        per_view_labels[k] = view_labels

    return majority_vote_labels(per_view_labels, per_view_valid, num_objects)


def lift_masks(
    gaussians: GaussiansResult,
    segments: SegmentationResult,
    cache_dir: str = "outputs/cache",
) -> LiftResult:
    """Stage 3 entry point."""
    def _run():
        H, W = gaussians.image_size
        labels = lift_masks_core(
            gaussians.means,
            gaussians.extrinsics,
            gaussians.intrinsics,
            segments.masks,
            segments.object_names,
            H, W,
        )
        return LiftResult(labels=labels, object_names=segments.object_names)

    return load_or_run("lift_masks", _run, cache_dir=cache_dir)

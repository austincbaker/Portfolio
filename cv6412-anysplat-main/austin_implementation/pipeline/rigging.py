"""Rig AnySplat Gaussians onto SuperDec superquadric primitives.

Implements the Option-C three-frame model from the rigging spec:
    world  ←─ similarity(c, s) ──  normalized  ←─ rigid(R_sq, t_sq) ──  sq-local

Conventions (audit surface; do not inline-clone elsewhere):
    ANYSPLAT_QUAT_ORDER = "xyzw"   # scalar last; matches gaussians.quaternion_to_matrix
    SUPERDEC_QUAT_ORDER = "wxyz"   # scalar first; matches superdec heads.quat2mat
    ROTATION_SEMANTICS  = "active" # p_world = R @ p_local + t
    COVARIANCE_FORMULA  = "R @ diag(s**2) @ R.T"   # matches build_covariance
    QUATERNION_ALGEBRA  = "hamilton"
    WORLD_HANDEDNESS    = "right"

Normalization (§4): matches SuperDec's `data/dataloader.py::normalize_points`
exactly — L∞ over coordinates, so the normalized point cloud fits in the
**cube** [−0.5, 0.5]^3 (NOT a sphere of radius 0.5 — see the paper vs. code
discrepancy documented in the spec review).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch

from pipeline.sq_math import (
    _as_rot_matrix,
    _as_rot_quat,
    mat_to_quat,
    quat_conjugate,
    quat_mul,
    quat_to_mat,
    sq_radial_distance,
    world_to_sq_local,
)
from pipeline.types import GaussiansResult, LiftResult


# -----------------------------
# Dataclasses (spec §2)
# -----------------------------
@dataclass
class SuperquadricPrimitive:
    """One SuperDec primitive in the NORMALIZED frame (pre-denormalize)."""
    scale_norm:  torch.Tensor   # [3]    semi-axes, linear, post-activation
    shape:       torch.Tensor   # [2]    (ε1, ε2), already in (0.1, 1.9)
    t_norm:      torch.Tensor   # [3]    translation in normalized frame
    R_norm:      torch.Tensor   # [3,3]  rotation local→normalized (same orientation as world)
    q_norm_xyzw: torch.Tensor   # [4]    same rotation as xyzw quat, stored for composition


@dataclass
class Normalization:
    """Immutable similarity (c, s): world ↔ normalized."""
    c: torch.Tensor   # [3]   centroid in world frame
    s: torch.Tensor   # scalar (0-d tensor), positive


@dataclass
class RigBinding:
    """Bind-time local state for all attached Gaussians."""
    attached_idx:  torch.Tensor   # [M]    long; indices into the full Gaussian array
    p_local:       torch.Tensor   # [M, 3] position in sq-local frame (unscaled)
    q_local_xyzw:  torch.Tensor   # [M, 4] Gaussian orientation in sq-local frame
    p_world_bind:  torch.Tensor   # [M, 3] world-frame bind-time positions (cached for fast apply)


@dataclass
class RiggedScene:
    """Full rigged state. Bind-time only; never mutated by apply_* functions."""
    primitive:     SuperquadricPrimitive
    normalization: Normalization
    binding:       RigBinding
    # Reference to bind-time Gaussians (by alias, not clone) for diagnostics only.
    gaussians_bind: Optional[GaussiansResult] = None


# -----------------------------
# Boundary conversions (spec §3)
# -----------------------------
def superdec_quat_to_anysplat_order(q_wxyz: torch.Tensor) -> torch.Tensor:
    """SuperDec wxyz → AnySplat/VGGT xyzw. The single place wxyz→xyzw happens."""
    w, x, y, z = q_wxyz.unbind(-1)
    return torch.stack([x, y, z, w], dim=-1)


def superquadric_from_outdict(
    outdict: dict,
    index: int = 0,
    batch: int = 0,
    verify_tol: float = 1e-5,
) -> SuperquadricPrimitive:
    """Parse one SQ out of SuperDec's `model(points)` output dict.

    Expects the POST-activation, UN-denormalized dict (i.e. `denormalize_outdict`
    NOT applied). We keep primitives in the normalized frame and store `(c, s)`
    separately — see `Normalization`.

    Args:
        outdict: `{"scale": [B,P,3], "shape": [B,P,2], "rotate": [B,P,3,3],
                   "trans": [B,P,3], "exist": [B,P,1]}`.
        index:   which primitive (0..P-1).
        batch:   batch slot (default 0 — SuperDec called with B=1 here).
    """
    scale_norm = outdict["scale"][batch, index].detach().clone()   # [3]
    shape = outdict["shape"][batch, index].detach().clone()        # [2]
    R_norm = outdict["rotate"][batch, index].detach().clone()       # [3,3]
    t_norm = outdict["trans"][batch, index].detach().clone()        # [3]

    # Derive xyzw quaternion from the matrix — SuperDec's raw internal quat is
    # wxyz but not exposed as a separate output; the matrix is authoritative.
    q_norm_xyzw = mat_to_quat(R_norm)

    # Consistency check: matrix and quaternion must agree.
    R_check = quat_to_mat(q_norm_xyzw)
    err = (R_check - R_norm).norm().item()
    if err > verify_tol:
        raise RuntimeError(
            f"SuperDec primitive {index}: matrix↔quaternion disagreement {err:.3e} "
            f"(tol {verify_tol}). Spec §3 verification failed."
        )

    return SuperquadricPrimitive(
        scale_norm=scale_norm,
        shape=shape,
        t_norm=t_norm,
        R_norm=R_norm,
        q_norm_xyzw=q_norm_xyzw,
    )


# -----------------------------
# Normalization (spec §4)
# -----------------------------
def compute_normalization(points_world: torch.Tensor) -> Normalization:
    """Matches `superdec/data/dataloader.py::normalize_points` EXACTLY.

        translation = mean(points)                     # [3]
        centered    = points - translation             # [P, 3]
        scale       = 2 * max(|centered|)              # scalar — L∞ over ALL coords
        normalized  = centered / scale                 # fits in [-0.5, 0.5]^3

    Returns:
        Normalization with c = translation, s = scale.
    """
    if points_world.shape[0] == 0:
        raise ValueError("points_world is empty — segmentation returned no Gaussians")

    c = points_world.mean(dim=0)
    centered = points_world - c
    # np.max(np.abs(points)) over ALL entries is max of a [P,3] tensor — scalar.
    r_max = centered.abs().max()
    if r_max.item() < 1e-6:
        raise ValueError(f"Degenerate point cloud: max(|centered|) = {r_max.item():.3e}")
    s = 2.0 * r_max
    return Normalization(c=c, s=s)


def world_to_normalized(points_world: torch.Tensor, norm: Normalization) -> torch.Tensor:
    return (points_world - norm.c) / norm.s


def normalized_to_world(points_norm: torch.Tensor, norm: Normalization) -> torch.Tensor:
    return points_norm * norm.s + norm.c


# -----------------------------
# Bind (spec §5)
# -----------------------------
def bind(
    gaussians: GaussiansResult,
    lift: LiftResult,
    obj_idx: int,
    primitive: SuperquadricPrimitive,
    normalization: Normalization,
    standardize_w: bool = True,
) -> RiggedScene:
    """Bind all Gaussians with `labels == obj_idx` to a single SQ primitive.

    Caller responsibility: SuperDec was run on the SAME world-frame point set
    that was used to compute `normalization`, using `z_up=False` and skipping
    `denormalize_outdict` (so the primitive is in normalized frame).

    Steps match spec §5.
    """
    labels = lift.labels
    attached_idx = (labels == obj_idx).nonzero(as_tuple=False).squeeze(-1)
    if attached_idx.numel() == 0:
        raise ValueError(f"obj_idx {obj_idx} has no attached Gaussians in lift.labels")

    p_world = gaussians.means[attached_idx]
    q_world_xyzw = gaussians.rotations[attached_idx]

    # 3. Normalize positions: p_norm = (p - c) / s
    p_norm = world_to_normalized(p_world, normalization)

    # 5. Decompose into sq-local frame (rotate+translate only; no scale divide)
    p_local = world_to_sq_local(p_norm, primitive.t_norm, primitive.R_norm)

    # Orientation composition. Since normalization preserves rotations,
    # q_sq_world == q_norm, so we conjugate by q_norm_xyzw.
    q_sq_inv = quat_conjugate(primitive.q_norm_xyzw)
    # Broadcasts: q_sq_inv is [4], q_world_xyzw is [M, 4]
    q_local_xyzw = quat_mul(q_sq_inv.expand_as(q_world_xyzw), q_world_xyzw)

    # Re-normalize to unit for drift protection.
    q_local_xyzw = q_local_xyzw / q_local_xyzw.norm(dim=-1, keepdim=True).clamp_min(1e-8)

    if standardize_w:
        # Double-cover: flip rows with negative w so the representation is unique.
        flip = q_local_xyzw[..., 3:4] < 0
        q_local_xyzw = torch.where(flip, -q_local_xyzw, q_local_xyzw)

    binding = RigBinding(
        attached_idx=attached_idx,
        p_local=p_local,
        q_local_xyzw=q_local_xyzw,
        p_world_bind=p_world.clone(),  # cached for the collapsed translate path
    )

    return RiggedScene(
        primitive=primitive,
        normalization=normalization,
        binding=binding,
        gaussians_bind=gaussians,  # reference alias, not a clone
    )


# -----------------------------
# Radial distance (spec §7)
# -----------------------------
def radial_distance_world(
    points_world: torch.Tensor,
    scene: RiggedScene,
) -> torch.Tensor:
    """Distance magnitude from world-frame points to the scene's SQ surface.

    Chains: world → normalized → sq_local; then §7 Eq.2. Result is in
    normalized-frame units; multiply by `scene.normalization.s` for world units.
    """
    p_norm = world_to_normalized(points_world, scene.normalization)
    return sq_radial_distance(
        p_norm,
        scene.primitive.t_norm,
        scene.primitive.R_norm,
        scene.primitive.scale_norm,
        scene.primitive.shape,
    )

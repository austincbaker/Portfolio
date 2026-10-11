"""SQ-bound edit operators.

All operators take a `RiggedScene` (read-only) and a `GaussiansResult`, and
return a new `GaussiansResult`. The scene identifies which Gaussians are
attached and where the SQ centroid is in world frame; the actual transforms
are expressed in world frame.

Pivot for rotate/scale is the SQ centroid in world frame:

    pivot_world = s · t_norm + c

where `s, c` are the normalization scalar/centroid and `t_norm` is the
primitive's translation in normalized frame.

Scope:
- translate: arbitrary world-frame delta. Already exact (no covariance change).
- rotate:    about pivot_world, arbitrary axis/angle. SH bands ℓ∈{0,1} rotated
             exactly; ℓ≥2 zeroed (lossy; documented in PLAN.md).
- scale:     isotropic only, about pivot_world. Anisotropic is out of scope.
- recolor:   replace (zero non-DC bands, set DC) or tint (preserve, shift DC).

Operators do not mutate `scene` and pass non-edited tensors through by
reference (matching the contract established by `apply_translate`).
"""
from __future__ import annotations

import math

import torch

from pipeline.rigging import RiggedScene
from pipeline.sq_math import mat_to_quat, quat_mul, sq_local_to_world
from pipeline.types import GaussiansResult


# DC SH coefficient for unit constant function over the sphere:
#   Y_0^0 = 1 / (2 sqrt(π)).  Color = 0.5 + SH0 · DC.
SH0: float = 1.0 / (2.0 * math.sqrt(math.pi))


def _pivot_world(scene: RiggedScene, device, dtype) -> torch.Tensor:
    """SQ centroid in world frame: s · t_norm + c."""
    s = scene.normalization.s.to(device=device, dtype=dtype)
    c = scene.normalization.c.to(device=device, dtype=dtype)
    t_norm = scene.primitive.t_norm.to(device=device, dtype=dtype)
    return s * t_norm + c


def _axis_angle_to_matrix(axis: torch.Tensor, angle_rad: float | torch.Tensor) -> torch.Tensor:
    """Rodrigues' formula. axis: [3] (need not be unit); angle: scalar (rad)."""
    a = axis / axis.norm().clamp_min(1e-12)
    angle = torch.as_tensor(angle_rad, device=axis.device, dtype=axis.dtype)
    cos_a = torch.cos(angle)
    sin_a = torch.sin(angle)
    x, y, z = a.unbind(dim=-1)
    K = torch.stack([
        torch.zeros_like(x), -z, y,
        z, torch.zeros_like(x), -x,
        -y, x, torch.zeros_like(x),
    ]).reshape(3, 3)
    eye = torch.eye(3, device=axis.device, dtype=axis.dtype)
    return eye + sin_a * K + (1 - cos_a) * (K @ K)


def _rotate_sh_band1(harmonics_attached: torch.Tensor, R: torch.Tensor) -> torch.Tensor:
    """Rotate SH band-1 coefficients under world rotation R.

    Real SH band-1 basis (3DGS / gsplat convention):
        m=-1 → y, m=0 → z, m=+1 → x

    The 3 coefficients per channel transform as a vector with components
    (y, z, x) under world rotation R. We re-order to (x,y,z), apply R, and
    re-order back.

    Args:
        harmonics_attached: [M, 3, d_sh]
        R: [3, 3] world-frame rotation
    Returns:
        New [M, 3, d_sh] with band-1 rotated; other bands untouched.
    """
    h = harmonics_attached.clone()
    if h.shape[-1] < 4:
        return h
    b1 = h[..., 1:4]                       # [M, 3, 3]  — last dim is m=(-1,0,+1)
    y_c = b1[..., 0]
    z_c = b1[..., 1]
    x_c = b1[..., 2]
    v = torch.stack([x_c, y_c, z_c], dim=-1)              # [M, 3, 3] xyz-ordered
    v_rot = torch.einsum("ij,...j->...i", R.to(v.dtype), v)
    x_n, y_n, z_n = v_rot.unbind(dim=-1)
    h[..., 1:4] = torch.stack([y_n, z_n, x_n], dim=-1)
    return h


def apply_translate(
    scene: RiggedScene,
    gaussians: GaussiansResult,
    delta_t_world: torch.Tensor,
    check_full_chain: bool = False,
    chain_tol: float = 1e-4,
) -> GaussiansResult:
    """Translate the attached object by `delta_t_world` (world units).

    Spec §6a shows that for translate-only edits, the full chain

        t_norm_new   = primitive.t_norm + delta_t_world / s
        p_norm_new   = R_norm @ p_local + t_norm_new
        p_world_new  = s * p_norm_new + c

    collapses algebraically to

        p_world_new = p_world_bind + delta_t_world

    We use the collapsed form on the hot path. Pass `check_full_chain=True`
    to also compute the full-chain path and assert agreement (used by T7).

    All invariant fields (covariances, rotations, scales, opacities, harmonics,
    extrinsics, intrinsics) pass through by reference — no clone.
    """
    device = gaussians.means.device
    dtype = gaussians.means.dtype
    delta = delta_t_world.to(device=device, dtype=dtype)
    if delta.shape != (3,):
        raise ValueError(f"delta_t_world must be [3], got {tuple(delta.shape)}")

    attached_idx = scene.binding.attached_idx.to(device)
    p_world_bind = scene.binding.p_world_bind.to(device=device, dtype=dtype)
    p_world_new_attached = p_world_bind + delta

    if check_full_chain:
        s = scene.normalization.s.to(device=device, dtype=dtype)
        c = scene.normalization.c.to(device=device, dtype=dtype)
        t_norm = scene.primitive.t_norm.to(device=device, dtype=dtype)
        R_norm = scene.primitive.R_norm.to(device=device, dtype=dtype)
        p_local = scene.binding.p_local.to(device=device, dtype=dtype)

        t_norm_new = t_norm + delta / s
        p_norm_new = sq_local_to_world(p_local, t_norm_new, R_norm)
        p_full = p_norm_new * s + c
        err = (p_full - p_world_new_attached).abs().max().item()
        if err > chain_tol:
            raise RuntimeError(
                f"apply_translate: full-chain vs collapsed mismatch {err:.3e} "
                f"(tol {chain_tol}). Spec §6a invariant broken."
            )

    means_out = gaussians.means.clone()
    means_out[attached_idx] = p_world_new_attached

    return GaussiansResult(
        means=means_out,
        covariances=gaussians.covariances,   # invariant under translation
        harmonics=gaussians.harmonics,       # invariant
        opacities=gaussians.opacities,       # invariant
        scales=gaussians.scales,             # invariant
        rotations=gaussians.rotations,       # invariant under translation
        extrinsics=gaussians.extrinsics,
        intrinsics=gaussians.intrinsics,
        image_size=gaussians.image_size,
    )


def apply_rotate(
    scene: RiggedScene,
    gaussians: GaussiansResult,
    axis: torch.Tensor,
    angle_rad: float | torch.Tensor,
) -> GaussiansResult:
    """Rotate the attached object about the SQ centroid in world frame.

    Updates:
      - means: p_world' = pivot + R · (p_world - pivot)
      - rotations: q_world' = q_delta ⊗ q_world  (left-compose; world frame)
      - covariances: Σ' = R · Σ · Rᵀ
      - harmonics: bands ℓ∈{0,1} rotated; ℓ≥2 zeroed (lossy; see PLAN.md)
      - scales: unchanged (rotation does not change axis-aligned scale magnitudes)

    Args:
        axis: [3] world-frame rotation axis (need not be unit).
        angle_rad: rotation angle in radians.
    """
    device = gaussians.means.device
    dtype = gaussians.means.dtype
    axis = axis.to(device=device, dtype=dtype)
    if axis.shape != (3,):
        raise ValueError(f"axis must be [3], got {tuple(axis.shape)}")

    R = _axis_angle_to_matrix(axis, angle_rad)               # [3, 3]
    q_delta = mat_to_quat(R)                                 # [4] xyzw
    pivot = _pivot_world(scene, device, dtype)               # [3]
    attached_idx = scene.binding.attached_idx.to(device)

    # Means
    means_out = gaussians.means.clone()
    rel = means_out[attached_idx] - pivot
    means_out[attached_idx] = pivot + torch.einsum("ij,nj->ni", R, rel)

    # Per-Gaussian rotations: left-compose with q_delta in world frame.
    rotations_out = gaussians.rotations.clone()
    q_attached = rotations_out[attached_idx]
    q_new = quat_mul(q_delta.unsqueeze(0).expand_as(q_attached), q_attached)
    q_new = q_new / q_new.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    rotations_out[attached_idx] = q_new

    # Covariances: Σ' = R Σ Rᵀ
    covariances_out = gaussians.covariances.clone()
    sigma = covariances_out[attached_idx]
    R_t = R.transpose(-1, -2)
    covariances_out[attached_idx] = torch.einsum("ij,njk,kl->nil", R, sigma, R_t)

    # SH: rotate band-1, zero ℓ≥2.
    harmonics_out = gaussians.harmonics.clone()
    h_attached = harmonics_out[attached_idx]
    h_attached = _rotate_sh_band1(h_attached, R)
    if h_attached.shape[-1] > 4:
        h_attached[..., 4:] = 0.0
    harmonics_out[attached_idx] = h_attached

    return GaussiansResult(
        means=means_out,
        covariances=covariances_out,
        harmonics=harmonics_out,
        opacities=gaussians.opacities,       # invariant
        scales=gaussians.scales,             # invariant under rotation
        rotations=rotations_out,
        extrinsics=gaussians.extrinsics,
        intrinsics=gaussians.intrinsics,
        image_size=gaussians.image_size,
    )


def apply_scale(
    scene: RiggedScene,
    gaussians: GaussiansResult,
    factor: float | torch.Tensor,
) -> GaussiansResult:
    """Isotropic scale of the attached object about the SQ centroid (world frame).

    Updates:
      - means: p' = pivot + α · (p - pivot)
      - scales: s' = α · s
      - covariances: Σ' = α² · Σ
      - rotations, harmonics: unchanged (isotropic scale doesn't change angular
        relationships).
    """
    device = gaussians.means.device
    dtype = gaussians.means.dtype
    alpha = torch.as_tensor(factor, device=device, dtype=dtype)
    if alpha.numel() != 1:
        raise ValueError(f"factor must be scalar, got shape {tuple(alpha.shape)}")
    if alpha.item() <= 0:
        raise ValueError(f"factor must be positive, got {alpha.item()}")

    pivot = _pivot_world(scene, device, dtype)
    attached_idx = scene.binding.attached_idx.to(device)

    means_out = gaussians.means.clone()
    rel = means_out[attached_idx] - pivot
    means_out[attached_idx] = pivot + alpha * rel

    scales_out = gaussians.scales.clone()
    scales_out[attached_idx] = alpha * scales_out[attached_idx]

    covariances_out = gaussians.covariances.clone()
    covariances_out[attached_idx] = (alpha * alpha) * covariances_out[attached_idx]

    return GaussiansResult(
        means=means_out,
        covariances=covariances_out,
        harmonics=gaussians.harmonics,       # invariant under isotropic scale
        opacities=gaussians.opacities,       # invariant
        scales=scales_out,
        rotations=gaussians.rotations,       # invariant
        extrinsics=gaussians.extrinsics,
        intrinsics=gaussians.intrinsics,
        image_size=gaussians.image_size,
    )


def apply_recolor(
    scene: RiggedScene,
    gaussians: GaussiansResult,
    mode: str,
    rgb: torch.Tensor,
) -> GaussiansResult:
    """Recolor the attached object via SH DC manipulation.

    SH DC encoding: color = 0.5 + SH0 · DC, so DC = (color - 0.5) / SH0.

    Modes:
      - "replace": DC := encode_dc(rgb); bands ℓ≥1 zeroed. Result is a flat
        constant color (no view-dependent variation).
      - "tint":    DC += encode_dc(rgb); bands ℓ≥1 preserved. Shifts the mean
        color while keeping high-frequency SH detail.

    Args:
        rgb: [3] RGB color in [0, 1] (replace target / tint shift).
    """
    if mode not in ("replace", "tint"):
        raise ValueError(f"mode must be 'replace' or 'tint', got {mode!r}")

    device = gaussians.means.device
    dtype = gaussians.harmonics.dtype
    rgb = rgb.to(device=device, dtype=dtype)
    if rgb.shape != (3,):
        raise ValueError(f"rgb must be [3], got {tuple(rgb.shape)}")

    attached_idx = scene.binding.attached_idx.to(device)
    dc = (rgb - 0.5) / SH0                                   # [3]

    harmonics_out = gaussians.harmonics.clone()
    h = harmonics_out[attached_idx]                          # [M, 3, d_sh]
    if mode == "replace":
        h[..., 0] = dc.unsqueeze(0).expand_as(h[..., 0])
        if h.shape[-1] > 1:
            h[..., 1:] = 0.0
    else:  # tint
        h[..., 0] = h[..., 0] + dc.unsqueeze(0).expand_as(h[..., 0])
    harmonics_out[attached_idx] = h

    return GaussiansResult(
        means=gaussians.means,               # invariant
        covariances=gaussians.covariances,   # invariant
        harmonics=harmonics_out,
        opacities=gaussians.opacities,       # invariant
        scales=gaussians.scales,             # invariant
        rotations=gaussians.rotations,       # invariant
        extrinsics=gaussians.extrinsics,
        intrinsics=gaussians.intrinsics,
        image_size=gaussians.image_size,
    )

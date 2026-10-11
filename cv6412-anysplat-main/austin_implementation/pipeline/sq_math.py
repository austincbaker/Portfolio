"""Superquadric ↔ world frame math for Gaussian rigging.

Rotation parameterization notes
-------------------------------
AnySplat stores Gaussian rotations as **xyzw** quaternions (scalar last,
scipy/gsplat convention — see
`anysplat/src/model/encoder/common/gaussians.py::quaternion_to_matrix`,
which unbinds the 4-vector as `i, j, k, r`). All quaternion I/O in this
module is xyzw.

SuperDec (`superdec/models/heads.py::SuperDecHead`) uses wxyz internally
but exposes rotation as a 3x3 matrix via `outdict['rotate']`. We accept
the SQ rotation as either a 3x3 matrix ([..., 3, 3]) or an xyzw
quaternion ([..., 4]); internal conversion goes via the matrix.

World ↔ SQ-local transforms
---------------------------
We use the "SQ-local = rotated-and-centered, unscaled" convention (same as
SuperDec's `superdec/utils/transforms.py::transform_to_primitive_frame`):

    p_local = R^T (p - t)                # NO scale divide
    p_world = R @ p_local + t

The scale divide is kept inline in `sq_inside_outside` (and consequently in
`sq_radial_distance`), which is the only place it's needed — dividing by
anisotropic scale would distort orientations and break the rigid-rig model.

For Gaussian orientation (an xyzw quaternion q_world):

    q_local = conj(q_sq) ⊗ q_world
    q_world = q_sq       ⊗ q_local

where ⊗ is Hamilton quaternion product in xyzw ordering.
"""

from __future__ import annotations

import torch


# -------------------------
# Quaternion utilities (xyzw — scalar last, matching AnySplat/scipy)
# -------------------------
def quat_conjugate(q: torch.Tensor) -> torch.Tensor:
    """Conjugate of an xyzw quaternion. Shape [..., 4] → [..., 4]."""
    x, y, z, w = q.unbind(dim=-1)
    return torch.stack([-x, -y, -z, w], dim=-1)


def quat_mul(q1: torch.Tensor, q2: torch.Tensor) -> torch.Tensor:
    """Hamilton product of two xyzw quaternions. Broadcasts."""
    x1, y1, z1, w1 = q1.unbind(dim=-1)
    x2, y2, z2, w2 = q2.unbind(dim=-1)
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
    z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
    return torch.stack([x, y, z, w], dim=-1)


def quat_to_mat(q: torch.Tensor) -> torch.Tensor:
    """xyzw quaternion [..., 4] → rotation matrix [..., 3, 3].

    Matches AnySplat `quaternion_to_matrix`.
    """
    q = q / q.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    x, y, z, w = q.unbind(dim=-1)
    w2, x2, y2, z2 = w * w, x * x, y * y, z * z
    wx, wy, wz = w * x, w * y, w * z
    xy, xz, yz = x * y, x * z, y * z
    m = torch.stack([
        w2 + x2 - y2 - z2, 2 * (xy - wz),     2 * (xz + wy),
        2 * (xy + wz),     w2 - x2 + y2 - z2, 2 * (yz - wx),
        2 * (xz - wy),     2 * (yz + wx),     w2 - x2 - y2 + z2,
    ], dim=-1)
    return m.reshape(*q.shape[:-1], 3, 3)


def mat_to_quat(R: torch.Tensor) -> torch.Tensor:
    """Rotation matrix [..., 3, 3] → xyzw quaternion [..., 4]."""
    batch_shape = R.shape[:-2]
    Rf = R.reshape(-1, 3, 3)
    m00, m01, m02 = Rf[:, 0, 0], Rf[:, 0, 1], Rf[:, 0, 2]
    m10, m11, m12 = Rf[:, 1, 0], Rf[:, 1, 1], Rf[:, 1, 2]
    m20, m21, m22 = Rf[:, 2, 0], Rf[:, 2, 1], Rf[:, 2, 2]
    trace = m00 + m11 + m22

    q = torch.zeros(Rf.shape[0], 4, device=R.device, dtype=R.dtype)  # (x, y, z, w)

    # Guard against numerical drift: the sqrt argument is mathematically ≥ 0 in
    # each branch, but floating-point noise on near-degenerate rotations can push
    # it slightly negative — and dividing by s=0 produces inf/nan.
    eps = torch.finfo(R.dtype).eps

    c1 = trace > 0
    if c1.any():
        s = torch.sqrt((trace[c1] + 1.0).clamp_min(eps)) * 2
        s = s.clamp_min(eps)
        q[c1, 3] = 0.25 * s
        q[c1, 0] = (m21[c1] - m12[c1]) / s
        q[c1, 1] = (m02[c1] - m20[c1]) / s
        q[c1, 2] = (m10[c1] - m01[c1]) / s

    c2 = (~c1) & (m00 > m11) & (m00 > m22)
    if c2.any():
        s = torch.sqrt((1.0 + m00[c2] - m11[c2] - m22[c2]).clamp_min(eps)) * 2
        s = s.clamp_min(eps)
        q[c2, 3] = (m21[c2] - m12[c2]) / s
        q[c2, 0] = 0.25 * s
        q[c2, 1] = (m01[c2] + m10[c2]) / s
        q[c2, 2] = (m02[c2] + m20[c2]) / s

    c3 = (~c1) & (~c2) & (m11 > m22)
    if c3.any():
        s = torch.sqrt((1.0 + m11[c3] - m00[c3] - m22[c3]).clamp_min(eps)) * 2
        s = s.clamp_min(eps)
        q[c3, 3] = (m02[c3] - m20[c3]) / s
        q[c3, 0] = (m01[c3] + m10[c3]) / s
        q[c3, 1] = 0.25 * s
        q[c3, 2] = (m12[c3] + m21[c3]) / s

    c4 = (~c1) & (~c2) & (~c3)
    if c4.any():
        s = torch.sqrt((1.0 + m22[c4] - m00[c4] - m11[c4]).clamp_min(eps)) * 2
        s = s.clamp_min(eps)
        q[c4, 3] = (m10[c4] - m01[c4]) / s
        q[c4, 0] = (m02[c4] + m20[c4]) / s
        q[c4, 1] = (m12[c4] + m21[c4]) / s
        q[c4, 2] = 0.25 * s

    q = q / q.norm(dim=-1, keepdim=True).clamp_min(1e-12)
    return q.reshape(*batch_shape, 4)


def _as_rot_matrix(sq_rot: torch.Tensor) -> torch.Tensor:
    """Accept either quat [...,4] or matrix [...,3,3]; return matrix."""
    if sq_rot.shape[-1] == 4 and sq_rot.shape[-2:] != (3, 3):
        return quat_to_mat(sq_rot)
    if sq_rot.shape[-2:] == (3, 3):
        return sq_rot
    raise ValueError(f"SQ rotation must be [...,4] quat or [...,3,3] matrix, got {tuple(sq_rot.shape)}")


def _as_rot_quat(sq_rot: torch.Tensor) -> torch.Tensor:
    """Accept either quat [...,4] or matrix [...,3,3]; return quat."""
    if sq_rot.shape[-1] == 4 and sq_rot.shape[-2:] != (3, 3):
        return sq_rot
    if sq_rot.shape[-2:] == (3, 3):
        return mat_to_quat(sq_rot)
    raise ValueError(f"SQ rotation must be [...,4] quat or [...,3,3] matrix, got {tuple(sq_rot.shape)}")


# -------------------------
# Point transforms
# -------------------------
def world_to_sq_local(
    points: torch.Tensor,
    sq_trans: torch.Tensor,
    sq_rot: torch.Tensor,
) -> torch.Tensor:
    """Transform world-frame points into the SQ's rotated-and-centered frame.

    p_local = R^T (p - t)        # no scale divide — see module docstring.

    Args:
        points:   [..., 3] world-frame (or normalized-frame) points
        sq_trans: [..., 3] SQ translation  (broadcasts with points)
        sq_rot:   [..., 4] xyzw quat OR [..., 3, 3] rotation matrix
    """
    R = _as_rot_matrix(sq_rot)
    centered = points - sq_trans
    return torch.einsum("...ji,...j->...i", R, centered)


def sq_local_to_world(
    points_local: torch.Tensor,
    sq_trans: torch.Tensor,
    sq_rot: torch.Tensor,
) -> torch.Tensor:
    """Inverse of `world_to_sq_local`:  p_world = R @ p_local + t."""
    R = _as_rot_matrix(sq_rot)
    rotated = torch.einsum("...ij,...j->...i", R, points_local)
    return rotated + sq_trans


# -------------------------
# Quaternion transforms
# -------------------------
def rotate_quaternion_to_sq_local(
    q_world: torch.Tensor,
    sq_rot: torch.Tensor,
) -> torch.Tensor:
    """Gaussian orientation (wxyz) → SQ-local orientation.

    q_local = conj(q_sq) ⊗ q_world
    """
    q_sq = _as_rot_quat(sq_rot)
    return quat_mul(quat_conjugate(q_sq), q_world)


def rotate_quaternion_to_world(
    q_local: torch.Tensor,
    sq_rot: torch.Tensor,
) -> torch.Tensor:
    """Inverse of `rotate_quaternion_to_sq_local`.

    q_world = q_sq ⊗ q_local
    """
    q_sq = _as_rot_quat(sq_rot)
    return quat_mul(q_sq, q_local)


# -------------------------
# Convenience: SuperDec radial distance (paper Eq. 2)
# -------------------------
def sq_inside_outside(
    points: torch.Tensor,
    sq_trans: torch.Tensor,
    sq_rot: torch.Tensor,
    sq_scale: torch.Tensor,
    sq_shape: torch.Tensor,
) -> torch.Tensor:
    """Superquadric implicit function f(p) from SuperDec LM optimizer.

    Matches `lm_optimization/lm_optimizer.py::compute_residuals_points_unweighted`
    and SuperDec paper Eq. 1. The expression is:

        f = ((x/sx)^(2/ε₂) + (y/sy)^(2/ε₂))^(ε₂/ε₁) + (z/sz)^(2/ε₁)

    with `sq_shape = (ε₁, ε₂)`.

    f < 1 → inside, f = 1 → surface, f > 1 → outside.

    (Note: SuperDec's `predictions_handler.py::get_occupancy` uses a different
    formula — 1/ε₁ in all three slots. That utility is inconsistent with the
    training loss; trust this one.)
    """
    p_local = world_to_sq_local(points, sq_trans, sq_rot)
    p_canon = p_local / sq_scale
    eps1 = sq_shape[..., 0]
    eps2 = sq_shape[..., 1]
    ax = p_canon[..., 0].abs().clamp_min(1e-12).pow(2.0 / eps2)
    ay = p_canon[..., 1].abs().clamp_min(1e-12).pow(2.0 / eps2)
    az = p_canon[..., 2].abs().clamp_min(1e-12).pow(2.0 / eps1)
    return (ax + ay).pow(eps2 / eps1) + az


def sq_radial_distance(
    points: torch.Tensor,
    sq_trans: torch.Tensor,
    sq_rot: torch.Tensor,
    sq_scale: torch.Tensor,
    sq_shape: torch.Tensor,
) -> torch.Tensor:
    """Radial distance magnitude to SQ surface (SuperDec paper Eq. 2).

    d(p, SQ) = ||p - t|| · | f(p)^(-ε₁/2) - 1 |

    Zero on surface. Positive on both sides (magnitude only; sign of
    `f^(-ε₁/2) - 1` is +inside / -outside — see docstring of
    `sq_inside_outside`). Used for argmin hard-assignment of Gaussians to
    parent SQs.
    """
    f = sq_inside_outside(points, sq_trans, sq_rot, sq_scale, sq_shape)
    radius = (points - sq_trans).norm(dim=-1)
    eps1 = sq_shape[..., 0]
    f_safe = f.clamp_min(1e-12)
    return radius * (f_safe.pow(-eps1 / 2.0) - 1.0).abs()

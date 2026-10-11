"""Round-trip + cross-check tests for pipeline.sq_math.

Run:
    cd /lustre/fs1/home/al402390/cv6412-anysplat-rigging
    python -m pytest austin_implementation/tests/test_sq_math.py -v
"""
from __future__ import annotations

import os
import sys

import pytest
import torch

WORKTREE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ANYSPLAT_DIR = os.path.join(WORKTREE, "anysplat")
AUSTIN_IMPL = os.path.join(WORKTREE, "austin_implementation")
sys.path.insert(0, AUSTIN_IMPL)
sys.path.insert(0, ANYSPLAT_DIR)

from pipeline.sq_math import (  # noqa: E402
    quat_conjugate,
    quat_mul,
    quat_to_mat,
    mat_to_quat,
    world_to_sq_local,
    sq_local_to_world,
    rotate_quaternion_to_sq_local,
    rotate_quaternion_to_world,
    sq_inside_outside,
    sq_radial_distance,
)


ATOL = 1e-5
SEED = 0xC0FFEE


def _rand_quat(n: int, generator: torch.Generator) -> torch.Tensor:
    """Random unit xyzw quaternion, shape [n, 4]."""
    q = torch.randn(n, 4, generator=generator, dtype=torch.float64)
    return q / q.norm(dim=-1, keepdim=True)


def _rand_positive(shape, generator, low=0.1, high=1.5) -> torch.Tensor:
    u = torch.rand(shape, generator=generator, dtype=torch.float64)
    return low + (high - low) * u


@pytest.fixture
def gen():
    g = torch.Generator()
    g.manual_seed(SEED)
    return g


# -----------------------------
# Quaternion basics
# -----------------------------
def test_quat_conjugate_involution(gen):
    q = _rand_quat(32, gen)
    assert torch.allclose(quat_conjugate(quat_conjugate(q)), q, atol=ATOL)


def test_quat_mul_identity(gen):
    q = _rand_quat(32, gen)
    ident = torch.tensor([0.0, 0.0, 0.0, 1.0], dtype=torch.float64).expand_as(q)
    assert torch.allclose(quat_mul(q, ident), q, atol=ATOL)
    assert torch.allclose(quat_mul(ident, q), q, atol=ATOL)


def test_quat_mul_conjugate_is_identity(gen):
    q = _rand_quat(32, gen)
    r = quat_mul(q, quat_conjugate(q))
    # r should be (0, 0, 0, 1)
    ident = torch.tensor([0.0, 0.0, 0.0, 1.0], dtype=torch.float64).expand_as(q)
    assert torch.allclose(r, ident, atol=ATOL)


def test_quat_to_mat_is_special_orthogonal(gen):
    q = _rand_quat(32, gen)
    R = quat_to_mat(q)
    eye = torch.eye(3, dtype=R.dtype).expand_as(R)
    assert torch.allclose(R @ R.transpose(-1, -2), eye, atol=ATOL)
    assert torch.allclose(torch.linalg.det(R), torch.ones(R.shape[0], dtype=R.dtype), atol=ATOL)


def test_quat_mat_quat_roundtrip(gen):
    q = _rand_quat(32, gen)
    R = quat_to_mat(q)
    q2 = mat_to_quat(R)
    # q and -q represent same rotation, so compare via R
    R2 = quat_to_mat(q2)
    assert torch.allclose(R, R2, atol=ATOL)


def test_quat_to_mat_matches_anysplat(gen):
    """Our quat_to_mat must agree with AnySplat's `quaternion_to_matrix` on xyzw input."""
    from src.model.encoder.common.gaussians import quaternion_to_matrix

    q = _rand_quat(32, gen).float()
    R_ours = quat_to_mat(q)
    R_anysplat = quaternion_to_matrix(q)
    assert torch.allclose(R_ours, R_anysplat, atol=ATOL)


def test_build_covariance_matches_anysplat(gen):
    """End-to-end: if we convert q→R via ours, and rebuild Σ = R S S^T R^T, we match AnySplat."""
    from src.model.encoder.common.gaussians import build_covariance

    q = _rand_quat(32, gen).float()
    s = _rand_positive((32, 3), gen).float()

    # AnySplat's covariance from (scale, quat)
    sigma_anysplat = build_covariance(s, q)

    # Reconstruct using our quat_to_mat
    R = quat_to_mat(q)
    S = torch.diag_embed(s)
    sigma_ours = R @ S @ S.transpose(-1, -2) @ R.transpose(-1, -2)

    assert torch.allclose(sigma_ours, sigma_anysplat, atol=ATOL)


# -----------------------------
# Point transforms
# -----------------------------
def test_point_roundtrip_with_matrix_rotation(gen):
    N = 64
    pts = torch.randn(N, 3, generator=gen, dtype=torch.float64) * 3.0
    t = torch.randn(3, generator=gen, dtype=torch.float64)
    R = quat_to_mat(_rand_quat(1, gen).squeeze(0))

    local = world_to_sq_local(pts, t, R)
    pts2 = sq_local_to_world(local, t, R)
    err = (pts2 - pts).abs().max().item()
    assert err < ATOL, f"max roundtrip err {err}"


def test_point_roundtrip_with_quaternion_rotation(gen):
    N = 64
    pts = torch.randn(N, 3, generator=gen, dtype=torch.float64) * 3.0
    t = torch.randn(3, generator=gen, dtype=torch.float64)
    q = _rand_quat(1, gen).squeeze(0)

    local = world_to_sq_local(pts, t, q)
    pts2 = sq_local_to_world(local, t, q)
    err = (pts2 - pts).abs().max().item()
    assert err < ATOL, f"max roundtrip err {err}"


def test_point_broadcast_over_multiple_sqs(gen):
    """Shape broadcast: [N,3] pts against [P,3]/[P,3,3] SQ params → [P,N,3]."""
    N, P = 32, 5
    pts = torch.randn(N, 3, generator=gen, dtype=torch.float64) * 2.0
    t = torch.randn(P, 3, generator=gen, dtype=torch.float64)
    R = quat_to_mat(_rand_quat(P, gen))

    local = world_to_sq_local(pts.unsqueeze(0), t.unsqueeze(1), R.unsqueeze(1))
    assert local.shape == (P, N, 3)

    pts2 = sq_local_to_world(local, t.unsqueeze(1), R.unsqueeze(1))
    err = (pts2 - pts.unsqueeze(0).expand(P, N, 3)).abs().max().item()
    assert err < ATOL, f"max roundtrip err {err}"


def test_point_transform_consistency_quat_vs_matrix(gen):
    """Feeding q vs feeding R = quat_to_mat(q) should give the same result."""
    N = 64
    pts = torch.randn(N, 3, generator=gen, dtype=torch.float64)
    t = torch.randn(3, generator=gen, dtype=torch.float64)
    q = _rand_quat(1, gen).squeeze(0)
    R = quat_to_mat(q)

    local_q = world_to_sq_local(pts, t, q)
    local_R = world_to_sq_local(pts, t, R)
    assert torch.allclose(local_q, local_R, atol=ATOL)


# -----------------------------
# Quaternion transforms
# -----------------------------
def test_quaternion_roundtrip(gen):
    N = 64
    q_world = _rand_quat(N, gen)
    q_sq = _rand_quat(1, gen).squeeze(0)

    q_local = rotate_quaternion_to_sq_local(q_world, q_sq)
    q_world2 = rotate_quaternion_to_world(q_local, q_sq)
    # compare as rotation matrices (to ignore ±q ambiguity)
    R1 = quat_to_mat(q_world)
    R2 = quat_to_mat(q_world2)
    assert torch.allclose(R1, R2, atol=ATOL)


def test_quaternion_transforms_accept_sq_matrix(gen):
    """If caller passes SQ rotation as a 3x3 matrix, result matches the quat path."""
    N = 32
    q_world = _rand_quat(N, gen)
    q_sq = _rand_quat(1, gen).squeeze(0)
    R_sq = quat_to_mat(q_sq)

    q_local_via_quat = rotate_quaternion_to_sq_local(q_world, q_sq)
    q_local_via_mat = rotate_quaternion_to_sq_local(q_world, R_sq)
    # Compare via matrix representation (avoids ±q sign flip)
    assert torch.allclose(
        quat_to_mat(q_local_via_quat), quat_to_mat(q_local_via_mat), atol=ATOL
    )


def test_quaternion_rotation_preserves_vector_action(gen):
    """Rotating a vector by q_world should equal: rotate to local, then back."""
    N = 16
    q_world = _rand_quat(N, gen)
    q_sq = _rand_quat(1, gen).squeeze(0)
    v = torch.randn(N, 3, generator=gen, dtype=torch.float64)

    # world rotation applied directly
    R_world = quat_to_mat(q_world)
    v_direct = torch.einsum("nij,nj->ni", R_world, v)

    # roundtrip through SQ local
    q_local = rotate_quaternion_to_sq_local(q_world, q_sq)
    q_world2 = rotate_quaternion_to_world(q_local, q_sq)
    R_world2 = quat_to_mat(q_world2)
    v_roundtrip = torch.einsum("nij,nj->ni", R_world2, v)

    assert torch.allclose(v_direct, v_roundtrip, atol=ATOL)


# -----------------------------
# Superquadric inside/outside & radial distance (sanity)
# -----------------------------
def test_inside_outside_at_origin_is_inside(gen):
    """A point at the SQ center should be strictly inside (F < 1)."""
    t = torch.randn(3, generator=gen, dtype=torch.float64)
    q = _rand_quat(1, gen).squeeze(0)
    s = _rand_positive((3,), gen, low=0.5, high=1.5)
    shape = torch.tensor([0.5, 0.5], dtype=torch.float64)

    F = sq_inside_outside(t.unsqueeze(0), t, q, s, shape)
    assert F.item() < 1.0


def test_inside_outside_at_axis_scale_is_on_surface(gen):
    """For ε=1 (ellipsoid), a point at (sx,0,0) relative to SQ center is on the surface."""
    t = torch.tensor([0.0, 0.0, 0.0], dtype=torch.float64)
    q = torch.tensor([0.0, 0.0, 0.0, 1.0], dtype=torch.float64)  # identity
    s = torch.tensor([1.0, 1.0, 1.0], dtype=torch.float64)
    shape = torch.tensor([1.0, 1.0], dtype=torch.float64)

    for axis in range(3):
        p = torch.zeros(1, 3, dtype=torch.float64)
        p[0, axis] = s[axis]
        F = sq_inside_outside(p, t, q, s, shape)
        assert abs(F.item() - 1.0) < 1e-6, f"axis {axis} gave F={F.item()}"


def test_radial_distance_at_surface_is_zero(gen):
    """Points on the SQ surface (for ε=1 ellipsoid) should have radial distance near 0."""
    t = torch.tensor([0.0, 0.0, 0.0], dtype=torch.float64)
    q = torch.tensor([0.0, 0.0, 0.0, 1.0], dtype=torch.float64)
    s = torch.tensor([2.0, 1.0, 0.5], dtype=torch.float64)
    shape = torch.tensor([1.0, 1.0], dtype=torch.float64)

    # Surface: (sx,0,0), (0,sy,0), (0,0,sz)
    p = torch.stack([
        torch.tensor([2.0, 0.0, 0.0]),
        torch.tensor([0.0, 1.0, 0.0]),
        torch.tensor([0.0, 0.0, 0.5]),
    ]).double()
    d = sq_radial_distance(p, t, q, s, shape)
    assert d.abs().max().item() < 1e-5, f"max radial distance on surface: {d}"

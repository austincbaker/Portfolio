"""Tests for SQ-bound edit operators (rotate, scale, recolor).

Mirrors the fixture style from `test_rigging.py`: synthetic scene with a
"cube" object's worth of attached Gaussians plus an unattached cluster, a
plausible SuperquadricPrimitive, and a Normalization computed from the cube
points (matching SuperDec's normalize_points exactly).
"""
from __future__ import annotations

import math
import os
import sys

import pytest
import torch

WORKTREE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ANYSPLAT_DIR = os.path.join(WORKTREE, "anysplat")
AUSTIN_IMPL = os.path.join(WORKTREE, "austin_implementation")
sys.path.insert(0, AUSTIN_IMPL)
sys.path.insert(0, ANYSPLAT_DIR)

from pipeline.operators import (  # noqa: E402
    SH0,
    apply_recolor,
    apply_rotate,
    apply_scale,
    apply_translate,
)
from pipeline.rigging import (  # noqa: E402
    SuperquadricPrimitive,
    bind,
    compute_normalization,
)
from pipeline.sq_math import quat_to_mat  # noqa: E402
from pipeline.types import GaussiansResult, LiftResult  # noqa: E402


SEED = 0xC0FFEE
DTYPE = torch.float64


def _rand_unit_quat(gen, n=1):
    q = torch.randn(n, 4, generator=gen, dtype=DTYPE)
    return q / q.norm(dim=-1, keepdim=True)


@pytest.fixture
def synthetic_scene():
    g = torch.Generator().manual_seed(SEED)

    N_cube = 200
    N_other = 200
    N = N_cube + N_other

    cube_center = torch.tensor([2.0, -1.0, 0.5], dtype=DTYPE)
    cube_pts = cube_center + 2.0 * (torch.rand(N_cube, 3, generator=g, dtype=DTYPE) - 0.5)
    other_pts = torch.tensor([-3.0, 2.0, 1.0], dtype=DTYPE) + torch.randn(
        N_other, 3, generator=g, dtype=DTYPE
    )
    means = torch.cat([cube_pts, other_pts], dim=0)

    rotations = _rand_unit_quat(g, N)
    scales = 0.01 + 0.05 * torch.rand(N, 3, generator=g, dtype=DTYPE)
    R_all = quat_to_mat(rotations)
    S_all = torch.diag_embed(scales)
    covariances = R_all @ S_all @ S_all.transpose(-1, -2) @ R_all.transpose(-1, -2)

    opacities = torch.rand(N, generator=g, dtype=DTYPE)
    # Non-trivial SH so we can test which bands change under rotate/recolor.
    harmonics = torch.randn(N, 3, 25, generator=g, dtype=DTYPE) * 0.1

    K = 4
    extrinsics = torch.eye(4, dtype=DTYPE).unsqueeze(0).expand(K, 4, 4).clone()
    intrinsics = torch.eye(3, dtype=DTYPE).unsqueeze(0).expand(K, 3, 3).clone()

    gaussians = GaussiansResult(
        means=means,
        covariances=covariances,
        harmonics=harmonics,
        opacities=opacities,
        scales=scales,
        rotations=rotations,
        extrinsics=extrinsics,
        intrinsics=intrinsics,
        image_size=(64, 64),
    )

    labels = torch.full((N,), -1, dtype=torch.long)
    labels[:N_cube] = 0
    lift = LiftResult(labels=labels, object_names=["cube"])

    normalization = compute_normalization(cube_pts)

    q_sq = _rand_unit_quat(g, 1).squeeze(0)
    R_sq = quat_to_mat(q_sq)
    primitive = SuperquadricPrimitive(
        scale_norm=torch.tensor([0.3, 0.25, 0.4], dtype=DTYPE),
        shape=torch.tensor([0.5, 0.5], dtype=DTYPE),
        t_norm=torch.tensor([0.05, -0.02, 0.1], dtype=DTYPE),
        R_norm=R_sq,
        q_norm_xyzw=q_sq,
    )

    scene = bind(gaussians, lift, 0, primitive, normalization)

    return dict(
        gaussians=gaussians,
        scene=scene,
        N_cube=N_cube,
        N_other=N_other,
    )


def _attached_mask(scene, N):
    mask = torch.zeros(N, dtype=torch.bool)
    mask[scene.binding.attached_idx] = True
    return mask


def _pivot_world(scene):
    return scene.normalization.s * scene.primitive.t_norm + scene.normalization.c


# -----------------------------
# Round-trip & identity
# -----------------------------
def test_translate_idempotent_in_total_delta(synthetic_scene):
    """`apply_translate` is parameterized by total delta from bind, not delta
    from current state — so `translate(g_fwd, d) == translate(g_orig, d)`.
    Documenting this asymmetry vs. rotate/scale (which compose normally)."""
    s = synthetic_scene
    delta = torch.tensor([0.4, -0.2, 0.9], dtype=DTYPE)
    g_fwd1 = apply_translate(s["scene"], s["gaussians"], delta)
    g_fwd2 = apply_translate(s["scene"], g_fwd1, delta)
    attached = s["scene"].binding.attached_idx
    # Both should land at p_world_bind + delta — second call is a no-op on attached.
    assert torch.allclose(g_fwd1.means[attached], g_fwd2.means[attached], atol=1e-12)


def test_rotate_zero_angle_is_identity(synthetic_scene):
    s = synthetic_scene
    out = apply_rotate(
        s["scene"], s["gaussians"], torch.tensor([1.0, 0.0, 0.0], dtype=DTYPE), 0.0
    )
    assert torch.allclose(out.means, s["gaussians"].means, atol=1e-12)
    # rotations may differ by sign (q vs -q represent same rotation); compare via dot.
    dot = (out.rotations * s["gaussians"].rotations).sum(dim=-1).abs()
    assert torch.allclose(dot, torch.ones_like(dot), atol=1e-10)
    assert torch.allclose(out.covariances, s["gaussians"].covariances, atol=1e-12)
    # Bands ℓ=0,1 unchanged at zero rotation; ℓ≥2 zeroed for attached.
    attached = s["scene"].binding.attached_idx
    assert torch.allclose(
        out.harmonics[attached, :, :4], s["gaussians"].harmonics[attached, :, :4], atol=1e-12
    )
    assert torch.equal(out.harmonics[attached, :, 4:], torch.zeros_like(out.harmonics[attached, :, 4:]))


def test_scale_factor_one_is_identity(synthetic_scene):
    s = synthetic_scene
    out = apply_scale(s["scene"], s["gaussians"], 1.0)
    assert torch.allclose(out.means, s["gaussians"].means, atol=1e-12)
    assert torch.allclose(out.scales, s["gaussians"].scales, atol=1e-12)
    assert torch.allclose(out.covariances, s["gaussians"].covariances, atol=1e-12)


def test_recolor_tint_with_grey_is_identity(synthetic_scene):
    s = synthetic_scene
    out = apply_recolor(
        s["scene"], s["gaussians"], "tint", torch.tensor([0.5, 0.5, 0.5], dtype=DTYPE)
    )
    assert torch.allclose(out.harmonics, s["gaussians"].harmonics, atol=1e-12)


# -----------------------------
# Rotate
# -----------------------------
def test_rotate_pivot_invariance(synthetic_scene):
    """The SQ centroid in world frame must be a fixed point of rotate."""
    s = synthetic_scene
    pivot_before = _pivot_world(s["scene"])
    out = apply_rotate(
        s["scene"], s["gaussians"], torch.tensor([0.3, 1.0, -0.5], dtype=DTYPE), 0.7
    )
    # Pivot is derived from scene state (not modified) — check that mean of
    # attached Gaussians doesn't drift orthogonally to the rotation about pivot.
    attached = s["scene"].binding.attached_idx
    mean_before = s["gaussians"].means[attached].mean(dim=0)
    mean_after = out.means[attached].mean(dim=0)
    # Distance from pivot is preserved (rotation is rigid).
    d_before = (mean_before - pivot_before).norm()
    d_after = (mean_after - pivot_before).norm()
    assert torch.isclose(d_before, d_after, atol=1e-10)


def test_rotate_only_touches_attached(synthetic_scene):
    s = synthetic_scene
    mask = _attached_mask(s["scene"], s["gaussians"].means.shape[0])
    out = apply_rotate(
        s["scene"], s["gaussians"], torch.tensor([0.0, 0.0, 1.0], dtype=DTYPE), 0.5
    )
    assert torch.equal(out.means[~mask], s["gaussians"].means[~mask])
    assert torch.equal(out.rotations[~mask], s["gaussians"].rotations[~mask])
    assert torch.equal(out.covariances[~mask], s["gaussians"].covariances[~mask])
    assert torch.equal(out.harmonics[~mask], s["gaussians"].harmonics[~mask])


def test_rotate_covariance_is_R_sigma_RT(synthetic_scene):
    s = synthetic_scene
    axis = torch.tensor([0.2, 0.7, -0.3], dtype=DTYPE)
    angle = 0.4
    out = apply_rotate(s["scene"], s["gaussians"], axis, angle)

    # Rebuild R the same way the operator does.
    from pipeline.operators import _axis_angle_to_matrix
    R = _axis_angle_to_matrix(axis, angle)

    attached = s["scene"].binding.attached_idx
    sigma = s["gaussians"].covariances[attached]
    expected = torch.einsum("ij,njk,kl->nil", R, sigma, R.transpose(-1, -2))
    assert torch.allclose(out.covariances[attached], expected, atol=1e-12)


def test_rotate_round_trip_means(synthetic_scene):
    """Rotate by +θ then by -θ about same axis must restore means and covariances."""
    s = synthetic_scene
    axis = torch.tensor([0.5, -0.4, 0.8], dtype=DTYPE)
    angle = 1.1
    g_fwd = apply_rotate(s["scene"], s["gaussians"], axis, angle)
    g_back = apply_rotate(s["scene"], g_fwd, axis, -angle)
    attached = s["scene"].binding.attached_idx
    assert torch.allclose(g_back.means[attached], s["gaussians"].means[attached], atol=1e-10)
    assert torch.allclose(
        g_back.covariances[attached], s["gaussians"].covariances[attached], atol=1e-10
    )


# -----------------------------
# Scale
# -----------------------------
def test_scale_pivot_invariance_and_radius(synthetic_scene):
    s = synthetic_scene
    alpha = 1.7
    pivot = _pivot_world(s["scene"])
    out = apply_scale(s["scene"], s["gaussians"], alpha)

    attached = s["scene"].binding.attached_idx
    rel_before = s["gaussians"].means[attached] - pivot
    rel_after = out.means[attached] - pivot
    assert torch.allclose(rel_after, alpha * rel_before, atol=1e-12)


def test_scale_updates_scales_and_covariances(synthetic_scene):
    s = synthetic_scene
    alpha = 0.6
    out = apply_scale(s["scene"], s["gaussians"], alpha)

    attached = s["scene"].binding.attached_idx
    assert torch.allclose(out.scales[attached], alpha * s["gaussians"].scales[attached], atol=1e-12)
    assert torch.allclose(
        out.covariances[attached], (alpha * alpha) * s["gaussians"].covariances[attached], atol=1e-12
    )
    # Off-attached unchanged.
    mask = _attached_mask(s["scene"], s["gaussians"].means.shape[0])
    assert torch.equal(out.scales[~mask], s["gaussians"].scales[~mask])
    assert torch.equal(out.covariances[~mask], s["gaussians"].covariances[~mask])


def test_scale_rejects_nonpositive(synthetic_scene):
    s = synthetic_scene
    with pytest.raises(ValueError):
        apply_scale(s["scene"], s["gaussians"], 0.0)
    with pytest.raises(ValueError):
        apply_scale(s["scene"], s["gaussians"], -1.0)


# -----------------------------
# Recolor
# -----------------------------
def test_recolor_replace_zeros_higher_bands_and_sets_dc(synthetic_scene):
    s = synthetic_scene
    rgb = torch.tensor([1.0, 0.0, 0.0], dtype=DTYPE)
    out = apply_recolor(s["scene"], s["gaussians"], "replace", rgb)

    attached = s["scene"].binding.attached_idx
    expected_dc = (rgb - 0.5) / SH0       # [3]
    got_dc = out.harmonics[attached, :, 0]  # [M, 3]
    assert torch.allclose(got_dc, expected_dc.unsqueeze(0).expand_as(got_dc), atol=1e-12)
    assert torch.equal(
        out.harmonics[attached, :, 1:], torch.zeros_like(out.harmonics[attached, :, 1:])
    )
    # Off-attached unchanged.
    mask = _attached_mask(s["scene"], s["gaussians"].means.shape[0])
    assert torch.equal(out.harmonics[~mask], s["gaussians"].harmonics[~mask])


def test_recolor_tint_preserves_higher_bands_and_shifts_dc(synthetic_scene):
    s = synthetic_scene
    rgb = torch.tensor([0.7, 0.5, 0.5], dtype=DTYPE)  # warm tint
    out = apply_recolor(s["scene"], s["gaussians"], "tint", rgb)

    attached = s["scene"].binding.attached_idx
    delta_dc = (rgb - 0.5) / SH0
    expected_dc = s["gaussians"].harmonics[attached, :, 0] + delta_dc.unsqueeze(0)
    assert torch.allclose(out.harmonics[attached, :, 0], expected_dc, atol=1e-12)
    # Higher bands preserved.
    assert torch.allclose(
        out.harmonics[attached, :, 1:], s["gaussians"].harmonics[attached, :, 1:], atol=1e-12
    )


def test_recolor_invalid_mode_raises(synthetic_scene):
    s = synthetic_scene
    with pytest.raises(ValueError):
        apply_recolor(
            s["scene"], s["gaussians"], "lerp", torch.tensor([0.5, 0.5, 0.5], dtype=DTYPE)
        )


# -----------------------------
# All operators leave non-attached Gaussians untouched (sanity)
# -----------------------------
@pytest.mark.parametrize("op,args", [
    ("translate", (torch.tensor([0.1, 0.2, -0.3], dtype=DTYPE),)),
    ("scale", (1.3,)),
    ("rotate", (torch.tensor([0.0, 0.0, 1.0], dtype=DTYPE), 0.5)),
])
def test_disjoint_other_means_unchanged(synthetic_scene, op, args):
    s = synthetic_scene
    fn = {"translate": apply_translate, "scale": apply_scale, "rotate": apply_rotate}[op]
    out = fn(s["scene"], s["gaussians"], *args)
    mask = _attached_mask(s["scene"], s["gaussians"].means.shape[0])
    assert torch.equal(out.means[~mask], s["gaussians"].means[~mask])

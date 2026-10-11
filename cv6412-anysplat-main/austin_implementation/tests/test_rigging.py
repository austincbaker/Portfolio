"""Tests for rigging + operators (spec §8 T4–T9, minus T8 surface sampling).

Build a synthetic scene:
    - 4000 random points around a cube-ish region as the "cube" Gaussians
    - another 4000 random points as "non-cube" (unattached) Gaussians
    - a known SuperquadricPrimitive in the normalized frame
    - manually-constructed Normalization from the cube points via
      compute_normalization (so it matches SuperDec's `normalize_points` exactly)

Then exercise bind, apply_translate, and radial_distance_world against the spec.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest
import torch

WORKTREE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ANYSPLAT_DIR = os.path.join(WORKTREE, "anysplat")
AUSTIN_IMPL = os.path.join(WORKTREE, "austin_implementation")
sys.path.insert(0, AUSTIN_IMPL)
sys.path.insert(0, ANYSPLAT_DIR)

from pipeline.rigging import (  # noqa: E402
    Normalization,
    RiggedScene,
    SuperquadricPrimitive,
    bind,
    compute_normalization,
    radial_distance_world,
    world_to_normalized,
)
from pipeline.operators import apply_translate  # noqa: E402
from pipeline.sq_math import (  # noqa: E402
    mat_to_quat,
    quat_to_mat,
    world_to_sq_local,
)
from pipeline.types import GaussiansResult, LiftResult  # noqa: E402


SEED = 0xC0FFEE
DTYPE = torch.float64  # use fp64 for the round-trip tests for tighter tolerances


def _rand_unit_quat(gen, n=1):
    q = torch.randn(n, 4, generator=gen, dtype=DTYPE)
    return q / q.norm(dim=-1, keepdim=True)


@pytest.fixture
def synthetic_scene():
    g = torch.Generator().manual_seed(SEED)

    N_cube = 4000
    N_other = 4000
    N = N_cube + N_other

    # Cube Gaussians: random points in roughly a box [-1,1]^3 shifted by (2,-1,0.5)
    cube_center = torch.tensor([2.0, -1.0, 0.5], dtype=DTYPE)
    cube_pts = cube_center + 2.0 * (torch.rand(N_cube, 3, generator=g, dtype=DTYPE) - 0.5)

    # Other Gaussians: far away cluster
    other_pts = torch.tensor([-3.0, 2.0, 1.0], dtype=DTYPE) + torch.randn(
        N_other, 3, generator=g, dtype=DTYPE
    )

    means = torch.cat([cube_pts, other_pts], dim=0)

    # Random unit xyzw quaternion per Gaussian
    rotations = _rand_unit_quat(g, N)
    scales = 0.01 + 0.05 * torch.rand(N, 3, generator=g, dtype=DTYPE)
    # Covariances from (scales, rotations) to match AnySplat storage convention
    R_all = quat_to_mat(rotations)
    S_all = torch.diag_embed(scales)
    covariances = R_all @ S_all @ S_all.transpose(-1, -2) @ R_all.transpose(-1, -2)

    opacities = torch.rand(N, generator=g, dtype=DTYPE)
    harmonics = torch.zeros(N, 3, 25, dtype=DTYPE)

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
    labels[:N_cube] = 0  # cube_idx = 0
    lift = LiftResult(labels=labels, object_names=["cube"])

    # Normalization from the cube points alone (same set fed to SuperDec in prod)
    normalization = compute_normalization(cube_pts)

    # Build a plausible SQ primitive: a rotated, off-center box in the normalized frame.
    q_sq = _rand_unit_quat(g, 1).squeeze(0)
    R_sq = quat_to_mat(q_sq)
    primitive = SuperquadricPrimitive(
        scale_norm=torch.tensor([0.3, 0.25, 0.4], dtype=DTYPE),
        shape=torch.tensor([0.5, 0.5], dtype=DTYPE),
        t_norm=torch.tensor([0.05, -0.02, 0.1], dtype=DTYPE),
        R_norm=R_sq,
        q_norm_xyzw=q_sq,
    )

    return dict(
        gaussians=gaussians,
        lift=lift,
        normalization=normalization,
        primitive=primitive,
        N_cube=N_cube,
        N_other=N_other,
    )


# -----------------------------
# Normalization matches SuperDec's code exactly (§4, corrected for L∞)
# -----------------------------
def test_normalization_matches_superdec_numpy():
    """Our compute_normalization must bit-match `data/dataloader.py::normalize_points`.

    Inlined here to avoid importing superdec.data.dataloader (which eagerly
    imports open3d at module top). The formula below is a byte-for-byte copy
    of the function body — update this together with any upstream change.
    """
    def normalize_points_superdec(points):
        translation = points.mean(0)
        points = points - translation
        scale = 2 * np.max(np.abs(points))
        points = points / scale
        return points, translation, scale

    g = torch.Generator().manual_seed(SEED)
    pts = torch.randn(512, 3, generator=g, dtype=torch.float64) * 3.0 + torch.tensor([1.0, 2.0, -0.5])
    pts_np = pts.numpy().copy()
    p_norm_sd, t_sd, s_sd = normalize_points_superdec(pts_np)

    norm = compute_normalization(pts)
    p_norm_ours = world_to_normalized(pts, norm)

    assert np.allclose(norm.c.numpy(), t_sd, atol=1e-12), "centroid mismatch"
    assert np.isclose(norm.s.item(), s_sd, atol=1e-12), (
        f"scale mismatch: ours={norm.s.item()} sd={s_sd}"
    )
    assert np.allclose(p_norm_ours.numpy(), p_norm_sd, atol=1e-12)


def test_normalization_rejects_degenerate():
    # Empty
    with pytest.raises(ValueError):
        compute_normalization(torch.zeros(0, 3))
    # All points coincident
    with pytest.raises(ValueError):
        compute_normalization(torch.ones(10, 3))


# -----------------------------
# T4 — translate-identity fixpoint
# -----------------------------
def test_translate_zero_is_exact_identity(synthetic_scene):
    s = synthetic_scene
    scene = bind(s["gaussians"], s["lift"], 0, s["primitive"], s["normalization"])
    result = apply_translate(scene, s["gaussians"], torch.zeros(3, dtype=DTYPE))
    assert torch.equal(result.means, s["gaussians"].means)


# -----------------------------
# T5 — attached shifts by exactly delta, others unchanged
# -----------------------------
def test_translate_shifts_only_attached(synthetic_scene):
    s = synthetic_scene
    delta = torch.tensor([0.3, -0.1, 0.7], dtype=DTYPE)
    scene = bind(s["gaussians"], s["lift"], 0, s["primitive"], s["normalization"])
    result = apply_translate(scene, s["gaussians"], delta)

    attached = scene.binding.attached_idx
    mask = torch.zeros(s["gaussians"].means.shape[0], dtype=torch.bool)
    mask[attached] = True

    got_attached = result.means[mask]
    want_attached = s["gaussians"].means[mask] + delta
    assert torch.allclose(got_attached, want_attached, atol=1e-12)

    got_other = result.means[~mask]
    want_other = s["gaussians"].means[~mask]
    assert torch.equal(got_other, want_other)


# -----------------------------
# T5b — apply_translate passes invariant fields through BY REFERENCE (not clone)
# -----------------------------
def test_translate_aliases_invariant_fields(synthetic_scene):
    """Spec §9 item 8: don't materialize Σ for attached Gaussians under translate."""
    s = synthetic_scene
    scene = bind(s["gaussians"], s["lift"], 0, s["primitive"], s["normalization"])
    delta = torch.tensor([0.3, -0.1, 0.7], dtype=DTYPE)
    result = apply_translate(scene, s["gaussians"], delta)

    # Identity — same tensor object, not a copy.
    assert result.covariances is s["gaussians"].covariances
    assert result.harmonics is s["gaussians"].harmonics
    assert result.opacities is s["gaussians"].opacities
    assert result.scales is s["gaussians"].scales
    assert result.rotations is s["gaussians"].rotations
    assert result.extrinsics is s["gaussians"].extrinsics
    assert result.intrinsics is s["gaussians"].intrinsics
    assert result.image_size == s["gaussians"].image_size
    # Means is the one field that MUST be a new tensor.
    assert result.means is not s["gaussians"].means


# -----------------------------
# T6 — body-frame invariance after translate (the real correctness check)
# -----------------------------
def test_body_frame_invariance_after_translate(synthetic_scene):
    s = synthetic_scene
    delta = torch.tensor([0.3, -0.1, 0.7], dtype=DTYPE)
    scene = bind(s["gaussians"], s["lift"], 0, s["primitive"], s["normalization"])
    result = apply_translate(scene, s["gaussians"], delta)

    # New primitive pose in normalized frame:
    t_norm_new = scene.primitive.t_norm + delta / scene.normalization.s

    # World→normalized→local for the post-translate attached Gaussians, using
    # the NEW primitive pose. Should reproduce the bind-time p_local.
    p_world_new = result.means[scene.binding.attached_idx]
    p_norm_new = world_to_normalized(p_world_new, scene.normalization)
    p_local_new = world_to_sq_local(p_norm_new, t_norm_new, scene.primitive.R_norm)

    err = (p_local_new - scene.binding.p_local).abs().max().item()
    assert err < 1e-10, f"body-frame invariance violated: max |Δp_local| = {err:.3e}"


# -----------------------------
# T7 — collapse consistency (full chain == collapsed form)
# -----------------------------
def test_translate_full_chain_matches_collapsed(synthetic_scene):
    s = synthetic_scene
    delta = torch.tensor([0.3, -0.1, 0.7], dtype=DTYPE)
    scene = bind(s["gaussians"], s["lift"], 0, s["primitive"], s["normalization"])
    # check_full_chain=True raises if full chain disagrees
    apply_translate(scene, s["gaussians"], delta, check_full_chain=True, chain_tol=1e-10)


# -----------------------------
# T8 — radial distance on sampled SQ surface points ≈ 0
# -----------------------------
def _sample_sq_surface_parametric(
    scale_norm, shape, R_norm, t_norm, n_u=32, n_v=32
):
    """Parametric superquadric surface sampling.

        x(u,v) = sx · sign(cos v) |cos v|^ε1 · sign(cos u) |cos u|^ε2
        y(u,v) = sy · sign(cos v) |cos v|^ε1 · sign(sin u) |sin u|^ε2
        z(u,v) = sz · sign(sin v) |sin v|^ε1

    u ∈ [-π, π], v ∈ [-π/2, π/2]. Points generated in SQ-local frame; we apply
    R_norm and t_norm to lift to the normalized frame.
    """
    dtype = scale_norm.dtype
    u = torch.linspace(-torch.pi, torch.pi, n_u, dtype=dtype)
    v = torch.linspace(-torch.pi / 2, torch.pi / 2, n_v, dtype=dtype)
    uu, vv = torch.meshgrid(u, v, indexing="ij")

    def _f(o, m):
        return torch.sign(torch.sin(o)) * torch.sin(o).abs().pow(m)

    def _g(o, m):
        return torch.sign(torch.cos(o)) * torch.cos(o).abs().pow(m)

    eps1 = shape[0]
    eps2 = shape[1]
    x = scale_norm[0] * _g(vv, eps1) * _g(uu, eps2)
    y = scale_norm[1] * _g(vv, eps1) * _f(uu, eps2)
    z = scale_norm[2] * _f(vv, eps1)

    pts_local = torch.stack([x, y, z], dim=-1).reshape(-1, 3)
    pts_norm = torch.einsum("ij,mj->mi", R_norm, pts_local) + t_norm
    return pts_norm


def test_sampled_surface_points_have_small_radial_distance(synthetic_scene):
    """Spec T8 — points sampled on the SQ surface should have |d_r| ≲ small."""
    from pipeline.rigging import radial_distance_world

    s = synthetic_scene
    scene = bind(s["gaussians"], s["lift"], 0, s["primitive"], s["normalization"])
    prim = scene.primitive

    pts_norm = _sample_sq_surface_parametric(
        prim.scale_norm, prim.shape, prim.R_norm, prim.t_norm, n_u=32, n_v=32
    )
    # Lift to world frame via inverse of normalization
    pts_world = pts_norm * scene.normalization.s + scene.normalization.c

    d = radial_distance_world(pts_world, scene)
    # Parametric points should sit exactly on the implicit surface (f = 1),
    # so f^(-ε₁/2) - 1 = 0, giving d ~= 0 up to floating-point noise.
    # Corners of the parametric patch have numerical drift; take 99th percentile.
    d_sorted, _ = d.sort()
    d_99 = d_sorted[int(0.99 * d.numel())].item()
    assert d_99 < 1e-3, f"99th percentile radial distance on surface = {d_99:.3e}"


# -----------------------------
# T9 — radial distance sanity (center inside, far away outside)
# -----------------------------
def test_radial_distance_center_vs_far(synthetic_scene):
    s = synthetic_scene
    scene = bind(s["gaussians"], s["lift"], 0, s["primitive"], s["normalization"])

    # SQ center in world frame
    center_world = scene.normalization.s * scene.primitive.t_norm + scene.normalization.c
    d_center = radial_distance_world(center_world.unsqueeze(0), scene)

    # Very far away
    far = center_world + torch.tensor([100.0, 0.0, 0.0], dtype=DTYPE)
    d_far = radial_distance_world(far.unsqueeze(0), scene)

    # Both return magnitudes; far-away d should be huge compared to center d.
    assert d_far.item() > 1.0 * d_center.item() + 1.0, (
        f"d_center={d_center.item()}, d_far={d_far.item()}"
    )


# -----------------------------
# Boundary conversion (spec §3)
# -----------------------------
def test_superdec_quat_to_anysplat_order():
    from pipeline.rigging import superdec_quat_to_anysplat_order

    q_wxyz = torch.tensor([[0.5, 0.6, 0.7, 0.8]])
    q_xyzw = superdec_quat_to_anysplat_order(q_wxyz)
    assert torch.equal(q_xyzw, torch.tensor([[0.6, 0.7, 0.8, 0.5]]))


# -----------------------------
# Parse SuperquadricPrimitive from synthetic outdict (spec §3 verification)
# -----------------------------
def test_superquadric_from_outdict_matrix_quat_consistency():
    from pipeline.rigging import superquadric_from_outdict

    g = torch.Generator().manual_seed(SEED)
    q = _rand_unit_quat(g, 1).squeeze(0).unsqueeze(0).unsqueeze(0)  # [1,1,4]
    R = quat_to_mat(q)
    outdict = {
        "scale": torch.tensor([[[0.3, 0.25, 0.4]]]),
        "shape": torch.tensor([[[0.5, 0.5]]]),
        "rotate": R,
        "trans": torch.tensor([[[0.05, -0.02, 0.1]]]),
        "exist": torch.tensor([[[0.9]]]),
    }
    p = superquadric_from_outdict(outdict, index=0, batch=0)
    # R_norm and q_norm_xyzw must agree via quat_to_mat
    R_from_q = quat_to_mat(p.q_norm_xyzw)
    assert torch.allclose(R_from_q, p.R_norm, atol=1e-5)

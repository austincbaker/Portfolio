"""Tests for EditSpec + apply_edits_v2.

Render and SuperDec are not exercised here — those are integration concerns
that need CUDA and AnySplat / SuperDec checkpoints. We verify:

- EditSpec.edit_name() is deterministic and changes when params change.
- apply_edit() dispatches to the right operator and respects the cache.
- apply_edits_v2() returns one entry per spec, keyed by edit_name.
- delete operator filters out attached Gaussians without needing a RiggedScene.
"""
from __future__ import annotations

import os
import sys
import tempfile

import pytest
import torch

WORKTREE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ANYSPLAT_DIR = os.path.join(WORKTREE, "anysplat")
AUSTIN_IMPL = os.path.join(WORKTREE, "austin_implementation")
sys.path.insert(0, AUSTIN_IMPL)
sys.path.insert(0, ANYSPLAT_DIR)

from pipeline.edit_v2 import apply_edit, apply_edits_v2  # noqa: E402
from pipeline.rigging import (  # noqa: E402
    SuperquadricPrimitive,
    bind,
    compute_normalization,
)
from pipeline.sq_math import quat_to_mat  # noqa: E402
from pipeline.types import EditSpec, GaussiansResult, LiftResult  # noqa: E402


SEED = 0xC0FFEE
DTYPE = torch.float64


def _rand_unit_quat(gen, n=1):
    q = torch.randn(n, 4, generator=gen, dtype=DTYPE)
    return q / q.norm(dim=-1, keepdim=True)


@pytest.fixture
def synthetic():
    g = torch.Generator().manual_seed(SEED)
    N_cube = 100
    N_other = 100
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
    harmonics = torch.randn(N, 3, 25, generator=g, dtype=DTYPE) * 0.1

    K = 4
    extrinsics = torch.eye(4, dtype=DTYPE).unsqueeze(0).expand(K, 4, 4).clone()
    intrinsics = torch.eye(3, dtype=DTYPE).unsqueeze(0).expand(K, 3, 3).clone()

    gaussians = GaussiansResult(
        means=means, covariances=covariances, harmonics=harmonics,
        opacities=opacities, scales=scales, rotations=rotations,
        extrinsics=extrinsics, intrinsics=intrinsics, image_size=(64, 64),
    )

    labels = torch.full((N,), -1, dtype=torch.long)
    labels[:N_cube] = 0
    lift = LiftResult(labels=labels, object_names=["cube"])

    normalization = compute_normalization(cube_pts)
    q_sq = _rand_unit_quat(g, 1).squeeze(0)
    primitive = SuperquadricPrimitive(
        scale_norm=torch.tensor([0.3, 0.25, 0.4], dtype=DTYPE),
        shape=torch.tensor([0.5, 0.5], dtype=DTYPE),
        t_norm=torch.tensor([0.05, -0.02, 0.1], dtype=DTYPE),
        R_norm=quat_to_mat(q_sq),
        q_norm_xyzw=q_sq,
    )
    scene = bind(gaussians, lift, 0, primitive, normalization)

    return dict(gaussians=gaussians, lift=lift, scene=scene, N_cube=N_cube)


# -----------------------------
# EditSpec
# -----------------------------
def test_edit_spec_rejects_unknown_operator():
    with pytest.raises(ValueError):
        EditSpec(target_object_index=0, operator="frobnicate", params={})


def test_edit_name_is_deterministic_and_human_readable():
    s1 = EditSpec(0, "rotate", {"axis": [0, 1, 0], "angle_rad": 0.5})
    s2 = EditSpec(0, "rotate", {"axis": [0, 1, 0], "angle_rad": 0.5})
    assert s1.edit_name() == s2.edit_name()
    name = s1.edit_name()
    assert name.startswith("rotate_obj0_")
    assert len(name.split("_")[-1]) == 6  # 6-char hex hash


def test_edit_name_changes_with_params():
    s1 = EditSpec(0, "translate", {"delta": [0.3, 0.0, 0.0]})
    s2 = EditSpec(0, "translate", {"delta": [-0.3, 0.0, 0.0]})
    assert s1.edit_name() != s2.edit_name()


def test_edit_name_changes_with_target():
    s1 = EditSpec(0, "scale", {"factor": 1.5})
    s2 = EditSpec(1, "scale", {"factor": 1.5})
    assert s1.edit_name() != s2.edit_name()


# -----------------------------
# apply_edit dispatch
# -----------------------------
def test_apply_edit_dispatches_translate(synthetic):
    s = synthetic
    spec = EditSpec(0, "translate", {"delta": [0.5, 0.0, 0.0]})
    with tempfile.TemporaryDirectory() as cd:
        out = apply_edit(s["gaussians"], s["lift"], spec, scene=s["scene"], cache_dir=cd)
    attached = s["scene"].binding.attached_idx
    delta = torch.tensor([0.5, 0.0, 0.0], dtype=DTYPE)
    expected = s["scene"].binding.p_world_bind + delta
    assert torch.allclose(out.means[attached], expected, atol=1e-12)


def test_apply_edit_dispatches_rotate(synthetic):
    s = synthetic
    spec = EditSpec(0, "rotate", {"axis": [0, 0, 1], "angle_rad": 0.7})
    with tempfile.TemporaryDirectory() as cd:
        out = apply_edit(s["gaussians"], s["lift"], spec, scene=s["scene"], cache_dir=cd)
    attached = s["scene"].binding.attached_idx
    # Distance from pivot is preserved.
    pivot = s["scene"].normalization.s * s["scene"].primitive.t_norm + s["scene"].normalization.c
    d_before = (s["gaussians"].means[attached] - pivot).norm(dim=-1)
    d_after = (out.means[attached] - pivot).norm(dim=-1)
    assert torch.allclose(d_before, d_after, atol=1e-10)


def test_apply_edit_dispatches_scale(synthetic):
    s = synthetic
    spec = EditSpec(0, "scale", {"factor": 1.5})
    with tempfile.TemporaryDirectory() as cd:
        out = apply_edit(s["gaussians"], s["lift"], spec, scene=s["scene"], cache_dir=cd)
    attached = s["scene"].binding.attached_idx
    assert torch.allclose(out.scales[attached], 1.5 * s["gaussians"].scales[attached], atol=1e-12)


def test_apply_edit_dispatches_recolor(synthetic):
    s = synthetic
    spec = EditSpec(0, "recolor", {"mode": "replace", "rgb": [1.0, 0.0, 0.0]})
    with tempfile.TemporaryDirectory() as cd:
        out = apply_edit(s["gaussians"], s["lift"], spec, scene=s["scene"], cache_dir=cd)
    attached = s["scene"].binding.attached_idx
    # Higher bands zeroed.
    assert torch.equal(
        out.harmonics[attached, :, 1:], torch.zeros_like(out.harmonics[attached, :, 1:])
    )


def test_apply_edit_delete_filters_attached(synthetic):
    s = synthetic
    spec = EditSpec(0, "delete", {})
    with tempfile.TemporaryDirectory() as cd:
        out = apply_edit(s["gaussians"], s["lift"], spec, scene=None, cache_dir=cd)
    # Attached gaussians removed; non-attached preserved.
    assert out.means.shape[0] == s["gaussians"].means.shape[0] - s["N_cube"]
    assert torch.equal(out.means, s["gaussians"].means[s["lift"].labels != 0])


def test_apply_edit_non_delete_requires_scene(synthetic):
    s = synthetic
    spec = EditSpec(0, "rotate", {"axis": [0, 0, 1], "angle_rad": 0.1})
    with tempfile.TemporaryDirectory() as cd:
        with pytest.raises(ValueError):
            apply_edit(s["gaussians"], s["lift"], spec, scene=None, cache_dir=cd)


# -----------------------------
# Caching
# -----------------------------
def test_apply_edit_uses_cache_on_repeat_call(synthetic):
    s = synthetic
    spec = EditSpec(0, "translate", {"delta": [0.1, 0.2, 0.3]})
    with tempfile.TemporaryDirectory() as cd:
        out1 = apply_edit(s["gaussians"], s["lift"], spec, scene=s["scene"], cache_dir=cd)
        cache_path = os.path.join(cd, "edit_v2", f"{spec.edit_name()}.pt")
        assert os.path.exists(cache_path), "first call must write a cache file"
        out2 = apply_edit(s["gaussians"], s["lift"], spec, scene=s["scene"], cache_dir=cd)
    assert torch.equal(out1.means, out2.means)


# -----------------------------
# apply_edits_v2 batch
# -----------------------------
def test_apply_edits_v2_returns_one_entry_per_spec(synthetic):
    s = synthetic
    specs = [
        EditSpec(0, "translate", {"delta": [0.3, 0.0, 0.0]}),
        EditSpec(0, "scale", {"factor": 1.4}),
        EditSpec(0, "recolor", {"mode": "tint", "rgb": [0.7, 0.5, 0.5]}),
        EditSpec(0, "delete", {}),
    ]
    with tempfile.TemporaryDirectory() as cd:
        out = apply_edits_v2(
            s["gaussians"], s["lift"], specs,
            scenes_by_obj={0: s["scene"]}, cache_dir=cd,
        )
    assert set(out.keys()) == {sp.edit_name() for sp in specs}
    # Delete result has fewer Gaussians than original.
    delete_name = next(sp.edit_name() for sp in specs if sp.operator == "delete")
    assert out[delete_name].means.shape[0] < s["gaussians"].means.shape[0]


def test_apply_edits_v2_raises_when_scene_missing(synthetic):
    s = synthetic
    specs = [EditSpec(0, "rotate", {"axis": [0, 0, 1], "angle_rad": 0.5})]
    with tempfile.TemporaryDirectory() as cd:
        with pytest.raises(ValueError):
            apply_edits_v2(s["gaussians"], s["lift"], specs, scenes_by_obj={}, cache_dir=cd)

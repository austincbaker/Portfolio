"""End-to-end runner for the edit_v2 demo path.

Reuses the upstream stages (reconstruct → segment → lift_masks) from `run.py`,
loads a SuperDec payload (produced by `experiment_rigging/stage_a_decompose.py`),
binds a `RiggedScene` per target object, applies the edit specs, and renders
the original + each variant with `render_edits`.

Edit specs are loaded from a JSON file. Schema:

    [
      {"target_object_index": 0, "operator": "rotate",
       "params": {"axis": [0, 1, 0], "angle_rad": 0.6}},
      {"target_object_index": 0, "operator": "recolor",
       "params": {"mode": "replace", "rgb": [1.0, 0.0, 0.0]}}
    ]

The SuperDec payload is the same `cube_sq.pt` / similar produced by stage_a:
    {
      "normalization": {"c": Tensor[3], "s": Tensor[]},
      "primitives": [{"R_norm": ..., "scale_norm": ..., "shape": ..., "trans": ...}, ...]
    }
"""
from __future__ import annotations

import json
import os
from typing import Any

import torch

from pipeline.cache import load_or_run  # noqa: F401  (re-exported for completeness)
from pipeline.edit_v2 import apply_edits_v2
from pipeline.lift_masks import lift_masks
from pipeline.reconstruct import reconstruct
from pipeline.render_edits import render_edits
from pipeline.rigging import (
    Normalization,
    RigBinding,
    RiggedScene,
    SuperquadricPrimitive,
    bind,
    radial_distance_world,
)
from pipeline.segment import segment
from pipeline.semantic_router import semantic_router
from pipeline.sq_math import mat_to_quat, quat_to_mat
from pipeline.types import EditSpec


def _primitive_from_payload(p: dict) -> SuperquadricPrimitive:
    R = p["R_norm"].float()
    q = mat_to_quat(R)
    R_check = quat_to_mat(q)
    err = (R_check - R).norm().item()
    if err > 1e-5:
        raise RuntimeError(f"R↔q verification failed: err={err:.3e}")
    return SuperquadricPrimitive(
        scale_norm=p["scale_norm"].float(),
        shape=p["shape"].float(),
        t_norm=p["trans"].float(),
        R_norm=R,
        q_norm_xyzw=q,
    )


def _pick_parent_argmin(p_world, normalization, primitives):
    """Per-Gaussian parent SQ = argmin radial distance across primitives."""
    M = p_world.shape[0]
    d = torch.empty(len(primitives), M, dtype=p_world.dtype, device=p_world.device)
    for pi, prim in enumerate(primitives):
        dummy = RiggedScene(
            primitive=prim,
            normalization=normalization,
            binding=RigBinding(
                attached_idx=torch.zeros(0, dtype=torch.long),
                p_local=torch.zeros(0, 3, dtype=p_world.dtype),
                q_local_xyzw=torch.zeros(0, 4, dtype=p_world.dtype),
                p_world_bind=torch.zeros(0, 3, dtype=p_world.dtype),
            ),
        )
        d[pi] = radial_distance_world(p_world, dummy)
    return d.argmin(dim=0)


def build_scenes_for_targets(
    gaussians,
    lift,
    payload: dict,
    target_indices: list[int],
) -> dict[int, RiggedScene]:
    """For each target object index, bind a RiggedScene against the SuperDec
    primitive that most of that object's Gaussians prefer (argmin radial dist).
    """
    normalization = Normalization(
        c=payload["normalization"]["c"].float(),
        s=payload["normalization"]["s"].float(),
    )
    primitives = [_primitive_from_payload(p) for p in payload["primitives"]]
    if not primitives:
        raise RuntimeError("SuperDec payload has no primitives — re-run stage_a")

    scenes: dict[int, RiggedScene] = {}
    for obj_idx in target_indices:
        attached = (lift.labels == obj_idx)
        n_attached = int(attached.sum())
        if n_attached == 0:
            raise ValueError(f"target_object_index={obj_idx} has 0 attached Gaussians in lift")

        if len(primitives) == 1:
            chosen = primitives[0]
            print(f"[run_edits] obj {obj_idx}: single SQ — binding directly")
        else:
            obj_pts = gaussians.means[attached].float()
            parent = _pick_parent_argmin(obj_pts, normalization, primitives)
            counts = torch.bincount(parent, minlength=len(primitives))
            top = int(counts.argmax().item())
            print(f"[run_edits] obj {obj_idx}: per-SQ counts {counts.tolist()}, "
                  f"binding to SQ #{top}")
            chosen = primitives[top]

        scenes[obj_idx] = bind(gaussians, lift, obj_idx, chosen, normalization)
    return scenes


def _load_specs(specs_json: str) -> list[EditSpec]:
    with open(specs_json) as f:
        raw: list[dict[str, Any]] = json.load(f)
    return [EditSpec(**entry) for entry in raw]


def run_edits(
    image_dir: str,
    query: str,
    specs_json: str,
    sq_pt: str,
    output_dir: str = "outputs",
    view_indices: list[int] | None = None,
) -> None:
    """End-to-end: pipeline up through lift_masks, bind, apply edits, render."""
    cache_dir = f"{output_dir}/cache"
    results_dir = f"{output_dir}/results"

    print(f"=== Pipeline (edit_v2) ===")
    print(f"Images: {image_dir}")
    print(f"Query:  {query}")
    print(f"Specs:  {specs_json}")
    print(f"SQ:     {sq_pt}")
    print()

    semantic = semantic_router(image_dir, query, cache_dir=cache_dir)
    if not semantic.object_names:
        print("[run_edits] semantic router found no objects. Nothing to edit.")
        return

    gaussians, decoder = reconstruct(image_dir, cache_dir=cache_dir)
    segments = segment(image_dir, object_names=semantic.object_names, cache_dir=cache_dir)
    lift = lift_masks(gaussians, segments, cache_dir=cache_dir)

    specs = _load_specs(specs_json)
    print(f"[run_edits] loaded {len(specs)} edit specs")

    payload = torch.load(sq_pt, map_location="cpu", weights_only=False)
    target_indices = sorted({s.target_object_index for s in specs if s.operator != "delete"})
    scenes = build_scenes_for_targets(gaussians, lift, payload, target_indices)

    edited = apply_edits_v2(gaussians, lift, specs, scenes_by_obj=scenes, cache_dir=cache_dir)

    os.makedirs(results_dir, exist_ok=True)
    render_edits(gaussians, edited, decoder, results_dir=results_dir,
                 view_indices=view_indices)

    print(f"\n=== run_edits complete. Results in {results_dir}/ ===")

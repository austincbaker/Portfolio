"""Stage 5 v2: apply structured edits to attached objects.

Replaces the delete-only `edit.py` with a generic stage that consumes a list of
`EditSpec`s and dispatches each to the right operator. Each spec is cached
under its own deterministic key so different (op, target, params) combinations
don't clobber each other.

Design notes
------------
- Operators (`translate`, `rotate`, `scale`, `recolor`) require a `RiggedScene`
  per target object. The caller is responsible for binding (running SuperDec
  + `pipeline.rigging.bind` and supplying the resulting `RiggedScene`).
- `delete` does not need a `RiggedScene` — it operates on `(gaussians, lift)`
  directly by filtering attached Gaussians out of the means tensor.
- This stage does not orchestrate SuperDec / segmentation. It assumes
  `lift` and (for non-delete ops) `scenes_by_obj` are already available.
- Cache key: `edit_v2/<edit_name>.pt`. `edit_name` is deterministic from
  `(target_object_index, operator, params)`.
"""
from __future__ import annotations

from typing import Any

import torch

from pipeline.cache import load_or_run
from pipeline.operators import (
    apply_recolor,
    apply_rotate,
    apply_scale,
    apply_translate,
)
from pipeline.rigging import RiggedScene
from pipeline.types import EditSpec, GaussiansResult, LiftResult


def _params_to_tensors(params: dict[str, Any], dtype, device) -> dict[str, Any]:
    """Convert list-typed params to torch tensors. Scalar params pass through."""
    out: dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(v, (list, tuple)) and all(isinstance(x, (int, float)) for x in v):
            out[k] = torch.tensor(v, dtype=dtype, device=device)
        else:
            out[k] = v
    return out


def _apply_delete(
    gaussians: GaussiansResult,
    lift: LiftResult,
    target_object_index: int,
) -> GaussiansResult:
    """Remove all Gaussians with `labels == target_object_index`."""
    keep = lift.labels != target_object_index
    return GaussiansResult(
        means=gaussians.means[keep],
        covariances=gaussians.covariances[keep],
        harmonics=gaussians.harmonics[keep],
        opacities=gaussians.opacities[keep],
        scales=gaussians.scales[keep],
        rotations=gaussians.rotations[keep],
        extrinsics=gaussians.extrinsics,
        intrinsics=gaussians.intrinsics,
        image_size=gaussians.image_size,
    )


def apply_edit(
    gaussians: GaussiansResult,
    lift: LiftResult,
    spec: EditSpec,
    scene: RiggedScene | None = None,
    cache_dir: str = "outputs/cache",
) -> GaussiansResult:
    """Apply a single edit. Caches under `edit_v2/<edit_name>.pt`.

    `scene` is required for translate/rotate/scale/recolor and ignored for
    delete (which uses `lift` instead).
    """
    if spec.operator != "delete" and scene is None:
        raise ValueError(
            f"operator {spec.operator!r} requires a RiggedScene; got scene=None"
        )

    def _run() -> GaussiansResult:
        dtype = gaussians.means.dtype
        device = gaussians.means.device
        params = _params_to_tensors(spec.params, dtype, device)

        if spec.operator == "translate":
            return apply_translate(scene, gaussians, params["delta"])
        if spec.operator == "rotate":
            return apply_rotate(scene, gaussians, params["axis"], params["angle_rad"])
        if spec.operator == "scale":
            return apply_scale(scene, gaussians, params["factor"])
        if spec.operator == "recolor":
            return apply_recolor(scene, gaussians, params["mode"], params["rgb"])
        if spec.operator == "delete":
            return _apply_delete(gaussians, lift, spec.target_object_index)

        raise ValueError(f"unhandled operator: {spec.operator!r}")  # unreachable

    stage_name = f"edit_v2/{spec.edit_name()}"
    return load_or_run(stage_name, _run, cache_dir=cache_dir)


def apply_edits_v2(
    gaussians: GaussiansResult,
    lift: LiftResult,
    specs: list[EditSpec],
    scenes_by_obj: dict[int, RiggedScene] | None = None,
    cache_dir: str = "outputs/cache",
) -> dict[str, GaussiansResult]:
    """Apply each spec independently; return {edit_name: edited_gaussians}.

    Each edit is cached separately. Caller orchestrates rendering after.
    """
    scenes_by_obj = scenes_by_obj or {}
    out: dict[str, GaussiansResult] = {}
    for spec in specs:
        if spec.operator != "delete":
            scene = scenes_by_obj.get(spec.target_object_index)
            if scene is None:
                raise ValueError(
                    f"no RiggedScene for target_object_index={spec.target_object_index}"
                    f" (operator={spec.operator!r}); bind it first"
                )
        else:
            scene = None
        out[spec.edit_name()] = apply_edit(gaussians, lift, spec, scene=scene, cache_dir=cache_dir)
    return out

# pipeline/types.py
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
import torch


@dataclass
class GaussiansResult:
    """Output of Stage 1 (reconstruct). Wraps AnySplat's native Gaussians with camera info."""
    means: torch.Tensor           # [N, 3]
    covariances: torch.Tensor     # [N, 3, 3]
    harmonics: torch.Tensor       # [N, 3, d_sh] where d_sh=25 for SH degree 4
    opacities: torch.Tensor       # [N]
    scales: torch.Tensor          # [N, 3]
    rotations: torch.Tensor       # [N, 4]
    extrinsics: torch.Tensor      # [K, 4, 4] camera-to-world (c2w)
    intrinsics: torch.Tensor      # [K, 3, 3] NORMALIZED (divide by W,H for pixel coords)
    image_size: tuple[int, int]   # (H, W) = (448, 448)


@dataclass
class SegmentationResult:
    """Output of Stage 2 (segment). Per-object 2D masks across K views."""
    masks: dict[str, torch.Tensor]   # object_name -> [K, H, W] binary masks
    boxes: dict[str, torch.Tensor]   # object_name -> [K, 4] bounding boxes
    object_names: list[str]


@dataclass
class LiftResult:
    """Output of Stage 3 (lift_masks). Per-Gaussian object labels."""
    labels: torch.Tensor   # [N] int, object index per Gaussian (-1 = unassigned)
    object_names: list[str]


@dataclass
class SemanticRouterResult:
    """Output of Stage 0 (semantic_router). Objects the VLM identified for editing."""
    object_names: list[str]   # objects visible in scene that match the query (to find AND remove)


@dataclass
class CompletionResult:
    """Output of Stage 4 (complete_objects). Per-object completed Gaussian sets."""
    # Maps object index → extra Gaussians representing inferred back-side geometry.
    # These are appended to the scene before editing so deletions leave no holes.
    extra_means: dict[int, torch.Tensor]        # obj_idx -> [M, 3]
    extra_harmonics: dict[int, torch.Tensor]    # obj_idx -> [M, 3, d_sh]
    extra_opacities: dict[int, torch.Tensor]    # obj_idx -> [M]
    extra_scales: dict[int, torch.Tensor]       # obj_idx -> [M, 3]
    extra_rotations: dict[int, torch.Tensor]    # obj_idx -> [M, 4]
    extra_covariances: dict[int, torch.Tensor]  # obj_idx -> [M, 3, 3]


@dataclass
class ReasoningResult:
    """Output of Stage 4b (reason). VLM-inferred properties per object."""
    properties: dict[str, dict]  # object_name -> {"material": ..., "weight_class": ..., ...}


@dataclass
class EditResult:
    """Output of Stage 5 (edit). Modified SH coefficients and delete mask."""
    highlight_harmonics: torch.Tensor  # [N, 3, d_sh] modified SH coefficients
    delete_mask: torch.Tensor          # [N] bool, True = Gaussian removed
    query: str


@dataclass
class EditSpec:
    """Specification of one edit applied to one target object.

    Params are kept as primitive Python types (not torch tensors) so the spec
    is JSON-serializable and produces stable hashes for cache keys.

    Operator-specific params:
      translate: {"delta": [x, y, z]}
      rotate:    {"axis":  [x, y, z], "angle_rad": float}
      scale:     {"factor": float}            # isotropic only
      recolor:   {"mode": "replace"|"tint", "rgb": [r, g, b]}
      delete:    {}
    """
    target_object_index: int
    operator: str  # "translate" | "rotate" | "scale" | "recolor" | "delete"
    params: dict[str, Any] = field(default_factory=dict)

    _VALID_OPS = ("translate", "rotate", "scale", "recolor", "delete")

    def __post_init__(self):
        if self.operator not in self._VALID_OPS:
            raise ValueError(
                f"operator must be one of {self._VALID_OPS}, got {self.operator!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_object_index": int(self.target_object_index),
            "operator": str(self.operator),
            "params": self.params,
        }

    def edit_name(self) -> str:
        """Deterministic, human-readable identifier: '<op>_obj<idx>_<hash6>'.

        Used as the per-edit subdir under outputs/<scene>/ and as the cache key
        suffix. The 6-char hash distinguishes specs that share op+target but
        differ in params (e.g., translate by [0.3,0,0] vs [-0.3,0,0]).
        """
        blob = json.dumps(self.to_dict(), sort_keys=True).encode("utf-8")
        h = hashlib.sha1(blob).hexdigest()[:6]
        return f"{self.operator}_obj{self.target_object_index}_{h}"

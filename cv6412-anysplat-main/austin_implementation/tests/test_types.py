# tests/test_types.py
import torch
from pipeline.types import (
    GaussiansResult, SegmentationResult, LiftResult,
    ReasoningResult, EditResult,
)


def test_gaussians_result_construction():
    N, K, d_sh = 100, 4, 25
    result = GaussiansResult(
        means=torch.randn(N, 3),
        covariances=torch.randn(N, 3, 3),
        harmonics=torch.randn(N, 3, d_sh),
        opacities=torch.randn(N),
        scales=torch.randn(N, 3),
        rotations=torch.randn(N, 4),
        extrinsics=torch.randn(K, 4, 4),
        intrinsics=torch.randn(K, 3, 3),
        image_size=(448, 448),
    )
    assert result.means.shape == (N, 3)
    assert result.harmonics.shape == (N, 3, d_sh)
    assert result.opacities.shape == (N,)
    assert result.image_size == (448, 448)


def test_segmentation_result_construction():
    K, H, W = 4, 448, 448
    result = SegmentationResult(
        masks={"bench": torch.ones(K, H, W, dtype=torch.bool)},
        boxes={"bench": torch.tensor([[10, 10, 100, 100]] * K, dtype=torch.float)},
        object_names=["bench"],
    )
    assert "bench" in result.masks
    assert result.masks["bench"].shape == (K, H, W)


def test_lift_result_construction():
    N = 100
    result = LiftResult(
        labels=torch.randint(-1, 3, (N,)),
        object_names=["bench", "tree", "building"],
    )
    assert result.labels.shape == (N,)
    assert len(result.object_names) == 3


def test_reasoning_result_construction():
    result = ReasoningResult(
        properties={"bench": {"material": "wood", "weight_class": "heavy", "movable": False}}
    )
    assert result.properties["bench"]["material"] == "wood"


def test_edit_result_construction():
    N, d_sh = 100, 25
    result = EditResult(
        highlight_harmonics=torch.randn(N, 3, d_sh),
        delete_mask=torch.zeros(N, dtype=torch.bool),
        query="remove all wooden objects",
    )
    assert result.highlight_harmonics.shape == (N, 3, d_sh)
    assert result.delete_mask.dtype == torch.bool

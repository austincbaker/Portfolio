# tests/test_lift_masks.py
import torch
from pipeline.lift_masks import project_gaussians_to_pixels, majority_vote_labels, lift_masks_core


def test_project_gaussians_identity_camera():
    """A Gaussian at (0, 0, 5) with identity extrinsic and simple intrinsic
    should project to the image center."""
    means = torch.tensor([[0.0, 0.0, 5.0]])  # [1, 3]
    # Camera at origin looking down +Z
    extrinsic_c2w = torch.eye(4)  # c2w = identity -> camera at origin
    # Simple intrinsic: focal=224, center=224 (for 448x448 image), normalized by 448
    intrinsic_norm = torch.tensor([
        [224.0 / 448, 0.0, 224.0 / 448],
        [0.0, 224.0 / 448, 224.0 / 448],
        [0.0, 0.0, 1.0],
    ])
    H, W = 448, 448

    pixels, valid = project_gaussians_to_pixels(means, extrinsic_c2w, intrinsic_norm, H, W)
    # Should project to center (224, 224)
    assert valid[0] == True
    assert abs(pixels[0, 0].item() - 224.0) < 1.0  # u ≈ 224
    assert abs(pixels[0, 1].item() - 224.0) < 1.0  # v ≈ 224


def test_project_gaussians_behind_camera():
    """A Gaussian behind the camera should be marked invalid."""
    means = torch.tensor([[0.0, 0.0, -5.0]])  # behind camera
    extrinsic_c2w = torch.eye(4)
    intrinsic_norm = torch.tensor([
        [0.5, 0.0, 0.5],
        [0.0, 0.5, 0.5],
        [0.0, 0.0, 1.0],
    ])
    _, valid = project_gaussians_to_pixels(means, extrinsic_c2w, intrinsic_norm, 448, 448)
    assert valid[0] == False


def test_majority_vote_clear_winner():
    """When one label dominates across views, it should win."""
    # 3 views, 2 Gaussians
    # Gaussian 0: label 1 in all 3 views -> label 1
    # Gaussian 1: label 2 in 2 views, label 0 in 1 view -> label 2
    per_view_labels = torch.tensor([
        [1, 2],   # view 0
        [1, 0],   # view 1
        [1, 2],   # view 2
    ])  # [K, N]
    per_view_valid = torch.tensor([
        [True, True],
        [True, True],
        [True, True],
    ])  # [K, N]
    num_objects = 3

    labels = majority_vote_labels(per_view_labels, per_view_valid, num_objects)
    assert labels[0] == 1
    assert labels[1] == 2


def test_majority_vote_no_valid_views():
    """A Gaussian with no valid projections gets label -1."""
    per_view_labels = torch.tensor([[0], [0]])  # [2, 1]
    per_view_valid = torch.tensor([[False], [False]])  # all invalid
    labels = majority_vote_labels(per_view_labels, per_view_valid, num_objects=1)
    assert labels[0] == -1


def test_majority_vote_background_wins():
    """A Gaussian seen mostly as background should get label -1."""
    # 5 views: object 0 in 1 view, background (-1) in 4 views
    per_view_labels = torch.tensor([
        [0],    # view 0: sees object 0
        [-1],   # view 1: background
        [-1],   # view 2: background
        [-1],   # view 3: background
        [-1],   # view 4: background
    ])
    per_view_valid = torch.ones(5, 1, dtype=torch.bool)
    labels = majority_vote_labels(per_view_labels, per_view_valid, num_objects=1)
    assert labels[0] == -1  # background wins


def test_lift_masks_core_integration():
    """End-to-end test with synthetic data: 2 Gaussians, 1 view, 2 objects."""
    N = 2
    means = torch.tensor([[-1.0, 0.0, 5.0], [1.0, 0.0, 5.0]])  # 2 Gaussians

    # One view: identity camera
    extrinsics = torch.eye(4).unsqueeze(0)  # [1, 4, 4]
    intrinsics = torch.tensor([
        [0.5, 0.0, 0.5],
        [0.0, 0.5, 0.5],
        [0.0, 0.0, 1.0],
    ]).unsqueeze(0)  # [1, 3, 3]

    H, W = 448, 448

    # Create masks: object 0 covers left half, object 1 covers right half
    mask_obj0 = torch.zeros(1, H, W, dtype=torch.bool)
    mask_obj0[0, :, :W // 2] = True
    mask_obj1 = torch.zeros(1, H, W, dtype=torch.bool)
    mask_obj1[0, :, W // 2:] = True

    masks = {"left_obj": mask_obj0, "right_obj": mask_obj1}
    object_names = ["left_obj", "right_obj"]

    labels = lift_masks_core(means, extrinsics, intrinsics, masks, object_names, H, W)
    # Gaussian at (-1,0,5): u = (224*(-1) + 224*5)/5 = 179 -> left half -> object 0
    # Gaussian at (1,0,5):  u = (224*1 + 224*5)/5 = 269  -> right half -> object 1
    assert labels.shape == (N,)
    assert labels[0].item() == 0  # left_obj
    assert labels[1].item() == 1  # right_obj

# tests/test_edit.py
import torch
from pipeline.edit import apply_edits


def test_apply_edits_selects_labeled_gaussians():
    """All labeled (non-background) Gaussians should be selected for removal."""
    N, d_sh = 10, 25
    harmonics = torch.randn(N, 3, d_sh)
    labels = torch.tensor([0, 0, 1, 1, -1, 0, 1, -1, 0, 1])

    result = apply_edits(harmonics, labels)

    labeled = [0, 1, 2, 3, 5, 6, 8, 9]
    background = [4, 7]

    for i in labeled:
        assert result.delete_mask[i] == True
        assert result.highlight_harmonics[i, 0, 0] > 1.0   # red DC set
        assert result.highlight_harmonics[i, 1, 0] == 0.0  # green zeroed
        assert result.highlight_harmonics[i, 2, 0] == 0.0  # blue zeroed
        assert result.highlight_harmonics[i, 0, 1:].sum() == 0.0  # higher SH bands zeroed

    for i in background:
        assert result.delete_mask[i] == False
        assert torch.equal(result.highlight_harmonics[i], harmonics[i])


def test_apply_edits_empty_scene():
    """All-background scene: nothing should be selected."""
    N, d_sh = 5, 25
    harmonics = torch.randn(N, 3, d_sh)
    labels = torch.full((N,), -1, dtype=torch.long)

    result = apply_edits(harmonics, labels)

    assert result.delete_mask.sum() == 0
    assert torch.equal(result.highlight_harmonics, harmonics)

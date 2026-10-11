# pipeline/edit.py
"""Stage 5: Apply edits — remove all Gaussians assigned to VLM-identified objects."""
import torch

from pipeline.cache import load_or_run
from pipeline.types import GaussiansResult, LiftResult, EditResult


def apply_edits(
    harmonics: torch.Tensor,   # [N, 3, d_sh]
    labels: torch.Tensor,      # [N] int, -1 = background
) -> EditResult:
    """Select all labeled (non-background) Gaussians for removal and highlight."""
    selected = labels != -1

    highlight = harmonics.clone()
    highlight[selected] = 0
    highlight[selected, 0, 0] = 1.7   # red DC
    highlight[selected, 1, 0] = 0.0
    highlight[selected, 2, 0] = 0.0

    return EditResult(
        highlight_harmonics=highlight,
        delete_mask=selected,
        query="",
    )


def edit(
    gaussians: GaussiansResult,
    lifted: LiftResult,
    query: str,
    cache_dir: str = "outputs/cache",
) -> EditResult:
    """Stage 5 entry point. Removes all Gaussians the VLM identified in Stage 0."""
    def _run():
        print(f"[edit] Query: '{query}'")
        print(f"[edit] Objects to remove: {lifted.object_names}")

        result = apply_edits(gaussians.harmonics, lifted.labels)
        result.query = query

        selected_count = int(result.delete_mask.sum())
        total = result.delete_mask.shape[0]
        print(f"[edit] Selected {selected_count:,}/{total:,} Gaussians")
        return result

    return load_or_run("edit", _run, cache_dir=cache_dir)

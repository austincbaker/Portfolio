# tests/test_cache.py
import json
import os

import torch
from pipeline.cache import load_or_run


def test_load_or_run_pt_caches_result(tmp_path):
    cache_dir = str(tmp_path)
    call_count = 0

    def expensive_fn():
        nonlocal call_count
        call_count += 1
        return {"tensor": torch.tensor([1.0, 2.0, 3.0])}

    # First call — runs the function
    result1 = load_or_run("test_stage", expensive_fn, cache_dir=cache_dir)
    assert call_count == 1
    assert torch.equal(result1["tensor"], torch.tensor([1.0, 2.0, 3.0]))

    # Second call — loads from cache
    result2 = load_or_run("test_stage", expensive_fn, cache_dir=cache_dir)
    assert call_count == 1  # function NOT called again
    assert torch.equal(result2["tensor"], torch.tensor([1.0, 2.0, 3.0]))


def test_load_or_run_json_caches_result(tmp_path):
    cache_dir = str(tmp_path)
    call_count = 0

    def expensive_fn():
        nonlocal call_count
        call_count += 1
        return {"material": "wood", "movable": True}

    result1 = load_or_run("reasoning", expensive_fn, fmt="json", cache_dir=cache_dir)
    assert call_count == 1
    assert result1["material"] == "wood"

    result2 = load_or_run("reasoning", expensive_fn, fmt="json", cache_dir=cache_dir)
    assert call_count == 1
    assert result2["movable"] is True

    # Verify it's valid JSON on disk
    with open(os.path.join(cache_dir, "reasoning.json")) as f:
        data = json.load(f)
    assert data["material"] == "wood"


def test_load_or_run_passes_args(tmp_path):
    cache_dir = str(tmp_path)

    def add(a, b):
        return torch.tensor([a + b])

    result = load_or_run("add_stage", add, 3, 4, cache_dir=cache_dir)
    assert torch.equal(result, torch.tensor([7]))

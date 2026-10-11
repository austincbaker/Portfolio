# pipeline/cache.py
import json
import os
from typing import Any, Callable

import torch


def load_or_run(
    stage_name: str,
    fn: Callable,
    *args,
    fmt: str = "pt",
    cache_dir: str = "outputs/cache",
) -> Any:
    """Run a stage function with caching. Returns cached result if available."""
    ext = "json" if fmt == "json" else "pt"
    path = os.path.join(cache_dir, f"{stage_name}.{ext}")
    # Create the parent dir (handles nested stage names like "edit_v2/<hash>").
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        print(f"[cache] Loading cached {stage_name} from {path}")
        if fmt == "json":
            with open(path, "r") as f:
                return json.load(f)
        return torch.load(path, weights_only=False, map_location="cpu")

    print(f"[cache] Running {stage_name}...")
    result = fn(*args)

    if fmt == "json":
        with open(path, "w") as f:
            json.dump(result, f, indent=2)
    else:
        torch.save(result, path)

    print(f"[cache] Saved {stage_name} to {path}")
    return result

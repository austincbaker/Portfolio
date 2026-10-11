"""Tiny YAML config loader with a `defaults:` include and dotted CLI overrides.

Usage:
    cfg = load_config("train_model/configs/sft.yaml", overrides=["training.lr=1e-5"])
    print(cfg["training"]["lr"])   # 1e-05 (Python float)

The top-level `defaults:` key, when present, is a list of sibling YAML stems to
load and deep-merge underneath the current file. Later files in the list win.
The current file's own keys win over all defaults.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import yaml


def _deep_merge(base: Mapping, override: Mapping) -> dict:

    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], Mapping) and isinstance(v, Mapping):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _resolve_defaults(path: Path) -> dict:

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    defaults = raw.pop("defaults", None)
    if not defaults:
        return raw
    merged: dict = {}
    for name in defaults:
        sib = path.parent / f"{name}.yaml"
        merged = _deep_merge(merged, _resolve_defaults(sib))
    return _deep_merge(merged, raw)


def _coerce(value: str) -> Any:

    try:
        return yaml.safe_load(value)
    except yaml.YAMLError:
        return value


def _apply_override(cfg: dict, dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    node = cfg
    for p in parts[:-1]:
        if p not in node or not isinstance(node[p], dict):
            node[p] = {}
        node = node[p]
    node[parts[-1]] = value


def load_config(path: str | Path, overrides: list[str] | None = None) -> dict:

    cfg = _resolve_defaults(Path(path))
    for ov in overrides or []:
        if "=" not in ov:
            raise ValueError(f"override must be key=value, got: {ov!r}")
        key, _, value = ov.partition("=")
        _apply_override(cfg, key.strip(), _coerce(value.strip()))
    return cfg


def save_config(cfg: dict, path: str | Path) -> None:

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)


def dump_json(cfg: dict) -> str:

    return json.dumps(cfg, sort_keys=True, default=str)

"""
Unified Vision-Language Model Loader

A generalized loader supporting multiple VLM families with a consistent interface.

Supported Models:
- Qwen2.5-VL (Alibaba) - 3B / 7B / 72B
- InternVL3 (OpenGVLab) - 2B / 8B / 78B
- Llama 3.2 Vision (Meta) - 11B / 90B
- NVILA (NVIDIA) - 8B / 15B
- Ovis 2.5 (AIDC-AI) - 2B / 9B

Usage:
    from model_loader import create_loader, ModelConfig

    config = ModelConfig(
        model_path="Qwen/Qwen2.5-VL-72B-Instruct",
        max_new_tokens=64,
    )

    loader = create_loader(config)
    loader.load()
    response = loader.generate_response(frames, "What is happening?")

CLI shortcut usage:
    from model_loader import create_loader_from_shortcut

    loader = create_loader_from_shortcut("qwen-72b")
"""
from .base import BaseVLMLoader, ModelConfig
from .registry import (
    get_loader_class,
    list_supported_models,
    list_supported_families,
    register_model,
    resolve_model_path,
    MODEL_SHORTCUTS,
)

__all__ = [

    "BaseVLMLoader",
    "ModelConfig",

    "create_loader",
    "create_loader_from_shortcut",
    "load_model",

    "get_loader_class",
    "list_supported_models",
    "list_supported_families",
    "register_model",
    "resolve_model_path",
    "MODEL_SHORTCUTS",
]

__version__ = "0.2.0"


def create_loader(config: ModelConfig | str) -> BaseVLMLoader:

    if isinstance(config, str):
        config = ModelConfig(model_path=config)

    loader_class = get_loader_class(config.model_path)
    return loader_class(config)


def create_loader_from_shortcut(
    shortcut: str,
    **config_overrides,
) -> BaseVLMLoader:

    model_path = resolve_model_path(shortcut)
    config = ModelConfig(model_path=model_path, **config_overrides)
    return create_loader(config)


def load_model(
    model_path: str,
    dtype: str = "bfloat16",
    device: str = "cuda",
    device_map: str | None = None,
    **kwargs,
) -> BaseVLMLoader:

    resolved_path = resolve_model_path(model_path)
    config = ModelConfig(
        model_path=resolved_path,
        dtype=dtype,
        device=device,
        device_map=device_map,
        **kwargs,
    )

    loader = create_loader(config)
    loader.load()

    return loader

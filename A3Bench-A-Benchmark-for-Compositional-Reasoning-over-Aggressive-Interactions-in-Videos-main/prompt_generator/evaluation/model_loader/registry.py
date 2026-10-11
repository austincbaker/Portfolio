"""
Model registry for vision-language model loaders.

Maps model path substrings to their corresponding loader classes
and provides a shortcut system for CLI convenience.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseVLMLoader


MODEL_SHORTCUTS: dict[str, str] = {

    "qwen-7b": "Qwen/Qwen2.5-VL-7B-Instruct",

    "internvl2.5-8b": "OpenGVLab/InternVL2_5-8B",

    "ovis-9b": "AIDC-AI/Ovis2.5-9B",
    "ovis2.5-9b": "AIDC-AI/Ovis2.5-9B",
    "ovis2-8b": "AIDC-AI/Ovis2-8B",

    "llava-video-7b": "lmms-lab/LLaVA-Video-7B-Qwen2",

    "videollama-7b": "DAMO-NLP-SG/VideoLLaMA3-7B",
    "videollama3-7b": "DAMO-NLP-SG/VideoLLaMA3-7B",

    "kimi-3b": "moonshotai/Kimi-VL-A3B-Instruct",
    "kimi-3b-thinking": "moonshotai/Kimi-VL-A3B-Thinking",

    "videochat-7b": "OpenGVLab/VideoChat-Flash-Qwen2_5-7B_InternVideo2-1B",
    "oryx-7b": "THUdyh/Oryx-7B",
    "valley-7b": "bytedance-research/Valley-Eagle-7B",
    "video-r1-7b": "Video-R1/Video-R1-7B",
    "lumian-7b": "prithivMLmods/Lumian-VLR-7B-Thinking",
    "hunyuan-7b": "TencentARC/ARC-Hunyuan-Video-7B",
    "internvideo-8b": "OpenGVLab/InternVideo2_5_Chat_8B",
}


def _get_loader_registry() -> list[tuple[list[str], str, str]]:

    return [

        (["llava-video", "llava_video"],  ".llava_video",    "LLaVAVideoLoader"),
        (["videollama"],                   ".videollama",     "VideoLLaMALoader"),
        (["videochat", "oryx", "valley", "video-r1", "lumian", "hunyuan"],
                                           ".video_generic",  "GenericVideoLoader"),
        (["kimi"],                         ".kimi",           "KimiVLLoader"),
        (["internvl", "internvideo"],      ".internvl",       "InternVLLoader"),
        (["nvila"],                        ".nvila",          "NVILALoader"),
        (["ovis"],                         ".ovis",           "OvisLoader"),

        (["qwen"],                         ".qwen_vl",        "QwenVLLoader"),
        (["llama"],                        ".llama_vision",   "LlamaVisionLoader"),
    ]


def get_loader_class(model_path: str) -> type["BaseVLMLoader"]:

    model_path_lower = model_path.lower()

    for patterns, module_path, class_name in _get_loader_registry():
        if any(p in model_path_lower for p in patterns):
            import importlib
            module = importlib.import_module(module_path, package=__package__)
            return getattr(module, class_name)

    raise ValueError(
        f"No loader found for model: {model_path}\n"
        f"Supported model families: {list_supported_families()}\n"
        f"Available shortcuts: {list(MODEL_SHORTCUTS.keys())}"
    )


def resolve_model_path(model_name: str) -> str:

    return MODEL_SHORTCUTS.get(model_name) or MODEL_SHORTCUTS.get(model_name.lower(), model_name)


def list_supported_families() -> list[str]:

    families = []
    for patterns, _, _ in _get_loader_registry():
        families.extend(patterns)
    return families


def list_supported_models() -> dict[str, str]:

    return dict(MODEL_SHORTCUTS)


def register_model(shortcut: str, model_path: str) -> None:

    MODEL_SHORTCUTS[shortcut] = model_path

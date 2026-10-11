"""
Base classes for vision-language model loaders.

Defines the abstract interface that all model-specific loaders must implement.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import warnings


@dataclass
class ModelConfig:
    """
    Unified configuration for all VLM loaders.

    Model-specific parameters are handled gracefully - loaders ignore
    parameters that don't apply to their model family.
    """
    model_path: str = "AIDC-AI/Ovis2.5-9B"


    max_new_tokens: int = 64
    temperature: float = 0.0
    do_sample: bool = False


    image_size: tuple[int, int] = (448, 448)
    num_frames: int = 8


    dtype: str = "bfloat16"
    device: str = "cuda"
    device_map: str | None = None


    use_torch_compile: bool = False
    use_flash_attention: bool = True
    compile_mode: str = "reduce-overhead"
    low_cpu_mem_usage: bool = True

    \
    enable_thinking: bool = False
    thinking_budget: int = 128


    enable_batching: bool = True
    max_batch_size: int = 4

    \
    trust_remote_code: bool = True


class BaseVLMLoader(ABC):
    """
    Abstract base class for vision-language model loaders.

    All model-specific loaders must implement this interface to ensure
    consistent behavior across different model families.
    """


    MODEL_FAMILY: str = "base"

\

    EXTRA_PACKAGES: list[str] = []

    \
    UPGRADE_PACKAGES: list[str] = []

    def ensure_packages(self) -> None:

        import importlib.util
        import subprocess
        import sys

        for entry in self.EXTRA_PACKAGES:
\
\

            if isinstance(entry, tuple):
                pkg, check_name = entry
            else:
                pkg = entry
                is_git_url = pkg.startswith("git+") or pkg.startswith("http")
                check_name = None if is_git_url else pkg.split("[")[0].replace("-", "_")

            if check_name is not None:
                needs_install = importlib.util.find_spec(check_name) is None
            else:
                needs_install = True

            if needs_install:
                print(f"Installing missing package: {pkg}")
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
                except Exception as e:
                    print(f"Warning: failed to install {pkg}: {e}")

        for pkg in self.UPGRADE_PACKAGES:
            print(f"Upgrading package: {pkg}")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", pkg])
            except Exception as e:
                print(f"Warning: failed to upgrade {pkg}: {e}")

    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()
        self.model = None
        self.processor = None
        self._torch = None
        self._compiled = False

    def _get_torch(self):

        if self._torch is None:
            import torch
            self._torch = torch
        return self._torch

    def _get_dtype(self):

        torch = self._get_torch()
        dtype_map = {
            "float16": torch.float16,
            "float32": torch.float32,
            "bfloat16": torch.bfloat16,
            "auto": "auto",
        }
        return dtype_map.get(self.config.dtype, torch.bfloat16)

    def _setup_cuda_optimizations(self) -> None:

        torch = self._get_torch()

        if not torch.cuda.is_available():
            return

        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.benchmark = True

        if hasattr(torch.backends.cuda, 'enable_flash_sdp'):
            torch.backends.cuda.enable_flash_sdp(True)
        if hasattr(torch.backends.cuda, 'enable_mem_efficient_sdp'):
            torch.backends.cuda.enable_mem_efficient_sdp(True)

    def _get_attention_implementation(self) -> str:


        if not self.config.use_flash_attention:
            return "eager"

        try:
            import flash_attn
            return "flash_attention_2"
        except ImportError:
            return "sdpa"

    def _apply_torch_compile(self) -> None:

        if not self.config.use_torch_compile or self._compiled:
            return

        torch = self._get_torch()

        if not hasattr(torch, 'compile'):
            warnings.warn("torch.compile requires PyTorch 2.0+")
            return

        try:
            self.model = torch.compile(
                self.model,
                mode=self.config.compile_mode,
                fullgraph=False,
            )
            self._compiled = True
            print(f"Model compiled with mode: {self.config.compile_mode}")
        except Exception as e:
            warnings.warn(f"torch.compile failed: {e}")

    @abstractmethod
    def load(self) -> None:

        pass

    @abstractmethod
    def generate_response(
        self,
        images: list,
        prompt: str,
        **kwargs,
    ) -> str:

        pass

    def generate_responses_batch(
        self,
        images: list,
        prompts: list[str],
        **kwargs,
    ) -> list[str]:

        return [self.generate_response(images, p, **kwargs) for p in prompts]

    def warmup(self, num_frames: int = 4) -> None:

        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        torch = self._get_torch()
        from PIL import Image
        import numpy as np

        print(f"Warming up {self.MODEL_FAMILY} model...")

        dummy_images = [
            Image.fromarray(
                np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
            )
            for _ in range(num_frames)
        ]

        with torch.no_grad():
            _ = self.generate_response(dummy_images, "Describe what you see.")

        print("Warmup complete.")

    def unload(self) -> None:

        torch = self._get_torch()

        if self.model is not None:
            del self.model
            self.model = None

        if self.processor is not None:
            del self.processor
            self.processor = None

        self._compiled = False

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def get_memory_usage(self) -> dict[str, float]:

        torch = self._get_torch()

        if not torch.cuda.is_available():
            return {"error": "CUDA not available"}

        return {
            "allocated_mb": torch.cuda.memory_allocated() / 1024**2,
            "reserved_mb": torch.cuda.memory_reserved() / 1024**2,
            "max_allocated_mb": torch.cuda.max_memory_allocated() / 1024**2,
        }

    def is_loaded(self) -> bool:

        return self.model is not None

    def __repr__(self) -> str:
        status = "loaded" if self.is_loaded() else "not loaded"
        return f"{self.__class__.__name__}(model={self.config.model_path}, {status})"
"""
Loader for MiniCPM-V vision-language models (OpenBMB).

Supports:
- openbmb/MiniCPM-V-2
- openbmb/MiniCPM-o-2.6
"""
from .base import BaseVLMLoader, ModelConfig


class MiniCPMLoader(BaseVLMLoader):
    """
    Loader for MiniCPM-V multimodal models.

    Features:
    - Compact yet capable (8B parameters)
    - Vision + speech + language understanding
    - Efficient for edge deployment
    """

    MODEL_FAMILY = "minicpm"

    def __init__(self, config: ModelConfig | None = None):
        super().__init__(config)
        self.tokenizer = None

    def load(self) -> None:
        if self.model is not None:
            return

        torch = self._get_torch()
        self._setup_cuda_optimizations()

        from transformers import AutoModel, AutoTokenizer

        print(f"Loading MiniCPM model: {self.config.model_path}")

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_path,
            trust_remote_code=self.config.trust_remote_code,
        )

        load_kwargs = {
            "torch_dtype": self._get_dtype(),
            "trust_remote_code": self.config.trust_remote_code,
            "low_cpu_mem_usage": self.config.low_cpu_mem_usage,
        }

        if self.config.device_map:
            load_kwargs["device_map"] = self.config.device_map

        self.model = AutoModel.from_pretrained(
            self.config.model_path,
            **load_kwargs,
        )

        if not self.config.device_map:
            self.model = self.model.to(self.config.device)

        self.model.eval()

        print(f"MiniCPM model loaded. Memory: {self.get_memory_usage()['allocated_mb']:.0f}MB")

    def generate_response(
        self,
        images: list,
        prompt: str,
        max_new_tokens: int | None = None,
        **kwargs,
    ) -> str:
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        torch = self._get_torch()
        max_new_tokens = max_new_tokens or self.config.max_new_tokens


        messages = [{"role": "user", "content": images + [prompt]}]

        if hasattr(self.model, 'chat'):
            response = self.model.chat(
                image=None,
                msgs=messages,
                tokenizer=self.tokenizer,
                max_new_tokens=max_new_tokens,
            )
            return response

        raise NotImplementedError(
            "MiniCPM model does not have expected chat interface. "
            "This loader may need updates for your model version."
        )
"""
Loader for NVIDIA NVILA vision-language models.

Supports:
- nvidia/NVILA-8B
- nvidia/NVILA-15B
- NVILA Lite variants

NVILA uses a LLaVA-style architecture with a VILA backbone.
It relies on the model's own chat template and image processing
via AutoModel with trust_remote_code=True.
"""
from .base import BaseVLMLoader, ModelConfig


class NVILALoader(BaseVLMLoader):
    """
    Loader for NVIDIA NVILA models.

    Features:
    - Efficient video understanding with temporal compression
    - LLaVA-style architecture (vision encoder + projector + LLM)
    - Supports long video inputs
    - Uses AutoModel with trust_remote_code for NVILA-specific code
    """

    MODEL_FAMILY = "nvila"

    def __init__(self, config: ModelConfig | None = None):
        super().__init__(config)
        self.tokenizer = None

    def load(self) -> None:
        if self.model is not None:
            return

        torch = self._get_torch()
        self._setup_cuda_optimizations()

        from transformers import AutoModel, AutoTokenizer

        print(f"Loading NVILA model: {self.config.model_path}")

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_path,
            trust_remote_code=self.config.trust_remote_code,
        )

        attn_impl = self._get_attention_implementation()
        print(f"Using attention: {attn_impl}")

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

        if self.config.use_torch_compile:
            self._apply_torch_compile()

        print(
            f"NVILA model loaded. "
            f"Memory: {self.get_memory_usage()['allocated_mb']:.0f}MB"
        )

    def _build_prompt(self, images: list, prompt: str) -> str:

        image_tags = "<image>\n" * len(images)
        return f"{image_tags}{prompt}"

    def _prepare_pixel_values(self, images: list):

        torch = self._get_torch()
        from torchvision import transforms

        transform = transforms.Compose([
            transforms.Resize(self.config.image_size),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        pixel_values = []
        for img in images:
            if img.mode != "RGB":
                img = img.convert("RGB")
            pixel_values.append(transform(img))

        return torch.stack(pixel_values).to(
            self.config.device, dtype=self._get_dtype()
        )

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

        full_prompt = self._build_prompt(images, prompt)
        pixel_values = self._prepare_pixel_values(images)


        if hasattr(self.model, "chat"):
            response = self.model.chat(
                self.tokenizer,
                pixel_values,
                full_prompt,
                generation_config=dict(
                    max_new_tokens=max_new_tokens,
                    do_sample=self.config.do_sample,
                    temperature=(
                        self.config.temperature if self.config.do_sample else None
                    ),
                ),
            )
            return response

        input_ids = self.tokenizer(
            full_prompt,
            return_tensors="pt",
        ).input_ids.to(self.config.device)

        with torch.inference_mode():
            outputs = self.model.generate(
                input_ids=input_ids,
                pixel_values=pixel_values,
                max_new_tokens=max_new_tokens,
                do_sample=self.config.do_sample,
                temperature=(
                    self.config.temperature if self.config.do_sample else None
                ),
            )

        response = self.tokenizer.decode(
            outputs[0][input_ids.shape[1]:],
            skip_special_tokens=True,
        )
        return response

    def generate_responses_batch(
        self,
        images: list,
        prompts: list[str],
        **kwargs,
    ) -> list[str]:

        return [self.generate_response(images, p, **kwargs) for p in prompts]

    def unload(self) -> None:

        torch = self._get_torch()

        if self.model is not None:
            del self.model
            self.model = None

        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None

        if self.processor is not None:
            del self.processor
            self.processor = None

        self._compiled = False

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

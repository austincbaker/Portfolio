"""
Loader for Meta Llama 3.2 Vision models.

Supports:
- meta-llama/Llama-3.2-11B-Vision-Instruct
- meta-llama/Llama-3.2-90B-Vision-Instruct
"""
from .base import BaseVLMLoader, ModelConfig


class LlamaVisionLoader(BaseVLMLoader):
    """
    Loader for Llama 3.2 Vision Instruct models.

    Features:
    - Uses MllamaForConditionalGeneration from transformers
    - Native multi-image support via <|image|> tokens
    - Cross-attention vision encoder
    - Chat template via AutoProcessor
    """

    MODEL_FAMILY = "llama_vision"

    def load(self) -> None:
        if self.model is not None:
            return

        torch = self._get_torch()
        self._setup_cuda_optimizations()

        from transformers import MllamaForConditionalGeneration, AutoProcessor

        print(f"Loading Llama Vision model: {self.config.model_path}")

        self.processor = AutoProcessor.from_pretrained(
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

        if attn_impl != "sdpa":
            load_kwargs["attn_implementation"] = attn_impl

        if self.config.device_map:
            load_kwargs["device_map"] = self.config.device_map

        self.model = MllamaForConditionalGeneration.from_pretrained(
            self.config.model_path,
            **load_kwargs,
        )

        if not self.config.device_map:
            self.model = self.model.to(self.config.device)

        self.model.eval()

        if self.config.use_torch_compile:
            self._apply_torch_compile()

        print(
            f"Llama Vision model loaded. "
            f"Memory: {self.get_memory_usage()['allocated_mb']:.0f}MB"
        )

    def _prepare_messages(self, images: list, prompt: str) -> list[dict]:

        content = []
        for img in images:
            if self.config.image_size != (448, 448):
                img = img.resize(self.config.image_size)
            content.append({"type": "image"})
        content.append({"type": "text", "text": prompt})

        return [{"role": "user", "content": content}]

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

        messages = self._prepare_messages(images, prompt)


        processed_images = []
        for img in images:
            if img.mode != "RGB":
                img = img.convert("RGB")
            if self.config.image_size != (448, 448):
                img = img.resize(self.config.image_size)
            processed_images.append(img)

        input_text = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
        )

        inputs = self.processor(
            text=input_text,
            images=processed_images,
            return_tensors="pt",
        ).to(self.config.device)

        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=self.config.do_sample,
                temperature=self.config.temperature if self.config.do_sample else None,
            )


        generated_ids = output_ids[:, inputs["input_ids"].shape[1]:]
        response = self.processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]

        return response

    def generate_responses_batch(
        self,
        images: list,
        prompts: list[str],
        **kwargs,
    ) -> list[str]:

        return [self.generate_response(images, p, **kwargs) for p in prompts]

"""
Loader for Kimi-VL models (Moonshot AI).

Supports:
- Kimi-VL-A3B-Instruct
- Kimi-VL-A3B-Thinking
- Other Kimi-VL variants
"""
from .base import BaseVLMLoader, ModelConfig


class KimiVLLoader(BaseVLMLoader):
    """
    Loader for Kimi-VL models from Moonshot AI.

    Kimi-VL supports both standard inference and thinking/reasoning modes.
    """

    MODEL_FAMILY = "kimi"
    EXTRA_PACKAGES = ["tiktoken"]


    def load(self) -> None:
        if self.model is not None:
            return

        torch = self._get_torch()
        self._setup_cuda_optimizations()

        from transformers import AutoModelForCausalLM, AutoProcessor

        print(f"Loading Kimi-VL model: {self.config.model_path}")


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
            "attn_implementation": attn_impl,
        }

        if self.config.device_map:
            load_kwargs["device_map"] = self.config.device_map

        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_path,
            **load_kwargs,
        )

        if not self.config.device_map:
            self.model = self.model.to(self.config.device)

        self.model.eval()

        if self.config.use_torch_compile:
            self._apply_torch_compile()

        print(f"Kimi-VL loaded. Memory: {self.get_memory_usage()['allocated_mb']:.0f}MB")

    def generate_response(
        self,
        images: list,
        prompt: str,
        max_new_tokens: int | None = None,
        enable_thinking: bool | None = None,
        **kwargs,
    ) -> str:
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        torch = self._get_torch()
        max_new_tokens = max_new_tokens or self.config.max_new_tokens
        enable_thinking = enable_thinking if enable_thinking is not None else self.config.enable_thinking


        messages = [
            {
                "role": "user",
                "content": [
                    *[{"type": "image", "image": img} for img in images],
                    {"type": "text", "text": prompt},
                ],
            }
        ]


        inputs = self.processor(
            messages=messages,
            return_tensors="pt",
        ).to(self.config.device)


        gen_kwargs = {
            "max_new_tokens": max_new_tokens,
            "do_sample": self.config.do_sample,
            "temperature": self.config.temperature,
            "use_cache": True,
            **kwargs,
        }


        if enable_thinking and "thinking" in self.config.model_path.lower():
            gen_kwargs["enable_thinking"] = True
            if self.config.thinking_budget > 0:
                gen_kwargs["thinking_budget"] = self.config.thinking_budget


        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs,
                **gen_kwargs,
            )


        generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
        response = self.processor.decode(
            generated_ids,
            skip_special_tokens=True,
        ).strip()

        return response

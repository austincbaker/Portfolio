"""
Loader for Phi Vision models (Microsoft).

Supports:
- microsoft/Phi-3.5-vision-instruct
- microsoft/Phi-4-vision (when released)
"""
from .base import BaseVLMLoader, ModelConfig


class PhiVisionLoader(BaseVLMLoader):
    """
    Loader for Microsoft Phi Vision models.

    Features:
    - Compact and efficient
    - Strong reasoning capabilities
    - Good for edge deployment
    """

    MODEL_FAMILY = "phi_vision"

    def load(self) -> None:
        if self.model is not None:
            return

        torch = self._get_torch()
        self._setup_cuda_optimizations()

        from transformers import AutoModelForCausalLM, AutoProcessor

        print(f"Loading Phi Vision model: {self.config.model_path}")

        self.processor = AutoProcessor.from_pretrained(
            self.config.model_path,
            trust_remote_code=self.config.trust_remote_code,
        )

        attn_impl = self._get_attention_implementation()

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

        print(f"Phi Vision loaded. Memory: {self.get_memory_usage()['allocated_mb']:.0f}MB")

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


        image_placeholders = "".join([f"<|image_{i+1}|>" for i in range(len(images))])
        full_prompt = f"{image_placeholders}\n{prompt}"

        messages = [{"role": "user", "content": full_prompt}]

        text = self.processor.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.processor(
            text=text,
            images=images,
            return_tensors="pt",
        ).to(self.config.device)

        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=self.config.do_sample,
                eos_token_id=self.processor.tokenizer.eos_token_id,
            )

        response = self.processor.decode(
            outputs[0][inputs.input_ids.shape[1]:],
            skip_special_tokens=True,
        )
        return response
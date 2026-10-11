"""
Generic loader for video models that follow standard transformers interface.

This loader can handle models like:
- VideoChat-Flash
- Oryx
- Valley
- Video-R1
- Lumian-VLR
- ARC-Hunyuan-Video
- Other models following standard AutoModel patterns
"""
from .base import BaseVLMLoader, ModelConfig


class GenericVideoLoader(BaseVLMLoader):
    """
    Generic loader for video VLMs using standard transformers interface.

    This loader works with models that support:
    - AutoModelForCausalLM/AutoModelForVision2Seq
    - AutoProcessor or AutoTokenizer
    - Standard generate() interface
    """

    MODEL_FAMILY = "generic_video"
    EXTRA_PACKAGES = ["flash_attn"]

    def load(self) -> None:
        if self.model is not None:
            return

        torch = self._get_torch()
        self._setup_cuda_optimizations()

        from transformers import (
            AutoModelForCausalLM,
            AutoProcessor,
            AutoTokenizer,
        )

        print(f"Loading video model: {self.config.model_path}")


        try:
            self.processor = AutoProcessor.from_pretrained(
                self.config.model_path,
                trust_remote_code=self.config.trust_remote_code,
            )
            print("Loaded AutoProcessor")
        except Exception as e:
            print(f"AutoProcessor failed ({e}), trying AutoTokenizer...")
            self.processor = AutoTokenizer.from_pretrained(
                self.config.model_path,
                trust_remote_code=self.config.trust_remote_code,
            )
            print("Loaded AutoTokenizer")


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


        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config.model_path,
                **load_kwargs,
            )
        except Exception as e:
            print(f"AutoModelForCausalLM failed ({e}), trying AutoModel...")
            from transformers import AutoModel
            self.model = AutoModel.from_pretrained(
                self.config.model_path,
                **load_kwargs,
            )

        if not self.config.device_map:
            self.model = self.model.to(self.config.device)

        self.model.eval()

        if self.config.use_torch_compile:
            self._apply_torch_compile()

        print(f"Model loaded. Memory: {self.get_memory_usage()['allocated_mb']:.0f}MB")

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


        response = None


        try:
            inputs = self.processor(
                text=prompt,
                images=images,
                return_tensors="pt",
            ).to(self.config.device)

            with torch.inference_mode():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=self.config.do_sample,
                    temperature=self.config.temperature,
                    use_cache=True,
                    **kwargs,
                )


            if hasattr(self.processor, 'batch_decode'):
                response = self.processor.batch_decode(
                    output_ids,
                    skip_special_tokens=True,
                )[0].strip()
            else:
                generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
                response = self.processor.decode(
                    generated_ids,
                    skip_special_tokens=True,
                ).strip()

            return response

        except Exception as e1:
            print(f"Method 1 failed: {e1}")


        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image"} for _ in images
                    ] + [{"type": "text", "text": prompt}],
                }
            ]

            if hasattr(self.processor, 'apply_chat_template'):
                text_prompt = self.processor.apply_chat_template(
                    messages,
                    add_generation_prompt=True,
                )
                inputs = self.processor(
                    text=text_prompt,
                    images=images,
                    return_tensors="pt",
                ).to(self.config.device)
            else:
                inputs = self.processor(
                    messages=messages,
                    return_tensors="pt",
                ).to(self.config.device)

            with torch.inference_mode():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=self.config.do_sample,
                    temperature=self.config.temperature,
                    **kwargs,
                )

            generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
            response = self.processor.decode(
                generated_ids,
                skip_special_tokens=True,
            ).strip()

            return response

        except Exception as e2:
            print(f"Method 2 failed: {e2}")

        try:
            if hasattr(self.model, 'chat'):
                response = self.model.chat(
                    images=images,
                    prompt=prompt,
                    max_new_tokens=max_new_tokens,
                    **kwargs,
                )
                return response
        except Exception as e3:
            print(f"Method 3 failed: {e3}")

        raise RuntimeError(
            "Could not generate response. Model may require custom loader implementation. "
            f"Please check the model's documentation at https://huggingface.co/{self.config.model_path}"
        )

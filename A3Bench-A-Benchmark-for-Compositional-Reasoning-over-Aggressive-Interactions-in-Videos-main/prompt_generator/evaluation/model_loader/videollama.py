"""
Loader for VideoLLaMA models.

Supports:
- VideoLLaMA3-7B
- Other VideoLLaMA variants
"""
from .base import BaseVLMLoader, ModelConfig


class VideoLLaMALoader(BaseVLMLoader):
    """
    Loader for VideoLLaMA models.

    VideoLLaMA specializes in long-form video understanding with
    efficient temporal modeling.
    """

    MODEL_FAMILY = "videollama"
    EXTRA_PACKAGES = ["ffmpeg", "bitsandbytes"]
    UPGRADE_PACKAGES = []

    @staticmethod
    def _ensure_video_utils() -> None:

        import sys
        import types
        import transformers

        if not hasattr(transformers, "video_utils"):
            mod = types.ModuleType("transformers.video_utils")

            mod.VideoInput = list  # type: ignore[attr-defined]
            transformers.video_utils = mod
            sys.modules["transformers.video_utils"] = mod

    def load(self) -> None:
        if self.model is not None:
            return


        self._ensure_video_utils()


        import os
        os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

        torch = self._get_torch()
        self._setup_cuda_optimizations()

        from transformers import AutoModelForCausalLM, AutoTokenizer

        print(f"Loading VideoLLaMA model: {self.config.model_path}")


        self.processor = AutoTokenizer.from_pretrained(
            self.config.model_path,
            trust_remote_code=self.config.trust_remote_code,
        )


        attn_impl = self._get_attention_implementation()
        print(f"Using attention: {attn_impl}")


        quantize = self.config.num_frames > 0
        load_kwargs = {
            "torch_dtype": self._get_dtype(),
            "trust_remote_code": self.config.trust_remote_code,
            "low_cpu_mem_usage": self.config.low_cpu_mem_usage,
            "attn_implementation": attn_impl,
        }
        if quantize:
            from transformers import BitsAndBytesConfig
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=self._get_dtype(),
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
            load_kwargs["device_map"] = self.config.device_map or "auto"
        elif self.config.device_map:
            load_kwargs["device_map"] = self.config.device_map

        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_path,
            **load_kwargs,
        )

        if not self.config.device_map and not quantize:
            self.model = self.model.to(self.config.device)

        self.model.eval()

        if self.config.use_torch_compile:
            self._apply_torch_compile()

        print(f"VideoLLaMA loaded. Memory: {self.get_memory_usage()['allocated_mb']:.0f}MB")

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


        try:

            if hasattr(self.model, 'generate_from_video'):
                response = self.model.generate_from_video(
                    frames=images,
                    prompt=prompt,
                    max_new_tokens=max_new_tokens,
                    **kwargs,
                )
                return response
        except Exception:
            pass

        from transformers import AutoProcessor

        if not hasattr(self, '_image_processor'):
            self._image_processor = AutoProcessor.from_pretrained(
                self.config.model_path,
                trust_remote_code=True,
            )


        if not images:
            messages = [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ]
            tmpl_fn = getattr(self._image_processor, "apply_chat_template", None) or\
                      getattr(self.processor, "apply_chat_template", None)
            if tmpl_fn is not None:
                text = tmpl_fn(messages, tokenize=False, add_generation_prompt=True)
            else:
                text = prompt
            inputs = self._image_processor(
                text=text, images=None, return_tensors="pt",
            ).to(self.config.device)
            with torch.inference_mode():
                output_ids = self.model.generate(
                    **inputs, max_new_tokens=max_new_tokens,
                    do_sample=self.config.do_sample,
                    temperature=self.config.temperature,
                )
            return self.processor.decode(output_ids[0], skip_special_tokens=True).strip()


        messages = [
            {
                "role": "user",
                "content": [{"type": "image"}] * len(images) + [{"type": "text", "text": prompt}],
            }
        ]


        image_token = getattr(self._image_processor, "image_token", "<image>")
        tmpl_fn = getattr(self._image_processor, "apply_chat_template", None) or\
                  getattr(self.processor, "apply_chat_template", None)
        if tmpl_fn is not None:
            try:
                text = tmpl_fn(messages, tokenize=False, add_generation_prompt=True,
                               image_token=image_token)
            except TypeError:
                # Some versions don't accept image_token kwarg
                text = tmpl_fn(messages, tokenize=False, add_generation_prompt=True)
        else:
            text = (image_token + "\n") * len(images) + prompt

        resized = [img.resize((448, 448)) if img.size != (448, 448) else img for img in images]

        inputs = self._image_processor(
            text=text,
            images=resized,
            return_tensors="pt",
        ).to(self.config.device)

        model_dtype = next(self.model.parameters()).dtype
        inputs = {
            k: v.to(model_dtype) if (hasattr(v, "is_floating_point") and v.is_floating_point()) else v
            for k, v in inputs.items()
        }

        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=self.config.do_sample,
                temperature=self.config.temperature,
                **kwargs,
            )


        response = self.processor.decode(output_ids[0], skip_special_tokens=True).strip()

        return response

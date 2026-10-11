"""
Loader for Ovis vision-language models (AIDC-AI).

Supports:
- AIDC-AI/Ovis2.5-2B
- AIDC-AI/Ovis2.5-9B
- AIDC-AI/Ovis2.5-14B
- And other Ovis variants
"""
from .base import BaseVLMLoader, ModelConfig


class OvisLoader(BaseVLMLoader):
    """
    Loader for Ovis 2.5 vision-language models.

    Ovis models have a unique API with:
    - model.preprocess_inputs() for message formatting
    - model.text_tokenizer for decoding
    - Optional thinking/reasoning mode
    """

    MODEL_FAMILY = "ovis"

    def _get_attention_implementation(self) -> str:

        if not self.config.use_flash_attention:
            return "eager"

        try:
            import flash_attn
            return "flash_attention_2"
        except ImportError:
            print("Ovis requires Flash Attention 2 or 'eager' mode. Falling back to eager.")
            return "eager"

    def load(self) -> None:
        if self.model is not None:
            return

        torch = self._get_torch()
        self._setup_cuda_optimizations()

        from transformers import AutoModelForCausalLM, AutoProcessor

        print(f"Loading Ovis model: {self.config.model_path}")




        self.processor = None

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

        self.model.config.output_hidden_states = False
        self.model.config.output_attentions = False
        self.model.config.use_cache = True

        if self.config.use_torch_compile:
            self._apply_torch_compile()

        print(f"Ovis model loaded. Memory: {self.get_memory_usage()['allocated_mb']:.0f}MB")

    def generate_response(
        self,
        images: list,
        prompt: str,
        max_new_tokens: int | None = None,
        thinking_budget: int | None = None,
        **kwargs,
    ) -> str:
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        torch = self._get_torch()


        max_new_tokens = max_new_tokens or self.config.max_new_tokens
        thinking_budget = thinking_budget or self.config.thinking_budget


        if not images:
            content = [{"type": "text", "text": prompt}]
        else:

            resized = [img.resize(self.config.image_size) for img in images]
            content = [{"type": "image", "image": img} for img in resized]
            content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]


        enable_thinking = self.config.enable_thinking
        enable_thinking_budget = self.config.enable_thinking


        if max_new_tokens < 64:
            enable_thinking = False
            enable_thinking_budget = False
            thinking_budget = 0

        input_ids, pixel_values, grid_thws = self.model.preprocess_inputs(
            messages=messages,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
        )

        input_ids = input_ids.to(self.config.device)
        if pixel_values is not None and pixel_values.numel() > 0:
            pixel_values = pixel_values.half().to(self.config.device)
        else:
            pixel_values = None
        if grid_thws is not None and grid_thws.numel() > 0:
            grid_thws = grid_thws.to(self.config.device)
        else:
            grid_thws = None


        with torch.cuda.amp.autocast(dtype=self._get_dtype()):
            outputs = self.model.generate(
                inputs=input_ids,
                pixel_values=pixel_values,
                grid_thws=grid_thws,
                enable_thinking=enable_thinking,
                enable_thinking_budget=enable_thinking_budget,
                max_new_tokens=max_new_tokens,
                thinking_budget=thinking_budget,
                output_attentions=False,
                output_hidden_states=False,
            )


        response = self.model.text_tokenizer.decode(
            outputs[0], skip_special_tokens=True
        )
        return response

    def generate_responses_batch(
        self,
        images: list,
        prompts: list[str],
        **kwargs,
    ) -> list[str]:

        if not self.config.enable_batching:
            return [self.generate_response(images, p, **kwargs) for p in prompts]

        torch = self._get_torch()
        resized = [img.resize(self.config.image_size) for img in images]

        responses = []
        content_base = [{"type": "image", "image": img} for img in resized]

        for prompt in prompts:
            content = content_base.copy()
            content.append({"type": "text", "text": prompt})
            messages = [{"role": "user", "content": content}]

            enable_thinking = self.config.enable_thinking

            input_ids, pixel_values, grid_thws = self.model.preprocess_inputs(
                messages=messages,
                add_generation_prompt=True,
                enable_thinking=enable_thinking,
            )

            input_ids = input_ids.to(self.config.device)
            pixel_values = pixel_values.half().to(self.config.device)
            grid_thws = grid_thws.to(self.config.device)

            with torch.cuda.amp.autocast(dtype=self._get_dtype()):
                outputs = self.model.generate(
                    inputs=input_ids,
                    pixel_values=pixel_values,
                    grid_thws=grid_thws,
                    enable_thinking=enable_thinking,
                    enable_thinking_budget=self.config.enable_thinking,
                    max_new_tokens=self.config.max_new_tokens,
                    thinking_budget=self.config.thinking_budget,
                    output_attentions=False,
                    output_hidden_states=False,
                )

            response = self.model.text_tokenizer.decode(
                outputs[0], skip_special_tokens=True
            )
            responses.append(response)

        return responses
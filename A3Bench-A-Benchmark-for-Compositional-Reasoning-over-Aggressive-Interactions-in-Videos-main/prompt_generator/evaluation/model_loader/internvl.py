"""
Loader for InternVL vision-language models (OpenGVLab/Shanghai AI Lab).

Supports:
- OpenGVLab/InternVL2.5-1B through 78B
- OpenGVLab/InternVL3-1B through 78B
"""
from .base import BaseVLMLoader, ModelConfig


class InternVLLoader(BaseVLMLoader):
    """
    Loader for InternVL2.5 and InternVL3 models.

    Features:
    - Large 6B vision encoder (InternViT)
    - Strong multimodal reasoning
    - Variable Visual Position Encoding (V2PE)
    - Good video understanding (MVBench, MLVU)
    """

    MODEL_FAMILY = "internvl"

    def __init__(self, config: ModelConfig | None = None):
        super().__init__(config)
        self.tokenizer = None
        self._generation_config = None

    def load(self) -> None:
        if self.model is not None:
            return

        torch = self._get_torch()
        self._setup_cuda_optimizations()

        from transformers import AutoModel, AutoTokenizer

        print(f"Loading InternVL model: {self.config.model_path}")

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




\



\





        is_awq_model = "awq" in self.config.model_path.lower()
        if is_awq_model:
            from transformers import AutoConfig
            model_config = AutoConfig.from_pretrained(
                self.config.model_path,
                trust_remote_code=self.config.trust_remote_code,
            )
            model_config.quantization_config = {
                "quant_method": "awq",
                "bits": 4,
                "group_size": 128,
                "zero_point": True,
                "version": "gemm",
                "modules_to_not_convert": ["vision_model", "mlp1", "lm_head"],
            }
            load_kwargs["config"] = model_config
            load_kwargs["torch_dtype"] = torch.float16
            load_kwargs["device_map"] = self.config.device_map or "auto"

        if self.config.device_map and "device_map" not in load_kwargs:
            load_kwargs["device_map"] = self.config.device_map

        self.model = AutoModel.from_pretrained(
            self.config.model_path,
            **load_kwargs,
        )

        if not self.config.device_map:
            self.model = self.model.to(self.config.device)

        self.model.eval()


        if hasattr(self.model, 'generation_config'):
            self._generation_config = self.model.generation_config

        if self.config.use_torch_compile:
            self._apply_torch_compile()

        print(f"InternVL model loaded. Memory: {self.get_memory_usage()['allocated_mb']:.0f}MB")

    def _load_images(self, images: list) -> "torch.Tensor":

        torch = self._get_torch()
        from torchvision import transforms


        transform = transforms.Compose([
            transforms.Resize((448, 448)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])

        pixel_values = []
        for img in images:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            pixel_values.append(transform(img))

        target_device = self.model.device if self.config.device_map or "awq" in self.config.model_path.lower() else self.config.device
        target_dtype = next(self.model.parameters()).dtype
        return torch.stack(pixel_values).to(target_device, dtype=target_dtype)

    def _build_prompt(self, prompt: str, num_images: int) -> str:


        image_tags = "<image>\n" * num_images
        return f"{image_tags}{prompt}"

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


        if not images:
            if hasattr(self.model, 'chat'):
                response = self.model.chat(
                    self.tokenizer,
                    None,
                    prompt,
                    generation_config=dict(
                        max_new_tokens=max_new_tokens,
                        do_sample=self.config.do_sample,
                        temperature=self.config.temperature if self.config.do_sample else None,
                    ),
                )
                return response
            if hasattr(self.tokenizer, "apply_chat_template"):
                messages = [{"role": "user", "content": prompt}]
                text_prompt = self.tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True,
                )
            else:
                text_prompt = prompt
            input_ids = self.tokenizer(
                text_prompt, return_tensors="pt",
            ).input_ids.to(self.config.device)
            with torch.inference_mode():
                outputs = self.model.generate(
                    input_ids=input_ids,
                    max_new_tokens=max_new_tokens,
                    do_sample=self.config.do_sample,
                    temperature=self.config.temperature if self.config.do_sample else None,
                )
            return self.tokenizer.decode(
                outputs[0][input_ids.shape[1]:], skip_special_tokens=True,
            )


        pixel_values = self._load_images(images)


        full_prompt = self._build_prompt(prompt, len(images))


        if hasattr(self.model, 'chat'):
            response = self.model.chat(
                self.tokenizer,
                pixel_values,
                full_prompt,
                generation_config=dict(
                    max_new_tokens=max_new_tokens,
                    do_sample=self.config.do_sample,
                    temperature=self.config.temperature if self.config.do_sample else None,
                ),
                num_patches_list=[1] * len(images),
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
                temperature=self.config.temperature if self.config.do_sample else None,
            )

        response = self.tokenizer.decode(
            outputs[0][input_ids.shape[1]:],
            skip_special_tokens=True,
        )
        return response

    def generate_response_multi_turn(
        self,
        images: list,
        conversation: list[dict],
        max_new_tokens: int | None = None,
        **kwargs,
    ) -> str:

        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        torch = self._get_torch()
        max_new_tokens = max_new_tokens or self.config.max_new_tokens

        pixel_values = self._load_images(images)


        prompt_parts = []
        for turn in conversation:
            role = turn["role"]
            content = turn["content"]
            if role == "user":
                prompt_parts.append(f"User: {content}")
            else:
                prompt_parts.append(f"Assistant: {content}")


        image_tags = "<image>\n" * len(images)
        full_prompt = image_tags + "\n".join(prompt_parts) + "\nAssistant:"

        if hasattr(self.model, 'chat'):
            response = self.model.chat(
                self.tokenizer,
                pixel_values,
                full_prompt,
                generation_config=dict(max_new_tokens=max_new_tokens),
            )
            return response

        input_ids = self.tokenizer(full_prompt, return_tensors="pt").input_ids.to(self.config.device)

        with torch.inference_mode():
            outputs = self.model.generate(
                input_ids=input_ids,
                pixel_values=pixel_values,
                max_new_tokens=max_new_tokens,
            )

        return self.tokenizer.decode(outputs[0][input_ids.shape[1]:], skip_special_tokens=True)
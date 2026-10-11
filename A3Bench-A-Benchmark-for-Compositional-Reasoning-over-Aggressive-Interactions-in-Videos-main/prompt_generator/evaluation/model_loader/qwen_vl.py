"""
Loader for Qwen vision-language models (Alibaba).

Supports:
- Qwen/Qwen2.5-VL-3B-Instruct
- Qwen/Qwen2.5-VL-7B-Instruct
- Qwen/Qwen2.5-VL-72B-Instruct
- Qwen3-VL variants (when released)
"""
from .base import BaseVLMLoader, ModelConfig


class QwenVLLoader(BaseVLMLoader):
    """
    Loader for Qwen2.5-VL and Qwen3-VL models.

    Features:
    - Native video understanding with dynamic FPS
    - Event localization (temporal grounding)
    - Strong OCR and document understanding
    - Uses qwen_vl_utils for preprocessing
    """

    MODEL_FAMILY = "qwen_vl"
    EXTRA_PACKAGES = ["qwen-vl-utils[decord]"]

    def __init__(self, config: ModelConfig | None = None):
        super().__init__(config)
        self._process_vision_info = None

    def load(self) -> None:
        if self.model is not None:
            return

        torch = self._get_torch()
        self._setup_cuda_optimizations()


\


        from transformers import AutoProcessor
        model_path_lower = self.config.model_path.lower()
        if "qwen3-vl" in model_path_lower:
            from transformers import Qwen3VLForConditionalGeneration as ModelClass
        elif "qwen2.5-vl" in model_path_lower or "qwen2_5-vl" in model_path_lower:
            from transformers import Qwen2_5_VLForConditionalGeneration as ModelClass
        elif "qwen2-vl" in model_path_lower:
            from transformers import Qwen2VLForConditionalGeneration as ModelClass
        else:
            \
            from transformers import Qwen2_5_VLForConditionalGeneration as ModelClass

        print(f"Loading Qwen VL model: {self.config.model_path}")


        try:
            from qwen_vl_utils import process_vision_info
            self._process_vision_info = process_vision_info
        except ImportError:
            self._process_vision_info = None

        processor_kwargs = {
            "trust_remote_code": self.config.trust_remote_code,
            "min_pixels": 256 * 28 * 28,
            "max_pixels": 768 * 28 * 28,
        }
        print(f"Qwen visual token limits: min_pixels={processor_kwargs['min_pixels']}, max_pixels={processor_kwargs['max_pixels']}")

        self.processor = AutoProcessor.from_pretrained(
            self.config.model_path,
            **processor_kwargs,
        )

        self.processor.tokenizer.padding_side = "left"

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

        self.model = ModelClass.from_pretrained(
            self.config.model_path,
            **load_kwargs,
        )

        if not self.config.device_map:
            self.model = self.model.to(self.config.device)

        if self.config.use_torch_compile:
            self._apply_torch_compile()

        print(f"Qwen VL model loaded. Memory: {self.get_memory_usage()['allocated_mb']:.0f}MB")

    def _prepare_messages(self, images: list | None, prompt: str) -> list[dict]:

        content = []


        for img in (images or []):

            if self.config.image_size != (448, 448):
                img = img.resize(self.config.image_size)
            content.append({"type": "image", "image": img})


        content.append({"type": "text", "text": prompt})

        return [{"role": "user", "content": content}]

    def _prepare_messages_video_path(self, video_path: str, prompt: str) -> list[dict]:

        content = [
            {"type": "video", "video": video_path},
            {"type": "text", "text": prompt},
        ]
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


        text = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )


        if self._process_vision_info:
            image_inputs, video_inputs = self._process_vision_info(messages)
        else:
            image_inputs = images
            video_inputs = None


        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        target_device = self.model.device if self.config.device_map else self.config.device
        inputs = inputs.to(target_device)


        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=self.config.do_sample,
                temperature=self.config.temperature if self.config.do_sample else None,
            )


        generated_ids = output_ids[:, inputs.input_ids.shape[1]:]
        response = self.processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]

        return response

    def generate_response_from_video(
        self,
        video_path: str,
        prompt: str,
        max_new_tokens: int | None = None,
        **kwargs,
    ) -> str:

        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        if self._process_vision_info is None:
            raise RuntimeError("qwen_vl_utils required for video path processing")

        torch = self._get_torch()
        max_new_tokens = max_new_tokens or self.config.max_new_tokens

        messages = self._prepare_messages_video_path(video_path, prompt)

        text = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        image_inputs, video_inputs = self._process_vision_info(messages)

        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to(self.config.device)

        with torch.inference_mode():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=self.config.do_sample,
            )

        generated_ids = output_ids[:, inputs.input_ids.shape[1]:]
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

        if not self.config.enable_batching or len(prompts) == 1:
            return [self.generate_response(images, p, **kwargs) for p in prompts]

        torch = self._get_torch()
        max_new_tokens = kwargs.get("max_new_tokens", self.config.max_new_tokens)


        all_messages = [self._prepare_messages(images, p) for p in prompts]


        texts = [
            self.processor.apply_chat_template(m, tokenize=False, add_generation_prompt=True)
            for m in all_messages
        ]


        if self._process_vision_info:
            image_inputs, video_inputs = self._process_vision_info(all_messages[0])
        else:
            image_inputs = images
            video_inputs = None

        responses = []


        for i in range(0, len(texts), self.config.max_batch_size):
            batch_texts = texts[i:i + self.config.max_batch_size]

            inputs = self.processor(
                text=batch_texts,
                images=[image_inputs] * len(batch_texts),
                videos=[video_inputs] * len(batch_texts) if video_inputs else None,
                padding=True,
                return_tensors="pt",
            )
            inputs = inputs.to(self.config.device)

            with torch.inference_mode():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=self.config.do_sample,
                )

            for j, output in enumerate(output_ids):
                generated = output[inputs.input_ids.shape[1]:]
                response = self.processor.decode(
                    generated,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False,
                )
                responses.append(response)

        return responses
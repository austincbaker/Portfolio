#!/usr/bin/env python3
"""
Example usage of the unified model loader.

This script demonstrates how to:
1. Use the factory function to auto-detect models
2. Compare different VLM families on the same task
3. Use model-specific features
"""
from pathlib import Path


def basic_usage():

    from model_loader import create_loader, ModelConfig


    loader = create_loader("Qwen/Qwen2.5-VL-7B-Instruct")


    config = ModelConfig(
        model_path="Qwen/Qwen2.5-VL-7B-Instruct",
        max_new_tokens=64,
        dtype="bfloat16",
        device="cuda",
    )
    loader = create_loader(config)


    loader.load()


    from PIL import Image
    frames = [Image.new("RGB", (224, 224), color="red") for _ in range(4)]
    response = loader.generate_response(frames, "What is shown in these frames?")
    print(f"Response: {response}")


    loader.unload()


def convenience_function():

    from model_loader import load_model


    loader = load_model(
        "Qwen/Qwen2.5-VL-7B-Instruct",
        dtype="bfloat16",
        max_new_tokens=128,
    )

    print(f"Loaded: {loader}")
    print(f"Memory: {loader.get_memory_usage()}")

    loader.unload()


def compare_models():

    from model_loader import create_loader, ModelConfig
    from PIL import Image
    import time

    models_to_test = [
        "AIDC-AI/Ovis2.5-2B",
        "Qwen/Qwen2.5-VL-7B-Instruct",
        "OpenGVLab/InternVL3-8B",
    ]


    frames = [Image.new("RGB", (224, 224), color="blue") for _ in range(8)]
    prompt = "Describe what you see in these video frames."

    results = {}

    for model_path in models_to_test:
        print(f"\n{'='*60}")
        print(f"Testing: {model_path}")
        print(f"{'='*60}")

        try:
            config = ModelConfig(
                model_path=model_path,
                max_new_tokens=64,
                dtype="bfloat16",
            )

            loader = create_loader(config)
            loader.load()


            loader.warmup()


            start = time.time()
            response = loader.generate_response(frames, prompt)
            elapsed = time.time() - start

            results[model_path] = {
                "response": response,
                "time_seconds": elapsed,
                "memory_mb": loader.get_memory_usage()["allocated_mb"],
            }

            print(f"Response: {response[:100]}...")
            print(f"Time: {elapsed:.2f}s")
            print(f"Memory: {results[model_path]['memory_mb']:.0f}MB")

            loader.unload()

        except Exception as e:
            print(f"Failed: {e}")
            results[model_path] = {"error": str(e)}

    return results


def multi_gpu_usage():

    from model_loader import create_loader, ModelConfig

    config = ModelConfig(
        model_path="Qwen/Qwen2.5-VL-72B-Instruct",
        device_map="auto",
        dtype="bfloat16",
        max_new_tokens=128,
    )

    loader = create_loader(config)
    loader.load()

    print(f"Model distributed across GPUs")

    loader.unload()


def qwen_video_path():

    from model_loader import create_loader, ModelConfig

    config = ModelConfig(
        model_path="Qwen/Qwen2.5-VL-7B-Instruct",
        max_new_tokens=256,
    )

    loader = create_loader(config)
    loader.load()


    if hasattr(loader, 'generate_response_from_video'):
        response = loader.generate_response_from_video(
            "/path/to/video.mp4",
            "Describe the action in this video.",
        )
        print(response)

    loader.unload()


def list_available_models():

    from model_loader import list_supported_models, get_recommended_model

    print("Supported model patterns:")
    for info in list_supported_models():
        print(f"  - {info['pattern']} -> {info['class']}")

    print("\nRecommended models:")
    for task in ["video", "document", "reasoning", "edge"]:
        print(f"\n{task.upper()}:")
        try:
            for size in ["tiny", "small", "medium", "large"]:
                try:
                    model = get_recommended_model(task, size)
                    print(f"  {size}: {model}")
                except ValueError:
                    pass
        except Exception:
            pass


def register_custom_model():

    from model_loader import register_model, create_loader
    from model_loader.base import BaseVLMLoader, ModelConfig


    class MyCustomLoader(BaseVLMLoader):
        MODEL_FAMILY = "custom"

        def load(self):
            print("Loading custom model...")


        def generate_response(self, images, prompt, **kwargs):
            return "Custom response"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python example_usage.py <example>")
        print("\nExamples:")
        print("  basic       - Basic usage with auto-detection")
        print("  convenience - One-liner loading")
        print("  compare     - Compare multiple models")
        print("  list        - List supported models")
        print("  multigpu    - Multi-GPU usage")
        sys.exit(1)

    example = sys.argv[1]

    if example == "basic":
        basic_usage()
    elif example == "convenience":
        convenience_function()
    elif example == "compare":
        compare_models()
    elif example == "list":
        list_available_models()
    elif example == "multigpu":
        multi_gpu_usage()
    else:
        print(f"Unknown example: {example}")
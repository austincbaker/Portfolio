# pipeline/semantic_router.py
"""Stage 0: VLM semantic router — inspect scene images and identify objects to edit."""
import json
import os
import re

import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image
from torchvision.transforms.functional import InterpolationMode

from pipeline.cache import load_or_run
from pipeline.types import SemanticRouterResult

MODEL_ID = "OpenGVLab/InternVL3-14B"

# Same normalization as InternVL3 training (ImageNet stats, 448×448)
_TRANSFORM = T.Compose([
    T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
    T.Resize((448, 448), interpolation=InterpolationMode.BICUBIC),
    T.ToTensor(),
    T.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
])

ROUTER_PROMPT = """\
You are analyzing a 3D scene from {n} camera views.

The user wants to: "{query}"

Carefully examine every provided image and identify the specific objects in this scene \
that should be affected by the user's edit. Only include objects you can actually see.

Return ONLY a JSON object, no other text:
{{
  "target_objects": ["singular noun 1", "singular noun 2"],
  "reasoning": "one sentence explaining what you found and why"
}}

Rules:
- Use singular, common English nouns (e.g. "chair", "wooden shelf", "metal cabinet")
- Only list objects that are clearly visible AND match the edit request
- If nothing in the scene matches, return an empty list — do not guess
- Do not include the same object twice under different names"""


def _load_sample_images(image_dir: str, n: int = 4) -> torch.Tensor:
    """Load n evenly-spaced images and return a stacked [n, C, H, W] tensor."""
    paths = sorted([
        os.path.join(image_dir, f)
        for f in os.listdir(image_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ])
    if not paths:
        raise ValueError(f"No images found in {image_dir}")
    n = min(n, len(paths))
    indices = np.linspace(0, len(paths) - 1, n, dtype=int)
    images = [Image.open(paths[i]).convert("RGB") for i in indices]
    return torch.stack([_TRANSFORM(img) for img in images])  # [n, C, H, W]


def _parse_response(text: str) -> dict:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        pass
    match = re.search(r'"target_objects"\s*:\s*\[([^\]]*)\]', text)
    if match:
        items = [s.strip().strip('"') for s in match.group(1).split(",") if s.strip()]
        return {"target_objects": items, "reasoning": ""}
    return {"target_objects": [], "reasoning": ""}


def _run_routing(query: str, image_dir: str) -> dict:
    from transformers import AutoModel, AutoTokenizer

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"[router] Loading {MODEL_ID}...")
    model = AutoModel.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    ).eval()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

    pixel_values = _load_sample_images(image_dir, n=8).to(device, dtype=torch.bfloat16)
    n = pixel_values.shape[0]

    # One <image> token per view
    image_tokens = "\n".join(["<image>"] * n)
    prompt = image_tokens + "\n\n" + ROUTER_PROMPT.format(n=n, query=query)

    generation_config = dict(max_new_tokens=512, do_sample=False)
    response = model.chat(tokenizer, pixel_values, prompt, generation_config)

    print(f"[router] Response: {response[:300]}")
    parsed = _parse_response(response)
    targets = parsed.get("target_objects", [])
    reasoning = parsed.get("reasoning", "")
    print(f"[router] Target objects ({len(targets)}): {targets}")
    print(f"[router] Reasoning: {reasoning}")

    return {"target_objects": targets, "reasoning": reasoning}


def semantic_router(
    image_dir: str,
    query: str,
    cache_dir: str = "outputs/cache",
) -> SemanticRouterResult:
    """Stage 0 entry point. Inspects scene images and identifies objects matching the query."""
    result = load_or_run(
        "semantic_router",
        _run_routing,
        query,
        image_dir,
        fmt="json",
        cache_dir=cache_dir,
    )
    return SemanticRouterResult(object_names=result.get("target_objects", []))

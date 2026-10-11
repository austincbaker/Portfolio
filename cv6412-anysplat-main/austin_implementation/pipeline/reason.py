# pipeline/reason.py
"""Stage 4: Per-object VLM property reasoning using InternVL3-14B."""
import json
import re

import numpy as np
import torch
import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode
from PIL import Image

from pipeline.cache import load_or_run
from pipeline.image_utils import load_and_crop_images
from pipeline.types import SegmentationResult, ReasoningResult

MODEL_ID = "OpenGVLab/InternVL3-14B"

# InternVL3 image preprocessing constants
_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD = (0.229, 0.224, 0.225)
_TRANSFORM = T.Compose([
    T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
    T.Resize((448, 448), interpolation=InterpolationMode.BICUBIC),
    T.ToTensor(),
    T.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
])

PROPERTY_PROMPT = """Analyze this object in the image and return a JSON object with these properties:
{
  "material": "<primary material — choose exactly one: wood, metal, stone, glass, plastic, concrete, fabric, ceramic, vegetation, water>",
  "weight_class": "<light|medium|heavy>",
  "fragile": <true|false>,
  "soft": <true|false>,
  "movable": <true|false>,
  "natural": <true|false>
}

Return ONLY the JSON object, no other text."""


def _parse_json_response(text: str) -> dict:
    """Parse JSON from VLM response, with fallback regex extraction."""
    # Try direct JSON parse
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    # Fallback: regex extraction
    result = {}
    material_match = re.search(r'"material"\s*:\s*"([^"]+)"', text)
    if material_match:
        result["material"] = material_match.group(1)

    weight_match = re.search(r'"weight_class"\s*:\s*"([^"]+)"', text)
    if weight_match:
        result["weight_class"] = weight_match.group(1)

    for bool_field in ["fragile", "movable", "natural"]:
        bool_match = re.search(rf'"{bool_field}"\s*:\s*(true|false)', text, re.IGNORECASE)
        if bool_match:
            result[bool_field] = bool_match.group(1).lower() == "true"

    return result if result else {"material": "unknown"}


def _run_reasoning(
    image_dir: str,
    segments: SegmentationResult,
) -> dict[str, dict]:
    """Run VLM reasoning on each detected object."""
    from transformers import AutoModel, AutoTokenizer

    print(f"[reason] Loading {MODEL_ID}...")
    model = AutoModel.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    ).eval()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    generation_config = dict(max_new_tokens=256, do_sample=False)

    images = load_and_crop_images(image_dir)
    properties = {}

    for obj_name in segments.object_names:
        print(f"[reason] Analyzing: {obj_name}")

        # Find best view: the one with the largest mask area
        mask_areas = segments.masks[obj_name].sum(dim=(1, 2))  # [K]
        best_view = mask_areas.argmax().item()

        if mask_areas[best_view] == 0:
            print(f"[reason]   No mask found for {obj_name}, skipping")
            properties[obj_name] = {"material": "unknown"}
            continue

        # Crop to bounding box of the mask
        mask = segments.masks[obj_name][best_view].numpy()  # [H, W]
        img = images[best_view]  # [H, W, 3]

        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        rmin, rmax = np.where(rows)[0][[0, -1]]
        cmin, cmax = np.where(cols)[0][[0, -1]]

        # Add padding
        pad = 10
        H, W = mask.shape
        rmin = max(0, rmin - pad)
        rmax = min(H - 1, rmax + pad)
        cmin = max(0, cmin - pad)
        cmax = min(W - 1, cmax + pad)

        crop = img[rmin:rmax + 1, cmin:cmax + 1]
        crop_pil = Image.fromarray(crop)

        # Preprocess image for InternVL3
        pixel_values = _TRANSFORM(crop_pil).unsqueeze(0).to(torch.bfloat16).to(model.device)

        # Query VLM — InternVL3 uses model.chat() with <image> token in prompt
        question = f"<image>\nThis is a cropped image of a '{obj_name}'. {PROPERTY_PROMPT}"
        response = model.chat(tokenizer, pixel_values, question, generation_config)

        print(f"[reason]   Response: {response[:100]}...")
        props = _parse_json_response(response)
        print(f"[reason]   Parsed: {props}")
        properties[obj_name] = props

    return properties


def reason(
    image_dir: str,
    segments: SegmentationResult,
    cache_dir: str = "outputs/cache",
) -> ReasoningResult:
    """Stage 4 entry point. Cached as JSON."""
    props = load_or_run(
        "reasoning",
        _run_reasoning,
        image_dir,
        segments,
        fmt="json",
        cache_dir=cache_dir,
    )
    return ReasoningResult(properties=props)

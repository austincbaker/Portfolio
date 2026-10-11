# pipeline/segment.py
"""Stage 2: 2D object segmentation via SAM3 (unified detection + segmentation)."""
import os

import torch
import numpy as np
from PIL import Image

from pipeline.cache import load_or_run
from pipeline.image_utils import load_and_crop_images
from pipeline.types import SegmentationResult


def _run_segmentation(
    image_dir: str,
    object_names: list[str],
) -> SegmentationResult:
    """Run SAM3 text-prompted detection + segmentation on all images.

    SAM3 replaces both Grounding DINO and SAM2 — it takes a text prompt
    and produces detection boxes + segmentation masks in one forward pass.
    """
    from sam3 import build_sam3_image_model
    from sam3.model.sam3_image_processor import Sam3Processor

    images = load_and_crop_images(image_dir)
    K = len(images)
    H, W = images[0].shape[:2]

    print(f"[segment] Loaded {K} images at {H}x{W}")

    # Build SAM3 model
    print("[segment] Loading SAM3...")
    import sam3 as _sam3_pkg
    bpe_path = os.path.join(os.path.dirname(_sam3_pkg.__file__), "assets", "bpe_simple_vocab_16e6.txt.gz")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # SAM3's public API expects a bf16 autocast context around all forward passes
    # (see its example notebooks: every one does `torch.autocast("cuda", dtype=torch.bfloat16).__enter__()`).
    # Without this, vitdet MLP activations are bf16 while weights are fp32 → dtype mismatch.
    if device == "cuda":
        torch.autocast("cuda", dtype=torch.bfloat16).__enter__()
    sam3_model = build_sam3_image_model(
        bpe_path=bpe_path,
        device=device,
        eval_mode=True,
    )
    processor = Sam3Processor(
        sam3_model,
        resolution=1008,
        device=device,
        confidence_threshold=0.25,
    )

    # Run detection + segmentation per image
    all_masks = {name: [] for name in object_names}
    all_boxes = {name: [] for name in object_names}

    for k, img_np in enumerate(images):
        print(f"[segment] Processing image {k + 1}/{K}...")
        pil_img = Image.fromarray(img_np)

        # Encode image once (reused across all text prompts for this image)
        state = processor.set_image(pil_img)

        for obj_name in object_names:
            # Reset prompts from previous object query
            processor.reset_all_prompts(state)
            # Re-encode image features (reset_all_prompts clears language features)
            state = processor.set_image(pil_img, state=state)

            # Run text-prompted detection + segmentation
            state = processor.set_text_prompt(obj_name, state)

            if "masks" not in state or len(state["masks"]) == 0:
                # No detection — empty mask
                all_masks[obj_name].append(torch.zeros(H, W, dtype=torch.bool))
                all_boxes[obj_name].append(torch.zeros(4))
                continue

            # Take best detection (highest confidence)
            scores = state["scores"]
            best_idx = scores.argmax()

            mask = state["masks"][best_idx, 0]  # [H_orig, W_orig]
            box = state["boxes"][best_idx]      # [4] in xyxy pixel coords

            all_masks[obj_name].append(mask.cpu().bool())
            all_boxes[obj_name].append(box.cpu().float())

    # Stack across views
    masks = {name: torch.stack(all_masks[name]) for name in object_names}   # [K, H, W]
    boxes = {name: torch.stack(all_boxes[name]) for name in object_names}   # [K, 4]

    return SegmentationResult(masks=masks, boxes=boxes, object_names=object_names)


def segment(
    image_dir: str,
    object_names: list[str],
    cache_dir: str = "outputs/cache",
) -> SegmentationResult:
    """Stage 2 entry point."""
    return load_or_run(
        "segment",
        _run_segmentation,
        image_dir,
        object_names,
        cache_dir=cache_dir,
    )

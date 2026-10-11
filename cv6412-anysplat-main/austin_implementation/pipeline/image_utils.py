# pipeline/image_utils.py
"""Shared image loading and center-crop logic (mirrors AnySplat's process_image)."""
import os

import numpy as np
from PIL import Image


def load_and_crop_images(image_dir: str, target_size: int = 448) -> list[np.ndarray]:
    """Load images and apply same center-crop as AnySplat's process_image.

    Returns list of numpy arrays [H, W, 3] in uint8 (for SAM3 input).
    """
    image_paths = sorted([
        os.path.join(image_dir, f)
        for f in os.listdir(image_dir)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ])
    assert len(image_paths) > 0, f"No images found in {image_dir}"

    images = []
    for path in image_paths:
        img = Image.open(path).convert("RGB")
        width, height = img.size
        if width > height:
            new_height = target_size
            new_width = int(width * (new_height / height))
        else:
            new_width = target_size
            new_height = int(height * (new_width / width))
        img = img.resize((new_width, new_height))

        # Center crop
        left = (new_width - target_size) // 2
        top = (new_height - target_size) // 2
        img = img.crop((left, top, left + target_size, top + target_size))
        images.append(np.array(img))

    return images

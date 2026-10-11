# pipeline/reconstruct.py
"""Stage 1: Reconstruct 3D Gaussians from uncalibrated images via AnySplat."""
import os
import sys

import torch

from pipeline.cache import load_or_run
from pipeline.types import GaussiansResult

# AnySplat imports — add to sys.path since it's not an installed package
ANYSPLAT_DIR = os.path.join(os.path.dirname(__file__), "..", "anysplat")
sys.path.insert(0, ANYSPLAT_DIR)

from src.model.model.anysplat import AnySplat
from src.utils.image import process_image


def _run_reconstruction(image_dir: str) -> tuple[GaussiansResult, object]:
    """Run AnySplat inference on images. Returns (GaussiansResult, decoder)."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Load model
    print("[reconstruct] Loading AnySplat model...")
    model = AnySplat.from_pretrained("lhjiang/anysplat")
    model = model.to(device)
    model.eval()
    for param in model.parameters():
        param.requires_grad = False

    # Load and preprocess images
    print(f"[reconstruct] Loading images from {image_dir}...")
    image_paths = sorted([
        os.path.join(image_dir, f)
        for f in os.listdir(image_dir)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ])
    assert len(image_paths) > 0, f"No images found in {image_dir}"
    print(f"[reconstruct] Found {len(image_paths)} images")

    images = [process_image(img_path) for img_path in image_paths]
    images = torch.stack(images, dim=0).unsqueeze(0).to(device)  # [1, K, 3, 448, 448]

    # Run inference
    print("[reconstruct] Running AnySplat inference...")
    gaussians, pred_context_pose = model.inference((images + 1) * 0.5)

    # Extract and squeeze batch dim
    result = GaussiansResult(
        means=gaussians.means[0],               # [N, 3]
        covariances=gaussians.covariances[0],    # [N, 3, 3]
        harmonics=gaussians.harmonics[0],        # [N, 3, d_sh]
        opacities=gaussians.opacities[0],        # [N]
        scales=gaussians.scales[0],              # [N, 3]
        rotations=gaussians.rotations[0],        # [N, 4]
        extrinsics=pred_context_pose["extrinsic"][0],  # [K, 4, 4]
        intrinsics=pred_context_pose["intrinsic"][0],  # [K, 3, 3]
        image_size=(448, 448),
    )

    decoder = model.decoder
    print(f"[reconstruct] Done. {result.means.shape[0]} Gaussians from {len(image_paths)} views.")
    return result, decoder


def reconstruct(image_dir: str, cache_dir: str = "outputs/cache") -> tuple[GaussiansResult, object]:
    """Stage 1 entry point. Returns (GaussiansResult, decoder).

    The decoder is NOT cached — it must be kept in memory for Stage 6 rendering.
    The GaussiansResult IS cached to disk.
    """
    # We can't cache the decoder, so we handle caching manually
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, "reconstruct.pt")

    if os.path.exists(cache_path):
        print(f"[reconstruct] Loading cached Gaussians from {cache_path}")
        result = torch.load(cache_path, weights_only=False, map_location="cpu")
        # Still need to load model for the decoder
        print("[reconstruct] Loading AnySplat model for decoder...")
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = AnySplat.from_pretrained("lhjiang/anysplat")
        model = model.to(device)
        model.eval()
        return result, model.decoder

    result, decoder = _run_reconstruction(image_dir)
    torch.save(result, cache_path)
    print(f"[reconstruct] Cached Gaussians to {cache_path}")
    return result, decoder

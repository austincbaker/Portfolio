# pipeline/video_utils.py
"""Extract frames from a video file for use as pipeline image input."""
import os

import cv2
import numpy as np


def _blur_score(frame: np.ndarray) -> float:
    """Return Laplacian variance — higher = sharper."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def extract_frames(
    video_path: str,
    output_dir: str,
    max_frames: int = 20,
    target_fps: float = 1.0,
    blur_threshold: float = 80.0,
) -> str:
    """Extract evenly-spaced, non-blurry frames from a video.

    Args:
        video_path: Path to input video file (.mp4, .mov, .avi, etc.)
        output_dir: Directory to write extracted frame PNGs.
        max_frames: Maximum number of frames to keep (default 20).
        target_fps: Target sampling rate in frames per second (default 1.0).
        blur_threshold: Laplacian variance below this is considered blurry and skipped.

    Returns:
        output_dir (same as input) containing the extracted frame PNGs.
    """
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s = total_frames / video_fps

    # Determine frame indices to sample
    sample_interval = max(1, int(video_fps / target_fps))
    candidate_indices = list(range(0, total_frames, sample_interval))

    print(f"[video] {os.path.basename(video_path)}: {duration_s:.1f}s @ {video_fps:.1f}fps, "
          f"{total_frames} frames total")
    print(f"[video] Sampling every {sample_interval} frames → {len(candidate_indices)} candidates")

    kept = []
    for idx in candidate_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        score = _blur_score(frame)
        if score < blur_threshold:
            print(f"[video]   Frame {idx:05d}: skipped (blur score {score:.1f} < {blur_threshold})")
            continue
        kept.append((idx, frame))

    cap.release()

    if not kept:
        raise RuntimeError(
            f"No usable frames found (all below blur threshold {blur_threshold}). "
            "Try lowering blur_threshold or using a less shaky video."
        )

    # If we have more than max_frames, subsample evenly
    if len(kept) > max_frames:
        step = len(kept) / max_frames
        kept = [kept[int(i * step)] for i in range(max_frames)]

    print(f"[video] Keeping {len(kept)} frames")

    for i, (idx, frame) in enumerate(kept):
        out_path = os.path.join(output_dir, f"frame_{i:04d}.png")
        cv2.imwrite(out_path, frame)

    print(f"[video] Saved {len(kept)} frames to {output_dir}")
    return output_dir

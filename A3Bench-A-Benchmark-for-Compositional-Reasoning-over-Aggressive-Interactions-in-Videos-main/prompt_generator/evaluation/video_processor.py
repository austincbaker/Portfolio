"""
Video processor with hardware-accelerated decoding and async prefetching.
"""
import cv2
from pathlib import Path
from PIL import Image
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional
import threading
import warnings


@dataclass
class VideoProcessorConfig:
    num_frames: int = 8
    frame_size: tuple[int, int] | None = None
    use_gpu_decoding: bool = True
    prefetch_count: int = 2
    use_black_frames: bool = False


class VideoProcessor:
    """Standard video processor using OpenCV."""

    def __init__(self, config: VideoProcessorConfig | None = None):
        self.config = config or VideoProcessorConfig()

    def extract_frames(self, video_path: str | Path) -> list[Image.Image]:
        if self.config.use_black_frames:
            return self._extract_black_frames(video_path)
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open video: {video_path}")

        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                raise RuntimeError(f"Video has no frames: {video_path}")

            frame_indices = self._compute_frame_indices(total_frames)
            frames = []

            for idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if not ret:
                    continue

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(frame_rgb)

                if self.config.frame_size:
                    pil_image = pil_image.resize(self.config.frame_size)

                frames.append(pil_image)

            if not frames:
                raise RuntimeError(f"Failed to extract frames from: {video_path}")

            return frames

        finally:
            cap.release()

    def _compute_frame_indices(self, total_frames: int) -> list[int]:
        num_frames = min(self.config.num_frames, total_frames)

        if num_frames == 1:
            return [total_frames // 2]

        if num_frames >= total_frames:
            return list(range(total_frames))

        step = (total_frames - 1) / (num_frames - 1)
        indices = [int(round(i * step)) for i in range(num_frames)]

        return indices

    def _extract_black_frames(self, video_path: str | Path) -> list[Image.Image]:

        video_path = Path(video_path)
        w, h = 224, 224
        try:
            cap = cv2.VideoCapture(str(video_path))
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 224
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 224
                cap.release()
        except Exception:
            pass

        if self.config.frame_size:
            w, h = self.config.frame_size

        black_frame = Image.new("RGB", (w, h), (0, 0, 0))
        return [black_frame.copy() for _ in range(self.config.num_frames)]

    def get_video_info(self, video_path: str | Path) -> dict:
        video_path = Path(video_path)
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            return {"error": f"Failed to open: {video_path}"}

        try:
            info = {
                "path": str(video_path),
                "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            }
            if info["fps"] > 0:
                info["duration_seconds"] = info["total_frames"] / info["fps"]
            return info
        finally:
            cap.release()


class FastVideoProcessor(VideoProcessor):
    """
    Hardware-accelerated video processor using decord library.
    Falls back to OpenCV if decord is not available.
    """

    def __init__(self, config: VideoProcessorConfig | None = None):
        super().__init__(config)
        self._decord_available = self._check_decord()
        self._gpu_ctx = None

        if self._decord_available and self.config.use_gpu_decoding:
            self._setup_gpu_context()

    def _check_decord(self) -> bool:
        try:
            import decord
            return True
        except ImportError:
            warnings.warn(
                "decord not available, falling back to OpenCV. "
                "Install with: pip install decord"
            )
            return False

    def _setup_gpu_context(self) -> None:
        if not self._decord_available:
            return

        try:
            from decord import gpu
            self._gpu_ctx = gpu(0)
        except Exception:
            self._gpu_ctx = None

    def extract_frames(self, video_path: str | Path) -> list[Image.Image]:
        if self.config.use_black_frames:
            return self._extract_black_frames(video_path)
        if not self._decord_available:
            return super().extract_frames(video_path)

        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        try:
            return self._extract_with_decord(video_path)
        except Exception as e:
            warnings.warn(f"Decord failed ({e}), falling back to OpenCV")
            return super().extract_frames(video_path)

    def _extract_with_decord(self, video_path: Path) -> list[Image.Image]:
        from decord import VideoReader, cpu

        # Use GPU context if available, otherwise CPU
        ctx = self._gpu_ctx if self._gpu_ctx is not None else cpu(0)

        try:
            vr = VideoReader(str(video_path), ctx=ctx)
        except Exception:
            vr = VideoReader(str(video_path), ctx=cpu(0))

        total_frames = len(vr)
        if total_frames <= 0:
            raise RuntimeError(f"Video has no frames: {video_path}")

        indices = self._compute_frame_indices(total_frames)


        frames_array = vr.get_batch(indices).asnumpy()

        frames = []
        for frame in frames_array:
            pil_image = Image.fromarray(frame)
            if self.config.frame_size:
                pil_image = pil_image.resize(self.config.frame_size)
            frames.append(pil_image)

        return frames


class AsyncFrameLoader:
    """
    Async frame loader that prefetches frames for upcoming videos
    while the model processes the current video.
    """

    def __init__(
        self,
        video_processor: VideoProcessor,
        prefetch_count: int = 2,
        max_cache_size: int = 5
    ):
        self.processor = video_processor
        self.prefetch_count = prefetch_count
        self.max_cache_size = max_cache_size

        self.executor = ThreadPoolExecutor(max_workers=prefetch_count)
        self.frame_cache: dict[str, list[Image.Image]] = {}
        self.pending: dict[str, Future] = {}
        self.lock = threading.Lock()
        self._cache_order: list[str] = []

    def prefetch(self, video_path: str | Path) -> None:

        video_key = str(video_path)

        with self.lock:
            if video_key in self.frame_cache or video_key in self.pending:
                return

            future = self.executor.submit(self.processor.extract_frames, video_path)
            self.pending[video_key] = future

    def prefetch_batch(self, video_paths: list[str | Path]) -> None:

        for path in video_paths[:self.prefetch_count]:
            self.prefetch(path)

    def get_frames(self, video_path: str | Path) -> list[Image.Image]:

        video_key = str(video_path)

        with self.lock:

            if video_key in self.frame_cache:
                return self.frame_cache[video_key]


            if video_key in self.pending:
                future = self.pending[video_key]


        if video_key in self.pending:
            try:
                frames = future.result()
                self._add_to_cache(video_key, frames)
                return frames
            finally:
                with self.lock:
                    self.pending.pop(video_key, None)


        frames = self.processor.extract_frames(video_path)
        self._add_to_cache(video_key, frames)
        return frames

    def _add_to_cache(self, video_key: str, frames: list[Image.Image]) -> None:

        with self.lock:

            while len(self.frame_cache) >= self.max_cache_size:
                if self._cache_order:
                    oldest = self._cache_order.pop(0)
                    self.frame_cache.pop(oldest, None)

            self.frame_cache[video_key] = frames
            self._cache_order.append(video_key)

    def clear_cache(self) -> None:

        with self.lock:
            self.frame_cache.clear()
            self._cache_order.clear()

    def shutdown(self) -> None:

        self.executor.shutdown(wait=True)
        self.clear_cache()


def create_video_processor(
    config: VideoProcessorConfig | None = None,
    use_fast: bool = True
) -> VideoProcessor:

    if use_fast:
        return FastVideoProcessor(config)
    return VideoProcessor(config)
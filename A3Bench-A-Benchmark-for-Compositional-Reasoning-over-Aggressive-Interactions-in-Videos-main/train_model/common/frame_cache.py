"""One-time frame extraction for the multimodal pipeline.

Reads every video_name referenced in the SFT train/val/test splits, extracts
`frames_per_video` evenly-spaced jpgs via ffmpeg, and writes them to
`{frames_dir}/{video_stem}/frame_{i:02d}.jpg`. Skips videos that are already
fully cached.

Failures are logged (with the underlying ffmpeg/ffprobe stderr) and a
manifest of everything that did not reach status="ok" is written to
`{frames_dir}/_failures.json`. The job exits 0 even when failures occur so
that downstream training can continue on the videos that did cache; the
multimodal dataset filters out examples whose video has missing frames.

Statuses emitted per video:
    ok        all N frames written this run
    skipped   all N frames already on disk
    missing   video file not present in videos_dir
    corrupt   file exists but ffprobe could not read its duration
    partial   ffmpeg failed on >= 1 frame (after one retry with ignore_err)

Invoke:
    python -m train_model.common.frame_cache \\
        --config train_model/configs/base.yaml
"""

from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from train_model.common.config import load_config


MANIFEST_NAME = "_failures.json"


def _referenced_videos(data_paths: list[str]) -> set[str]:
    videos: set[str] = set()
    for p in data_paths:
        with open(p, encoding="utf-8") as f:
            examples = json.load(f)
        if isinstance(examples, list):
            for ex in examples:
                v = ex.get("video_name")
                if v:
                    videos.add(v)
        elif isinstance(examples, dict) and "questions_by_video" in examples:
            videos.update(examples["questions_by_video"].keys())
    return videos


def _video_duration(video_path: Path) -> tuple[float, str]:

    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True,
    )
    try:
        return float(res.stdout.strip()), res.stderr.strip()
    except ValueError:
        return 0.0, res.stderr.strip() or "unparseable duration"


def _run_ffmpeg(cmd: list[str]) -> tuple[bool, str]:
    res = subprocess.run(cmd, capture_output=True, text=True)
    return (res.returncode == 0, res.stderr.strip())


def _extract_frame(video_path: Path, timestamp: float, output_path: Path,
                   duration: float) -> tuple[bool, str]:

    output_path.parent.mkdir(parents=True, exist_ok=True)

    attempt1 = [
        "ffmpeg", "-nostdin", "-y",
        "-ss", f"{timestamp:.3f}",
        "-i", str(video_path),
        "-frames:v", "1", "-q:v", "2",
        str(output_path),
    ]
    ok, err1 = _run_ffmpeg(attempt1)
    if ok and output_path.exists():
        return True, ""


    attempt2 = [
        "ffmpeg", "-nostdin", "-y",
        "-err_detect", "ignore_err",
        "-i", str(video_path),
        "-ss", f"{timestamp:.3f}",
        "-vsync", "0",
        "-frames:v", "1", "-q:v", "2",
        str(output_path),
    ]
    ok, err2 = _run_ffmpeg(attempt2)
    if ok and output_path.exists():
        return True, ""


    attempt3 = [
        "ffmpeg", "-nostdin", "-y",
        "-err_detect", "ignore_err",
        "-i", str(video_path),
        "-vf", f"select='eq(pict_type\\,I)'",
        "-frames:v", "1", "-q:v", "2",
        "-vsync", "0",
        str(output_path),
    ]
    ok, err3 = _run_ffmpeg(attempt3)
    if ok and output_path.exists():
        return True, ""


    def _tail(s: str) -> str:
        return s.splitlines()[-1] if s else ""
    err = f"attempt1: {_tail(err1)} | attempt2: {_tail(err2)} | attempt3: {_tail(err3)}"
    return False, err


def _process_video(video_name: str, videos_dir: Path, frames_dir: Path,
                   n_frames: int) -> dict:

    video_path = videos_dir / video_name
    result: dict = {"video_name": video_name, "status": "ok",
                    "failed_frames": [], "errors": []}

    if not video_path.is_file():
        result["status"] = "missing"
        result["errors"].append(f"file not found: {video_path}")
        return result

    stem = Path(video_name).stem
    out_dir = frames_dir / stem
    expected = [out_dir / f"frame_{i:02d}.jpg" for i in range(n_frames)]
    if all(p.exists() for p in expected):
        result["status"] = "skipped"
        return result

    duration, probe_err = _video_duration(video_path)
    if duration <= 0:
        result["status"] = "corrupt"
        result["errors"].append(f"ffprobe: {probe_err}")
        return result

    any_failed = False
    for i, out_path in enumerate(expected):
        if out_path.exists():
            continue
        t = duration * (i + 1) / (n_frames + 1)
        ok, err = _extract_frame(video_path, t, out_path, duration)
        if not ok:
            any_failed = True
            result["failed_frames"].append(i)
            result["errors"].append(f"frame {i:02d} @ t={t:.3f}s: {err}")

    if any_failed:
        result["status"] = "partial"
    return result


def extract_all_frames(config: dict, workers: int = 8) -> dict:
    videos_dir = Path(config["video"]["videos_dir"])
    frames_dir = Path(config["video"]["frames_dir"])
    n_frames = int(config["video"]["frames_per_video"])
    frames_dir.mkdir(parents=True, exist_ok=True)

    data = config["data"]
    data_paths = [p for p in [data.get("train"), data.get("val"), data.get("test")] if p]
    videos = sorted(_referenced_videos(data_paths))
    print(f"Found {len(videos)} unique videos across {data_paths}", flush=True)
    print(f"Extracting {n_frames} frames/video into {frames_dir}", flush=True)

    counts = {"ok": 0, "skipped": 0, "missing": 0, "corrupt": 0, "partial": 0}
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_process_video, v, videos_dir, frames_dir, n_frames)
                   for v in videos]
        for i, fut in enumerate(as_completed(futures), start=1):
            result = fut.result()
            status = result["status"]
            counts[status] = counts.get(status, 0) + 1
            if status not in ("ok", "skipped"):
                failures.append(result)
            if i % 100 == 0 or i == len(videos):
                print(
                    f"  [{i}/{len(videos)}] ok={counts['ok']} skip={counts['skipped']}"
                    f" miss={counts['missing']} corrupt={counts['corrupt']}"
                    f" partial={counts['partial']}",
                    flush=True,
                )

    print(f"\nFinal counts: {counts}", flush=True)

    manifest_path = frames_dir / MANIFEST_NAME
    if failures:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"counts": counts, "failures": failures}, f, indent=2)
        print(f"\nWrote {len(failures)} failure records to {manifest_path}", flush=True)
        for rec in failures[:5]:
            print(f"  [{rec['status']:7s}] {rec['video_name']}", flush=True)
            for e in rec["errors"][:2]:
                print(f"        {e}", flush=True)
    else:

        if manifest_path.exists():
            manifest_path.unlink()
        print("\nAll videos cached successfully.", flush=True)

    return {"counts": counts, "failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="train_model/configs/base.yaml")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--override", action="append", default=[],
                        help="Dotted override, e.g. video.frames_per_video=16")
    args = parser.parse_args()

    cfg = load_config(args.config, overrides=args.override)


    extract_all_frames(cfg, workers=args.workers)


if __name__ == "__main__":
    main()

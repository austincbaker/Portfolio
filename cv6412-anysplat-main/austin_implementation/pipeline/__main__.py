# pipeline/__main__.py
"""CLI entry point: python -m pipeline ..."""
import argparse
import os


def main():
    parser = argparse.ArgumentParser(
        description="Language guided 3D scene decomposition pipeline"
    )
    parser.add_argument(
        "--image_dir",
        type=str,
        default=None,
        help="Path to directory of input images",
    )
    parser.add_argument(
        "--video",
        type=str,
        default=None,
        help="Path to a video file — frames are extracted automatically",
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help='Edit query, e.g. "remove all wooden objects"',
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="outputs",
        help="Output directory for cache and results (default: outputs)",
    )
    parser.add_argument(
        "--edits",
        type=str,
        default=None,
        help="Path to JSON file of EditSpecs. If set together with --sq_pt, runs "
             "the edit_v2 demo path (rotate/scale/recolor/translate/delete) "
             "instead of the legacy delete-only flow.",
    )
    parser.add_argument(
        "--sq_pt",
        type=str,
        default=None,
        help="Path to SuperDec payload (output of stage_a_decompose). Required "
             "when --edits is set.",
    )
    args = parser.parse_args()

    if args.video is None and args.image_dir is None:
        parser.error("Provide either --image_dir or --video")
    if (args.edits is None) ^ (args.sq_pt is None):
        parser.error("--edits and --sq_pt must be provided together")

    image_dir = args.image_dir
    if args.video is not None:
        from pipeline.video_utils import extract_frames
        frames_dir = os.path.join(args.output_dir, "frames")
        image_dir = extract_frames(args.video, frames_dir)

    if args.edits is not None:
        from pipeline.run_edits import run_edits
        run_edits(image_dir, args.query, args.edits, args.sq_pt, args.output_dir)
    else:
        from pipeline.run import run
        run(image_dir, args.query, args.output_dir)


if __name__ == "__main__":
    main()

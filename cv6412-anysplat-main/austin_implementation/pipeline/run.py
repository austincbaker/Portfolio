# pipeline/run.py
"""Pipeline orchestrator — chains all stages in order (v2)."""
import pipeline.visualize as viz


def run(image_dir: str, query: str, output_dir: str = "outputs"):
    """Run the full pipeline.

    Args:
        image_dir: Path to directory of input images (or extracted video frames).
        query: Natural language edit query (e.g., "remove all wooden objects").
        output_dir: Directory for outputs (cache + results).
    """
    from pipeline.reconstruct import reconstruct
    from pipeline.semantic_router import semantic_router
    from pipeline.segment import segment
    from pipeline.lift_masks import lift_masks
    from pipeline.complete_objects import complete_objects
    from pipeline.edit import edit
    from pipeline.render import render

    cache_dir = f"{output_dir}/cache"
    results_dir = f"{output_dir}/results"
    stages_dir = f"{output_dir}/results/stages"

    print(f"=== Pipeline ===")
    print(f"Images: {image_dir}")
    print(f"Query:  {query}")
    print()

    # Stage 0: VLM inspects scene images + query → identifies exactly which objects to remove
    print("[pipeline] Stage 0: semantic router (VLM + images)...")
    semantic = semantic_router(image_dir, query, cache_dir=cache_dir)

    if not semantic.object_names:
        print("[pipeline] No matching objects found in scene. Nothing to edit.")
        return

    print(f"[pipeline] Objects to remove: {semantic.object_names}")
    print()

    # Stage 1: Reconstruct 3D Gaussians from images
    print("[pipeline] Stage 1: reconstruct...")
    gaussians, decoder = reconstruct(image_dir, cache_dir=cache_dir)
    viz.save_stage1_pointcloud(gaussians, stages_dir)

    # Stage 2: Segment exactly the VLM-identified objects
    segments = segment(image_dir, object_names=semantic.object_names, cache_dir=cache_dir)
    viz.save_stage2_masks(image_dir, segments, stages_dir)

    # Stage 3: Lift 2D masks to 3D
    lifted = lift_masks(gaussians, segments, cache_dir=cache_dir)
    viz.save_stage3_labels(gaussians, lifted, decoder, stages_dir)

    # Stage 4: Per-object 3D completion (geometric mirroring)
    completed = complete_objects(gaussians, lifted, cache_dir=cache_dir)
    viz.save_stage4_completion(gaussians, lifted, completed, stages_dir)

    # Stage 5: Remove all VLM-identified objects (no secondary matching)
    edits = edit(gaussians, lifted, query, cache_dir=cache_dir)

    # Stage 6: Render all views + export videos
    render(gaussians, edits, decoder, results_dir=results_dir)

    print(f"\n=== Pipeline complete! Results in {results_dir}/ ===")

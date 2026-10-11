# Austin Baker | Software Engineering and Computer Vision

![AI engineering, computer vision, and developer platforms](assets/portfolio-header.svg)

I'm a Software Engineer at Lockheed Martin and a Computer Vision graduate student at the University of Central Florida. My work spans AI-enabled engineering tools, vision-language models, 3D reconstruction, and full-stack software development.

This portfolio contains source code for my recent research and software projects, along with an archive of earlier work.

[Featured projects](#featured-projects) · [Earlier projects](#earlier-projects) · [LinkedIn](https://www.linkedin.com/in/austinbaker1991/) · [Email](mailto:austincbaker1991@gmail.com)

## Featured projects

| Project | Focus | Source and documentation |
| --- | --- | --- |
| **A3Bench** | Compositional reasoning and participant-role understanding in video | [Source](A3Bench-A-Benchmark-for-Compositional-Reasoning-over-Aggressive-Interactions-in-Videos-main/) · [README](A3Bench-A-Benchmark-for-Compositional-Reasoning-over-Aggressive-Interactions-in-Videos-main/README.md) |
| **DecompFormer** | Language-guided 3D scene editing with AnySplat, SAM3, and a vision-language model | [My implementation](cv6412-anysplat-main/austin_implementation/) · [README](cv6412-anysplat-main/austin_implementation/README.md) |
| **Looting Bag Loot Tracker** | Event-driven loot tracking for RuneLite | [Source](runelite-plugin-lootingbag-tracker/) · [README](runelite-plugin-lootingbag-tracker/README.md) |

### A3Bench

**A Benchmark for Compositional Reasoning over Aggressive Interactions in Videos · NeurIPS 2026**

Recognizing an action is only part of understanding an interaction. A model also needs to identify who performed the action, who was affected, and how those roles fit together. With my collaborators, I developed a role-grounded benchmark that tests these relationships through compositional questions and challenging distractors.

The code in this portfolio includes:

- Multiple-choice question generation from annotated videos, covering six question types across approximately 2,700 clips.
- Shared model-loading and evaluation tools for several vision-language model families.
- Multi-GPU evaluation with checkpointing and resume support.
- Supervised fine-tuning tools using LoRA with InternVL2.5-8B.

**Technologies:** Python, PyTorch, CUDA, Transformers, OpenCV/Decord, and SLURM.

[Explore A3Bench](A3Bench-A-Benchmark-for-Compositional-Reasoning-over-Aggressive-Interactions-in-Videos-main/) · [Fine-tuning documentation](A3Bench-A-Benchmark-for-Compositional-Reasoning-over-Aggressive-Interactions-in-Videos-main/train_model/sft/README.md)

### DecompFormer

**Language-guided 3D scene editing · UCF Advanced Computer Vision**

Given multiple views of a scene, or a video, and a query such as “remove all wooden objects,” DecompFormer reconstructs a 3D scene, identifies the target objects, and renders the scene after their removal.

My implementation combines:

- **InternVL3-14B** to identify visible objects that match the query.
- **AnySplat** to reconstruct a 3D Gaussian Splatting representation from multiple views.
- **SAM3** to produce text-prompted segmentation masks for each view.
- Projection and majority voting to lift 2D masks into per-Gaussian object labels.
- A geometric mirroring baseline for approximating unseen object geometry.
- Object removal, diagnostic visualizations, PNG previews, and MP4 orbit videos.

The pipeline caches intermediate results and includes a SLURM driver that supports requeueing and resuming interrupted runs.

**Technologies:** Python, PyTorch, CUDA, AnySplat, SAM3, InternVL3, gsplat, and SLURM.

[Project overview](cv6412-anysplat-main/README.md) · [My implementation and usage](cv6412-anysplat-main/austin_implementation/README.md) · [Upstream AnySplat documentation](cv6412-anysplat-main/anysplat/README.md)

### Looting Bag Loot Tracker

**RuneLite plugin for Old School RuneScape**

RuneLite's standard Loot Tracker doesn't record items sent directly into a looting bag instead of the player's inventory. This plugin detects those items and records them under the chest, container, or pickpocket interaction that produced them.

Supported interactions include Rogues' Den chests, standard chest actions, pickpocketing, and other lootable containers. The looting bag must be open, and RuneLite's Loot Tracker must be enabled.

**Technologies:** Java and the RuneLite plugin ecosystem.

[Explore the plugin](runelite-plugin-lootingbag-tracker/) · [Usage and requirements](runelite-plugin-lootingbag-tracker/README.md)

## Earlier projects

The [`archived/`](archived/) directory contains 20 earlier projects covering mobile development, concurrency, data structures, desktop applications, and Python scripting.

| Area | Projects |
| --- | --- |
| Android / Kotlin | Geofenced reminders; math, currency, and maps; lifecycle and gesture exercises; a simple math application |
| C++ | Dining philosophers, a post office simulator, readers-writers synchronization, and semaphore-based processor scheduling |
| Java / C# | Encrypted chat, tree/hash-map/linked-list exercises, Zoom scheduling and recording, and a screen recording component |
| Python | A dictionary scraper, employee information tools, a medication compiler, fantasy game utilities, a password-cracking example, and additional scripts |

[Browse the archive](archived/)

## Running the projects

Each project has its own dependencies and setup instructions. Open its README before installing or running it. The computer vision projects require CUDA-capable hardware and external model or dataset setup; the RuneLite plugin uses its own Java/Gradle project.

## Attribution and licensing

A3Bench is collaborative research. The 3D editing project includes upstream AnySplat code alongside my DecompFormer implementation in `austin_implementation/`. Refer to the individual project directories for their credits, license files, and dependency terms.


"""Generate a small, no-video visual-consistency sample for one character."""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from storymotion.models import StoryMotionBundle
from storymotion.providers import MiniMaxImageProvider, UrllibMiniMaxMediaTransport
from storymotion.services import VisualReferenceRenderer


ROOT = Path(__file__).resolve().parents[1]


def reduced_bundle(bundle: StoryMotionBundle, shot_count: int) -> StoryMotionBundle:
    shots = list(bundle.storyboard.shots[:shot_count])
    if not shots or not shots[0].character_ids:
        raise ValueError("The selected storyboard needs a visible primary character")
    primary_id = shots[0].character_ids[0]
    shots = [
        shot.model_copy(
            update={
                "character_ids": [primary_id] if primary_id in shot.character_ids else []
            }
        )
        for shot in shots
    ]
    scene_ids = {shot.scene_id for shot in shots}
    scenes = [
        scene.model_copy(
            update={
                "characters": [primary_id] if primary_id in scene.characters else []
            }
        )
        for scene in bundle.screenplay.scenes
        if scene.scene_id in scene_ids
    ]
    characters = [
        character for character in bundle.story.characters if character.id == primary_id
    ]
    story = bundle.story.model_copy(update={"characters": characters})
    screenplay = bundle.screenplay.model_copy(
        update={"characters": characters, "scenes": scenes}
    )
    storyboard = bundle.storyboard.model_copy(update={"shots": shots})
    return bundle.model_copy(
        update={"story": story, "screenplay": screenplay, "storyboard": storyboard}
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundle",
        type=Path,
        default=ROOT / "outputs" / "latest_storymotion_bundle.json",
    )
    parser.add_argument("--shot-count", type=int, default=3, choices=range(1, 4))
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Reuse an existing sample directory; present assets will not be regenerated.",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY is not configured")
    bundle = StoryMotionBundle.model_validate_json(args.bundle.read_text(encoding="utf-8"))
    sample = reduced_bundle(bundle, args.shot_count)
    output_dir = args.output_dir or ROOT / "outputs" / (
        "character_consistency_ab_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    provider = MiniMaxImageProvider(
        UrllibMiniMaxMediaTransport(
            api_key=api_key,
            base_url=os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com"),
        )
    )
    assets = VisualReferenceRenderer(provider).prepare(sample, output_dir=output_dir)
    print(f"output_dir={output_dir}")
    print(f"characters={len(assets.character_frames)}")
    print(f"turnarounds={len(assets.character_turnarounds)}")
    print(f"scenes={len(assets.scene_frames)}")
    print(f"keyframes={len(assets.shot_frames)}")


if __name__ == "__main__":
    main()

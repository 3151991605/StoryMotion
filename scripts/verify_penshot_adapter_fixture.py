"""Convert a documented PenShot fragment fixture into strict StoryMotion outputs."""

from __future__ import annotations

import json
from pathlib import Path

from storymotion.adapters import adapt_penshot_result
from storymotion.models import (
    ProjectBrief,
    ScreenplayPackage,
    StoryMotionBundle,
    StoryPackage,
)


ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_DIR = ROOT / "outputs" / "verification"
OUTPUT_DIR = VERIFICATION_DIR / "penshot"
BRIEF_FILE = VERIFICATION_DIR / "minimax_m3_project_brief_run_01.json"
STORY_FILE = VERIFICATION_DIR / "story_graph" / "story_package.json"
SCREENPLAY_FILE = (
    VERIFICATION_DIR / "screenplay" / "screenplay_package_repaired.json"
)
RAW_FIXTURE_FILE = ROOT / "tests" / "fixtures" / "penshot_fragments.json"
SHOT_FILE = OUTPUT_DIR / "shot_package.json"
BUNDLE_FILE = OUTPUT_DIR / "storymotion_bundle_through_shots.json"
SUMMARY_FILE = VERIFICATION_DIR / "penshot_adapter_fixture_summary.json"


def main() -> int:
    brief = ProjectBrief.model_validate_json(BRIEF_FILE.read_text(encoding="utf-8"))
    story = StoryPackage.model_validate_json(STORY_FILE.read_text(encoding="utf-8"))
    screenplay = ScreenplayPackage.model_validate_json(
        SCREENPLAY_FILE.read_text(encoding="utf-8")
    )
    raw_result = json.loads(RAW_FIXTURE_FILE.read_text(encoding="utf-8"))

    storyboard = adapt_penshot_result(raw_result, screenplay)
    bundle = StoryMotionBundle(
        brief=brief,
        story=story,
        screenplay=screenplay,
        storyboard=storyboard,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SHOT_FILE.write_text(
        json.dumps(storyboard.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    BUNDLE_FILE.write_text(
        json.dumps(bundle.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    scene_durations = {
        scene.scene_id: sum(
            shot.duration
            for shot in storyboard.shots
            if shot.scene_id == scene.scene_id
        )
        for scene in screenplay.scenes
    }
    summary = {
        "mode": "documented_penshot_fragment_fixture",
        "penshot_distribution_version": "0.3.4",
        "sdk_import_passed": False,
        "adapter_passed": True,
        "cross_layer_bundle_passed": True,
        "shot_count": len(storyboard.shots),
        "total_shot_duration": storyboard.total_shot_duration,
        "scene_durations": scene_durations,
        "all_image_prompts_present": all(
            bool(shot.image_prompt.strip()) for shot in storyboard.shots
        ),
        "all_video_prompts_present": all(
            bool(shot.video_prompt.strip()) for shot in storyboard.shots
        ),
        "all_character_references_valid": all(
            set(shot.character_ids)
            <= {character.id for character in screenplay.characters}
            for shot in storyboard.shots
        ),
        "shot_package_file": str(SHOT_FILE.relative_to(ROOT)),
        "bundle_file": str(BUNDLE_FILE.relative_to(ROOT)),
        "decision": "GO_WITH_ADAPTER_ONLY",
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {SUMMARY_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

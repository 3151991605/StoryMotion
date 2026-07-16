"""Generate and verify a strict ShotPackage with RuleShotProvider."""

from __future__ import annotations

import json
from pathlib import Path

from storymotion.models import (
    ProjectBrief,
    ScreenplayPackage,
    StoryMotionBundle,
    StoryPackage,
)
from storymotion.providers import RuleShotProvider


ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_DIR = ROOT / "outputs" / "verification"
OUTPUT_DIR = VERIFICATION_DIR / "rule_shots"
BRIEF_FILE = VERIFICATION_DIR / "minimax_m3_project_brief_run_01.json"
STORY_FILE = VERIFICATION_DIR / "story_graph" / "story_package.json"
SCREENPLAY_FILE = (
    VERIFICATION_DIR / "screenplay" / "screenplay_package_repaired.json"
)
SHOT_FILE = OUTPUT_DIR / "shot_package.json"
BUNDLE_FILE = OUTPUT_DIR / "storymotion_bundle.json"
SUMMARY_FILE = VERIFICATION_DIR / "rule_shot_provider_summary.json"


def main() -> int:
    brief = ProjectBrief.model_validate_json(BRIEF_FILE.read_text(encoding="utf-8"))
    story = StoryPackage.model_validate_json(STORY_FILE.read_text(encoding="utf-8"))
    screenplay = ScreenplayPackage.model_validate_json(
        SCREENPLAY_FILE.read_text(encoding="utf-8")
    )
    storyboard = RuleShotProvider(max_shot_duration=10).generate(screenplay)
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
        "provider": "RuleShotProvider",
        "network_requests": 0,
        "model_tokens": 0,
        "passed": True,
        "cross_layer_bundle_passed": True,
        "shot_count": len(storyboard.shots),
        "total_duration": storyboard.total_shot_duration,
        "maximum_shot_duration": max(shot.duration for shot in storyboard.shots),
        "scene_durations": scene_durations,
        "all_image_prompts_present": all(
            bool(shot.image_prompt.strip()) for shot in storyboard.shots
        ),
        "all_video_prompts_present": all(
            bool(shot.video_prompt.strip()) for shot in storyboard.shots
        ),
        "all_audio_prompts_present": all(
            bool(shot.audio_prompt and shot.audio_prompt.strip())
            for shot in storyboard.shots
        ),
        "shot_package_file": str(SHOT_FILE.relative_to(ROOT)),
        "bundle_file": str(BUNDLE_FILE.relative_to(ROOT)),
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {SUMMARY_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

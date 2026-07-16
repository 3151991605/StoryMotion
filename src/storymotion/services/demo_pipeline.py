from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from storymotion.models import (
    ProjectBrief,
    ScreenplayPackage,
    ShotPackage,
    StoryMotionBundle,
    StoryPackage,
)


class ShotProvider(Protocol):
    def generate(self, screenplay: ScreenplayPackage) -> ShotPackage: ...


class VideoProvider(Protocol):
    def render(self, package: ShotPackage, *, output_file: Path) -> Path: ...


@dataclass(frozen=True)
class DemoPipelineResult:
    bundle: StoryMotionBundle
    bundle_path: Path
    storyboard_path: Path
    video_path: Path


class DemoPipeline:
    def __init__(
        self,
        *,
        shot_provider: ShotProvider,
        video_provider: VideoProvider,
    ) -> None:
        self.shot_provider = shot_provider
        self.video_provider = video_provider

    def run(
        self,
        *,
        brief: ProjectBrief,
        story: StoryPackage,
        screenplay: ScreenplayPackage,
        output_dir: Path,
    ) -> DemoPipelineResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        storyboard = self.shot_provider.generate(screenplay)
        bundle = StoryMotionBundle(
            brief=brief,
            story=story,
            screenplay=screenplay,
            storyboard=storyboard,
        )

        bundle_path = output_dir / "storymotion_bundle.json"
        storyboard_path = output_dir / "shot_package.json"
        video_output_path = output_dir / "storymotion_mock.mp4"
        bundle_path.write_text(
            json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        storyboard_path.write_text(
            json.dumps(
                storyboard.model_dump(mode="json"), ensure_ascii=False, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        video_path = self.video_provider.render(
            storyboard,
            output_file=video_output_path,
        )
        return DemoPipelineResult(
            bundle=bundle,
            bundle_path=bundle_path,
            storyboard_path=storyboard_path,
            video_path=video_path,
        )

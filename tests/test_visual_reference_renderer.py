from __future__ import annotations

import base64
from pathlib import Path

from storymotion.models import GeneratedImage, StoryMotionBundle
from storymotion.services.visual_reference_renderer import VisualReferenceRenderer


class FakeImageProvider:
    def __init__(self) -> None:
        self.requests = []

    def generate(self, request, *, output_file: Path) -> GeneratedImage:
        self.requests.append(request)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(b"\x89PNG\r\n\x1a\n" + output_file.name.encode())
        return GeneratedImage(
            provider="fake",
            model="fake-image",
            request_id=f"image-{len(self.requests)}",
            path=output_file,
            media_type="image/png",
        )


def load_bundle() -> StoryMotionBundle:
    fixture = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"
    return StoryMotionBundle.model_validate_json(fixture.read_text(encoding="utf-8"))


def test_generates_reference_assets_for_every_character_scene_and_shot(tmp_path: Path) -> None:
    bundle = load_bundle()
    provider = FakeImageProvider()

    assets = VisualReferenceRenderer(provider).prepare(bundle, output_dir=tmp_path)

    assert set(assets.character_frames) == {item.id for item in bundle.story.characters}
    assert set(assets.character_turnarounds) == {
        item.id for item in bundle.story.characters
    }
    assert set(assets.scene_frames) == {item.scene_id for item in bundle.screenplay.scenes}
    assert set(assets.shot_frames) == {item.shot_id for item in bundle.storyboard.shots}
    assert all(path.is_file() for path in assets.shot_frames.values())
    assert len(provider.requests) == (
        len(bundle.story.characters)
        * 2
        + len(bundle.screenplay.scenes)
        + len(bundle.storyboard.shots)
    )
    character_count = len(bundle.story.characters)
    assert all(
        request.aspect_ratio == "1:1" for request in provider.requests[:character_count]
    )
    assert all(
        request.aspect_ratio == "3:4"
        for request in provider.requests[character_count : character_count * 2]
    )
    assert all(
        request.aspect_ratio == "9:16" for request in provider.requests[character_count * 2 :]
    )
    assert provider.requests[len(bundle.story.characters)].reference_image.startswith(
        "data:image/png;base64,"
    )
    assert all(
        request.seed is not None for request in provider.requests
    )
    assert provider.requests[-1].reference_image.startswith("data:image/png;base64,")
    first_keyframe = provider.requests[-1]
    primary_character = bundle.storyboard.shots[-1].character_ids[0]
    expected_turnaround = "data:image/png;base64," + base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + f"{primary_character}.png".encode()
    ).decode("ascii")
    assert first_keyframe.reference_image == expected_turnaround
    assert "turnaround model sheet is the sole character authority" in first_keyframe.prompt
    assert "turnaround model sheet is the sole authority" in provider.requests[
        character_count * 2
    ].prompt
    assert "sole identity authority" in provider.requests[0].prompt
    assert "Do not invent hats, glasses" in provider.requests[character_count].prompt
    assert "IDENTITY CONTRACT (must not change)" in provider.requests[-1].prompt
    assert (tmp_path / "visual_references" / "reference_manifest.json").is_file()


def test_reuses_existing_reference_assets_without_another_image_request(tmp_path: Path) -> None:
    bundle = load_bundle()
    provider = FakeImageProvider()
    renderer = VisualReferenceRenderer(provider)

    first = renderer.prepare(bundle, output_dir=tmp_path)
    requested = len(provider.requests)
    second = renderer.prepare(bundle, output_dir=tmp_path)

    assert len(provider.requests) == requested
    assert second == first

from __future__ import annotations

import base64
import json
from pathlib import Path

from storymotion.models import GeneratedImage, StoryMotionBundle
from storymotion.services.visual_reference_renderer import VisualReferenceRenderer


class FakeImageProvider:
    def __init__(self) -> None:
        self.requests = []

    def generate(self, request, *, output_file: Path) -> GeneratedImage:
        self.requests.append(request)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + f"{output_file.parent.name}/{output_file.name}".encode()
        )
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
    shots = list(bundle.storyboard.shots)
    shots[1] = shots[1].model_copy(
        update={
            "scene_id": shots[0].scene_id,
            "character_ids": shots[0].character_ids,
        }
    )
    bundle = bundle.model_copy(
        update={"storyboard": bundle.storyboard.model_copy(update={"shots": shots})}
    )
    provider = FakeImageProvider()

    assets = VisualReferenceRenderer(provider).prepare(bundle, output_dir=tmp_path)

    assert set(assets.character_frames) == {item.id for item in bundle.story.characters}
    assert set(assets.character_turnarounds) == {
        item.id for item in bundle.story.characters
    }
    assert assets.prop_frames == {}
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
    scene_count = len(bundle.screenplay.scenes)
    keyframe_requests = provider.requests[character_count * 2 + scene_count :]
    first_keyframe = keyframe_requests[0]
    primary_character = bundle.storyboard.shots[0].character_ids[0]
    expected_anchor = "data:image/png;base64," + base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + f"characters/{primary_character}.png".encode()
    ).decode("ascii")
    assert first_keyframe.reference_image == expected_anchor
    expected_second_anchor = "data:image/png;base64," + base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + f"characters/{primary_character}.png".encode()
    ).decode("ascii")
    assert keyframe_requests[1].reference_image == expected_second_anchor
    assert "IDENTITY CONTRACT" in first_keyframe.prompt
    assert "ACTING CONTRACT" in first_keyframe.prompt
    assert "COMPOSITION CONTRACT" in first_keyframe.prompt
    assert "AESTHETIC CONTRACT" in first_keyframe.prompt
    assert "strictly flat hand-drawn 2D cel animation" in first_keyframe.prompt
    assert "3D" not in first_keyframe.prompt
    assert "photoreal" not in first_keyframe.prompt.lower()
    assert "turnaround model sheet is the sole authority" in provider.requests[
        character_count * 2
    ].prompt
    assert "sole identity authority" in provider.requests[0].prompt
    assert "Do not invent hats, glasses" in provider.requests[character_count].prompt
    assert len(first_keyframe.prompt) <= 1500
    manifest = tmp_path / "visual_references" / "reference_manifest.json"
    assert manifest.is_file()
    assert json.loads(manifest.read_text(encoding="utf-8"))["pipeline_version"] == (
        VisualReferenceRenderer.PIPELINE_VERSION
    )


def test_identity_contract_excludes_temporary_expression_and_action() -> None:
    character = load_bundle().story.characters[0].model_copy(
        update={
            "visual_prompt_zh": (
                "黑色短发少年，深灰宗门服，左眼下浅色伤痕，"
                "表情惊恐地瞪大眼睛，正在回头看怪物"
            )
        }
    )

    contract = VisualReferenceRenderer._identity_contract(character)

    assert "黑色短发少年" in contract
    assert "表情惊恐" not in contract
    assert "正在回头" not in contract
    assert "closed appearance inventory" in contract
    assert "zero unlisted wearable items" in contract


def test_each_keyframe_has_an_independent_seed(tmp_path: Path) -> None:
    bundle = load_bundle()
    provider = FakeImageProvider()

    VisualReferenceRenderer(provider).prepare(bundle, output_dir=tmp_path)

    character_count = len(bundle.story.characters)
    scene_count = len(bundle.screenplay.scenes)
    keyframe_requests = provider.requests[character_count * 2 + scene_count :]
    assert len(keyframe_requests) >= 2
    assert len({request.seed for request in keyframe_requests}) == len(
        keyframe_requests
    )


def test_reuses_existing_reference_assets_without_another_image_request(tmp_path: Path) -> None:
    bundle = load_bundle()
    provider = FakeImageProvider()
    renderer = VisualReferenceRenderer(provider)

    first = renderer.prepare(bundle, output_dir=tmp_path)
    requested = len(provider.requests)
    second = renderer.prepare(bundle, output_dir=tmp_path)

    assert len(provider.requests) == requested
    assert second == first


def test_multi_reference_provider_receives_cast_scene_and_continuity_assets(
    tmp_path: Path,
) -> None:
    bundle = load_bundle()
    provider = FakeImageProvider()
    provider.max_reference_images = 9

    assets = VisualReferenceRenderer(provider).prepare(bundle, output_dir=tmp_path)

    character_count = len(bundle.story.characters)
    scene_count = len(bundle.screenplay.scenes)
    scene_requests = provider.requests[character_count * 2 : character_count * 2 + scene_count]
    keyframe_requests = provider.requests[character_count * 2 + scene_count :]
    assert all(request.reference_image is None for request in scene_requests)
    assert all(request.reference_images for request in scene_requests)
    assert keyframe_requests[0].reference_image is None
    assert len(keyframe_requests[0].reference_images) >= 3
    assert all(
        reference.startswith("data:image/png;base64,")
        for reference in keyframe_requests[0].reference_images
    )
    prior_keyframe = "data:image/png;base64," + base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + b"keyframes/shot_001.png"
    ).decode("ascii")
    assert all(
        prior_keyframe not in request.reference_images
        for request in keyframe_requests[1:]
    )
    manifest = json.loads(
        (tmp_path / "visual_references" / "reference_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["image_provider"] == "FakeImageProvider"
    assert set(assets.shot_frames) == {
        shot.shot_id for shot in bundle.storyboard.shots
    }


def test_generates_and_reuses_clean_prop_reference_in_relevant_shots(
    tmp_path: Path,
) -> None:
    data = json.loads(
        (
            Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"
        ).read_text(encoding="utf-8")
    )
    prop = {
        "id": "prop_phone",
        "name": "林辰的手机",
        "visual_description": "黑色窄边手机，透明裂纹保护壳，左上双摄",
        "continuity_features": ["透明裂纹保护壳", "左上双摄"],
        "aliases": ["手机"],
    }
    data["story"]["props"] = [prop]
    data["screenplay"]["props"] = [prop]
    data["screenplay"]["scenes"][0]["prop_ids"] = ["prop_phone"]
    for shot in data["storyboard"]["shots"]:
        if shot["scene_id"] == data["screenplay"]["scenes"][0]["scene_id"]:
            shot["prop_ids"] = ["prop_phone"]
    bundle = StoryMotionBundle.model_validate(data)
    provider = FakeImageProvider()
    provider.max_reference_images = 9

    assets = VisualReferenceRenderer(provider).prepare(bundle, output_dir=tmp_path)

    assert set(assets.prop_frames) == {"prop_phone"}
    assert assets.prop_frames["prop_phone"].is_file()
    character_count = len(bundle.story.characters)
    prop_request = provider.requests[character_count * 2]
    assert "PROP IDENTITY CONTRACT" in prop_request.prompt
    assert "透明裂纹保护壳" in prop_request.prompt
    scene_count = len(bundle.screenplay.scenes)
    keyframe_start = character_count * 2 + 1 + scene_count
    relevant_requests = [
        request
        for request, shot in zip(
            provider.requests[keyframe_start:], bundle.storyboard.shots
        )
        if "prop_phone" in shot.prop_ids
    ]
    expected_prop = "data:image/png;base64," + base64.b64encode(
        b"\x89PNG\r\n\x1a\n" + b"props/prop_phone.png"
    ).decode("ascii")
    assert relevant_requests
    assert all(
        expected_prop in request.reference_images for request in relevant_requests
    )

"""Create reusable visual assets before image-to-video rendering."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from storymotion.models import (
    GeneratedImage,
    ImageGenerationRequest,
    StoryMotionBundle,
)


class ImageProvider(Protocol):
    def generate(
        self, request: ImageGenerationRequest, *, output_file: Path
    ) -> GeneratedImage: ...


@dataclass(frozen=True)
class VisualReferenceAssets:
    """Persisted character, scene, and shot-first-frame assets."""

    character_frames: dict[str, Path]
    character_turnarounds: dict[str, Path]
    scene_frames: dict[str, Path]
    shot_frames: dict[str, Path]


class VisualReferenceRenderer:
    """Build a hierarchy of references so each video starts from a planned frame."""

    STYLE_CONTRACT = (
        "STYLE CONTRACT (immutable): premium 2D Chinese anime drama, cel shading, "
        "clean linework, controlled flat color palette, consistent proportions and line weight. "
        "Never photorealistic, live action, 3D render, painterly oil style, chibi, collage, "
        "text, subtitles, logo or watermark."
    )

    def __init__(self, provider: ImageProvider) -> None:
        self.provider = provider

    def prepare(
        self, bundle: StoryMotionBundle, *, output_dir: Path
    ) -> VisualReferenceAssets:
        root = Path(output_dir) / "visual_references"
        character_dir = root / "characters"
        turnaround_dir = root / "character_turnarounds"
        scene_dir = root / "scenes"
        keyframe_dir = root / "keyframes"

        characters = {character.id: character for character in bundle.story.characters}
        character_frames = {
            character.id: self._ensure_image(
                character_dir / f"{character.id}.png",
                ImageGenerationRequest(
                    prompt=(
                        "Identity anchor for image and video generation. Square 1:1, exactly one "
                        "character, tightly cropped from head to upper chest only; hands, arms and all "
                        "objects must be outside the frame. Straight-on face, both eyes visible, neutral "
                        "expression, even studio light, pure white seamless background. 2D anime "
                        "cel-shaded production art, clean linework, flat controlled colors; never "
                        "photorealistic, never live action. No text, no watermark, no props, no collage. "
                        "This image is the sole identity authority for all later assets. "
                        f"{self._identity_contract(character)} {self.STYLE_CONTRACT}"
                    )[:1500],
                    aspect_ratio="1:1",
                    seed=self._seed_for(character.id),
                ),
            )
            for character in bundle.story.characters
        }
        character_turnarounds = {
            character.id: self._ensure_image(
                turnaround_dir / f"{character.id}.png",
                ImageGenerationRequest(
                    prompt=(
                        "Character turnaround model sheet for animation production. Vertical 3:4, "
                        "one identical full-body character shown in a clean 2x2 layout: front view, "
                        "left three-quarter view, right three-quarter view, back view. Pure white "
                        "background, even light, same face, hairstyle, body proportions and exact "
                        "costume in every panel. 2D anime cel-shaded production art; never photorealistic. "
                        "No text, labels, props, extra characters or watermark. "
                        "Do not invent hats, glasses, jewellery, weapons, gloves, bags or new costume "
                        "layers. "
                        f"{self._identity_contract(character)} {self.STYLE_CONTRACT}"
                    )[:1500],
                    aspect_ratio="3:4",
                    reference_image=self._data_url(character_frames[character.id]),
                    seed=self._seed_for(f"{character.id}:turnaround"),
                ),
            )
            for character in bundle.story.characters
        }

        scenes = {scene.scene_id: scene for scene in bundle.screenplay.scenes}
        locations = {location.id: location for location in bundle.screenplay.locations}
        scene_frames: dict[str, Path] = {}
        for scene_id, scene in scenes.items():
            location = locations[scene.location_id]
            # A model sheet—not a face crop—is the source of truth for wardrobe, body
            # proportions and the 2D drawing language in all later production frames.
            reference = (
                character_turnarounds.get(scene.characters[0]) if scene.characters else None
            )
            cast = "; ".join(
                self._identity_contract(characters[character_id])
                for character_id in scene.characters
            )
            scene_frames[scene_id] = self._ensure_image(
                scene_dir / f"{scene_id}.png",
                ImageGenerationRequest(
                    prompt=(
                        "Scene visual reference, vertical 9:16. The supplied character turnaround model "
                        "sheet is the sole authority. Render one cinematic scene, never a model sheet or "
                        "photograph. Preserve its face, eye shape and colour, hairstyle, body proportions, "
                        "distinctive marks and complete wardrobe exactly. Do not add, remove "
                        "or swap accessories, costume layers, hats, glasses, jewellery, weapons, gloves "
                        "or bags unless already visible in that anchor. No text or watermark. "
                        f"{self.STYLE_CONTRACT} Preserve this location for later shots. "
                        f"Location={location.name}; environment={location.visual_description}; "
                        f"dramatic mood={scene.emotion}; staging goal={scene.scene_goal}; "
                        f"cast identity details={cast or 'no visible character'}."
                    )[:1500],
                    aspect_ratio="9:16",
                    reference_image=self._data_url(reference) if reference else None,
                    seed=self._seed_for(scene_id),
                ),
            )

        shot_frames = {
            shot.shot_id: self._ensure_image(
                keyframe_dir / f"{shot.shot_id}.png",
                ImageGenerationRequest(
                    prompt=(
                        "Shot first-frame keyframe. The supplied character turnaround model sheet is the "
                        "sole character authority. Transform that exact 2D model into one cinematic scene; "
                        "do not output a character sheet, photograph or live-action person. IDENTITY "
                        "CONTRACT (must not change): face geometry, eye shape and colour, "
                        "hairstyle, hair colour, body proportions, skin tone, distinctive marks, and every "
                        "visible wardrobe layer. Do not add/remove/swap hats, glasses, jewellery, weapons, "
                        "gloves, bags or costume layers unless already visible in the turnaround model. "
                        f"{self.STYLE_CONTRACT} Keep scene palette and setting stable. "
                        f"{shot.image_prompt}"
                    )[:1500],
                    aspect_ratio="9:16",
                    reference_image=self._data_url(
                        character_turnarounds[shot.character_ids[0]]
                        if shot.character_ids
                        else scene_frames[shot.scene_id]
                    ),
                    seed=self._seed_for(shot.shot_id),
                ),
            )
            for shot in bundle.storyboard.shots
        }
        assets = VisualReferenceAssets(
            character_frames, character_turnarounds, scene_frames, shot_frames
        )
        self._write_manifest(root / "reference_manifest.json", assets)
        return assets

    @staticmethod
    def _identity_contract(character: object) -> str:
        """Turn the story bible into an explicit, reusable no-change character spec."""
        # Character is intentionally structural here: this service only needs the public
        # story-model attributes and keeping it duck-typed makes fixture migration safe.
        appearance = character.appearance
        age_band = f"age={character.age}" if character.age is not None else "age=as shown"
        features = "; ".join(appearance.distinctive_features) or "none beyond the anchor"
        return (
            "IDENTITY CONTRACT (immutable): "
            f"name={character.name}; role={character.role}; {age_band}; "
            f"hair={appearance.hair}; wardrobe={appearance.clothing}; "
            f"distinctive_features={features}; canonical_design={character.visual_prompt_zh}. "
            "The reference anchor decides any unspecified face, eye, physique and skin details. "
            "No age, gender presentation, face, hairstyle, eye, body, wardrobe or signature-feature drift."
        )

    def _ensure_image(self, output_file: Path, request: ImageGenerationRequest) -> Path:
        if output_file.is_file() and output_file.stat().st_size > 0:
            return output_file
        artifact = self.provider.generate(request, output_file=output_file)
        return artifact.path

    @staticmethod
    def _data_url(path: Path) -> str:
        raw = Path(path).read_bytes()
        media_type = "image/png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"
        return f"data:{media_type};base64,{base64.b64encode(raw).decode('ascii')}"

    @staticmethod
    def _seed_for(identifier: str) -> int:
        """Keep each asset reproducible without coupling unrelated characters."""
        return int.from_bytes(identifier.encode("utf-8"), "little", signed=False) % 2_147_483_647

    @staticmethod
    def _write_manifest(path: Path, assets: VisualReferenceAssets) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "characters": {key: str(value) for key, value in assets.character_frames.items()},
            "character_turnarounds": {
                key: str(value) for key, value in assets.character_turnarounds.items()
            },
            "scenes": {key: str(value) for key, value in assets.scene_frames.items()},
            "shots": {key: str(value) for key, value in assets.shot_frames.items()},
        }
        temporary = path.with_suffix(".part")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

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
    prop_frames: dict[str, Path]
    scene_frames: dict[str, Path]
    shot_frames: dict[str, Path]


class VisualReferenceRenderer:
    """Build a hierarchy of references so each video starts from a planned frame."""

    PIPELINE_VERSION = "identity-prop-v5-clean-keyframes"

    AESTHETIC_CONTRACT = (
        "AESTHETIC CONTRACT: strictly flat hand-drawn 2D cel animation; polished Chinese animated "
        "drama production frame; refined adult character design; elegant facial proportions; clean "
        "ink contours; two-step matte cel shadows; controlled eye highlights; deliberate shape "
        "language; cinematic color script; simplified painted background; one coherent line weight; "
        "the exact same drawing language as the supplied reference."
    )

    def __init__(self, provider: ImageProvider) -> None:
        self.provider = provider

    def prepare(
        self, bundle: StoryMotionBundle, *, output_dir: Path
    ) -> VisualReferenceAssets:
        root = Path(output_dir) / "visual_references"
        character_dir = root / "characters"
        turnaround_dir = root / "character_turnarounds"
        prop_dir = root / "props"
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
                        f"{self._identity_contract(character)} {self.AESTHETIC_CONTRACT}"
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
                        f"{self._identity_contract(character)} {self.AESTHETIC_CONTRACT}"
                    )[:1500],
                    aspect_ratio="3:4",
                    **self._reference_inputs(
                        character_frames[character.id],
                        [character_frames[character.id]],
                    ),
                    seed=self._seed_for(f"{character.id}:turnaround"),
                ),
            )
            for character in bundle.story.characters
        }
        props = {prop.id: prop for prop in bundle.story.props}
        prop_frames = {
            prop.id: self._ensure_image(
                prop_dir / f"{prop.id}.png",
                ImageGenerationRequest(
                    prompt=(
                        "Production prop identity sheet, square 1:1, exactly one object shown in a "
                        "clean 2x2 layout: front, back, side and construction-detail view. Pure white "
                        "seamless background, even studio light, consistent scale and exact same "
                        "object in every panel. 2D anime cel-shaded production art matching the "
                        "project style. No hands, people, scenery, text, labels, logos, watermark or "
                        "duplicate objects. Any phone or display screen must remain blank. "
                        f"PROP IDENTITY CONTRACT: name={prop.name}; design={prop.visual_description}; "
                        f"immutable features={'; '.join(prop.continuity_features) or 'all visible design details'}. "
                        "Never change colour, material, silhouette, proportions, camera layout, case, "
                        "damage, attachments or signature marks in later scenes. "
                        f"{self.AESTHETIC_CONTRACT}"
                    )[:1500],
                    aspect_ratio="1:1",
                    seed=self._seed_for(prop.id),
                ),
            )
            for prop in bundle.story.props
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
            cast_references = [
                character_turnarounds[character_id]
                for character_id in scene.characters
                if character_id in character_turnarounds
            ]
            scene_prop_references = [
                prop_frames[prop_id]
                for prop_id in scene.prop_ids
                if prop_id in prop_frames
            ]
            cast = "; ".join(
                self._identity_contract(characters[character_id])
                for character_id in scene.characters
            )
            scene_props = "; ".join(
                f"{props[prop_id].name}={props[prop_id].visual_description}"
                for prop_id in scene.prop_ids
                if prop_id in props
            )
            if reference is None and scene_prop_references:
                reference = scene_prop_references[0]
            scene_frames[scene_id] = self._ensure_image(
                scene_dir / f"{scene_id}.png",
                ImageGenerationRequest(
                    prompt=(
                        "Scene visual reference, vertical 9:16. Each supplied character "
                        "turnaround model sheet is the sole authority for that cast member. "
                        "The sheets are ordered by the cast list. "
                        "Keep every referenced character separate. Render one cinematic scene, never a model sheet or "
                        "photograph. Preserve its face, eye shape and colour, hairstyle, body proportions, "
                        "distinctive marks and complete wardrobe exactly. Do not add, remove "
                        "or swap accessories, costume layers, hats, glasses, jewellery, weapons, gloves "
                        "or bags unless already visible in that anchor. No text or watermark. "
                        f"{self.AESTHETIC_CONTRACT} Preserve this location for later shots. "
                        f"Location={location.name}; environment={location.visual_description}; "
                        f"dramatic mood={scene.emotion}; staging goal={scene.scene_goal}; "
                        f"cast identity details={cast or 'no visible character'}; "
                        f"prop identity details={scene_props or 'no continuity-critical prop'}."
                    )[:1500],
                    aspect_ratio="9:16",
                    **self._reference_inputs(
                        reference, [*cast_references, *scene_prop_references]
                    ),
                    seed=self._seed_for(scene_id),
                ),
            )

        shot_frames: dict[str, Path] = {}
        for shot in bundle.storyboard.shots:
            primary_character_id = shot.character_ids[0] if shot.character_ids else None
            if primary_character_id is not None:
                reference = character_frames[primary_character_id]
            else:
                reference = scene_frames[shot.scene_id]
            multi_references: list[Path] = []
            if primary_character_id is not None:
                multi_references.append(character_frames[primary_character_id])
            multi_references.append(scene_frames[shot.scene_id])
            multi_references.extend(
                character_turnarounds[character_id]
                for character_id in shot.character_ids
                if character_id in character_turnarounds
            )
            multi_references.extend(
                prop_frames[prop_id]
                for prop_id in shot.prop_ids
                if prop_id in prop_frames
            )
            shot_frames[shot.shot_id] = self._ensure_image(
                keyframe_dir / f"{shot.shot_id}.png",
                ImageGenerationRequest(
                    prompt=self._keyframe_prompt(
                        shot,
                        characters=characters,
                        props=props,
                        scene=scenes[shot.scene_id],
                        location=locations[scenes[shot.scene_id].location_id],
                    ),
                    aspect_ratio="9:16",
                    # Every shot starts from clean canonical assets. Generated keyframes are
                    # deliberately excluded to prevent iterative texture/noise amplification.
                    **self._reference_inputs(reference, multi_references),
                    seed=self._seed_for(shot.shot_id),
                ),
            )
        assets = VisualReferenceAssets(
            character_frames=character_frames,
            character_turnarounds=character_turnarounds,
            prop_frames=prop_frames,
            scene_frames=scene_frames,
            shot_frames=shot_frames,
        )
        self._write_manifest(
            root / "reference_manifest.json",
            assets,
            pipeline_version=self.PIPELINE_VERSION,
            image_provider=type(self.provider).__name__,
        )
        return assets

    def _reference_inputs(
        self,
        single_reference: Path | None,
        multi_references: list[Path],
    ) -> dict[str, object]:
        """Use provider capabilities without weakening single-reference fallbacks."""
        maximum = int(getattr(self.provider, "max_reference_images", 1))
        if maximum <= 1:
            return {
                "reference_image": (
                    self._data_url(single_reference)
                    if single_reference is not None
                    else None
                )
            }
        unique: list[Path] = []
        for path in multi_references:
            path = Path(path)
            if path.is_file() and path not in unique:
                unique.append(path)
        return {
            "reference_images": [
                self._data_url(path) for path in unique[:maximum]
            ]
        }

    @staticmethod
    def _identity_contract(character: object) -> str:
        """Turn the story bible into an explicit, reusable no-change character spec."""
        # Character is intentionally structural here: this service only needs the public
        # story-model attributes and keeping it duck-typed makes fixture migration safe.
        appearance = character.appearance
        age_band = f"age={character.age}" if character.age is not None else "age=as shown"
        features = "; ".join(appearance.distinctive_features) or "none beyond the anchor"
        static_design = VisualReferenceRenderer._static_visual_design(
            character.visual_prompt_zh
        )
        return (
            "IDENTITY CONTRACT: "
            f"name={character.name}; role={character.role}; {age_band}; "
            f"hair={appearance.hair}; wardrobe={appearance.clothing}; "
            f"distinctive_features={features}; static_design={static_design}. "
            "Keep the exact reference face geometry, eyes, nose, lips, jaw, hairline, age, body, "
            "wardrobe and signature features; expression and pose are controlled separately. "
            "This is a closed appearance inventory: every frame contains exactly the listed hair, "
            "wardrobe and signature features, with zero unlisted wearable items or costume additions."
        )

    @staticmethod
    def _static_visual_design(description: str) -> str:
        """Remove temporary acting clauses from prose used as immutable identity."""
        markers = (
            "，表情",
            ",表情",
            ", expression",
            "，神情",
            ",神情",
            "，正在",
            ",正在",
            "，动作",
            ",动作",
        )
        end = len(description)
        for marker in markers:
            index = description.find(marker)
            if index >= 0:
                end = min(end, index)
        return description[:end].strip(" ，,。.;")

    def _keyframe_prompt(
        self,
        shot: object,
        *,
        characters: dict[str, object],
        props: dict[str, object],
        scene: object,
        location: object,
    ) -> str:
        """Render a compact prompt whose identity and acting instructions cannot conflict."""
        cast = self._clip(
            " | ".join(
                self._identity_contract(characters[character_id])
                for character_id in shot.character_ids
            )
            or "IDENTITY CONTRACT: no visible character",
            450,
        )
        prop_contract = self._clip(
            " | ".join(
                (
                    f"PROP IDENTITY CONTRACT: {props[prop_id].name}; "
                    f"design={props[prop_id].visual_description}; "
                    f"immutable={'; '.join(props[prop_id].continuity_features) or 'match supplied prop sheet exactly'}"
                )
                for prop_id in shot.prop_ids
                if prop_id in props
            )
            or "PROP IDENTITY CONTRACT: no continuity-critical prop",
            280,
        )
        contract = shot.keyframe_contract
        acting = self._clip(contract.start_keyframe, 150)
        action_direction = self._clip(contract.action, 110)
        visual = self._clip(shot.visual_description, 100)
        composition = self._clip(
            f"COMPOSITION CONTRACT: vertical 9:16 {shot.shot_type}; camera={shot.camera_movement}; "
            f"location={location.name}, {self._clip(location.visual_description, 90)}; "
            f"frame content={visual}.",
            240,
        )
        acting_contract = self._clip(
            "ACTING CONTRACT: first-frame emotional state="
            f"{acting}; performance direction={action_direction}. Make the emotion unmistakable through "
            "coordinated eyebrows, eyelids, gaze, pupils, mouth, jaw, head angle, shoulders, hands and "
            "body tension. Use a neutral face only when the stated emotion is neutral.",
            350,
        )
        prompt = " ".join(
            (
                "Single cinematic animation keyframe, not a model sheet or collage.",
                self._clip(self.AESTHETIC_CONTRACT, 300),
                cast,
                prop_contract,
                acting_contract,
                composition,
                f"Scene mood={scene.emotion}. Preserve the supplied face exactly.",
            )
        )
        return self._clip(prompt, 1500)

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        compact = " ".join(str(text).split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"

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
    def _write_manifest(
        path: Path,
        assets: VisualReferenceAssets,
        *,
        pipeline_version: str,
        image_provider: str,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pipeline_version": pipeline_version,
            "image_provider": image_provider,
            "characters": {key: str(value) for key, value in assets.character_frames.items()},
            "character_turnarounds": {
                key: str(value) for key, value in assets.character_turnarounds.items()
            },
            "props": {key: str(value) for key, value in assets.prop_frames.items()},
            "scenes": {key: str(value) for key, value in assets.scene_frames.items()},
            "shots": {key: str(value) for key, value in assets.shot_frames.items()},
        }
        temporary = path.with_suffix(".part")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

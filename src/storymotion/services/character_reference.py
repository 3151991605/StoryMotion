"""Generate and reuse a protagonist reference image for visual consistency."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from storymotion.models import Character, GeneratedImage, ImageGenerationRequest


class CharacterReferenceImageProvider(Protocol):
    def generate(
        self, request: ImageGenerationRequest, *, output_file: Path
    ) -> GeneratedImage: ...


def protagonist_reference_prompt(character: Character) -> str:
    """Describe one stable, full-body Chinese animation character sheet."""
    age = f"，{character.age}岁" if character.age is not None else ""
    features = "、".join(character.appearance.distinctive_features) or "无额外饰物"
    return (
        "中国都市动画短剧角色设定图，竖版全身单人肖像，正面站姿。"
        f"角色：{character.name}{age}；{character.visual_prompt_zh}。"
        f"发型：{character.appearance.hair}；服装：{character.appearance.clothing}；"
        f"标志特征：{features}。"
        "固定同一张脸、发型、服装和年龄；自然棚拍光，纯净中性背景，"
        "清晰五官和全身比例；不出现其他人物、文字、字幕、水印、标志。"
    )


class CharacterReferenceGenerator:
    """Creates one reusable protagonist reference asset, without regeneration."""

    def __init__(self, provider: CharacterReferenceImageProvider) -> None:
        self.provider = provider

    def generate(self, character: Character, *, output_dir: Path) -> GeneratedImage:
        output_file = Path(output_dir) / f"{character.id}_reference.jpg"
        if output_file.is_file():
            return GeneratedImage(
                provider="local-cache",
                model="character-reference",
                request_id=f"cached-{character.id}",
                path=output_file,
                media_type="image/jpeg",
            )
        return self.provider.generate(
            ImageGenerationRequest(
                prompt=protagonist_reference_prompt(character),
                aspect_ratio="2:3",
            ),
            output_file=output_file,
        )

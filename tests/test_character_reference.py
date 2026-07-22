from __future__ import annotations

from pathlib import Path

from storymotion.models import Character, GeneratedImage, ImageGenerationRequest
from storymotion.services import CharacterReferenceGenerator, protagonist_reference_prompt


def protagonist() -> Character:
    return Character.model_validate(
        {
            "id": "char_001",
            "name": "林夏",
            "role": "protagonist",
            "age": 24,
            "personality": ["执着"],
            "goal": "找出真相",
            "ability": None,
            "appearance": {
                "hair": "黑色短发",
                "clothing": "明黄色外卖制服",
                "distinctive_features": ["左眉浅痣"],
            },
            "visual_prompt_zh": "黑色短发青年，明黄色外卖制服，左眉浅痣",
            "visual_prompt_en": "young man in a yellow delivery uniform",
        }
    )


class RecordingImageProvider:
    def __init__(self) -> None:
        self.requests: list[ImageGenerationRequest] = []

    def generate(
        self, request: ImageGenerationRequest, *, output_file: Path
    ) -> GeneratedImage:
        self.requests.append(request)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(b"\xff\xd8\xff\xe0reference")
        return GeneratedImage(
            provider="test",
            model="test-image",
            request_id="reference-001",
            path=output_file,
            media_type="image/jpeg",
        )


def test_reference_prompt_fixes_visible_identity() -> None:
    prompt = protagonist_reference_prompt(protagonist())

    assert "林夏" in prompt
    assert "黑色短发" in prompt
    assert "明黄色外卖制服" in prompt
    assert "左眉浅痣" in prompt
    assert "不出现其他人物" in prompt


def test_reference_generator_reuses_existing_asset(tmp_path: Path) -> None:
    provider = RecordingImageProvider()
    generator = CharacterReferenceGenerator(provider)

    generated = generator.generate(protagonist(), output_dir=tmp_path)
    cached = generator.generate(protagonist(), output_dir=tmp_path)

    assert generated.path == tmp_path / "char_001_reference.jpg"
    assert cached.path == generated.path
    assert cached.provider == "local-cache"
    assert len(provider.requests) == 1
    assert provider.requests[0].aspect_ratio == "2:3"

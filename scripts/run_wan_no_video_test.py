"""Run StoryMotion from a fresh idea through all Wan visual assets, without video."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from storymotion.models import (
    GeneratedImage,
    ImageGenerationRequest,
    ProjectBrief,
    StoryMotionBundle,
)
from storymotion.providers import (
    OpenAICompatibleChatClient,
    RuleShotProvider,
    UrllibWanMediaTransport,
    WanImageProvider,
)
from storymotion.services import CreationPipeline, NarrativeGenerator, VisualReferenceRenderer

class ProgressImageProvider:
    """Expose Wan capabilities while printing one safe line per completed asset."""

    max_reference_images = 9

    def __init__(self, provider: WanImageProvider) -> None:
        self.provider = provider
        self.completed = 0

    def generate(
        self, request: ImageGenerationRequest, *, output_file: Path
    ) -> GeneratedImage:
        print(
            f"IMAGE_START file={output_file.name} references="
            f"{len(request.reference_images) + int(request.reference_image is not None)}",
            flush=True,
        )
        result = self.provider.generate(request, output_file=output_file)
        self.completed += 1
        print(
            f"IMAGE_DONE count={self.completed} file={result.path.name} "
            f"request_id={result.request_id}",
            flush=True,
        )
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--idea",
        default=(
            "雨夜里，年轻女法医沈知夏发现一段被删除的监控，画面中的搭档顾临川"
            "似乎提前知道受害者会出现；当她质问他时，停电的走廊尽头传来受害者的手机铃声。"
        ),
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    minimax_key = os.getenv("MINIMAX_API_KEY", "").strip()
    wan_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not minimax_key:
        raise RuntimeError("MINIMAX_API_KEY is not configured")
    if not wan_key:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured")

    output_dir = args.output_dir or ROOT / "outputs" / (
        "wan_complete_no_video_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_file = output_dir / "storymotion_bundle.json"
    if bundle_file.is_file():
        bundle = StoryMotionBundle.model_validate_json(
            bundle_file.read_text(encoding="utf-8")
        )
        print(
            f"TEXT_REUSE characters={len(bundle.story.characters)} "
            f"scenes={len(bundle.screenplay.scenes)} "
            f"shots={len(bundle.storyboard.shots)}",
            flush=True,
        )
    else:
        brief = ProjectBrief(
            genre="都市悬疑",
            style=["精致二维国漫", "电影感", "冷色雨夜"],
            protagonist_name="沈知夏",
            core_idea=args.idea,
            target_duration=15,
            max_characters=2,
            max_locations=1,
            ending_type="cliffhanger",
        )
        text_client = OpenAICompatibleChatClient(
            api_key=minimax_key,
            model=os.getenv("MINIMAX_TEXT_MODEL", "MiniMax-M2.7").strip(),
            base_url="https://api.minimaxi.com/v1",
            use_json_response_format=False,
            max_completion_tokens=8192,
            extra_payload={"reasoning_split": True},
            timeout_seconds=300.0,
        )
        print("TEXT_START provider=minimax", flush=True)
        bundle = CreationPipeline(
            narrative_generator=NarrativeGenerator(text_client),
            shot_provider=RuleShotProvider(max_shot_duration=6),
        ).create(brief)
        bundle_file.write_text(
            json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"TEXT_DONE characters={len(bundle.story.characters)} "
            f"scenes={len(bundle.screenplay.scenes)} "
            f"shots={len(bundle.storyboard.shots)}",
            flush=True,
        )

    wan = ProgressImageProvider(
        WanImageProvider(
            UrllibWanMediaTransport(
                api_key=wan_key,
                base_url=os.getenv(
                    "DASHSCOPE_API_HOST", "https://dashscope.aliyuncs.com"
                ),
            ),
            model=os.getenv("DASHSCOPE_IMAGE_MODEL", "wan2.7-image-pro").strip(),
        )
    )
    assets = VisualReferenceRenderer(wan).prepare(bundle, output_dir=output_dir)
    summary = {
        "text_provider": "minimax",
        "image_provider": "wan",
        "image_model": os.getenv("DASHSCOPE_IMAGE_MODEL", "wan2.7-image-pro"),
        "video_generated": False,
        "characters": len(assets.character_frames),
        "turnarounds": len(assets.character_turnarounds),
        "scenes": len(assets.scene_frames),
        "keyframes": len(assets.shot_frames),
        "total_images": wan.completed,
        "bundle": str(bundle_file),
        "manifest": str(
            output_dir / "visual_references" / "reference_manifest.json"
        ),
    }
    summary_file = output_dir / "test_summary.json"
    summary_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("TEST_SUCCESS " + json.dumps(summary, ensure_ascii=False), flush=True)
    print(f"OUTPUT_DIR={output_dir}", flush=True)


if __name__ == "__main__":
    main()

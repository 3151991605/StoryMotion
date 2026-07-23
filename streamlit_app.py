"""Interactive StoryMotion production console."""

from __future__ import annotations

import json
import os
import uuid
from hashlib import sha256
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from storymotion.models import ProjectBrief, StoryMotionBundle
from storymotion.providers import (
    HailuoVideoProvider,
    MiniMaxImageProvider,
    OpenAICompatibleChatClient,
    RuleShotProvider,
    TextGenerationError,
    UrllibWanMediaTransport,
    UrllibMiniMaxMediaTransport,
    WanImageProvider,
)
from storymotion.services import (
    CreationPipeline,
    HailuoVideoRenderer,
    NarrativeGenerator,
    VisualReferenceRenderer,
)


ROOT = Path(__file__).resolve().parent
SAMPLE_FILE = ROOT / "tests" / "fixtures" / "valid_storymotion_bundle.json"
LATEST_BUNDLE_FILE = ROOT / "outputs" / "latest_storymotion_bundle.json"
load_dotenv(ROOT / ".env")

st.set_page_config(page_title="StoryMotion", page_icon="🎬", layout="wide")
st.title("StoryMotion · AI 漫剧制作台")
st.caption("一句需求 → 小说 → 漫剧剧本 → 分镜与视频 Prompt。所有生成结果均会经过跨层协议校验。")


def configured_client() -> OpenAICompatibleChatClient | None:
    minimax_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if minimax_key:
        return OpenAICompatibleChatClient(
            api_key=minimax_key,
            model=os.getenv("MINIMAX_TEXT_MODEL", "MiniMax-M2.7").strip(),
            base_url="https://api.minimaxi.com/v1",
            use_json_response_format=False,
            max_completion_tokens=8192,
            extra_payload={"reasoning_split": True},
            timeout_seconds=300.0,
        )

    key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    if not key or not model:
        return None
    return OpenAICompatibleChatClient(
        api_key=key,
        model=model,
        base_url=os.getenv("LLM_API_BASE", "https://api.openai.com/v1"),
    )


def generate(brief: ProjectBrief) -> StoryMotionBundle:
    client = configured_client()
    if client is None:
        raise RuntimeError("缺少 LLM_API_KEY 或 MINIMAX_API_KEY；请检查 .env 配置。")
    return CreationPipeline(
        narrative_generator=NarrativeGenerator(client), shot_provider=RuleShotProvider(max_shot_duration=6)
    ).create(brief)


def save_latest_bundle(bundle: StoryMotionBundle) -> None:
    LATEST_BUNDLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LATEST_BUNDLE_FILE.write_text(
        json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_saved_bundle() -> Path | None:
    """Return the canonical saved bundle, or the most recent test output."""
    if LATEST_BUNDLE_FILE.is_file():
        return LATEST_BUNDLE_FILE

    candidates = sorted(
        ROOT.glob("outputs/*/storymotion_bundle.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def bundle_fingerprint(bundle: StoryMotionBundle) -> str:
    """Create a stable link between a story bundle and its rendered visual assets."""
    payload = json.dumps(
        bundle.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def save_bundle_copy(bundle: StoryMotionBundle, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "storymotion_bundle.json"
    path.write_text(
        json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def has_image_provider_config() -> bool:
    return bool(
        os.getenv("DASHSCOPE_API_KEY", "").strip()
        or os.getenv("MINIMAX_API_KEY", "").strip()
    )


def configured_image_provider() -> MiniMaxImageProvider | WanImageProvider:
    wan_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if wan_key:
        return WanImageProvider(
            UrllibWanMediaTransport(
                api_key=wan_key,
                base_url=os.getenv(
                    "DASHSCOPE_API_HOST", "https://dashscope.aliyuncs.com"
                ),
            ),
            model=os.getenv(
                "DASHSCOPE_IMAGE_MODEL", "wan2.7-image-pro"
            ).strip(),
        )
    image_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not image_key:
        raise RuntimeError(
            "Missing DASHSCOPE_API_KEY or MINIMAX_API_KEY; visual references require image quota."
        )
    return MiniMaxImageProvider(
        UrllibMiniMaxMediaTransport(
            api_key=image_key,
            base_url=os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com"),
        )
    )


def configured_image_provider_label() -> str:
    return "阿里万相 wan2.7-image-pro" if os.getenv(
        "DASHSCOPE_API_KEY", ""
    ).strip() else "MiniMax image-01"


def prepare_visual_references(bundle: StoryMotionBundle) -> Path:
    """Generate reusable visual assets only after an explicit UI action."""
    output_dir = (
        ROOT
        / "outputs"
        / "visual_reference_previews"
        / bundle_fingerprint(bundle)
        / VisualReferenceRenderer.PIPELINE_VERSION
    )
    VisualReferenceRenderer(configured_image_provider()).prepare(bundle, output_dir=output_dir)
    save_bundle_copy(bundle, output_dir)
    return output_dir


def load_visual_assets(bundle: StoryMotionBundle) -> tuple[dict[str, dict[str, Path]], Path | None]:
    """Load persisted assets belonging to this exact story, never unrelated outputs."""
    fingerprint = bundle_fingerprint(bundle)
    candidates: list[Path] = []
    session_dir = st.session_state.get("visual_reference_dir")
    if session_dir:
        candidates.append(Path(session_dir) / "visual_references" / "reference_manifest.json")
    candidates.append(
        ROOT / "outputs" / "visual_reference_previews" / fingerprint
        / VisualReferenceRenderer.PIPELINE_VERSION
        / "visual_references" / "reference_manifest.json"
    )
    for bundle_file in ROOT.glob("outputs/**/storymotion_bundle.json"):
        try:
            saved = StoryMotionBundle.model_validate_json(bundle_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if bundle_fingerprint(saved) == fingerprint:
            candidates.append(bundle_file.parent / "visual_references" / "reference_manifest.json")

    root = ROOT.resolve()
    for manifest in candidates:
        if not manifest.is_file():
            continue
        try:
            raw = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        assets: dict[str, dict[str, Path]] = {}
        for group in ("characters", "character_turnarounds", "props", "scenes", "shots"):
            values = raw.get(group, {})
            if not isinstance(values, dict):
                continue
            valid: dict[str, Path] = {}
            for asset_id, value in values.items():
                if not isinstance(asset_id, str) or not isinstance(value, str):
                    continue
                path = Path(value)
                try:
                    path.resolve().relative_to(root)
                except (OSError, ValueError):
                    continue
                if path.is_file():
                    valid[asset_id] = path
            if valid:
                assets[group] = valid
        if assets:
            return assets, manifest
    return {}, None


def generate_video(bundle: StoryMotionBundle, *, preview_only: bool = False) -> Path:
    key = os.getenv("MINIMAX_VIDEO_API_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少 MINIMAX_VIDEO_API_KEY，无法提交 Hailuo 视频任务。")
    provider = HailuoVideoProvider(
        UrllibMiniMaxMediaTransport(
            api_key=key,
            base_url=os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com"),
        )
    )
    image_provider = configured_image_provider()
    generated_root = ROOT / "outputs" / "generated"
    active_file = generated_root / "active_hailuo_job.json"
    if active_file.is_file():
        output_dir = Path(json.loads(active_file.read_text(encoding="utf-8"))["output_dir"])
    else:
        output_dir = generated_root / uuid.uuid4().hex
    package = bundle.storyboard
    if preview_only:
        first_shot = package.shots[0]
        package = package.model_copy(
            update={"target_duration": int(first_shot.duration), "shots": [first_shot]}
        )
    references = VisualReferenceRenderer(image_provider).prepare(
        bundle, output_dir=output_dir
    )
    save_bundle_copy(bundle, output_dir)
    st.session_state.visual_reference_dir = str(output_dir)
    return HailuoVideoRenderer(
        provider,
        image_provider=image_provider,
        character_references=references.character_frames,
    ).render(
        package,
        output_dir=output_dir,
        shot_keyframes=references.shot_frames,
    )


with st.sidebar:
    st.header("创意输入")
    idea = st.text_area("一句需求", placeholder="例如：外卖员发现每次差评都会让时间倒退十分钟", height=100)
    genre = st.text_input("类型", "都市奇幻")
    protagonist = st.text_input("主角名", "林夏")
    style = st.text_input("风格（用中文逗号分隔）", "悬疑，热血")
    duration = st.select_slider("成片时长（秒）", options=[15, 30, 45, 60, 90, 120, 180], value=60)
    can_generate = configured_client() is not None
    if not can_generate:
        st.warning("尚未配置文本模型 Key；可先查看内置样例。")
    if st.button("生成小说、剧本和分镜", type="primary", disabled=not can_generate):
        if not idea.strip():
            st.error("请先输入一句需求。")
        else:
            try:
                brief = ProjectBrief(
                    genre=genre.strip() or "短剧",
                    style=[item.strip() for item in style.replace("，", ",").split(",") if item.strip()] or ["电影感"],
                    protagonist_name=protagonist.strip() or "主角",
                    core_idea=idea.strip(),
                    target_duration=duration,
                )
                with st.spinner("编剧 Agent 正在创作并校验结构…"):
                    st.session_state.bundle = generate(brief)
                    save_latest_bundle(st.session_state.bundle)
                st.success("故事、剧本和分镜已生成。")
            except (RuntimeError, TextGenerationError, ValueError) as exc:
                st.error(f"生成失败：{exc}")
    if st.button("载入内置样例"):
        st.session_state.bundle = StoryMotionBundle.model_validate_json(SAMPLE_FILE.read_text(encoding="utf-8"))

bundle: StoryMotionBundle | None = st.session_state.get("bundle")
saved_bundle = find_saved_bundle()
if bundle is None and saved_bundle is not None:
    bundle = StoryMotionBundle.model_validate_json(saved_bundle.read_text(encoding="utf-8"))
    st.session_state.bundle = bundle
if bundle is None:
    st.info("在左侧输入一句创意开始；也可以载入样例查看最终交付格式。")
    st.stop()

st.subheader(bundle.story.title)
st.write(bundle.story.logline)
st.caption(f"{bundle.brief.genre} · {bundle.brief.target_duration} 秒 · {len(bundle.storyboard.shots)} 个镜头")

story_tab, screenplay_tab, shots_tab, visuals_tab, export_tab = st.tabs(
    ["小说", "漫剧剧本", "分镜", "视觉资产", "导出"]
)
with story_tab:
    st.markdown(bundle.story.story_text)
    st.subheader("角色设定")
    for character in bundle.story.characters:
        st.write(f"**{character.name}** · {character.role}：{character.goal}")

with screenplay_tab:
    for scene in bundle.screenplay.scenes:
        st.markdown(f"#### {scene.scene_id} · {scene.duration} 秒 · {scene.emotion}")
        st.write(scene.action)
        for dialogue in scene.dialogues:
            st.write(f"{dialogue.speaker_id}：{dialogue.text}")
        if scene.voiceover:
            st.caption(f"旁白：{scene.voiceover}")

with shots_tab:
    for shot in bundle.storyboard.shots:
        with st.expander(f"{shot.shot_id} · {shot.duration:g} 秒 · {shot.shot_type}"):
            st.write(shot.visual_description)
            st.code(shot.video_prompt, language="text")

with visuals_tab:
    st.subheader("角色与分镜视觉资产")
    assets, manifest = load_visual_assets(bundle)
    if assets:
        if manifest is not None:
            st.caption(f"已加载：{manifest.relative_to(ROOT)}")

        st.markdown("#### 角色建模")
        character_columns = st.columns(min(3, max(1, len(bundle.story.characters))))
        for index, character in enumerate(bundle.story.characters):
            with character_columns[index % len(character_columns)]:
                turnaround = assets.get("character_turnarounds", {}).get(character.id)
                anchor = assets.get("characters", {}).get(character.id)
                image = turnaround or anchor
                if image is not None:
                    st.image(str(image), use_container_width=True)
                    label = "多角度建模图" if turnaround else "身份锚点图"
                    st.caption(f"{character.name} · {label}")
                else:
                    st.info(f"{character.name} 暂无已保存的建模图。")

        prop_images = assets.get("props", {})
        if prop_images:
            st.markdown("#### 关键道具设定")
            prop_columns = st.columns(min(3, len(prop_images)))
            for index, prop in enumerate(bundle.story.props):
                image = prop_images.get(prop.id)
                if image is not None:
                    with prop_columns[index % len(prop_columns)]:
                        st.image(str(image), use_container_width=True)
                        st.caption(f"{prop.name} · 道具标准图")
                        st.caption(prop.visual_description)

        scene_images = assets.get("scenes", {})
        if scene_images:
            st.markdown("#### 场景参考图")
            scene_columns = st.columns(min(3, len(scene_images)))
            for index, scene in enumerate(bundle.screenplay.scenes):
                image = scene_images.get(scene.scene_id)
                if image is not None:
                    with scene_columns[index % len(scene_columns)]:
                        st.image(str(image), use_container_width=True)
                        st.caption(f"{scene.scene_id} · {scene.emotion}")

        shot_images = assets.get("shots", {})
        if shot_images:
            st.markdown("#### 分镜关键帧")
            shot_columns = st.columns(3)
            for index, shot in enumerate(bundle.storyboard.shots):
                image = shot_images.get(shot.shot_id)
                if image is not None:
                    with shot_columns[index % len(shot_columns)]:
                        st.image(str(image), use_container_width=True)
                        st.caption(f"{shot.shot_id} · {shot.duration:g} 秒")
                        st.caption(shot.visual_description)

        using_current_pipeline = (
            manifest is not None
            and VisualReferenceRenderer.PIPELINE_VERSION in manifest.parts
        )
        if not using_current_pipeline:
            st.warning(
                "当前展示的是旧版视觉资产；新版已加入关键道具锁定，并移除会产生雪花噪声的关键帧链式参考。"
            )
            regenerate = st.checkbox(
                f"我确认重新生成会消耗 {configured_image_provider_label()} 图片额度",
                key="confirm_visual_reference_upgrade",
            )
            if st.button(
                "按新版一致性流程重新生成",
                disabled=not (
                    has_image_provider_config() and regenerate
                ),
            ):
                try:
                    with st.spinner("正在按新版流程重建角色、道具、场景和关键帧…"):
                        st.session_state.visual_reference_dir = str(
                            prepare_visual_references(bundle)
                        )
                    st.rerun()
                except Exception as exc:
                    st.error(f"视觉资产重新生成失败：{exc}")
    else:
        st.info(
            "当前故事尚未生成视觉资产。生成后会在这里展示角色建模图、"
            "关键道具标准图、场景图和分镜关键帧。"
        )
        has_image_key = has_image_provider_config()
        confirmed = st.checkbox(
            f"我确认生成视觉资产会消耗 {configured_image_provider_label()} 图片额度",
            key="confirm_visual_references",
        )
        if st.button(
            "生成并展示视觉参考图",
            type="primary",
            disabled=not (has_image_key and confirmed),
        ):
            try:
                with st.spinner("正在生成角色、关键道具、场景参考图和分镜关键帧…"):
                    st.session_state.visual_reference_dir = str(prepare_visual_references(bundle))
                st.rerun()
            except Exception as exc:
                st.error(f"视觉资产生成失败：{exc}")
        if not has_image_key:
            st.warning("未配置 DASHSCOPE_API_KEY 或 MINIMAX_API_KEY，暂不能生成视觉资产。")

with export_tab:
    payload = json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2)
    st.download_button("下载完整制作包 JSON", payload, file_name="storymotion_bundle.json", mime="application/json")
    has_video_key = bool(os.getenv("MINIMAX_VIDEO_API_KEY", "").strip())
    has_image_key = has_image_provider_config()
    st.warning(
        f"整集将提交 {len(bundle.storyboard.shots)} 个海螺视频任务，并预先生成角色、场景和每个镜头的参考图。"
        "不要重复点击：运行中的任务会自动复用，不会再次提交。"
    )
    preview = st.checkbox("先只生成首镜预览（推荐，消耗 1 个视频任务）")
    confirmed = st.checkbox("我确认此次生成会消耗海螺视频额度")
    label = "生成首镜预览 MP4" if preview else "生成整集 Hailuo MP4"
    if st.button(
        label,
        type="primary",
        disabled=not (has_video_key and has_image_key and confirmed),
    ):
        try:
            with st.spinner("正在逐镜头生成并合成 MP4；海螺任务通常需要数分钟，请保持页面打开…"):
                st.session_state.video_path = generate_video(bundle, preview_only=preview)
            st.success("MP4 已生成。")
        except Exception as exc:
            st.error(f"视频生成失败：{exc}")
    if not has_video_key:
        st.warning("未配置 MINIMAX_VIDEO_API_KEY，暂不能生成海螺视频。")
    if not has_image_key:
        st.warning("未配置 DASHSCOPE_API_KEY 或 MINIMAX_API_KEY，无法生成逐镜头参考图。")
    video_path = st.session_state.get("video_path")
    if video_path and Path(video_path).is_file():
        st.video(str(video_path))
        st.download_button(
            "下载生成的 MP4",
            data=Path(video_path).read_bytes(),
            file_name="storymotion_hailuo.mp4",
            mime="video/mp4",
        )

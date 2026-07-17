"""Turn a story beat into an explicit, visible video-performance brief."""

from __future__ import annotations

from storymotion.models import ScreenplayPackage, ShotPackage, StoryPackage


def _beat_for_offset(story: StoryPackage, offset: float) -> str:
    elapsed = 0.0
    for beat in story.beats:
        elapsed += beat.duration
        if offset < elapsed:
            return beat.content
    return story.beats[-1].content


def direct_storyboard(
    story: StoryPackage, screenplay: ScreenplayPackage, storyboard: ShotPackage
) -> ShotPackage:
    """Make narrative cause and effect mandatory, not optional prompt flavor."""
    scenes = {scene.scene_id: scene for scene in screenplay.scenes}
    elapsed = 0.0
    directed = []
    for shot in storyboard.shots:
        scene = scenes[shot.scene_id]
        beat = _beat_for_offset(story, elapsed)
        elapsed += shot.duration
        visible_event = f"故事钩子：{story.logline}。当前转折：{beat}。场景动作：{scene.action}"
        image_prompt = (
            f"Vertical 9:16 cinematic Chinese anime drama keyframe. MUST visibly depict: {visible_event}. "
            f"{shot.image_prompt}. Show the causal event and its consequence in one readable composition, "
            "not a person passively looking at a prop. Dramatic lighting, coherent character design, no text."
        )[:4900]
        video_prompt = (
            f"竖屏 9:16 高品质中国动画短剧。必须清楚呈现且不可省略：{visible_event}。"
            f"镜头一开始，建立人物、道具和环境的因果关系；中段，{scene.action} 产生肉眼可见的变化；"
            f"结尾，角色对“{beat}”作出明确反应并定格在新的剧情状态。"
            "若手机、信件或屏幕出现，它只能作为触发器，必须紧接着展示事件后果，绝不能只拍人物看屏幕。"
            f"{shot.video_prompt}"
        )[:4900]
        directed.append(
            shot.model_copy(
                update={"image_prompt": image_prompt, "video_prompt": video_prompt}
            )
        )
    return storyboard.model_copy(update={"shots": directed})

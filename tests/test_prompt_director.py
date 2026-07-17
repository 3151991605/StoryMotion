from pathlib import Path

from storymotion.models import StoryMotionBundle
from storymotion.services import direct_storyboard


def test_makes_the_story_turn_visible_in_every_video_prompt() -> None:
    fixture = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"
    bundle = StoryMotionBundle.model_validate_json(fixture.read_text(encoding="utf-8"))
    directed = direct_storyboard(bundle.story, bundle.screenplay, bundle.storyboard)
    assert all("必须清楚呈现且不可省略" in shot.video_prompt for shot in directed.shots)
    assert all(bundle.story.logline in shot.video_prompt for shot in directed.shots)
    assert all("not a person passively looking at a prop" in shot.image_prompt for shot in directed.shots)

from __future__ import annotations

from dataclasses import dataclass

from storymotion.models import ProjectBrief, StoryMotionBundle
from storymotion.providers.rule_shot_provider import RuleShotProvider

from .narrative_generator import NarrativeGenerator
from .prompt_director import direct_storyboard


@dataclass(frozen=True)
class CreationPipeline:
    """The product's online path: brief -> narrative -> deterministic storyboard."""

    narrative_generator: NarrativeGenerator
    shot_provider: RuleShotProvider

    def create(self, brief: ProjectBrief) -> StoryMotionBundle:
        narrative = self.narrative_generator.generate(brief)
        storyboard = direct_storyboard(
            narrative.story,
            narrative.screenplay,
            self.shot_provider.generate(narrative.screenplay),
        )
        return StoryMotionBundle(
            brief=brief,
            story=narrative.story,
            screenplay=narrative.screenplay,
            storyboard=storyboard,
        )

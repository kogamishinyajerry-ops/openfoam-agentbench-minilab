"""Experience memory — the data flywheel.

Every diagnosed-and-repaired failure is mined into a reusable ExperienceRecord
and (when it represents a real regression) promoted to a guard case. Failures
stop being throw-away logs and become knowledge assets.
"""
from .store import ExperienceStore
from .case_miner import mine_experience

__all__ = ["ExperienceStore", "mine_experience"]

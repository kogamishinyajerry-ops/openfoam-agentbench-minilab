"""Demo orchestration — scenario builder + artifact seeding."""
from .replay_data import build_bundle, HERO_FAULT
from .seed_experiment import seed, run_experiment
from .real_evidence import capture_real_evidence
from .couette_evidence import capture_couette_evidence
from .pipe_evidence import capture_pipe_evidence

__all__ = [
    "build_bundle", "HERO_FAULT", "seed", "run_experiment",
    "capture_real_evidence", "capture_couette_evidence", "capture_pipe_evidence",
]

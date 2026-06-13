"""Runners — produce a RunResult for a (case, fault) state.

  * mock_runner     — synthesize from physics (no OpenFOAM, deterministic). The
                      engine the experiment uses to build the replay bundle.
  * replay_runner   — read a pre-generated RunResult from the data bundle.
  * openfoam_runner — execute a real OpenFOAM case in a Docker container and
                      parse the profile (optional; falls back to mock).
"""
from .mock_runner import build_run, run_synthetic, profile_model

__all__ = ["build_run", "run_synthetic", "profile_model"]

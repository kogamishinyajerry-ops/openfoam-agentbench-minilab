"""The generalisation thesis, asserted directly as a test.

The project's headline claim is that the benchmark is a *general method*, not a
one-case demo: the SAME unchanged diagnosis routes a fault correctly across
physically different flows. These tests feed runs from both the parabola
(Poiseuille) and the line (Couette) physics into the one `diagnose()` and check
the classifications agree with each flow's ground truth.
"""
from __future__ import annotations

import numpy as np

from ofab import physics
from ofab import physics_couette as pc
from ofab import physics_pipe as pp
from ofab.benchmark import diagnose
from ofab.models import (
    EngineeringStatus,
    ExecutionStatus,
    Fault,
    RunMode,
    RunResult,
    Workflow,
)


def _run(case_id: str, u, ref, feats_fn, *, residual: float = 6.0e-7) -> RunResult:
    u = np.asarray(u, dtype=float)
    ref = np.asarray(ref, dtype=float)
    qoi = physics.l2_relative_error(u, ref)
    feats = feats_fn(u, ref)
    return RunResult(
        run_id=f"gen_{case_id}",
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        case_id=case_id,
        fault=Fault.BC_MISMATCH,
        mode=RunMode.REPLAY,
        round_index=0,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=EngineeringStatus.NEEDS_REPAIR,
        qoi_error=round(float(qoi), 5),
        residual_final=residual,
        runtime_s=1.0,
        features={k: round(float(v), 5) for k, v in feats.items()},
    )


def test_same_diagnose_classifies_bc_fault_in_both_flows():
    """One diagnose(), two different flows -> both BC faults classified BC_MISMATCH
    from the wall-slip feature. This is the generalisation claim, as a test."""
    pois = _run(
        "channel_poiseuille",
        physics.failed_profile("bc_mismatch"),
        physics.analytical_profile(),
        physics.profile_features,
    )
    cou = _run(
        "couette_shear",
        pc.failed_profile(),
        pc.analytical_profile(),
        pc.couette_features,
    )
    assert diagnose(pois).failure_mode.value == "BC_MISMATCH"
    assert diagnose(cou).failure_mode.value == "BC_MISMATCH"


def test_same_diagnose_classifies_three_flows_including_a_different_fault():
    """The strongest form of the claim: one unchanged diagnose() over THREE flows,
    and the third heroes a *different* fault. Parabola(BC) + line(BC) both ->
    BC_MISMATCH; round-pipe radial parabola(coarse mesh) -> MESH_TOO_COARSE. The
    benchmark generalises across flows AND across failure modes."""
    pois = _run(
        "channel_poiseuille",
        physics.failed_profile("bc_mismatch"),
        physics.analytical_profile(),
        physics.profile_features,
    )
    cou = _run(
        "couette_shear", pc.failed_profile(), pc.analytical_profile(), pc.couette_features
    )
    pipe = _run(
        "pipe_poiseuille", pp.failed_profile(), pp.analytical_profile(), pp.pipe_features
    )
    assert diagnose(pois).failure_mode.value == "BC_MISMATCH"
    assert diagnose(cou).failure_mode.value == "BC_MISMATCH"
    assert diagnose(pipe).failure_mode.value == "MESH_TOO_COARSE"


def test_pipe_coarse_mesh_is_not_misread_as_bc():
    """The pipe-specific feature extractor matters: a radial mesh fault keeps the
    wall at no-slip (wall_slip ~ 0), so it must NOT trip the BC gate — it has to
    route to MESH_TOO_COARSE from the clipped peak / faceting."""
    pipe = _run(
        "pipe_poiseuille", pp.failed_profile(), pp.analytical_profile(), pp.pipe_features
    )
    d = diagnose(pipe)
    assert d.failure_mode.value == "MESH_TOO_COARSE"
    assert d.failure_mode.value != "BC_MISMATCH"


def test_same_diagnose_passes_clean_runs_in_both_flows():
    """The correct solution of each flow (parabola / line) is judged NONE by the
    same function — no false positives across cases."""
    pois = _run(
        "channel_poiseuille",
        physics.analytical_profile(),
        physics.analytical_profile(),
        physics.profile_features,
    )
    cou = _run(
        "couette_shear",
        pc.analytical_profile(),
        pc.analytical_profile(),
        pc.couette_features,
    )
    assert diagnose(pois).failure_mode.value == "NONE"
    assert diagnose(cou).failure_mode.value == "NONE"


def test_couette_bc_fault_is_not_misread_as_mesh():
    """The Couette-specific feature extractor matters: a linear BC fault must not
    trip the mesh gate (peak_deficit / curvature stay ~0 for a line)."""
    cou = _run(
        "couette_shear",
        pc.failed_profile(),
        pc.analytical_profile(),
        pc.couette_features,
    )
    d = diagnose(cou)
    assert d.failure_mode.value == "BC_MISMATCH"
    assert d.failure_mode.value != "MESH_TOO_COARSE"


def test_experience_recall_is_case_independent(tmp_path):
    """The 错题本 (experience store) is keyed by failure MODE, not case — so a
    lesson learned on one flow is recalled for the same failure mode on a
    *different* flow. The core BC fix (restore no-slip) genuinely applies to both
    a pressure-driven channel and a shear-driven Couette, since both have a
    no-slip wall. This is the experience flywheel transferring across cases."""
    from ofab.memory.case_miner import mine_experience
    from ofab.memory.store import ExperienceStore
    from ofab.models import Diagnosis, FailureMode

    store = ExperienceStore(tmp_path / "exp.jsonl")
    # a BC_MISMATCH lesson sedimented on the hero (Poiseuille) case
    diag = Diagnosis(
        run_id="hero_bc",
        failure_mode=FailureMode.BC_MISMATCH,
        confidence=0.83,
        evidence=[],
        suggested_repair=["恢复 no-slip"],
    )
    store.append(
        mine_experience(
            diag, Fault.BC_MISMATCH, qoi_before=0.18, qoi_after=0.02,
            case_id="channel_poiseuille",
        )
    )

    # a DIFFERENT flow (Couette) hits the same failure mode -> recalls the lesson
    recalled = store.recall(FailureMode.BC_MISMATCH)
    assert recalled is not None
    assert recalled.case_id == "channel_poiseuille"   # learned on case 1
    assert "no-slip" in recalled.repair               # transferable core fix
    # a mode never sedimented returns nothing — no spurious cross-mode transfer
    assert store.recall(FailureMode.MESH_TOO_COARSE) is None

"""Contract + reference-CSV locks for BOTH cases (hero parabola + Couette line).

The ``benchmarks/contracts/*.yaml`` files and their ``benchmarks/references/*.csv``
answer keys are the human-inspectable "标准答案 / 合格线" for each case. They must
not silently drift from what the code actually enforces (the shared tolerances in
``config.py``) nor from the physics that produces the reference solution. These
tests turn those documents into *verified artifacts*:

  1. every contract YAML parses, and ``BenchmarkContract.load()`` reads it back
     self-consistently (case_id / qoi name / tolerances / reference path);
  2. each YAML's tolerances are byte-for-byte the shared config tolerances — the
     documented bar == the enforced bar, for both flows (case-agnostic judging);
  3. each reference CSV reproduces that case's *derived* analytical profile
     (parabola via ``physics``; line via ``physics_couette``) — the answer key is
     locked to the physics, not hand-typed.
"""
from __future__ import annotations

import csv

import numpy as np
import pytest
import yaml

from ofab import config, physics
from ofab import physics_couette as pc
from ofab.benchmark import BenchmarkContract
from ofab.paths import CONTRACTS_DIR, REFERENCES_DIR

# (case_id, contract yaml, reference csv, derived analytical profile) for each flow.
CASES = [
    ("channel_poiseuille", "channel_poiseuille.yaml",
     "channel_poiseuille_reference.csv", physics.analytical_profile()),
    ("couette_shear", "couette_shear.yaml",
     "couette_shear_reference.csv", pc.analytical_profile()),
]
CASE_IDS = [c[0] for c in CASES]


@pytest.fixture(params=CASES, ids=CASE_IDS)
def case(request):
    case_id, yaml_name, csv_name, analytical = request.param
    return {
        "case_id": case_id,
        "yaml": CONTRACTS_DIR / yaml_name,
        "csv": REFERENCES_DIR / csv_name,
        "csv_name": csv_name,
        "analytical": np.asarray(analytical, dtype=float),
    }


def test_contract_yaml_parses_and_loads_self_consistently(case):
    """The YAML is well-formed and the real loader reads it back with the right
    case_id, QoI name and reference path."""
    assert case["yaml"].is_file(), f"missing contract {case['yaml']}"
    contract = BenchmarkContract.load(case["yaml"])
    assert contract.case_id == case["case_id"]
    assert contract.qoi_name == "velocity_profile_l2_error"
    assert contract.reference_csv.endswith(case["csv_name"])


def test_contract_tolerances_equal_shared_config(case):
    """The documented合格线 == the enforced bar. Both flows share ONE tolerance
    triple (this is what lets the unchanged benchmark judge either flow)."""
    data = yaml.safe_load(case["yaml"].read_text())
    tol = data["tolerances"]
    assert float(tol["qoi_l2"]) == config.QOI_L2_TOL
    assert float(tol["residual"]) == config.RESIDUAL_TOL
    assert float(tol["wall_slip"]) == config.WALL_SLIP_TOL
    assert data["qoi"]["n_points"] == config.N_PROFILE_POINTS


def test_reference_csv_reproduces_derived_analytical(case):
    """The answer key on disk is the physics, not a hand-typed table: the CSV's
    u column equals the case's derived analytical profile, sampled at the same
    wall-normal stations (y/H linspace, y_m = y/H * H)."""
    with case["csv"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == config.N_PROFILE_POINTS  # 41 stations

    y_over_h = np.array([float(r["y_over_H"]) for r in rows])
    y_m = np.array([float(r["y_m"]) for r in rows])
    u = np.array([float(r["u_analytical_ms"]) for r in rows])

    yn = np.linspace(0.0, 1.0, config.N_PROFILE_POINTS)
    assert np.allclose(y_over_h, yn, atol=1e-9)
    assert np.allclose(y_m, yn * config.CHANNEL_HEIGHT, atol=1e-9)  # both H = 0.01
    # the locked claim: CSV answer key == derived analytical profile
    assert np.allclose(u, case["analytical"], atol=1e-6)


def test_couette_reference_is_linear_and_hero_is_curved():
    """Guard the two answer keys are genuinely the two different physics: the
    Couette key is a straight line (2nd difference ~0), the hero key is a curved
    parabola (clearly non-zero curvature). If these ever collapse to the same
    shape, the 'generalises to a different flow' claim is hollow."""
    cou = np.array([float(r["u_analytical_ms"])
                    for r in csv.DictReader((REFERENCES_DIR / "couette_shear_reference.csv").open())])
    hero = np.array([float(r["u_analytical_ms"])
                     for r in csv.DictReader((REFERENCES_DIR / "channel_poiseuille_reference.csv").open())])
    assert float(np.max(np.abs(np.diff(cou, n=2)))) < 1e-9          # line
    assert float(np.max(np.abs(np.diff(hero, n=2)))) > 1e-4         # parabola

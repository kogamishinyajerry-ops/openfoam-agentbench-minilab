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
from ofab import physics_pipe as pp
from ofab.benchmark import BenchmarkContract
from ofab.paths import CONTRACTS_DIR, REFERENCES_DIR

# Per-case answer-key spec: the contract YAML, the reference CSV (with its coordinate
# column names + physical length scale), and the derived analytical profile. Each flow
# uses geometry-appropriate columns — wall-normal y for the channel/Couette, radial r
# for the pipe — so the test reads them per case rather than assuming one naming.
CASES = [
    dict(case_id="channel_poiseuille", yaml="channel_poiseuille.yaml",
         csv="channel_poiseuille_reference.csv", coord_col="y_over_H", phys_col="y_m",
         length_scale=config.CHANNEL_HEIGHT, analytical=physics.analytical_profile(),
         shape="curved"),
    dict(case_id="couette_shear", yaml="couette_shear.yaml",
         csv="couette_shear_reference.csv", coord_col="y_over_H", phys_col="y_m",
         length_scale=config.COUETTE_HEIGHT, analytical=pc.analytical_profile(),
         shape="line"),
    dict(case_id="pipe_poiseuille", yaml="pipe_poiseuille.yaml",
         csv="pipe_poiseuille_reference.csv", coord_col="r_over_R", phys_col="r_m",
         length_scale=config.PIPE_RADIUS, analytical=pp.analytical_profile(),
         shape="curved"),
]
CASE_IDS = [c["case_id"] for c in CASES]


@pytest.fixture(params=CASES, ids=CASE_IDS)
def case(request):
    c = dict(request.param)
    c["yaml"] = CONTRACTS_DIR / c["yaml"]
    c["csv_name"] = c["csv"]
    c["csv"] = REFERENCES_DIR / c["csv"]
    c["analytical"] = np.asarray(c["analytical"], dtype=float)
    return c


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
    stations (normalized coord linspace, physical coord = normalized * length scale).
    Geometry-appropriate columns per case (y for channel/Couette, r for the pipe)."""
    with case["csv"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == config.N_PROFILE_POINTS  # 41 stations

    coord = np.array([float(r[case["coord_col"]]) for r in rows])
    phys = np.array([float(r[case["phys_col"]]) for r in rows])
    u = np.array([float(r["u_analytical_ms"]) for r in rows])

    xn = np.linspace(0.0, 1.0, config.N_PROFILE_POINTS)
    assert np.allclose(coord, xn, atol=1e-9)
    assert np.allclose(phys, xn * case["length_scale"], atol=1e-9)
    # the locked claim: CSV answer key == derived analytical profile
    assert np.allclose(u, case["analytical"], atol=1e-6)


def test_reference_shapes_are_genuinely_different_physics():
    """Guard the three answer keys are genuinely different physics: Couette is a
    straight line (2nd difference ~0); the channel and pipe are curved parabolas
    (clearly non-zero curvature). If these ever collapse to the same shape, the
    'generalises to different flows' claim is hollow."""
    def u_col(name):
        return np.array([float(r["u_analytical_ms"])
                         for r in csv.DictReader((REFERENCES_DIR / name).open())])
    cou = u_col("couette_shear_reference.csv")
    hero = u_col("channel_poiseuille_reference.csv")
    pipe = u_col("pipe_poiseuille_reference.csv")
    assert float(np.max(np.abs(np.diff(cou, n=2)))) < 1e-9          # line
    assert float(np.max(np.abs(np.diff(hero, n=2)))) > 1e-4         # channel parabola
    assert float(np.max(np.abs(np.diff(pipe, n=2)))) > 1e-4         # pipe radial parabola

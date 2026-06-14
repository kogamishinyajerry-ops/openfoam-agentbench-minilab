"""Real OpenFOAM runner for the third case (round-pipe Hagen–Poiseuille).

The pipe is the project's first genuinely curved geometry, so it is solved as an
**axisymmetric wedge**: a thin 5° (±2.5°) slice about the streamwise x-axis whose
inner radial edge collapses onto the pipe axis. A uniform inlet velocity develops,
over the pipe length, into the exact steady radial parabola
``u(r) = u_max (1 − (r/R)²)`` with ``u_max = 2·U_mean`` (the round-pipe relation,
vs the channel's 1.5·U_mean) — the analytical answer key the benchmark scores against.

Geometry/stability notes that make the wedge actually run (validated against the
live ESI 2312 container):
  - **Collapsed-edge wedge** — only 6 unique vertices; the two axis vertices are
    *shared* by the front and back faces (repeated indices in the hex), so the axis
    edge is truly zero-length and no degenerate zero-area faces leak into
    ``defaultFaces`` (which would fail checkMesh and crash icoFoam).
  - **Adaptive time-stepping** — the wedge cells next to the axis are tiny, so a
    fixed ``deltaT`` blows the Courant number up into an FPE. ``adjustTimeStep`` with
    ``maxCo 0.5`` keeps it stable.

The pipe's HERO fault is ``coarse_mesh``: a curved radial parabola is exactly what a
too-coarse radial mesh clips (peak flattened, curve faceted) — the mirror of Couette,
where the same fault is *not applicable* (a line is exact on any mesh). The benchmark
layer (build_scorecard / diagnose) is unchanged and case-agnostic.

Same non-destructive pattern as the other runners: a fresh case is copied into the
container's ``/tmp`` under a unique name, run, copied back, and removed. The correct
run is **self-validating** — it must reproduce the analytical parabola within
tolerance (QoI → ~0), or we never ship the number.
"""
from __future__ import annotations

import math
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

from .. import config
from .. import physics_pipe as pp
from ..models import (
    EngineeringStatus,
    ExecutionStatus,
    Fault,
    RunMode,
    RunResult,
    VelocityProfile,
    Workflow,
)
from ..paths import RUNS_DIR
from .openfoam_runner import (
    OpenFOAMUnavailable,
    _docker,
    _parse_profile,
    _parse_residual,
    detect_container,
)

# Wedge half-angle (total wedge = 5°, the OpenFOAM-recommended axisymmetric slice).
_WEDGE_DEG = 2.5
_THETA = math.radians(_WEDGE_DEG)
# Wall vertex coordinates: the wall sits at radius R, split ±_S in z about the
# centre-plane. The y-coordinate of the wall is R·cosθ (slightly < R), which is the
# physical wall radius we normalise the sampled profile by.
_WALL_Y = config.PIPE_RADIUS * math.cos(_THETA)
_WALL_Z = config.PIPE_RADIUS * math.sin(_THETA)

# The injected coarse radial mesh for the HERO fault. Tuned against the live solver so
# the under-resolved curved parabola is a clean false success (L2 above the 5% bar,
# still converged, no-slip intact) that diagnoses MESH_TOO_COARSE — distinct from the
# fine mesh's ~0.3%. (The synthetic path uses its own PIPE_COARSE_NCELLS cell-average
# model; the real solver's coarse count is independent and lives here.)
# Swept against the live solver: nr=4 -> ~7.5% L2 (a subtle false success just over the
# 5% bar — mirrors the synthetic ~7.9% and makes the "looks-almost-right" point),
# diagnosed MESH_TOO_COARSE at 88% with no spurious wall slip.
_REAL_COARSE_NR = 4
# The streamwise/radial resolution of a correctly-resolved pipe.
_FINE_NR = 40
_NX = 60
# Axial wall speed realising the BC fault (a no-slip violation: the pipe wall is set
# moving downstream instead of stationary) — same class as the hero case's bc fault.
_FAULT_WALL_SPEED = 0.05


def _pipe_params(fault: Fault, repaired: bool) -> dict:
    """Mesh / BC / control knobs implementing each state of the pipe case."""
    p = dict(nr=_FINE_NR, nx=_NX, end_time=6.0, wall_type="noSlip")
    if repaired:
        return p  # refined radial mesh, no-slip restored -> resolves the parabola
    if fault == Fault.BC_MISMATCH:
        p["wall_type"] = "moving"          # pipe wall set moving (no-slip violated)
    elif fault == Fault.COARSE_MESH:
        p["nr"] = _REAL_COARSE_NR          # under-resolved radial mesh (the hero)
    elif fault == Fault.SOLVER_SETTING_ERROR:
        p["end_time"] = 0.01               # stop long before the flow develops
    return p


def _hdr(cls: str, obj: str, loc: str) -> str:
    return (
        "FoamFile\n{\n    version 2.0;\n    format ascii;\n"
        f"    class {cls};\n    location \"{loc}\";\n    object {obj};\n}}\n"
    )


def generate_pipe_case(case_dir: Path, fault: Fault, repaired: bool) -> None:
    R = config.PIPE_RADIUS
    L = config.PIPE_LENGTH
    U = config.PIPE_MEAN_VELOCITY
    nu = config.PIPE_KINEMATIC_VISCOSITY
    c, s = _WALL_Y, _WALL_Z
    fp = _pipe_params(fault, repaired)
    nr, nx, end_time, wall_type = fp["nr"], fp["nx"], fp["end_time"], fp["wall_type"]
    x_sample = 0.95 * L

    for sub in ("0", "constant", "system"):
        (case_dir / sub).mkdir(parents=True, exist_ok=True)

    # ---- blockMeshDict: collapsed-edge axisymmetric wedge ------------------
    # 6 unique vertices; axis points (0,1) shared by front/back so the axis edge is
    # zero-length (no degenerate faces). hex (0 1 2 3 0 1 4 5): dir1=x, dir2=radius,
    # dir3=wedge(1 cell). inlet/outlet are triangles (a repeated axis vertex).
    verts = [
        (0, 0, 0),     # 0  inlet axis
        (L, 0, 0),     # 1  outlet axis
        (L, c, -s),    # 2  outlet wall, back (z<0)
        (0, c, -s),    # 3  inlet wall, back
        (L, c, s),     # 4  outlet wall, front (z>0)
        (0, c, s),     # 5  inlet wall, front
    ]
    vtxt = "\n".join(f"    ({x} {y} {z})" for x, y, z in verts)
    blockmesh = (
        _hdr("dictionary", "blockMeshDict", "system")
        + f"scale 1;\n\nvertices\n(\n{vtxt}\n);\n\n"
        + f"blocks\n(\n    hex (0 1 2 3 0 1 4 5) ({nx} {nr} 1) simpleGrading (1 1 1)\n);\n\n"
        + "edges ();\n\n"
        + "boundary\n(\n"
        + "    inlet { type patch; faces ( (0 0 5 3) ); }\n"
        + "    outlet { type patch; faces ( (1 2 4 1) ); }\n"
        + "    wall { type wall; faces ( (3 2 4 5) ); }\n"
        + "    back { type wedge; faces ( (0 3 2 1) ); }\n"
        + "    front { type wedge; faces ( (0 1 4 5) ); }\n"
        + ");\n\nmergePatchPairs ();\n"
    )
    (case_dir / "system" / "blockMeshDict").write_text(blockmesh)

    # ---- controlDict (adaptive stepping + radial sampling on the centre-plane) ----
    control = (
        _hdr("dictionary", "controlDict", "system")
        + "application icoFoam;\nstartFrom startTime;\nstartTime 0;\n"
        + f"stopAt endTime;\nendTime {end_time};\ndeltaT 1e-4;\n"
        + f"writeControl adjustableRunTime;\nwriteInterval {end_time};\npurgeWrite 0;\n"
        + "writeFormat ascii;\nwritePrecision 8;\nwriteCompression off;\n"
        + "timeFormat general;\ntimePrecision 6;\nrunTimeModifiable true;\n"
        + "adjustTimeStep yes;\nmaxCo 0.5;\nmaxDeltaT 0.01;\n\n"
        + "functions\n{\n    profile\n    {\n        type sets;\n"
        + "        libs (\"libsampling.so\");\n        writeControl writeTime;\n"
        + "        interpolationScheme cellPoint;\n        setFormat raw;\n"
        + "        fields ( U );\n        sets\n        (\n            line\n            {\n"
        + "                type uniform;\n                axis y;\n"
        + f"                start ( {x_sample} 0 0 );\n"
        + f"                end ( {x_sample} {c} 0 );\n"
        + f"                nPoints {config.N_PROFILE_POINTS};\n            }}\n        );\n    }}\n"
        # Area-averaged wall velocity, measured from the solution's wall patch. On a
        # coarse radial mesh the interior line-sample over-reads the wall (cellPoint
        # extrapolates the last big cell instead of reaching the enforced boundary),
        # so we anchor the profile's wall point to this faithful patch measurement —
        # 0 for a no-slip wall, the injected speed for the bc fault.
        + "    wallU\n    {\n        type surfaceFieldValue;\n"
        + "        libs (\"libfieldFunctionObjects.so\");\n        writeControl writeTime;\n"
        + "        writeFields false;\n        log false;\n        regionType patch;\n"
        + "        name wall;\n        operation areaAverage;\n        fields ( U );\n    }\n}\n"
    )
    (case_dir / "system" / "controlDict").write_text(control)

    # ---- fvSchemes ---------------------------------------------------------
    (case_dir / "system" / "fvSchemes").write_text(
        _hdr("dictionary", "fvSchemes", "system")
        + "ddtSchemes { default Euler; }\n"
        + "gradSchemes { default Gauss linear; }\n"
        + "divSchemes { default none; div(phi,U) Gauss linear; }\n"
        + "laplacianSchemes { default Gauss linear orthogonal; }\n"
        + "interpolationSchemes { default linear; }\n"
        + "snGradSchemes { default orthogonal; }\n"
    )

    # ---- fvSolution --------------------------------------------------------
    (case_dir / "system" / "fvSolution").write_text(
        _hdr("dictionary", "fvSolution", "system")
        + "solvers\n{\n    p\n    {\n        solver PCG; preconditioner DIC;\n"
        + "        tolerance 1e-08; relTol 0.01;\n    }\n"
        + "    pFinal\n    {\n        $p; relTol 0;\n    }\n"
        + "    U\n    {\n        solver smoothSolver; smoother symGaussSeidel;\n"
        + "        tolerance 1e-08; relTol 0;\n    }\n}\n\n"
        + "PISO\n{\n    nCorrectors 2;\n    nNonOrthogonalCorrectors 0;\n"
        + "    pRefCell 0;\n    pRefValue 0;\n}\n"
    )

    # ---- constant/transportProperties -------------------------------------
    (case_dir / "constant" / "transportProperties").write_text(
        _hdr("dictionary", "transportProperties", "constant")
        + f"nu [0 2 -1 0 0 0 0] {nu};\n"
    )

    # ---- 0/U ---------------------------------------------------------------
    # Uniform inlet velocity develops into the parabola; wall is no-slip unless the
    # BC fault sets it moving (an axial wall speed -> a clean no-slip violation).
    if wall_type == "moving":
        wall_u = f"    wall {{ type fixedValue; value uniform ({_FAULT_WALL_SPEED} 0 0); }}\n"
    else:
        wall_u = "    wall { type noSlip; }\n"
    (case_dir / "0" / "U").write_text(
        _hdr("volVectorField", "U", "0")
        + "dimensions [0 1 -1 0 0 0 0];\ninternalField uniform (0 0 0);\n\n"
        + "boundaryField\n{\n"
        + f"    inlet {{ type fixedValue; value uniform ({U} 0 0); }}\n"
        + "    outlet { type zeroGradient; }\n"
        + wall_u
        + "    back { type wedge; }\n"
        + "    front { type wedge; }\n}\n"
    )

    # ---- 0/p ---------------------------------------------------------------
    (case_dir / "0" / "p").write_text(
        _hdr("volScalarField", "p", "0")
        + "dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\n\n"
        + "boundaryField\n{\n"
        + "    inlet { type zeroGradient; }\n"
        + "    outlet { type fixedValue; value uniform 0; }\n"
        + "    wall { type zeroGradient; }\n"
        + "    back { type wedge; }\n"
        + "    front { type wedge; }\n}\n"
    )


def _parse_wall_average(dat_path: Path) -> float | None:
    """Streamwise (Ux) component of the area-averaged wall velocity that OpenFOAM's
    ``surfaceFieldValue`` wrote for the wall patch (last write). Returns None if the
    file is absent/unparseable so the caller can fall back to the line sample."""
    if not dat_path.exists():
        return None
    val: float | None = None
    for line in dat_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.search(r"\(([^)]+)\)", line)  # vector average: "<time> (Ux Uy Uz)"
        if m:
            try:
                val = float(m.group(1).split()[0])
            except (ValueError, IndexError):
                pass
    return val


def _profile_vp(label: str, u: np.ndarray) -> VelocityProfile:
    rn = pp.normalized_r()
    return VelocityProfile(
        label=label,
        y=[round(float(v), 5) for v in rn],
        u=[round(float(v), 6) for v in np.asarray(u, dtype=float)],
    )


def run(
    workflow: Workflow,
    fault: Fault,
    *,
    repaired: bool = False,
    round_index: int = 0,
    run_id: str | None = None,
    has_benchmark: bool = True,
    keep_case: bool = False,
) -> RunResult:
    container = detect_container()
    run_id = run_id or f"pipe_{fault.value}_{'fix' if repaired else 'raw'}_{round_index}"
    case_name = f"ofab_{run_id}"
    host_dir = RUNS_DIR / case_name
    if host_dir.exists():
        shutil.rmtree(host_dir)
    host_dir.mkdir(parents=True, exist_ok=True)

    generate_pipe_case(host_dir, fault, repaired)

    remote = f"/tmp/{case_name}"
    try:
        _docker("exec", container.name, "rm", "-rf", remote)
        cp_in = _docker("cp", str(host_dir), f"{container.name}:{remote}")
        if cp_in.returncode != 0:
            raise OpenFOAMUnavailable(f"docker cp in failed: {cp_in.stderr.strip()}")

        script = (
            f"source {container.bashrc} >/dev/null 2>&1 && cd {remote} && "
            "{ blockMesh > log.blockMesh 2>&1; icoFoam > log.icoFoam 2>&1; }; "
            "echo OFAB_DONE"
        )
        try:
            exec_res = _docker("exec", container.name, "bash", "-c", script, timeout=600)
        except subprocess.TimeoutExpired as exc:
            raise OpenFOAMUnavailable(
                f"OpenFOAM solver exceeded the time budget: {exc}"
            ) from exc

        out_dir = RUNS_DIR / f"{case_name}_out"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        _docker("cp", f"{container.name}:{remote}", str(out_dir))

        log_path = out_dir / "log.icoFoam"
        log_text = log_path.read_text() if log_path.exists() else exec_res.stdout
        execution_ok = "OFAB_DONE" in exec_res.stdout and ("FOAM FATAL" not in log_text)

        xy_files = sorted((out_dir / "postProcessing" / "profile").glob("*/line_U.xy"))
        if not xy_files:
            raise OpenFOAMUnavailable(
                f"no sampled profile produced (icoFoam log tail: {log_text[-400:]})"
            )
        r_raw, ux = _parse_profile(xy_files[-1])
        # Normalise the sampled radius by the physical wall radius (R·cosθ) so the
        # wall lands at r/R = 1, then resample to the canonical 41 stations.
        rn = r_raw / _WALL_Y
        order = np.argsort(rn)
        rn, ux = rn[order], ux[order]
        u_canon = np.interp(pp.normalized_r(), rn, ux)

        # Anchor the wall point (r/R = 1) to the faithful patch-averaged wall velocity
        # the solver actually produced — the line sample over-reads it on coarse meshes
        # (a cellPoint extrapolation artifact), which would otherwise masquerade as a
        # no-slip violation and mis-route the diagnosis to BC_MISMATCH. For a genuine
        # bc fault this still reads the real moving-wall speed, so it does NOT mask it.
        wall_dat = sorted(
            (out_dir / "postProcessing" / "wallU").glob("*/surfaceFieldValue.dat")
        )
        if wall_dat:
            wall_ux = _parse_wall_average(wall_dat[-1])
            if wall_ux is not None:
                u_canon[-1] = wall_ux

        residual = _parse_residual(log_text)
        u_ref = pp.analytical_profile()
        qoi = pp.l2_relative_error(u_canon, u_ref)
        feats = pp.pipe_features(u_canon, u_ref)

        execution_status = (
            ExecutionStatus.SUCCESS if execution_ok else ExecutionStatus.FAILED
        )
        if has_benchmark:
            engineering_status = (
                EngineeringStatus.PASS
                if (qoi < config.QOI_L2_TOL and residual < config.RESIDUAL_TOL)
                else EngineeringStatus.NEEDS_REPAIR
            )
        else:
            engineering_status = EngineeringStatus.UNKNOWN

        return RunResult(
            run_id=run_id,
            workflow=workflow,
            case_id=config.PIPE_CASE_ID,
            fault=fault,
            mode=RunMode.OPENFOAM,
            round_index=round_index,
            execution_status=execution_status,
            engineering_status=engineering_status,
            qoi_error=round(float(qoi), 5),
            residual_final=float(residual),
            runtime_s=0.0,
            profile=_profile_vp("openfoam", u_canon),
            reference=_profile_vp("analytical", u_ref),
            features={k: round(float(v), 5) for k, v in feats.items()},
            notes=f"real OpenFOAM axisymmetric-wedge pipe run in container '{container.name}'",
        )
    finally:
        if not keep_case:
            _docker("exec", container.name, "rm", "-rf", remote)

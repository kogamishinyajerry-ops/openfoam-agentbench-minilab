"""Real OpenFOAM runner for the second case (plane Couette / shear flow).

Mirrors :mod:`openfoam_runner` but for the shear-driven case: the bottom wall is
fixed (no-slip) and the top wall (lid) is dragged at a constant speed, so the
exact steady solution is the linear profile ``u(y) = U_lid * y/H``. The injected
fault sets the *stationary* wall to a small non-zero velocity (a no-slip
violation) — the same class of BC mismatch the hero case uses, here giving the
same ~18% wall slip.

Reuses the container discovery + log/profile parsing from :mod:`openfoam_runner`,
and scores the run with :mod:`physics_couette` (linear reference). It is the same
non-destructive pattern: a fresh case is copied into the container's ``/tmp`` under
a unique name, run, copied back, and removed.

The correct run is **self-validating**: if the case is set up right it reproduces
the analytical line within tolerance (QoI -> ~0). If it does not, the benchmark
flags it — we never ship a Couette "evidence" number the analytical oracle rejects.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

from .. import config
from .. import physics_couette as pc
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

# The stationary-wall velocity that realises the injected BC fault. Equals
# COUETTE_BC_SLIP * U_lid, so the steady linear profile leaks by exactly that
# fraction at the fixed wall -> wall_slip == slip, L2 == slip (~18%).
_FAULT_WALL_SPEED = round(config.COUETTE_BC_SLIP * config.COUETTE_LID_VELOCITY, 6)


def _couette_params(fault: Fault, repaired: bool) -> dict:
    """Mesh / BC / control knobs implementing each state of the Couette case."""
    p = dict(ny=40, nx=20, end_time=2.0, delta_t=0.001, bottom_speed=0.0)
    if repaired:
        return p  # no-slip restored -> linear
    if fault == Fault.BC_MISMATCH:
        p["bottom_speed"] = _FAULT_WALL_SPEED   # stationary wall set wrong (leaks)
    elif fault == Fault.COARSE_MESH:
        p["ny"] = 4                              # under-resolved (linear -> still exact)
    elif fault == Fault.SOLVER_SETTING_ERROR:
        p["end_time"] = 0.02                     # stop long before the shear develops
    return p


def generate_couette_case(case_dir: Path, fault: Fault, repaired: bool) -> None:
    H = config.COUETTE_HEIGHT
    L = 4.0 * H                       # short streamwise extent; flow is x-invariant
    U_lid = config.COUETTE_LID_VELOCITY
    nu = config.COUETTE_KINEMATIC_VISCOSITY
    dz = H / 20.0
    fp = _couette_params(fault, repaired)
    nx, ny, end_time, delta_t, bottom_speed = (
        fp["nx"], fp["ny"], fp["end_time"], fp["delta_t"], fp["bottom_speed"]
    )
    x_sample = 0.5 * L
    z_mid = dz / 2.0

    for sub in ("0", "constant", "system"):
        (case_dir / sub).mkdir(parents=True, exist_ok=True)

    def _hdr(cls: str, obj: str, loc: str) -> str:
        return (
            "FoamFile\n{\n    version 2.0;\n    format ascii;\n"
            f"    class {cls};\n    location \"{loc}\";\n    object {obj};\n}}\n"
        )

    # ---- blockMeshDict -----------------------------------------------------
    # Bottom wall (y=0) fixed, top wall (y=H) moving. Streamwise ends are
    # zeroGradient (no imposed pressure gradient — the lid drives the flow).
    verts = [
        (0, 0, 0), (L, 0, 0), (L, H, 0), (0, H, 0),
        (0, 0, dz), (L, 0, dz), (L, H, dz), (0, H, dz),
    ]
    vtxt = "\n".join(f"    ({x} {y} {z})" for x, y, z in verts)
    blockmesh = (
        _hdr("dictionary", "blockMeshDict", "system")
        + f"scale 1;\n\nvertices\n(\n{vtxt}\n);\n\n"
        + f"blocks\n(\n    hex (0 1 2 3 4 5 6 7) ({nx} {ny} 1) simpleGrading (1 1 1)\n);\n\n"
        + "edges ();\n\n"
        + "boundary\n(\n"
        + "    inlet { type patch; faces ( (0 4 7 3) ); }\n"
        + "    outlet { type patch; faces ( (1 2 6 5) ); }\n"
        + "    movingWall { type wall; faces ( (3 7 6 2) ); }\n"
        + "    fixedWall { type wall; faces ( (0 1 5 4) ); }\n"
        + "    frontAndBack { type empty; faces ( (0 3 2 1) (4 5 6 7) ); }\n"
        + ");\n\nmergePatchPairs ();\n"
    )
    (case_dir / "system" / "blockMeshDict").write_text(blockmesh)

    # ---- controlDict (with embedded wall-normal sampling) ------------------
    control = (
        _hdr("dictionary", "controlDict", "system")
        + "application icoFoam;\nstartFrom startTime;\nstartTime 0;\n"
        + f"stopAt endTime;\nendTime {end_time};\ndeltaT {delta_t};\n"
        + "writeControl runTime;\n"
        + f"writeInterval {end_time};\npurgeWrite 0;\nwriteFormat ascii;\n"
        + "writePrecision 8;\nwriteCompression off;\ntimeFormat general;\n"
        + "timePrecision 6;\nrunTimeModifiable true;\n\n"
        + "functions\n{\n    profile\n    {\n        type sets;\n"
        + "        libs (\"libsampling.so\");\n        writeControl writeTime;\n"
        + "        interpolationScheme cellPoint;\n        setFormat raw;\n"
        + "        fields ( U );\n        sets\n        (\n            line\n            {\n"
        + "                type uniform;\n                axis y;\n"
        + f"                start ( {x_sample} 0 {z_mid} );\n"
        + f"                end ( {x_sample} {H} {z_mid} );\n"
        + f"                nPoints {config.N_PROFILE_POINTS};\n            }}\n        );\n    }}\n}}\n"
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
    # movingWall always carries the lid speed; the fixed wall is no-slip unless
    # the BC fault sets it to a small non-zero velocity (the injected mismatch).
    if bottom_speed > 0.0:
        bottom_u = f"    fixedWall {{ type fixedValue; value uniform ({bottom_speed} 0 0); }}\n"
    else:
        bottom_u = "    fixedWall { type noSlip; }\n"
    (case_dir / "0" / "U").write_text(
        _hdr("volVectorField", "U", "0")
        + "dimensions [0 1 -1 0 0 0 0];\ninternalField uniform (0 0 0);\n\n"
        + "boundaryField\n{\n"
        + "    inlet { type zeroGradient; }\n"
        + "    outlet { type zeroGradient; }\n"
        + f"    movingWall {{ type fixedValue; value uniform ({U_lid} 0 0); }}\n"
        + bottom_u
        + "    frontAndBack { type empty; }\n}\n"
    )

    # ---- 0/p ---------------------------------------------------------------
    (case_dir / "0" / "p").write_text(
        _hdr("volScalarField", "p", "0")
        + "dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\n\n"
        + "boundaryField\n{\n"
        + "    inlet { type zeroGradient; }\n"
        + "    outlet { type fixedValue; value uniform 0; }\n"
        + "    movingWall { type zeroGradient; }\n"
        + "    fixedWall { type zeroGradient; }\n"
        + "    frontAndBack { type empty; }\n}\n"
    )


def _profile_vp(label: str, u: np.ndarray) -> VelocityProfile:
    yn = pc.normalized_y()
    return VelocityProfile(
        label=label,
        y=[round(float(v), 5) for v in yn],
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
    run_id = run_id or f"couette_{fault.value}_{'fix' if repaired else 'raw'}_{round_index}"
    case_name = f"ofab_{run_id}"
    host_dir = RUNS_DIR / case_name
    if host_dir.exists():
        shutil.rmtree(host_dir)
    host_dir.mkdir(parents=True, exist_ok=True)

    generate_couette_case(host_dir, fault, repaired)

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
        y_raw, ux = _parse_profile(xy_files[-1])
        yn = y_raw / config.COUETTE_HEIGHT
        order = np.argsort(yn)
        yn, ux = yn[order], ux[order]
        u_canon = np.interp(pc.normalized_y(), yn, ux)

        residual = _parse_residual(log_text)
        u_ref = pc.analytical_profile()
        qoi = pc.l2_relative_error(u_canon, u_ref)
        feats = pc.couette_features(u_canon, u_ref)

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
            case_id=config.COUETTE_CASE_ID,
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
            notes=f"real OpenFOAM Couette run in container '{container.name}'",
        )
    finally:
        if not keep_case:
            _docker("exec", container.name, "rm", "-rf", remote)

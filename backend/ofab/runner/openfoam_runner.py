"""Real OpenFOAM runner (optional path).

Generates a self-contained 2D plane-Poiseuille channel case, injects the chosen
fault, runs ``blockMesh`` + ``icoFoam`` inside a detected OpenFOAM Docker
container, samples the wall-normal velocity profile, and packages a RunResult
identical in shape to the mock/replay runners.

It is non-destructive: it copies a fresh case into the container's ``/tmp`` under
a unique name, runs there, copies results back, and never touches anything else.
If no usable container is found (or any step fails) the caller can fall back to
the mock runner — the replay spine never depends on this module.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import config, physics
from ..models import (
    EngineeringStatus,
    ExecutionStatus,
    Fault,
    RunMode,
    RunResult,
    Workflow,
)
from ..paths import RUNS_DIR
from .mock_runner import profile_model

# Candidate OpenFOAM environment scripts inside a container, newest layouts first.
_BASHRC_CANDIDATES = [
    "/usr/lib/openfoam/openfoam2312/etc/bashrc",
    "/usr/lib/openfoam/openfoam2306/etc/bashrc",
    "/opt/openfoam10/etc/bashrc",
    "/opt/openfoam11/etc/bashrc",
    "/openfoam/etc/bashrc",
]


class OpenFOAMUnavailable(RuntimeError):
    pass


@dataclass
class Container:
    name: str
    bashrc: str


# --------------------------------------------------------------------------- #
# Container discovery                                                         #
# --------------------------------------------------------------------------- #
def _docker(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout
    )


def detect_container() -> Container:
    """Find a running container that exposes an OpenFOAM environment."""
    forced = os.environ.get("OFAB_OPENFOAM_CONTAINER")
    candidates: list[str] = []
    if forced:
        candidates.append(forced)
    try:
        ps = _docker("ps", "--format", "{{.Names}}")
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:  # docker missing
        raise OpenFOAMUnavailable(f"docker not available: {exc}") from exc
    if ps.returncode != 0:
        raise OpenFOAMUnavailable(f"docker ps failed: {ps.stderr.strip()}")
    candidates += [n for n in ps.stdout.split() if n and n not in candidates]

    for name in candidates:
        for bashrc in _BASHRC_CANDIDATES:
            probe = _docker("exec", name, "test", "-f", bashrc)
            if probe.returncode == 0:
                # Confirm the core apps resolve under THIS exact invocation
                # (non-login `source && command`) — a login-shell probe can give
                # a false positive when a broken env script is on the image.
                check = _docker(
                    "exec", name, "bash", "-c",
                    f"source {bashrc} >/dev/null 2>&1 && command -v blockMesh && command -v icoFoam",
                )
                if check.returncode == 0 and check.stdout.strip():
                    return Container(name=name, bashrc=bashrc)
    raise OpenFOAMUnavailable(
        "no running container with blockMesh/icoFoam found "
        "(set OFAB_OPENFOAM_CONTAINER or start an OpenFOAM container)"
    )


def is_available() -> bool:
    try:
        detect_container()
        return True
    except OpenFOAMUnavailable:
        return False


# --------------------------------------------------------------------------- #
# Case generation                                                            #
# --------------------------------------------------------------------------- #
def _fault_params(fault: Fault, repaired: bool) -> dict:
    """Mesh / BC / control knobs implementing each injected fault."""
    p = dict(ny=40, nx=60, end_time=6.0, delta_t=0.003, wall_type="noSlip")
    if repaired:
        return p
    if fault == Fault.BC_MISMATCH:
        # Moving wall instead of no-slip: converges to a wrong steady profile with
        # non-zero wall velocity (a clean, detectable no-slip violation). A pure
        # `slip` wall never develops a parabola and just fails to converge.
        p["wall_type"] = "moving"
    elif fault == Fault.COARSE_MESH:
        p["ny"] = 4                        # under-resolved wall-normal
    elif fault == Fault.SOLVER_SETTING_ERROR:
        # Stop far before the flow develops -> genuinely not converged at the
        # outlet sample (endTime=0.3 already develops at Re~20, so go much lower).
        p["end_time"] = 0.05
    return p


def generate_case(case_dir: Path, fault: Fault, repaired: bool) -> None:
    H = config.CHANNEL_HEIGHT
    L = config.CHANNEL_LENGTH
    U0 = config.INLET_VELOCITY
    nu = config.KINEMATIC_VISCOSITY
    dz = H / 20.0
    fp = _fault_params(fault, repaired)
    nx, ny, end_time, delta_t, wall_type = (
        fp["nx"], fp["ny"], fp["end_time"], fp["delta_t"], fp["wall_type"]
    )
    x_sample = 0.95 * L
    z_mid = dz / 2.0

    for sub in ("0", "constant", "system"):
        (case_dir / sub).mkdir(parents=True, exist_ok=True)

    def _hdr(cls: str, obj: str, loc: str) -> str:
        return (
            "FoamFile\n{\n    version 2.0;\n    format ascii;\n"
            f"    class {cls};\n    location \"{loc}\";\n    object {obj};\n}}\n"
        )

    # ---- blockMeshDict -----------------------------------------------------
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
        + "    walls { type wall; faces ( (0 1 5 4) (3 7 6 2) ); }\n"
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
    if wall_type == "noSlip":
        wall_u = "    walls { type noSlip; }\n"
    elif wall_type == "moving":  # wrong wall BC: a translating wall (no-slip violated)
        wall_u = "    walls { type fixedValue; value uniform (0.05 0 0); }\n"
    else:  # slip
        wall_u = "    walls { type slip; }\n"
    (case_dir / "0" / "U").write_text(
        _hdr("volVectorField", "U", "0")
        + "dimensions [0 1 -1 0 0 0 0];\ninternalField uniform (0 0 0);\n\n"
        + "boundaryField\n{\n"
        + f"    inlet {{ type fixedValue; value uniform ({U0} 0 0); }}\n"
        + "    outlet { type zeroGradient; }\n"
        + wall_u
        + "    frontAndBack { type empty; }\n}\n"
    )

    # ---- 0/p ---------------------------------------------------------------
    (case_dir / "0" / "p").write_text(
        _hdr("volScalarField", "p", "0")
        + "dimensions [0 2 -2 0 0 0 0];\ninternalField uniform 0;\n\n"
        + "boundaryField\n{\n"
        + "    inlet { type zeroGradient; }\n"
        + "    outlet { type fixedValue; value uniform 0; }\n"
        + "    walls { type zeroGradient; }\n"
        + "    frontAndBack { type empty; }\n}\n"
    )


# --------------------------------------------------------------------------- #
# Execution                                                                  #
# --------------------------------------------------------------------------- #
def _parse_profile(xy_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Parse a raw `sets` output: columns are `y Ux Uy Uz`."""
    rows = []
    for line in xy_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            rows.append((float(parts[0]), float(parts[1])))
    if not rows:
        raise OpenFOAMUnavailable(f"empty sample file {xy_path}")
    arr = np.array(rows)
    return arr[:, 0], arr[:, 1]


def _parse_residual(log_text: str) -> float:
    """Final-timestep initial residual for Ux from an icoFoam log."""
    matches = re.findall(
        r"Solving for Ux, Initial residual = ([0-9.eE+-]+)", log_text
    )
    if matches:
        return float(matches[-1])
    return config.RESIDUAL_TOL  # unknown -> borderline


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
    run_id = run_id or f"of_{fault.value}_{'fix' if repaired else 'raw'}_{round_index}"
    case_name = f"ofab_{run_id}"
    host_dir = RUNS_DIR / case_name
    if host_dir.exists():
        shutil.rmtree(host_dir)
    host_dir.mkdir(parents=True, exist_ok=True)

    generate_case(host_dir, fault, repaired)

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
            exec_res = _docker(
                "exec", container.name, "bash", "-c", script, timeout=600
            )
        except subprocess.TimeoutExpired as exc:
            # Translate a stuck/slow solver into the graceful fallback path the
            # CLI/API handlers expect, instead of a raw traceback.
            raise OpenFOAMUnavailable(
                f"OpenFOAM solver exceeded the time budget: {exc}"
            ) from exc
        runtime_s = 0.0  # filled by caller's wall clock if desired

        # Copy results back (remove any prior copy first: docker cp into an
        # existing directory nests the source inside it, shadowing fresh results).
        out_dir = RUNS_DIR / f"{case_name}_out"
        if out_dir.exists():
            shutil.rmtree(out_dir)
        _docker("cp", f"{container.name}:{remote}", str(out_dir))

        log_path = out_dir / "log.icoFoam"
        log_text = log_path.read_text() if log_path.exists() else exec_res.stdout
        execution_ok = "OFAB_DONE" in exec_res.stdout and (
            "FOAM FATAL" not in log_text
        )

        xy_files = sorted((out_dir / "postProcessing" / "profile").glob("*/line_U.xy"))
        if not xy_files:
            raise OpenFOAMUnavailable(
                f"no sampled profile produced (icoFoam log tail: {log_text[-400:]})"
            )
        y_raw, ux = _parse_profile(xy_files[-1])
        # resample to the canonical 41 stations in case the set ordering differs
        yn = y_raw / config.CHANNEL_HEIGHT
        order = np.argsort(yn)
        yn, ux = yn[order], ux[order]
        u_canon = np.interp(physics.normalized_y(), yn, ux)

        residual = _parse_residual(log_text)
        u_ref = physics.analytical_profile()
        qoi = physics.l2_relative_error(u_canon, u_ref)
        feats = physics.profile_features(u_canon, u_ref)

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
            case_id=config.CASE_ID,
            fault=fault,
            mode=RunMode.OPENFOAM,
            round_index=round_index,
            execution_status=execution_status,
            engineering_status=engineering_status,
            qoi_error=round(float(qoi), 5),
            residual_final=float(residual),
            runtime_s=round(float(runtime_s), 2),
            profile=profile_model("openfoam", u_canon),
            reference=profile_model("analytical", u_ref),
            features={k: round(float(v), 5) for k, v in feats.items()},
            notes=f"real OpenFOAM run in container '{container.name}'",
        )
    finally:
        # Always remove the in-container case (the run's own self-named /tmp dir),
        # even when sampling/parse raises — keeps the "cleans up" guarantee true.
        if not keep_case:
            _docker("exec", container.name, "rm", "-rf", remote)

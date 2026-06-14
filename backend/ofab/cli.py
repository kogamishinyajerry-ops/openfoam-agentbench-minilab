"""ofab CLI — drive the benchmark-feedback loop from the terminal.

    ofab demo seed
    ofab run --fault bc_mismatch --mode replay
    ofab benchmark runs/latest
    ofab diagnose runs/latest
    ofab reward runs/latest
    ofab recall --fault bc_mismatch
    ofab experiment experiments/pilot_001/protocol.yaml
"""
from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import paths
from .benchmark import build_scorecard, compute_reward, diagnose
from .models import Fault, RunMode, RunResult, Workflow
from .runner import mock_runner

app = typer.Typer(no_args_is_help=True, add_completion=False,
                  help="OpenFOAM-AgentBench MiniLab — Benchmark-Feedback CFD agent loop")
demo_app = typer.Typer(no_args_is_help=True, help="Seed and inspect replay demo data")
app.add_typer(demo_app, name="demo")
console = Console()


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _resolve_run_path(arg: str) -> Path:
    p = Path(arg)
    if p.is_dir():
        return p / "latest.json"
    if p.suffix == ".json":
        return p
    # "runs/latest" -> runs/latest.json (under repo or cwd)
    cand = Path(f"{arg}.json")
    if cand.exists():
        return cand
    return paths.RUNS_DIR / f"{p.name}.json"


def _load_run(arg: str) -> RunResult:
    path = _resolve_run_path(arg)
    if not path.exists():
        console.print(f"[red]No run found at {path}. Run `ofab run ...` first.[/red]")
        raise typer.Exit(1)
    return RunResult.model_validate_json(path.read_text())


def _save_run(run: RunResult) -> Path:
    paths.ensure_dirs()
    latest = paths.RUNS_DIR / "latest.json"
    named = paths.RUNS_DIR / f"{run.run_id}.json"
    latest.write_text(run.model_dump_json(indent=2))
    named.write_text(run.model_dump_json(indent=2))
    return latest


def _print_run(run: RunResult) -> None:
    exec_c = "green" if run.execution_status.value == "success" else "red"
    eng = run.engineering_status.value
    eng_c = {"pass": "green", "needs_repair": "red", "unknown": "yellow"}[eng]
    t = Table(show_header=False, box=None)
    t.add_row("run_id", run.run_id)
    t.add_row("workflow", run.workflow.value)
    t.add_row("fault", run.fault.value)
    t.add_row("mode", run.mode.value)
    t.add_row("execution", f"[{exec_c}]{run.execution_status.value}[/{exec_c}]")
    t.add_row("engineering", f"[{eng_c}]{eng}[/{eng_c}]")
    t.add_row("QoI L2 error", f"{run.qoi_error*100:.1f}%")
    t.add_row("residual", f"{run.residual_final:.1e}")
    t.add_row("runtime", f"{run.runtime_s:.1f}s")
    console.print(Panel(t, title="RunResult", border_style=exec_c))


# --------------------------------------------------------------------------- #
# demo                                                                        #
# --------------------------------------------------------------------------- #
@demo_app.command("seed")
def demo_seed(mode: RunMode = typer.Option(RunMode.REPLAY, help="replay | mock")):
    """Generate the replay bundle + example artifacts + frontend data."""
    from .demo import seed
    out = seed(mode)
    console.print(Panel.fit(
        f"[green]✓ seeded[/green]  runs=[bold]{out['runs']}[/bold]  "
        f"false_success=[bold]{out['false_success_detected']}[/bold]  "
        f"experience=[bold]{out['experience_records']}[/bold]\n"
        f"bundle: {out['bundle']}\nfrontend: {out['frontend_data']}",
        title="ofab demo seed"))


@demo_app.command("summary")
def demo_summary():
    """Print the head-to-head comparison from the seeded bundle."""
    from .runner.replay_runner import load_bundle
    try:
        bundle = load_bundle()
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    cmp = bundle["comparison"]
    t = Table(title=f"{bundle['case']['title']} — head-to-head")
    t.add_column("Metric"); t.add_column("Agent-only", justify="right")
    t.add_column("Agent+Benchmark", justify="right"); t.add_column("Δ", justify="right")
    t.add_row("Rerun count", str(cmp["rerun_count"]["before"]),
              str(cmp["rerun_count"]["after"]), f"{cmp['rerun_count']['delta_pct']:.0f}%")
    t.add_row("Time to pass", cmp["time_to_pass"]["before_label"],
              cmp["time_to_pass"]["after_label"], f"{cmp['time_to_pass']['delta_pct']:.0f}%")
    t.add_row("Final QoI error", cmp["qoi_error"]["before_label"],
              cmp["qoi_error"]["after_label"], "—")
    t.add_row("False success detected", "0", str(cmp["false_success_detected"]["after"]), "—")
    t.add_row("Experience records", "0", str(cmp["experience_records"]["after"]), "—")
    console.print(t)


# --------------------------------------------------------------------------- #
# run / benchmark / diagnose / reward / experiment                            #
# --------------------------------------------------------------------------- #
@demo_app.command("real-evidence")
def demo_real_evidence():
    """Run the correct case + 3 faults on a live OpenFOAM container and record
    what the benchmark detected (writes data/real_evidence.json)."""
    from .demo import capture_real_evidence
    from .runner.openfoam_runner import OpenFOAMUnavailable
    try:
        ev = capture_real_evidence()
    except OpenFOAMUnavailable as exc:
        console.print(f"[red]OpenFOAM unavailable: {exc}[/red]")
        raise typer.Exit(1)
    c = ev["correct"]
    console.print(Panel.fit(
        f"container [bold]{ev['container']}[/bold]\n"
        f"correct case: L2=[green]{c['qoi_error']*100:.2f}%[/green] "
        f"(u_peak {c['u_peak_sampled']} vs {c['u_peak_analytical']})",
        title="real OpenFOAM evidence"))
    t = Table(title="Injected faults — real false successes")
    t.add_column("fault"); t.add_column("L2"); t.add_column("residual")
    t.add_column("false success"); t.add_column("diagnosis")
    for f in ev["faults"]:
        fs = "[red]yes[/red]" if f["false_success_detected"] else "no"
        t.add_row(f["fault"], f"{f['qoi_error']*100:.1f}%", f"{f['residual_final']:.1e}",
                  fs, f"{f['diagnosis']} ({f['confidence']:.0%})")
    console.print(t)
    console.print(f"[dim]written: {ev['_path']}[/dim]")


@demo_app.command("couette-evidence")
def demo_couette_evidence():
    """Run the second case (Couette) on a live OpenFOAM container and record what
    the same benchmark detected — proving generalisation on real hardware
    (writes data/real_evidence_couette.json + the frontend copy)."""
    from .demo import capture_couette_evidence
    from .runner.openfoam_runner import OpenFOAMUnavailable
    try:
        ev = capture_couette_evidence()
    except OpenFOAMUnavailable as exc:
        console.print(f"[red]OpenFOAM unavailable: {exc}[/red]")
        raise typer.Exit(1)
    c = ev["correct"]
    console.print(Panel.fit(
        f"container [bold]{ev['container']}[/bold]  ·  案例 [bold]Couette 剪切流[/bold]\n"
        f"correct case: L2=[green]{c['qoi_error']*100:.2f}%[/green] "
        f"(u_lid {c['u_top_sampled']} vs {c['u_top_analytical']})",
        title="real OpenFOAM evidence — 第二个案例"))
    t = Table(title="同一套基准检验在 Couette 上抓到的真实假成功")
    t.add_column("fault"); t.add_column("L2"); t.add_column("residual")
    t.add_column("false success"); t.add_column("diagnosis")
    for f in ev["faults"]:
        fs = "[red]yes[/red]" if f["false_success_detected"] else "no"
        t.add_row(f["fault"], f"{f['qoi_error']*100:.1f}%", f"{f['residual_final']:.1e}",
                  fs, f"{f['diagnosis']} ({f['confidence']:.0%})")
    console.print(t)
    cm = ev["coarse_mesh_check"]
    console.print(f"[dim]网格检查: 粗网格 L2={cm['qoi_error']*100:.2f}% "
                  f"({'合格' if cm['overall_pass'] else '不合格'}) —— 印证「网格太粗」不适用[/dim]")
    console.print(f"[dim]written: {ev['_path']}[/dim]")


@demo_app.command("pipe-evidence")
def demo_pipe_evidence():
    """Run the third case (round pipe) on a live OpenFOAM container — an axisymmetric
    wedge — and record what the same benchmark detected. The pipe's HERO fault is
    coarse_mesh (the radial parabola a coarse mesh clips), the mirror of Couette where
    that fault is N/A. Writes data/real_evidence_pipe.json + the frontend copy."""
    from .demo import capture_pipe_evidence
    from .runner.openfoam_runner import OpenFOAMUnavailable
    try:
        ev = capture_pipe_evidence()
    except OpenFOAMUnavailable as exc:
        console.print(f"[red]OpenFOAM unavailable: {exc}[/red]")
        raise typer.Exit(1)
    c = ev["correct"]
    console.print(Panel.fit(
        f"container [bold]{ev['container']}[/bold]  ·  案例 [bold]圆管层流（Hagen–Poiseuille）[/bold]\n"
        f"几何 [dim]{ev['geometry']}[/dim]\n"
        f"correct case: L2=[green]{c['qoi_error']*100:.2f}%[/green] "
        f"(u_peak {c['u_peak_sampled']} vs {c['u_peak_analytical']})",
        title="real OpenFOAM evidence — 第三个案例"))
    t = Table(title="同一套基准检验在圆管上抓到的真实假成功（主场故障 = 网格太粗）")
    t.add_column("fault"); t.add_column("L2"); t.add_column("residual")
    t.add_column("false success"); t.add_column("diagnosis")
    for f in ev["faults"]:
        fs = "[red]yes[/red]" if f["false_success_detected"] else "no"
        name = f"{f['fault']}{' ★' if f.get('is_hero') else ''}"
        t.add_row(name, f"{f['qoi_error']*100:.1f}%", f"{f['residual_final']:.1e}",
                  fs, f"{f['diagnosis']} ({f['confidence']:.0%})")
    console.print(t)
    console.print(f"[dim]written: {ev['_path']}[/dim]")


@app.command()
def run(
    ctx: typer.Context,
    case: str = typer.Option("channel_poiseuille",
                             help="case id: channel_poiseuille (hero) | couette_shear | pipe_poiseuille"),
    fault: Fault = typer.Option(Fault.BC_MISMATCH, help="injected fault"),
    mode: RunMode = typer.Option(RunMode.REPLAY, help="replay | mock | openfoam"),
    repaired: bool = typer.Option(False, help="run the repaired (fixed) case"),
    workflow: Workflow = typer.Option(Workflow.AGENT_PLUS_BENCHMARK),
):
    """Generate (or replay) one OpenFOAM run and save it to runs/latest.json."""
    # Did the user actually type --fault, or fall back to the global default? Each case
    # heroes a DIFFERENT fault, so the bare `ofab run --case X` should showcase X's hero.
    # bc_mismatch is the channel/Couette hero (and the global default); the pipe heroes
    # coarse_mesh. We honor an explicit --fault exactly, but for the pipe's default we
    # swap in its hero so `ofab run --case pipe_poiseuille` isn't a vacuous clean pass.
    # (Compare the source enum by name: typer/click expose two distinct ParameterSource
    # classes, so identity comparison against an imported member is unreliable.)
    fault_is_default = ctx.get_parameter_source("fault").name == "DEFAULT"

    if case.lower() in {"couette", "couette_shear", "shear"}:
        # Second case (Couette): real solver for openfoam mode, deterministic
        # synthetic otherwise. The benchmark layer downstream is unchanged.
        from .demo.couette_case import synthesize_couette_run
        if mode == RunMode.OPENFOAM:
            from .runner import openfoam_couette
            from .runner.openfoam_runner import OpenFOAMUnavailable
            try:
                console.print("[cyan]running real OpenFOAM (Couette)…[/cyan]")
                run_result = openfoam_couette.run(
                    workflow, fault, repaired=repaired,
                    has_benchmark=(workflow == Workflow.AGENT_PLUS_BENCHMARK))
            except OpenFOAMUnavailable as exc:
                console.print(f"[yellow]OpenFOAM unavailable ({exc}); synthetic Couette.[/yellow]")
                run_result = synthesize_couette_run(fault, repaired)
        else:
            run_result = synthesize_couette_run(fault, repaired)
        _save_run(run_result)
        _print_run(run_result)
        return

    if case.lower() in {"pipe", "pipe_poiseuille", "round_pipe"}:
        # Third case (round pipe): deterministic synthetic run for mock/replay; a real
        # axisymmetric solve for openfoam mode when its runner is available, else fall
        # back to synthetic. The pipe's HERO fault is coarse_mesh (the radial parabola's
        # curvature is exactly what a coarse mesh clips), so the bare invocation defaults
        # to it — but an explicit --fault is honored verbatim. The benchmark layer below
        # is unchanged for every fault.
        pipe_fault = Fault.COARSE_MESH if fault_is_default else fault
        from .demo.pipe_case import synthesize_pipe_run
        if mode == RunMode.OPENFOAM:
            try:
                from .runner import openfoam_pipe
                from .runner.openfoam_runner import OpenFOAMUnavailable
                try:
                    console.print("[cyan]running real OpenFOAM (pipe)…[/cyan]")
                    run_result = openfoam_pipe.run(
                        workflow, pipe_fault, repaired=repaired,
                        has_benchmark=(workflow == Workflow.AGENT_PLUS_BENCHMARK))
                except OpenFOAMUnavailable as exc:
                    console.print(f"[yellow]OpenFOAM unavailable ({exc}); synthetic pipe.[/yellow]")
                    run_result = synthesize_pipe_run(pipe_fault, repaired)
            except ImportError:
                console.print("[yellow]real pipe runner not available; synthetic pipe.[/yellow]")
                run_result = synthesize_pipe_run(pipe_fault, repaired)
        else:
            run_result = synthesize_pipe_run(pipe_fault, repaired)
        _save_run(run_result)
        _print_run(run_result)
        return

    if mode == RunMode.OPENFOAM:
        from .runner import openfoam_runner
        try:
            console.print("[cyan]running real OpenFOAM…[/cyan]")
            run_result = openfoam_runner.run(workflow, fault, repaired=repaired,
                                             has_benchmark=(workflow == Workflow.AGENT_PLUS_BENCHMARK))
        except openfoam_runner.OpenFOAMUnavailable as exc:
            console.print(f"[yellow]OpenFOAM unavailable ({exc}); falling back to mock.[/yellow]")
            run_result = mock_runner.run_synthetic(
                f"mock_{fault.value}", workflow, fault, repaired=repaired,
                has_benchmark=(workflow == Workflow.AGENT_PLUS_BENCHMARK))
    elif mode == RunMode.REPLAY:
        from .runner.replay_runner import list_runs, BundleNotFound
        run_result = None
        try:
            target_round = None
            for r in list_runs():
                if r.fault == fault and r.workflow == workflow:
                    if r.round_index == 0 and not repaired:
                        run_result = r; break
                    if repaired and r.engineering_status.value == "pass":
                        run_result = r; break
        except BundleNotFound:
            pass
        if run_result is None:
            run_result = mock_runner.run_synthetic(
                f"replay_{fault.value}", workflow, fault, repaired=repaired,
                mode=RunMode.REPLAY,
                has_benchmark=(workflow == Workflow.AGENT_PLUS_BENCHMARK))
    else:  # mock
        run_result = mock_runner.run_synthetic(
            f"mock_{fault.value}", workflow, fault, repaired=repaired,
            mode=RunMode.MOCK,
            has_benchmark=(workflow == Workflow.AGENT_PLUS_BENCHMARK))

    _save_run(run_result)
    _print_run(run_result)


@app.command()
def benchmark(run_path: str = typer.Argument("runs/latest")):
    """Score a run: execution vs residual vs QoI, and flag false success."""
    run = _load_run(run_path)
    sc = build_scorecard(run)
    out = paths.RUNS_DIR / "scorecard.json"
    out.write_text(sc.model_dump_json(indent=2))
    t = Table(title="Scorecard")
    t.add_column("Check"); t.add_column("Result"); t.add_column("value"); t.add_column("threshold")
    for c in sc.checks:
        mark = "[green]PASS[/green]" if c.passed else "[red]FAIL[/red]"
        t.add_row(c.name, mark, f"{c.value:.2e}", f"{c.threshold:.2e}")
    console.print(t)
    if sc.false_success:
        console.print(Panel("[red]⚠ FALSE SUCCESS[/red] — ran fine, engineering result is wrong",
                            border_style="red"))
    else:
        verdict = "[green]engineering PASS[/green]" if sc.overall_pass else "[yellow]needs repair[/yellow]"
        console.print(verdict)


def diagnose_cmd(run_path: str = typer.Argument("runs/latest")):
    """Diagnose the failure mode from profile features."""
    run = _load_run(run_path)
    dg = diagnose(run)
    out = paths.RUNS_DIR / "diagnosis.json"
    out.write_text(dg.model_dump_json(indent=2))
    body = [f"[bold]{dg.failure_mode.value}[/bold]  (confidence {dg.confidence:.0%})", ""]
    body += ["[dim]evidence[/dim]"] + [f"  • {e}" for e in dg.evidence]
    if dg.suggested_repair:
        body += ["", "[dim]suggested repair[/dim]"] + [f"  → {s}" for s in dg.suggested_repair]
    console.print(Panel("\n".join(body), title="Diagnosis", border_style="magenta"))


# expose as `ofab diagnose`
app.command(name="diagnose")(diagnose_cmd)


@app.command()
def reward(run_path: str = typer.Argument("runs/latest"),
           round_index: int = typer.Option(0)):
    """Compute the reward signal that drives the next repair."""
    run = _load_run(run_path)
    sc = build_scorecard(run)
    dg = diagnose(run)
    rw = compute_reward(sc, dg, round_index=round_index,
                        experience_created=not sc.overall_pass)
    out = paths.RUNS_DIR / "reward.json"
    out.write_text(rw.model_dump_json(indent=2))
    color = "green" if rw.total_reward >= 0 else "red"
    t = Table(show_header=False, box=None)
    t.add_row("total", f"[{color}]{rw.total_reward:+.2f}[/{color}]")
    t.add_row("engineering", f"{rw.engineering_reward:+.2f}")
    t.add_row("efficiency", f"{rw.efficiency_reward:+.2f}")
    t.add_row("experience", f"{rw.experience_reward:+.2f}")
    t.add_row("decision", rw.decision)
    t.add_row("focus", ", ".join(rw.suggested_focus) or "—")
    console.print(Panel(t, title="Reward", border_style=color))


@app.command()
def recall(fault: Fault = typer.Option(Fault.BC_MISMATCH, help="recurring fault to look up")):
    """Recall a prior lesson for a recurring fault from the experience store — the
    flywheel's retrieval half. Run `ofab demo seed` first to populate the store."""
    from .memory import ExperienceStore
    from .models import FailureMode
    fault_mode = {
        Fault.BC_MISMATCH: FailureMode.BC_MISMATCH,
        Fault.COARSE_MESH: FailureMode.MESH_TOO_COARSE,
        Fault.SOLVER_SETTING_ERROR: FailureMode.RESIDUAL_NOT_CONVERGED,
    }
    mode = fault_mode.get(fault)
    rec = ExperienceStore().recall(mode) if mode else None
    if rec is None:
        console.print(Panel.fit(
            f"[yellow]错题本里还没有 `{fault.value}` —— 这次只能从头摸索。[/yellow]\n"
            f"[dim]先跑 `ofab demo seed` 沉淀经验，再回来 recall。[/dim]",
            title="recall", border_style="yellow"))
        return
    t = Table(show_header=False, box=None)
    t.add_row("failure_mode", f"[bold]{rec.failure_mode.value}[/bold]")
    t.add_row("症状", rec.symptom)
    t.add_row("修复方式", f"[green]{rec.repair}[/green]")
    t.add_row("上次结果", rec.outcome)
    t.add_row("回归用例", "✅ 是" if rec.promote_to_regression else "否")
    console.print(Panel(
        t, title=f"recall · {fault.value} —— 命中错题本，直接套用已知修复",
        border_style="cyan"))


@app.command()
def experiment(protocol: str = typer.Argument(...)):
    """Run an experiment protocol and emit all JSON artifacts + report.md."""
    from .demo import run_experiment
    out = run_experiment(protocol)
    console.print(Panel.fit(
        f"[green]✓ experiment complete[/green]  mode={out['mode']}  runs={out['runs']}\n"
        f"false_success={out['false_success_detected']}  experience={out['experience_records']}\n"
        f"results: {out['results_dir']}\nreport: {out['report']}",
        title="ofab experiment"))


def main() -> None:
    app()


if __name__ == "__main__":
    main()

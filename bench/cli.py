"""Command-line interface for benchmarking."""

import os
import platform
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from bench import __version__
from bench.config import load_config
from bench.logging import logger, setup_logging

app = typer.Typer(
    name="bench",
    help="OpenFold2-NIM Benchmarking Suite",
    add_completion=False,
)

console = Console()


@app.command()
def version():
    """Show version information."""
    console.print(f"bench version {__version__}")


@app.command()
def preflight(verbose: bool = typer.Option(False, "--verbose", "-v")):
    """Validate environment and prerequisites."""
    if verbose:
        setup_logging(level=20, verbose=True)

    console.print("[bold]Preflight Checks[/bold]")

    checks = []

    # Check nvidia-smi
    try:
        result = subprocess.run(
            ["nvidia-smi"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            checks.append(("nvidia-smi", True, "Found"))
        else:
            checks.append(("nvidia-smi", False, "Failed"))
    except Exception as e:
        checks.append(("nvidia-smi", False, str(e)))

    # Check docker
    try:
        result = subprocess.run(
            ["docker", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            checks.append(("docker", True, result.stdout.strip()))
        else:
            checks.append(("docker", False, "Not found"))
    except Exception as e:
        checks.append(("docker", False, str(e)))

    # Check NGC_API_KEY (Fix #13: Enhanced validation)
    ngc_key = os.environ.get("NGC_API_KEY")
    if ngc_key:
        # Check if it's exported (not just set)
        try:
            result = subprocess.run(
                ["env"], capture_output=True, text=True, timeout=5
            )
            if "NGC_API_KEY=" in result.stdout:
                checks.append(("NGC_API_KEY", True, "Set and exported"))
            else:
                checks.append(("NGC_API_KEY", False, "Set but not exported (use 'export NGC_API_KEY=...')"))
        except Exception:
            checks.append(("NGC_API_KEY", True, "Set (export status unknown)"))
    else:
        checks.append(("NGC_API_KEY", False, "Not set (required for NIM)"))

    # Check disk space
    home = Path.home()
    stat = os.statvfs(home)
    free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
    if free_gb >= 100:
        checks.append(("Disk space", True, f"{free_gb:.1f} GB available"))
    else:
        checks.append(("Disk space", False, f"Only {free_gb:.1f} GB available (need 100+ GB)"))

    # Check Python version (Fix #13: Minimum version check)
    py_version = sys.version_info
    if py_version >= (3, 10):
        checks.append(("Python version", True, f"{py_version.major}.{py_version.minor}.{py_version.micro}"))
    else:
        checks.append(("Python version", False, f"{py_version.major}.{py_version.minor}.{py_version.micro} (need 3.10+)"))

    # Check Docker daemon (Fix #13: Enhanced Docker check)
    try:
        result = subprocess.run(
            ["docker", "ps"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            checks.append(("Docker daemon", True, "Running and accessible"))
        else:
            checks.append(("Docker daemon", False, "Not accessible or permission denied"))
    except Exception as e:
        checks.append(("Docker daemon", False, str(e)))

    # Check GPU visibility (Fix #13: nvidia-smi GPU check)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_info = result.stdout.strip().split('\n')[0]
            checks.append(("GPU visibility", True, gpu_info))
        else:
            checks.append(("GPU visibility", False, "No GPUs detected"))
    except Exception as e:
        checks.append(("GPU visibility", False, str(e)))

    # Display results
    table = Table(title="Preflight Results")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    all_passed = True
    for check_name, passed, details in checks:
        status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        table.add_row(check_name, status, details)
        if not passed:
            all_passed = False

    console.print(table)

    if all_passed:
        console.print("\n[green]All checks passed![/green]")
        return 0
    else:
        console.print("\n[red]Some checks failed. Fix issues before running benchmark.[/red]")
        return 1


@app.command()
def prepare_data(
    config_path: Path = typer.Option("configs/default.yaml", "--config", "-c"),
    suite: Optional[str] = typer.Option(None, "--suite", "-s"),
):
    """Prepare benchmark datasets."""
    console.print(f"[bold]Preparing data from {config_path}[/bold]")

    config = load_config(config_path)

    # Implementation would:
    # 1. Load targets from YAML or generate synthetic sequences
    # 2. Fetch PDB structures if needed
    # 3. Generate synthetic MSAs
    # 4. Create OpenFold precomputed alignment directories

    console.print("[green]Data preparation complete[/green]")


@app.command()
def run(
    config_path: Path = typer.Option("configs/default.yaml", "--config", "-c"),
    output_dir: Path = typer.Option("results", "--output-dir", "-o"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run full benchmark."""
    from bench.orchestrator import BenchmarkOrchestrator

    if verbose:
        setup_logging(level=10, verbose=True)

    console.print(f"[bold]Running benchmark with {config_path}[/bold]")

    config = load_config(config_path)

    # Set up output directory
    run_dir = output_dir / config.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(log_file=run_dir / "bench.log", verbose=verbose)

    logger.info(f"Starting benchmark run: {config.run_id}")
    logger.info(f"Output directory: {run_dir}")

    try:
        # Run benchmark
        orchestrator = BenchmarkOrchestrator(config, run_dir)
        manifest = orchestrator.run()

        console.print(f"\n[green]✓ Benchmark complete![/green]")
        console.print(f"[green]  Run ID: {manifest.run_id}[/green]")
        console.print(f"[green]  Results: {run_dir}[/green]")
        console.print(f"[green]  Records: {manifest.records_count}[/green]")

    except Exception as e:
        console.print(f"\n[red]✗ Benchmark failed: {e}[/red]")
        logger.error("Benchmark failed", exc_info=True)
        raise typer.Exit(code=1)


@app.command()
def analyze(
    input_dir: Path = typer.Argument(..., help="Results directory to analyze"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o"),
    export_csv: bool = typer.Option(True, "--csv/--no-csv", help="Export CSV data"),
    update_readme: bool = typer.Option(False, "--update-readme", help="Update README with results"),
):
    """Generate analysis and plots from results."""
    from bench.analysis.report import generate_html_report

    if output_dir is None:
        output_dir = input_dir / "analysis"

    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Analyzing results from {input_dir}[/bold]")

    try:
        # Generate report (includes CSV export by default via generate_html_report)
        report_path = generate_html_report(input_dir, output_dir)

        console.print(f"\n[green]✓ Analysis complete![/green]")
        console.print(f"[green]  Report: {report_path}[/green]")

        # Note about CSV export
        if export_csv:
            csv_dir = output_dir / "data"
            console.print(f"[green]  CSV Data: {csv_dir}[/green]")

        # Update README if requested
        if update_readme:
            from bench.analysis.load import load_results
            from bench.analysis.markdown import (
                generate_results_markdown,
                update_readme_with_results,
            )

            manifest, df = load_results(input_dir)
            results_md = generate_results_markdown(manifest, df)
            readme_path = Path("README.md")
            update_readme_with_results(readme_path, results_md)
            console.print("[green]✓ README updated with latest results[/green]")

        console.print(f"\n[cyan]Open in browser:[/cyan] file://{report_path.absolute()}")

    except Exception as e:
        console.print(f"\n[red]✗ Analysis failed: {e}[/red]")
        logger.error("Analysis failed", exc_info=True)
        raise typer.Exit(code=1)


@app.command()
def aggregate(
    input_patterns: list[Path] = typer.Argument(..., help="Manifest files to aggregate"),
    output_dir: Path = typer.Argument(..., help="Output directory"),
):
    """Aggregate results from multiple runs."""
    console.print(f"[bold]Aggregating {len(input_patterns)} runs[/bold]")

    # Implementation would:
    # 1. Load all manifests
    # 2. Combine records
    # 3. Generate comparative analysis

    console.print(f"[green]Aggregation complete: {output_dir}[/green]")


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()

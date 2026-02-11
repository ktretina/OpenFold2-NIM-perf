"""HTML report generation."""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from bench.analysis.export import export_all_csvs
from bench.analysis.load import load_results
from bench.analysis.plots import generate_all_plots
from bench.analysis.statistics import compute_distribution_stats
from bench.logging import logger


def generate_summary_table(df: pd.DataFrame) -> str:
    """Generate HTML summary table with distribution statistics."""
    # Aggregate by system and variant
    summary = (
        df.groupby(["system", "variant"])
        .agg(
            {
                "wall_time_s": [
                    "mean",
                    "median",
                    "std",
                    "min",
                    "max",
                    ("p90", lambda x: np.percentile(x, 90)),
                    ("p95", lambda x: np.percentile(x, 95)),
                    ("p99", lambda x: np.percentile(x, 99)),
                ],
                "gpu_sm_util_avg_pct": "mean",
                "gpu_mem_peak_mb": "mean",
                "gpu_energy_wh": "mean",
                "mean_plddt": "mean",
                "ca_lddt": "mean",
                "tm_score": "mean",
                "gdt_ts": "mean",
                "target_id": "count",
            }
        )
        .reset_index()
    )

    # Flatten column names
    summary.columns = [
        "System",
        "Variant",
        "Time Mean (s)",
        "Time Median (s)",
        "Time Std (s)",
        "Time Min (s)",
        "Time Max (s)",
        "Time p90 (s)",
        "Time p95 (s)",
        "Time p99 (s)",
        "Avg GPU Util (%)",
        "Peak GPU Mem (MB)",
        "Energy (Wh)",
        "Mean pLDDT",
        "Mean lDDT",
        "Mean TM-score",
        "Mean GDT_TS",
        "N Predictions",
    ]

    # Format numbers
    for col in summary.columns:
        if "Time" in col or "Util" in col or "Mem" in col or "Energy" in col:
            if summary[col].dtype in [float, int]:
                summary[col] = summary[col].round(2)
        elif "LDDT" in col or "pLDDT" in col or "TM-score" in col:
            if summary[col].dtype in [float, int]:
                summary[col] = summary[col].round(3)
        elif "GDT_TS" in col:
            if summary[col].dtype in [float, int]:
                summary[col] = summary[col].round(1)

    return summary.to_html(index=False, classes="summary-table", border=0)


def generate_distribution_insights(df: pd.DataFrame) -> str:
    """Generate insights about latency distribution."""
    insights_html = []

    # Compute distribution stats
    stats = compute_distribution_stats(df, "wall_time_s", ["system", "variant"])

    # Add insights for each variant
    for _, row in stats.iterrows():
        system = row["system"]
        variant = row["variant"]
        median = row["median"]
        p95 = row["p95"]
        p99 = row["p99"]
        count = row["count"]

        # Calculate tail latency ratio
        tail_ratio = (p99 / median - 1) * 100 if median > 0 else 0

        # Determine stability
        if tail_ratio < 10:
            stability = "🟢 Excellent - very stable"
        elif tail_ratio < 20:
            stability = "🟡 Good - minor variance"
        elif tail_ratio < 50:
            stability = "🟠 Moderate - some outliers"
        else:
            stability = "🔴 High variance - investigate outliers"

        insights_html.append(f"""
        <div class="info-box">
            <h3>{system.upper()} - {variant}</h3>
            <p><strong>Median:</strong> {median:.2f}s | <strong>p95:</strong> {p95:.2f}s | <strong>p99:</strong> {p99:.2f}s</p>
            <p><strong>Tail Latency:</strong> p99 is {tail_ratio:.1f}% higher than median</p>
            <p><strong>Stability:</strong> {stability}</p>
            <p><strong>Sample Size:</strong> {int(count)} measurements</p>
        </div>
        """)

    return '<div class="info-grid">' + ''.join(insights_html) + '</div>'


def create_latest_symlink(run_dir: Path):
    """
    Create results/latest symlink to most recent run.

    Args:
        run_dir: Directory of the current run
    """
    try:
        results_dir = run_dir.parent
        latest_link = results_dir / "latest"

        # Remove existing symlink
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()

        # Create new symlink pointing to run directory
        latest_link.symlink_to(run_dir.name, target_is_directory=True)
        logger.info(f"Created symlink: {latest_link} -> {run_dir.name}")
    except (OSError, NotImplementedError) as e:
        # Symlinks may not be supported on some filesystems (e.g., some Windows or network drives)
        logger.warning(f"Could not create latest symlink: {e}")
        logger.info("This is not critical - you can access results directly via run directory")


def generate_html_report(run_dir: Path, output_dir: Optional[Path] = None):
    """
    Generate comprehensive HTML report.

    Args:
        run_dir: Directory containing benchmark results
        output_dir: Directory to save report (default: run_dir/analysis)
    """
    run_dir = Path(run_dir)
    if output_dir is None:
        output_dir = run_dir / "analysis"

    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(exist_ok=True)

    logger.info(f"Generating report for {run_dir}")

    # Load results
    manifest, df = load_results(run_dir)

    # Export CSVs
    csv_dir = output_dir / "data"
    export_all_csvs(df, csv_dir)

    # Generate all plots
    generate_all_plots(df, plots_dir)

    # Create latest symlink
    create_latest_symlink(run_dir)

    # Build HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenFold2-NIM Benchmark Report - {manifest.run_id}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #1f77b4;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
            border-bottom: 2px solid #ddd;
            padding-bottom: 5px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin: 20px 0;
        }}
        .info-box {{
            background-color: #f9f9f9;
            padding: 15px;
            border-left: 4px solid #1f77b4;
        }}
        .info-box h3 {{
            margin-top: 0;
            color: #1f77b4;
        }}
        table.summary-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        table.summary-table th, table.summary-table td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        table.summary-table th {{
            background-color: #1f77b4;
            color: white;
            font-weight: bold;
        }}
        table.summary-table tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        table.summary-table tr:hover {{
            background-color: #f0f0f0;
        }}
        .plot-container {{
            margin: 30px 0;
            border: 1px solid #ddd;
            border-radius: 5px;
            overflow: hidden;
        }}
        iframe {{
            width: 100%;
            border: none;
        }}
        .metadata {{
            background-color: #f0f0f0;
            padding: 15px;
            border-radius: 5px;
            font-family: monospace;
            font-size: 0.9em;
        }}
        .status-badge {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 3px;
            font-weight: bold;
        }}
        .status-completed {{
            background-color: #4caf50;
            color: white;
        }}
        .status-running {{
            background-color: #ff9800;
            color: white;
        }}
        .status-failed {{
            background-color: #f44336;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>OpenFold2-NIM Benchmark Report</h1>

        <div class="info-grid">
            <div class="info-box">
                <h3>Run Information</h3>
                <p><strong>Run ID:</strong> {manifest.run_id}</p>
                <p><strong>Start Time:</strong> {manifest.start_time}</p>
                <p><strong>End Time:</strong> {manifest.end_time or 'Running...'}</p>
                <p><strong>Status:</strong> <span class="status-badge status-{manifest.status}">{manifest.status.upper()}</span></p>
                <p><strong>Total Predictions:</strong> {manifest.records_count}</p>
            </div>

            <div class="info-box">
                <h3>System Information</h3>
                <p><strong>Hostname:</strong> {manifest.system_info.hostname}</p>
                <p><strong>GPU:</strong> {', '.join(manifest.system_info.gpu_models)}</p>
                <p><strong>VRAM:</strong> {', '.join(map(str, manifest.system_info.gpu_vram_mb))} MB</p>
                <p><strong>Driver:</strong> {manifest.system_info.gpu_driver}</p>
                <p><strong>CUDA:</strong> {manifest.system_info.cuda_version}</p>
            </div>
        </div>

        <div class="section">
            <h2>Performance Summary</h2>
            {generate_summary_table(df)}
        </div>

        <div class="section">
            <h2>Latency Distribution Analysis</h2>
            <p>Statistical distribution of latencies showing median, p95, and p99 percentiles.
            Tail latencies (p95/p99) are critical for production SLA definition.</p>
            {generate_distribution_insights(df)}

            <h3>Violin Plot: Full Distribution</h3>
            <div class="plot-container">
                <iframe src="plots/latency_distribution_violin.html" height="750px"></iframe>
            </div>

            <h3>Percentile Comparison</h3>
            <div class="plot-container">
                <iframe src="plots/percentile_comparison.html" height="650px"></iframe>
            </div>

            <h3>Tail Latency Analysis</h3>
            <p>This shows p99/median ratio - values closer to 100% indicate more stable performance.</p>
            <div class="plot-container">
                <iframe src="plots/tail_latency_analysis.html" height="650px"></iframe>
            </div>
        </div>

        <div class="section">
            <h2>Pareto Frontier Analysis</h2>
            <p>This plot shows the trade-off between accuracy and computational cost. Points on the Pareto frontier represent optimal configurations where improving one metric requires sacrificing the other.</p>
            <div class="plot-container">
                <iframe src="plots/pareto_curve.html" height="850px"></iframe>
            </div>
        </div>

        <div class="section">
            <h2>Sequence Length Scaling</h2>
            <p>How performance metrics scale with protein sequence length.</p>
            <div class="plot-container">
                <iframe src="plots/scaling_seq_length.html" height="1050px"></iframe>
            </div>
        </div>

        <div class="section">
            <h2>GPU Utilization Distribution</h2>
            <p>Distribution of GPU utilization across all predictions.</p>
            <div class="plot-container">
                <iframe src="plots/gpu_util_distribution.html" height="650px"></iframe>
            </div>
        </div>

        <div class="section">
            <h2>Per-Target Accuracy</h2>
            <p>Accuracy comparison for individual benchmark targets.</p>
            <div class="plot-container">
                <iframe src="plots/accuracy_per_target.html" height="650px"></iframe>
            </div>
        </div>

        <div class="section">
            <h2>Energy Efficiency</h2>
            <p>Relationship between prediction accuracy and energy consumption.</p>
            <div class="plot-container">
                <iframe src="plots/energy_efficiency.html" height="850px"></iframe>
            </div>
        </div>

        <div class="section">
            <h2>Configuration</h2>
            <details>
                <summary><strong>Show Full Configuration</strong></summary>
                <div class="metadata">
                    <pre>{format_config(manifest.config)}</pre>
                </div>
            </details>
        </div>

        <div class="section">
            <h2>Metadata</h2>
            {format_metadata(manifest)}
        </div>

        <hr style="margin: 40px 0;">
        <p style="text-align: center; color: #888;">
            Generated by OpenFold2-NIM Benchmark Suite |
            <a href="https://github.com/ktretina/OpenFold2-NIM-perf">GitHub</a>
        </p>
    </div>
</body>
</html>
"""

    # Write HTML file
    report_path = output_dir / "report.html"
    report_path.write_text(html_content)

    logger.info(f"Report generated: {report_path}")
    logger.info(f"Open in browser: file://{report_path.absolute()}")

    return report_path


def format_config(config: dict) -> str:
    """Format configuration as readable text."""
    import json

    return json.dumps(config, indent=2)


def format_metadata(manifest) -> str:
    """Format metadata section."""
    html = ""

    if manifest.nim_metadata:
        html += "<h3>NIM Metadata</h3><div class='metadata'>"
        html += f"<p><strong>Backend:</strong> {manifest.nim_metadata.backend}</p>"
        if manifest.nim_metadata.container_digest:
            html += f"<p><strong>Container Digest:</strong> {manifest.nim_metadata.container_digest}</p>"
        html += "</div>"

    if manifest.openfold_metadata:
        html += "<h3>OpenFold Metadata</h3><div class='metadata'>"
        html += f"<p><strong>Git Commit:</strong> {manifest.openfold_metadata.git_commit}</p>"
        html += f"<p><strong>Python:</strong> {manifest.openfold_metadata.python_version}</p>"
        if manifest.openfold_metadata.torch_version:
            html += f"<p><strong>PyTorch:</strong> {manifest.openfold_metadata.torch_version}</p>"
        html += "</div>"

    return html

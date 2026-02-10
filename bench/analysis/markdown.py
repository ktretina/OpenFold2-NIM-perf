"""Markdown generation for README updates."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from bench.logging import logger
from bench.results.schema import RunManifest


def generate_results_markdown(manifest: RunManifest, df: pd.DataFrame) -> str:
    """
    Generate markdown section for README (no plots, tables only).

    Args:
        manifest: Run manifest with metadata
        df: Results DataFrame

    Returns:
        Markdown-formatted string with results summary
    """
    md = "## Latest Benchmark Results\n\n"
    md += f"**Run ID:** `{manifest.run_id}`  \n"
    md += f"**Date:** {manifest.start_time}  \n"
    md += f"**GPU:** {', '.join(manifest.system_info.gpu_models)}  \n"
    md += f"**Predictions:** {manifest.records_count}  \n\n"

    # Summary table
    md += "### Performance Summary\n\n"

    summary = (
        df.groupby(["system", "variant"])
        .agg(
            {
                "wall_time_s": "mean",
                "gpu_sm_util_avg_pct": "mean",
                "gpu_mem_peak_mb": "mean",
                "gpu_energy_wh": "mean",
                "ca_lddt": "mean",
                "target_id": "count",
            }
        )
        .reset_index()
    )

    summary.columns = [
        "System",
        "Variant",
        "Latency (s)",
        "GPU Util (%)",
        "GPU Mem (MB)",
        "Energy (Wh)",
        "Accuracy (lDDT)",
        "N",
    ]

    # Round and format
    summary = summary.round(
        {
            "Latency (s)": 2,
            "GPU Util (%)": 1,
            "GPU Mem (MB)": 0,
            "Energy (Wh)": 3,
            "Accuracy (lDDT)": 3,
        }
    )

    try:
        md += summary.to_markdown(index=False)
    except ImportError:
        logger.warning("tabulate not installed - falling back to basic table format")
        # Fallback to basic markdown table
        md += "| " + " | ".join(summary.columns) + " |\n"
        md += "| " + " | ".join(["---"] * len(summary.columns)) + " |\n"
        for _, row in summary.iterrows():
            md += "| " + " | ".join(str(v) for v in row.values) + " |\n"
    md += "\n\n"

    # Key findings
    md += "### Key Findings\n\n"
    if "nim" in df["system"].unique() and "openfold" in df["system"].unique():
        nim_time = df[df["system"] == "nim"]["wall_time_s"].mean()
        of_time = df[df["system"] == "openfold"]["wall_time_s"].mean()
        speedup = of_time / nim_time
        md += f"- **NIM achieves {speedup:.1f}× speedup** over OpenFold\n"

        nim_energy = df[df["system"] == "nim"]["gpu_energy_wh"].mean()
        of_energy = df[df["system"] == "openfold"]["gpu_energy_wh"].mean()
        energy_ratio = of_energy / nim_energy
        md += f"- **NIM uses {energy_ratio:.1f}× less energy** per prediction\n"

    if "ca_lddt" in df.columns and df["ca_lddt"].notna().any():
        avg_lddt = df["ca_lddt"].mean()
        md += f"- **Average accuracy:** {avg_lddt:.3f} lDDT across all targets\n"

    md += "\n"

    # Links to full analysis
    md += "📊 **[View Interactive Report](results/latest/analysis/report.html)**  \n"
    md += "📁 **[Download CSV Data](results/latest/analysis/data/)**  \n\n"

    md += "---\n"
    md += f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"

    return md


def update_readme_with_results(
    readme_path: Path, results_md: str, marker: str = "<!-- BENCHMARK_RESULTS -->"
):
    """
    Update README with results between markers.

    Args:
        readme_path: Path to README.md file
        results_md: Markdown content to insert
        marker: HTML comment marker for insertion point
    """
    content = readme_path.read_text()

    if marker not in content:
        logger.warning(f"Marker '{marker}' not found. Appending to end.")
        content += "\n\n" + results_md
    else:
        # Replace between markers
        start_marker = marker
        end_marker = "<!-- /BENCHMARK_RESULTS -->"

        if end_marker in content:
            start_idx = content.find(start_marker)
            end_idx = content.find(end_marker) + len(end_marker)
            new_section = f"{start_marker}\n\n{results_md}\n{end_marker}"
            content = content[:start_idx] + new_section + content[end_idx:]
        else:
            idx = content.find(start_marker) + len(start_marker)
            content = content[:idx] + "\n\n" + results_md + "\n" + content[idx:]

    readme_path.write_text(content)
    logger.info(f"Updated README at {readme_path}")

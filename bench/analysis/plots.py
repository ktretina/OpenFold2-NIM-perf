"""Plotting functions for benchmark visualization."""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from bench.analysis.pareto import compute_pareto_by_system
from bench.logging import logger

# Fix #4: Make kaleido optional
try:
    import kaleido
    KALEIDO_AVAILABLE = True
except ImportError:
    KALEIDO_AVAILABLE = False
    logger.info("Kaleido not available - PNG export will be skipped. Install with: pip install kaleido")


COLORS = {
    "nim": "#1f77b4",  # Blue
    "openfold": "#ff7f0e",  # Orange
}


def plot_pareto_curve(df: pd.DataFrame, output_dir: Path):
    """
    Plot Pareto frontier: accuracy vs performance trade-off.

    Args:
        df: Results DataFrame
        output_dir: Directory to save plots
    """
    logger.info("Generating Pareto frontier plot...")

    # Filter to accuracy suite with valid lDDT scores
    accuracy_df = df[df["suite"].str.contains("accuracy", case=False, na=False)].copy()
    accuracy_df = accuracy_df.dropna(subset=["ca_lddt", "gpu_hours_per_prediction"])

    if accuracy_df.empty:
        logger.warning("No accuracy data available for Pareto plot")
        return

    # Aggregate repeats: mean ± std
    agg_df = (
        accuracy_df.groupby(["system", "variant"])
        .agg(
            {
                "gpu_hours_per_prediction": ["mean", "std"],
                "ca_lddt": ["mean", "std"],
                "mean_plddt": "mean",
                "target_id": "count",
            }
        )
        .reset_index()
    )

    agg_df.columns = [
        "system",
        "variant",
        "gpu_hours_mean",
        "gpu_hours_std",
        "lddt_mean",
        "lddt_std",
        "plddt_mean",
        "n_preds",
    ]

    # Create figure
    fig = go.Figure()

    for system in agg_df["system"].unique():
        system_df = agg_df[agg_df["system"] == system]

        # Determine marker shape (ensemble vs single model)
        is_ensemble = system_df["variant"].str.contains("ensemble|5models|1-2-3-4-5")
        system_df["shape"] = is_ensemble.map({True: "square", False: "circle"})

        # Plot scatter with error bars
        fig.add_trace(
            go.Scatter(
                x=system_df["gpu_hours_mean"],
                y=system_df["lddt_mean"],
                error_x=dict(type="data", array=system_df["gpu_hours_std"], visible=True),
                error_y=dict(type="data", array=system_df["lddt_std"], visible=True),
                mode="markers",
                name=system.upper(),
                marker=dict(
                    size=system_df["plddt_mean"] / 5,  # Scale by confidence
                    color=COLORS.get(system, "#888888"),
                    symbol=system_df["shape"].tolist(),
                    line=dict(width=1, color="white"),
                    opacity=0.8,
                ),
                text=system_df["variant"],
                customdata=system_df[["plddt_mean", "n_preds"]],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "GPU hours: %{x:.4f}<br>"
                    "lDDT: %{y:.3f}<br>"
                    "Mean pLDDT: %{customdata[0]:.1f}<br>"
                    "N predictions: %{customdata[1]}<br>"
                    "<extra></extra>"
                ),
            )
        )

    # Compute and plot Pareto frontiers
    pareto_by_system = compute_pareto_by_system(agg_df, "gpu_hours_mean", "lddt_mean")

    for system, pareto_df in pareto_by_system.items():
        if pareto_df.empty:
            continue

        pareto_sorted = pareto_df.sort_values("gpu_hours_mean")

        fig.add_trace(
            go.Scatter(
                x=pareto_sorted["gpu_hours_mean"],
                y=pareto_sorted["lddt_mean"],
                mode="lines",
                name=f"{system.upper()} Pareto",
                line=dict(width=2, dash="dash", color=COLORS.get(system, "#888888")),
                showlegend=True,
                hoverinfo="skip",
            )
        )

    fig.update_layout(
        title="Accuracy vs Performance Trade-off (Pareto Frontier)",
        xaxis_title="GPU Hours per Prediction (log scale)",
        yaxis_title="Cα lDDT (Accuracy)",
        xaxis_type="log",
        yaxis=dict(range=[0, 1]),
        hovermode="closest",
        template="plotly_white",
        width=1200,
        height=800,
        font=dict(size=14),
        legend=dict(x=0.02, y=0.98),
    )

    # Save
    html_path = output_dir / "pareto_curve.html"
    png_path = output_dir / "pareto_curve.png"

    fig.write_html(str(html_path))
    if KALEIDO_AVAILABLE:
        try:
            fig.write_image(str(png_path), width=1200, height=800, scale=2)
        except Exception as e:
            logger.warning(f"Failed to save PNG: {e}")

    logger.info(f"Saved Pareto plot to {html_path}")


def plot_scaling_sequence_length(df: pd.DataFrame, output_dir: Path):
    """
    Plot scaling behavior with sequence length.

    Args:
        df: Results DataFrame
        output_dir: Directory to save plots
    """
    logger.info("Generating sequence length scaling plot...")

    # Filter to scaling suite
    scaling_df = df[df["suite"].str.contains("seq_length", case=False, na=False)].copy()

    if scaling_df.empty:
        logger.warning("No sequence length scaling data available")
        return

    # Aggregate by sequence length
    agg_df = (
        scaling_df.groupby(["system", "sequence_length"])
        .agg(
            {
                "wall_time_s": ["mean", "std"],
                "gpu_mem_peak_mb": ["mean", "std"],
                "gpu_sm_util_avg_pct": ["mean", "std"],
                "time_to_first_gpu_activity_s": ["mean", "std"],
            }
        )
        .reset_index()
    )

    agg_df.columns = [
        "system",
        "seq_len",
        "time_mean",
        "time_std",
        "mem_mean",
        "mem_std",
        "util_mean",
        "util_std",
        "ttfg_mean",
        "ttfg_std",
    ]

    # Create subplots
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Wall Time vs Sequence Length",
            "Peak GPU Memory vs Sequence Length",
            "GPU Utilization vs Sequence Length",
            "Time-to-First-GPU vs Sequence Length",
        ),
        vertical_spacing=0.12,
        horizontal_spacing=0.10,
    )

    for system in agg_df["system"].unique():
        sys_df = agg_df[agg_df["system"] == system]
        color = COLORS.get(system, "#888888")

        # Plot 1: Wall time
        fig.add_trace(
            go.Scatter(
                x=sys_df["seq_len"],
                y=sys_df["time_mean"],
                error_y=dict(type="data", array=sys_df["time_std"]),
                mode="lines+markers",
                name=system.upper(),
                line=dict(color=color, width=2),
                marker=dict(size=8),
                legendgroup=system,
                showlegend=True,
            ),
            row=1,
            col=1,
        )

        # Plot 2: Peak memory
        fig.add_trace(
            go.Scatter(
                x=sys_df["seq_len"],
                y=sys_df["mem_mean"],
                error_y=dict(type="data", array=sys_df["mem_std"]),
                mode="lines+markers",
                name=system.upper(),
                line=dict(color=color, width=2),
                marker=dict(size=8),
                legendgroup=system,
                showlegend=False,
            ),
            row=1,
            col=2,
        )

        # Plot 3: GPU utilization
        fig.add_trace(
            go.Scatter(
                x=sys_df["seq_len"],
                y=sys_df["util_mean"],
                error_y=dict(type="data", array=sys_df["util_std"]),
                mode="lines+markers",
                name=system.upper(),
                line=dict(color=color, width=2),
                marker=dict(size=8),
                legendgroup=system,
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        # Plot 4: Time to first GPU
        fig.add_trace(
            go.Scatter(
                x=sys_df["seq_len"],
                y=sys_df["ttfg_mean"],
                error_y=dict(type="data", array=sys_df["ttfg_std"]),
                mode="lines+markers",
                name=system.upper(),
                line=dict(color=color, width=2),
                marker=dict(size=8),
                legendgroup=system,
                showlegend=False,
            ),
            row=2,
            col=2,
        )

    # Update axes
    fig.update_xaxes(title_text="Sequence Length (residues)", row=1, col=1)
    fig.update_xaxes(title_text="Sequence Length (residues)", row=1, col=2)
    fig.update_xaxes(title_text="Sequence Length (residues)", row=2, col=1)
    fig.update_xaxes(title_text="Sequence Length (residues)", row=2, col=2)

    fig.update_yaxes(title_text="Wall Time (s)", type="log", row=1, col=1)
    fig.update_yaxes(title_text="Peak GPU Memory (MB)", row=1, col=2)
    fig.update_yaxes(title_text="Avg GPU Util (%)", row=2, col=1)
    fig.update_yaxes(title_text="Time to First GPU (s)", row=2, col=2)

    fig.update_layout(
        title_text="Scaling Analysis: Sequence Length",
        height=1000,
        width=1400,
        template="plotly_white",
        font=dict(size=12),
    )

    # Save
    html_path = output_dir / "scaling_seq_length.html"
    png_path = output_dir / "scaling_seq_length.png"

    fig.write_html(str(html_path))
    if KALEIDO_AVAILABLE:
        try:
            fig.write_image(str(png_path), width=1400, height=1000, scale=2)
        except Exception as e:
            logger.warning(f"Failed to save PNG: {e}")

    logger.info(f"Saved scaling plot to {html_path}")


def plot_gpu_utilization_distribution(df: pd.DataFrame, output_dir: Path):
    """
    Plot distribution of GPU utilization metrics.

    Args:
        df: Results DataFrame
        output_dir: Directory to save plots
    """
    logger.info("Generating GPU utilization distribution plot...")

    fig = px.box(
        df,
        x="variant",
        y="gpu_sm_util_avg_pct",
        color="system",
        title="GPU Utilization Distribution",
        labels={"gpu_sm_util_avg_pct": "GPU SM Utilization (%)", "variant": "Configuration"},
        template="plotly_white",
        color_discrete_map=COLORS,
    )

    fig.update_layout(width=1200, height=600)

    # Save
    html_path = output_dir / "gpu_util_distribution.html"
    png_path = output_dir / "gpu_util_distribution.png"

    fig.write_html(str(html_path))
    if KALEIDO_AVAILABLE:
        try:
            fig.write_image(str(png_path), width=1200, height=600, scale=2)
        except Exception as e:
            logger.warning(f"Failed to save PNG: {e}")

    logger.info(f"Saved utilization plot to {html_path}")


def plot_accuracy_per_target(df: pd.DataFrame, output_dir: Path):
    """
    Plot per-target accuracy comparison.

    Args:
        df: Results DataFrame
        output_dir: Directory to save plots
    """
    logger.info("Generating per-target accuracy plot...")

    # Filter to accuracy suite
    accuracy_df = df[df["suite"].str.contains("accuracy", case=False, na=False)].copy()
    accuracy_df = accuracy_df.dropna(subset=["ca_lddt"])

    if accuracy_df.empty:
        logger.warning("No accuracy data available")
        return

    fig = px.bar(
        accuracy_df,
        x="target_id",
        y="ca_lddt",
        color="variant",
        facet_col="system",
        title="Per-Target Accuracy Comparison",
        barmode="group",
        template="plotly_white",
    )

    fig.update_layout(width=1600, height=600)

    # Save
    html_path = output_dir / "accuracy_per_target.html"
    png_path = output_dir / "accuracy_per_target.png"

    fig.write_html(str(html_path))
    if KALEIDO_AVAILABLE:
        try:
            fig.write_image(str(png_path), width=1600, height=600, scale=2)
        except Exception as e:
            logger.warning(f"Failed to save PNG: {e}")

    logger.info(f"Saved accuracy plot to {html_path}")


def plot_energy_efficiency(df: pd.DataFrame, output_dir: Path):
    """
    Plot energy efficiency: accuracy vs power consumption.

    Args:
        df: Results DataFrame
        output_dir: Directory to save plots
    """
    logger.info("Generating energy efficiency plot...")

    # Filter to data with valid accuracy and energy
    energy_df = df.dropna(subset=["ca_lddt", "gpu_energy_wh"]).copy()

    if energy_df.empty:
        logger.warning("No energy/accuracy data available")
        return

    fig = px.scatter(
        energy_df,
        x="ca_lddt",
        y="gpu_energy_wh",
        size="wall_time_s",
        color="system",
        hover_data=["variant", "target_id"],
        title="Energy Efficiency: Accuracy vs Power Consumption",
        labels={"ca_lddt": "Accuracy (lDDT)", "gpu_energy_wh": "Energy per Prediction (Wh)"},
        template="plotly_white",
        color_discrete_map=COLORS,
    )

    fig.update_layout(width=1200, height=800)

    # Save
    html_path = output_dir / "energy_efficiency.html"
    png_path = output_dir / "energy_efficiency.png"

    fig.write_html(str(html_path))
    if KALEIDO_AVAILABLE:
        try:
            fig.write_image(str(png_path), width=1200, height=800, scale=2)
        except Exception as e:
            logger.warning(f"Failed to save PNG: {e}")

    logger.info(f"Saved energy plot to {html_path}")


def generate_all_plots(df: pd.DataFrame, output_dir: Path):
    """
    Generate all plots.

    Args:
        df: Results DataFrame
        output_dir: Directory to save plots
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_pareto_curve(df, output_dir)
    plot_scaling_sequence_length(df, output_dir)
    plot_gpu_utilization_distribution(df, output_dir)
    plot_accuracy_per_target(df, output_dir)
    plot_energy_efficiency(df, output_dir)

    logger.info(f"All plots generated in {output_dir}")

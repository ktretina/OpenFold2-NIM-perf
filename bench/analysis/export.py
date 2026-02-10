"""CSV export functionality for benchmark results."""

from pathlib import Path

import pandas as pd

from bench.logging import logger


def export_raw_records(df: pd.DataFrame, output_dir: Path):
    """
    Export all prediction records to CSV.

    Args:
        df: Results DataFrame
        output_dir: Directory to save CSV files
    """
    csv_path = output_dir / "raw_records.csv"
    df.to_csv(csv_path, index=False)
    logger.info(f"Exported raw records to {csv_path}")


def export_pareto_data(df: pd.DataFrame, output_dir: Path):
    """
    Export Pareto frontier aggregated data.

    This replicates the aggregation logic from plot_pareto_curve()
    to provide the underlying data for the Pareto analysis.

    Args:
        df: Results DataFrame
        output_dir: Directory to save CSV files
    """
    # Filter to accuracy suite with valid lDDT scores
    accuracy_df = df[df["suite"].str.contains("accuracy", case=False, na=False)].copy()
    accuracy_df = accuracy_df.dropna(subset=["ca_lddt", "gpu_hours_per_prediction"])

    if accuracy_df.empty:
        logger.warning("No accuracy data available for Pareto export")
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

    # Flatten column names
    agg_df.columns = [
        "system",
        "variant",
        "gpu_hours_mean",
        "gpu_hours_std",
        "lddt_mean",
        "lddt_std",
        "plddt_mean",
        "n_predictions",
    ]

    csv_path = output_dir / "pareto_data.csv"
    agg_df.to_csv(csv_path, index=False)
    logger.info(f"Exported Pareto data to {csv_path}")


def export_scaling_data(df: pd.DataFrame, output_dir: Path):
    """
    Export sequence length scaling data.

    This replicates the aggregation logic from plot_scaling_sequence_length()
    to provide the underlying data for scaling analysis.

    Args:
        df: Results DataFrame
        output_dir: Directory to save CSV files
    """
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

    # Flatten column names
    agg_df.columns = [
        "system",
        "sequence_length",
        "wall_time_mean",
        "wall_time_std",
        "gpu_mem_peak_mean",
        "gpu_mem_peak_std",
        "gpu_util_mean",
        "gpu_util_std",
        "time_to_first_gpu_mean",
        "time_to_first_gpu_std",
    ]

    csv_path = output_dir / "scaling_data.csv"
    agg_df.to_csv(csv_path, index=False)
    logger.info(f"Exported scaling data to {csv_path}")


def export_accuracy_data(df: pd.DataFrame, output_dir: Path):
    """
    Export per-target accuracy data.

    Args:
        df: Results DataFrame
        output_dir: Directory to save CSV files
    """
    accuracy_df = df[df["suite"].str.contains("accuracy", case=False, na=False)].copy()
    accuracy_df = accuracy_df.dropna(subset=["ca_lddt"])

    if accuracy_df.empty:
        logger.warning("No accuracy data available for per-target export")
        return

    # Select relevant columns
    cols = [
        "target_id",
        "system",
        "variant",
        "ca_lddt",
        "mean_plddt",
        "wall_time_s",
        "gpu_energy_wh",
        "sequence_length",
    ]

    # Filter to only columns that exist in the DataFrame
    available_cols = [col for col in cols if col in accuracy_df.columns]

    csv_path = output_dir / "accuracy_per_target.csv"
    accuracy_df[available_cols].to_csv(csv_path, index=False)
    logger.info(f"Exported per-target accuracy to {csv_path}")


def export_summary_statistics(df: pd.DataFrame, output_dir: Path):
    """
    Export summary table (same as HTML report table).

    Args:
        df: Results DataFrame
        output_dir: Directory to save CSV files
    """
    # Build aggregation dict based on available columns
    agg_dict = {}
    required_cols = ["system", "variant"]

    # Check required groupby columns exist
    if not all(col in df.columns for col in required_cols):
        logger.warning(f"Missing required columns for summary statistics: {required_cols}")
        return

    # Add metrics that exist in the DataFrame
    if "wall_time_s" in df.columns:
        agg_dict["wall_time_s"] = ["mean", "std", "min", "max"]
    if "gpu_sm_util_avg_pct" in df.columns:
        agg_dict["gpu_sm_util_avg_pct"] = "mean"
    if "gpu_mem_peak_mb" in df.columns:
        agg_dict["gpu_mem_peak_mb"] = "mean"
    if "gpu_energy_wh" in df.columns:
        agg_dict["gpu_energy_wh"] = "mean"
    if "mean_plddt" in df.columns:
        agg_dict["mean_plddt"] = "mean"
    if "ca_lddt" in df.columns:
        agg_dict["ca_lddt"] = "mean"
    if "target_id" in df.columns:
        agg_dict["target_id"] = "count"

    if not agg_dict:
        logger.warning("No valid metrics found for summary statistics")
        return

    summary = (
        df.groupby(["system", "variant"])
        .agg(agg_dict)
        .reset_index()
    )

    # Flatten column names
    summary.columns = [
        "system",
        "variant",
        "wall_time_mean",
        "wall_time_std",
        "wall_time_min",
        "wall_time_max",
        "gpu_util_avg_pct",
        "gpu_mem_peak_mb",
        "gpu_energy_wh",
        "mean_plddt",
        "ca_lddt",
        "n_predictions",
    ]

    csv_path = output_dir / "summary_statistics.csv"
    summary.to_csv(csv_path, index=False)
    logger.info(f"Exported summary statistics to {csv_path}")


def export_all_csvs(df: pd.DataFrame, output_dir: Path):
    """
    Export all CSV files.

    Args:
        df: Results DataFrame
        output_dir: Directory to save CSV files
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Exporting CSV files to {output_dir}")

    export_raw_records(df, output_dir)
    export_pareto_data(df, output_dir)
    export_scaling_data(df, output_dir)
    export_accuracy_data(df, output_dir)
    export_summary_statistics(df, output_dir)

    logger.info("CSV export complete")

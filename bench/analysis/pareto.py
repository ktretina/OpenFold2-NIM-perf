"""Pareto frontier computation."""

import numpy as np
import pandas as pd


def compute_pareto_frontier(df: pd.DataFrame, cost_col: str, accuracy_col: str) -> pd.DataFrame:
    """
    Compute Pareto frontier (non-dominated points).

    A point is on the Pareto frontier if no other point has both:
    - Lower cost (better)
    - Higher accuracy (better)

    Args:
        df: DataFrame with results
        cost_col: Column name for cost metric (minimize)
        accuracy_col: Column name for accuracy metric (maximize)

    Returns:
        DataFrame containing only Pareto-optimal points
    """
    if df.empty:
        return df

    # Drop rows with missing values
    df_clean = df[[cost_col, accuracy_col]].dropna()
    if df_clean.empty:
        return pd.DataFrame()

    points = df_clean[[cost_col, accuracy_col]].values
    is_pareto = np.ones(len(points), dtype=bool)

    for i in range(len(points)):
        if not is_pareto[i]:
            continue

        # Point i is dominated if another point has:
        # - cost <= cost[i] AND accuracy >= accuracy[i]
        # - AND at least one is strictly better
        dominated = (
            (points[:, 0] <= points[i, 0])  # Cost is better or equal
            & (points[:, 1] >= points[i, 1])  # Accuracy is better or equal
            & (
                (points[:, 0] < points[i, 0])  # Cost is strictly better
                | (points[:, 1] > points[i, 1])  # OR accuracy is strictly better
            )
        )
        is_pareto[dominated] = False

    # Return original dataframe rows that are on frontier
    pareto_indices = df_clean.index[is_pareto]
    return df.loc[pareto_indices]


def compute_pareto_by_system(
    df: pd.DataFrame, cost_col: str = "gpu_hours_per_prediction", accuracy_col: str = "ca_lddt"
) -> dict[str, pd.DataFrame]:
    """
    Compute Pareto frontier separately for each system.

    Args:
        df: DataFrame with results
        cost_col: Column name for cost metric
        accuracy_col: Column name for accuracy metric

    Returns:
        Dictionary mapping system name to Pareto-optimal DataFrame
    """
    pareto_by_system = {}

    for system in df["system"].unique():
        system_df = df[df["system"] == system].copy()
        pareto_df = compute_pareto_frontier(system_df, cost_col, accuracy_col)
        pareto_by_system[system] = pareto_df

    return pareto_by_system

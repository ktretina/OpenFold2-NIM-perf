"""Statistical analysis utilities for benchmark results.

Provides functions for computing distribution statistics including
percentiles (p90, p95, p99) which are critical for understanding
tail latencies in production systems.
"""

import numpy as np
import pandas as pd
from typing import List


def compute_distribution_stats(
    df: pd.DataFrame,
    metric: str,
    group_by: List[str]
) -> pd.DataFrame:
    """
    Compute distribution statistics including percentiles.

    Args:
        df: DataFrame containing benchmark results
        metric: Column name to compute statistics for (e.g., "wall_time_s")
        group_by: List of columns to group by (e.g., ["system", "variant"])

    Returns:
        DataFrame with columns: [group_by columns] + stats columns
        Stats columns: mean, median, std, min, max, p90, p95, p99, count

    Example:
        >>> stats = compute_distribution_stats(
        ...     df, "wall_time_s", ["system", "variant"]
        ... )
        >>> print(stats[["system", "variant", "median", "p95", "p99"]])
    """
    stats = df.groupby(group_by)[metric].agg([
        ('mean', 'mean'),
        ('median', 'median'),
        ('std', 'std'),
        ('min', 'min'),
        ('max', 'max'),
        ('p90', lambda x: np.percentile(x, 90)),
        ('p95', lambda x: np.percentile(x, 95)),
        ('p99', lambda x: np.percentile(x, 99)),
        ('count', 'count')
    ]).reset_index()

    return stats


def compute_cv(df: pd.DataFrame, metric: str, group_by: List[str]) -> pd.DataFrame:
    """
    Compute coefficient of variation (CV = std/mean) for assessing stability.

    A lower CV indicates more consistent performance across runs.

    Args:
        df: DataFrame containing benchmark results
        metric: Column name to compute CV for
        group_by: List of columns to group by

    Returns:
        DataFrame with CV values (as percentage)
    """
    stats = df.groupby(group_by)[metric].agg([
        ('mean', 'mean'),
        ('std', 'std')
    ]).reset_index()

    stats['cv_pct'] = (stats['std'] / stats['mean']) * 100.0

    return stats[group_by + ['cv_pct']]


def compute_speedup(
    df: pd.DataFrame,
    metric: str,
    baseline_filter: dict,
    group_by: List[str]
) -> pd.DataFrame:
    """
    Compute speedup relative to a baseline configuration.

    Args:
        df: DataFrame containing benchmark results
        metric: Metric to compute speedup for (e.g., "wall_time_s")
        baseline_filter: Dict of column:value pairs identifying baseline
                        (e.g., {"system": "openfold", "variant": "bf16_model3"})
        group_by: List of columns to group by

    Returns:
        DataFrame with speedup values (baseline_time / variant_time)
    """
    # Get baseline statistics
    baseline_df = df.copy()
    for col, val in baseline_filter.items():
        baseline_df = baseline_df[baseline_df[col] == val]

    baseline_stats = baseline_df.groupby(group_by)[metric].median().reset_index()
    baseline_stats.rename(columns={metric: 'baseline_median'}, inplace=True)

    # Get all variant statistics
    all_stats = df.groupby(group_by + list(baseline_filter.keys()))[metric].median().reset_index()

    # Merge and compute speedup
    merged = all_stats.merge(baseline_stats, on=group_by, how='left')
    merged['speedup'] = merged['baseline_median'] / merged[metric]

    return merged


def detect_outliers_iqr(
    df: pd.DataFrame,
    metric: str,
    group_by: List[str],
    iqr_factor: float = 1.5
) -> pd.DataFrame:
    """
    Detect outliers using IQR (Interquartile Range) method.

    Outliers are values that fall outside [Q1 - iqr_factor*IQR, Q3 + iqr_factor*IQR].

    Args:
        df: DataFrame containing benchmark results
        metric: Column to detect outliers in
        group_by: List of columns to group by
        iqr_factor: Multiplier for IQR (1.5 is standard, 3.0 is more conservative)

    Returns:
        DataFrame with boolean 'is_outlier' column added
    """
    df = df.copy()
    df['is_outlier'] = False

    for group_vals, group_df in df.groupby(group_by):
        values = group_df[metric]

        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        lower_bound = q1 - iqr_factor * iqr
        upper_bound = q3 + iqr_factor * iqr

        outliers = (values < lower_bound) | (values > upper_bound)
        df.loc[group_df.index[outliers], 'is_outlier'] = True

    return df


def bootstrap_confidence_interval(
    data: np.ndarray,
    statistic: str = 'median',
    confidence: float = 0.95,
    n_bootstrap: int = 10000
) -> tuple[float, float, float]:
    """
    Compute bootstrap confidence interval for a statistic.

    Args:
        data: Array of measurements
        statistic: 'median', 'mean', 'p95', or 'p99'
        confidence: Confidence level (e.g., 0.95 for 95% CI)
        n_bootstrap: Number of bootstrap samples

    Returns:
        Tuple of (point_estimate, lower_ci, upper_ci)
    """
    stat_funcs = {
        'median': np.median,
        'mean': np.mean,
        'p95': lambda x: np.percentile(x, 95),
        'p99': lambda x: np.percentile(x, 99),
    }

    if statistic not in stat_funcs:
        raise ValueError(f"Unknown statistic: {statistic}")

    stat_func = stat_funcs[statistic]

    # Generate bootstrap samples
    bootstrap_stats = []
    n = len(data)

    for _ in range(n_bootstrap):
        sample = np.random.choice(data, size=n, replace=True)
        bootstrap_stats.append(stat_func(sample))

    bootstrap_stats = np.array(bootstrap_stats)

    # Compute confidence interval
    alpha = 1 - confidence
    lower_percentile = (alpha / 2) * 100
    upper_percentile = (1 - alpha / 2) * 100

    point_estimate = stat_func(data)
    lower_ci = np.percentile(bootstrap_stats, lower_percentile)
    upper_ci = np.percentile(bootstrap_stats, upper_percentile)

    return point_estimate, lower_ci, upper_ci

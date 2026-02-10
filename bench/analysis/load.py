"""Load benchmark results from disk."""

import json
from pathlib import Path
from typing import Tuple

import pandas as pd

from bench.logging import logger
from bench.results.schema import RunManifest


def load_results(run_dir: Path) -> Tuple[RunManifest, pd.DataFrame]:
    """
    Load benchmark results from a run directory.

    Args:
        run_dir: Directory containing benchmark results

    Returns:
        Tuple of (manifest, records_dataframe)
    """
    run_dir = Path(run_dir)

    # Load manifest
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path) as f:
        manifest_data = json.load(f)
    manifest = RunManifest(**manifest_data)

    logger.info(f"Loaded manifest for run: {manifest.run_id}")

    # Load records (prefer Parquet)
    parquet_path = run_dir / "records.parquet"
    jsonl_path = run_dir / "records.jsonl"

    if parquet_path.exists():
        logger.info(f"Loading records from Parquet: {parquet_path}")
        df = pd.read_parquet(parquet_path)
    elif jsonl_path.exists():
        logger.info(f"Loading records from JSONL: {jsonl_path}")
        records = []
        with open(jsonl_path) as f:
            for line in f:
                records.append(json.loads(line))
        df = pd.DataFrame(records)
    else:
        raise FileNotFoundError(f"No records found in {run_dir}")

    logger.info(f"Loaded {len(df)} prediction records")

    return manifest, df


def load_multiple_results(run_dirs: list[Path]) -> pd.DataFrame:
    """
    Load and combine results from multiple run directories.

    Args:
        run_dirs: List of run directories

    Returns:
        Combined DataFrame with all records
    """
    all_dfs = []

    for run_dir in run_dirs:
        try:
            manifest, df = load_results(run_dir)
            all_dfs.append(df)
        except FileNotFoundError as e:
            logger.warning(f"Results not found in {run_dir}: {e}")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {run_dir}: {e}")
        except PermissionError as e:
            logger.warning(f"Permission denied reading {run_dir}: {e}")
        except Exception as e:
            # Re-raise unexpected errors instead of silently continuing
            logger.error(f"Unexpected error loading results from {run_dir}: {e}")
            raise

    if not all_dfs:
        raise ValueError("No results loaded from any directory")

    combined_df = pd.concat(all_dfs, ignore_index=True)
    logger.info(f"Combined {len(combined_df)} records from {len(all_dfs)} runs")

    return combined_df

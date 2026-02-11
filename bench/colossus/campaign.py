"""Campaign mode for multi-GPU benchmark orchestration and aggregation.

This module enables running benchmarks across multiple GPU types and
aggregating results for cross-GPU comparison studies.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

from bench.logging import logger


class Campaign:
    """Manage multi-GPU benchmark campaign."""

    def __init__(self, campaign_dir: Path, campaign_name: str):
        """Initialize campaign.

        Args:
            campaign_dir: Directory to store campaign data
            campaign_name: Descriptive name for the campaign
        """
        self.campaign_dir = Path(campaign_dir)
        self.campaign_name = campaign_name
        self.manifest_path = self.campaign_dir / "campaign_manifest.json"

        # Ensure directory exists
        self.campaign_dir.mkdir(parents=True, exist_ok=True)

        # Load or create manifest
        self.manifest = self._load_or_create_manifest()

    def _load_or_create_manifest(self) -> dict:
        """Load existing manifest or create new one."""
        if self.manifest_path.exists():
            logger.info(f"Loading campaign manifest from {self.manifest_path}")
            with open(self.manifest_path) as f:
                return json.load(f)
        else:
            logger.info(f"Creating new campaign: {self.campaign_name}")
            return {
                "campaign_name": self.campaign_name,
                "created_at": datetime.now().isoformat(),
                "runs": [],
            }

    def _save_manifest(self):
        """Save manifest to disk."""
        with open(self.manifest_path, "w") as f:
            json.dump(self.manifest, f, indent=2, default=str)

    def register_run(self, run_dir: Path):
        """Register a completed benchmark run.

        Args:
            run_dir: Directory containing run results (manifest.json)
        """
        run_dir = Path(run_dir)
        manifest_file = run_dir / "manifest.json"

        if not manifest_file.exists():
            raise FileNotFoundError(f"No manifest found in {run_dir}")

        logger.info(f"Registering run from {run_dir}")

        # Load run manifest
        with open(manifest_file) as f:
            run_manifest = json.load(f)

        # Extract key info
        run_info = {
            "run_id": run_manifest["run_id"],
            "run_dir": str(run_dir.absolute()),
            "gpu_model": run_manifest["system_info"]["gpu_models"][0],
            "gpu_vram_mb": run_manifest["system_info"]["gpu_vram_mb"][0],
            "start_time": run_manifest["start_time"],
            "end_time": run_manifest.get("end_time"),
            "records_count": run_manifest["records_count"],
            "status": run_manifest["status"],
            "registered_at": datetime.now().isoformat(),
        }

        # Add NIM metadata if available
        if "nim_metadata" in run_manifest and run_manifest["nim_metadata"]:
            run_info["nim_backend"] = run_manifest["nim_metadata"].get("backend")
            run_info["nim_container_digest"] = run_manifest["nim_metadata"].get(
                "container_digest"
            )

        # Add to campaign
        self.manifest["runs"].append(run_info)
        self._save_manifest()

        logger.info(
            f"Registered run {run_info['run_id']} "
            f"({run_info['gpu_model']}, {run_info['records_count']} records)"
        )

    def list_runs(self) -> List[dict]:
        """Get list of registered runs.

        Returns:
            List of run info dictionaries
        """
        return self.manifest["runs"]

    def aggregate_results(self) -> pd.DataFrame:
        """Aggregate results from all registered runs.

        Returns:
            Combined DataFrame with results from all runs
        """
        logger.info(f"Aggregating {len(self.manifest['runs'])} runs")

        dfs = []
        for run_info in self.manifest["runs"]:
            run_dir = Path(run_info["run_dir"])
            parquet_path = run_dir / "records.parquet"

            if not parquet_path.exists():
                logger.warning(f"No parquet file found for run {run_info['run_id']}")
                continue

            # Load run data
            df = pd.read_parquet(parquet_path)

            # Add campaign metadata columns
            df["campaign_gpu"] = run_info["gpu_model"]
            df["campaign_run_id"] = run_info["run_id"]
            df["campaign_gpu_vram_gb"] = run_info["gpu_vram_mb"] / 1024

            if "nim_backend" in run_info:
                df["campaign_nim_backend"] = run_info["nim_backend"]

            dfs.append(df)

        if not dfs:
            raise ValueError("No data to aggregate")

        # Combine all runs
        combined = pd.concat(dfs, ignore_index=True)

        # Save aggregated data
        aggregated_path = self.campaign_dir / "aggregated.parquet"
        combined.to_parquet(aggregated_path, index=False)
        logger.info(f"Saved aggregated data: {aggregated_path} ({len(combined)} records)")

        # Save CSV for easy inspection
        csv_path = self.campaign_dir / "aggregated.csv"
        combined.to_csv(csv_path, index=False)
        logger.info(f"Saved CSV: {csv_path}")

        return combined

    def generate_comparison_report(self, output_path: Optional[Path] = None) -> Path:
        """Generate cross-GPU comparison report.

        Args:
            output_path: Path for report HTML (default: campaign_dir/report.html)

        Returns:
            Path to generated report
        """
        if output_path is None:
            output_path = self.campaign_dir / "campaign_report.html"

        logger.info("Generating campaign comparison report")

        # Load aggregated data
        aggregated_path = self.campaign_dir / "aggregated.parquet"
        if not aggregated_path.exists():
            logger.info("Aggregated data not found, running aggregation first")
            df = self.aggregate_results()
        else:
            df = pd.read_parquet(aggregated_path)

        # Generate summary statistics by GPU
        from bench.analysis.statistics import compute_distribution_stats

        stats = compute_distribution_stats(
            df, "wall_time_s", ["campaign_gpu", "system", "variant"]
        )

        # Create HTML report
        html_content = self._build_campaign_html(stats, df)

        with open(output_path, "w") as f:
            f.write(html_content)

        logger.info(f"Campaign report saved: {output_path}")
        return output_path

    def _build_campaign_html(self, stats: pd.DataFrame, df: pd.DataFrame) -> str:
        """Build HTML content for campaign report.

        Args:
            stats: Distribution statistics DataFrame
            df: Full aggregated results DataFrame

        Returns:
            HTML string
        """
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Campaign Report: {self.campaign_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>Campaign Report: {self.campaign_name}</h1>

    <div class="summary">
        <h2>Campaign Summary</h2>
        <p><strong>Total Runs:</strong> {len(self.manifest['runs'])}</p>
        <p><strong>Total Records:</strong> {len(df)}</p>
        <p><strong>GPU Types:</strong> {', '.join(df['campaign_gpu'].unique())}</p>
    </div>

    <h2>Performance Statistics by GPU</h2>
    {stats.to_html(index=False, float_format='%.4f')}

    <h2>Registered Runs</h2>
    <table>
        <tr>
            <th>Run ID</th>
            <th>GPU</th>
            <th>VRAM (GB)</th>
            <th>Records</th>
            <th>Start Time</th>
            <th>Status</th>
        </tr>
"""

        for run in self.manifest["runs"]:
            html += f"""
        <tr>
            <td>{run['run_id']}</td>
            <td>{run['gpu_model']}</td>
            <td>{run['gpu_vram_mb'] / 1024:.0f}</td>
            <td>{run['records_count']}</td>
            <td>{run['start_time']}</td>
            <td>{run['status']}</td>
        </tr>
"""

        html += """
    </table>
</body>
</html>
"""
        return html

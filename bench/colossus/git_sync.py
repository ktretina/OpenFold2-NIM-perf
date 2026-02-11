"""Git synchronization for automated result tracking.

This module provides automated Git commits and pushes for checkpoint
data and results during benchmark runs.
"""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from bench.logging import logger


class GitSync:
    """Git synchronization for results."""

    def __init__(self, run_dir: Path, run_id: str, hw_profile: dict):
        """Initialize Git sync.

        Args:
            run_dir: Directory containing results
            run_id: Unique run identifier
            hw_profile: Hardware profile dictionary
        """
        self.run_dir = Path(run_dir)
        self.run_id = run_id
        self.hw_profile = hw_profile
        self.branch_name: Optional[str] = None
        self.enabled = False

    def setup(self):
        """Set up Git branch for results tracking."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        gpu = self.hw_profile.get("gpu_model", "unknown").lower().replace(" ", "_")
        self.branch_name = f"results/{self.run_id}_{gpu}_{timestamp}"

        logger.info(f"Setting up Git sync on branch: {self.branch_name}")

        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.run_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                logger.warning("Not in a Git repository - Git sync disabled")
                return

            # Create and checkout branch
            subprocess.run(
                ["git", "checkout", "-b", self.branch_name],
                cwd=self.run_dir,
                capture_output=True,
                timeout=10,
            )

            self.enabled = True
            logger.info("Git sync enabled")

        except Exception as e:
            logger.warning(f"Failed to set up Git sync: {e}")
            self.enabled = False

    def push_checkpoint(self, manifest: dict, checkpoint_state: dict):
        """Push checkpoint to Git.

        Args:
            manifest: Run manifest dictionary
            checkpoint_state: Checkpoint state dictionary
        """
        if not self.enabled:
            return

        try:
            # Stage files
            files_to_add = [
                "manifest.json",
                "checkpoint.json",
                "records.jsonl",
                "records.parquet",
            ]

            subprocess.run(
                ["git", "add"] + files_to_add,
                cwd=self.run_dir,
                capture_output=True,
                timeout=10,
            )

            # Create commit message
            completed = checkpoint_state.get("completed_count", 0)
            total = checkpoint_state.get("total_tasks", 0)
            gpu = self.hw_profile.get("gpu_model", "unknown")

            commit_msg = (
                f"Checkpoint: {completed}/{total} tasks ({gpu})\n\n"
                f"Run ID: {self.run_id}\n"
                f"GPU: {gpu}\n"
                f"Progress: {completed}/{total} ({100*completed/total:.1f}%)"
            )

            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.run_dir,
                capture_output=True,
                timeout=10,
            )

            # Push to remote
            subprocess.run(
                ["git", "push", "-u", "origin", self.branch_name],
                cwd=self.run_dir,
                capture_output=True,
                timeout=30,
            )

            logger.info(f"Pushed checkpoint: {completed}/{total} tasks")

        except Exception as e:
            logger.warning(f"Failed to push checkpoint: {e}")

    def push_final(self, manifest: dict):
        """Push final results to Git.

        Args:
            manifest: Run manifest dictionary
        """
        if not self.enabled:
            return

        try:
            # Stage all results
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.run_dir,
                capture_output=True,
                timeout=10,
            )

            # Create final commit
            gpu = self.hw_profile.get("gpu_model", "unknown")
            records = manifest.get("records_count", 0)

            commit_msg = (
                f"Final results: {self.run_id} ({gpu})\n\n"
                f"Run ID: {self.run_id}\n"
                f"GPU: {gpu}\n"
                f"Total Records: {records}\n"
                f"Status: {manifest.get('status', 'unknown')}"
            )

            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.run_dir,
                capture_output=True,
                timeout=10,
            )

            # Push to remote
            subprocess.run(
                ["git", "push", "origin", self.branch_name],
                cwd=self.run_dir,
                capture_output=True,
                timeout=30,
            )

            logger.info("Pushed final results")

        except Exception as e:
            logger.warning(f"Failed to push final results: {e}")

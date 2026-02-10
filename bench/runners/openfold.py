"""OpenFold runner implementation."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

from bench.config import OpenFoldConfig
from bench.dataset.openfold_precomputed import create_openfold_alignment_dir
from bench.logging import logger
from bench.monitoring.metrics import (
    compute_avg_cpu_util,
    compute_avg_sm_util,
    compute_energy_wh,
    compute_peak_mem,
    compute_peak_rss,
    compute_peak_sm_util,
)
from bench.monitoring.nvml_sampler import NVMLSampler
from bench.monitoring.process_tree import get_process_tree
from bench.monitoring.system_sampler import SystemSampler
from bench.runners.base import PredictionResult, RunnerBase
from bench.scoring.confidence import extract_mean_plddt_from_pdb


class OpenFoldRunner(RunnerBase):
    """Runner for open-source OpenFold."""

    def __init__(
        self,
        config: OpenFoldConfig,
        gpu_ids: list[int],
        output_dir: Path,
        workdir: Path,
    ):
        """
        Initialize OpenFold runner.

        Args:
            config: OpenFold configuration
            gpu_ids: GPU device IDs to use
            output_dir: Directory for output structures
            workdir: Working directory for intermediate files
        """
        self.config = config
        self.gpu_ids = gpu_ids
        self.output_dir = output_dir
        self.workdir = workdir
        self.python_bin: Optional[Path] = None

        # Create directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.workdir.mkdir(parents=True, exist_ok=True)

    def setup(self) -> None:
        """Clone repository and install dependencies."""
        if not self.config.enabled:
            return

        repo_path = Path(self.config.repo_path)

        # Clone repository if it doesn't exist
        if not repo_path.exists():
            logger.info("Cloning OpenFold repository to %s", repo_path)
            try:
                subprocess.run(
                    [
                        "git",
                        "clone",
                        "https://github.com/aqlaboratory/openfold.git",
                        str(repo_path),
                    ],
                    check=True,
                    capture_output=True,
                )
                logger.info("Successfully cloned OpenFold repository")
            except subprocess.CalledProcessError as e:
                logger.error("Failed to clone repository: %s", e.stderr.decode())
                raise

        # Checkout specific commit
        logger.info("Checking out commit: %s", self.config.commit_hash)
        try:
            subprocess.run(
                ["git", "checkout", self.config.commit_hash],
                cwd=repo_path,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error("Failed to checkout commit: %s", e.stderr.decode())
            raise

        # Create virtual environment
        venv_path = repo_path / "venv"
        if not venv_path.exists():
            logger.info("Creating virtual environment at %s", venv_path)
            try:
                subprocess.run(
                    [sys.executable, "-m", "venv", str(venv_path)],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                logger.error("Failed to create venv: %s", e.stderr.decode())
                raise

        self.python_bin = venv_path / "bin" / "python"

        # Install OpenFold
        logger.info("Installing OpenFold dependencies...")
        try:
            subprocess.run(
                [str(self.python_bin), "-m", "pip", "install", "-e", "."],
                cwd=repo_path,
                check=True,
                capture_output=True,
            )
            logger.info("Successfully installed OpenFold")
        except subprocess.CalledProcessError as e:
            logger.error("Failed to install OpenFold: %s", e.stderr.decode())
            raise

    def start(self) -> None:
        """No-op for OpenFold (stateless)."""
        if not self.config.enabled:
            return

        # Verify python binary exists
        if self.python_bin is None:
            self.python_bin = Path(self.config.repo_path) / "venv" / "bin" / "python"

        if not self.python_bin.exists():
            raise RuntimeError(
                f"OpenFold Python binary not found at {self.python_bin}. "
                "Did you run setup()?"
            )

        logger.info("OpenFold runner ready (using %s)", self.python_bin)

    def predict(
        self,
        target_id: str,
        sequence: str,
        msa_depth: int,
        variant: str,
        models: list[int],
    ) -> PredictionResult:
        """
        Run OpenFold inference.

        Args:
            target_id: Target identifier
            sequence: Amino acid sequence
            msa_depth: MSA depth for synthetic MSA generation
            variant: Variant identifier
            models: Model indices to use (currently ignored, controlled by preset)

        Returns:
            PredictionResult with metrics
        """
        # Prepare input directories
        fasta_dir = self.workdir / "fastas"
        fasta_dir.mkdir(exist_ok=True)
        fasta_file = fasta_dir / f"{target_id}.fasta"
        fasta_file.write_text(f">{target_id}\n{sequence}\n")

        # Prepare precomputed alignments directory
        alignment_parent = self.workdir / "alignments"
        alignment_parent.mkdir(exist_ok=True)
        alignment_dir = alignment_parent / target_id

        logger.debug(
            "Creating precomputed alignments for %s (depth=%d)", target_id, msa_depth
        )
        create_openfold_alignment_dir(target_id, sequence, msa_depth, alignment_parent)

        # Prepare template directory (even if empty)
        template_dir = self.workdir / "templates"
        template_dir.mkdir(exist_ok=True)

        # Prepare output directory
        output_dir = self.output_dir / target_id / variant
        output_dir.mkdir(parents=True, exist_ok=True)

        # Parse variant to get configuration
        # variant format: "openfold_<preset>_<precision>_[deepspeed]"
        precision = self.config.precision
        use_deepspeed = self.config.use_deepspeed
        model_preset = self.config.model_presets[0]  # Use first preset

        # Build command
        run_script = Path(self.config.repo_path) / "run_pretrained_openfold.py"
        if not run_script.exists():
            raise RuntimeError(f"OpenFold run script not found: {run_script}")

        cmd = [
            str(self.python_bin),
            str(run_script),
            str(fasta_dir),
            str(template_dir),
            "--output_dir",
            str(output_dir),
            "--use_precomputed_alignments",
            str(alignment_parent),
            "--config_preset",
            model_preset,
            "--model_device",
            f"cuda:{self.gpu_ids[0]}",
        ]

        # Add precision flag if supported
        if precision == "bf16":
            cmd.extend(["--precision", "bf16"])
        elif precision == "fp32":
            cmd.extend(["--precision", "fp32"])

        # Add DeepSpeed flag if enabled
        if use_deepspeed:
            cmd.append("--use_deepspeed_inference")

        logger.info("Running OpenFold prediction for %s (variant: %s)", target_id, variant)
        logger.debug("Command: %s", " ".join(cmd))

        # Start monitoring
        nvml_sampler = NVMLSampler(self.gpu_ids, interval_ms=50)
        system_sampler = SystemSampler(tracked_pids=[], interval_ms=100)

        nvml_sampler.start()
        system_sampler.start()

        t0 = subprocess.time.time() if hasattr(subprocess, 'time') else __import__('time').time()

        # Run subprocess
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.config.repo_path,
            )

            # Track subprocess tree for CPU monitoring
            import time
            time.sleep(0.5)  # Give process time to spawn
            pids = get_process_tree(proc.pid)
            for pid in pids:
                system_sampler.add_pid(pid)
            logger.debug("Tracking %d OpenFold PIDs for system monitoring", len(pids))

            stdout, stderr = proc.communicate(timeout=3600)

            if proc.returncode != 0:
                logger.error("OpenFold failed with return code %d", proc.returncode)
                logger.error("STDOUT: %s", stdout.decode())
                logger.error("STDERR: %s", stderr.decode())
                raise RuntimeError(f"OpenFold failed: {stderr.decode()}")

        except subprocess.TimeoutExpired:
            logger.error("OpenFold timed out after 3600s")
            proc.kill()
            raise
        except Exception as e:
            logger.error("OpenFold execution failed: %s", e)
            raise
        finally:
            # Always stop monitoring
            import time
            wall_time = time.time() - t0
            nvml_samples = nvml_sampler.stop()
            system_samples = system_sampler.stop()

        logger.info("OpenFold prediction completed in %.2fs", wall_time)

        # Parse output structure
        # OpenFold writes to predictions/<target_id>/relaxed_model_*.pdb
        pred_dir = output_dir / "predictions" / target_id
        if not pred_dir.exists():
            # Fallback to checking output_dir directly
            pred_dir = output_dir

        structure_files = list(pred_dir.glob("relaxed_model_*.pdb"))
        if not structure_files:
            structure_files = list(pred_dir.glob("unrelaxed_model_*.pdb"))

        if not structure_files:
            raise RuntimeError(
                f"No output structures found in {pred_dir}. "
                f"Check OpenFold logs for errors."
            )

        # Take the first structure (or could rank by pLDDT if timings.json available)
        best_structure = structure_files[0]
        logger.debug("Found output structure: %s", best_structure)

        # Compute metrics
        time_to_first_gpu = nvml_sampler.compute_time_to_first_gpu_activity(t0)
        avg_util = compute_avg_sm_util(nvml_samples, self.gpu_ids)
        peak_util = compute_peak_sm_util(nvml_samples, self.gpu_ids)
        peak_mem = compute_peak_mem(nvml_samples, self.gpu_ids)
        energy_wh = compute_energy_wh(nvml_samples, self.gpu_ids)

        # Average power
        avg_power = (energy_wh * 3600.0 / wall_time) if wall_time > 0 else 0.0

        # CPU metrics
        cpu_util = compute_avg_cpu_util(system_samples)
        cpu_rss = compute_peak_rss(system_samples)

        # Extract pLDDT from structure B-factors
        mean_plddt = extract_mean_plddt_from_pdb(best_structure)

        logger.info(
            "Metrics - GPU util: %.1f%%, GPU mem: %.0f MB, Energy: %.3f Wh, pLDDT: %.1f",
            avg_util,
            peak_mem,
            energy_wh,
            mean_plddt,
        )

        return PredictionResult(
            output_structure_path=best_structure,
            wall_time_s=wall_time,
            time_to_first_gpu_activity_s=time_to_first_gpu,
            time_to_first_response_byte_s=None,  # N/A for OpenFold
            gpu_sm_util_avg_pct=avg_util,
            gpu_sm_util_peak_pct=peak_util,
            gpu_mem_peak_mb=peak_mem,
            gpu_energy_wh=energy_wh,
            gpu_power_avg_w=avg_power,
            cpu_rss_peak_mb=cpu_rss,
            cpu_util_avg_pct=cpu_util,
            mean_plddt=mean_plddt,
            timeseries_samples=nvml_samples,
        )

    def stop(self) -> None:
        """No-op for OpenFold (stateless)."""
        logger.debug("OpenFold runner stopped")

    def get_metadata(self) -> dict:
        """Get OpenFold metadata."""
        metadata = {
            "repo_path": str(self.config.repo_path),
            "commit_hash": self.config.commit_hash,
            "precision": self.config.precision,
            "use_deepspeed": self.config.use_deepspeed,
        }

        # Get git commit hash
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.config.repo_path,
                capture_output=True,
                check=True,
            )
            metadata["actual_commit"] = result.stdout.decode().strip()
        except subprocess.CalledProcessError:
            logger.warning("Failed to get git commit hash")

        # Get Python version
        if self.python_bin:
            try:
                result = subprocess.run(
                    [str(self.python_bin), "--version"],
                    capture_output=True,
                    check=True,
                )
                metadata["python_version"] = result.stdout.decode().strip()
            except subprocess.CalledProcessError:
                logger.warning("Failed to get Python version")

        # Get PyTorch version
        if self.python_bin:
            try:
                result = subprocess.run(
                    [
                        str(self.python_bin),
                        "-c",
                        "import torch; print(torch.__version__)",
                    ],
                    capture_output=True,
                    check=True,
                )
                metadata["torch_version"] = result.stdout.decode().strip()
            except subprocess.CalledProcessError:
                logger.warning("Failed to get PyTorch version")

        return metadata

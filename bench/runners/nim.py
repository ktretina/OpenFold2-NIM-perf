"""NIM (NVIDIA Inference Microservice) runner implementation."""

import os
import time
import uuid
from pathlib import Path
from typing import Optional

import docker
import requests

from bench.config import NIMConfig
from bench.dataset.nim_payloads import create_nim_payload
from bench.dataset.synthetic_msa import generate_synthetic_a3m
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
from bench.monitoring.process_tree import get_container_main_pid, get_process_tree
from bench.monitoring.system_sampler import SystemSampler
from bench.runners.base import PredictionResult, RunnerBase


class NIMRunner(RunnerBase):
    """Runner for OpenFold2 NIM microservice."""

    def __init__(
        self, config: NIMConfig, gpu_ids: list[int], output_dir: Path, workdir: Path
    ):
        """
        Initialize NIM runner.

        Args:
            config: NIM configuration
            gpu_ids: GPU device IDs to use
            output_dir: Directory for output structures
            workdir: Working directory for intermediate files
        """
        self.config = config
        self.gpu_ids = gpu_ids
        self.output_dir = output_dir
        self.workdir = workdir
        self.container: Optional[docker.models.containers.Container] = None
        self.base_url = config.base_url
        self._container_name: Optional[str] = None

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def setup(self) -> None:
        """One-time setup (pull container image if needed)."""
        if not self.config.enabled:
            return

        if self.base_url:
            logger.info("Using existing NIM service at %s", self.base_url)
            return

        # Pull container image
        logger.info("Pulling NIM container image: %s", self.config.container_image)
        try:
            client = docker.from_env()
            client.images.pull(self.config.container_image)
            logger.info("Successfully pulled NIM container image")
        except docker.errors.DockerException as e:
            logger.warning("Failed to pull container image: %s", e)
            logger.warning("Will attempt to use cached image if available")

    def start(self) -> None:
        """Start NIM container or connect to existing service."""
        if not self.config.enabled:
            return

        if self.base_url:
            # Use existing NIM
            self._wait_for_ready()
            logger.info("Connected to existing NIM at %s", self.base_url)
        else:
            # Start local container
            self._start_container()

    def _start_container(self):
        """Start NIM container with proper configuration."""
        client = docker.from_env()

        # Check NGC_API_KEY
        if "NGC_API_KEY" not in os.environ:
            raise RuntimeError("NGC_API_KEY environment variable not set")

        # Prepare environment
        env = {
            "NGC_API_KEY": os.environ["NGC_API_KEY"],
        }
        if self.config.backend == "torch":
            env["NIM_OPTIMIZED_BACKEND"] = "torch"

        # Create cache directory (Fix #12: Validate write permissions)
        cache_dir = Path(self.config.cache_dir).resolve()
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            # Test write permission
            test_file = cache_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except PermissionError as e:
            raise RuntimeError(
                f"Cannot write to cache directory: {cache_dir}. "
                f"Check permissions or set cache_dir in config."
            ) from e

        # Generate unique container name
        self._container_name = f"openfold2-nim-{uuid.uuid4().hex[:8]}"

        logger.info("Starting NIM container: %s", self._container_name)
        logger.info("Cache directory: %s", cache_dir)
        logger.info("Backend: %s", self.config.backend)
        logger.info("GPUs: %s", self.gpu_ids)

        # Start container (Fix #8: Handle port conflicts)
        port = self.config.port
        for attempt in range(10):
            try:
                self.container = client.containers.run(
                    self.config.container_image,
                    detach=True,
                    device_requests=[
                        docker.types.DeviceRequest(
                            device_ids=[str(i) for i in self.gpu_ids],
                            capabilities=[["gpu"]],
                        )
                    ],
                    ports={"8000/tcp": port},
                    volumes={
                        str(cache_dir.absolute()): {"bind": "/opt/nim/.cache", "mode": "rw"}
                    },
                    environment=env,
                    name=self._container_name,
                    remove=False,  # Keep container for debugging
                )

                self.base_url = f"http://localhost:{port}"
                if port != self.config.port:
                    logger.info("Using alternate port %d (default port %d was in use)", port, self.config.port)

                # Wait for ready and record cold start time
                logger.info("Waiting for NIM to be ready...")
                t0 = time.time()
                self._wait_for_ready(timeout=600)
                cold_start_time = time.time() - t0
                logger.info("NIM ready! Cold start time: %.1fs", cold_start_time)
                break

            except docker.errors.APIError as e:
                # Check if port conflict error
                if "port is already allocated" in str(e).lower() or "address already in use" in str(e).lower():
                    logger.warning("Port %d is in use, trying port %d", port, port + 1)
                    port += 1
                    if attempt == 9:
                        logger.error("All ports %d-%d are in use", self.config.port, port)
                        raise RuntimeError(f"Cannot find available port for NIM (tried {self.config.port}-{port})")
                else:
                    logger.error("Failed to start NIM container: %s", e)
                    raise
            except docker.errors.DockerException as e:
                logger.error("Failed to start NIM container: %s", e)
                raise

    def _wait_for_ready(self, timeout: int = 600):
        """
        Poll health endpoint until ready.

        Args:
            timeout: Maximum time to wait in seconds
        """
        health_url = f"{self.base_url}/v1/health/ready"
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                resp = requests.get(health_url, timeout=5)
                if resp.status_code == 200:
                    logger.debug("NIM health check passed")
                    return
                else:
                    logger.debug("NIM not ready yet (status %d)", resp.status_code)
            except requests.RequestException as e:
                logger.debug("NIM not ready yet: %s", e)

            time.sleep(2)

        raise RuntimeError(f"NIM not ready after {timeout}s")

    def predict(
        self,
        target_id: str,
        sequence: str,
        msa_depth: int,
        variant: str,
        models: list[int],
    ) -> PredictionResult:
        """
        Run NIM inference.

        Args:
            target_id: Target identifier
            sequence: Amino acid sequence
            msa_depth: MSA depth for synthetic MSA generation
            variant: Variant identifier (for logging)
            models: Model indices to use (e.g., [3] or [1,2,3,4,5])

        Returns:
            PredictionResult with metrics
        """
        # Generate synthetic MSAs
        logger.debug(
            "Generating synthetic MSA for %s (depth=%d)", target_id, msa_depth
        )
        payload = create_nim_payload(target_id, sequence, msa_depth)
        payload["selected_models"] = models

        # Start monitoring
        nvml_sampler = NVMLSampler(self.gpu_ids, interval_ms=50)
        system_sampler = SystemSampler(tracked_pids=[], interval_ms=100)

        # Get container PIDs for CPU monitoring if running locally
        if self.container:
            try:
                main_pid = get_container_main_pid(self._container_name)
                pids = get_process_tree(main_pid)
                for pid in pids:
                    system_sampler.add_pid(pid)
                logger.debug("Tracking %d container PIDs for system monitoring", len(pids))
            except Exception as e:
                logger.warning("Failed to get container PIDs: %s", e)

        nvml_sampler.start()
        system_sampler.start()

        # Make request
        logger.info("Running NIM prediction for %s (variant: %s)", target_id, variant)
        t0 = time.time()
        ttfb = None

        endpoint = f"{self.base_url}/biology/openfold/openfold2/predict-structure-from-msa-and-template"

        try:
            with requests.post(
                endpoint, json=payload, stream=True, timeout=3600
            ) as resp:
                resp.raise_for_status()

                # Capture time to first byte
                for chunk in resp.iter_content(chunk_size=1):
                    if chunk and ttfb is None:
                        ttfb = time.time() - t0
                        logger.debug("Time to first byte: %.3fs", ttfb)
                    break

                # Read rest of response
                result = resp.json()

        except requests.RequestException as e:
            logger.error("NIM request failed: %s", e)
            nvml_sampler.stop()
            system_sampler.stop()
            raise

        wall_time = time.time() - t0
        logger.info("NIM prediction completed in %.2fs", wall_time)

        # Stop monitoring
        nvml_samples = nvml_sampler.stop()
        system_samples = system_sampler.stop()

        # Extract structure
        if not result.get("structures_in_ranked_order"):
            raise RuntimeError("No structures returned by NIM")

        top_structure = result["structures_in_ranked_order"][0]
        structure_pdb = top_structure["structure"]
        confidence = top_structure.get("confidence", [])

        # Save structure
        output_path = self.output_dir / f"{target_id}_{variant}.pdb"
        output_path.write_text(structure_pdb)
        logger.debug("Saved structure to %s", output_path)

        # Compute derived metrics
        time_to_first_gpu = nvml_sampler.compute_time_to_first_gpu_activity(t0)
        avg_util = compute_avg_sm_util(nvml_samples, self.gpu_ids)
        peak_util = compute_peak_sm_util(nvml_samples, self.gpu_ids)
        peak_mem = compute_peak_mem(nvml_samples, self.gpu_ids)
        energy_wh = compute_energy_wh(nvml_samples, self.gpu_ids)

        # Compute average power
        avg_power = (energy_wh * 3600.0 / wall_time) if wall_time > 0 else 0.0

        # CPU metrics
        cpu_util = compute_avg_cpu_util(system_samples)
        cpu_rss = compute_peak_rss(system_samples)

        # Mean pLDDT
        import numpy as np

        mean_plddt = float(np.mean(confidence)) if confidence else 0.0

        logger.info(
            "Metrics - GPU util: %.1f%%, GPU mem: %.0f MB, Energy: %.3f Wh, pLDDT: %.1f",
            avg_util,
            peak_mem,
            energy_wh,
            mean_plddt,
        )

        return PredictionResult(
            output_structure_path=output_path,
            wall_time_s=wall_time,
            time_to_first_gpu_activity_s=time_to_first_gpu,
            time_to_first_response_byte_s=ttfb,
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
        """Stop and cleanup NIM container."""
        if self.container:
            logger.info("Stopping NIM container: %s", self._container_name)
            try:
                self.container.stop(timeout=10)
                logger.info("NIM container stopped")
            except docker.errors.DockerException as e:
                logger.warning("Error stopping container: %s", e)

            # Optionally remove container
            try:
                self.container.remove()
                logger.debug("NIM container removed")
            except docker.errors.DockerException as e:
                logger.warning("Error removing container: %s", e)

    def get_metadata(self) -> dict:
        """Get NIM metadata."""
        metadata = {
            "backend": self.config.backend,
            "container_image": self.config.container_image,
        }

        # Try to fetch metadata endpoint
        if self.base_url:
            try:
                resp = requests.get(f"{self.base_url}/v1/metadata", timeout=5)
                if resp.status_code == 200:
                    metadata["nim_metadata"] = resp.json()
            except requests.RequestException as e:
                logger.warning("Failed to fetch NIM metadata: %s", e)

        # Get container digest if running locally
        if self.container:
            try:
                self.container.reload()
                image = self.container.image
                if hasattr(image, "attrs") and "RepoDigests" in image.attrs:
                    metadata["container_digest"] = image.attrs["RepoDigests"][0]
            except Exception as e:
                logger.warning("Failed to get container digest: %s", e)

        return metadata

"""Benchmark orchestrator - coordinates runners and manages execution."""

import os
import platform
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import py3nvml.py3nvml as pynvml
import yaml

from bench.config import BenchmarkConfig, BenchmarkSuite
from bench.dataset.fetch_pdb import extract_chain_sequence, fetch_pdb_mmcif
from bench.logging import logger
from bench.results.schema import (
    NIMMetadata,
    OpenFoldMetadata,
    PredictionRecord,
    RunManifest,
    SystemInfo,
)
from bench.results.writer import ResultsWriter
from bench.runners.nim import NIMRunner
from bench.runners.openfold import OpenFoldRunner
from bench.scoring.parse_structures import parse_pdb_coordinates
from bench.scoring.rmsd import kabsch_rmsd
from bench.scoring.lddt import compute_lddt


def collect_system_info() -> SystemInfo:
    """Collect system hardware and software information."""
    logger.info("Collecting system information...")

    # Initialize NVML
    pynvml.nvmlInit()

    try:
        # GPU information
        device_count = pynvml.nvmlDeviceGetCount()
        gpu_models = []
        gpu_vram_mb = []

        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpu_models.append(name)
            gpu_vram_mb.append(int(mem.total / 1024**2))

        # Driver and CUDA version
        driver = pynvml.nvmlSystemGetDriverVersion()
        cuda = pynvml.nvmlSystemGetCudaDriverVersion_v2()
        cuda_str = f"{cuda // 1000}.{(cuda % 1000) // 10}"

    finally:
        pynvml.nvmlShutdown()

    # CPU information
    try:
        if platform.system() == "Linux":
            with open("/proc/cpuinfo") as f:
                cpuinfo = f.read()
            for line in cpuinfo.split("\n"):
                if "model name" in line:
                    cpu_model = line.split(":")[1].strip()
                    break
            else:
                cpu_model = "Unknown"
        else:
            cpu_model = platform.processor()
    except Exception:
        cpu_model = "Unknown"

    # RAM information
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                meminfo = f.read()
            for line in meminfo.split("\n"):
                if "MemTotal" in line:
                    ram_kb = int(line.split()[1])
                    ram_mb = ram_kb // 1024
                    break
            else:
                ram_mb = 0
        else:
            # Fallback for non-Linux
            import psutil

            ram_mb = int(psutil.virtual_memory().total / 1024**2)
    except Exception:
        ram_mb = 0

    info = SystemInfo(
        hostname=socket.gethostname(),
        gpu_models=gpu_models,
        gpu_vram_mb=gpu_vram_mb,
        gpu_driver=driver,
        cuda_version=cuda_str,
        cpu_model=cpu_model,
        ram_mb=ram_mb,
        kernel=platform.release(),
        timestamp=datetime.now(),
    )

    logger.info("System: %s", info.hostname)
    logger.info("GPUs: %s", ", ".join(gpu_models))
    logger.info("Driver: %s, CUDA: %s", driver, cuda_str)

    return info


class BenchmarkOrchestrator:
    """Orchestrates benchmark execution across runners."""

    def __init__(self, config: BenchmarkConfig, output_dir: Path):
        """
        Initialize orchestrator.

        Args:
            config: Benchmark configuration
            output_dir: Output directory for results
        """
        self.config = config
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Working directory for intermediate files
        self.workdir = output_dir / "work"
        self.workdir.mkdir(exist_ok=True)

        # Results writer
        self.writer = ResultsWriter(output_dir)

        # Initialize runners
        self.runners = {}

    def run(self) -> RunManifest:
        """
        Run complete benchmark.

        Returns:
            RunManifest with results summary
        """
        start_time = datetime.now()
        logger.info("=" * 80)
        logger.info("Starting benchmark run: %s", self.config.run_id)
        logger.info("=" * 80)

        # Collect system info
        system_info = collect_system_info()

        # Initialize runners
        self._initialize_runners()

        # Collect metadata
        nim_metadata = self._collect_nim_metadata() if self.config.nim.enabled else None
        openfold_metadata = (
            self._collect_openfold_metadata() if self.config.openfold.enabled else None
        )

        # Create manifest
        manifest = RunManifest(
            run_id=self.config.run_id,
            config=self.config.model_dump(),
            system_info=system_info,
            nim_metadata=nim_metadata,
            openfold_metadata=openfold_metadata,
            start_time=start_time,
            status="running",
        )

        self.writer.write_manifest(manifest)

        try:
            # Run warmup
            self._run_warmup()

            # Run measured benchmarks
            for suite in self.config.suites:
                logger.info("-" * 80)
                logger.info("Running suite: %s", suite.name)
                logger.info("-" * 80)
                self._run_suite(suite)

            # Finalize results
            self.writer.finalize()

            # Update manifest
            manifest.end_time = datetime.now()
            manifest.status = "completed"
            manifest.records_count = len(self.writer.records)
            self.writer.write_manifest(manifest)

            logger.info("=" * 80)
            logger.info("Benchmark completed successfully!")
            logger.info("Total predictions: %d", manifest.records_count)
            logger.info("Results: %s", self.output_dir)
            logger.info("=" * 80)

        except Exception as e:
            logger.error("Benchmark failed: %s", e, exc_info=True)
            manifest.end_time = datetime.now()
            manifest.status = "failed"
            manifest.error_message = str(e)
            self.writer.write_manifest(manifest)
            raise

        finally:
            # Stop runners
            self._stop_runners()

        return manifest

    def _initialize_runners(self):
        """Initialize all enabled runners."""
        logger.info("Initializing runners...")

        if self.config.nim.enabled:
            logger.info("Setting up NIM runner...")
            nim_runner = NIMRunner(
                self.config.nim,
                self.config.gpu.device_ids,
                self.output_dir / "structures",
                self.workdir / "nim",
            )
            nim_runner.setup()
            nim_runner.start()
            self.runners["nim"] = nim_runner
            logger.info("NIM runner ready")

        if self.config.openfold.enabled:
            logger.info("Setting up OpenFold runner...")
            openfold_runner = OpenFoldRunner(
                self.config.openfold,
                self.config.gpu.device_ids,
                self.output_dir / "structures",
                self.workdir / "openfold",
            )
            openfold_runner.setup()
            openfold_runner.start()
            self.runners["openfold"] = openfold_runner
            logger.info("OpenFold runner ready")

    def _collect_nim_metadata(self) -> Optional[NIMMetadata]:
        """Collect NIM metadata."""
        if "nim" not in self.runners:
            return None

        metadata_dict = self.runners["nim"].get_metadata()

        return NIMMetadata(
            container_digest=metadata_dict.get("container_digest"),
            backend=metadata_dict.get("backend", "unknown"),
            metadata_response=metadata_dict.get("nim_metadata"),
        )

    def _collect_openfold_metadata(self) -> Optional[OpenFoldMetadata]:
        """Collect OpenFold metadata."""
        if "openfold" not in self.runners:
            return None

        metadata_dict = self.runners["openfold"].get_metadata()

        return OpenFoldMetadata(
            git_commit=metadata_dict.get("actual_commit", metadata_dict.get("commit_hash", "unknown")),
            python_version=metadata_dict.get("python_version", "unknown"),
            torch_version=metadata_dict.get("torch_version"),
        )

    def _run_warmup(self):
        """Run warmup predictions to warm caches."""
        logger.info("Running warmup predictions...")

        # Use first suite for warmup
        if not self.config.suites:
            logger.warning("No suites configured, skipping warmup")
            return

        suite = self.config.suites[0]
        targets = self._load_targets(suite)

        if not targets:
            logger.warning("No targets found for warmup")
            return

        # Use first target
        target = targets[0]

        # Run warmup for each runner
        for system_name, runner in self.runners.items():
            variants = self._get_variants(system_name)
            for variant in variants[:1]:  # Just first variant
                logger.info("Warmup: %s - %s", system_name, variant)
                try:
                    models = self._parse_models_from_variant(system_name, variant)
                    runner.predict(
                        target_id=f"warmup_{target['id']}",
                        sequence=target["sequence"],
                        msa_depth=suite.msa_depth,
                        variant=variant,
                        models=models,
                    )
                except Exception as e:
                    logger.warning("Warmup failed for %s: %s", variant, e)

        logger.info("Warmup completed")

    def _run_suite(self, suite: BenchmarkSuite):
        """Run a benchmark suite."""
        targets = self._load_targets(suite)

        if not targets:
            logger.warning("No targets in suite %s", suite.name)
            return

        logger.info("Suite %s: %d targets", suite.name, len(targets))

        # Determine MSA depths to test
        msa_depths = suite.msa_depths if suite.msa_depths else [suite.msa_depth]

        # Run predictions
        for target in targets:
            for msa_depth in msa_depths:
                for system_name, runner in self.runners.items():
                    variants = self._get_variants(system_name)

                    for variant in variants:
                        models = self._parse_models_from_variant(system_name, variant)

                        # Run repeats
                        for repeat_idx in range(suite.repeats):
                            logger.info(
                                "Predicting: %s | %s | %s | MSA=%d | Repeat %d/%d",
                                suite.name,
                                target["id"],
                                variant,
                                msa_depth,
                                repeat_idx + 1,
                                suite.repeats,
                            )

                            try:
                                # Run prediction
                                result = runner.predict(
                                    target_id=target["id"],
                                    sequence=target["sequence"],
                                    msa_depth=msa_depth,
                                    variant=variant,
                                    models=models,
                                )

                                # Save timeseries
                                timeseries_path = self.writer.write_timeseries(
                                    target["id"], variant, result.timeseries_samples
                                )

                                # Compute accuracy if ground truth available
                                ca_rmsd = None
                                ca_lddt = None

                                if "ground_truth_coords" in target:
                                    try:
                                        pred_coords = parse_pdb_coordinates(
                                            result.output_structure_path, atoms=["CA"]
                                        )
                                        true_coords = target["ground_truth_coords"]

                                        ca_rmsd = kabsch_rmsd(pred_coords, true_coords)
                                        ca_lddt = compute_lddt(pred_coords, true_coords)

                                        logger.info(
                                            "Accuracy: RMSD=%.2f Å, lDDT=%.3f",
                                            ca_rmsd,
                                            ca_lddt,
                                        )
                                    except Exception as e:
                                        logger.warning(
                                            "Failed to compute accuracy: %s", e
                                        )

                                # Compute GPU hours
                                num_gpus = len(self.config.gpu.device_ids)
                                gpu_hours = result.wall_time_s * num_gpus / 3600.0

                                # Create record
                                record = PredictionRecord(
                                    run_id=self.config.run_id,
                                    suite=suite.name,
                                    target_id=target["id"],
                                    system=system_name,
                                    variant=variant,
                                    wall_time_s=result.wall_time_s,
                                    time_to_first_gpu_activity_s=result.time_to_first_gpu_activity_s,
                                    time_to_first_response_byte_s=result.time_to_first_response_byte_s,
                                    gpu_hours_per_prediction=gpu_hours,
                                    gpu_sm_util_avg_pct=result.gpu_sm_util_avg_pct,
                                    gpu_sm_util_peak_pct=result.gpu_sm_util_peak_pct,
                                    gpu_power_avg_w=result.gpu_power_avg_w,
                                    gpu_energy_wh=result.gpu_energy_wh,
                                    gpu_mem_peak_mb=result.gpu_mem_peak_mb,
                                    cpu_rss_peak_mb=result.cpu_rss_peak_mb,
                                    cpu_util_avg_pct=result.cpu_util_avg_pct,
                                    ca_rmsd=ca_rmsd,
                                    ca_lddt=ca_lddt,
                                    mean_plddt=result.mean_plddt,
                                    sequence_length=len(target["sequence"]),
                                    msa_depth=msa_depth,
                                    models_used=models,
                                    output_structure_path=result.output_structure_path,
                                    timeseries_path=timeseries_path,
                                    repeat_index=repeat_idx,
                                )

                                # Write record
                                self.writer.append_record(record)

                            except Exception as e:
                                logger.error(
                                    "Prediction failed for %s/%s: %s",
                                    target["id"],
                                    variant,
                                    e,
                                    exc_info=True,
                                )

    def _load_targets(self, suite: BenchmarkSuite) -> list[dict]:
        """Load targets for a suite."""
        targets = []

        # Load from YAML file
        if suite.targets_file:
            logger.info("Loading targets from %s", suite.targets_file)
            with open(suite.targets_file) as f:
                data = yaml.safe_load(f)

            for target_spec in data.get("targets", []):
                # Fetch PDB and extract sequence
                try:
                    pdb_id = target_spec["pdb_id"]
                    chain = target_spec["chain"]

                    # Download PDB if not cached
                    cache_dir = self.workdir / "pdb_cache"
                    cache_dir.mkdir(exist_ok=True)
                    mmcif_path = fetch_pdb_mmcif(pdb_id, cache_dir)

                    # Extract sequence and coordinates
                    sequence = extract_chain_sequence(mmcif_path, chain)
                    ground_truth_coords = parse_pdb_coordinates(mmcif_path, atoms=["CA"])

                    targets.append(
                        {
                            "id": f"{pdb_id}_{chain}",
                            "sequence": sequence,
                            "ground_truth_coords": ground_truth_coords,
                            "metadata": target_spec,
                        }
                    )

                    logger.debug("Loaded target %s_%s (%d residues)", pdb_id, chain, len(sequence))

                except Exception as e:
                    logger.warning(
                        "Failed to load target %s: %s", target_spec.get("pdb_id"), e
                    )

        # Generate synthetic sequences
        elif suite.sequences:
            logger.info("Generating synthetic sequences")
            for seq_spec in suite.sequences:
                seq_id = seq_spec["id"]
                length = seq_spec["length"]

                # Generate random sequence
                import random

                amino_acids = "ACDEFGHIKLMNPQRSTVWY"
                sequence = "".join(random.choices(amino_acids, k=length))

                targets.append({"id": seq_id, "sequence": sequence})

                logger.debug("Generated synthetic sequence %s (%d residues)", seq_id, length)

        return targets

    def _get_variants(self, system_name: str) -> list[str]:
        """Get list of variants for a system."""
        variants = []

        if system_name == "nim":
            backend = self.config.nim.backend
            for model_set in self.config.nim.model_sets:
                models_str = "-".join(map(str, model_set))
                variant = f"nim_{backend}_models-{models_str}"
                variants.append(variant)

        elif system_name == "openfold":
            for preset in self.config.openfold.model_presets:
                precision = self.config.openfold.precision
                variant = f"openfold_{preset}_{precision}"
                if self.config.openfold.use_deepspeed:
                    variant += "_deepspeed"
                variants.append(variant)

        return variants

    def _parse_models_from_variant(self, system_name: str, variant: str) -> list[int]:
        """Parse model indices from variant string."""
        if system_name == "nim":
            # variant format: "nim_tensorrt_models-1-2-3"
            parts = variant.split("models-")
            if len(parts) == 2:
                return [int(x) for x in parts[1].split("-")]
        elif system_name == "openfold":
            # For OpenFold, model is determined by preset (config)
            # Return dummy list
            return [1]

        return []

    def _stop_runners(self):
        """Stop all runners."""
        logger.info("Stopping runners...")
        for name, runner in self.runners.items():
            try:
                runner.stop()
                logger.info("Stopped %s runner", name)
            except Exception as e:
                logger.warning("Error stopping %s runner: %s", name, e)

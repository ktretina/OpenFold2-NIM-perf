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

    def _run_warmup(self, suite: BenchmarkSuite, targets: list[dict]):
        """Run dedicated warmup passes over all targets.

        Args:
            suite: Benchmark suite configuration
            targets: List of target dictionaries
        """
        if suite.warmup_passes == 0:
            logger.info("Warmup disabled for suite: %s", suite.name)
            return

        logger.info("Running %d warmup pass(es) for suite: %s",
                    suite.warmup_passes, suite.name)

        # Determine MSA depths
        msa_depths = suite.msa_depths if suite.msa_depths else [suite.msa_depth]

        for pass_idx in range(suite.warmup_passes):
            logger.info("WARMUP PASS %d/%d", pass_idx + 1, suite.warmup_passes)

            for target in targets:
                for msa_depth in msa_depths:
                    for system_name, runner in self.runners.items():
                        variants = self._get_variants(system_name)
                        for variant in variants:
                            try:
                                models = self._parse_models_from_variant(system_name, variant)

                                # Run prediction (results discarded)
                                _ = runner.predict(
                                    target_id=f"warmup_{target['id']}",
                                    sequence=target['sequence'],
                                    msa_depth=msa_depth,
                                    variant=variant,
                                    models=models,
                                )
                                logger.debug("Warmup: %s - %s - %s (MSA=%d)",
                                           target['id'], system_name, variant, msa_depth)
                            except Exception as e:
                                logger.warning("Warmup failed for %s-%s: %s",
                                             system_name, variant, e)

        logger.info("Warmup complete")

    def _run_suite(self, suite: BenchmarkSuite):
        """Run a benchmark suite (dispatcher).

        Args:
            suite: Benchmark suite configuration
        """
        if suite.suite_type == "cold_start":
            self._run_cold_start_suite(suite)
        else:
            self._run_standard_suite(suite)

    def _run_standard_suite(self, suite: BenchmarkSuite):
        """Run standard benchmark suite with warmup and measurement phases.

        Args:
            suite: Benchmark suite configuration
        """
        logger.info("Running suite: %s", suite.name)

        targets = self._load_targets(suite)

        if not targets:
            logger.warning("No targets in suite %s", suite.name)
            return

        logger.info("Suite %s: %d targets", suite.name, len(targets))

        # Load precomputed MSAs if configured
        if suite.precomputed_msa_dir:
            logger.info("Using precomputed MSAs from %s", suite.precomputed_msa_dir)
            from bench.dataset.precomputed import load_precomputed_inputs

            for target in targets:
                try:
                    precomputed = load_precomputed_inputs(
                        target['id'],
                        suite.precomputed_msa_dir
                    )
                    target['precomputed'] = precomputed
                    logger.debug("Loaded precomputed MSA for %s (hash: %s...)",
                               target['id'], precomputed.msa_hash[:16])
                except FileNotFoundError:
                    if suite.inference_only_mode:
                        logger.error("Precomputed MSA not found for %s (inference_only_mode=true)",
                                   target['id'])
                        raise
                    else:
                        logger.warning("Precomputed MSA not found for %s, will generate on-the-fly",
                                     target['id'])
                except Exception as e:
                    logger.error("Failed to load precomputed MSA for %s: %s",
                               target['id'], e)
                    if suite.inference_only_mode:
                        raise

        # Determine MSA depths to test
        msa_depths = suite.msa_depths if suite.msa_depths else [suite.msa_depth]

        # Phase 1: Warmup
        self._run_warmup(suite, targets)

        # Phase 2: Measurement passes
        measurement_passes = suite.measurement_passes
        logger.info("Running %d measurement pass(es)", measurement_passes)

        for pass_idx in range(measurement_passes):
            logger.info("MEASUREMENT PASS %d/%d", pass_idx + 1, measurement_passes)

            # Shuffle targets if configured
            targets_for_pass = targets.copy()
            if suite.shuffle_targets_each_pass:
                import random
                random.shuffle(targets_for_pass)
                logger.info("Shuffled target order for this pass")

            # Run predictions on all targets
            for target in targets_for_pass:
                for msa_depth in msa_depths:
                    for system_name, runner in self.runners.items():
                        variants = self._get_variants(system_name)

                        for variant in variants:
                            models = self._parse_models_from_variant(system_name, variant)

                            logger.info(
                                "Predicting: %s | %s | %s | MSA=%d | Pass %d/%d",
                                suite.name,
                                target["id"],
                                variant,
                                msa_depth,
                                pass_idx + 1,
                                measurement_passes,
                            )

                            try:
                                # Get precomputed inputs if available
                                precomputed_inputs = target.get('precomputed')

                                # Run prediction
                                result = runner.predict(
                                    target_id=target["id"],
                                    sequence=target["sequence"],
                                    msa_depth=msa_depth,
                                    variant=variant,
                                    models=models,
                                    precomputed_inputs=precomputed_inputs,
                                )

                                # Save timeseries
                                timeseries_path = self.writer.write_timeseries(
                                    target["id"], variant, result.timeseries_samples
                                )

                                # Compute accuracy if ground truth available
                                ca_rmsd = None
                                ca_lddt = None
                                tm_score = None
                                gdt_ts = None

                                if "ground_truth_coords" in target:
                                    try:
                                        pred_coords = parse_pdb_coordinates(
                                            result.output_structure_path, atoms=["CA"]
                                        )
                                        true_coords = target["ground_truth_coords"]

                                        # Import scoring functions
                                        from bench.scoring.tmscore import compute_tm_score
                                        from bench.scoring.gdtts import compute_gdt_ts

                                        ca_rmsd = kabsch_rmsd(pred_coords, true_coords)
                                        ca_lddt = compute_lddt(pred_coords, true_coords)
                                        tm_score = compute_tm_score(pred_coords, true_coords)
                                        gdt_ts = compute_gdt_ts(pred_coords, true_coords)

                                        logger.info(
                                            "Accuracy: RMSD=%.2f Å, lDDT=%.3f, TM-score=%.3f, GDT_TS=%.1f",
                                            ca_rmsd,
                                            ca_lddt,
                                            tm_score,
                                            gdt_ts,
                                        )
                                    except Exception as e:
                                        logger.warning(
                                            "Failed to compute accuracy: %s", e
                                        )

                                # Compute GPU hours
                                num_gpus = len(self.config.gpu.device_ids)
                                gpu_hours = result.wall_time_s * num_gpus / 3600.0

                                # Get MSA hash if precomputed
                                msa_hash = None
                                if precomputed_inputs:
                                    msa_hash = precomputed_inputs.msa_hash

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
                                    tm_score=tm_score,
                                    gdt_ts=gdt_ts,
                                    mean_plddt=result.mean_plddt,
                                    sequence_length=len(target["sequence"]),
                                    msa_depth=msa_depth,
                                    models_used=models,
                                    output_structure_path=result.output_structure_path,
                                    timeseries_path=timeseries_path,
                                    pass_index=pass_idx,
                                    is_warmup=False,
                                    msa_template_hash=msa_hash,
                                    repeat_index=pass_idx,  # Backward compatibility
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

    def _run_cold_start_suite(self, suite: BenchmarkSuite):
        """Run cold-start benchmark with container restarts.

        Measures:
        - Container startup time (stop to ready)
        - First request latency (cold)
        - Second request latency (warm)

        Args:
            suite: Benchmark suite configuration with suite_type="cold_start"
        """
        logger.info("Running COLD-START suite: %s", suite.name)

        if "nim" not in self.runners:
            logger.warning("Cold-start suite requires NIM, but NIM is not enabled")
            return

        targets = self._load_targets(suite)
        if not targets:
            logger.warning("No targets in cold-start suite %s", suite.name)
            return

        nim_runner = self.runners["nim"]
        variant = self._get_variants("nim")[0]  # Use first NIM variant
        models = self._parse_models_from_variant("nim", variant)

        # Import ColdStartRecord
        from bench.results.schema import ColdStartRecord

        for target in targets:
            sequence = target['sequence']
            target_id = target['id']

            for restart_idx in range(suite.measurement_passes):
                logger.info("Cold start %d/%d for %s",
                           restart_idx + 1, suite.measurement_passes, target_id)

                # Stop NIM container
                logger.info("Stopping NIM container...")
                nim_runner.stop()

                # Measure container startup time
                import time
                t0 = time.time()
                nim_runner.start()
                container_ready_time = time.time() - t0
                logger.info("Container ready in %.2f seconds", container_ready_time)

                # First request (cold)
                t1 = time.time()
                try:
                    result1 = nim_runner.predict(
                        target_id=f"{target_id}_cold",
                        sequence=sequence,
                        msa_depth=suite.msa_depth,
                        variant=variant,
                        models=models,
                    )
                    first_request_time = time.time() - t1
                    logger.info("First request (cold): %.2f seconds", first_request_time)
                except Exception as e:
                    logger.error("First request failed: %s", e)
                    continue

                # Second request (warm)
                t2 = time.time()
                try:
                    result2 = nim_runner.predict(
                        target_id=f"{target_id}_warm",
                        sequence=sequence,
                        msa_depth=suite.msa_depth,
                        variant=variant,
                        models=models,
                    )
                    second_request_time = time.time() - t2
                    logger.info("Second request (warm): %.2f seconds", second_request_time)
                except Exception as e:
                    logger.error("Second request failed: %s", e)
                    continue

                # Save cold start record
                record = ColdStartRecord(
                    run_id=self.config.run_id,
                    suite=suite.name,
                    target_id=target_id,
                    system="nim",
                    variant=variant,
                    container_start_time_s=container_ready_time,
                    first_request_time_s=first_request_time,
                    second_request_time_s=second_request_time,
                    restart_index=restart_idx,
                    timestamp=datetime.now()
                )

                self.writer.append_cold_start_record(record)
                logger.info("Cold start recorded: container=%.2fs, first=%.2fs, second=%.2fs",
                           container_ready_time, first_request_time, second_request_time)

        logger.info("Cold-start suite complete")

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

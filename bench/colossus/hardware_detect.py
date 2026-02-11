"""Hardware detection and auto-configuration for optimal benchmark settings.

This module detects GPU type, VRAM, storage characteristics and recommends
optimal benchmark configuration parameters.
"""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from bench.logging import logger

try:
    import pynvml

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    logger.warning("pynvml not available - GPU detection will be limited")


@dataclass
class HardwareProfile:
    """Detected hardware characteristics and recommendations."""

    # GPU info
    gpu_model: str  # "H100", "A100", "L40S", etc.
    gpu_vram_gb: int
    gpu_count: int

    # Storage info
    fast_storage_paths: List[Path]  # Ordered by speed (NVMe first)
    available_disk_gb: float

    # Recommended benchmark settings
    recommended_model_sets: List[List[int]]
    recommended_warmup: int
    recommended_measurement: int
    recommended_batch_mode: str  # "sequential" or "parallel"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "gpu_model": self.gpu_model,
            "gpu_vram_gb": self.gpu_vram_gb,
            "gpu_count": self.gpu_count,
            "fast_storage_paths": [str(p) for p in self.fast_storage_paths],
            "available_disk_gb": self.available_disk_gb,
            "recommended_model_sets": self.recommended_model_sets,
            "recommended_warmup": self.recommended_warmup,
            "recommended_measurement": self.recommended_measurement,
            "recommended_batch_mode": self.recommended_batch_mode,
        }


def detect_hardware() -> HardwareProfile:
    """Detect system hardware and return recommendations.

    Returns:
        HardwareProfile with detected hardware and recommended settings

    Raises:
        RuntimeError: If GPU detection fails
    """
    if not PYNVML_AVAILABLE:
        logger.warning("pynvml not available - using fallback detection")
        return _detect_hardware_fallback()

    try:
        pynvml.nvmlInit()
    except Exception as e:
        logger.error(f"Failed to initialize NVML: {e}")
        return _detect_hardware_fallback()

    try:
        # Get GPU info
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu_name = pynvml.nvmlDeviceGetName(handle)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_gb = int(mem_info.total / (1024**3))
        gpu_count = pynvml.nvmlDeviceGetCount()

        # Classify GPU and recommend settings
        if "H100" in gpu_name:
            gpu_type = "H100"
            warmup = 3
            measurement = 10
            batch_mode = "parallel"
        elif "A100" in gpu_name:
            gpu_type = "A100"
            warmup = 3
            measurement = 10
            batch_mode = "parallel"
        elif "L40S" in gpu_name:
            gpu_type = "L40S"
            warmup = 2
            measurement = 5
            batch_mode = "sequential"
        elif "L40" in gpu_name:
            gpu_type = "L40"
            warmup = 2
            measurement = 5
            batch_mode = "sequential"
        elif "V100" in gpu_name:
            gpu_type = "V100"
            warmup = 2
            measurement = 5
            batch_mode = "sequential"
        else:
            gpu_type = gpu_name
            warmup = 1
            measurement = 3
            batch_mode = "sequential"

        # Recommend model sets based on VRAM
        if vram_gb >= 80:
            # Full ensemble possible
            model_sets = [[3], [1, 2, 3, 4, 5]]
        elif vram_gb >= 40:
            # Partial ensemble
            model_sets = [[3], [1, 2, 3]]
        elif vram_gb >= 24:
            # Single model only
            model_sets = [[3]]
        else:
            # Minimal configuration
            model_sets = [[3]]
            logger.warning(
                f"Low VRAM ({vram_gb}GB) - may need to reduce sequence length"
            )

        # Detect fast storage
        fast_paths = detect_fast_storage()
        available_gb = get_available_space(fast_paths[0]) if fast_paths else 0.0

        return HardwareProfile(
            gpu_model=gpu_type,
            gpu_vram_gb=vram_gb,
            gpu_count=gpu_count,
            fast_storage_paths=fast_paths,
            available_disk_gb=available_gb,
            recommended_model_sets=model_sets,
            recommended_warmup=warmup,
            recommended_measurement=measurement,
            recommended_batch_mode=batch_mode,
        )

    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass


def _detect_hardware_fallback() -> HardwareProfile:
    """Fallback hardware detection without pynvml.

    Returns conservative recommendations.
    """
    logger.warning("Using fallback hardware detection")

    # Try to get GPU info from nvidia-smi
    gpu_model = "Unknown"
    vram_gb = 24  # Conservative estimate
    gpu_count = 1

    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            gpu_count = len(lines)

            # Parse first GPU
            first_gpu = lines[0]
            parts = first_gpu.split(",")
            if len(parts) >= 2:
                gpu_model = parts[0].strip()
                vram_str = parts[1].strip().split()[0]
                vram_gb = int(float(vram_str) / 1024)  # Convert MiB to GiB

    except Exception as e:
        logger.warning(f"Failed to run nvidia-smi: {e}")

    # Conservative recommendations
    fast_paths = detect_fast_storage()
    available_gb = get_available_space(fast_paths[0]) if fast_paths else 0.0

    return HardwareProfile(
        gpu_model=gpu_model,
        gpu_vram_gb=vram_gb,
        gpu_count=gpu_count,
        fast_storage_paths=fast_paths,
        available_disk_gb=available_gb,
        recommended_model_sets=[[3]],  # Conservative
        recommended_warmup=1,
        recommended_measurement=3,
        recommended_batch_mode="sequential",
    )


def detect_fast_storage() -> List[Path]:
    """Detect fast storage locations (NVMe, local SSD).

    Returns paths ordered by likely speed (NVMe first).

    Returns:
        List of paths to fast storage, ordered by priority
    """
    candidates = []

    # Check for Colossus-style mount
    colossus_primary = Path("/mnt/primary")
    if colossus_primary.exists() and colossus_primary.is_dir():
        candidates.append(colossus_primary)
        logger.info(f"Detected Colossus primary storage: {colossus_primary}")

    # Check for /tmp (usually tmpfs or local)
    tmp_path = Path("/tmp")
    if tmp_path.exists():
        candidates.append(tmp_path)

    # Check for local NVMe mounts
    for nvme_mount in ["/mnt/nvme", "/mnt/ssd", "/mnt/local"]:
        nvme_path = Path(nvme_mount)
        if nvme_path.exists() and nvme_path.is_dir():
            candidates.append(nvme_path)

    # Fallback to home directory
    home_path = Path.home()
    if home_path not in candidates:
        candidates.append(home_path)

    return candidates


def get_available_space(path: Path) -> float:
    """Get available disk space in GB.

    Args:
        path: Path to check

    Returns:
        Available space in GB
    """
    try:
        stat = os.statvfs(path)
        available_bytes = stat.f_bavail * stat.f_frsize
        return available_bytes / (1024**3)
    except Exception as e:
        logger.warning(f"Failed to get disk space for {path}: {e}")
        return 0.0


def get_total_space(path: Path) -> float:
    """Get total disk space in GB.

    Args:
        path: Path to check

    Returns:
        Total space in GB
    """
    try:
        stat = os.statvfs(path)
        total_bytes = stat.f_blocks * stat.f_frsize
        return total_bytes / (1024**3)
    except Exception as e:
        logger.warning(f"Failed to get total disk space for {path}: {e}")
        return 0.0

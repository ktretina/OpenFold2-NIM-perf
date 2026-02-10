"""Configuration models for benchmarking."""

from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field


class GPUConfig(BaseModel):
    """GPU monitoring configuration."""

    device_ids: list[int] = Field(default_factory=lambda: [0])
    sampling_interval_ms: int = 50


class NIMConfig(BaseModel):
    """NIM configuration."""

    enabled: bool = True
    container_image: str = "nvcr.io/nim/openfold/openfold2:latest"
    cache_dir: Path
    port: int = 8000
    base_url: Optional[str] = None  # If None, start local container
    backend: Literal["tensorrt", "torch"] = "tensorrt"
    model_sets: list[list[int]] = Field(default_factory=lambda: [[3], [1, 2, 3, 4, 5]])


class OpenFoldConfig(BaseModel):
    """OpenFold configuration."""

    enabled: bool = True
    repo_path: Path
    commit_hash: str = "main"
    model_presets: list[str] = Field(default_factory=lambda: ["model_3_ptm"])
    precision: Literal["fp32", "bf16"] = "bf16"
    use_deepspeed: bool = False


class BenchmarkSuite(BaseModel):
    """Benchmark suite configuration."""

    name: str
    targets_file: Optional[Path] = None  # If None, use synthetic
    sequences: Optional[list[dict]] = None  # Synthetic sequences
    msa_depth: int = 1
    msa_depths: Optional[list[int]] = None  # For MSA scaling studies
    repeats: int = 3
    warmup_runs: int = 1


class BenchmarkConfig(BaseModel):
    """Main benchmark configuration."""

    output_dir: Path
    run_id: Optional[str] = None
    gpu: GPUConfig
    nim: NIMConfig
    openfold: OpenFoldConfig
    suites: list[BenchmarkSuite]

    def __init__(self, **data):
        """Initialize config with environment variable expansion."""
        # Expand environment variables in paths
        if "nim" in data and "cache_dir" in data["nim"]:
            data["nim"]["cache_dir"] = self._expand_path(data["nim"]["cache_dir"])
        if "openfold" in data and "repo_path" in data["openfold"]:
            data["openfold"]["repo_path"] = self._expand_path(data["openfold"]["repo_path"])
        super().__init__(**data)

    @staticmethod
    def _expand_path(path_str: str) -> Path:
        """Expand environment variables and resolve path."""
        import os

        expanded = os.path.expandvars(str(path_str))
        return Path(expanded).expanduser()


def load_config(path: Path) -> BenchmarkConfig:
    """Load configuration from YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    # Generate run_id if not provided
    if data.get("run_id") is None:
        data["run_id"] = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return BenchmarkConfig(**data)

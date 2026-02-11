"""Base runner interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from bench.results.schema import PrecomputedInputs


@dataclass
class PredictionResult:
    """Result from a single prediction."""

    output_structure_path: Path
    wall_time_s: float
    time_to_first_gpu_activity_s: float
    time_to_first_response_byte_s: Optional[float]
    gpu_sm_util_avg_pct: float
    gpu_sm_util_peak_pct: float
    gpu_mem_peak_mb: float
    gpu_energy_wh: float
    gpu_power_avg_w: float
    cpu_rss_peak_mb: float
    cpu_util_avg_pct: float
    mean_plddt: float
    timeseries_samples: list[dict]


class RunnerBase(ABC):
    """Abstract base class for inference runners."""

    @abstractmethod
    def setup(self) -> None:
        """One-time setup (install, download models, etc.)."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the service/prepare for inference."""
        pass

    @abstractmethod
    def predict(
        self,
        target_id: str,
        sequence: str,
        msa_depth: int,
        variant: str,
        models: list[int],
        precomputed_inputs: Optional["PrecomputedInputs"] = None,
    ) -> PredictionResult:
        """
        Run inference and return structured result.

        Args:
            target_id: Target identifier
            sequence: Amino acid sequence
            msa_depth: MSA depth for synthetic MSA generation
            variant: Variant identifier
            models: Model indices to use
            precomputed_inputs: Optional precomputed MSA/template inputs

        Returns:
            PredictionResult with metrics and paths
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Cleanup and stop services."""
        pass

    @abstractmethod
    def get_metadata(self) -> dict:
        """
        Get version/environment metadata.

        Returns:
            Dictionary with metadata
        """
        pass

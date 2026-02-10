"""GPU monitoring via NVML."""

import threading
import time
from typing import Optional

import py3nvml.py3nvml as pynvml

from bench.logging import logger


class NVMLSampler:
    """High-frequency GPU monitoring using NVML."""

    def __init__(self, device_ids: list[int], interval_ms: int = 50):
        """
        Initialize NVML sampler.

        Args:
            device_ids: List of GPU device IDs to monitor
            interval_ms: Sampling interval in milliseconds
        """
        self.devices = device_ids
        self.interval = interval_ms / 1000.0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._samples = []
        self._baseline_mem = {}

    def start(self):
        """Start sampling in background thread."""
        try:
            pynvml.nvmlInit()
        except Exception as e:
            logger.error(f"Failed to initialize NVML: {e}")
            raise

        # Get baseline memory usage
        for device_id in self.devices:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                self._baseline_mem[device_id] = mem.used / 1024**2  # MB
            except Exception as e:
                logger.warning(f"Failed to get baseline memory for GPU {device_id}: {e}")
                self._baseline_mem[device_id] = 0

        self._running = True
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()
        logger.debug(f"Started NVML sampling on GPUs {self.devices} at {self.interval*1000:.0f}ms")

    def stop(self) -> list[dict]:
        """
        Stop sampling and return all samples.

        Returns:
            List of sample dictionaries
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

        try:
            pynvml.nvmlShutdown()
        except Exception as e:
            logger.warning(f"Error shutting down NVML: {e}")

        logger.debug(f"Stopped NVML sampling, collected {len(self._samples)} samples")
        return self._samples

    def _sample_loop(self):
        """Background sampling loop."""
        while self._running:
            t0 = time.time()
            sample = {"timestamp": t0, "gpus": {}}

            for device_id in self.devices:
                try:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW -> W

                    sample["gpus"][device_id] = {
                        "sm_util_pct": util.gpu,
                        "mem_util_pct": util.memory,
                        "mem_used_mb": mem.used / 1024**2,
                        "power_w": power,
                    }
                except Exception as e:
                    logger.warning(f"Error sampling GPU {device_id}: {e}")
                    sample["gpus"][device_id] = {
                        "sm_util_pct": 0,
                        "mem_util_pct": 0,
                        "mem_used_mb": 0,
                        "power_w": 0,
                    }

            self._samples.append(sample)

            # Sleep for remainder of interval
            elapsed = time.time() - t0
            sleep_time = max(0, self.interval - elapsed)
            time.sleep(sleep_time)

    def compute_time_to_first_gpu_activity(self, start_time: float) -> float:
        """
        Compute time from start until GPU shows activity.

        Args:
            start_time: Start timestamp

        Returns:
            Time to first GPU activity in seconds
        """
        threshold_util_pct = 5
        threshold_mem_mb = 256

        for sample in self._samples:
            if sample["timestamp"] < start_time:
                continue

            for device_id, gpu_data in sample["gpus"].items():
                baseline_mem = self._baseline_mem.get(device_id, 0)
                mem_increase = gpu_data["mem_used_mb"] - baseline_mem

                if gpu_data["sm_util_pct"] > threshold_util_pct or mem_increase > threshold_mem_mb:
                    return sample["timestamp"] - start_time

        # No activity detected
        return 0.0

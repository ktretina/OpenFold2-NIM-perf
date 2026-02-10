"""System (CPU/memory) monitoring via psutil."""

import threading
import time
from typing import Optional

import psutil

from bench.logging import logger


class SystemSampler:
    """Monitor CPU and memory for tracked processes."""

    def __init__(self, tracked_pids: Optional[list[int]] = None, interval_ms: int = 100):
        """
        Initialize system sampler.

        Args:
            tracked_pids: List of process IDs to monitor
            interval_ms: Sampling interval in milliseconds
        """
        self.tracked_pids = set(tracked_pids or [])
        self.interval = interval_ms / 1000.0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._samples = []

    def add_pid(self, pid: int):
        """Add a PID to track."""
        self.tracked_pids.add(pid)

    def start(self):
        """Start sampling in background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()
        logger.debug(f"Started system sampling for PIDs {self.tracked_pids}")

    def stop(self) -> list[dict]:
        """
        Stop sampling and return all samples.

        Returns:
            List of sample dictionaries
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

        logger.debug(f"Stopped system sampling, collected {len(self._samples)} samples")
        return self._samples

    def _sample_loop(self):
        """Background sampling loop."""
        while self._running:
            t0 = time.time()
            sample = {"timestamp": t0, "processes": {}}

            for pid in list(self.tracked_pids):
                try:
                    proc = psutil.Process(pid)
                    cpu_pct = proc.cpu_percent()
                    mem_info = proc.memory_info()

                    sample["processes"][pid] = {
                        "cpu_percent": cpu_pct,
                        "rss_mb": mem_info.rss / 1024**2,
                        "vms_mb": mem_info.vms / 1024**2,
                    }
                except psutil.NoSuchProcess:
                    # Process terminated
                    logger.debug(f"Process {pid} terminated")
                    self.tracked_pids.discard(pid)
                except Exception as e:
                    logger.warning(f"Error sampling process {pid}: {e}")

            self._samples.append(sample)

            # Sleep for remainder of interval
            elapsed = time.time() - t0
            sleep_time = max(0, self.interval - elapsed)
            time.sleep(sleep_time)

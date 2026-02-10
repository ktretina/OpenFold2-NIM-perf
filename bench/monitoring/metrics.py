"""Derived metrics computation from timeseries data."""

from typing import Optional

import numpy as np


def compute_avg_sm_util(samples: list[dict], device_ids: list[int]) -> float:
    """
    Compute average SM utilization across all GPUs.

    Args:
        samples: List of sample dictionaries from NVMLSampler
        device_ids: GPU device IDs

    Returns:
        Average SM utilization percentage
    """
    if not samples:
        return 0.0

    utils = []
    for sample in samples:
        for device_id in device_ids:
            if device_id in sample.get("gpus", {}):
                utils.append(sample["gpus"][device_id]["sm_util_pct"])

    return float(np.mean(utils)) if utils else 0.0


def compute_peak_sm_util(samples: list[dict], device_ids: list[int]) -> float:
    """Compute peak SM utilization."""
    if not samples:
        return 0.0

    utils = []
    for sample in samples:
        for device_id in device_ids:
            if device_id in sample.get("gpus", {}):
                utils.append(sample["gpus"][device_id]["sm_util_pct"])

    return float(np.max(utils)) if utils else 0.0


def compute_peak_mem(samples: list[dict], device_ids: list[int]) -> float:
    """
    Compute peak memory usage across all GPUs.

    Returns:
        Peak memory in MB
    """
    if not samples:
        return 0.0

    mems = []
    for sample in samples:
        for device_id in device_ids:
            if device_id in sample.get("gpus", {}):
                mems.append(sample["gpus"][device_id]["mem_used_mb"])

    return float(np.max(mems)) if mems else 0.0


def compute_energy_wh(samples: list[dict], device_ids: list[int]) -> float:
    """
    Compute total energy consumption via trapezoidal integration.

    Args:
        samples: List of sample dictionaries
        device_ids: GPU device IDs

    Returns:
        Energy in watt-hours
    """
    if len(samples) < 2:
        return 0.0

    total_energy_ws = 0.0  # Watt-seconds

    for i in range(len(samples) - 1):
        dt = samples[i + 1]["timestamp"] - samples[i]["timestamp"]

        for device_id in device_ids:
            if device_id in samples[i].get("gpus", {}) and device_id in samples[i + 1].get(
                "gpus", {}
            ):
                power1 = samples[i]["gpus"][device_id]["power_w"]
                power2 = samples[i + 1]["gpus"][device_id]["power_w"]
                avg_power = (power1 + power2) / 2
                total_energy_ws += avg_power * dt

    # Convert watt-seconds to watt-hours
    return total_energy_ws / 3600.0


def compute_avg_power(samples: list[dict], device_ids: list[int]) -> float:
    """
    Compute average power consumption across all GPUs.

    Args:
        samples: List of sample dictionaries
        device_ids: GPU device IDs

    Returns:
        Average power in watts
    """
    if not samples:
        return 0.0

    powers = []
    for sample in samples:
        for device_id in device_ids:
            if device_id in sample.get("gpus", {}):
                powers.append(sample["gpus"][device_id]["power_w"])

    return float(np.mean(powers)) if powers else 0.0


def compute_avg_cpu_util(samples: list[dict], pids: Optional[list[int]] = None) -> float:
    """
    Compute average CPU utilization.

    Args:
        samples: List of sample dictionaries from SystemSampler
        pids: Optional specific PIDs to compute for

    Returns:
        Average CPU utilization percentage
    """
    if not samples:
        return 0.0

    utils = []
    for sample in samples:
        processes = sample.get("processes", {})
        if pids:
            for pid in pids:
                if pid in processes:
                    utils.append(processes[pid]["cpu_percent"])
        else:
            # All processes
            for proc_data in processes.values():
                utils.append(proc_data["cpu_percent"])

    return float(np.mean(utils)) if utils else 0.0


def compute_peak_rss(samples: list[dict], pids: Optional[list[int]] = None) -> float:
    """
    Compute peak RSS memory.

    Returns:
        Peak RSS in MB
    """
    if not samples:
        return 0.0

    rss_values = []
    for sample in samples:
        processes = sample.get("processes", {})
        if pids:
            for pid in pids:
                if pid in processes:
                    rss_values.append(processes[pid]["rss_mb"])
        else:
            # Sum across all processes for total
            total_rss = sum(p["rss_mb"] for p in processes.values())
            if total_rss > 0:
                rss_values.append(total_rss)

    return float(np.max(rss_values)) if rss_values else 0.0

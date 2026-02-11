"""Colossus-specific production features for large-scale GPU campaigns.

This module provides production-ready infrastructure for running benchmarks
on Colossus clusters and other large-scale GPU environments:

- Dual storage (fast NVMe + persistent network storage)
- Task-level resumability with checkpointing
- Hardware auto-detection and config generation
- Campaign mode for multi-GPU studies
- Git sync for automated result tracking
- Enhanced preflight checks with actionable errors
"""

from bench.colossus.checkpoint import CheckpointManager, CheckpointState, TaskID
from bench.colossus.hardware_detect import detect_hardware, HardwareProfile
from bench.colossus.auto_config import generate_config, print_hardware_summary
from bench.colossus.campaign import Campaign
from bench.colossus.git_sync import GitSync
from bench.colossus.preflight import run_preflight_checks, PreflightCheck

__all__ = [
    "CheckpointManager",
    "CheckpointState",
    "TaskID",
    "detect_hardware",
    "HardwareProfile",
    "generate_config",
    "print_hardware_summary",
    "Campaign",
    "GitSync",
    "run_preflight_checks",
    "PreflightCheck",
]

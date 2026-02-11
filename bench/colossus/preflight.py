"""Enhanced preflight checks with actionable fix hints.

This module provides comprehensive environment validation with clear
error messages and remediation instructions.
"""

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from bench.logging import logger


@dataclass
class PreflightCheck:
    """Result of a single preflight check."""

    name: str
    passed: bool
    message: str
    fix_hint: Optional[str] = None


def run_preflight_checks() -> List[PreflightCheck]:
    """Run all preflight checks.

    Returns:
        List of PreflightCheck results
    """
    checks = []

    # Check NVIDIA drivers
    checks.append(_check_nvidia_smi())

    # Check Docker
    checks.append(_check_docker())

    # Check Docker daemon
    checks.append(_check_docker_daemon())

    # Check NGC API key
    checks.append(_check_ngc_api_key())

    # Check GPU visibility
    checks.append(_check_gpu_visibility())

    # Check disk space
    checks.append(_check_disk_space())

    # Check Python version
    checks.append(_check_python_version())

    # Check required Python packages
    checks.append(_check_python_packages())

    return checks


def _check_nvidia_smi() -> PreflightCheck:
    """Check NVIDIA drivers and nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            return PreflightCheck(
                name="NVIDIA drivers",
                passed=True,
                message="nvidia-smi accessible",
            )
        else:
            return PreflightCheck(
                name="NVIDIA drivers",
                passed=False,
                message="nvidia-smi failed",
                fix_hint="Install NVIDIA drivers: https://www.nvidia.com/drivers",
            )

    except FileNotFoundError:
        return PreflightCheck(
            name="NVIDIA drivers",
            passed=False,
            message="nvidia-smi not found",
            fix_hint="Install NVIDIA drivers: https://www.nvidia.com/drivers",
        )
    except Exception as e:
        return PreflightCheck(
            name="NVIDIA drivers",
            passed=False,
            message=f"Error: {e}",
            fix_hint="Check NVIDIA driver installation",
        )


def _check_docker() -> PreflightCheck:
    """Check Docker installation."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            version = result.stdout.strip()
            return PreflightCheck(
                name="Docker",
                passed=True,
                message=version,
            )
        else:
            return PreflightCheck(
                name="Docker",
                passed=False,
                message="Docker not found",
                fix_hint="Install Docker: https://docs.docker.com/get-docker/",
            )

    except FileNotFoundError:
        return PreflightCheck(
            name="Docker",
            passed=False,
            message="Docker not found",
            fix_hint="Install Docker: https://docs.docker.com/get-docker/",
        )
    except Exception as e:
        return PreflightCheck(
            name="Docker",
            passed=False,
            message=f"Error: {e}",
            fix_hint="Check Docker installation",
        )


def _check_docker_daemon() -> PreflightCheck:
    """Check Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            return PreflightCheck(
                name="Docker daemon",
                passed=True,
                message="Running and accessible",
            )
        else:
            return PreflightCheck(
                name="Docker daemon",
                passed=False,
                message="Not accessible",
                fix_hint="Start Docker daemon: sudo systemctl start docker",
            )

    except Exception as e:
        return PreflightCheck(
            name="Docker daemon",
            passed=False,
            message=f"Error: {e}",
            fix_hint="Start Docker daemon and check permissions",
        )


def _check_ngc_api_key() -> PreflightCheck:
    """Check NGC API key is set and exported."""
    ngc_key = os.environ.get("NGC_API_KEY")

    if not ngc_key:
        return PreflightCheck(
            name="NGC_API_KEY",
            passed=False,
            message="Not set",
            fix_hint="Set NGC_API_KEY: export NGC_API_KEY='your-api-key'",
        )

    # Check if exported
    try:
        result = subprocess.run(
            ["env"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if "NGC_API_KEY=" in result.stdout:
            return PreflightCheck(
                name="NGC_API_KEY",
                passed=True,
                message="Set and exported",
            )
        else:
            return PreflightCheck(
                name="NGC_API_KEY",
                passed=False,
                message="Set but not exported",
                fix_hint="Export NGC_API_KEY: export NGC_API_KEY='your-api-key'",
            )

    except Exception:
        return PreflightCheck(
            name="NGC_API_KEY",
            passed=True,
            message="Set (export status unknown)",
        )


def _check_gpu_visibility() -> PreflightCheck:
    """Check GPU visibility via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0 and result.stdout.strip():
            gpu_info = result.stdout.strip().split("\n")[0]
            return PreflightCheck(
                name="GPU visibility",
                passed=True,
                message=gpu_info,
            )
        else:
            return PreflightCheck(
                name="GPU visibility",
                passed=False,
                message="No GPUs detected",
                fix_hint="Check CUDA_VISIBLE_DEVICES and driver installation",
            )

    except Exception as e:
        return PreflightCheck(
            name="GPU visibility",
            passed=False,
            message=f"Error: {e}",
            fix_hint="Check nvidia-smi and CUDA installation",
        )


def _check_disk_space(min_gb: float = 100) -> PreflightCheck:
    """Check available disk space.

    Args:
        min_gb: Minimum required space in GB
    """
    try:
        home = Path.home()
        stat = os.statvfs(home)
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)

        if free_gb >= min_gb:
            return PreflightCheck(
                name="Disk space",
                passed=True,
                message=f"{free_gb:.1f} GB available",
            )
        else:
            return PreflightCheck(
                name="Disk space",
                passed=False,
                message=f"Only {free_gb:.1f} GB available (need {min_gb}+ GB)",
                fix_hint=f"Free up disk space or use external storage",
            )

    except Exception as e:
        return PreflightCheck(
            name="Disk space",
            passed=False,
            message=f"Error: {e}",
            fix_hint="Check disk space manually: df -h",
        )


def _check_python_version(min_version: tuple = (3, 10)) -> PreflightCheck:
    """Check Python version.

    Args:
        min_version: Minimum required (major, minor) version
    """
    py_version = sys.version_info

    version_str = f"{py_version.major}.{py_version.minor}.{py_version.micro}"

    if (py_version.major, py_version.minor) >= min_version:
        return PreflightCheck(
            name="Python version",
            passed=True,
            message=version_str,
        )
    else:
        min_str = f"{min_version[0]}.{min_version[1]}"
        return PreflightCheck(
            name="Python version",
            passed=False,
            message=f"{version_str} (need {min_str}+)",
            fix_hint=f"Upgrade Python to {min_str} or higher",
        )


def _check_python_packages() -> PreflightCheck:
    """Check required Python packages are installed."""
    required_packages = [
        ("pydantic", "Configuration validation"),
        ("typer", "CLI framework"),
        ("pandas", "Data analysis"),
        ("numpy", "Numerical computing"),
        ("requests", "HTTP client"),
    ]

    missing = []
    for package, _ in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if not missing:
        return PreflightCheck(
            name="Python packages",
            passed=True,
            message="All required packages installed",
        )
    else:
        return PreflightCheck(
            name="Python packages",
            passed=False,
            message=f"Missing: {', '.join(missing)}",
            fix_hint=f"Install missing packages: pip install {' '.join(missing)}",
        )


def print_preflight_results(checks: List[PreflightCheck]) -> bool:
    """Print formatted preflight results.

    Args:
        checks: List of PreflightCheck results

    Returns:
        True if all checks passed, False otherwise
    """
    print("\n" + "=" * 70)
    print("PREFLIGHT CHECKS")
    print("=" * 70)

    all_passed = True
    for check in checks:
        status = "✓ PASS" if check.passed else "✗ FAIL"
        print(f"\n{check.name:20s} [{status}]")
        print(f"  {check.message}")

        if not check.passed:
            all_passed = False
            if check.fix_hint:
                print(f"  💡 Fix: {check.fix_hint}")

    print("\n" + "=" * 70)

    if all_passed:
        print("✓ All checks passed!")
    else:
        print("✗ Some checks failed. Fix issues before running benchmark.")

    print("=" * 70 + "\n")

    return all_passed

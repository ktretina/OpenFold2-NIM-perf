"""Automatic configuration generation based on detected hardware.

This module generates optimized benchmark configurations by detecting system
hardware and applying best practices for GPU type, VRAM capacity, and storage.
"""

import yaml
from pathlib import Path
from typing import Optional

from bench.config import load_config
from bench.colossus.hardware_detect import detect_hardware, HardwareProfile
from bench.logging import logger


def generate_config(
    base_config_path: Path,
    output_dir: Path,
    hw_profile: Optional[HardwareProfile] = None,
) -> Path:
    """Generate optimized config based on detected hardware.

    Args:
        base_config_path: Path to base configuration YAML
        output_dir: Directory to write generated config
        hw_profile: Pre-detected hardware profile (if None, will detect)

    Returns:
        Path to generated configuration file
    """
    # Load base config
    logger.info(f"Loading base config from {base_config_path}")
    base_config = load_config(base_config_path)
    config_dict = base_config.model_dump()

    # Detect hardware if not provided
    if hw_profile is None:
        logger.info("Detecting hardware...")
        hw_profile = detect_hardware()

    logger.info(f"Detected GPU: {hw_profile.gpu_model} ({hw_profile.gpu_vram_gb}GB)")
    logger.info(f"GPU count: {hw_profile.gpu_count}")
    logger.info(f"Fast storage: {hw_profile.fast_storage_paths[0]}")
    logger.info(f"Available space: {hw_profile.available_disk_gb:.1f}GB")

    # Update NIM config with recommendations
    if "nim" in config_dict and config_dict["nim"]["enabled"]:
        config_dict["nim"]["model_sets"] = hw_profile.recommended_model_sets
        logger.info(f"Recommended model sets: {hw_profile.recommended_model_sets}")

        # Set cache to fast storage
        if hw_profile.fast_storage_paths:
            fast_path = hw_profile.fast_storage_paths[0]
            config_dict["nim"]["cache_dir"] = str(fast_path / "nim_cache")

    # Update suite configs with recommendations
    for suite in config_dict.get("suites", []):
        suite["warmup_passes"] = hw_profile.recommended_warmup
        suite["measurement_passes"] = hw_profile.recommended_measurement

        logger.info(
            f"Suite '{suite['name']}': warmup={hw_profile.recommended_warmup}, "
            f"measurement={hw_profile.recommended_measurement}"
        )

    # Update storage paths if available
    if hw_profile.fast_storage_paths:
        fast_path = hw_profile.fast_storage_paths[0]
        persist_path = Path.home() / "openfold_results"

        # Note: PathConfig would be added to schema separately
        # For now, update output_dir
        config_dict["output_dir"] = str(persist_path)

        logger.info(f"Results directory: {persist_path}")

    # Check disk space warning
    if hw_profile.available_disk_gb < 100:
        logger.warning(
            f"Low disk space on fast storage: {hw_profile.available_disk_gb:.1f}GB "
            f"(recommended: 100+ GB)"
        )

    # Write generated config
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_filename = f"auto_{hw_profile.gpu_model.lower().replace(' ', '_')}.yaml"
    generated_path = output_dir / generated_filename

    with open(generated_path, "w") as f:
        # Write header comment
        f.write(f"# Auto-generated configuration for {hw_profile.gpu_model}\n")
        f.write(f"# Generated based on detected hardware:\n")
        f.write(f"#   GPU: {hw_profile.gpu_model} ({hw_profile.gpu_vram_gb}GB)\n")
        f.write(f"#   GPU Count: {hw_profile.gpu_count}\n")
        f.write(f"#   Fast Storage: {hw_profile.fast_storage_paths[0]}\n")
        f.write(f"#   Available Space: {hw_profile.available_disk_gb:.1f}GB\n")
        f.write(f"#\n")
        f.write(f"# Recommendations:\n")
        f.write(f"#   Model Sets: {hw_profile.recommended_model_sets}\n")
        f.write(f"#   Warmup Passes: {hw_profile.recommended_warmup}\n")
        f.write(f"#   Measurement Passes: {hw_profile.recommended_measurement}\n")
        f.write(f"#\n")
        f.write(f"# Base config: {base_config_path.name}\n\n")

        # Write config
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Generated config: {generated_path}")
    return generated_path


def print_hardware_summary(hw_profile: HardwareProfile):
    """Print formatted hardware detection summary.

    Args:
        hw_profile: Hardware profile to display
    """
    print("\n" + "=" * 70)
    print("HARDWARE DETECTION SUMMARY")
    print("=" * 70)
    print(f"GPU Model:          {hw_profile.gpu_model}")
    print(f"GPU VRAM:           {hw_profile.gpu_vram_gb} GB")
    print(f"GPU Count:          {hw_profile.gpu_count}")
    print(f"Fast Storage:       {hw_profile.fast_storage_paths[0]}")
    print(f"Available Space:    {hw_profile.available_disk_gb:.1f} GB")
    print()
    print("RECOMMENDATIONS:")
    print(f"  Model Sets:       {hw_profile.recommended_model_sets}")
    print(f"  Warmup Passes:    {hw_profile.recommended_warmup}")
    print(f"  Measurement:      {hw_profile.recommended_measurement}")
    print(f"  Batch Mode:       {hw_profile.recommended_batch_mode}")
    print("=" * 70 + "\n")

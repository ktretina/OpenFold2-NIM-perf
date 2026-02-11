#!/usr/bin/env python3
"""Precompute MSAs for inference-only benchmarking.

This script generates synthetic MSAs for a set of targets and saves them in
the format expected by both NIM and OpenFold. This enables apples-to-apples
comparison by ensuring identical inputs for both systems.

Usage:
    python scripts/precompute_msas.py \\
      --targets bench/dataset/casp15_targets.yaml \\
      --output data/precomputed/casp15_msa128 \\
      --msa-depth 128

Features:
- Generates identical MSAs for NIM (A3M) and OpenFold (directory structure)
- Computes SHA256 hashes for integrity verification
- Saves manifests for each target
- Supports batch processing
- Provides progress tracking
"""

import argparse
import sys
from pathlib import Path

import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bench.dataset.precomputed import precompute_inputs, precompute_batch
from bench.logging import logger


def load_targets(targets_file: Path) -> list[dict]:
    """Load targets from YAML file.

    Args:
        targets_file: Path to targets YAML file

    Returns:
        List of target dictionaries with 'id' and 'sequence' keys

    Raises:
        FileNotFoundError: If targets file doesn't exist
        ValueError: If file format is invalid
    """
    if not targets_file.exists():
        raise FileNotFoundError(f"Targets file not found: {targets_file}")

    with open(targets_file) as f:
        data = yaml.safe_load(f)

    # Handle different YAML formats
    if isinstance(data, list):
        # Direct list of targets
        targets = data
    elif isinstance(data, dict) and "targets" in data:
        # Nested under 'targets' key
        targets = data["targets"]
    else:
        raise ValueError(f"Invalid targets file format: {targets_file}")

    # Validate required fields
    for i, target in enumerate(targets):
        if "id" not in target:
            raise ValueError(f"Target {i} missing 'id' field")
        if "sequence" not in target:
            raise ValueError(f"Target {target['id']} missing 'sequence' field")

    return targets


def main():
    parser = argparse.ArgumentParser(
        description="Precompute MSAs for inference-only benchmarking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Precompute MSAs for CASP15 targets at depth 128
  python scripts/precompute_msas.py \\
    --targets bench/dataset/casp15_targets.yaml \\
    --output data/precomputed/casp15_msa128 \\
    --msa-depth 128

  # Precompute multiple depths
  python scripts/precompute_msas.py \\
    --targets bench/dataset/targets.yaml \\
    --output data/precomputed/multi_depth \\
    --msa-depths 32 64 128 256

  # Overwrite existing precomputed data
  python scripts/precompute_msas.py \\
    --targets bench/dataset/targets.yaml \\
    --output data/precomputed/test \\
    --msa-depth 16 \\
    --overwrite
        """,
    )

    parser.add_argument(
        "--targets",
        type=Path,
        required=True,
        help="Path to targets YAML file",
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory for precomputed MSAs",
    )

    # MSA depth options (mutually exclusive)
    depth_group = parser.add_mutually_exclusive_group(required=True)
    depth_group.add_argument(
        "--msa-depth",
        type=int,
        help="MSA depth (number of sequences including query)",
    )
    depth_group.add_argument(
        "--msa-depths",
        type=int,
        nargs="+",
        help="Multiple MSA depths to generate",
    )

    parser.add_argument(
        "--mutation-rate",
        type=float,
        default=0.3,
        help="Mutation rate for synthetic MSAs (0.0-1.0, default: 0.3)",
    )

    parser.add_argument(
        "--source",
        type=str,
        default="synthetic",
        choices=["synthetic", "hhsuite", "mmseqs2"],
        help="MSA source type (default: synthetic)",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing precomputed data",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Set log level
    if args.verbose:
        import logging
        logger.setLevel(logging.DEBUG)

    # Load targets
    logger.info("Loading targets from %s", args.targets)
    try:
        targets = load_targets(args.targets)
        logger.info("Loaded %d targets", len(targets))
    except Exception as e:
        logger.error("Failed to load targets: %s", e)
        return 1

    # Determine MSA depths
    if args.msa_depth:
        msa_depths = [args.msa_depth]
    else:
        msa_depths = args.msa_depths

    logger.info("Precomputing MSAs at depths: %s", msa_depths)
    logger.info("Output directory: %s", args.output)
    logger.info("Mutation rate: %.2f", args.mutation_rate)
    logger.info("Overwrite existing: %s", args.overwrite)

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Precompute MSAs
    try:
        count = precompute_batch(
            targets=targets,
            output_dir=args.output,
            msa_depths=msa_depths,
            source=args.source,
            mutation_rate=args.mutation_rate,
            overwrite=args.overwrite,
        )

        logger.info("✓ Successfully precomputed %d MSAs", count)
        logger.info("Output saved to: %s", args.output)

        # Print usage instructions
        print("\n" + "="*70)
        print("Precomputation complete!")
        print("="*70)
        print(f"\nPrecomputed MSAs saved to: {args.output}")
        print(f"Total MSAs generated: {count}")
        print("\nTo use in benchmark, add to your config:")
        print("  suites:")
        print("    - name: inference_only")
        print("      inference_only_mode: true")
        print(f"      precomputed_msa_dir: \"{args.output}\"")
        print(f"      msa_depth: {msa_depths[0]}")
        print("\n" + "="*70)

        return 0

    except Exception as e:
        logger.error("Precomputation failed: %s", e)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

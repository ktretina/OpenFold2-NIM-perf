#!/usr/bin/env python
"""Quick test to verify configuration and dataset files load correctly."""

import sys
from pathlib import Path

import yaml


def test_yaml_file(filepath: Path) -> bool:
    """Test if a YAML file loads correctly."""
    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)

        if not data:
            print(f"✗ {filepath}: Empty or invalid YAML")
            return False

        print(f"✓ {filepath}: Valid YAML")
        return True
    except Exception as e:
        print(f"✗ {filepath}: {e}")
        return False


def test_targets_yaml(filepath: Path) -> bool:
    """Test if targets YAML has correct structure."""
    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)

        if "targets" not in data:
            print(f"✗ {filepath}: Missing 'targets' key")
            return False

        targets = data["targets"]
        if not isinstance(targets, list):
            print(f"✗ {filepath}: 'targets' is not a list")
            return False

        required_fields = ["pdb_id", "chain"]
        for i, target in enumerate(targets):
            missing = [f for f in required_fields if f not in target]
            if missing:
                print(f"✗ {filepath}: Target {i} missing fields: {missing}")
                return False

        print(f"✓ {filepath}: Valid targets file with {len(targets)} targets")
        return True
    except Exception as e:
        print(f"✗ {filepath}: {e}")
        return False


def main():
    """Run all tests."""
    print("Testing configuration and dataset files...")
    print()

    all_passed = True

    # Test dataset files
    print("Dataset files:")
    for yaml_file in ["bench/dataset/targets.yaml", "bench/dataset/casp15_targets.yaml"]:
        path = Path(yaml_file)
        if path.exists():
            if not test_targets_yaml(path):
                all_passed = False
        else:
            print(f"⚠ {yaml_file}: File not found (may be optional)")

    print()

    # Test config files
    print("Configuration files:")
    for yaml_file in ["configs/default.yaml", "configs/casp15.yaml", "configs/full_matrix.yaml"]:
        path = Path(yaml_file)
        if path.exists():
            if not test_yaml_file(path):
                all_passed = False
        else:
            print(f"⚠ {yaml_file}: File not found (may be optional)")

    print()

    if all_passed:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Test script for Colossus features.

This script validates that all Colossus modules can be imported
and basic functionality works.
"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")

    try:
        from bench.colossus import (
            CheckpointManager,
            CheckpointState,
            TaskID,
            detect_hardware,
            HardwareProfile,
            generate_config,
            print_hardware_summary,
            Campaign,
            GitSync,
            run_preflight_checks,
            PreflightCheck,
        )
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_checkpoint():
    """Test checkpoint functionality."""
    print("\nTesting checkpoint module...")

    from bench.colossus.checkpoint import CheckpointManager, TaskID
    import tempfile

    try:
        # Create temp checkpoint file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            checkpoint_path = Path(f.name)

        # Create checkpoint manager
        manager = CheckpointManager(checkpoint_path, "test_run")
        state = manager.load()

        # Create a test task
        task = TaskID(
            suite="test_suite",
            target_id="test_target",
            system="nim",
            variant="trt_models-3",
            msa_depth=128,
            pass_index=0,
        )

        # Test operations
        assert not state.is_completed(task), "Task should not be completed initially"

        state.mark_completed(task)
        assert state.is_completed(task), "Task should be completed after marking"

        # Save and reload
        manager.save()
        manager2 = CheckpointManager(checkpoint_path, "test_run")
        state2 = manager2.load()

        assert state2.is_completed(task), "Task should still be completed after reload"

        # Cleanup
        checkpoint_path.unlink()

        print("✓ Checkpoint tests passed")
        return True

    except Exception as e:
        print(f"✗ Checkpoint test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hardware_detect():
    """Test hardware detection."""
    print("\nTesting hardware detection...")

    try:
        from bench.colossus.hardware_detect import detect_hardware

        hw_profile = detect_hardware()

        print(f"  GPU: {hw_profile.gpu_model} ({hw_profile.gpu_vram_gb}GB)")
        print(f"  Fast storage: {hw_profile.fast_storage_paths[0]}")
        print(f"  Recommended model sets: {hw_profile.recommended_model_sets}")

        assert hw_profile.gpu_model is not None
        assert hw_profile.gpu_vram_gb > 0
        assert len(hw_profile.fast_storage_paths) > 0

        print("✓ Hardware detection tests passed")
        return True

    except Exception as e:
        print(f"✗ Hardware detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_preflight():
    """Test preflight checks."""
    print("\nTesting preflight checks...")

    try:
        from bench.colossus.preflight import run_preflight_checks

        checks = run_preflight_checks()

        print(f"  Ran {len(checks)} checks")
        passed = sum(1 for c in checks if c.passed)
        print(f"  Passed: {passed}/{len(checks)}")

        assert len(checks) > 0, "Should have at least one check"

        print("✓ Preflight tests passed")
        return True

    except Exception as e:
        print(f"✗ Preflight test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_campaign():
    """Test campaign functionality."""
    print("\nTesting campaign module...")

    try:
        from bench.colossus.campaign import Campaign
        import tempfile
        import shutil

        # Create temp campaign directory
        campaign_dir = Path(tempfile.mkdtemp())

        try:
            # Create campaign
            campaign = Campaign(campaign_dir, "test_campaign")

            # Verify manifest exists
            assert campaign.manifest_path.exists()
            assert campaign.manifest["campaign_name"] == "test_campaign"

            print(f"  Campaign created at {campaign_dir}")
            print("✓ Campaign tests passed")
            return True

        finally:
            # Cleanup
            shutil.rmtree(campaign_dir)

    except Exception as e:
        print(f"✗ Campaign test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("Colossus Features Test Suite")
    print("=" * 70)

    all_passed = True

    # Run tests
    all_passed &= test_imports()
    all_passed &= test_checkpoint()
    all_passed &= test_hardware_detect()
    all_passed &= test_preflight()
    all_passed &= test_campaign()

    print("\n" + "=" * 70)
    if all_passed:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

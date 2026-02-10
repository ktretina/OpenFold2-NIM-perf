"""Test RMSD calculation."""

import numpy as np
import pytest

from bench.scoring.rmsd import kabsch_rmsd


def test_rmsd_identical_structures():
    """Test RMSD of identical structures is zero."""
    coords = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)

    rmsd = kabsch_rmsd(coords, coords)
    assert rmsd < 1e-10, f"RMSD of identical structures should be ~0, got {rmsd}"


def test_rmsd_translated_structures():
    """Test RMSD after translation (should be zero after alignment)."""
    coords1 = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    coords2 = coords1 + np.array([5, 3, 2])  # Translate

    rmsd = kabsch_rmsd(coords1, coords2)
    assert rmsd < 1e-6, f"RMSD after pure translation should be ~0, got {rmsd}"


def test_rmsd_rotated_structures():
    """Test RMSD after rotation (should be zero after alignment)."""
    coords1 = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)

    # 90-degree rotation around Z-axis
    theta = np.pi / 2
    R = np.array([[np.cos(theta), -np.sin(theta), 0], [np.sin(theta), np.cos(theta), 0], [0, 0, 1]])
    coords2 = coords1 @ R.T

    rmsd = kabsch_rmsd(coords1, coords2)
    assert rmsd < 1e-6, f"RMSD after pure rotation should be ~0, got {rmsd}"


def test_rmsd_perturbed_structures():
    """Test RMSD with small perturbations."""
    np.random.seed(42)
    coords1 = np.random.rand(10, 3)
    noise = np.random.randn(10, 3) * 0.1  # Small noise
    coords2 = coords1 + noise

    rmsd = kabsch_rmsd(coords1, coords2)

    # RMSD should be approximately the RMS of noise
    expected_rmsd = np.sqrt((noise**2).mean())
    assert abs(rmsd - expected_rmsd) < 0.05, f"RMSD {rmsd} doesn't match expected ~{expected_rmsd}"


def test_rmsd_shape_mismatch():
    """Test that shape mismatch raises ValueError."""
    coords1 = np.random.rand(10, 3)
    coords2 = np.random.rand(8, 3)

    with pytest.raises(ValueError):
        kabsch_rmsd(coords1, coords2)


def test_rmsd_empty_structures():
    """Test RMSD of empty structures."""
    coords = np.array([]).reshape(0, 3)
    rmsd = kabsch_rmsd(coords, coords)
    assert rmsd == 0.0

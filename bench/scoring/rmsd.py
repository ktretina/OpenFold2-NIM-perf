"""RMSD calculation with Kabsch alignment."""

import numpy as np


def kabsch_rmsd(P: np.ndarray, Q: np.ndarray) -> float:
    """
    Compute RMSD after optimal Kabsch alignment.

    Args:
        P: (N, 3) array of coordinates (predicted)
        Q: (N, 3) array of coordinates (reference)

    Returns:
        RMSD value in Angstroms

    Raises:
        ValueError: If arrays have different shapes
    """
    if P.shape != Q.shape:
        raise ValueError(f"Shape mismatch: P {P.shape} vs Q {Q.shape}")

    if len(P) == 0:
        return 0.0

    # Center both structures
    P_centered = P - P.mean(axis=0)
    Q_centered = Q - Q.mean(axis=0)

    # Compute covariance matrix
    C = P_centered.T @ Q_centered

    # SVD
    U, S, Vt = np.linalg.svd(C)

    # Check for reflection (det < 0)
    d = np.sign(np.linalg.det(Vt.T @ U.T))

    # Optimal rotation matrix
    R = Vt.T @ np.diag([1, 1, d]) @ U.T

    # Apply rotation to P
    P_aligned = P_centered @ R

    # Compute RMSD
    diff = P_aligned - Q_centered
    rmsd = np.sqrt((diff**2).sum() / len(P))

    return float(rmsd)

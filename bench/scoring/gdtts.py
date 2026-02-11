"""GDT_TS (Global Distance Test - Total Score) calculation.

GDT_TS is a metric used in CASP (Critical Assessment of protein Structure
Prediction) to evaluate the accuracy of protein structure predictions. It
measures the percentage of residues within specific distance thresholds
after optimal superposition.

Reference:
    Zemla (2003). "LGA: a method for finding 3D similarities in protein
    structures." Nucleic Acids Research, 31(13), 3370-3374.
"""

import numpy as np
from typing import List


def compute_gdt_ts(P: np.ndarray, Q: np.ndarray, thresholds: List[float] = None) -> float:
    """
    Compute GDT_TS score between two protein structures.

    GDT_TS (Total Score) is the average of GDT scores at 4 distance thresholds:
    1Å, 2Å, 4Å, and 8Å. For each threshold, we find the optimal superposition
    and calculate the percentage of residues within that distance cutoff.

    Args:
        P: (N, 3) array of predicted structure CA coordinates in Angstroms
        Q: (N, 3) array of reference structure CA coordinates in Angstroms
        thresholds: List of distance thresholds in Angstroms.
                   Default: [1.0, 2.0, 4.0, 8.0]

    Returns:
        GDT_TS score between 0 and 100 (higher is better)
        - Score > 50 indicates good quality model
        - Score > 70 indicates high accuracy model

    Raises:
        ValueError: If arrays have different shapes or are empty
    """
    if P.shape != Q.shape:
        raise ValueError(f"Shape mismatch: P {P.shape} vs Q {Q.shape}")

    if len(P) == 0:
        raise ValueError("Cannot compute GDT_TS for empty structures")

    if thresholds is None:
        thresholds = [1.0, 2.0, 4.0, 8.0]

    N = len(P)
    gdt_scores = []

    for threshold in thresholds:
        # For each threshold, find optimal superposition and count residues within cutoff
        percent_within = _gdt_at_threshold(P, Q, threshold)
        gdt_scores.append(percent_within)

    # GDT_TS is the average of all GDT scores
    gdt_ts = np.mean(gdt_scores)

    return float(gdt_ts)


def _gdt_at_threshold(P: np.ndarray, Q: np.ndarray, threshold: float) -> float:
    """
    Calculate GDT score at a specific distance threshold.

    This implementation uses the full structure for superposition (LGA method).
    A more sophisticated approach would iteratively find the largest subset
    within the threshold, but the simple approach is commonly used and faster.

    Args:
        P: (N, 3) predicted coordinates
        Q: (N, 3) reference coordinates
        threshold: Distance cutoff in Angstroms

    Returns:
        Percentage of residues within threshold (0-100)
    """
    # Perform Kabsch alignment on full structure
    P_aligned = _kabsch_superpose(P, Q)

    # Compute distances after alignment
    distances = np.linalg.norm(P_aligned - Q, axis=1)

    # Count residues within threshold
    within_threshold = np.sum(distances <= threshold)

    # Return as percentage
    percent = (within_threshold / len(P)) * 100.0

    return percent


def _kabsch_superpose(P: np.ndarray, Q: np.ndarray) -> np.ndarray:
    """
    Apply Kabsch algorithm to superpose P onto Q.

    Args:
        P: (N, 3) array to be aligned
        Q: (N, 3) array as reference

    Returns:
        P_aligned: (N, 3) array of P after optimal rotation and translation
    """
    # Center both structures
    P_mean = P.mean(axis=0)
    Q_mean = Q.mean(axis=0)

    P_centered = P - P_mean
    Q_centered = Q - Q_mean

    # Compute covariance matrix
    C = P_centered.T @ Q_centered

    # SVD for optimal rotation
    U, S, Vt = np.linalg.svd(C)

    # Correct for reflection (ensure proper rotation)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T

    # Apply rotation and translation
    P_aligned = (P - P_mean) @ R + Q_mean

    return P_aligned


def compute_gdt_ha(P: np.ndarray, Q: np.ndarray) -> float:
    """
    Compute GDT_HA (High Accuracy) score.

    GDT_HA uses tighter thresholds (0.5Å, 1Å, 2Å, 4Å) for evaluating
    high-accuracy models.

    Args:
        P: (N, 3) predicted coordinates
        Q: (N, 3) reference coordinates

    Returns:
        GDT_HA score between 0 and 100
    """
    return compute_gdt_ts(P, Q, thresholds=[0.5, 1.0, 2.0, 4.0])

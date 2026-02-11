"""TM-score calculation for structural similarity assessment.

TM-score (Template Modeling score) is a metric for measuring the structural
similarity between two protein models. It is more sensitive to global topology
than RMSD and is normalized to be length-independent (values between 0 and 1).

Reference:
    Zhang & Skolnick (2004). "Scoring function for automated assessment of
    protein structure template quality." Proteins, 57(4), 702-710.
"""

import numpy as np


def compute_tm_score(P: np.ndarray, Q: np.ndarray) -> float:
    """
    Compute TM-score between two protein structures.

    The TM-score is calculated as:
        TM = (1/L_target) * Σ[1 / (1 + (di/d0)²)]

    where:
        - L_target is the length of the target (reference) structure
        - di is the distance between residue i after optimal superposition
        - d0 is a length-dependent scale: d0 = 1.24 * (L-15)^(1/3) - 1.8

    Args:
        P: (N, 3) array of predicted structure CA coordinates in Angstroms
        Q: (N, 3) array of reference structure CA coordinates in Angstroms

    Returns:
        TM-score value between 0 and 1 (higher is better)
        - Score > 0.5 typically indicates same fold
        - Score > 0.6 indicates high structural similarity
        - Score < 0.17 is random similarity

    Raises:
        ValueError: If arrays have different shapes or are empty
    """
    if P.shape != Q.shape:
        raise ValueError(f"Shape mismatch: P {P.shape} vs Q {Q.shape}")

    if len(P) == 0:
        raise ValueError("Cannot compute TM-score for empty structures")

    L = len(Q)  # Length of target structure

    # Compute d0 normalization factor (length-dependent)
    if L <= 21:
        d0 = 0.5
    else:
        d0 = 1.24 * ((L - 15) ** (1.0 / 3.0)) - 1.8

    # Perform Kabsch alignment to find optimal superposition
    P_aligned = _kabsch_superpose(P, Q)

    # Compute distances after alignment
    distances = np.linalg.norm(P_aligned - Q, axis=1)

    # Calculate TM-score
    tm_score = np.mean(1.0 / (1.0 + (distances / d0) ** 2))

    return float(tm_score)


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

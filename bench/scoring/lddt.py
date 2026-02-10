"""lDDT (local Distance Difference Test) calculation."""

import numpy as np


def compute_lddt(
    pred_coords: np.ndarray, true_coords: np.ndarray, inclusion_radius: float = 15.0
) -> float:
    """
    Compute lDDT (local Distance Difference Test).

    Measures preservation of local distances. Higher is better (0-1 scale).

    Args:
        pred_coords: (N, 3) predicted coordinates
        true_coords: (N, 3) true coordinates
        inclusion_radius: Radius for neighbor consideration (Angstroms)

    Returns:
        lDDT score (0-1)

    Raises:
        ValueError: If arrays have different shapes
    """
    if pred_coords.shape != true_coords.shape:
        raise ValueError(f"Shape mismatch: pred {pred_coords.shape} vs true {true_coords.shape}")

    if len(pred_coords) == 0:
        return 0.0

    thresholds = [0.5, 1.0, 2.0, 4.0]
    n_residues = len(pred_coords)

    scores = []

    for i in range(n_residues):
        # Find neighbors within inclusion_radius in true structure
        true_dists = np.linalg.norm(true_coords - true_coords[i], axis=1)
        neighbors = np.where((true_dists > 0) & (true_dists <= inclusion_radius))[0]

        if len(neighbors) == 0:
            continue

        # Compute distance differences for neighbors
        pred_dists = np.linalg.norm(pred_coords - pred_coords[i], axis=1)
        diff = np.abs(pred_dists[neighbors] - true_dists[neighbors])

        # Count how many pass each threshold
        residue_score = sum(np.mean(diff < t) for t in thresholds) / len(thresholds)
        scores.append(residue_score)

    return float(np.mean(scores)) if scores else 0.0

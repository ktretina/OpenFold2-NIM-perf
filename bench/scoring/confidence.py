"""Extract confidence scores from predicted structures."""

from pathlib import Path

import numpy as np
from Bio.PDB import PDBParser

from bench.logging import logger


def extract_mean_plddt_from_pdb(pdb_path: Path) -> float:
    """
    Extract mean pLDDT from B-factor column of PDB file.

    AlphaFold and OpenFold store pLDDT (0-100) in the B-factor column.

    Args:
        pdb_path: Path to PDB file

    Returns:
        Mean pLDDT score (0-100)
    """
    parser = PDBParser(QUIET=True)

    try:
        structure = parser.get_structure("pred", str(pdb_path))
    except Exception as e:
        logger.warning(f"Failed to parse {pdb_path}: {e}")
        return 0.0

    plddts = []

    for model in structure:
        for chain in model:
            for residue in chain:
                # Skip heteroatoms
                if residue.id[0] != " ":
                    continue

                for atom in residue:
                    plddts.append(atom.get_bfactor())

        # Only use first model
        break

    if not plddts:
        logger.warning(f"No pLDDT values found in {pdb_path}")
        return 0.0

    return float(np.mean(plddts))

"""Structure parsing utilities."""

from pathlib import Path

import numpy as np
from Bio.PDB import PDBParser, MMCIFParser

from bench.logging import logger


def parse_pdb_coordinates(
    structure_path: Path, atoms: list[str] = None, chain: str = None
) -> np.ndarray:
    """
    Extract atom coordinates from PDB or mmCIF file.

    Args:
        structure_path: Path to PDB or mmCIF file
        atoms: List of atom names to extract (default: ["CA"])
        chain: Specific chain ID to extract (default: first chain)

    Returns:
        Numpy array of shape (N, 3) with coordinates

    Raises:
        RuntimeError: If parsing fails
    """
    if atoms is None:
        atoms = ["CA"]

    # Determine file type and parse
    suffix = structure_path.suffix.lower()
    if suffix == ".cif":
        parser = MMCIFParser(QUIET=True)
    elif suffix in [".pdb", ".ent"]:
        parser = PDBParser(QUIET=True)
    else:
        # Try PDB parser as fallback
        parser = PDBParser(QUIET=True)

    try:
        structure = parser.get_structure("structure", str(structure_path))
    except Exception as e:
        raise RuntimeError(f"Failed to parse structure file {structure_path}: {e}")

    # Extract coordinates
    coords = []

    for model in structure:
        for chain_obj in model:
            # If specific chain requested, skip others
            if chain is not None and chain_obj.id != chain:
                continue

            for residue in chain_obj:
                # Skip heteroatoms
                if residue.id[0] != " ":
                    continue

                # Extract requested atoms
                for atom_name in atoms:
                    if atom_name in residue:
                        atom = residue[atom_name]
                        coords.append(atom.get_coord())

            # If we found atoms and no specific chain was requested, break after first chain
            if coords and chain is None:
                break

        # Only use first model
        break

    if not coords:
        raise RuntimeError(f"No {atoms} atoms found in {structure_path}")

    return np.array(coords)

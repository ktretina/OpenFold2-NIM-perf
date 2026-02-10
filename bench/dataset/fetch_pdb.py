"""PDB structure fetching and parsing."""

from pathlib import Path

import requests
from Bio.PDB import MMCIFParser

from bench.logging import logger


def fetch_pdb_mmcif(pdb_id: str, output_dir: Path) -> Path:
    """
    Download mmCIF file from RCSB.

    Args:
        pdb_id: PDB ID (e.g., "1UBQ")
        output_dir: Directory to save file

    Returns:
        Path to downloaded file

    Raises:
        RuntimeError: If download fails
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{pdb_id}.cif"

    if output_path.exists():
        logger.debug(f"mmCIF file already exists: {output_path}")
        return output_path

    url = f"https://files.rcsb.org/download/{pdb_id}.cif"
    logger.info(f"Downloading {pdb_id} from RCSB...")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        output_path.write_text(response.text)
        logger.info(f"Downloaded {pdb_id} to {output_path}")
        return output_path

    except requests.RequestException as e:
        raise RuntimeError(f"Failed to download {pdb_id}: {e}")


def extract_chain_sequence(mmcif_path: Path, chain: str) -> tuple[str, list[tuple[float, float, float]]]:
    """
    Extract amino acid sequence and Cα coordinates from mmCIF file.

    Args:
        mmcif_path: Path to mmCIF file
        chain: Chain identifier

    Returns:
        Tuple of (sequence, ca_coords) where ca_coords is list of (x, y, z) tuples

    Raises:
        RuntimeError: If parsing fails or chain not found
    """
    parser = MMCIFParser(QUIET=True)

    try:
        structure = parser.get_structure("protein", str(mmcif_path))
    except Exception as e:
        raise RuntimeError(f"Failed to parse mmCIF file: {e}")

    # Find the specified chain
    target_chain = None
    for model in structure:
        for chain_obj in model:
            if chain_obj.id == chain:
                target_chain = chain_obj
                break
        if target_chain:
            break

    if target_chain is None:
        available_chains = [c.id for model in structure for c in model]
        raise RuntimeError(
            f"Chain {chain} not found in structure. Available chains: {available_chains}"
        )

    # Extract sequence and Cα coordinates
    sequence = []
    ca_coords = []

    # Standard amino acid three-letter codes
    aa_codes = {
        "ALA": "A",
        "CYS": "C",
        "ASP": "D",
        "GLU": "E",
        "PHE": "F",
        "GLY": "G",
        "HIS": "H",
        "ILE": "I",
        "LYS": "K",
        "LEU": "L",
        "MET": "M",
        "ASN": "N",
        "PRO": "P",
        "GLN": "Q",
        "ARG": "R",
        "SER": "S",
        "THR": "T",
        "VAL": "V",
        "TRP": "W",
        "TYR": "Y",
    }

    for residue in target_chain:
        # Skip heteroatoms
        if residue.id[0] != " ":
            continue

        resname = residue.resname
        if resname not in aa_codes:
            logger.warning(f"Unknown residue {resname}, skipping")
            continue

        # Check for Cα
        if "CA" not in residue:
            logger.warning(f"No Cα in residue {residue.id}, skipping")
            continue

        sequence.append(aa_codes[resname])
        ca_atom = residue["CA"]
        ca_coords.append(tuple(ca_atom.get_coord()))

    if not sequence:
        raise RuntimeError(f"No valid residues found in chain {chain}")

    sequence_str = "".join(sequence)
    logger.debug(f"Extracted sequence of length {len(sequence_str)} from chain {chain}")

    return sequence_str, ca_coords

"""Synthetic MSA generation for benchmarking."""

import random
from typing import Optional

from bench.logging import logger


# Conservative substitution matrix (BLOSUM-inspired)
CONSERVATIVE_SUBS = {
    "A": ["A", "V", "G", "S"],  # Small aliphatic
    "V": ["V", "I", "L", "A"],  # Hydrophobic aliphatic
    "I": ["I", "V", "L", "M"],
    "L": ["L", "I", "V", "M"],
    "M": ["M", "L", "I", "V"],
    "F": ["F", "Y", "W", "L"],  # Aromatic
    "Y": ["Y", "F", "W", "H"],
    "W": ["W", "F", "Y", "H"],
    "S": ["S", "T", "A", "C"],  # Small polar
    "T": ["T", "S", "A", "V"],
    "N": ["N", "D", "S", "Q"],  # Polar
    "Q": ["Q", "E", "N", "K"],
    "C": ["C", "S", "A", "T"],  # Cysteine (usually conserved)
    "G": ["G", "A", "S", "P"],  # Glycine (flexible)
    "P": ["P", "G", "A", "S"],  # Proline (rigid)
    "D": ["D", "E", "N", "S"],  # Acidic
    "E": ["E", "D", "Q", "K"],
    "K": ["K", "R", "Q", "E"],  # Basic
    "R": ["R", "K", "Q", "H"],
    "H": ["H", "R", "Y", "Q"],
}

ALL_AA = list("ACDEFGHIKLMNPQRSTVWY")


def mutate_sequence(
    sequence: str, mutation_rate: float = 0.3, conserve_structure: bool = True
) -> str:
    """
    Generate synthetic homolog with controlled mutations.

    Args:
        sequence: Query amino acid sequence
        mutation_rate: Fraction of residues to mutate (0.0-1.0)
        conserve_structure: If True, use conservative substitutions

    Returns:
        Mutated sequence of same length
    """
    mutated = []
    for aa in sequence:
        if random.random() < mutation_rate:
            if conserve_structure and aa in CONSERVATIVE_SUBS:
                # Pick from conservative substitution set
                mutated.append(random.choice(CONSERVATIVE_SUBS[aa]))
            else:
                # Random substitution
                mutated.append(random.choice(ALL_AA))
        else:
            # Keep original
            mutated.append(aa)

    return "".join(mutated)


def generate_synthetic_a3m(
    sequence: str, depth: int = 1, mutation_rate: float = 0.3, seed: Optional[int] = None
) -> str:
    """
    Generate synthetic A3M alignment with controlled diversity.

    A3M format:
    >query_sequence
    SEQUENCE
    >homolog_1
    MUTATED_SEQUENCE_1
    ...

    Args:
        sequence: Query sequence
        depth: Number of sequences in MSA (including query)
        mutation_rate: Average fraction of positions mutated per homolog
        seed: Random seed for reproducibility

    Returns:
        A3M format string
    """
    if seed is not None:
        random.seed(seed)

    if depth == 1:
        # Query only
        return f">query\n{sequence}\n"

    lines = [f">query\n{sequence}\n"]

    # Generate depth-1 synthetic homologs with varying mutation rates
    for i in range(depth - 1):
        # Vary mutation rate: closer homologs (20%) to distant (50%)
        # Simulate natural MSA diversity profile
        if i < (depth - 1) * 0.3:
            # Close homologs (30% of MSA)
            mut_rate = mutation_rate * 0.5  # 15% mutations
        elif i < (depth - 1) * 0.7:
            # Medium distance (40% of MSA)
            mut_rate = mutation_rate  # 30% mutations
        else:
            # Distant homologs (30% of MSA)
            mut_rate = mutation_rate * 1.5  # 45% mutations

        mutated = mutate_sequence(sequence, mutation_rate=mut_rate, conserve_structure=True)
        lines.append(f">synthetic_homolog_{i+1}\n{mutated}\n")

    return "".join(lines)


def generate_synthetic_sto(
    sequence: str, depth: int = 1, mutation_rate: float = 0.3, seed: Optional[int] = None
) -> str:
    """
    Generate synthetic Stockholm format alignment.

    Stockholm format (used by OpenFold):
    # STOCKHOLM 1.0
    query              SEQUENCE
    synthetic_homolog_1 MUTATED_SEQUENCE_1
    //

    Note: Stockholm requires aligned sequences (same length, gaps with '-')
    For synthetic MSAs without real gaps, sequences are same length.

    Args:
        sequence: Query sequence
        depth: Number of sequences in MSA (including query)
        mutation_rate: Average fraction of positions mutated per homolog
        seed: Random seed for reproducibility

    Returns:
        Stockholm format string
    """
    if seed is not None:
        random.seed(seed)

    lines = ["# STOCKHOLM 1.0\n"]

    # Query sequence (padded for alignment)
    lines.append(f"{'query':<20} {sequence}\n")

    if depth > 1:
        for i in range(depth - 1):
            # Generate mutation rate variation
            if i < (depth - 1) * 0.3:
                mut_rate = mutation_rate * 0.5
            elif i < (depth - 1) * 0.7:
                mut_rate = mutation_rate
            else:
                mut_rate = mutation_rate * 1.5

            mutated = mutate_sequence(sequence, mutation_rate=mut_rate, conserve_structure=True)
            seq_name = f"synth_hom_{i+1}"
            lines.append(f"{seq_name:<20} {mutated}\n")

    lines.append("//\n")
    return "".join(lines)


def generate_synthetic_sequence(length: int, seed: Optional[int] = None) -> str:
    """
    Generate a random amino acid sequence.

    Args:
        length: Sequence length
        seed: Random seed

    Returns:
        Random amino acid sequence
    """
    if seed is not None:
        random.seed(seed)

    return "".join(random.choices(ALL_AA, k=length))

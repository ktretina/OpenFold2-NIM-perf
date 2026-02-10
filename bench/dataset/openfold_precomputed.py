"""Create OpenFold precomputed alignment directories."""

from pathlib import Path

from bench.dataset.synthetic_msa import generate_synthetic_a3m, generate_synthetic_sto
from bench.logging import logger


def create_openfold_alignment_dir(
    target_id: str, sequence: str, msa_depth: int, output_dir: Path
):
    """
    Create OpenFold precomputed alignment directory.

    OpenFold expects:
    - bfd_uniclust_hits.a3m
    - mgnify_hits.sto
    - uniref90_hits.sto
    - pdb70_hits.hhr (minimal empty file)

    Args:
        target_id: Target identifier
        sequence: Amino acid sequence
        msa_depth: MSA depth
        output_dir: Base output directory
    """
    target_dir = output_dir / target_id
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. bfd_uniclust_hits.a3m (main MSA)
    a3m = generate_synthetic_a3m(sequence, msa_depth)
    (target_dir / "bfd_uniclust_hits.a3m").write_text(a3m)

    # 2. mgnify_hits.sto (environmental sequences, typically smaller)
    sto_mgnify = generate_synthetic_sto(sequence, max(1, msa_depth // 4))
    (target_dir / "mgnify_hits.sto").write_text(sto_mgnify)

    # 3. uniref90_hits.sto
    sto_uniref90 = generate_synthetic_sto(sequence, msa_depth)
    (target_dir / "uniref90_hits.sto").write_text(sto_uniref90)

    # 4. pdb70_hits.hhr (minimal no-hits file for template search)
    hhr = "Query         query\nMatch_columns 0\nNo_of_seqs    1\nDone!\n"
    (target_dir / "pdb70_hits.hhr").write_text(hhr)

    logger.debug(f"Created OpenFold alignment directory for {target_id} at {target_dir}")

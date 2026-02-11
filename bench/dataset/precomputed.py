"""MSA/template precomputation for apples-to-apples comparison.

This module enables generating MSAs once and reusing them for both NIM and
OpenFold, ensuring identical inputs for fair benchmarking. This transforms
the benchmark from an "MSA pipeline benchmark" into a pure "inference benchmark".
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from bench.dataset.synthetic_msa import generate_synthetic_a3m, generate_synthetic_sto
from bench.results.schema import PrecomputedInputs
from bench.logging import logger


def compute_msa_hash(msa_content: str) -> str:
    """
    Compute SHA256 hash of MSA content for verification.

    Args:
        msa_content: MSA content as string

    Returns:
        Hexadecimal SHA256 hash
    """
    return hashlib.sha256(msa_content.encode()).hexdigest()


def precompute_inputs(
    target_id: str,
    sequence: str,
    msa_depth: int,
    output_dir: Path,
    source: str = "synthetic",
    mutation_rate: float = 0.3,
    seed: Optional[int] = None
) -> PrecomputedInputs:
    """
    Precompute and save MSA/template inputs for both NIM and OpenFold.

    This ensures IDENTICAL inputs are used for both systems, enabling
    fair apples-to-apples comparison of inference performance.

    The output directory structure:
    output_dir/
      {target_id}/
        manifest.json          # Metadata and hashes
        nim_msa.a3m           # NIM MSA input
        openfold_alignments/  # OpenFold alignment directory
          bfd_uniclust_hits.a3m    # Main MSA (identical to NIM)
          uniref90_hits.sto        # UniRef90 hits
          mgnify_hits.sto          # MGnify environmental sequences
          pdb70_hits.hhr           # Template hits (empty for no-template mode)

    Args:
        target_id: Unique identifier for this target
        sequence: Amino acid sequence
        msa_depth: Number of sequences in MSA (including query)
        output_dir: Root directory for precomputed data
        source: Source of MSA ("synthetic", "hhsuite", "mmseqs2")
        mutation_rate: Mutation rate for synthetic MSAs (0.0-1.0)
        seed: Random seed for reproducibility

    Returns:
        PrecomputedInputs manifest

    Raises:
        ValueError: If msa_depth < 1
    """
    if msa_depth < 1:
        raise ValueError(f"MSA depth must be >= 1, got {msa_depth}")

    output_dir = Path(output_dir)
    target_dir = output_dir / target_id
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Precomputing MSAs for %s (depth=%d, source=%s)", target_id, msa_depth, source)

    # Generate MSAs with controlled randomness
    # Use hash of target_id + msa_depth as seed for reproducibility across runs
    if seed is None and source == "synthetic":
        seed = abs(hash(f"{target_id}_{msa_depth}")) % (2**32)

    # For NIM: A3M format
    nim_a3m = generate_synthetic_a3m(sequence, depth=msa_depth, mutation_rate=mutation_rate, seed=seed)
    nim_a3m_path = target_dir / "nim_msa.a3m"
    nim_a3m_path.write_text(nim_a3m)

    # For OpenFold: directory with multiple alignment files
    openfold_dir = target_dir / "openfold_alignments"
    openfold_dir.mkdir(exist_ok=True)

    # Main MSA (bfd_uniclust) - IDENTICAL to NIM for fair comparison
    (openfold_dir / "bfd_uniclust_hits.a3m").write_text(nim_a3m)

    # Environmental sequences (MGnify) - reduced depth
    mgnify_depth = max(1, msa_depth // 4)
    mgnify_sto = generate_synthetic_sto(
        sequence,
        depth=mgnify_depth,
        mutation_rate=mutation_rate,
        seed=seed + 1 if seed is not None else None
    )
    (openfold_dir / "mgnify_hits.sto").write_text(mgnify_sto)

    # UniRef90 hits - same depth as main MSA
    uniref_sto = generate_synthetic_sto(
        sequence,
        depth=msa_depth,
        mutation_rate=mutation_rate,
        seed=seed + 2 if seed is not None else None
    )
    (openfold_dir / "uniref90_hits.sto").write_text(uniref_sto)

    # Empty template file (templates disabled for fair comparison)
    # HHR format: minimal header to indicate no templates
    hhr_content = "Query         query\nMatch_columns 0\nNo_of_seqs    1\nDone!\n"
    (openfold_dir / "pdb70_hits.hhr").write_text(hhr_content)

    # Compute hash for verification
    msa_hash = compute_msa_hash(nim_a3m)

    # Create manifest
    manifest = PrecomputedInputs(
        target_id=target_id,
        sequence=sequence,
        msa_depth=msa_depth,
        msa_hash=msa_hash,
        template_hash=None,  # No templates
        nim_a3m_path=nim_a3m_path.relative_to(output_dir),
        openfold_alignment_dir=openfold_dir.relative_to(output_dir),
        template_dir=None,
        created_at=datetime.now(),
        source=source
    )

    # Save manifest as JSON
    manifest_path = target_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2))

    logger.info("Saved precomputed inputs to %s (hash: %s...)", target_dir, msa_hash[:16])
    return manifest


def load_precomputed_inputs(target_id: str, precomputed_dir: Path) -> PrecomputedInputs:
    """
    Load and validate precomputed inputs from disk.

    Verifies that:
    1. Manifest exists
    2. All referenced files exist
    3. MSA hash matches content (integrity check)

    Args:
        target_id: Target identifier
        precomputed_dir: Root directory containing precomputed data

    Returns:
        PrecomputedInputs manifest

    Raises:
        FileNotFoundError: If manifest or required files are missing
        ValueError: If MSA hash verification fails
    """
    precomputed_dir = Path(precomputed_dir)
    manifest_path = precomputed_dir / target_id / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Precomputed manifest not found: {manifest_path}")

    # Load manifest
    manifest = PrecomputedInputs.model_validate_json(manifest_path.read_text())

    # Verify NIM MSA file exists
    nim_a3m_path = precomputed_dir / manifest.nim_a3m_path
    if not nim_a3m_path.exists():
        raise FileNotFoundError(f"NIM MSA file not found: {nim_a3m_path}")

    # Verify OpenFold alignment directory exists
    openfold_dir = precomputed_dir / manifest.openfold_alignment_dir
    if not openfold_dir.exists():
        raise FileNotFoundError(f"OpenFold alignment directory not found: {openfold_dir}")

    # Verify MSA hash (integrity check)
    actual_content = nim_a3m_path.read_text()
    actual_hash = compute_msa_hash(actual_content)

    if actual_hash != manifest.msa_hash:
        raise ValueError(
            f"MSA hash mismatch for {target_id}:\n"
            f"  Expected: {manifest.msa_hash}\n"
            f"  Actual:   {actual_hash}\n"
            f"This indicates file corruption or tampering."
        )

    # Update manifest paths to be absolute
    manifest.nim_a3m_path = nim_a3m_path
    manifest.openfold_alignment_dir = openfold_dir
    if manifest.template_dir:
        manifest.template_dir = precomputed_dir / manifest.template_dir

    logger.debug(
        "Loaded precomputed inputs for %s (depth=%d, hash verified)",
        target_id, manifest.msa_depth
    )
    return manifest


def precompute_batch(
    targets: list[dict],
    output_dir: Path,
    msa_depths: list[int],
    source: str = "synthetic",
    mutation_rate: float = 0.3,
    overwrite: bool = False
) -> int:
    """
    Precompute MSAs for a batch of targets at multiple depths.

    Args:
        targets: List of target dicts with 'id' and 'sequence' keys
        output_dir: Root directory for precomputed data
        msa_depths: List of MSA depths to generate
        source: MSA source type
        mutation_rate: Mutation rate for synthetic MSAs
        overwrite: If True, overwrite existing precomputed data

    Returns:
        Number of precomputed MSAs generated

    Example:
        >>> targets = [
        ...     {"id": "T1234", "sequence": "MKTAYIAKQRQISFVKSHFSRQLE..."},
        ...     {"id": "T5678", "sequence": "AKQRQISFVKSHFSRQLEMKTAYI..."},
        ... ]
        >>> count = precompute_batch(
        ...     targets,
        ...     Path("data/precomputed/casp15"),
        ...     msa_depths=[32, 64, 128, 256]
        ... )
        >>> print(f"Generated {count} precomputed MSAs")
    """
    count = 0
    total = len(targets) * len(msa_depths)

    for target in targets:
        target_id = target["id"]
        sequence = target["sequence"]

        for msa_depth in msa_depths:
            # Check if already exists
            manifest_path = output_dir / target_id / "manifest.json"
            if manifest_path.exists() and not overwrite:
                logger.debug("Skipping %s (depth=%d) - already exists", target_id, msa_depth)
                continue

            try:
                precompute_inputs(
                    target_id=target_id,
                    sequence=sequence,
                    msa_depth=msa_depth,
                    output_dir=output_dir,
                    source=source,
                    mutation_rate=mutation_rate
                )
                count += 1
                logger.info("Progress: %d/%d precomputed MSAs generated", count, total)

            except Exception as e:
                logger.error("Failed to precompute %s (depth=%d): %s", target_id, msa_depth, e)
                continue

    return count

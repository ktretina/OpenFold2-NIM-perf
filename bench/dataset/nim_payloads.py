"""Generate NIM request payloads."""

from bench.dataset.synthetic_msa import generate_synthetic_a3m


def create_nim_payload(
    target_id: str, sequence: str, msa_depth: int, selected_models: list[int] = None
) -> dict:
    """
    Generate NIM request payload.

    Args:
        target_id: Target identifier
        sequence: Amino acid sequence
        msa_depth: MSA depth
        selected_models: Model indices (default: [3])

    Returns:
        NIM request payload dictionary
    """
    if selected_models is None:
        selected_models = [3]

    # Generate synthetic MSAs
    uniref90_a3m = generate_synthetic_a3m(sequence, msa_depth)
    bfd_a3m = generate_synthetic_a3m(sequence, max(1, msa_depth // 2))

    return {
        "sequence": sequence,
        "input_id": target_id,
        "selected_models": selected_models,
        "alignments": {"uniref90": uniref90_a3m, "small_bfd": bfd_a3m},
        "use_templates": False,
        "relax_prediction": False,
    }

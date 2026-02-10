"""Test synthetic MSA generation."""

import pytest

from bench.dataset.synthetic_msa import (
    generate_synthetic_a3m,
    generate_synthetic_sto,
    mutate_sequence,
)


def test_mutate_sequence_no_mutation():
    """Test that mutation_rate=0 keeps sequence unchanged."""
    sequence = "ACDEFGHIKLMNPQRSTVWY"
    mutated = mutate_sequence(sequence, mutation_rate=0.0)
    assert mutated == sequence


def test_mutate_sequence_full_mutation():
    """Test that mutation_rate=1 changes all positions."""
    sequence = "AAAAAAAA"
    mutated = mutate_sequence(sequence, mutation_rate=1.0, conserve_structure=False)
    # Should have at least some non-A residues
    assert mutated != sequence


def test_mutate_sequence_length_preserved():
    """Test that mutated sequence has same length."""
    sequence = "ACDEFGHIKLMNPQRSTVWY"
    mutated = mutate_sequence(sequence, mutation_rate=0.5)
    assert len(mutated) == len(sequence)


def test_generate_synthetic_a3m_depth_1():
    """Test A3M with depth 1 (query only)."""
    sequence = "ACDEFGHIK"
    a3m = generate_synthetic_a3m(sequence, depth=1)

    # Should contain query header and sequence
    assert ">query" in a3m
    assert sequence in a3m
    # Should not contain homologs
    assert "homolog" not in a3m


def test_generate_synthetic_a3m_depth_5():
    """Test A3M with depth 5."""
    sequence = "ACDEFGHIK"
    a3m = generate_synthetic_a3m(sequence, depth=5, seed=42)

    # Should contain query + 4 homologs
    lines = a3m.strip().split("\n")
    headers = [l for l in lines if l.startswith(">")]
    assert len(headers) == 5  # query + 4 homologs

    # All sequences should have same length
    sequences = [lines[i + 1] for i in range(len(lines)) if lines[i].startswith(">")]
    assert all(len(s) == len(sequence) for s in sequences)


def test_generate_synthetic_a3m_reproducible():
    """Test that seed makes generation reproducible."""
    sequence = "ACDEFGHIK"
    a3m1 = generate_synthetic_a3m(sequence, depth=10, seed=42)
    a3m2 = generate_synthetic_a3m(sequence, depth=10, seed=42)
    assert a3m1 == a3m2


def test_generate_synthetic_sto_depth_1():
    """Test Stockholm format with depth 1."""
    sequence = "ACDEFGHIK"
    sto = generate_synthetic_sto(sequence, depth=1)

    # Should have Stockholm header
    assert "# STOCKHOLM 1.0" in sto
    # Should have query line
    assert "query" in sto
    assert sequence in sto
    # Should have terminator
    assert "//" in sto


def test_generate_synthetic_sto_depth_5():
    """Test Stockholm format with depth 5."""
    sequence = "ACDEFGHIK"
    sto = generate_synthetic_sto(sequence, depth=5, seed=42)

    lines = sto.strip().split("\n")
    # Filter out header and terminator
    seq_lines = [l for l in lines if not l.startswith("#") and not l.startswith("//") and l.strip()]

    # Should have 5 sequences (query + 4 homologs)
    assert len(seq_lines) == 5


def test_generate_synthetic_sto_format():
    """Test Stockholm format correctness."""
    sequence = "ACDEFGHIK"
    sto = generate_synthetic_sto(sequence, depth=3)

    # Must start with header
    assert sto.startswith("# STOCKHOLM 1.0\n")
    # Must end with terminator
    assert sto.strip().endswith("//")

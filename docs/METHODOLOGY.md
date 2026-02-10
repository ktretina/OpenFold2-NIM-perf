# Benchmarking Methodology

## Design Principles

### 1. Fairness

Both systems (NIM and OpenFold) receive identical inputs:
- **Synthetic MSAs**: Generated with controlled diversity, avoiding database dependency
- **No templates**: Template-free inference by default
- **Same sequences**: Identical test targets for accuracy comparison
- **Consistent precision**: Both systems compared at similar precision levels (bf16)

### 2. Reproducibility

- **Controlled warmup**: Explicit warmup phase before measured runs
- **Multiple repeats**: 3+ repeats per configuration with statistical aggregation
- **Seeded randomness**: Deterministic synthetic MSA generation
- **Version tracking**: Git commits, container digests, package versions recorded

### 3. Transparency

- **Open source**: All code, configs, and data generation scripts available
- **Documented metrics**: Clear definitions for all measurements
- **Raw data**: Per-prediction records and timeseries data saved
- **Methodology document**: This file!

## Avoiding Confounders

### Warmup Phase

**Why warmup matters:**
- First run may include model loading, compilation, cache warming
- JIT compilation, cuDNN autotuning can skew first-run timings
- Network/filesystem caches may not be primed

**Warmup protocol:**
1. **NIM**: Wait for `/v1/health/ready` → run 1 warmup prediction per variant
2. **OpenFold**: Run 1 warmup prediction per model preset
3. **Discard warmup results** - not included in analysis

### Thermal State

**Problem**: GPU throttling due to temperature can skew results

**Mitigation**:
1. Monitor GPU temperature during runs via NVML
2. Flag results if thermal throttling detected (clocks < base frequency)
3. Wait between predictions if needed (though typically not required)

### MSA and Template Parity

**Problem**: Different MSA quality or template usage creates unfair comparison

**Solution**:
- **Synthetic MSAs**: Both systems use identically generated MSAs
  - Same depth (number of sequences)
  - Same diversity profile (mutation rate distribution)
  - Same format (A3M for NIM, STO for OpenFold)
- **No templates**: Templates disabled by default
  - Avoids dependency on template database
  - Focuses on MSA-driven prediction

### Caching Effects

**Problem**: Second run on same input may be faster due to caching

**Mitigation**:
- Each target predicted only once per repeat
- Repeats run with fresh process/container restart if needed
- Cache state documented in metadata

## Benchmark Suites

### 1. accuracy_small

**Purpose**: Compare prediction accuracy on known structures

**Design**:
- 20 diverse PDB targets (30-400 residues)
- Mix of fold types (α, β, α+β)
- High-quality structures (resolution < 2.5Å)
- Real ground truth for RMSD/lDDT calculation

**MSAs**: Synthetic, depth=1 (query-only) for consistency

**Metrics**:
- Cα RMSD (after Kabsch alignment)
- Cα lDDT (local distance difference)
- Mean pLDDT (model confidence)

### 2. scaling_seq_length

**Purpose**: Characterize compute scaling with sequence length

**Design**:
- Synthetic sequences: 128, 256, 512, 768, 1024 residues
- Fixed MSA depth (8 sequences)
- 3 repeats per length

**Metrics**:
- Wall time vs length
- Peak GPU memory vs length
- GPU utilization vs length

**Expected behavior**: Quadratic or near-quadratic scaling due to MSA processing

### 3. scaling_msa_depth

**Purpose**: Understand MSA processing cost

**Design**:
- Fixed sequence length (256 residues)
- MSA depths: 1, 8, 32, 128, 512
- 3 repeats per depth

**Metrics**:
- Wall time vs MSA depth
- Memory usage vs MSA depth

**Expected behavior**: Near-linear or subquadratic scaling

## Metrics Definitions

### Time to First GPU Activity

**Definition**: Time from prediction start until GPU shows measurable activity

**Two measurement methods**:

1. **time_to_first_gpu_activity_s**: From request start → first NVML sample showing:
   - GPU utilization > 5%, OR
   - GPU memory increase > 256 MB over baseline

2. **time_to_first_response_byte_s** (NIM only):
   - HTTP stream first byte received
   - Measures API response latency

**Interpretation**:
- High value → significant overhead (model loading, preprocessing)
- Low value → efficient startup

### GPU Hours per Prediction

**Formula**: `gpu_hours = wall_time_s * num_gpus / 3600`

**Purpose**: Normalize cost across GPU types and multi-GPU configs

**Interpretation**: Lower is better (more efficient)

**Note**: Does NOT account for GPU performance differences (A100 vs H100)

### GPU Utilization Metrics

**SM Utilization** (`gpu_sm_util_avg_pct`):
- Percentage of time SMs are actively executing
- Averaged across sampling interval (50ms)
- Averaged across all GPUs

**Memory Utilization** (`gpu_mem_util_pct`):
- Not memory capacity, but memory *bandwidth* utilization
- Indicates memory-bound vs compute-bound

**Interpretation**:
- High SM util (>80%) → compute-bound, good efficiency
- Low SM util (<50%) → bottleneck elsewhere (I/O, CPU preprocessing)

### Energy Consumption

**Formula**: Trapezoidal integration of power readings

```
energy_wh = Σ[(power[i] + power[i+1])/2 * (t[i+1] - t[i])] / 3600
```

**Sampling**: 50ms intervals via NVML

**Units**: Watt-hours (Wh)

**Interpretation**: Lower is better (more energy efficient)

### Accuracy Metrics

#### Cα RMSD

**Formula**: Root-mean-square deviation of Cα atoms after Kabsch alignment

```
RMSD = sqrt(Σ||p_i - R*q_i||² / N)
```

where:
- `p_i` = predicted Cα coordinate
- `q_i` = true Cα coordinate
- `R` = optimal rotation matrix (Kabsch algorithm)
- `N` = number of residues

**Units**: Angstroms (Å)

**Interpretation**: Lower is better
- < 2Å: Excellent
- 2-5Å: Good
- 5-10Å: Poor
- > 10Å: Incorrect fold

#### Cα lDDT

**Formula**: Local Distance Difference Test

For each residue i:
1. Find neighbors within 15Å in true structure
2. Compute distance differences in predicted vs true structure
3. Count fraction passing thresholds: [0.5Å, 1.0Å, 2.0Å, 4.0Å]
4. Average across neighbors

Overall lDDT = average across all residues

**Units**: 0-1 scale (higher is better)

**Interpretation**:
- > 0.9: Excellent local accuracy
- 0.7-0.9: Good
- 0.5-0.7: Moderate
- < 0.5: Poor

**Advantages over RMSD**:
- Local metric (not sensitive to domain movements)
- No alignment needed
- More robust to flexible regions

#### Mean pLDDT

**Definition**: Per-residue predicted lDDT from model

**Source**: B-factor column in PDB file (AlphaFold convention)

**Units**: 0-100 (higher is better)

**Interpretation**:
- > 90: Very high confidence
- 70-90: Confident
- 50-70: Low confidence
- < 50: Very low confidence (disordered)

**Note**: This is a *predicted* confidence, not ground truth accuracy

## Pareto Frontier

**Definition**: Set of non-dominated points in accuracy-performance space

**Computation**:
- X-axis: GPU hours per prediction (cost, minimize)
- Y-axis: lDDT score (accuracy, maximize)
- Point A dominates B if: A has lower cost AND higher accuracy
- Pareto frontier = all non-dominated points

**Interpretation**:
- Points on frontier are optimal trade-offs
- Points inside frontier are suboptimal (dominated)
- Frontier shape shows cost of accuracy gains

**Use cases**:
- **Latency-critical**: Choose leftmost point (fastest)
- **Accuracy-critical**: Choose topmost point (most accurate)
- **Balanced**: Choose point with best accuracy/cost ratio

## Statistical Reporting

### Aggregation

- **Mean ± std**: Reported for all metrics across repeats
- **Median**: Reported for skewed distributions (rare)
- **Min/max**: Included in detailed tables

### Outlier Handling

- Outliers NOT automatically removed
- Flagged in logs if detected (>3σ from mean)
- User can investigate and decide to exclude

### Significance Testing

- Not performed by default (descriptive statistics only)
- Can add t-tests if comparing specific variants
- Focus on effect sizes (mean differences) over p-values

## Limitations

### Synthetic MSAs

**Limitation**: Synthetic MSAs don't capture coevolution (paired mutations)

**Impact**:
- May underestimate benefit of MSAs
- Absolute accuracy may be lower than with real MSAs
- Relative comparison (NIM vs OpenFold) still valid

**Rationale**: Consistency and reproducibility outweigh realism

### Ground Truth Quality

**Limitation**: PDB structures may have errors, low resolution, or missing regions

**Mitigation**:
- Curated target list (high-quality structures)
- Multiple accuracy metrics (RMSD, lDDT)
- Documented resolution and quality metrics

### Single-Domain Proteins

**Limitation**: Benchmark focuses on monomeric, single-domain proteins

**Rationale**:
- Simpler evaluation (single RMSD, no alignment ambiguity)
- Keeps benchmark fast (<2 hours)

**Future work**: Add multi-domain and oligomeric targets

### Template-Free Only

**Limitation**: Templates disabled by default

**Rationale**:
- Avoids template database dependency
- Focus on MSA-driven accuracy

**Future work**: Add template-based benchmark suite

## Changelog

### v0.1.0 (2025-01-15)
- Initial methodology
- Synthetic MSA approach
- Accuracy, scaling suites
- Pareto frontier analysis

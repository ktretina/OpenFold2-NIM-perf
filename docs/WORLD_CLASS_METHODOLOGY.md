# World-Class Benchmarking Methodology

This document explains the rationale behind the benchmarking improvements that transform this suite into a publication-quality, community-trusted evaluation framework.

## Table of Contents

- [Overview](#overview)
- [Key Problems Solved](#key-problems-solved)
- [Methodological Improvements](#methodological-improvements)
- [Best Practices](#best-practices)
- [Interpretation Guide](#interpretation-guide)
- [Publication Checklist](#publication-checklist)

---

## Overview

### What Makes a Benchmark "World-Class"?

A world-class benchmark meets these criteria:

1. **Fair Comparison**: Identical inputs, controlled variables
2. **Statistical Rigor**: Sufficient samples, proper warmup, tail latency analysis
3. **Reproducibility**: Version pinning, complete metadata, reproducible inputs
4. **Comprehensive Metrics**: Industry-standard accuracy measures
5. **Production Relevance**: Measures real-world deployment scenarios

### Transformation Summary

This benchmark suite has been enhanced from a "quick comparison tool" to a **publication-quality evaluation framework**:

| Aspect | Before | After |
|--------|--------|-------|
| **Accuracy Metrics** | RMSD, lDDT | + TM-score, GDT_TS (CASP standards) |
| **Statistical Method** | 3 repeats, no warmup | Warmup passes, 20+ measurements, percentiles |
| **Input Parity** | Independent MSA generation | Precomputed MSAs (identical inputs) |
| **Deployment Reality** | Warm-start only | + Cold-start measurements |
| **Reproducibility** | `:latest` tags | Version pinning, digest capture |
| **Distribution Analysis** | Mean ± std | p50, p90, p95, p99 percentiles |

---

## Key Problems Solved

### Problem 1: Non-Identical Inputs (MSA Variance)

**The Issue:**
- MSAs were generated independently for NIM and OpenFold
- Synthetic MSA generation is stochastic (random mutations)
- Different MSA pipelines for each system
- **Result:** Inadvertently benchmarking "MSA generation" not "inference"

**The Solution:**
- Precompute MSAs once, use for both systems
- SHA256 hash verification ensures identical inputs
- CLI tool for batch MSA generation
- Transforms into pure **inference benchmark**

**Impact:**
```
Before: NIM MSA ≠ OpenFold MSA → unfair comparison
After:  NIM MSA = OpenFold MSA → apples-to-apples
```

### Problem 2: Weak Statistical Methodology

**The Issue:**
- Only 3 repeats → insufficient for tail latency analysis
- No warmup phase → cold-start effects contaminate measurements
- No percentile tracking → can't define production SLAs
- **Result:** Unreliable p95/p99 estimates, variance not quantified

**The Solution:**
- Separate warmup phase (configurable, default 5-10 passes)
- Measurement passes (configurable, default 20 for percentiles)
- Compute p90, p95, p99 percentiles
- Track coefficient of variation (CV) for stability

**Impact:**
```
Before: 3 measurements → p99 unreliable
After:  20 measurements → robust p95/p99 for SLA definition
```

**Why This Matters:**
- **SLA Definition**: "95% of predictions complete in < 60s"
- **Capacity Planning**: Need p99 for tail latency handling
- **Stability Detection**: High p99/median ratio indicates variance issues

### Problem 3: Limited Accuracy Metrics

**The Issue:**
- Only RMSD and lDDT
- No CASP-standard metrics
- RMSD is sensitive to local errors (misleading for global fold quality)
- **Result:** Can't compare to literature, incomplete accuracy assessment

**The Solution:**
- **TM-score**: Length-normalized, insensitive to local errors
  - >0.5 = same fold (statistically)
  - Used extensively in protein structure prediction literature
- **GDT_TS**: CASP's official metric
  - 0-100 scale, easy interpretation
  - Directly comparable to CASP competition results

**Impact:**
```
Before: RMSD only → misleading for domain-swapped predictions
After:  TM-score + GDT_TS → comprehensive structural similarity
```

### Problem 4: No Cold-Start Measurements

**The Issue:**
- Only measured "warm" inference
- Container startup overhead unknown
- Model loading time not quantified
- **Result:** Can't assess microservice/serverless feasibility

**The Solution:**
- Cold-start suite with container restarts
- Measure:
  - Container startup time (stop → ready)
  - First request latency (cold)
  - Second request latency (warm)
- Separate `cold_start_records.parquet` output

**Impact:**
```
Before: Only warm latency (e.g., 45s)
After:  Container startup (15s) + first request (50s) + warm (45s)
        → Total cold start: 65s
```

**Why This Matters:**
- Serverless deployment: Is cold start acceptable?
- Auto-scaling: How long to scale up?
- Cost optimization: Keep containers warm or accept cold starts?

### Problem 5: Version Reproducibility Gaps

**The Issue:**
- Using `:latest` tags → results not reproducible
- No digest capture → can't verify exact version used
- **Result:** Can't reproduce benchmarks, published results unreliable

**The Solution:**
- Automatic warnings for `:latest` tags
- Capture full container registry digest
- Track in metadata: `container_registry_digest`
- Store MSA hashes: `msa_template_hash`

**Impact:**
```
Before: "We used NIM latest" → Which version??
After:  "We used sha256:abc123..." → Exact reproducibility
```

---

## Methodological Improvements

### 1. Warmup/Measurement Separation

**Rationale:**
Cold-start effects (cache warming, JIT compilation, GPU frequency ramping) contaminate measurements.

**Implementation:**
```yaml
warmup_passes: 10      # Run but discard results
measurement_passes: 20  # Use for statistics
```

**Effect:**
- Eliminates bias from cold starts
- More stable measurements
- Standard practice in systems benchmarking

**When to Use:**
- Always for production benchmarks
- Especially important for TensorRT (compilation caching)

### 2. Target Shuffling

**Rationale:**
Order effects can introduce bias:
- GPU throttling after heavy targets
- Cache effects from similar targets
- Memory fragmentation over time

**Implementation:**
```yaml
shuffle_targets_each_pass: true
```

**Effect:**
- Randomizes order each measurement pass
- Averages out order effects
- Reduces systematic bias

### 3. Percentile Tracking

**Rationale:**
Mean and standard deviation don't capture tail behavior.

**Why Percentiles Matter:**

| Metric | Meaning | Use Case |
|--------|---------|----------|
| **p50 (median)** | Typical performance | User experience baseline |
| **p90** | 90% of requests | Good performance target |
| **p95** | 95% of requests | Common SLA threshold |
| **p99** | 99% of requests | Tail latency, outlier detection |

**Example Interpretation:**
```
Configuration A: median=45s, p95=48s, p99=50s  (stable)
Configuration B: median=42s, p95=55s, p99=75s  (high variance!)
```

Configuration B is faster on average but **unreliable** - some users experience 75s latency!

**Sample Size Requirements:**
- p90: Minimum 10 samples
- p95: Minimum 20 samples (recommended)
- p99: Minimum 100 samples (ideal for production)

### 4. Model Weight Parity

**Rationale:**
NIM uses AlphaFold v2.3.0 official weights. OpenFold can use:
- OpenFold-trained weights (different)
- AlphaFold official weights (same as NIM)

**For Fair Comparison:**
```yaml
openfold:
  weights_source: "alphafold_official"  # Match NIM
```

**Impact:**
Ensures any performance differences are due to implementation (TensorRT optimization, etc.) not parameter differences.

### 5. Identical MSA Inputs

**Rationale:**
The MSA featurization pipeline differs between NIM and OpenFold. Even with the same sequence, independently generated MSAs will differ.

**Solution Flow:**
```
1. Generate MSA once
2. Save in both formats:
   - NIM: A3M file
   - OpenFold: Directory with A3M + Stockholm files
3. Hash verification
4. Use identical MSAs for both systems
```

**Verification:**
```python
# The benchmark automatically verifies:
assert nim_msa_hash == openfold_msa_hash
```

---

## Best Practices

### For Quick Validation (Development)

```yaml
warmup_passes: 1
measurement_passes: 3
msa_depth: 1  # Minimal MSA for speed
```

**Use Case:** Testing code changes, validating setup

### For Production Benchmarks

```yaml
warmup_passes: 5
measurement_passes: 10
shuffle_targets_each_pass: true
precomputed_msa_dir: "data/precomputed/targets_msa128"
inference_only_mode: true
```

**Use Case:** Performance comparisons, vendor selection

### For Publication-Quality Results

```yaml
warmup_passes: 10
measurement_passes: 20  # Enables robust p95/p99
shuffle_targets_each_pass: true
precomputed_msa_dir: "data/precomputed/casp15_msa128"
inference_only_mode: true

nim:
  container_image: "nvcr.io/nim/openfold/openfold2@sha256:..."  # Digest!

openfold:
  weights_source: "alphafold_official"  # Match NIM weights
  commit_hash: "abc123def"  # Pin commit
```

**Use Case:** Academic papers, technical reports

---

## Interpretation Guide

### Understanding Percentile Distributions

**Healthy Distribution (Stable Performance):**
```
median: 45.2s
p90:    46.8s  (+3.5%)
p95:    47.5s  (+5.1%)
p99:    49.1s  (+8.6%)
```
**Interpretation:** Very stable, low variance, production-ready

**Unhealthy Distribution (High Variance):**
```
median: 42.0s
p90:    48.5s  (+15.5%)
p95:    55.2s  (+31.4%)
p99:    78.3s  (+86.4%)
```
**Interpretation:** High variance, investigate outliers before production

**Rule of Thumb:**
- **Good**: p99 < 1.2 × median (20% variance)
- **Acceptable**: p99 < 1.5 × median (50% variance)
- **Problematic**: p99 > 2 × median (100% variance) - investigate!

### TM-score vs RMSD Comparison

Both metrics measure structural similarity, but behave differently:

| Scenario | RMSD | TM-score |
|----------|------|----------|
| Perfect match | 0.0 Å | 1.0 |
| Small local error | High (>5Å) | Still high (>0.8) |
| Correct global fold | May be high | >0.5 |
| Wrong fold | Very high | <0.3 |

**When to Use Which:**
- **RMSD**: Fine-grained accuracy (local precision)
- **TM-score**: Fold correctness (global topology)
- **Both**: Comprehensive assessment

**Example:**
```
Prediction A: RMSD=6.2Å, TM-score=0.72  → Correct fold, local errors
Prediction B: RMSD=3.5Å, TM-score=0.42  → Wrong fold, locally precise
```

Prediction A is actually better despite higher RMSD!

### GDT_TS Interpretation

GDT_TS is the average percentage of residues within distance thresholds (1Å, 2Å, 4Å, 8Å):

| GDT_TS | Quality | CASP Context |
|--------|---------|--------------|
| >80 | Excellent | Top CASP models |
| 60-80 | High accuracy | Good CASP performance |
| 40-60 | Medium accuracy | Acceptable prediction |
| <40 | Low accuracy | Poor prediction |

**CASP14 Winners:** Best models achieved GDT_TS >90 on many targets

---

## Publication Checklist

### Before Publishing Benchmark Results

#### Methodology

- [ ] Warmup passes used (specify number)
- [ ] Sufficient measurement passes (≥10 for p95, ≥20 for p99)
- [ ] Target shuffling enabled
- [ ] Precomputed MSAs used (include SHA256 hashes)
- [ ] Statistical significance tested (if comparing systems)

#### Reproducibility

- [ ] NIM version pinned (digest or exact tag)
- [ ] OpenFold commit hash recorded
- [ ] AlphaFold weights version specified
- [ ] Hardware specs documented (GPU model, VRAM, driver, CUDA)
- [ ] All configuration files included in supplementary materials

#### Results Reporting

- [ ] Report median AND p95/p99 (not just mean)
- [ ] Include sample size (N measurements)
- [ ] Report all accuracy metrics (RMSD, lDDT, TM-score, GDT_TS)
- [ ] Include error bars or confidence intervals
- [ ] State whether results are warm-start or cold-start

#### Data Availability

- [ ] Raw results data available (Parquet/CSV)
- [ ] Precomputed MSAs available or reproducible
- [ ] Configuration files in repository
- [ ] Analysis scripts provided

### Example Methods Section (Paper)

```
Benchmarking Methodology

We compared NIM (nvcr.io/nim/openfold/openfold2@sha256:abc123...)
against OpenFold (commit def456) using AlphaFold v2.3.0 official
weights for model parity. All experiments used precomputed MSAs
(depth=128, SHA256 verified) to ensure identical inputs.

For each configuration, we performed 10 warmup passes followed by
20 measurement passes with target shuffling enabled. We report
median latency and 95th percentile (p95) as recommended for
systems benchmarking [cite: Hoefler & Belli, 2015].

Accuracy was assessed using CASP-standard metrics: TM-score
[Zhang & Skolnick, 2004] and GDT_TS [Zemla, 2003] in addition
to RMSD and lDDT.

Hardware: NVIDIA H100 (80GB), CUDA 12.1, Driver 535.104.05
```

---

## Common Pitfalls to Avoid

### ❌ Don't: Mix Warm and Cold Start Results

**Wrong:**
> "NIM is faster (45s vs 52s)"

**Context:** If NIM was warm-started and OpenFold cold-started, this is misleading!

**Right:**
> "NIM (warm): 45s, OpenFold (warm): 52s" OR
> "NIM (cold): 65s, OpenFold (cold): 78s"

### ❌ Don't: Report Only Mean

**Wrong:**
> "Average latency: 45.2s"

**Problem:** Hides variance! p99 could be 90s.

**Right:**
> "Latency: median=45.2s, p95=47.5s, p99=49.1s (N=20)"

### ❌ Don't: Compare Different MSAs

**Wrong:**
> Using independently generated MSAs for NIM and OpenFold

**Problem:** Benchmarking MSA generation, not inference!

**Right:**
> Use precomputed MSAs with hash verification

### ❌ Don't: Use `:latest` in Production

**Wrong:**
```yaml
container_image: "nvcr.io/nim/openfold/openfold2:latest"
```

**Problem:** Results not reproducible!

**Right:**
```yaml
container_image: "nvcr.io/nim/openfold/openfold2@sha256:abc123..."
```

---

## Advanced Topics

### When to Use Cold-Start vs Warm-Start

**Warm-Start Benchmarks:**
- Long-running services (days/weeks uptime)
- Dedicated inference servers
- High request rates (keep containers warm)

**Cold-Start Benchmarks:**
- Serverless deployments (AWS Lambda, etc.)
- Auto-scaling scenarios (scale from zero)
- Infrequent predictions (containers die between requests)
- Cost-optimized deployments (pay per request)

**Hybrid Approach:**
Report both! Different deployment scenarios need different metrics.

### Dealing with Outliers

If you observe high p99/median ratios:

1. **Check GPU throttling:**
   ```bash
   nvidia-smi -q -d TEMPERATURE,POWER,CLOCKS
   ```

2. **Check system load:**
   ```bash
   top, htop  # CPU competition
   nvidia-smi # GPU competition
   ```

3. **Increase warmup:**
   ```yaml
   warmup_passes: 20  # More thorough warmup
   ```

4. **Use outlier detection:**
   ```python
   from bench.analysis.statistics import detect_outliers_iqr
   df_clean = detect_outliers_iqr(df, "wall_time_s", ["system", "variant"])
   df_no_outliers = df_clean[~df_clean["is_outlier"]]
   ```

5. **Report with and without outliers:**
   > "Median: 45.2s (44.8s excluding outliers, N=18/20)"

---

## References

### Benchmarking Methodology
- Hoefler & Belli (2015). "Scientific Benchmarking of Parallel Computing Systems"
- Jain (1991). "The Art of Computer Systems Performance Analysis"

### Protein Structure Metrics
- Zhang & Skolnick (2004). "Scoring function for automated assessment of protein structure template quality." *Proteins*, 57(4):702-710
- Zemla (2003). "LGA: a method for finding 3D similarities in protein structures." *Nucleic Acids Research*, 31(13):3370-3374
- Mariani et al. (2013). "lDDT: a local superposition-free score for comparing protein structures and models." *Bioinformatics*, 29(21):2722-2728

### AlphaFold & Protein Prediction
- Jumper et al. (2021). "Highly accurate protein structure prediction with AlphaFold." *Nature*, 596:583-589
- CASP15 (2022). https://predictioncenter.org/casp15/

---

## Summary

This benchmark suite implements world-class methodology by:

✅ **Fair Comparison**: Identical precomputed MSAs, model weight parity
✅ **Statistical Rigor**: Warmup/measurement separation, percentile tracking
✅ **Comprehensive Metrics**: CASP-standard accuracy (TM-score, GDT_TS)
✅ **Production Relevance**: Cold-start measurements, tail latency analysis
✅ **Reproducibility**: Version pinning, digest capture, hash verification

**Ready for publication-quality research and production decision-making.**

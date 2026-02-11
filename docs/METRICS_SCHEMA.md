# Metrics Schema Documentation

This document comprehensively describes all metrics collected by the OpenFold2-NIM benchmark suite.

## Table of Contents

- [Performance Metrics](#performance-metrics)
  - [Timing Metrics](#timing-metrics)
  - [GPU Metrics](#gpu-metrics)
  - [CPU Metrics](#cpu-metrics)
  - [Energy Metrics](#energy-metrics)
- [Accuracy Metrics](#accuracy-metrics)
  - [Structural Accuracy](#structural-accuracy)
  - [Confidence Scores](#confidence-scores)
- [Metadata Fields](#metadata-fields)
- [Distribution Statistics](#distribution-statistics)

---

## Performance Metrics

### Timing Metrics

#### `wall_time_s`
- **Type:** float
- **Unit:** seconds
- **Description:** Total wall-clock time from request submission to structure reception
- **Includes:** MSA generation (if applicable), model inference, structure output
- **Interpretation:**
  - Primary performance metric for end-to-end latency
  - For inference-only mode (precomputed MSAs), this measures pure inference time
  - Lower is better

#### `time_to_first_gpu_activity_s`
- **Type:** float
- **Unit:** seconds
- **Description:** Time from request start until first GPU activity detected
- **Purpose:** Measures overhead before GPU utilization begins
- **Interpretation:**
  - Includes data loading, preprocessing, model initialization
  - High values indicate bottlenecks in data pipeline or model loading
  - Lower is better

#### `time_to_first_response_byte_s`
- **Type:** float (optional, NIM only)
- **Unit:** seconds
- **Description:** Time until first byte of HTTP response received (TTFB)
- **Purpose:** Network and server processing latency measurement
- **Interpretation:**
  - Relevant for remote NIM deployments
  - Includes network latency + server queue time + initial processing
  - Lower is better

---

### GPU Metrics

#### `gpu_hours_per_prediction`
- **Type:** float
- **Unit:** GPU-hours
- **Description:** Total GPU time consumed (sum across all GPUs if multi-GPU)
- **Calculation:** `wall_time_s * num_gpus / 3600`
- **Purpose:** Resource usage for cost estimation
- **Interpretation:**
  - Used for cloud cost calculations (e.g., $2.50/GPU-hr * gpu_hours)
  - Lower is better for cost efficiency

#### `gpu_sm_util_avg_pct`
- **Type:** float
- **Unit:** percent (0-100)
- **Description:** Average GPU streaming multiprocessor (SM) utilization
- **Sampling:** Measured at configurable interval (default: 50ms)
- **Purpose:** Assess GPU compute efficiency
- **Interpretation:**
  - High values (>80%) indicate good GPU utilization
  - Low values (<40%) suggest CPU bottlenecks or memory-bound operations
  - Higher is better for compute efficiency

#### `gpu_sm_util_peak_pct`
- **Type:** float
- **Unit:** percent (0-100)
- **Description:** Peak GPU SM utilization during prediction
- **Purpose:** Identify maximum GPU load
- **Interpretation:**
  - Should approach 100% for compute-bound workloads
  - Lower peaks may indicate intermittent CPU bottlenecks

#### `gpu_power_avg_w`
- **Type:** float
- **Unit:** watts
- **Description:** Average GPU power draw during prediction
- **Sampling:** Measured at configurable interval (default: 50ms)
- **Purpose:** Energy efficiency analysis
- **Interpretation:**
  - Typical range: 100-450W depending on GPU model and utilization
  - Higher power may indicate less efficient operations
  - Compare across variants to assess energy tradeoffs

#### `gpu_energy_wh`
- **Type:** float
- **Unit:** watt-hours
- **Description:** Total GPU energy consumed for the prediction
- **Calculation:** Integral of power over time
- **Purpose:** Total energy footprint measurement
- **Interpretation:**
  - Lower is better for energy efficiency
  - Multiply by electricity cost for energy cost per prediction

---

### CPU Metrics

#### `cpu_util_avg_pct`
- **Type:** float
- **Unit:** percent (0-100 per core, can exceed 100 for multi-core)
- **Description:** Average CPU utilization during prediction
- **Purpose:** Detect CPU bottlenecks
- **Interpretation:**
  - Very high values (>300% on 8-core) may indicate CPU bottleneck
  - Low values (<50%) indicate GPU-bound workload

#### `cpu_rss_peak_mb`
- **Type:** float
- **Unit:** megabytes (MB)
- **Description:** Peak resident set size (physical RAM) used by process
- **Purpose:** Memory footprint measurement
- **Interpretation:**
  - Critical for deployment sizing
  - Exceeding available RAM causes swapping and severe slowdown

---

### Memory Metrics

#### `gpu_mem_peak_mb`
- **Type:** float
- **Unit:** megabytes (MB)
- **Description:** Peak GPU memory allocated during prediction
- **Purpose:** GPU memory requirement measurement
- **Interpretation:**
  - Must be < total GPU VRAM (e.g., 24GB = 24576 MB for RTX 4090)
  - Higher memory usage may limit batch size or multi-GPU utilization

---

### Energy Metrics

Energy metrics enable analysis of computational sustainability and operational costs.

#### `gpu_energy_wh`
- **Type:** float
- **Unit:** watt-hours (Wh)
- **Description:** Total GPU energy consumed
- **Cost Calculation:** `energy_wh * electricity_cost_per_kwh / 1000`
  - Example: 0.5 Wh * $0.12/kWh / 1000 = $0.00006 per prediction

---

## Accuracy Metrics

Accuracy metrics require ground truth structures (`ground_truth_coords` in target definition).

### Structural Accuracy

#### `ca_rmsd`
- **Type:** float (optional)
- **Unit:** Ångströms (Å)
- **Description:** Root mean square deviation of Cα atoms after optimal Kabsch alignment
- **Formula:** `√(Σ(d²ᵢ) / N)` where dᵢ is distance between atom pairs
- **Interpretation:**
  - 0-2Å: Excellent (near-native structure)
  - 2-5Å: Good (correct fold)
  - 5-10Å: Moderate (partial fold correctness)
  - >10Å: Poor (incorrect fold)
- **Note:** Sensitive to local errors, can be high even for correct global fold
- **Lower is better**

#### `ca_lddt`
- **Type:** float (optional)
- **Unit:** 0-100 scale
- **Description:** Local Distance Difference Test - measures local structure preservation
- **Calculation:** Percentage of Cα-Cα distances within 4 thresholds (0.5, 1, 2, 4Å)
- **Interpretation:**
  - >90: Very high accuracy
  - 70-90: High accuracy
  - 50-70: Medium accuracy
  - <50: Low accuracy
- **Advantage:** More robust to domain movements than RMSD
- **Higher is better**

#### `tm_score`
- **Type:** float (optional)
- **Unit:** 0-1 scale
- **Description:** Template Modeling score - length-normalized structural similarity
- **Formula:** `(1/L) * Σ[1 / (1 + (dᵢ/d₀)²)]`
  - d₀ = 1.24 * (L-15)^(1/3) - 1.8 (length-dependent scale)
- **Interpretation:**
  - >0.5: Same fold (statistically significant)
  - >0.6: High structural similarity
  - <0.17: Random similarity
- **Advantage:** Length-independent, better for comparing different targets
- **Higher is better**
- **Reference:** Zhang & Skolnick (2004), *Proteins* 57(4):702-710

#### `gdt_ts`
- **Type:** float (optional)
- **Unit:** 0-100 scale
- **Description:** Global Distance Test - Total Score (CASP standard metric)
- **Calculation:** Average of percentages of residues within 1Å, 2Å, 4Å, and 8Å after superposition
- **Interpretation:**
  - >70: High accuracy (CASP top models)
  - 50-70: Good quality model
  - 30-50: Moderate quality
  - <30: Low quality
- **Use Case:** Primary metric in CASP competitions
- **Higher is better**
- **Reference:** Zemla (2003), *Nucleic Acids Res* 31(13):3370-3374

---

### Confidence Scores

#### `mean_plddt`
- **Type:** float
- **Unit:** 0-100 scale
- **Description:** Predicted lDDT - model's confidence in its own prediction
- **Calculation:** Mean of per-residue pLDDT scores from model output
- **Interpretation:**
  - >90: Very high confidence
  - 70-90: Confident
  - 50-70: Low confidence
  - <50: Very low confidence (likely disordered or incorrect)
- **Note:** Prediction quality, not accuracy (no ground truth needed)
- **Higher is better**

---

## Metadata Fields

### Identifiers

- **`run_id`**: Unique identifier for benchmark run (format: `run_YYYYMMDD_HHMMSS`)
- **`suite`**: Suite name (e.g., "casp15_accuracy", "msa_scaling")
- **`target_id`**: Target sequence identifier (e.g., "T1234", "seq_300aa")
- **`system`**: System being benchmarked ("nim" or "openfold")
- **`variant`**: Configuration variant (e.g., "nim_trt_models-3", "openfold_bf16_model3_ptm")

### Input Parameters

- **`sequence_length`**: Number of amino acids in query sequence
- **`msa_depth`**: Number of sequences in MSA (including query)
- **`models_used`**: List of model parameter sets used (e.g., `[3]` or `[1,2,3,4,5]`)
- **`msa_template_hash`**: SHA256 hash of MSA content (for reproducibility)

### Measurement Tracking

- **`pass_index`**: Which measurement pass (0-indexed)
  - Distinguishes warmup from measurement passes
  - Multiple measurements enable percentile calculation
- **`is_warmup`**: Boolean flag indicating warmup run (results discarded)
- **`repeat_index`**: **DEPRECATED** - use `pass_index` instead

### File Paths

- **`output_structure_path`**: Path to predicted structure PDB file
- **`timeseries_path`**: Path to GPU/CPU timeseries data (optional)

---

## Distribution Statistics

For measurement passes with `measurement_passes >= 10`, the analysis tools compute distribution statistics:

### Central Tendency
- **`mean`**: Arithmetic mean
- **`median`**: 50th percentile (p50) - robust to outliers

### Spread
- **`std`**: Standard deviation
- **`min`**: Minimum value
- **`max`**: Maximum value

### Tail Latencies
- **`p90`**: 90th percentile - 90% of runs complete by this time
- **`p95`**: 95th percentile - important for SLA definition
- **`p99`**: 99th percentile - worst-case latency for most users

### Sample Size
- **`count`**: Number of measurements in group

### Interpretation

Percentiles are critical for production systems:
- **Median (p50)**: Typical user experience
- **p95**: SLA target (e.g., "95% of predictions complete in <60s")
- **p99**: Tail latency - critical for user satisfaction
  - If p99 >> median, indicates high variability or outliers

**Example:**
```
median: 45.2s
p95:    48.1s
p99:    52.3s
```
This shows stable performance with minimal tail latency (p99 only 16% higher than median).

---

## Cold Start Metrics

For `suite_type: "cold_start"` benchmarks:

- **`container_start_time_s`**: Time from container stop to ready state
- **`first_request_time_s`**: Latency of first request after cold start
- **`second_request_time_s`**: Latency of second request (warmed)
- **`restart_index`**: Which cold start iteration

**Purpose:** Quantify microservice overhead and initialization costs.

---

## NIM-Specific Metadata

- **`container_digest`**: Docker image digest from NIM metadata endpoint
- **`reported_version`**: NIM version string
- **`backend`**: "tensorrt" or "torch"
- **`container_registry_digest`**: Full registry digest (e.g., `sha256:abc123...`)
- **`using_latest_tag`**: Boolean - true if using `:latest` tag

---

## OpenFold-Specific Metadata

- **`git_commit`**: Git commit hash of OpenFold repository
- **`python_version`**: Python version string
- **`torch_version`**: PyTorch version
- **`openfold_version`**: OpenFold package version

---

## Units Summary

| Metric Type | Unit | Symbol |
|-------------|------|--------|
| Time | seconds | s |
| GPU Time | GPU-hours | GPU-hr |
| Utilization | percent | % |
| Power | watts | W |
| Energy | watt-hours | Wh |
| Memory | megabytes | MB |
| Distance | Ångströms | Å |
| Scores | unitless (0-1 or 0-100) | - |

---

## Data Formats

Results are stored in multiple formats:

1. **JSONL** (`.jsonl`): Newline-delimited JSON for streaming
2. **Parquet** (`.parquet`): Columnar format for efficient analysis
3. **CSV** (`.csv`): Human-readable exports for spreadsheets

All formats contain identical data - choose based on your analysis tools.

---

## Example Record

```json
{
  "run_id": "run_20260210_143022",
  "suite": "casp15_accuracy",
  "target_id": "T1234",
  "system": "nim",
  "variant": "nim_trt_models-3",
  "wall_time_s": 45.3,
  "time_to_first_gpu_activity_s": 2.1,
  "time_to_first_response_byte_s": 0.05,
  "gpu_hours_per_prediction": 0.0126,
  "gpu_sm_util_avg_pct": 87.4,
  "gpu_sm_util_peak_pct": 98.2,
  "gpu_power_avg_w": 320.5,
  "gpu_energy_wh": 4.03,
  "gpu_mem_peak_mb": 8192,
  "cpu_rss_peak_mb": 4096,
  "cpu_util_avg_pct": 150.2,
  "ca_rmsd": 2.34,
  "ca_lddt": 82.5,
  "tm_score": 0.68,
  "gdt_ts": 71.2,
  "mean_plddt": 88.3,
  "sequence_length": 234,
  "msa_depth": 128,
  "models_used": [3],
  "pass_index": 5,
  "is_warmup": false,
  "msa_template_hash": "a3f2e8b4c9d7..."
}
```

---

## Best Practices

1. **Always use precomputed MSAs** for inference-only benchmarks
2. **Run ≥10 measurement passes** to compute reliable percentiles
3. **Separate warmup from measurement** to avoid cold-start bias
4. **Pin versions** using digest hashes for reproducibility
5. **Monitor p95/p99** not just medians for production planning
6. **Compare identical configurations** (same MSA depth, models, sequence length)

---

## References

- **TM-score:** Zhang & Skolnick (2004). *Proteins*, 57(4):702-710
- **GDT_TS:** Zemla (2003). *Nucleic Acids Research*, 31(13):3370-3374
- **lDDT:** Mariani et al. (2013). *Bioinformatics*, 29(21):2722-2728
- **AlphaFold2:** Jumper et al. (2021). *Nature*, 596:583-589

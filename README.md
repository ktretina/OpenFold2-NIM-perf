# OpenFold2-NIM Performance Benchmark

World-class benchmarking suite for comparing NVIDIA OpenFold2 NIM microservice against open-source OpenFold with publication-quality statistical rigor.

> **🚀 Deploying on Colossus?** See [COLOSSUS_DEPLOY.md](COLOSSUS_DEPLOY.md) for push-button setup (5 minutes from clone to running benchmarks)

## Features

### Core Capabilities
- **Out-of-the-box execution**: Clone → bootstrap → run benchmarks → view HTML report
- **Comprehensive metrics**: Latency, GPU utilization, memory, energy, accuracy
- **Pareto frontier analysis**: Find optimal accuracy/performance trade-offs
- **Multi-GPU support**: Run on A100, H100, or other GPUs
- **Colossus-optimized**: Scripts and docs for NVIDIA Colossus infrastructure

### NEW: World-Class Benchmarking Features
- **CASP-standard accuracy metrics**: TM-score, GDT_TS in addition to RMSD/lDDT
- **Statistical rigor**: Proper warmup/measurement separation, p90/p95/p99 percentiles
- **Apples-to-apples comparison**: Precomputed MSAs ensure identical inputs for both systems
- **Cold-start measurements**: Quantify container startup and initialization overhead
- **Version tracking**: Automatic warnings for `:latest` tags, digest capture for reproducibility
- **Tail latency analysis**: Identify performance variance with percentile tracking

## Quick Start

### Prerequisites

- NVIDIA GPU with drivers
- Docker with nvidia-container-toolkit
- NGC API key (for NIM): https://catalog.ngc.nvidia.com/
- Python 3.10+
- 100 GB free disk space

### Installation

```bash
git clone https://github.com/your-org/openfold2-bench.git
cd openfold2-bench

# Install dependencies with pip
pip install -e .

# Optional: Install PNG export support (recommended)
pip install -e .[plots]

# Set NGC API key
export NGC_API_KEY="your_key_here"
```

**Note:** PNG export requires kaleido, which can be difficult to install on some HPC systems. If you skip `[plots]`, the benchmark will still work but will only generate HTML plots (not PNG).

### Running on Colossus

The benchmark suite includes production-ready Colossus integration with:
- **One-click execution** - Single command runs entire workflow
- **Hardware auto-detection** - Automatic GPU/storage detection and optimization
- **Resumable benchmarks** - Checkpoint and resume long-running jobs
- **Campaign mode** - Aggregate results across GPU types

#### Quick Start (One-Click)

```bash
# One command to bootstrap, configure, and run
./scripts/colossus/run.sh configs/default.yaml
```

This automatically:
1. Bootstraps environment (first time only)
2. Detects hardware (GPU type, VRAM, fast storage)
3. Generates optimized config
4. Validates prerequisites
5. Runs benchmark with checkpointing

#### Manual Workflow

```bash
# 1. Bootstrap (first time only)
./scripts/colossus/bootstrap.sh
source .env.colossus

# 2. Detect hardware and generate config
bench colossus detect
bench colossus auto-config --base-config configs/default.yaml

# 3. Validate environment
bench preflight

# 4. Run benchmark
bench run --config configs/generated/auto_*.yaml

# Results will be at: $PERSIST_DIR/results/run_*/
```

#### Campaign Mode (Multi-GPU Studies)

```bash
# Create campaign for GPU comparison
bench colossus campaign-create campaigns/gpu_comparison --name "H100 vs A100"

# Run on H100
bench run --config configs/auto_h100.yaml
bench colossus campaign-add --campaign-dir campaigns/gpu_comparison \
  --run-dir results/run_h100

# Run on A100
bench run --config configs/auto_a100.yaml
bench colossus campaign-add --campaign-dir campaigns/gpu_comparison \
  --run-dir results/run_a100

# Aggregate and compare
bench colossus campaign-aggregate campaigns/gpu_comparison
bench colossus campaign-report campaigns/gpu_comparison

# View report
open campaigns/gpu_comparison/campaign_report.html
```

See [Colossus Runbook](docs/COLOSSUS_RUNBOOK.md) for detailed operations guide.

### Running Locally

```bash
# Preflight checks
bench preflight

# Run default benchmark (~1-2 hours)
bench run --config configs/default.yaml

# View results
open results/run_*/analysis/report.html
```

## Datasets

The benchmark suite supports multiple protein datasets:

### Classic Proteins (`targets.yaml`)
- **20 well-studied proteins** covering diverse fold types
- Size range: 20-260 residues
- All fold types: all-α, all-β, α+β
- **Use for:** Quick validation and development

### CASP15 (`casp15_targets.yaml`)
- **18 CASP15 (2022) targets** from the Critical Assessment of Structure Prediction
- Categories: Free Modeling (FM), Template-Based Modeling Easy/Hard (TBM-easy/TBM-hard)
- Size range: 112-324 residues
- **Use for:** Research-grade benchmarking and publication-quality results

To run CASP15 benchmark:
```bash
bench run --config configs/casp15.yaml
```

## Configuration

### Available Benchmark Configurations

**Standard Benchmarks:**
- `default.yaml`: Fast benchmark with accuracy evaluation (~1-2 hours)
- `casp15.yaml`: CASP15 benchmark with deeper MSA (~3-4 hours)
- `full_matrix.yaml`: Comprehensive with scaling studies (~8-12 hours)

**World-Class Benchmarks (NEW):**
- `inference_only_benchmark.yaml`: Apples-to-apples with precomputed MSAs
- `statistical_rigor.yaml`: 20 measurement passes for reliable percentiles
- `nim_backend_comparison.yaml`: TensorRT vs Torch comparison
- `cold_start.yaml`: Container initialization overhead measurements
- `world_class_benchmark.yaml`: Comprehensive publication-quality suite

### Example Configuration

```yaml
gpu:
  device_ids: [0]
  sampling_interval_ms: 50

nim:
  enabled: true
  container_image: "nvcr.io/nim/openfold/openfold2:latest"
  cache_dir: "${FAST_CACHE:-$HOME}/nim_cache"
  backend: "tensorrt"
  model_sets:
    - [3]              # Single model
    - [1, 2, 3, 4, 5]  # Ensemble

suites:
  - name: accuracy_small
    targets_file: bench/dataset/targets.yaml
    msa_depth: 1
    repeats: 3
```

## Advanced Benchmark Modes

### Inference-Only Benchmark (Apples-to-Apples)

For fair comparison, use precomputed MSAs to ensure identical inputs:

```bash
# Step 1: Generate precomputed MSAs
python scripts/precompute_msas.py \
  --targets bench/dataset/casp15_targets.yaml \
  --output data/precomputed/casp15_msa128 \
  --msa-depth 128

# Step 2: Run inference-only benchmark
bench run --config configs/inference_only_benchmark.yaml
```

This eliminates MSA generation variance and measures pure inference performance.

### Statistical Rigor Benchmark

For publication-quality results with proper statistics:

```bash
bench run --config configs/statistical_rigor.yaml
```

Features:
- 10 warmup passes (excluded from results)
- 20 measurement passes (for reliable p95/p99 calculation)
- Target shuffling between passes
- Distribution statistics (median, p90, p95, p99)

### Cold-Start Benchmark

Measure container startup and initialization overhead:

```bash
bench run --config configs/cold_start.yaml
```

Measures:
- Container startup time (stop → ready)
- First request latency (cold)
- Second request latency (warm)

### NIM Backend Comparison

Compare TensorRT vs Torch backends:

```bash
# Run TensorRT
bench run --config configs/nim_backend_comparison.yaml

# Edit config: set backend to "torch"
# Run again
bench run --config configs/nim_backend_comparison.yaml
```

## Best Practices

### Version Pinning for Reproducibility

**Don't use `:latest` tags in production!**

```yaml
# ❌ NOT RECOMMENDED
nim:
  container_image: "nvcr.io/nim/openfold/openfold2:latest"

# ✅ RECOMMENDED - Pin to specific version
nim:
  container_image: "nvcr.io/nim/openfold/openfold2:1.0"

# ✅ BEST - Pin to specific digest
nim:
  container_image: "nvcr.io/nim/openfold/openfold2@sha256:abc123..."
```

The benchmark automatically:
- Warns when using `:latest` tags
- Captures container digests in results
- Tracks exact versions for reproducibility

### Statistical Rigor

For publication-quality benchmarks:

1. **Use warmup passes** to eliminate cold-start effects
   ```yaml
   warmup_passes: 5-10  # Recommended
   ```

2. **Run sufficient measurements** for tail latency analysis
   ```yaml
   measurement_passes: 20  # Enables reliable p95/p99
   ```

3. **Enable target shuffling** to reduce order effects
   ```yaml
   shuffle_targets_each_pass: true
   ```

4. **Use precomputed MSAs** for inference-only comparison
   ```yaml
   precomputed_msa_dir: "data/precomputed/casp15_msa128"
   inference_only_mode: true
   ```

### Model Parity

Ensure fair comparison by using AlphaFold official weights:

```yaml
openfold:
  weights_source: "alphafold_official"  # Match NIM's weights
```

## CLI Reference

```bash
# Validate environment
bench preflight

# Prepare datasets
bench prepare-data --config configs/default.yaml

# Run benchmark
bench run --config configs/default.yaml --output-dir results/run_001

# Generate analysis
bench analyze results/run_001

# Generate analysis with README update
bench analyze results/run_001 --update-readme

# Use latest symlink for most recent run
bench analyze results/latest --update-readme

# Aggregate multi-machine results
bench aggregate results/*/manifest.json --output-dir results/aggregate
```

## Results Schema

Each benchmark run produces:
- `manifest.json`: Run metadata and environment info
- `records.parquet`: Per-prediction metrics (fast analysis)
- `records.jsonl`: Human-readable metrics
- `timeseries/*.parquet`: GPU/CPU monitoring data
- `structures/`: Predicted protein structures
- `analysis/report.html`: Interactive HTML report with plots
- `analysis/data/*.csv`: Exported CSV data files for external analysis

### CSV Data Exports

The analyze command automatically exports CSV files for all plots and analyses:

- `raw_records.csv` - All prediction records
- `summary_statistics.csv` - Aggregated performance metrics
- `pareto_data.csv` - Pareto frontier analysis data
- `scaling_data.csv` - Sequence length scaling data
- `accuracy_per_target.csv` - Per-target accuracy breakdown

These CSV files enable:
- External data analysis and visualization
- Publication-quality figure generation
- Integration with other tools and workflows
- Long-term data archival and reproducibility

## Key Metrics

### Performance
- **Wall time**: End-to-end latency per prediction
- **GPU hours**: Normalized compute cost
- **Time-to-first-GPU**: Startup/overhead latency
- **GPU utilization**: SM and memory utilization
- **Energy**: Power consumption (Wh)

### Accuracy
- **Cα RMSD**: Coordinate accuracy after Kabsch alignment (Ångströms)
- **Cα lDDT**: Local distance difference test (0-100)
- **TM-score**: Length-normalized structural similarity (0-1, >0.5 = same fold)
- **GDT_TS**: CASP standard metric (0-100, measures % residues within distance thresholds)
- **Mean pLDDT**: Model confidence (0-100)

## Documentation

- [Colossus Runbook](docs/COLOSSUS_RUNBOOK.md): Operations guide for Colossus
- [Methodology](docs/METHODOLOGY.md): Benchmarking methodology and fairness
- [Metrics Schema](docs/METRICS_SCHEMA.md): Complete metrics documentation
- [API Integration](docs/API_INTEGRATION.md): NIM and OpenFold integration details

## Example Output

### Generated Reports & Visualizations

The benchmark generates comprehensive HTML reports with interactive Plotly visualizations:

**Performance Analysis:**
1. **Latency distribution analysis**: Violin plots, percentile comparison (NEW)
2. **Tail latency analysis**: p99/median ratios for stability assessment (NEW)
3. **Pareto frontier plot**: Accuracy vs performance trade-offs
4. **Scaling analysis**: Sequence length and MSA depth scaling
5. **GPU utilization**: Distribution and time-series plots

**Accuracy Analysis:**
6. **Per-target accuracy**: RMSD, lDDT, TM-score, GDT_TS breakdown (NEW)
7. **Energy efficiency**: Power consumption vs accuracy trade-offs

**Data Exports:**
- `raw_records.csv`: All prediction results
- `latency_distributions.csv`: p50/p90/p95/p99 statistics (NEW)
- `accuracy_distributions.csv`: Statistical distribution of accuracy metrics (NEW)
- `summary_statistics.csv`: Aggregated performance summary
- `cold_start_records.parquet`: Container initialization metrics (NEW)

<!-- BENCHMARK_RESULTS -->
<!-- Results will be inserted here when using: bench analyze results/latest --update-readme -->
<!-- /BENCHMARK_RESULTS -->

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black bench/
ruff check bench/

# Type checking
mypy bench/
```

## Troubleshooting

### NIM Container Won't Start
- Check NGC_API_KEY is set: `echo $NGC_API_KEY`
- Check port 8000 is available: `lsof -i :8000`
- Check GPU access: `docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu20.04 nvidia-smi`

### Out of Disk Space
- Clean old results: `rm -rf results/run_*` (after backing up)
- Clean Docker: `docker system prune -a`

### Slow Performance
- Ensure using fast storage (primary drive on Colossus, not volume)
- Check GPU not throttling: `nvidia-smi dmon -s puct`

## License

MIT License - see LICENSE file

## Citation

If you use this benchmark in your research, please cite:

```bibtex
@software{openfold2_nim_bench,
  title={OpenFold2-NIM Performance Benchmark},
  author={NVIDIA Performance Team},
  year={2025},
  url={https://github.com/your-org/openfold2-bench}
}
```

## Contributing

Contributions welcome! Please open an issue or pull request.

## Support

For questions or issues:
- GitHub Issues: https://github.com/your-org/openfold2-bench/issues
- NVIDIA Developer Forums: https://forums.developer.nvidia.com/
